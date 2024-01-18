import asyncio

from mahiru import PREFIX
from mahiru.mahiru import Mahiru
from mahiru.util.filters import admin_only, sudo_only
from pyrogram import enums, filters
from pyrogram.errors import FloodWait

__PLUGIN__ = "admin"
__HELP__ = "admin_help"

@Mahiru.on_message(filters.group, group=1)
async def chat_watcher(c,m):
    db = c.db["chat_list"]
    chat_id = m.chat.id
    check = await db.find_one({'chat_id': chat_id})
    if not check:
        await admincache(c,m, True)
    await db.update_one({'chat_id': chat_id},{"$set": {'chat_username': m.chat.username, 'chat_name': m.chat.title}}, upsert=True)

@Mahiru.on_message(filters.command("admincache", PREFIX) & (admin_only | sudo_only))
async def admincache(c,m, no_reply=False):
    chat_id = m.chat.id
    db = c.db["admin_list"]
    if not no_reply:
        r = await m.reply_text(await c.tl(chat_id, "refreshing_admin"))
    check = await db.find_one({'chat_id': chat_id})
    admin_list = []
    try:
        all_admin = c.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS)
    except FloodWait as e:
        await asyncio.sleep(e.value)
    async for admin in all_admin:
        admin_list.append(admin.user.id)
    if check:
        for user_id in check["list"]:
            if user_id not in admin_list:
                await db.update_one({'chat_id': chat_id},{"$pull": {'list': user_id}})
    second_loop = False
    for user_id in admin_list:
        if check or second_loop:
            if second_loop:
                check = await db.find_one({'chat_id': chat_id})
            if user_id not in check["list"]:
                await db.update_one({'chat_id': chat_id},{"$push": {'list': user_id}})
        else:
            await db.update_one({'chat_id': chat_id},{"$push": {'list': user_id}}, upsert=True)
            second_loop = True
    if not no_reply:
        await r.edit(await c.tl(chat_id, "admin_refreshed"))

@Mahiru.on_message(filters.command("adminlist", PREFIX) & filters.group & admin_only)
async def cmd_adminlist(c,m):
    db = c.db["admin_list"]
    chat_id = m.chat.id
    text = await c.tl(chat_id, "admin_list_text")
    check = await db.find_one({'chat_id': chat_id})
    if not check:
        await admincache(c,m)
    for user_id in check["list"]:
        user = await c.get_chat_member(chat_id,user_id)
        if user.status == enums.ChatMemberStatus.OWNER:
            text = text+"\n • 👑 "+user.user.mention
        else:
            text = text+"\n• "+user.user.mention

    await m.reply_text(text)
