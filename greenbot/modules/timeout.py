import logging

import json
import discord
from datetime import datetime

from greenbot import utils
from greenbot.managers.schedule import ScheduleManager
from greenbot.managers.redis import RedisManager
from greenbot.managers.db import DBManager
from greenbot.models.command import Command
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting

log = logging.getLogger(__name__)


class Timeout(BaseModule):
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

        only_this_channel = False

        if command_args[0] == "here":
            only_this_channel = True
            command_args = command_args[1:]

        if len(command_args) == 0:
            await self.bot.say(channel=channel, message=f"!untimeout (here) <User mention> (reason...)")
            return False


        member = list(self.bot.filters.get_member_value([command_args[0]], None, {}))[0]
        if not member:
            await self.bot.say(channel=channel, message=f"Cant find member, {command_args[0]}")
            return False
        
        with DBManager.create_session_scope() as db_session:
            user_level = self.bot.psudo_level_member(db_session, member)

        if user_level <= args["user_level"]:
            await self.bot.say(channel=channel, message=f"You cannot timeout a member with a with a level the same or higher than you!")
            return False

        timedelta = utils.parse_timedelta(command_args[1]) if len(command_args) > 1 else None
        reason = " ".join(command_args[1:]) if not timedelta else " ".join(command_args[2:])
        channels = self.bot.discord_bot.guild.text_channels if not only_this_channel else [only_this_channel]
        self.bot.timeout_manager.timeout_user(member, timedelta, channels, reason)

    async def untimeout_user(self, bot, author, channel, message, args):
        command_args = message.split(" ") if message else []
        if len(command_args) == 0:
            await self.bot.say(channel=channel, message=f"!untimeout (here) <User mention> (reason...)")
            return False

        only_this_channel = False

        if command_args[0] == "here":
            only_this_channel = True
            command_args = command_args[1:]

        if len(command_args) == 0:
            await self.bot.say(channel=channel, message=f"!untimeout (here) <User mention> (reason...)")
            return False

        member = list(self.bot.filters.get_member_value([command_args[0]], None, {}))[0]
        if not member:
            await self.bot.say(channel=channel, message=f"Cant find member, {command_args[0]}")
            return False

        channels = self.bot.discord_bot.guild.text_channels if not only_this_channel else [only_this_channel]
        reason = " ".join(command_args[1:])
        self.bot.timeout_manager.untimeout_user(member, channels, reason)

    async def query_timeouts(self, bot, author, channel, message, args):
        command_args = message.split(" ") if message else []
        member = list(self.bot.filters.get_member_value([command_args[0]], None, {}))[0]
        if not member:
            await self.bot.say(channel=channel, message=f"Cant find member, {command_args[0]}")
            return False

        timeouts = self.bot.timeout_manager.query_timeouts(member)
        if not timeouts:
            await self.bot.say(channel=channel, message=f"{member.mention} has no timeouts")
            return True
        count = 1
        await self.bot.say(channel=channel, message=f"{member.mention}'s current timeouts'")
        for timeout in timeouts:
            embed = discord.Embed(
                description=f"Timeout {count}",
                timestamp=timeout["date_issued"],
                colour=member.colour,
            )
            channels = []
            for x in timeout["channels"]:
                channel = list(self.bot.filters.get_channel([int(x)]))[0]
                if channel:
                    channels.append(channel.metion) 

            embed.add_field(
                name="Channels Banned In", value="\n".join(channels), inline=False
            )
            embed.add_field(
                name="Banned on", value=timeout["date_issued"].strftime("%b %d %Y %H:%M:%S %Z"), inline=False
            )
            embed.add_field(
                name="Banned till", value=timeout["date_expired"].strftime("%b %d %Y %H:%M:%S %Z"), inline=False
            )
            embed.add_field(
                name="Timeleft", value=utils.seconds_to_resp((timeout["date_expired"] - timeout["date_issued"]).total_seconds()), inline=False
            )
            embed.add_field(
                name="Banned by", value=timeout["issued_by"], inline=False
            )
            await self.bot.say(channel=channel, embed=embed)
            count += 1
        

    def load_commands(self, **options):
        self.commands["timeout"] = Command.raw_command(
            self.timeout_user,
            delay_all=0,
            delay_user=0,
            cost=int(self.settings["cost"]),
            can_execute_with_whisper=False,
            description="Adds a timeout to a user",
        )
        self.commands["untimeout"] = Command.raw_command(
            self.untimeout_user,
            delay_all=0,
            delay_user=0,
            can_execute_with_whisper=False,
            description="Removes a timeout on a user",
        )
        self.commands["timeouts"] = Command.raw_command(
            self.query_timeouts,
            delay_all=0,
            delay_user=0,
            can_execute_with_whisper=False,
            description="Queries timeouts of a user",
        )
        if self.bot:
            self.bot.timeout_manager.enable()

    async def execute_reminder(self, salt, user_id, reminder):
        self.reminder_tasks.pop(salt)
        try:
            channel = self.bot.discord_bot.guild.get_channel(
                int(reminder["channel_id"])
            )
            bot_message = await channel.fetch_message(int(reminder["message_id"]))
        except:
            return
        message = reminder["message"]
        for reaction in bot_message.reactions:
            if reaction.emoji == self.settings["emoji"]:
                users = await reaction.users().flatten()
                users.remove(self.bot.discord_bot.client.user)
                sender = await self.bot.discord_bot.get_user(user_id)
                if sender and sender not in users:
                    users.append(sender)
                for user in users:
                    date_of_reminder = utils.parse_date(reminder["date_of_reminder"])
                    date_reminder_set = utils.parse_date(reminder["date_reminder_set"])
                    seconds = int(
                        round((date_of_reminder - date_reminder_set).total_seconds())
                    )
                    response_str = utils.seconds_to_resp(seconds)
                    await self.bot.private_message(
                        user,
                        f"Hello! You asked me to remind you {response_str} ago:\n{message}",
                    )
                break
        try:
            await bot_message.delete()
        except Exception as e:
            log.error(f"Failed to delete message from bot: {e}")
        try:
            reminders_list = json.loads(
                self.redis.get(f"{self.bot.bot_name}:remind-me-reminders")
            )
            """
            { 
                user_id: [
                    {
                        "message_id": message_id,
                        "channel_id": channel_id,
                        "salt": salt,
                        "message": message,
                        "date_of_reminder": date_of_reminder,
                        "date_reminder_set": date_reminder_set
                    },
                ],
            }
            """
        except:
            self.redis.set(f"{self.bot.bot_name}:remind-me-reminders", json.dumps({}))
            reminders_list = {}
        user_reminders = (
            reminders_list[str(user_id)] if str(user_id) in reminders_list else []
        )
        for _reminder in user_reminders:
            if _reminder == reminder:
                user_reminders.remove(_reminder)
                break
        reminders_list[str(user_id)] = user_reminders
        self.redis.set(
            f"{self.bot.bot_name}:remind-me-reminders", json.dumps(reminders_list)
        )

    def enable(self, bot):
        if not bot:
            return

        self.bot.timeout_manager.enable({"enabled": True, "log_timeout": self.settings["log_timeout"], "log_untimeout": self.settings["log_untimeout"]})

    def disable(self, bot):
        if not bot:
            return

        self.bot.timeout_manager.disable()
