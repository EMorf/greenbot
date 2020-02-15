import logging

import json
import random
import discord
import string
from datetime import timedelta
import regex as re
from datetime import datetime

from sqlalchemy.orm import joinedload

from greenbot import utils
from greenbot.exc import InvalidPointAmount
from greenbot.managers.db import DBManager
from greenbot.managers.schedule import ScheduleManager
from greenbot.managers.redis import RedisManager
from greenbot.models.command import Command
from greenbot.models.message import Message
from greenbot.models.user import User
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting

log = logging.getLogger(__name__)

TIME_RE_STRING = r"\s?".join(
    [
        r"((?P<weeks>\d+?)\s?(weeks?|w))?",
        r"((?P<days>\d+?)\s?(days?|d))?",
        r"((?P<hours>\d+?)\s?(hours?|hrs|hr?))?",
        r"((?P<minutes>\d+?)\s?(minutes?|mins?|m(?!o)))?",  # prevent matching "months"
        r"((?P<seconds>\d+)\s?(seconds?|secs?|s?))?",
    ]
)

TIME_RE = re.compile(TIME_RE_STRING, re.I)

def parse_timedelta(
    argument,
    maximum = None,
    minimum = None,
    allowed_units = None,
):
    matches = TIME_RE.match(argument)
    allowed_units = allowed_units or ["weeks", "days", "hours", "minutes", "seconds"]
    if matches:
        params = {k: int(v) for k, v in matches.groupdict().items() if v is not None}
        for k in params.keys():
            if k not in allowed_units:
                return None
        if params:
            delta = timedelta(**params)
            if maximum and maximum < delta:
                return None
            if minimum and delta < minimum:
                return None
            return delta
    return None

