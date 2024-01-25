import random
import re

from mahiru import PREFIX
from mahiru.mahiru import Mahiru
from mahiru.util.filters import sudo_only
from pyrogram import filters

async def get_random_waifu(c):
    db = c.db['char_list']
    data = {}
    anime = db.aggregate([{ "$sample": { 'size': 1 } }]).next()
    data['anime'] = anime['title']
    char = random.choice(anime['characters'])
    data['char'] = char['name']
    data['image'] = char['image']
    data['alias'] = char['alias']
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
            await adb.update_one({'chat_id': m.chat.id}, {'$set': {'anime': data['anime'], 'char': data['char'], 'alias': data["alias"]}}, upsert=True)
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
    alias = check_waifu['alias']
    text = m.text.split(None, 1)
    protecc = False
    if re.search(text[1], waifu, re.IGNORECASE):
        protecc = True
    else:
        for a in alias:
            if re.search(text[1], a, re.IGNORECASE):
                protecc = True
    if protecc:
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

@Mahiru.on_message(filters.command("addchar", PREFIX) & sudo_only)
async def cmd_add_char(c, m):
    db = c.db["char_list"]
    anime = await m.ask(await c.tl(m.chat.id, 'input_anime'))
    anime_title = anime.text
    if re.match(r'^(\/|\$)cancel.*', anime_title):
        return await m.reply_text(await c.tl(m.chat.id, 'canceled'))
    char = await m.ask(await c.tl(m.chat.id, 'input_char'))
    characters = char.text
    if re.match(r'^(\/|\$)cancel.*', characters):
        return await m.reply_text(await c.tl(m.chat.id, 'canceled'))
    i = 0
    for line in characters.split("\n"):
        line = line.split(";")
        await db.update_one(
            {
                'title': anime_title
            }, {
                "$push": {
                    'characters': {
                        'name': line[0],
                        'image': line[1],
                        'alias': [a for a in line[2].split(",")] if len(line) > 2 else []
                    }
                }
            },
            upsert=True
        )
        i += 1
    await m.reply_text((await c.tl(m.chat.id, 'char_added')).format(i, anime_title))
