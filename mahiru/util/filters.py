from pyrogram import filters

async def owner_check(_, c, m):
    if m.sender_chat:
        return False
    user_id = m.from_user.id
    if user_id == c.config['bot']['OWNER']:
        return True
    return False

async def sudo_check(_, c, m):
    if m.sender_chat:
        return False
    user_id = m.from_user.id
    db = c.db["bot_settings"]
    check = await db.find_one({'name': 'sudo_list'})
    owner = await owner_check(_, c, m)
    if (check and user_id in check['list']) or owner:
        return True
    return False

async def admin_check(_, c, m):
    chat_id = m.chat.id
    user_id = (
        m.from_user.id if m.from_user
        else
        m.sender_chat.id
    )
    if user_id == chat_id: # Anonymous admin
        return True
    try:
        curr_chat = await c.get_chat(chat_id)
    except FloodWait as e:
        asyncio.sleep(e.value)
    if curr_chat.linked_chat:
        if (
            user_id == curr_chat.linked_chat.id and
            not m.forward_from
        ): # Linked channel owner
            return True
    db = c.db["admin_list"]
    check = await db.find_one({"chat_id": chat_id})
    if check and user_id in check["list"]:
        return True
    return False

owner_only = filters.create(owner_check)
sudo_only = filters.create(sudo_check)
admin_only = filters.create(admin_check)