def seconds_to_resp(seconds):
    time_data = {
        "week": int(seconds // 604800),
        "day": int((seconds % 604800) // 86400),
        "hour": int((seconds % 86400) // 3600),
        "minute": int((seconds % 3600) // 60),
        "second": int(seconds % 60)
    }
    response = []
    for item in time_data:
        if time_data[item] > 0:
            response.append(f"{time_data[item]} {item}{'s' if time_data[item] > 1 else ''}")
    response_str = ", ".join(response[:-1])
    return response_str + f"{'and ' if response_str != '' else ''}{response[-1]}"

def random_string(length=10):
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

def parse_date(string):
    if ":" in string[-5:]:
        string = f"{string[:-5]}{string[-5:-3]}{string[-2:]}"
    return datetime.strptime(string, "%Y-%m-%d %H:%M:%S.%f%z")

class RemindMe(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "RemindMe"
    DESCRIPTION = "Allows users to create reminders"
    CATEGORY = "Feature"

    SETTINGS = [
        ModuleSetting(
            key="max_reminders_per_user",
            label="Maximum reminders per user",
            type="int",
            placeholder="",
            default=3,
        ),
        ModuleSetting(
            key="cost",
            label="Points required to add a reminder",
            type="number",
            placeholder="",
            default="0",
        ),
        ModuleSetting(
            key="emoji",
            label="Emoji for reminder",
            type="text",
            placeholder="🔔",
            default="🔔",
        ),
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.redis = RedisManager.get()
        self.reminder_tasks = {}

    @property
    def help(self):
        help_desc = f"""
        `Syntax: {self.bot.command_prefix}remindme <time> <text>`
        Send you <text> when the time is up.
        Accepts: seconds, minutes, hours, days, weeks
        Examples:
        - {self.bot.command_prefix}remindme 2min Do that thing in 2 minutes
        - {self.bot.command_prefix}remindme 3h40m Do that thing in 3 hours and 40 minutes
        """
        data = discord.Embed(title="RemindMe help Menu", description=help_desc, colour=discord.Colour.red())
        data.set_thumbnail(url=self.bot.discord_bot.client.user.avatar_url)
        return data

    async def create_reminder(self, bot, author, channel, message, args):
        command_args = message.split(" ") if message else []
        try:
            reminders_list = json.loads(self.redis.get("remind-me-reminders"))
            """
            { 
                user_id: [
                    {
                        "message_id": message_id,
                        "channel_id": channel_id,
                        "message": message,
                        "date_of_reminder": date_of_reminder,
                        "date_reminder_set": date_reminder_set
                    },
                ],
            }
            """
        except:
            self.redis.set("remind-me-reminders", json.dumps({}))
            reminders_list = {}
        user_reminders = reminders_list[str(author.id)] if str(author.id) in reminders_list else []
        if len(user_reminders) >= int(self.settings["max_reminders_per_user"]):
            await self.bot.say(channel, f"{author.mention} you already have {len(user_reminders)} reminders!")
            return False
        if len(command_args) == 0:
            await self.bot.say(channel, embed=self.help)
            return False
        time_delta = parse_timedelta(command_args[0])
        if not time_delta:
            await self.bot.say(channel, f"{author.mention} invalid time: {command_args[0]}")
            return False
        await self.bot.say(channel, f"{author.mention} ill remind you that in {seconds_to_resp(time_delta.total_seconds())}")
        bot_message = await self.bot.say(channel, f"If anyone else wants to be reminded click the {self.settings['emoji']}")
        salt = random_string()
        await bot_message.add_reaction(self.settings['emoji'])
        reminder = {
            "message_id": bot_message.id,
            "channel_id": bot_message.channel.id,
            "salt": salt,
            "message": " ".join(command_args[1:]),
            "date_of_reminder": str(utils.now() + time_delta),
            "date_reminder_set": str(utils.now())
        }
        user_reminders.append(reminder)
        reminders_list[str(author.id)] = user_reminders
        self.redis.set("remind-me-reminders", json.dumps(reminders_list))
        self.reminder_tasks[salt] = ScheduleManager.execute_delayed(time_delta.total_seconds(), self.execute_reminder, args=[salt, author.id, reminder])


    async def forgetme(self, bot, author, channel, message, args):
        try:
            reminders_list = json.loads(self.redis.get("remind-me-reminders"))
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
            self.redis.set("remind-me-reminders", json.dumps({}))
            reminders_list = {}
        user_reminders = reminders_list[str(author.id)] if str(author.id) else []
        for reminder in user_reminders:
            self.reminder_tasks.pop(reminder["salt"]).remove()
            try:
                channel = self.bot.discord_bot.guild.get_channel(int(reminder["channel_id"]))
                bot_message = await channel.fetch_message(int(reminder["message_id"]))
                await bot_message.delete()  
            except Exception as e:
                log.error(f"Failed to delete message from bot: {e}")
        reminders_list[str(author.id)] = []
        self.redis.set("remind-me-reminders", json.dumps(reminders_list))
        await self.bot.say(channel, f"{author.mention} you have been forgotten")

    def load_commands(self, **options):
        self.commands["remindme"] = Command.raw_command(
            self.create_reminder,
            delay_all=0,
            delay_user=0,
            cost=int(self.settings["cost"]),
            can_execute_with_whisper=False,
            description="Creates a reminder",
        )
        self.commands["forgetme"] = Command.raw_command(
            self.forgetme,
            delay_all=0,
            delay_user=0,
            can_execute_with_whisper=False,
            description="Creates a reminder",
        )

    async def execute_reminder(self, salt, user_id, reminder):
        self.reminder_tasks.pop(salt)
        try:
            channel = self.bot.discord_bot.guild.get_channel(int(reminder["channel_id"]))
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
                    date_of_reminder = parse_date(reminder["date_of_reminder"])
                    date_reminder_set = parse_date(reminder["date_reminder_set"])
                    seconds = int(round((date_of_reminder - date_reminder_set).total_seconds()))
                    response_str = seconds_to_resp(seconds)
                    await self.bot.private_message(user, f"Hello! You asked me to remind you {response_str} ago:\n{message}")
                break
        try:
            await bot_message.delete()  
        except Exception as e:
            log.error(f"Failed to delete message from bot: {e}")
        try:
            reminders_list = json.loads(self.redis.get("remind-me-reminders"))
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
            self.redis.set("remind-me-reminders", json.dumps({}))
            reminders_list = {}
        user_reminders = reminders_list[str(user_id)] if str(user_id) in reminders_list else []
        for _reminder in user_reminders:
            if _reminder == reminder:
                user_reminders.remove(_reminder)
                break
        reminders_list[str(user_id)] = user_reminders
        self.redis.set("remind-me-reminders", json.dumps(reminders_list))

    def enable(self, bot):
        if not bot:
            return
        try:
            reminders_list = json.loads(self.redis.get("remind-me-reminders"))
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
            self.redis.set("remind-me-reminders", json.dumps({}))
            reminders_list = {}
        new_reminders_list = {}
        for user_id in reminders_list:
            user_reminders = reminders_list[user_id]
            new_user_reminders = []
            for reminder in user_reminders:
                salt = reminder["salt"]
                date_of_reminder = reminder["date_of_reminder"]
                if ":" in date_of_reminder[-5:]:
                    date_of_reminder = f"{date_of_reminder[:-5]}{date_of_reminder[-5:-3]}{date_of_reminder[-2:]}"
                date_of_reminder = datetime.strptime(date_of_reminder, "%Y-%m-%d %H:%M:%S.%f%z")
                if date_of_reminder < utils.now():
                    continue
                new_user_reminders.append(reminder)
                self.reminder_tasks[salt] = ScheduleManager.execute_delayed((date_of_reminder-utils.now()).total_seconds(), self.execute_reminder, args=[salt, user_id, reminder])
            new_reminders_list[user_id] = new_user_reminders
        self.redis.set("remind-me-reminders", json.dumps(new_reminders_list))

    def disable(self, bot):
        if not bot:
            return
