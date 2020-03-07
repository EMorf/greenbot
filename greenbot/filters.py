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

    def get_role(self, args, key, extra):
        role = self.discord_bot.get_role(args[0]) or self.discord_bot.get_role_by_name(
            args[0]
        )
        return getattr(role, key) if key else (role if role else None), None

    def get_role_value(self, args, key, extra):
        role_name = args[0]
        role = list(self.get_role([role_name], None, extra))[0]
        if not role:
            return f"Role {role_name} not found"
        return getattr(role, key) if role else None, None

    def get_member(self, args, key, extra):
        member = self.discord_bot.get_member(args[0]) if args[0] else extra["author"]
        return getattr(member, key) if key and member else member, None

    def get_member_value(self, args, key, extra):
        return list(self.get_member([args[0][3:][:-1]], key, extra))[0], None

    def get_currency(self, args, key, extra):
        return self.bot.get_currency().get(key) if key else None, None

    def get_user(self, args, key, extra):
        member = list(self.get_member_value([args[0]], None, extra))[0]
        if not member:
            member = extra["author"]
        with DBManager.create_session_scope() as db_session:
            db_user = User._create_or_get_by_discord_id(db_session, member.id, str(member))
            return getattr(db_user, key) if key and db_user else db_user, None

    def get_user_info(self, args, key, extra):
        try:
            member = list(self.get_member(int(args[0]), None, extra))[0]
            log.info(member)
        except:
            member = None
        message = extra["message_raw"]
        if not member:
            member = extra["author"]

        roles = member.roles[-1:0:-1]

        joined_at = member.joined_at
        since_created = (message.created_at - member.created_at).days
        if joined_at is not None:
            since_joined = (message.created_at - joined_at).days
            user_joined = joined_at.strftime("%d %b %Y %H:%M")
        else:
            since_joined = "?"
            user_joined = "Unknown"
        user_created = member.created_at.strftime("%d %b %Y %H:%M")
        voice_state = member.voice

        created_on = ("{}\n({} days ago)").format(user_created, since_created)
        joined_on = ("{}\n({} days ago)").format(user_joined, since_joined)

        activity = ("Chilling in {} status").format(member.status)
        if member.activity is None:  # Default status
            pass
        elif member.activity.type == discord.ActivityType.playing:
            activity = ("Playing {}").format(member.activity.name)
        elif member.activity.type == discord.ActivityType.streaming:
            activity = ("Streaming [{}]({})").format(
                member.activity.name, member.activity.url
            )
        elif member.activity.type == discord.ActivityType.listening:
            activity = ("Listening to {}").format(member.activity.name)
        elif member.activity.type == discord.ActivityType.watching:
            activity = ("Watching {}").format(member.activity.name)

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

        data = discord.Embed(description=activity, colour=member.colour)
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
        data.set_footer(text=(f"User ID: {member.id}"))

        name = str(member)
        name = " ~ ".join((name, member.nick)) if member.nick else name
        if member.avatar:
            avatar = member.avatar_url_as(static_format="png")
            data.set_author(name=name, url=avatar)
            data.set_thumbnail(url=avatar)
        else:
            data.set_author(name=name)
        return None, data

    def get_role_info(self, args, key, extra):
        role_name = extra["message"]
        role = list(self.get_role([role_name], None, extra))[0]
        if not role:
            return f"Role {role_name} not found", None
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
        return None, data

    def get_commands(self, args, key, extra):
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
        return None, data

    def get_command_info(self, args, key, extra):
        if args[0] not in self.bot.commands:
            return f"Cannot find command {args[0]}", None
        command = self.bot.commands[args[0]]
        data = discord.Embed(description=(args[0]), colour=discord.Colour.dark_gold())
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

        return None, data

    def get_time_value(self, args, key, extra):
        try:
            tz = timezone(key)
            return datetime.datetime.now(tz).strftime("%H:%M"), None
        except:
            log.exception("Unhandled exception in get_time_value")
        return None, None

    def get_channel(self, args, key, extra):
        channel = self.discord_bot.guild.get_channel(args[0])
        return getattr(channel, key) if key else (channel if channel else None), None

    @staticmethod
    def get_command_value(args, key, extra):
        if key:
            return getattr(extra["command"].data, key), None
        else:
            return extra["command"].data, None

    @staticmethod
    def get_author_value(args, key, extra):
        if key:
            return getattr(extra["author"], key), None
        else:
            return extra["author"], None

    @staticmethod
    def get_channel_value(args, key, extra):
        if key:
            return getattr(extra["channel"], key), None
        else:
            return extra["channel"], None
