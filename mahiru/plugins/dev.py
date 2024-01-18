import asyncio
import inspect
import io
import os
import pyrogram
import re
import sys
import socket
import traceback
import uuid

from datetime import datetime
from html import escape
from mahiru import PREFIX
from mahiru.mahiru import Mahiru
from mahiru.util.error import format_exception
from mahiru.util.filters import owner_only
from mahiru.util.system import run_command
from mahiru.util.time import format_duration_us, usec, readable_time
from meval import meval
from pyrogram import filters, __version__
from pyrogram.raw.all import layer
from pyrogram.utils import run_sync
from typing import Any, Optional, Tuple

@Mahiru.on_message((filters.command("alive", PREFIX) | filters.command("on", PREFIX)) & owner_only)
async def alive(c, m):
    db = c.db['bot_settings']
    alive_text = "Bot services is running...\n"
    alive_text += "•  ⚙️ PyroFork    : v{} (Layer {})\n".format(__version__,layer)
    alive_text += "•  🐍 Python         : v{}".format(sys.version.split(' ')[0])
    start = datetime.now()
    msg = await m.reply_text(alive_text+"\n•  📶 Latency        : ⏳")
    end = datetime.now()
    latency = (end - start).microseconds / 1000
    text = alive_text+"\n•  📶 Latency        : {}ms".format(latency)
    data = await db.find_one({'name': 'uptime'})
    start_time = data['value']
    uptime = readable_time(start_time)
    text = text+"\n•  🕐 Uptime        : {}".format(uptime)
    await msg.edit(text)

@Mahiru.on_message(filters.command("eval", PREFIX) & owner_only)
@Mahiru.on_edited_message(filters.command("eval", PREFIX) & owner_only)
async def exec_eval(c,m):
    text = m.text if m.text is not None else m.caption
    text = text.split(None,1)
    if not len(text) > 1:
        return
    code = text[1]
    out_buf = io.StringIO()
    async def _eval() -> Tuple[str, Optional[str]]:
        # Message sending helper for convenience
        async def send(*args: Any, **kwargs: Any) -> pyrogram.types.Message:
            return await m.reply(*args, **kwargs)

        # Print wrapper to capture output
        # We don't override sys.stdout to avoid interfering with other output
        def _print(*args: Any, **kwargs: Any) -> None:
            if "file" not in kwargs:
                kwargs["file"] = out_buf
                return print(*args, **kwargs)

        eval_vars = {
            # Contextual info
            "loop": c.loop,
            "client": c,
            "stdout": out_buf,
            "db": c.db,
            # Convenience aliases
            "c": c,
            "m": m,
            "msg": m,
            "message": m,
            "r": m.reply_to_message,
            "reply": m.reply_to_message,
            "raw": pyrogram.raw,
            # Helper functions
            "send": send,
            "print": _print,
            # Built-in modules
            "inspect": inspect,
            "os": os,
            "re": re,
            "sys": sys,
            "traceback": traceback,
            # Third-party modules
            "pyrogram": pyrogram
        }

        try:
            return "", await meval(code, globals(), **eval_vars)
        except Exception as e:  # skipcq: PYL-W0703
            # Find first traceback frame involving the snippet
            first_snip_idx = -1
            tb = traceback.extract_tb(e.__traceback__)
            for i, frame in enumerate(tb):
                if frame.filename == "<string>" or frame.filename.endswith("ast.py"):
                    first_snip_idx = i
                    break

            # Re-raise exception if it wasn't caused by the snippet
            if first_snip_idx == -1:
                raise e
            # Return formatted stripped traceback
            stripped_tb = tb[first_snip_idx:]
            formatted_tb = format_exception(e, tb=stripped_tb)
            return "⚠️ Error executing snippet\n\n", formatted_tb

    before = usec()
    prefix, result = await _eval()
    after = usec()

    # Always write result if no output has been collected thus far
    if not out_buf.getvalue() or result is not None:
        print(result, file=out_buf)

    el_us = after - before
    el_str = format_duration_us(el_us)

    out = out_buf.getvalue()
    # Strip only ONE final newline to compensate for our message formatting
    if out.endswith("\n"):
        out = out[:-1]

    code = c.redact_message(code)
    out = c.redact_message(out)

    result = f"""{prefix}<b>In:</b>
<pre language="python">{escape(code)}</pre>
<b>Out:</b>
<pre>{escape(out)}</pre>
Time: {el_str}"""

    if len(result) > 4096:
        with io.BytesIO(str.encode(out)) as out_file:
            out_file.name = str(uuid.uuid4()).split("-")[0].upper() + ".TXT"
            caption = f"""{prefix}<b>In:</b>
<pre language="python">{escape(code)}</pre>

Time: {el_str}"""
            await m.reply_document(
                document=out_file, caption=caption, disable_notification=True,parse_mode=pyrogram.enums.parse_mode.ParseMode.HTML
            )
        return None

    await m.reply_text(
        result,
        parse_mode=pyrogram.enums.parse_mode.ParseMode.HTML,
        disable_web_page_preview=True
    )

