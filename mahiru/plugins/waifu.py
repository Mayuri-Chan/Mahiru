import math
import random
import re

from mahiru import PREFIX
from mahiru.mahiru import Mahiru
from mahiru.util.filters import sudo_only
from mahiru.util.misc import removeduplicate
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

async def get_random_waifu(c):
    db = c.db['char_list']
    data = {}
    anime = await db.aggregate([{ "$sample": { 'size': 1 } }]).next()
    data['anime'] = anime['title']
    char = random.choice(anime['characters'])
    data['char'] = char['name']
    data['image'] = char['image']
    data['alias'] = char['alias']
    return data

@Mahiru.on_message(filters.group, group=11)
async def message_watcher(c, m):
    db = c.db["chat_waifu"]
    adb = c.db["active_waifu"]
    check = await db.find_one({'chat_id': m.chat.id})
    if check:
        if check['active'] == True:
            if m.command and m.command[0] == "protecc":
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
        return await db.update_one({'chat_id': m.chat.id}, {'$set': {'message_count': check["message_count"]+1}})
    await db.update_one({'chat_id': m.chat.id}, {"$set": {'message_count': 1, 'active': False}}, upsert=True)

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
    if (text[1]).lower() in waifu.lower():
        protecc = True
    else:
        for a in alias:
            if (text[1]).lower() in a.lower():
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
        return await m.reply_text((await c.tl(m.chat.id, 'protecc_waifu')).format(waifu, anime))
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

async def get_sorted_waifu_list(c, chat_id, user_id):
    db = c.db["user_waifu"]
    check = await db.find_one({'user_id': user_id, 'chat_id': chat_id})
    if not check:
        return None
    sorted_list = sorted(check['harem'], key=lambda k: (k['anime'],k["characters"]))
    return sorted_list

async def get_percentage(c, user_waifu_list):
    db = c.db["char_list"]
    user_waifu_count = len([waifu for waifu in removeduplicate(user_waifu_list)])
    user_anime_count = len([anime for anime in removeduplicate([a['anime'] for a in user_waifu_list])])
    bot_waifu_count = sum([len(a['characters']) async for a in db.find()])
    bot_anime_count = await db.count_documents({})
    user_waifu_percentage = round((user_waifu_count / bot_waifu_count) * 100, 2)
    user_anime_percentage = round((user_anime_count / bot_anime_count) * 100, 2)
    return user_waifu_percentage, user_anime_percentage, user_waifu_count, user_anime_count, bot_waifu_count, bot_anime_count

async def get_waifu_list(c, m, page: int=1):
    chat_id = m.chat.id
    user_id = m.from_user.id
    sorted_list = await get_sorted_waifu_list(c, chat_id, user_id)
    if sorted_list is None:
        return None
    uwp, uap, uwc, uac, bwc, bac = await get_percentage(c, sorted_list)
    limit = 10
    offset = (page - 1) * limit
    max = len(sorted_list)
    previos_anime = ""
    page_count = math.ceil(max / limit)
    text = (
        (await c.tl(chat_id, "user_harem_with_page")).format(
            m.from_user.first_name,
            m.chat.title,
            page
        ) if page_count > 1 else (await c.tl(chat_id, "user_harem")).format(
            m.from_user.first_name,
            m.chat.title
        )
    )
    for i in range(offset, offset + limit):
        if i < max:
            if previos_anime != sorted_list[i]['anime']:
                previos_anime = sorted_list[i]['anime']
                text += "\n\n" + sorted_list[i]['anime']
            text += f"\n{i+1}." + sorted_list[i]["characters"]
    text += f"\n\n{(await c.tl(chat_id, 'user_harem_percentage')).format(uwc,bwc,uwp,uac,bac,uap)}"
    return text, page, page_count

async def create_button(c, page, page_count, chat_id, user_id):
    button = []
    if page_count > 1:
        if page > 2:
            button.append(
                InlineKeyboardButton(
                    text=await c.tl(chat_id, 'first_page'),
                    callback_data=f"h_{user_id}_1"
                )
            )
        if page > 1:
            button.append(
                InlineKeyboardButton(
                    text=f"⏪ {page-1}",
                    callback_data=f"h_{user_id}_{page}"
                )
            )
        if page < page_count:
            button.append(
                InlineKeyboardButton(
                    text=f"{page+1} ⏩",
                    callback_data=f"h_{user_id}_{page+2}"
                )
            )
        if page < page_count-1:
            button.append(
                InlineKeyboardButton(
                    text=await c.tl(chat_id, 'last_page'),
                    callback_data=f"h_{user_id}_{page_count}"
                )
            )
    if len(button) > 0:
        return InlineKeyboardMarkup([button])
    return None

@Mahiru.on_message(filters.command("harem", PREFIX))
async def harem(c,m):
    chat_id = m.chat.id
    user_id = m.from_user.id
    check, page, page_count = await get_waifu_list(c, m)
    if check is None:
        return await m.reply_text((await c.tl(m.chat.id, 'protecc_waifu_none')).format(m.from_user.first_name, m.chat.title))
    button = await create_button(c, page, page_count, chat_id, user_id)
    await m.reply_text(check, reply_markup=button)

@Mahiru.on_callback_query(filters.regex(r"^h_(.*)_(.*)"))
async def harem_page(c, q):
    if q.from_user.id != int(q.matches[0].group(1)):
        return await q.answer((await c.tl(q.message.chat.id, 'not_your_harem')))
    m = q.message
    chat_id = m.chat.id
    user_id = int(q.matches[0].group(1))
    page = int(q.matches[0].group(2))
    check, page, page_count = await get_waifu_list(c, m, page)
    button = await create_button(c, page, page_count, chat_id, user_id)
    await m.edit_text(check, reply_markup=button)
