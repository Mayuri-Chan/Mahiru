import random
import re

from mahiru import PREFIX
from mahiru.mahiru import Mahiru
from pyrogram import filters

async def get_random_waifu(c):
    db = c.db['char_list']
    data = {}
    anime = db.aggregate([{ "$sample": { 'size': 1 } }]).next()
    data['anime'] = anime['title']
    char = random.choice(anime['characters'])
    data['char'] = char['name']
    data['image'] = char['image']
    return data

@Mahiru.on_message(filters.group, group=1)
async def message_watcher(c, m):
    db = c.db["chat_waifu"]
    adb = c.db["active_waifu"]
    check = await db.find_one({'chat_id': m.chat.id})
    if check:
        if check['active'] == True:
            if m.command[0] == "protecc":
                return
            if check['message_count'] >= 10:
                return await db.update_one({'chat_id': m.chat.id}, {'$set': {'message_count': 0, 'active': False}})
            return await db.update_one({'chat_id': m.chat.id}, {'$set': {'message_count': check["message_count"]+1}})
        if check["message_count"] >= 50:
            data = await get_random_waifu(c)
            text = await c.tl(m.chat.id, 'new_waifu')
            await c.send_photo(m.chat.id, photo=data['image'], caption=text)
            await adb.update_one({'chat_id': m.chat.id}, {'$set': {'anime': data['anime'], 'char': data['char']}}, upsert=True)
            return await db.update_one({'chat_id': m.chat.id}, {'$set': {'message_count': 0, 'active': True}})
        return await db.update_one({'chat_id': m.chat.id}, {'$set': {'message_count': check["message_count"]+0}})
    await db.update_one({'chat_id': m.chat.id}, {'$set': {'message_count': 1}})

@Mahiru.on_message(filters.group & filters.command("protecc", PREFIX))
async def cmd_protecc(c,m):
    db = c.db["chat_waifu"]
    adb = c.db["active_waifu"]
    udb = c.db["user_waifu"]
    check = await db.find_one({'chat_id': m.chat.id})
    if check['active'] == False:
        return
    check_waifu = await adb.find_one({'chat_id': m.chat.id})
    waifu = check_waifu['char']
    anime = check_waifu['anime']
    text = m.text.split(None, 1)
    if re.search(text[1], waifu, re.IGNORECASE):
        await udb.update_one(
            {
                "$and": [
                    {
                        'user_id': m.from_user.id
                    },{
                        'chat_id': m.chat.id
                    }
                ]
            }, {
                '$push': {
                    'harem': {
                        'anime': anime,
                        'characters': waifu
                    }
                }
            },
            upsert=True
        )
        await db.update_one({'chat_id': m.chat.id}, {'$set': {'message_count': 0, 'active': False}})
        return await m.reply_text(await c.tl(m.chat.id, 'protecc_waifu').format(waifu, anime))
    await m.reply_text(await c.tl(m.chat.id, 'protecc_not_waifu'))