@Mahiru.on_message(filters.command("sh", PREFIX) & owner_only)
async def cmd_shell(c, m) -> Optional[str]:
    text = m.text.split(None,1)
    if not len(text) > 1:
        return
    snip = text[1]
    if not snip:
        return "Give me command to run."

    msg = await m.reply_text("Running snippet...")
    before = usec()

    try:
        stdout, _, ret = await run_command(
            snip, shell=True, timeout=120  # skipcq: BAN-B604
        )
    except FileNotFoundError as E:
        after = usec()
        await msg.edit(
            f"""<b>Input</b>:<pre language="bash">{escape(snip)}</pre>
<b>Output</b>:
⚠️ Error executing command:
<pre language="bash">{escape(format_exception(E))}</pre>

f"Time: {format_duration_us(after - before)}""",
            parse_mode=pyrogram.enums.ParseMode.HTML,
        )
        return
    except asyncio.TimeoutError:
        after = usec()
        await msg.edit(
            f"""<b>Input</b>:
<pre language="bash">{escape(snip)}</pre>
<b>Output</b>:
🕑 Snippet failed to finish within 2 minutes."""
            f"Time: {format_duration_us(after - before)}",
            parse_mode=pyrogram.enums.ParseMode.HTML,
            disable_web_page_preview=True
        )
        return

    after = usec()

    el_us = after - before
    el_str = f"\nTime: {format_duration_us(el_us)}"

    if not stdout:
        stdout = "[no output]"
    elif stdout[-1:] != "\n":
        stdout += "\n"

    stdout = c.redact_message(stdout)
    err = f"⚠️ Return code: {ret}" if ret != 0 else ""
    result = f"""<b>Input</b>:
<pre language="bash">{escape(snip)}</pre>
<b>Output</b>:
<pre language="bash">{escape(stdout)}</pre>{err}{el_str}"""

    if len(result) > 4096:
        with io.BytesIO(str.encode(stdout)) as out_file:
            out_file.name = str(uuid.uuid4()).split("-")[0].upper() + ".TXT"
            caption = f"""<b>Input</b>:
<pre language="bash">{escape(snip)}</pre>

Time: {el_str}"""
            await msg.delete()
            await m.reply_document(
                document=out_file, caption=caption, disable_notification=True,parse_mode=pyrogram.enums.parse_mode.ParseMode.HTML
            )
        return None
    await msg.edit(
        result,
        parse_mode=pyrogram.enums.ParseMode.HTML,
        disable_web_page_preview=True
    )

@Mahiru.on_message(filters.command("restart", PREFIX) & owner_only)
async def cmd_restart(c,m):
    msg = await m.reply_text("Restarting...")
    await asyncio.sleep(2)
    await msg.edit("✅ Bot restarted.")
    await c.stop(block=False)
    os.execl(sys.executable, sys.executable, "-m", "mahiru")
