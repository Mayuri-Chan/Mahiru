import aiofiles
import asyncio
import os
import json
import imghdr
import html
import pendulum

from mahiru import PREFIX
from mahiru.mahiru import Mahiru
from pyrogram import enums, filters
from pyrogram.errors import FloodWait

__PLUGIN__ = "whatanime"
__HELP__ = "whatanime_help"

@Mahiru.on_message(filters.command("whatanime", PREFIX))
async def whatanime(c,m):
	chat_id = m.chat.id
	reply = m.reply_to_message
	if reply:
		if reply.photo:
			media = reply.photo
			file_type = "image"
		elif reply.document:
			media = reply.document
			file_type = "document"
		elif reply.video:
			media = reply.video
			file_type = "video"
		else:
			await m.reply_text(await c.tl(chat_id, "whatanime_reply_to_message"))
			return
		file_id = media.file_id
		if file_type == "image":
			msg = await m.reply_text(await c.tl(chat_id, "downloading"))
			file_path = await c.download_media(file_id)
			image_type = imghdr.what(open(file_path, 'rb'))
			if image_type == 'jpeg':
				mime_type = 'image/jpeg'
			elif image_type == 'png':
				mime_type = 'image/png'
			elif image_type == 'gif':
				mime_type = 'image/gif'
			else:
				return await msg.edit((await c.tl(chat_id, "file_not_supported")).format(image_type))
		elif file_type == "document":
			if 'image' in media.mime_type:
				if image_type != 'jpeg' and image_type != 'png' and image_type != 'gif':
					await msg.edit((await c.tl(chat_id, "file_not_supported")).format(image_type))
					return
				file_path = await c.download_media(file_id)
			elif 'video' in media.mime_type:
				file_path = await c.download_media(file_id)
			else:
				await msg.edit((await c.tl(chat_id, "file_not_supported")).format(image_type))
				return
			mime_type = media.mime_type
		elif file_type == 'video':
			mime_type = 'video/mp4'
			file_path = await c.download_media(file_id)
		file = await aiofiles.open(file_path, mode='rb')
		await msg.edit(await c.tl(chat_id, "searching"))
		url = "https://api.trace.moe/search?anilistInfo"
		raw_resp0 = (await c.fetch.post(url, data=file, headers={"Content-Type": mime_type})).json()
		resp0 = json.dumps(raw_resp0, indent=4)
		js0 = json.loads(resp0)
		if "result" not in js0:
			await msg.edit(await c.tl(chat_id, "result_not_found"))
			return
		js0 = js0["result"][0]
		text = f'<b>{html.escape(js0["anilist"]["title"]["romaji"])}'
		if (
			"native" in js0["anilist"]["title"]
			and
			js0["anilist"]["title"]["native"] != js0["anilist"]["title"]["romaji"]
		):
			text += f' ({html.escape(js0["anilist"]["title"]["native"])})'
		text += "</b>\n"
		if "episode" in js0:
			text += f'<b>Episode:</b> {html.escape(str(js0["episode"]))}\n'
		percent = round(js0["similarity"] * 100, 2)
		text += f"<b>{await c.tl(chat_id, 'similarity')}:</b> {percent}%\n"
		dt0 = pendulum.from_timestamp(js0["from"])
		dt1 = pendulum.from_timestamp(js0["to"])
		text += f"<b>{await c.tl(chat_id, 'whatanime_at')}:</b> {html.escape(dt0.to_time_string())}-{html.escape(dt1.to_time_string())}"
		await msg.delete()
		try:
			await c.send_chat_action(chat_id=m.chat.id, action=enums.ChatAction.UPLOAD_VIDEO)
			await m.reply_video(video=js0["video"], caption=text)
		except FloodWait as e:
			await asyncio.sleep(e.value)
		except Exception:
			await m.reply_text((await c.tl(chat_id, "cannot_send_preview")).format(text))
		os.remove(file_path)
	else:
		await m.reply_text(await c.tl(chat_id, "whatanime_reply_to_message"))
