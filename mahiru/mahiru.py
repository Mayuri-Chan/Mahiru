import colorlog
import importlib
import logging
import time

from async_pymongo import AsyncClient
from apscheduler import RunState
from apscheduler.schedulers.async_ import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from mahiru import config, init_help
from mahiru.plugins import list_all_plugins
from mahiru.util.filters import admin_check
from pyrogram import Client, raw

logging.getLogger().handlers.clear()
log = logging.getLogger("Mahiru")

class Mahiru(Client):
    def __init__(self):
        name = self.__class__.__name__.lower()
        conn = AsyncClient(config['bot']['DATABASE_URL'])
        super().__init__(
            "mahiru_sessions",
            bot_token=config['bot']['BOT_TOKEN'],
            api_id=config['telegram']['API_ID'],
            api_hash=config['telegram']['API_HASH'],
            mongodb=dict(connection=conn, remove_peers=False),
            workers=config['bot']['WORKERS'],
            plugins=dict(
                root=f"{name}.plugins"
            ),
            ipv6=True,
            max_concurrent_transmissions=20,
            sleep_threshold=180
        )
        self.config = config
        self.db = conn["mahiru"]
        self.log = log
        self.scheduler = AsyncScheduler()

    async def start(self):
        self._setup_log()
        self.log.info("---[Starting bot...]---")
        await super().start()
        await self.catch_up()
        await self.start_scheduler()
        await init_help(list_all_plugins())
        db = self.db['bot_settings']
        await db.update_one({'name': 'uptime'}, {"$set": {'value': time.time()}}, upsert=True)
        self.log.info("---[Mahiru Services is Running...]---")

    async def stop(self, block=True):
        self.log.info("---[Saving state...]---")
        db = self.db['bot_settings']
        state = await self.invoke(raw.functions.updates.GetState())
        value = {'pts': state.pts, 'qts': state.qts, 'date': state.date}
        await db.update_one({'name': 'state'}, {"$set": {'value': value}}, upsert=True)
        await super().stop(block=block)
        self.log.info("---[Bye]---")
        self.log.info("---[Thankyou for using my bot...]---")

    def _setup_log(self):
        """Configures logging"""
        level = logging.INFO
        logging.root.setLevel(level)

        # Color log config
        log_color: bool = True

        file_format = "[ %(asctime)s: %(levelname)-8s ] %(name)-15s - %(message)s"
        logfile = logging.FileHandler("mahiru.log")
        formatter = logging.Formatter(file_format, datefmt="%H:%M:%S")
        logfile.setFormatter(formatter)
        logfile.setLevel(level)

        if log_color:
            formatter = colorlog.ColoredFormatter(
                "  %(log_color)s%(levelname)-8s%(reset)s  |  "
                "%(name)-15s  |  %(log_color)s%(message)s%(reset)s"
            )
        else:
            formatter = logging.Formatter("  %(levelname)-8s  |  %(name)-15s  |  %(message)s")
        stream = logging.StreamHandler()
        stream.setLevel(level)
        stream.setFormatter(formatter)

        root = logging.getLogger()
        root.setLevel(level)
        root.addHandler(stream)
        root.addHandler(logfile)

        # Logging necessary for selected libs
        logging.getLogger("apscheduler").setLevel(logging.WARNING)
        logging.getLogger("pymongo").setLevel(logging.WARNING)
        logging.getLogger("pyrogram").setLevel(logging.WARNING)

    async def catch_up(self):
        self.log.info("---[Recovering gaps...]---")
        db = self.db['bot_settings']
        state = await db.find_one({'name': 'state'})
        if not state:
            return
        value = state['value']
        pts = value['pts']
        date = value['date']
        prev_pts = 0
        while(True):
            diff = await self.invoke(
                    raw.functions.updates.GetDifference(
                        pts=pts,
                        date=date,
                        qts=0
                    )
                )
            if isinstance(diff, raw.types.updates.DifferenceEmpty):
                await db.delete_one({'name': 'state'})
                break
            elif isinstance(diff, raw.types.updates.DifferenceTooLong):
                pts = diff.pts
                continue
            users = {u.id: u for u in diff.users}
            chats = {c.id: c for c in diff.chats}
            if isinstance(diff, raw.types.updates.DifferenceSlice):
                new_state = diff.intermediate_state
                pts = new_state.pts
                date = new_state.date
                if prev_pts == pts:
                    await db.delete_one({'name': 'state'})
                    break
                prev_pts = pts
            else:
                new_state = diff.state
            for msg in diff.new_messages:
                self.dispatcher.updates_queue.put_nowait((
                    raw.types.UpdateNewMessage(
                        message=msg,
                        pts=new_state.pts,
                        pts_count=-1
                    ),
                    users,
                    chats
                ))

            for update in diff.other_updates:
                self.dispatcher.updates_queue.put_nowait((update, users, chats))
            if isinstance(diff, raw.types.updates.Difference):
                await db.delete_one({'name': 'state'})
                break

    async def start_scheduler(self):
        self.log.info("---[Starting scheduler...]---")
        # Initialize the scheduler
        await self.scheduler.__aenter__()

        # check if scheduler is already started
        if self.scheduler.state == RunState.stopped:
            # run every 2 hours
            await self.scheduler.add_schedule(self.adminlist_watcher, CronTrigger(hour=0))
            # Run the scheduler in background
            await self.scheduler.start_in_background()

    async def tl(self, chat_id, string):
        db = self.db["chat_settings"]
        check = await db.find_one({'chat_id': chat_id})
        if check and "lang" in check:
            lang = check["lang"]
        else:
            lang = "en"
        t = importlib.import_module("mahiru.lang."+lang)
        if string in t.text:
            result = t.text[string]
            return result
        return (t.text['translation_not_found']).format(string)

    async def check_admin(self, m):
        return await admin_check(None, self, m)

    async def adminlist_watcher(self):
        db = self.db["admin_list"]
        chat_db = self.db["chat_list"]
        async for chat in chat_db.find():
            admin_list = []
            admin_list.clear()
            chat_id = chat["chat_id"]
            check = await db.find_one({'chat_id': chat_id})
            try:
                all_admin = self.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS)
                async for admin in all_admin:
                    admin_list.append(admin.user.id)
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except ChannelPrivate:
                continue
            except Exception as e:
                self.log.warning(e)
                continue
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

    def redact_message(self, text):
        api_id = str(self.config['telegram']['API_ID'])
        api_hash = self.config['telegram']['API_HASH']
        bot_token = self.config['bot']['BOT_TOKEN']
        db_uri = self.config['bot']['DATABASE_URL']

        if api_id in text:
            text = text.replace(api_id, "[REDACTED]")
        if api_hash in text:
            text = text.replace(api_hash, "[REDACTED]")
        if bot_token in text:
            text = text.replace(bot_token, "[REDACTED]")
        if db_uri in text:
            text = text.replace(db_uri, "[REDACTED]")

        return text
