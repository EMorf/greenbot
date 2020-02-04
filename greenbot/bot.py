import logging
import asyncio
import sys

from greenbot.managers.schedule import ScheduleManager
from greenbot.managers.db import DBManager
from greenbot.managers.redis import RedisManager
from greenbot.managers.handler import HandlerManager
from greenbot.managers.discord_bot import DiscordBotManager
from greenbot.managers.command import CommandManager
from greenbot.migration.db import DatabaseMigratable
from greenbot.migration.migrate import Migration
from greenbot.utils import wait_for_redis_data_loaded

import greenbot.migration_revisions.db

log = logging.getLogger(__name__)

def custom_exception_handler(loop, context):
    # first, handle with default handler
    loop.default_exception_handler(context)
    log.error(context)


class Bot:
    """
    Main class for the discord bot
    """

    def __init__(self, config, args):
        self.config = config
        self.args = args
        self.private_loop = asyncio.get_event_loop()
        self.private_loop.set_exception_handler(custom_exception_handler)

        self.discord_token = self.config["main"]["discord_token"]

        ScheduleManager.init()
        DBManager.init(self.config["main"]["db"])

        # redis
        redis_options = {}
        if "redis" in config:
            redis_options = dict(config.items("redis"))
        RedisManager.init(**redis_options)
        wait_for_redis_data_loaded(RedisManager.get())

        # SQL migrations
        try:
            with DBManager.create_dbapi_connection_scope() as sql_conn:
                sql_migratable = DatabaseMigratable(sql_conn)
                sql_migration = Migration(sql_migratable, greenbot.migration_revisions.db, self)
                sql_migration.run()
        except ValueError as error:
            log.error(error)

        HandlerManager.init_handlers()
        HandlerManager.add_handler("discord_message", self.discord_message)

        self.settings = {
            "discord_token": self.discord_token,
            "channels": self.config["discord"]["channels_to_listen_in"].split(" "),
            "command_prefix": self.config["discord"]["command_prefix"],
            "discord_guild_id": self.config["discord"]["discord_guild_id"],
            "admin_roles": [{"role_id": self.config[role]["role_id"], "level": self.config[role]["level"]} for role in self.config["discord"]["admin_roles"].split(" ")]
        }

        self.discord_bot = DiscordBotManager(bot=self, settings=self.settings, redis=RedisManager.get(), private_loop=self.private_loop)
        self.commands = CommandManager(module_manager=None, bot=self).load()
        HandlerManager.trigger("manager_loaded")

    def quit_bot(self):
        HandlerManager.trigger("on_quit")
        try:
            ScheduleManager.base_scheduler.print_jobs()
            ScheduleManager.base_scheduler.shutdown(wait=False)
        except:
            log.exception("Error while shutting down the apscheduler")
        self.private_loop.call_soon_threadsafe(self.private_loop.stop)

    def connect(self):
        self.discord_bot.connect()

    def start(self):
        self.private_loop.run_forever()

    def ban(self, user_id, timeout_in_seconds=0, reason=None, delete_message_days=0):
        self.discord_bot.ban(user_id=user_id, timeout_in_seconds=timeout_in_seconds, reason=reason, delete_message_days=delete_message_days)

    def unban(self, user_id, reason=None):
        self.discord_bot.unban(user_id=user_id, reason=reason)
    
    def private_message(self, user, message):
        self.discord_bot.private_message(user, message)

    def discord_message(self, message, user_id, user_level, whisper):
        msg_lower = message.lower()
        if msg_lower[:1] == self.settings["command_prefix"]:
            msg_lower_parts = msg_lower.split(" ")
            trigger = msg_lower_parts[0][1:]
            msg_raw_parts = message.split(" ")
            remaining_message = " ".join(msg_raw_parts[1:]) if len(msg_raw_parts) > 1 else None
            if trigger in self.commands:
                command = self.commands[trigger]
                extra_args = {
                    "trigger": trigger,
                    "user_level": user_level,
                }
                command.run(self, user_id, remaining_message, whisper=whisper, args=extra_args)

    def quit(self, message, event, **options):
        self.quit_bot()