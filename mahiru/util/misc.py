from pyrogram.types import InlineKeyboardButton

_EMOJI_REGEXP = None

class EqInlineKeyboardButton(InlineKeyboardButton):
    def __eq__(self, other):
        return self.text == other.text

    def __lt__(self, other):
        return self.text < other.text

    def __gt__(self, other):
        return self.text > other.text

async def paginate_plugins(client, _page_n, plugin_dict, prefix, chat_id, chat=None):
    if not chat:
        plugins = sorted(
            [EqInlineKeyboardButton(await client.tl(chat_id, x.__PLUGIN__),
                                    callback_data="{}_plugin({})".format(prefix, x.__PLUGIN__.lower())) for x
             in plugin_dict.values()])
    else:
        plugins = sorted(
            [EqInlineKeyboardButton(await client.tl(chat_id, x.__PLUGIN__),
                                    callback_data="{}_plugin({},{})".format(prefix, chat, x.__PLUGIN__.lower())) for x
             in plugin_dict.values()])

    pairs = [
    plugins[i * 3:(i + 1) * 3] for i in range((len(plugins) + 3 - 1) // 3)
    ]
    round_num = len(plugins) / 3
    calc = len(plugins) - round(round_num)
    if calc == 1:
        pairs.append((plugins[-1], ))
    elif calc == 2:
        pairs.append((plugins[-1],))

    return pairs

def removeduplicate(it):
    seen = []
    for x in it:
        if x not in seen:
            yield x
            seen.append(x)
