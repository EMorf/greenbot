import logging
import asyncio
import sys
import discord
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
    
    def private_message(self, user, message, embed=None):
        self.discord_bot.private_message(user, message, embed)

    def say(self, channel, message, embed=None):
        log.info(f"embed: {embed}")
        self.discord_bot.say(channel, message, embed)

    def discord_message(self, message_raw, message, author, channel, user_level, whisper):
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
                    "message_raw": message_raw,
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

    def get_member(self, member_id):
        return self.discord_bot.get_member(member_id)

    def get_member_value(self, key, extra={}):
        if len(extra["argument"]) != 22:
            return getattr(extra["author"], key)
        member = self.get_member(extra["argument"][3:][:-1])
        return_val = getattr(member, key) if member else None
        return return_val

    def get_role_value(self, key, extra={}):
        if len(extra["argument"]) != 18: return None
        role = self.get_role(extra["argument"])
        return_val = getattr(role, key) if role else None
        return return_val

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

    def get_user_info(self, key, extra={}):
        user = self.get_member(extra["argument"]) if "argument" in extra else None
        message = extra["message_raw"]
        if not user:
            user = extra["author"]

        roles = user.roles[-1:0:-1]

        joined_at = user.joined_at
        since_created = (message.created_at - user.created_at).days
        if joined_at is not None:
            since_joined = (message.created_at - joined_at).days
            user_joined = joined_at.strftime("%d %b %Y %H:%M")
        else:
            since_joined = "?"
            user_joined = ("Unknown")
        user_created = user.created_at.strftime("%d %b %Y %H:%M")
        voice_state = user.voice

        created_on = ("{}\n({} days ago)").format(user_created, since_created)
        joined_on = ("{}\n({} days ago)").format(user_joined, since_joined)

        activity = ("Chilling in {} status").format(user.status)
        if user.activity is None:  # Default status
            pass
        elif user.activity.type == discord.ActivityType.playing:
            activity = ("Playing {}").format(user.activity.name)
        elif user.activity.type == discord.ActivityType.streaming:
            activity = ("Streaming [{}]({})").format(user.activity.name, user.activity.url)
        elif user.activity.type == discord.ActivityType.listening:
            activity = ("Listening to {}").format(user.activity.name)
        elif user.activity.type == discord.ActivityType.watching:
            activity = ("Watching {}").format(user.activity.name)

        if roles:

            role_str = ", ".join([x.mention for x in roles])
            # 400 BAD REQUEST (error code: 50035): Invalid Form Body
            # In embed.fields.2.value: Must be 1024 or fewer in length.
            if len(role_str) > 1024:
                # Alternative string building time.
                # This is not the most optimal, but if you're hitting this, you are losing more time
                # to every single check running on users than the occasional user info invoke
                # We don't start by building this way, since the number of times we hit this should be
                # infintesimally small compared to when we don't across all uses of Red.
                continuation_string = (
                    "and {numeric_number} more roles not displayed due to embed limits."
                )
                available_length = 1024 - len(continuation_string)  # do not attempt to tweak, i18n

                role_chunks = []
                remaining_roles = 0

                for r in roles:
                    chunk = f"{r.mention}, "
                    chunk_size = len(chunk)

                    if chunk_size < available_length:
                        available_length -= chunk_size
                        role_chunks.append(chunk)
                    else:
                        remaining_roles += 1

                role_chunks.append(continuation_string.format(numeric_number=remaining_roles))

                role_str = "".join(role_chunks)

        else:
            role_str = None

        data = discord.Embed(description=activity, colour=user.colour)
        data.add_field(name=("Joined Discord on"), value=created_on)
        data.add_field(name=("Joined this server on"), value=joined_on)
        if role_str is not None:
            data.add_field(name=("Roles"), value=role_str, inline=False)
        if voice_state and voice_state.channel:
            data.add_field(
                name=("Current voice channel"),
                value="{0.mention} ID: {0.id}".format(voice_state.channel),
                inline=False,
            )
        data.set_footer(text=(f"User ID: {user.id}"))

        name = str(user)
        name = " ~ ".join((name, user.nick)) if user.nick else name
        if user.avatar:
            avatar = user.avatar_url_as(static_format="png")
            data.set_author(name=name, url=avatar)
            data.set_thumbnail(url=avatar)
        else:
            data.set_author(name=name)
        return data

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
