import logging

import json
import discord
from datetime import datetime

from greenbot import utils
from greenbot.managers.schedule import ScheduleManager
from greenbot.managers.redis import RedisManager
from greenbot.managers.db import DBManager
from greenbot.models.command import Command
from greenbot.models.timeout import Timeout
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting

log = logging.getLogger(__name__)


class TimeoutModule(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "Timeout"
    DESCRIPTION = "Allows moderators to timeout users"
    CATEGORY = "Feature"

    SETTINGS = [
        ModuleSetting(
            key="level_for_command",
            label="Level required to timeout user",
            type="number",
            placeholder="",
            default=500,
        ),
        ModuleSetting(
            key="log_timeout",
            label="Log timeout Event",
            type="boolean",
            placeholder="",
            default=True,
        ),
        ModuleSetting(
            key="log_untimeout",
            label="Log untimeout Event",
            type="boolean",
            placeholder="",
            default=True,
        ),
        ModuleSetting(
            key="log_timeout_update",
            label="Log timeout_update Event",
            type="boolean",
            placeholder="",
            default=True,
        ),
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.redis = RedisManager.get()
        self.reminder_tasks = {}

    async def timeout_user(self, bot, author, channel, message, args): # !timeout <here> @username
        command_args = message.split(" ") if message else []

        if len(command_args) == 0:
            await self.bot.say(channel=channel, message=f"!timeout (here) <User mention> <duration> (reason...)")
            return False

        member = list(self.bot.filters.get_member_value([command_args[0]], None, {}))[0]
        if not member:
            await self.bot.say(channel=channel, message=f"Cant find member, {command_args[0]}")
            return False
        
        with DBManager.create_session_scope() as db_session:
            user_level = self.bot.psudo_level_member(db_session, member)

            if user_level >= args["user_level"]:
                await self.bot.say(channel=channel, message=f"You cannot timeout a member with a with a level the same or higher than you!")
                return False

            timedelta = utils.parse_timedelta(command_args[1]) if len(command_args) > 1 else None
            ban_reason = " ".join(command_args[1:]) if not timedelta else " ".join(command_args[2:])
            success, resp = await self.bot.timeout_manager.timeout_user(db_session, member, author, utils.now() + timedelta, ban_reason)
            if success:
                return True

            self.bot.say(channel=channel, messgae=resp)
            return False

    async def untimeout_user(self, bot, author, channel, message, args):
        command_args = message.split(" ") if message else []
        if len(command_args) == 0:
            await self.bot.say(channel=channel, message=f"!untimeout (here) <User mention> (reason...)")
            return False

        member = list(self.bot.filters.get_member_value([command_args[0]], None, {}))[0]
        if not member:
            await self.bot.say(channel=channel, message=f"Cant find member, {command_args[0]}")
            return False

        unban_reason = " ".join(command_args[1:])

        with DBManager.create_session_scope() as db_session:
            success, resp = await self.bot.timeout_manager.untimeout_user(db_session, member, author, unban_reason)
            if success:
                return True

            self.bot.say(channel=channel, messgae=resp)
            return False

    async def query_timeouts(self, bot, author, channel, message, args):
        command_args = message.split(" ") if message else []
        member = list(self.bot.filters.get_member_value([command_args[0]], None, {}))[0]
        if not member:
            await self.bot.say(channel=channel, message=f"Cant find member, {command_args[0]}")
            return False
        with DBManager.create_session_scope() as db_session:
            timeouts = Timeout._by_user_id(db_session, str(member.id))

            if not timeouts:
                await self.bot.say(channel=channel, message=f"The user {member} has no timeouts")
                return True

            for timeout in timeouts:                    
                embed = discord.Embed(
                    description=f"Timeout #{timeout.id}",
                    timestamp=timeout.created_at,
                    colour=member.colour,
                )
                embed.add_field(
                    name="Banned on", value=str(timeout.created_at.strftime("%b %d %Y %H:%M:%S %Z")), inline=False
                )
                embed.add_field(
                    name="Banned till" if timeout.time_left != 0 else "Unbanned on", value=str(timeout.until.strftime("%b %d %Y %H:%M:%S %Z")) if timeout.until else "Permanently", inline=False
                )
                if timeout.time_left != 0:
                    embed.add_field(
                        name="Timeleft", value=str(utils.seconds_to_resp(timeout.time_left)), inline=False
                    )
                if timeout.issued_by:
                    embed.add_field(
                        name="Banned by", value=str(timeout.issued_by), inline=False
                    )
                if timeout.ban_reason:
                    embed.add_field(
                        name="Ban Reason", value=str(timeout.ban_reason), inline=False
                    )
                if timeout.time_left != 0 and timeout.unban_reason:
                    embed.add_field(
                        name="Unban Reason", value=str(timeout.unban_reason), inline=False
                    )
                await self.bot.say(channel=channel, embed=embed)

    async def is_timedout(self, bot, author, channel, message, args):
        command_args = message.split(" ") if message else []
        member = list(self.bot.filters.get_member_value([command_args[0]], None, {}))[0]
        if not member:
            await self.bot.say(channel=channel, message=f"Cant find member, {command_args[0]}")
            return False
        with DBManager.create_session_scope() as db_session:
            timeout = Timeout._is_timedout(db_session, str(member.id))

            if not timeout:
                await self.bot.say(channel=channel, message=f"The user {member} has not currently timedout")
                return True

            embed = discord.Embed(
                description=f"Timeout #{timeout.id}",
                timestamp=timeout.created_at,
                colour=member.colour,
            )
            embed.add_field(
                name="Banned on", value=str(timeout.created_at.strftime("%b %d %Y %H:%M:%S %Z")), inline=False
            )
            embed.add_field(
                name="Banned till" if timeout.time_left != 0 else "Unbanned on", value=str(timeout.until.strftime("%b %d %Y %H:%M:%S %Z")) if timeout.until else "Permanently", inline=False
            )
            if timeout.time_left != 0:
                embed.add_field(
                    name="Timeleft", value=str(utils.seconds_to_resp(timeout.time_left)), inline=False
                )
            if timeout.issued_by:
                embed.add_field(
                    name="Banned by", value=str(timeout.issued_by), inline=False
                )
            if timeout.ban_reason:
                embed.add_field(
                    name="Ban Reason", value=str(timeout.ban_reason), inline=False
                )
            if timeout.time_left != 0 and timeout.unban_reason:
                embed.add_field(
                    name="Unban Reason", value=str(timeout.unban_reason), inline=False
                )
            await self.bot.say(channel=channel, embed=embed)
        

    def load_commands(self, **options):
        self.commands["timeout"] = Command.raw_command(
            self.timeout_user,
            delay_all=0,
            delay_user=0,
            level=int(self.settings["level_for_command"]),
            can_execute_with_whisper=False,
            description="Adds a timeout to a user",
        )
        self.commands["untimeout"] = Command.raw_command(
            self.untimeout_user,
            delay_all=0,
            delay_user=0,
            level=int(self.settings["level_for_command"]),
            can_execute_with_whisper=False,
            description="Removes a timeout on a user",
        )
        self.commands["timeouts"] = Command.raw_command(
            self.query_timeouts,
            delay_all=0,
            delay_user=0,
            level=int(self.settings["level_for_command"]),
            can_execute_with_whisper=False,
            description="Queries timeouts of a user",
        )
        self.commands["istimedout"] = Command.raw_command(
            self.is_timedout,
            delay_all=0,
            delay_user=0,
            level=int(self.settings["level_for_command"]),
            can_execute_with_whisper=False,
            description="Checks if the user is currently timedout",
        )

    def enable(self, bot):
        if not bot:
            return

        self.bot.timeout_manager.enable({"enabled": True, "log_timeout": self.settings["log_timeout"], "log_untimeout": self.settings["log_untimeout"]})

    def disable(self, bot):
        if not bot:
            return

        self.bot.timeout_manager.disable()
