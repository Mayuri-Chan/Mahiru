import io
import math
import random
import re
import uuid

from bson import json_util
from datetime import datetime
from mahiru import PREFIX
from mahiru.mahiru import Mahiru
from mahiru.util.filters import sudo_only
from mahiru.util.misc import removeduplicate
from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from time import time

__PLUGIN__ = "waifu"
__HELP__ = "waifu_help"

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
    check_active = await adb.find_one({'chat_id': m.chat.id})
    if check:
        if check['active'] == True:
            if m.command and m.command[0] == "protecc":
                return
            if check['message_count'] >= 10 or check_active['timeout'] < time():
                await db.update_one({'chat_id': m.chat.id}, {'$set': {'message_count': 0, 'active': False}})
                await adb.delete_one({'chat_id': m.chat.id})
                return await c.send_message(m.chat.id, await c.tl(m.chat.id, 'waifu_running'))
            return await db.update_one({'chat_id': m.chat.id}, {'$set': {'message_count': check["message_count"]+1}})
        if check["message_count"] >= 50:
            await db.update_one({'chat_id': m.chat.id}, {'$set': {'message_count': 0, 'active': True}})
            data = await get_random_waifu(c)
            text = await c.tl(m.chat.id, 'new_waifu')
            timeout = time() + (60*5) # 5 minutes
            await adb.update_one({'chat_id': m.chat.id}, {'$set': {'anime': data['anime'], 'char': data['char'], 'alias': data["alias"], 'timeout': timeout}}, upsert=True)
            return await c.send_photo(m.chat.id, photo=data['image'], caption=text)
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
        await db.update_one({'chat_id': m.chat.id}, {'$set': {'message_count': 0, 'active': False}})
        count = 0
        check_user_waifu = await udb.find_one({'user_id': m.from_user.id, 'chat_id': m.chat.id})
        if check_user_waifu:
            waifu_list = check_user_waifu['harem']
            exists = [x for x in waifu_list if x["anime"]==anime and x["characters"]==waifu]
            if len(exists) > 0:
                count = exists[0]['count']
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
                        '$pull': {
                            'harem': {
                                'anime': anime,
                                'characters': waifu
                            }
                        }
                    }
                )
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
                        'characters': waifu,
                        'count': count+1
                    }
                }
            },
            upsert=True
        )
        await adb.delete_one({'chat_id': m.chat.id})
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
        return None, None, None
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
            text += f"\n{i+1}." + sorted_list[i]["characters"] + f" ({sorted_list[i]['count']})" if sorted_list[i]['count'] > 1 else f"\n{i+1}." + sorted_list[i]["characters"]
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
                    callback_data=f"h_{user_id}_{page-1}"
                )
            )
        if page < page_count:
            button.append(
                InlineKeyboardButton(
                    text=f"{page+1} ⏩",
                    callback_data=f"h_{user_id}_{page+1}"
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
    check, page, page_count = await get_waifu_list(c, m.reply_to_message, page)
    button = await create_button(c, page, page_count, chat_id, user_id)
    await m.edit_text(check, reply_markup=button)

@Mahiru.on_message(filters.command("exportall", PREFIX) & sudo_only)
async def cmd_exportall(c,m):
    db = c.db['char_list']
    data = db.find()
    list_anime = []
    async for d in data:
        d.pop('_id')
        d["characters"] = sorted(d["characters"], key=lambda k: (k['name']))
        list_anime.append(d)
    sorted_list = sorted(list_anime, key=lambda k: (k['title']))
    json_data = json_util.dumps({'list': sorted_list}, indent=4)
    now = datetime.now()
    now_formatted = now.strftime("%Y%m%d-%H:%M:%S")
    filename = f"backup-anime-{now_formatted}.json"
    f = io.BytesIO(json_data.encode('utf8'))
    f.name = filename
    await m.reply_document(document=f)

@Mahiru.on_message(filters.command("importall", PREFIX) & sudo_only)
async def cmd_importall(c,m):
    db = c.db['char_list']
    if not m.reply_to_message:
        return await m.reply_text(await c.tl(m.chat.id, 'reply_to_message_with_document'))
    if not m.reply_to_message.document:
        return await m.reply_text(await c.tl(m.chat.id, 'reply_to_message_with_document'))
    if not m.reply_to_message.document.file_name.endswith(".json"):
        return await m.reply_text(await c.tl(m.chat.id, 'reply_to_message_with_json'))
    data = await m.reply_to_message.download()
    with open(data, 'r') as f:
        data = json_util.loads(f.read())
    list_anime = data['list']
    i = 0
    for anime in list_anime:
        check = await db.find_one({'title': anime['title']})
        if check:
            for char in anime['characters']:
                char_exist = False
                for char2 in check['characters']:
                    if char['name'] == char2['name']:
                        char_exist = char2
                        break
                if check and char_exist:
                    await db.update_one(
                        {
                            'title': anime['title']
                        }, {
                            "$pull": {
                                'characters': {
                                    'name': char_exist['name'],
                                    'image': char_exist['image'],
                                    'alias': char_exist['alias']
                                }
                            }
                        }
                    )
                await db.update_one(
                    {
                        'title': anime['title']
                    }, {
                        "$push": {
                            'characters': {
                                'name': char['name'],
                                'image': char['image'],
                                'alias': char['alias']
                            }
                        }
                    },
                    upsert=True
                )
        else:
            await db.insert_one(anime)
        i += 1
    await m.reply_text((await c.tl(m.chat.id, 'data_imported')).format(i))

@Mahiru.on_message(filters.group & filters.command("trade", PREFIX))
async def cmd_trade(c,m):
    if not m.reply_to_message:
        return await m.reply_text(await c.tl(m.chat.id, 'reply_to_message_trade'))
    if not m.reply_to_message.from_user:
        return await m.reply_text(await c.tl(m.chat.id, 'reply_to_message_trade'))
    if m.reply_to_message.from_user.id == m.from_user.id:
        return await m.reply_text(await c.tl(m.chat.id, 'trade_self'))
    db = c.db["user_waifu"]
    tdb = c.db["trade_waifu"]
    user_id = m.from_user.id
    chat_id = m.chat.id
    target_id = m.reply_to_message.from_user.id
    user_harem = await get_sorted_waifu_list(c, chat_id, user_id)
    target_harem = await get_sorted_waifu_list(c, chat_id, target_id)
    text = (m.text).split()
    if len(text) < 3:
        return await m.reply_text(await c.tl(m.chat.id, 'reply_to_message_trade'))
    if not text[1].isdigit() or not text[2].isdigit():
        return await m.reply_text(await c.tl(m.chat.id, 'reply_to_message_trade'))
    user_waifu = int(text[1])
    target_waifu = int(text[2])
    if user_waifu > len(user_harem):
        return await m.reply_text((await c.tl(m.chat.id, 'your_waifu_not_found')).format(user_waifu))
    if target_waifu > len(target_harem):
        return await m.reply_text((await c.tl(m.chat.id, 'target_waifu_not_found')).format(target_waifu))
    user_waifu_name = user_harem[user_waifu-1]['characters']
    user_waifu_anime = user_harem[user_waifu-1]['anime']
    target_waifu_name = target_harem[target_waifu-1]['characters']
    target_waifu_anime = target_harem[target_waifu-1]['anime']
    trade_id = str(uuid.uuid4()).split("-")[0].lower()
    await tdb.update_one(
        {
            "trade_id": trade_id
        }, {
            '$set': {
                'user_id': user_id,
                'target_id': target_id,
                'user_waifu': {
                    'anime': user_waifu_anime,
                    'characters': user_waifu_name
                },
                'target_waifu': {
                    'anime': target_waifu_anime,
                    'characters': target_waifu_name
                }
            }
        },
        upsert=True
    )
    button = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    text=await c.tl(m.chat.id, 'accept_trade'),
                    callback_data=f"trade_accept_{trade_id}"
                ),
                InlineKeyboardButton(
                    text=await c.tl(m.chat.id, 'decline_trade'),
                    callback_data=f"trade_decline_{trade_id}"
                )
            ]
        ]
    )
    text = (await c.tl(m.chat.id, 'trade_request')).format(m.from_user.mention, target_waifu_name, target_waifu_anime, user_waifu_name, user_waifu_anime)
    await m.reply_to_message.reply_text(text, reply_markup=button)

