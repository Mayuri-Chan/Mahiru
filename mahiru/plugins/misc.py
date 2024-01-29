import importlib
import re
from mahiru import HELP_COMMANDS, PREFIX
from mahiru.lang import list_all_lang
from mahiru.mahiru import Mahiru
from mahiru.util.filters import admin_only
from mahiru.util.misc import paginate_plugins
from pyrogram import enums, filters, __version__
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

__PLUGIN__ = "misc"
__HELP__ = "misc_help"

@Mahiru.on_message(filters.command("start", PREFIX))
async def start_msg(c, m):
    chat_id = m.chat.id
    if m.chat.type == enums.ChatType.CHANNEL:
        return await m.edit_text("chat_id: `{}`".format(m.chat.id))
    if m.chat.type != enums.ChatType.PRIVATE:
        return await m.reply_text(await c.tl(chat_id, "pm_me"))
    keyboard = [[InlineKeyboardButton(text=(await c.tl(chat_id, "donate")), callback_data="donate")]]
    text = "hello!\n"
    text += "This bot is under development."
    text += "\nYou can contact my master [here](tg://user?id={})\n\n".format(c.config['bot']['OWNER'])
    text += "Powered by [Pyrofork v{}](https://pyrofork.mayuri.my.id)".format(__version__)
    await m.reply_text(text,reply_markup=InlineKeyboardMarkup(keyboard))

async def _create_donate(_, __, query):
    if re.match(r"donate", query.data):
        return True

donate_callback = filters.create(_create_donate)

@Mahiru.on_callback_query(donate_callback)
async def _donate_start(c,q):
    m = q.message
    text = await c.tl(m.chat.id, 'donate_text')
    button = [
        [
            InlineKeyboardButton(text="Github Sponsors", url="https://github.com/sponsors/Mayuri-Chan")
        ],
        [
            InlineKeyboardButton(text="Ko-FI", url="https://ko-fi.com/wulan17"),
            InlineKeyboardButton(text="Saweria", url="https://saweria.co/wulan17"),
            InlineKeyboardButton(text="Trakteer", url="https://trakteer.id/wulan17")
        ],
        [
            InlineKeyboardButton(text="Paypal", url="https://paypal.me/wulan17")
        ]
    ]
    await m.edit_text(text, reply_markup=InlineKeyboardMarkup(button))

@Mahiru.on_message(filters.command("donate", PREFIX))
async def cmd_donate(c,m):
    text = await c.tl(m.chat.id, 'donate_text')
    button = [
        [
            InlineKeyboardButton(text="Github Sponsors", url="https://github.com/sponsors/Mayuri-Chan")
        ],
        [
            InlineKeyboardButton(text="Ko-FI", url="https://ko-fi.com/wulan17"),
            InlineKeyboardButton(text="Saweria", url="https://saweria.co/wulan17"),
            InlineKeyboardButton(text="Trakteer", url="https://trakteer.id/wulan17")
        ],
        [
            InlineKeyboardButton(text="Paypal", url="https://paypal.me/wulan17")
        ]
    ]
    await m.reply_text(text, reply_markup=InlineKeyboardMarkup(button))


async def help_parser(c, chat_id, text, keyboard=None):
    if not keyboard:
        keyboard = InlineKeyboardMarkup(await paginate_plugins(c, 0, HELP_COMMANDS, "help", chat_id))
    await c.send_message(chat_id, text, parse_mode=enums.ParseMode.MARKDOWN, reply_markup=keyboard)

@Mahiru.on_message(filters.command("help", PREFIX))
async def help_msg(c, m):
    chat_id = m.chat.id
    if m.chat.type != enums.ChatType.PRIVATE:
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text=await c.tl(chat_id, "helps"), url=f"t.me/{(await c.get_me()).username}?start=help")]])
        await m.reply(await c.tl(chat_id, "pm_me"), reply_markup=keyboard)
        return
    await help_parser(c, m.chat.id, (await c.tl(chat_id, "HELP_STRINGS")).format(", ".join(PREFIX)))

async def help_button_callback(_, __, query):
    if re.match(r"help_", query.data):
        return True

help_button_create = filters.create(help_button_callback)

@Mahiru.on_callback_query(help_button_create)
async def help_button(c, q):
    chat_id = q.message.chat.id
    mod_match = re.match(r"help_plugin\((.+?)\)", q.data)
    back_match = re.match(r"help_back", q.data)
    if mod_match:
        plugin = mod_match.group(1)
        text = (await c.tl(chat_id, "this_plugin_help")).format(await c.tl(chat_id, HELP_COMMANDS[plugin].__PLUGIN__)) \
               + await c.tl(chat_id, HELP_COMMANDS[plugin].__HELP__)

        await q.message.edit(text=text,
            parse_mode=enums.ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(text=await c.tl(chat_id, "back"), callback_data="help_back")]]))

    elif back_match:
        await q.message.edit(text=(await c.tl(chat_id, "HELP_STRINGS")).format(", ".join(PREFIX)),
            reply_markup=InlineKeyboardMarkup(await paginate_plugins(c, 0, HELP_COMMANDS, "help", chat_id)))


@Mahiru.on_message((filters.command("setlang", PREFIX) | filters.command("lang", PREFIX)) & admin_only)
async def set_language(c,m):
    db = c.db["chat_settings"]
    chat_id = m.chat.id
    #text = m.text.split(None, 1)
    if m.chat.type != enums.ChatType.PRIVATE and not await c.check_admin(m):
        return
    #if len(text) > 1:
    #    lang = text[1]
    buttons = []
    temp = []
    check = await db.find_one({'chat_id': chat_id})
    if check and "lang" in check:
        curr_lang = check["lang"]
    else:
        curr_lang = 'en'
    i = 1
    for lang in list_all_lang():
        t = importlib.import_module("mahiru.lang."+lang)
        data = "setlang_{}".format(lang)
        if lang == curr_lang:
            text = f"* {t.lang_name}"
        else:
            text = t.lang_name
        temp.append(InlineKeyboardButton(text=text, callback_data=data))
        if i % 2 == 0:
            buttons.append(temp)
            temp = []
        if i == len(list_all_lang()):
            buttons.append(temp)
        i += 1
    await m.reply_text(text=(await c.tl(chat_id, "select_lang")), reply_markup=InlineKeyboardMarkup(buttons))

async def set_lang_callback(_, __, query):
    if re.match(r"setlang_", query.data):
        return True

set_lang_create = filters.create(set_lang_callback)

@Mahiru.on_callback_query(set_lang_create)
async def set_lang_respond(c,q):
    db = c.db["chat_settings"]
    m = q.message
    if m.chat.type != enums.ChatType.PRIVATE and not await c.check_admin(m):
        return await c.answer_callback_query(callback_query_id=q.id, text="You're not admin!", show_alert=True)
    lang = q.data[8:]
    await db.update_one({'chat_id': m.chat.id},{"$set": {'lang': lang}}, upsert=True)
    await m.edit(text=await c.tl(m.chat.id, "language_changed"))
