import logging
import asyncio
import sys
from pytz import timezone
import urllib

from greenbot.models.action import ActionParser
from greenbot.managers.schedule import ScheduleManager
from greenbot.managers.db import DBManager
from greenbot.managers.redis import RedisManager
from greenbot.managers.handler import HandlerManager
from greenbot.managers.discord_bot import DiscordBotManager
from greenbot.managers.command import CommandManager
from greenbot.migration.db import DatabaseMigratable
from greenbot.migration.migrate import Migration
import greenbot.migration_revisions.db
import greenbot.utils as utils

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

    def ban(self, user, timeout_in_seconds=0, reason=None, delete_message_days=0):
        self.discord_bot.ban(user=user, timeout_in_seconds=timeout_in_seconds, reason=reason, delete_message_days=delete_message_days)

    def unban(self, user, reason=None):
        self.discord_bot.unban(user=user, reason=reason)
    
    def private_message(self, user, message):
        self.discord_bot.private_message(user, message)

    def say(self, channel, message):
        self.discord_bot.say(channel, message)

    def discord_message(self, message, author, channel, user_level, whisper):
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
                command.run(bot=self, author=author, channel=channel, message=remaining_message, whisper=whisper, args=extra_args)

    def get_role_id(self, role_name):
        return self.discord_bot.get_role_id(role_name)

    def get_role(self, role_id):
        return self.discord_bot.get_role(role_id)

    def add_role(self, user, role):
        return self.discord_bot.add_role(user, role)

    def remove_role(self, user, role):
        return self.discord_bot.remove_role(user, role)

    def quit(self, message, event, **options):
        self.quit_bot()

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
            "time_since": lambda var, args: "no time" if var == 0 else utils.time_since(var, 0, time_format="long"),
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

    def get_time_value(self, key, extra={}):
        try:
            tz = timezone(key)
            return datetime.datetime.now(tz).strftime("%H:%M")
        except:
            log.exception("Unhandled exception in get_time_value")

        return None

    def get_strictargs_value(self, key, extra={}):
        ret = self.get_args_value(key, extra)

        if not ret:
            return None

        return ret

    @staticmethod
    def get_args_value(key, extra={}):
        r = None
        try:
            msg_parts = extra["message"].split(" ")
        except (KeyError, AttributeError):
            msg_parts = [""]

        try:
            if "-" in key:
                range_str = key.split("-")
                if len(range_str) == 2:
                    r = (int(range_str[0]), int(range_str[1]))

            if r is None:
                r = (int(key), len(msg_parts))
        except (TypeError, ValueError):
            r = (0, len(msg_parts))

        try:
            return " ".join(msg_parts[r[0] : r[1]])
        except AttributeError:
            return ""
        except:
            log.exception("Caught exception in get_args_value")
            return ""

    @staticmethod
    def get_command_value(key, extra={}):
        try:
            return getattr(extra["command"].data, key)
        except:
            log.exception("Caught exception in get_command_value")

        return None

    @staticmethod
    def get_author_value(key, extra={}):
        try:
            return getattr(extra["author"], key)
        except:
            log.exception("Caught exception in get_author_value")

        return None

    @staticmethod
    def get_channel_value(key, extra={}):
        try:
            return getattr(extra["channel"], key)
        except:
            log.exception("Caught exception in get_channel_value")

        return None

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
