import logging
import discord

from greenbot.managers.db import DBManager
from greenbot.models.user import User
from greenbot import utils

log = logging.getLogger("greenbot")


class Functions:
    def __init__(self, bot, filters):
        self.bot = bot
        self.filters = filters

    async def func_kick_member(
        self, args, extra={}
    ):  # !kick <member_mention> <reason....>
        if len(args) != 2:
            return "Invalid Comand Args", None

        author = extra["author"]
        member = list(self.filters.get_member([args[0]], None, extra))[0]
        if not member:
            return "Member not found", None

        with DBManager.create_session_scope() as db_session:
            author_user = User._create_or_get_by_discord_id(
                db_session, str(author.id), user_name=str(author)
            )
            member_user = User._create_or_get_by_discord_id(
                db_session, str(member.id), user_name=str(member)
            )
            if max(author_user.level, self.bot.psudo_level_member(author_user)) <= max(
                member_user.level, self.bot.psudo_level_member(member_user)
            ):
                return (
                    "You cannot kick someone who has the same or a higher level than you :)",
                    None,
                )

        reason = args[1]
        resp = await self.bot.kick(member, f"{reason}\nKicked by {author}")
        if not resp:
            return f"Failed to kick member {member}!", None

        return f"Member {member.mention} has been kicked by {author.mention}!", None

    async def func_ban_member(self, args, extra={}):
        if len(args) != 4:
            return "Invalid Comand Args", None
        member = list(self.filters.get_member([args[0]], None, extra))[0]
        author = extra["author"]
        if not member:
            return "Member not found", None
        with DBManager.create_session_scope() as db_session:
            author_user = User._create_or_get_by_discord_id(
                db_session, str(author.id), user_name=str(author)
            )
            member_user = User._create_or_get_by_discord_id(
                db_session, str(member.id), user_name=str(member)
            )
            if author.id == member.id:
                return "You cannot ban yourself :)", None

            if max(author_user.level, self.bot.psudo_level_member(author_user)) <= max(
                member_user.level, self.bot.psudo_level_member(member_user)
            ):
                return (
                    "You cannot ban someone who has the same or a higher level than you :)",
                    None,
                )

        time_to_parse = utils.parse_timedelta(args[1])
        if not time_to_parse:
            return (
                f"Invalid timeout in seconds {args[1]}",
                None,
            )

        timeout_in_seconds = time_to_parse.total_seconds()

        try:
            delete_message_days = int(args[2])
        except ValueError:
            return (
                f"Invalid delete message days {args[2]}!",
                None,
            )

        reason = args[3]

        resp = await self.bot.ban(
            user=member,
            timeout_in_seconds=timeout_in_seconds,
            delete_message_days=delete_message_days,
            reason=f"{reason}\nBanned by {author}",
        )
        if not resp:
            return f"Failed to ban member {member.mention}!", None

        return f"Member {member.mention} has been banned!", None

    async def func_unban_member(self, args, extra={}):
        if len(args) != 2:
            return "Invalid Comand Args", None

        member_id = args[0][3:][:-1]
        author = extra["author"]
        reason = args[1]

        resp = await self.bot.unban(
            user_id=member_id, reason=f"{reason}\nUnbanned by {author}",
        )
        if not resp:
            return f"Failed to unban member <@!{member_id}>!", None
        return f"Member <@!{member_id}> has been unbanned!", None

    async def func_add_role_member(self, args, extra={}):
        if len(args) != 3:
            return "Invalid Comand Args", None

        author = extra["author"]
        member = list(self.filters.get_member([args[0]], None, extra))[0]
        if not member:
            return f"Invalid Member, {args[0]}", None

        role = list(self.filters.get_role([args[1]], None, extra))[0]
        if not role:
            return f"Invalid Role, {args[1]}", None

        reason = args[2]
        resp = await self.bot.add_role(
            user=member, role=role, reason=f"{reason}\nAdded by {author}",
        )
        if not resp:
            return f"Failed to add role ({role}) to user {member.mention}!", None

        return f"Role {role.name} has been added to {member.mention}!", None

    async def func_remove_role_member(self, args, extra={}):
        if len(args) != 3:
            return "Invalid Comand Args", None

        author = extra["author"]
        member = list(self.filters.get_member([args[0]], None, extra))[0]
        if not member:
            return f"Invalid Member {args[0]}", None

        role = list(self.filters.get_role([args[1]], None, extra))[0]
        if not role:
            return f"Invalid Role {args[1]}", None

        reason = args[2]
        resp = await self.bot.remove_role(
            user=member, role=role, reason=f"{reason}\nRemoved by {author}",
        )
        if not resp:
            return f"Failed to remove role {role} from user {member.mention}!", None

        return f"Role {role.name} has been removed from {member.mention}!", None

    async def func_level(self, args, extra={}):
        if len(args) != 2:
            return "Invalid Comand Args", None

        member = list(self.filters.get_member([args[0]], None, extra))[0]
        if not member:
            return f"Invalid Member {args[0]}", None

        if member == extra["author"]:
            return "You cannot edit your own level :)", None

        level = args[1]
        try:
            level = int(level)
        except ValueError:
            return f"Invalid level (1-2000) {args[1]}", None

        if level >= extra["user_level"]:
            return "You cannot set a level higher then your own!", None

        with DBManager.create_session_scope() as db_session:
            user = User._create_or_get_by_discord_id(db_session, str(member.id), str(member))
            if user.level >= extra["user_level"]:
                return (
                    "You cannot set a level of a user with a higher then your own!",
                    None,
                )
            user.level = level
        return f"Level, {level}, set for {member.mention}!", None

    async def func_set_balance(self, args, extra={}):
        if len(args) == 2:
            return "Invalid Comand Args", None

        member = list(self.filters.get_member([args[0]], None, extra))[0]
        if not member:
            return f"Invalid Member {args[0]}", None

        try:
            amount = int(args[1])
        except ValueError:
            return (
                f"Invalid points amount, please enter a valid positive integer not {args[0]}",
                None,
            )

        with DBManager.create_session_scope() as db_session:
            user = User._create_or_get_by_discord_id(db_session, str(member.id), str(member))
            user.points = amount
        currency = self.bot.get_currency().get("name").capitalize()
        return f"{currency} balance for {member.mention} set to {amount}", None

    async def func_adj_balance(self, args, extra={}):
        if len(args) == 2:
            return "Invalid Comand Args", None

        member = list(self.filters.get_member([args[0]], None, extra))[0]
        if not member:
            return f"Invalid Member {args[0]}", None

        try:
            amount = int(args[1])
        except ValueError:
            return (
                f"Invalid points amount, please enter a valid positive integer not {args[0]}",
                None,
            )

        with DBManager.create_session_scope() as db_session:
            user = User._create_or_get_by_discord_id(db_session, str(member.id), str(member))
            user.points += amount
        action = "added to" if amount > 0 else "removed from"
        currency = self.bot.get_currency().get("name")
        return f"{amount} {currency} {action} {member.mention} ", None

    async def func_output(self, args, extra={}):
        return f"args: {args}\nextra: {extra}", None

    async def func_embed_image(self, args, extra={}):
        data = discord.Embed()
        data.set_image(url=args[0])
        return None, data
