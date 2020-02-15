import logging

from greenbot.managers.db import DBManager
from greenbot.models.user import User

import discord
import datetime

log = logging.getLogger("greenbot")


class Filters:
    def __init__(self, bot, discord_bot):
        self.bot = bot
        self.discord_bot = discord_bot

    def get_role_id(self, role_name):
        return self.discord_bot.get_role_id(role_name)

    def get_role(self, role_id):
        return self.discord_bot.get_role(role_id)

    def get_member(self, member_id):
        return self.discord_bot.get_member(member_id)

    def get_member_value(self, key, extra={}):
        if len(extra["argument"]) != 22:
            return getattr(extra["author"], key)
        member = self.get_member(extra["argument"][3:][:-1])
        return_val = getattr(member, key) if member else None
        return return_val

    def get_currency(self, key, extra={}):
        return self.bot.get_currency().get(key) if key else None

    def get_user(self, key, extra={}):
        user = (
            self.get_member(extra["argument"][3:][:-1]) if extra["argument"] else None
        )
        if not user:
            user = extra["author"]
        with DBManager.create_session_scope() as db_session:
            db_user = User._create_or_get_by_discord_id(db_session, user.id)
            return getattr(db_user, key) if db_user else None

    def rest(self, key, extra={}):
        return " ".join(extra["message"].split(" ")[int(key) :])

    def get_role_value(self, key, extra={}):
        role_name = extra["argument"]
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
            if len(role_str) > 1024:
                continuation_string = (
                    "and {numeric_number} more roles not displayed due to embed limits."
                )
                available_length = 1024 - len(continuation_string)

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
        commands = list(self.bot.commands.keys())
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
        if key not in self.bot.commands:
            return f"Cannot find command {key}"
        command = self.bot.commands[key]
        data = discord.Embed(description=(key), colour=discord.Colour.dark_gold())
        if command.id:
            data.add_field(name=("ID"), value=command.id)
        data.add_field(name=("Level"), value=command.level)
        data.add_field(name=("Delay All"), value=command.delay_all)
        data.add_field(name=("Delay User"), value=command.delay_user)
        data.add_field(name=("Enabled"), value="Yes" if command.enabled else "No")
        currency = self.bot.get_currency().get("name")
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
        if command.description:
            data.add_field(name=("Description"), value=command.description)
        else:
            data.add_field(name=("Response"), value=command.action.response)
        data.set_thumbnail(url=extra["message_raw"].guild.icon_url)

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
