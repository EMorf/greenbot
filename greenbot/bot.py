import logging
import asyncio
import sys
import discord
from pytz import timezone
import urllib

from greenbot.models.action import ActionParser
from greenbot.models.user import User
from greenbot.models.message import Message
from greenbot.models.module import ModuleManager
from greenbot.managers.sock import SocketManager
from greenbot.managers.schedule import ScheduleManager
from greenbot.managers.db import DBManager
from greenbot.managers.redis import RedisManager
from greenbot.managers.message import MessageManager
from greenbot.managers.handler import HandlerManager
from greenbot.managers.discord_bot import DiscordBotManager
from greenbot.managers.command import CommandManager
from greenbot.managers.twitter import TwitterManager
from greenbot.migration.db import DatabaseMigratable
from greenbot.migration.migrate import Migration
from greenbot.functions import Functions
from greenbot.filters import Filters
import greenbot.migration_revisions.db
import greenbot.utils as utils

log = logging.getLogger(__name__)


def custom_exception_handler(loop, context):
    # first, handle with default handler
    if "exception" in context:
        if context["exception"] == AssertionError:
            log.error("error ignored")
            return
    log.error(context["message"])
    return


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

        ScheduleManager.init(self)
        DBManager.init(self.config["main"]["db"])

        ActionParser.bot = self

        # redis
        redis_options = {}
        if "redis" in config:
            redis_options = dict(config.items("redis"))
        RedisManager.init(**redis_options)
        utils.wait_for_redis_data_loaded(RedisManager.get())

        # SQL migrations
        try:
            with DBManager.create_dbapi_connection_scope() as sql_conn:
                sql_migratable = DatabaseMigratable(sql_conn)
                sql_migration = Migration(
                    sql_migratable, greenbot.migration_revisions.db, self
                )
                sql_migration.run()
        except ValueError as error:
            log.error(error)

        HandlerManager.init_handlers()
        HandlerManager.add_handler(
            "parse_command_from_message", self.parse_command_from_message
        )
        self.bot_name = self.config["main"]["bot_name"]
        self.command_prefix = self.config["discord"]["command_prefix"]
        self.settings = {
            "discord_token": self.discord_token,
            "bot_name": self.bot_name,
            "command_prefix": self.command_prefix,
            "discord_guild_id": self.config["discord"]["discord_guild_id"],
        }

        HandlerManager.add_handler("discord_ready", self.wait_discord_load)

        self.discord_bot = DiscordBotManager(
            bot=self,
            settings=self.settings,
            redis=RedisManager.get(),
            private_loop=self.private_loop,
        )
        self.twitter_manager = TwitterManager(self, self.config["twitter"]) if utils.contains_value(["consumer_key", "consumer_secret", "access_token", "access_token_secret"], self.config["twitter"]) else None
        self.filters = Filters(self, self.discord_bot)
        self.functions = Functions(self, self.filters)

    @property
    def bot_id(self):
        return self.discord_bot.client.user.id

    async def wait_discord_load(self):
        self.roles = {} 
        self.socket_manager = SocketManager(self.bot_name, self.execute_now)
        self.message_manager = MessageManager(self)
        self.module_manager = ModuleManager(self.socket_manager, bot=self).load()

        self.commands = CommandManager(
            socket_manager=self.socket_manager,
            module_manager=self.module_manager,
            bot=self,
        ).load()
        await HandlerManager.trigger("manager_loaded")

        # promote the admin to level 2000
        owner = self.config["main"].get("owner_id", None)
        if owner is None:
            log.warning(
                "No admin user specified. See the [main] section in the example config for its usage."
            )
        else:
            with DBManager.create_session_scope() as db_session:
                owner = User._create_or_get_by_discord_id(db_session, str(owner))
                if owner is None:
                    log.warning(
                        "The login name you entered for the admin user does not exist on twitch. "
                        "No admin user has been created."
                    )
                else:
                    owner.level = 2000

    def execute_now(self, function, *args, **kwargs):
        self.execute_delayed(0, function, *args, **kwargs)

    def execute_delayed(self, delay, function, *args, **kwargs):
        ScheduleManager.execute_delayed(delay, function, *args, *kwargs)

    def execute_every(self, period, function, *args, **kwargs):
        ScheduleManager.execute_every(period, function, *args, **kwargs)

    async def _quit_bot(self):
        await HandlerManager.trigger("on_quit")
        try:
            ScheduleManager.base_scheduler.print_jobs()
            ScheduleManager.base_scheduler.shutdown(wait=False)
        except:
            log.exception("Error while shutting down the apscheduler")
        self.private_loop.call_soon_threadsafe(self.private_loop.stop)
        self.socket_manager.quit()

    def connect(self):
        self.discord_bot.connect()

    def start(self):
        self.private_loop.run_forever()

    async def ban(self, user, timeout_in_seconds=0, delete_message_days=0, reason=None):
        return await self.discord_bot.ban(
            user=user,
            timeout_in_seconds=timeout_in_seconds,
            delete_message_days=delete_message_days,
            reason=reason,
        )

    async def unban(self, user_id, reason=None):
        return await self.discord_bot.unban(user_id=user_id, reason=reason)

    async def kick(self, user, reason=None):
        return await self.discord_bot.kick(user=user, reason=reason)

    async def private_message(self, user, message=None, embed=None, ignore_escape=False):
        if message is None and embed is None:
            return None
        return await self.discord_bot.private_message(user, message, embed, ignore_escape)

    async def say(self, channel, message=None, embed=None, ignore_escape=False):
        if message is None and embed is None:
            log.error("sent invalid message")
            return None
        return await self.discord_bot.say(channel, message, embed, ignore_escape)

    async def parse_command_from_message(
        self, message, content, user_level, author, not_whisper, channel
    ):
        msg_lower = content.lower()
        if msg_lower[:1] == self.settings["command_prefix"]:
            msg_lower_parts = msg_lower.split(" ")
            trigger = msg_lower_parts[0][1:]
            msg_raw_parts = content.split(" ")
            remaining_message = (
                " ".join(msg_raw_parts[1:]) if len(msg_raw_parts) > 1 else ""
            )
            if trigger in self.commands:
                command = self.commands[trigger]
                extra_args = {
                    "trigger": trigger,
                    "message_raw": message,
                    "user_level": user_level,
                    "whisper": not not_whisper,
                }
                try:
                    await command.run(
                        bot=self,
                        author=author,
                        channel=channel if not_whisper else None,
                        message=remaining_message,
                        args=extra_args,
                    )
                except Exception as e:
                    log.error(f"Error thrown on command {trigger}")
                    log.exception(e)

    async def add_role(self, user, role, reason=None):
        return await self.discord_bot.add_role(user, role)

    async def remove_role(self, user, role, reason=None):
        return await self.discord_bot.remove_role(user, role, reason)

    def quit(self, bot, author, channel, message, args):
        self.quit_bot()

    def quit_bot(self):
        self.private_loop.create_task(self._quit_bot())

    def apply_filter(self, resp, f):
        available_filters = {
            "strftime": _filter_strftime,
            "timezone": _filter_timezone,
            "lower": lambda var, args: var.lower(),
            "upper": lambda var, args: var.upper(),
            "title": lambda var, args: var.title(),
            "capitalize": lambda var, args: var.capitalize(),
            "swapcase": lambda var, args: var.swapcase(),
            "time_since_minutes": lambda var, args: "no time"
            if var == 0
            else utils.time_since(var * 60, 0, time_format="long"),
            "time_since": lambda var, args: "no time"
            if var == 0
            else utils.time_since(var, 0, time_format="long"),
            "time_since_dt": _filter_time_since_dt,
            "urlencode": _filter_urlencode,
            "join": _filter_join,
            "number_format": _filter_number_format,
            "add": _filter_add,
            "or_else": _filter_or_else,
        }
        if f.name in available_filters:
            return available_filters[f.name](resp, f.arguments)
        return resp

    def get_currency(self):
        return {"name": "points"}


def _filter_time_since_dt(var, args):
    try:
        ts = utils.time_since(utils.now().timestamp(), var.timestamp())
        if ts:
            return ts

        return "0 seconds"
    except:
        return "never FeelsBadMan ?"


def _filter_join(var, args):
    try:
        separator = args[0]
    except IndexError:
        separator = ", "

    return separator.join(var.split(" "))


def _filter_number_format(var, args):
    try:
        return f"{int(var):,d}"
    except:
        log.exception("asdasd")
    return var


def _filter_strftime(var, args):
    return var.strftime(args[0])


def _filter_timezone(var, args):
    return var.astimezone(timezone(args[0]))


def _filter_urlencode(var, args):
    return urllib.parse.urlencode({"x": var})[2:]


def lowercase_first_letter(s):
    return s[:1].lower() + s[1:] if s else ""


def _filter_add(var, args):
    try:
        return str(int(var) + int(args[0]))
    except:
        return ""


def _filter_or_else(var, args):
    if var is None or len(var) <= 0:
        return args[0]
    else:
        return var