@Mahiru.on_callback_query(filters.regex(r"^trade_accept_(.*)"))
async def accept_trade(c,q):
    trade_id = q.matches[0].group(1)
    db = c.db["trade_waifu"]
    tdb = c.db["user_waifu"]
    trade_data = await db.find_one({'trade_id': trade_id})
    if not trade_data:
        return await q.answer((await c.tl(q.message.chat.id, 'trade_not_found')).format(trade_id))
    user_id = trade_data['user_id']
    target_user_id = trade_data['target_id']
    if q.from_user.id != target_user_id:
        return await q.answer((await c.tl(q.message.chat.id, 'not_your_trade')))
    user_waifu = trade_data['user_waifu']
    target_waifu = trade_data['target_waifu']
    user = await c.get_users(user_id)
    user_waifu_data = await tdb.find_one({'user_id': user_id, 'chat_id': q.message.chat.id})
    target_waifu_data = await tdb.find_one({'user_id': target_user_id, 'chat_id': q.message.chat.id})
    find_user_waifu = [x for x in user_waifu_data["harem"] if x["anime"]==user_waifu["anime"] and x["characters"]==user_waifu["characters"]]
    find_target_waifu = [x for x in target_waifu_data["harem"] if x["anime"]==target_waifu["anime"] and x["characters"]==target_waifu["characters"]]
    if find_user_waifu[0]['count'] > 1:
        await tdb.update_one(
            {
                "$and": [
                    {
                        'user_id': user_id
                    },{
                        'chat_id': q.message.chat.id
                    }
                ]
            }, {
                '$pull': {
                    'harem': {
                        'anime': user_waifu['anime'],
                        'characters': user_waifu['characters']
                    }
                }
            }
        )
        await tdb.update_one(
            {
                "$and": [
                    {
                        'user_id': user_id
                    },{
                        'chat_id': q.message.chat.id
                    }
                ]
            }, {
                '$push': {
                    'harem': {
                        'anime': user_waifu['anime'],
                        'characters': user_waifu['characters'],
                        'count': find_user_waifu[0]['count']-1
                    }
                }
            },
            upsert=True
        )
    else:
        await tdb.update_one(
            {
                "$and": [
                    {
                        'user_id': user_id
                    },{
                        'chat_id': q.message.chat.id
                    }
                ]
            }, {
                '$pull': {
                    'harem': {
                        'anime': user_waifu['anime'],
                        'characters': user_waifu['characters']
                    }
                }
            }
        )
    if find_target_waifu[0]['count'] > 1:
        await tdb.update_one(
            {
                "$and": [
                    {
                        'user_id': target_user_id
                    },{
                        'chat_id': q.message.chat.id
                    }
                ]
            }, {
                '$pull': {
                    'harem': {
                        'anime': target_waifu['anime'],
                        'characters': target_waifu['characters']
                    }
                }
            }
        )
    else:
        await tdb.update_one(
            {
                "$and": [
                    {
                        'user_id': target_user_id
                    },{
                        'chat_id': q.message.chat.id
                    }
                ]
            }, {
                '$pull': {
                    'harem': {
                        'anime': target_waifu['anime'],
                        'characters': target_waifu['characters']
                    }
                }
            }
        )
    user_waifu_exist = [x for x in user_waifu_data["harem"] if x["anime"]==target_waifu["anime"] and x["characters"]==target_waifu["characters"]]
    if len(user_waifu_exist) > 0:
        await tdb.update_one(
            {
                "$and": [
                    {
                        'user_id': user_id
                    },{
                        'chat_id': q.message.chat.id
                    }
                ]
            }, {
                '$pull': {
                    'harem': {
                        'anime': target_waifu['anime'],
                        'characters': target_waifu['characters']
                    }
                }
            }
        )
        await tdb.update_one(
            {
                "$and": [
                    {
                        'user_id': user_id
                    },{
                        'chat_id': q.message.chat.id
                    }
                ]
            }, {
                '$push': {
                    'harem': {
                        'anime': target_waifu['anime'],
                        'characters': target_waifu['characters'],
                        'count': user_waifu_exist[0]['count']+1
                    }
                }
            },
            upsert=True
        )
    else:
        await tdb.update_one(
            {
                "$and": [
                    {
                        'user_id': user_id
                    },{
                        'chat_id': q.message.chat.id
                    }
                ]
            }, {
                '$push': {
                    'harem': {
                        'anime': target_waifu['anime'],
                        'characters': target_waifu['characters'],
                        'count': 1
                    }
                }
            },
            upsert=True
        )
    target_waifu_exist = [x for x in target_waifu_data["harem"] if x["anime"]==user_waifu["anime"] and x["characters"]==user_waifu["characters"]]
    if len(target_waifu_exist) > 0:
        await tdb.update_one(
            {
                "$and": [
                    {
                        'user_id': target_user_id
                    },{
                        'chat_id': q.message.chat.id
                    }
                ]
            }, {
                '$pull': {
                    'harem': {
                        'anime': user_waifu['anime'],
                        'characters': user_waifu['characters']
                    }
                }
            }
        )
        await tdb.update_one(
            {
                "$and": [
                    {
                        'user_id': target_user_id
                    },{
                        'chat_id': q.message.chat.id
                    }
                ]
            }, {
                '$push': {
                    'harem': {
                        'anime': user_waifu['anime'],
                        'characters': user_waifu['characters'],
                        'count': target_waifu_exist[0]['count']+1
                    }
                }
            },
            upsert=True
        )
    else:
        await tdb.update_one(
            {
                "$and": [
                    {
                        'user_id': target_user_id
                    },{
                        'chat_id': q.message.chat.id
                    }
                ]
            }, {
                '$push': {
                    'harem': {
                        'anime': user_waifu['anime'],
                        'characters': user_waifu['characters'],
                        'count': 1
                    }
                }
            },
            upsert=True
        )
    await db.delete_one({'trade_id': trade_id})
    await q.message.edit_text((await c.tl(q.message.chat.id, 'trade_accepted')).format(target_waifu['characters'], user.mention, user_waifu['characters']))

