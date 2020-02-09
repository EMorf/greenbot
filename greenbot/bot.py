import logging
import asyncio
import sys
import discord
from pytz import timezone
import urllib
import datetime
import time

from greenbot.models.action import ActionParser
from greenbot.models.user import User
from greenbot.models.module import ModuleManager
from greenbot.managers.sock import SocketManager
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
                sql_migration = Migration(
                    sql_migratable, greenbot.migration_revisions.db, self
                )
                sql_migration.run()
        except ValueError as error:
            log.error(error)

        HandlerManager.init_handlers()
        HandlerManager.add_handler("discord_message", self.discord_message)
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

    @property
    def bot_id(self):
        return self.discord_bot.client.user.id

    def wait_discord_load(self):
        self.socket_manager = SocketManager(self.bot_name, self.execute_now)
        self.module_manager = ModuleManager(self.socket_manager, bot=self).load()

        self.commands = CommandManager(
            socket_manager=self.socket_manager,
            module_manager=self.module_manager,
            bot=self,
        ).load()
        HandlerManager.trigger("manager_loaded")

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
        ScheduleManager.execute_delayed(delay, lambda: function(*args, **kwargs))

    def execute_every(self, period, function, *args, **kwargs):
        ScheduleManager.execute_every(period, lambda: function(*args, **kwargs))

    def quit_bot(self):
        HandlerManager.trigger("on_quit")
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

    def ban(self, user, timeout_in_seconds=0, delete_message_days=0, reason=None):
        self.discord_bot.ban(
            user=user,
            timeout_in_seconds=timeout_in_seconds,
            delete_message_days=delete_message_days,
            reason=reason,
        )

    def unban(self, user_id, reason=None):
        self.discord_bot.unban(user_id=user_id, reason=reason)

    def kick(self, user, reason=None):
        self.discord_bot.kick(user=user, reason=reason)

    def private_message(self, user, message, embed=None):
        self.discord_bot.private_message(user, message, embed)

    def say(self, channel, message, embed=None):
        self.discord_bot.say(channel, message, embed)

    def discord_message(
        self, message_raw, message, author, channel, user_level, whisper
    ):
        msg_lower = message.lower()
        if msg_lower[:1] == self.settings["command_prefix"]:
            msg_lower_parts = msg_lower.split(" ")
            trigger = msg_lower_parts[0][1:]
            msg_raw_parts = message.split(" ")
            remaining_message = (
                " ".join(msg_raw_parts[1:]) if len(msg_raw_parts) > 1 else None
            )
            if trigger in self.commands:
                command = self.commands[trigger]
                extra_args = {
                    "trigger": trigger,
                    "message_raw": message_raw,
                    "user_level": user_level,
                    "whisper": whisper,
                }
                try:
                    command.run(
                        bot=self,
                        author=author,
                        channel=channel,
                        message=remaining_message,
                        args=extra_args,
                    )
                except Exception as e:
                    log.error(f"Error thrown on command {trigger}")
                    log.exception(e)
                    raise Exception

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

    def func_kick_member(self, args, extra={}):
        author = extra["author"]
        if len(args) == 0:
            return "Invalid User", None
        member = self.get_member(args[0][3:][:-1])
        if not member:
            return "Member not found"
        with DBManager.create_session_scope() as db_session:
            author_user = User._create_or_get_by_discord_id(
                db_session, str(author.id), user_name=str(author)
            )
            member_user = User._create_or_get_by_discord_id(
                db_session, str(member.id), user_name=str(member)
            )
            if author_user.level <= member_user.level:
                return "You cannot kick someone who has the same level as you :)", None
        reason = args[1] if len(args) > 1 else ""
        message = f"Member {member} has been kicked!"
        self.kick(member, f"{reason}\nKicked by {author}")
        return message, None

    def func_ban_member(self, args, extra={}):
        if len(args) == 0:
            return "Invalid User", None
        member = self.get_member(args[0][3:][:-1])
        author = extra["author"]
        if not member:
            return "Member not found"
        with DBManager.create_session_scope() as db_session:
            author_user = User._create_or_get_by_discord_id(
                db_session, str(author.id), user_name=str(author)
            )
            member_user = User._create_or_get_by_discord_id(
                db_session, str(member.id), user_name=str(member)
            )
            if author_user.level <= member_user.level:
                return "You cannot ban someone who has the same level as you :)", None
        timeout_in_seconds = int(args[1] if len(args) > 2 else 0)
        delete_message_days = int(args[2] if len(args) > 3 else 0)
        reason = args[3] if len(args) == 4 else ""

        message = f"Member {member.mention} has been banned!"
        self.ban(
            user=member,
            timeout_in_seconds=timeout_in_seconds,
            delete_message_days=delete_message_days,
            reason=f"{reason}\nBanned by {author}",
        )
        return message, None

    def func_unban_member(self, args, extra={}):
        if len(args) == 0:
            return "Invalid User", None
        member_id = args[0][3:][:-1]
        author = extra["author"]
        reason = args[1]

        message = f"Member <@!{member_id}> has been unbanned!"
        self.unban(
            user_id=member_id, reason=f"{reason}\nUnbanned by {author}",
        )
        return message, None

    def func_set_balance(self, args, extra={}):
        if len(args) == 0:
            return "Invalid User", None
        user_id = args[0][3:][:-1]
        try:
            amount = int(args[1])
        except:
            return f"Invalid points amount", None
        with DBManager.create_session_scope() as db_session:
            user = User._create_or_get_by_discord_id(db_session, str(user_id))
            user.points = amount
        currency = self._get_currency().get("name").capitalize()
        return f"{currency} balance for <@!{user_id}> set to {amount}", None

    def func_adj_balance(self, args, extra={}):
        if len(args) == 0:
            return "Invalid User", None
        user_id = args[0][3:][:-1]
        try:
            amount = int(args[1])
        except:
            return f"Invalid points amount, {args[1]}", None
        with DBManager.create_session_scope() as db_session:
            user = User._create_or_get_by_discord_id(db_session, str(user_id))
            user.points += amount
        action = "added to" if amount > 0 else "removed from"
        currency = self._get_currency().get("name")
        return f"{amount} {currency} {action} <@!{user_id}> ", None

    def quit(self, bot, author, channel, message, whisper, args):
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

    def get_role_value(self, key, extra={}):
        role_name = extra["message"]
        role = self.get_role(self.get_role_id(role_name))
        if not role:
            return f"Role {role_name} not found"
        return_val = getattr(role, key) if role else None
        return return_val

    def get_user_info(self, key, extra={}):
        user = self.get_member(key[3:][:-1]) if key else None
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
            user_joined = "Unknown"
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
            activity = ("Streaming [{}]({})").format(
                user.activity.name, user.activity.url
            )
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
                available_length = 1024 - len(
                    continuation_string
                )  # do not attempt to tweak, i18n

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

                role_chunks.append(
                    continuation_string.format(numeric_number=remaining_roles)
                )

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

    def get_role_info(self, key, extra={}):
        role_name = extra["message"]
        role_id = self.get_role_id(role_name)
        if not role_id:
            return f"Role {role_name} not found"
        role = self.get_role(role_id)
        data = discord.Embed(colour=role.colour)
        data.add_field(name=("Role Name"), value=role.name)
        data.add_field(
            name=("Created"),
            value=f"{(datetime.datetime.now() - role.created_at).days}d ago",
        )
        data.add_field(name=("Users in Role"), value=len(role.members))
        data.add_field(name=("ID"), value=role.id)
        data.add_field(name=("Color"), value=str(role.color))
        data.add_field(name=("Position"), value=role.position)
        valid_permissions = []
        invalid_permissions = []
        for (perm, value) in role.permissions:
            if value:
                valid_permissions.append(perm)
                continue
            invalid_permissions.append(perm)

        data.add_field(
            name=("Valid Permissions"),
            value="\n".join([str(x) for x in valid_permissions]),
        )
        data.add_field(
            name=("Invalid Permissions"),
            value="\n".join([str(x) for x in invalid_permissions]),
        )
        data.set_thumbnail(url=extra["message_raw"].guild.icon_url)
        return data

    def get_commands(self, key, extra={}):
        data = discord.Embed(
            description=("All Commands"), colour=discord.Colour.dark_gold()
        )
        commands = list(self.commands.keys())
        data.add_field(
            name=("All Commands"),
            value="\n".join([str(x) for x in commands[: len(commands) // 2]]),
        )
        data.add_field(
            name=("All Commands"),
            value="\n".join([str(x) for x in commands[len(commands) // 2 :]]),
        )
        data.set_thumbnail(url=extra["message_raw"].guild.icon_url)
        return data

    def get_command_info(self, key, extra={}):
        if key not in self.commands:
            return f"Cannot find command {key}"
        command = self.commands[key]
        data = discord.Embed(
            description=(command.command), colour=discord.Colour.dark_gold()
        )
        data.add_field(name=("ID"), value=command.id)
        data.add_field(name=("Level"), value=command.level)
        data.add_field(name=("Delay All"), value=command.delay_all)
        data.add_field(name=("Delay User"), value=command.delay_user)
        data.add_field(name=("Enabled"), value="Yes" if command.enabled else "No")
        currency = self._get_currency().get("name")
        data.add_field(name=("Cost"), value=f"{command.cost} {currency}")
        data.add_field(
            name=("Whispers"), value="Yes" if command.can_execute_with_whisper else "No"
        )
        if command.data:
            data.add_field(name=("Number of uses"), value=command.data.num_uses)
            data.set_footer(
                text=(
                    f"Made by: {command.data.added_by} | Edited by {command.data.edited_by}"
                )
            )
        try:
            data.add_field(name=("Description"), value=command.action.response)
        except:
            pass
        data.set_thumbnail(url=extra["message_raw"].guild.icon_url)

        return data

    def _get_currency(self):
        return {"name": "points"}

    def get_currency(self, key, extra={}):
        return self._get_currency().get(key) if key else None

    def get_user(self, key, extra={}):
        user = (
            self.get_member(extra["argument"][3:][:-1]) if extra["argument"] else None
        )
        if not user:
            user = extra["author"]
        with DBManager.create_session_scope() as db_session:
            db_user = User._create_or_get_by_discord_id(db_session, user.id)
            return getattr(db_user, key) if db_user else None

    def func_output(self, args, extra={}):
        return f"args: {args}\nextra: {extra}", None

    def rest(self, key, extra={}):
        return " ".join(extra["message"].split(" ")[int(key):])

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
            return extra["command"].data

        return None

    @staticmethod
    def get_author_value(key, extra={}):
        try:
            return getattr(extra["author"], key)
        except:
            return extra["author"]

    @staticmethod
    def get_channel_value(key, extra={}):
        try:
            return getattr(extra["channel"], key)
        except:
            return extra["channel"]

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