@Mahiru.on_callback_query(filters.regex(r"^trade_decline_(.*)"))
async def decline_trade(c,q):
    trade_id = q.matches[0].group(1)
    db = c.db["trade_waifu"]
    trade_data = await db.find_one({'trade_id': trade_id})
    if not trade_data:
        return await q.answer((await c.tl(q.message.chat.id, 'trade_not_found')))
    target_user_id = trade_data['target_id']
    if q.from_user.id != target_user_id:
        return await q.answer((await c.tl(q.message.chat.id, 'not_your_trade')))
    await db.delete_one({'trade_id': trade_id})
    await q.message.edit_text((await c.tl(q.message.chat.id, 'trade_declined')))

@Mahiru.on_message(filters.command("test_waifu", PREFIX) & sudo_only)
async def cmd_test_waifu(c,m):
    db = c.db["chat_waifu"]
    adb = c.db["active_waifu"]
    cdb = c.db["char_list"]
    text = m.text.split(None, 1)
    if len(text) > 1:
        char = text[1]
        data = {}
        chara_data = None
        async for anime_data in cdb.find():
            for char_data in anime_data['characters']:
                if char.lower() in char_data['name'].lower():
                    data['anime'] = anime_data['title']
                    chara_data = char_data
                    break
                for alias in char_data['alias']:
                    if char.lower() in alias.lower():
                        data['anime'] = anime_data['title']
                        chara_data = char_data
                        break
            if chara_data is not None:
                break
        if chara_data is None:
            return await m.reply_text((await c.tl(m.chat.id, 'waifu_not_found')).format(char))
        data['char'] = chara_data['name']
        data['image'] = chara_data['image']
        data['alias'] = chara_data['alias']
    else:
        data = await get_random_waifu(c)
    await db.update_one({'chat_id': m.chat.id}, {'$set': {'message_count': 0, 'active': True}})
    text = await c.tl(m.chat.id, 'new_waifu')
    timeout = time() + (60*5) # 5 minutes
    await adb.update_one({'chat_id': m.chat.id}, {'$set': {'anime': data['anime'], 'char': data['char'], 'alias': data["alias"], 'timeout': timeout}}, upsert=True)
    return await c.send_photo(m.chat.id, photo=data['image'], caption=text)
