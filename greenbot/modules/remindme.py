import logging

import json
import random
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

def random_string(length=10):
    return ''.join(random.choice(str.ascii_lowercase) for i in range(length))

def parse_date(string):
    if ":" in string[-5:]:
        string = f"{string[:-5]}{string[-5:-3]}{string[-2:]}"
    return datetime.strptime(string, "%Y-%m-%d %H:%M:%S.%f%z")

class ActivityTracker(BaseModule):
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
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.redis = RedisManager.get()
        self.reminder_tasks = {}

    def create_reminder(self, bot, author, channel, message, args):
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
            self.bot.say(channel, f"{author.mention} you already have {len(user_reminders)} reminders!")
            return False
        


    def myreminders(self, bot, author, channel, message, args):
        pass

    def forgetme(self, bot, author, channel, message, args):
        pass

    def load_commands(self, **options):
        self.commands["remindme"] = Command.raw_command(
            self.create_reminder,
            delay_all=0,
            delay_user=0,
            cost=self.settings["cost"],
            can_execute_with_whisper=False,
            description="Creates a reminder",
        )
        self.commands["myreminders"] = Command.raw_command(
            self.myreminders,
            delay_all=0,
            delay_user=0,
            cost=self.settings["cost"],
            description="Creates a reminder",
        )
        self.commands["forgetme"] = Command.raw_command(
            self.forgetme,
            delay_all=0,
            delay_user=0,
            can_execute_with_whisper=False,
            description="Creates a reminder",
        )


    def execute_reminder(self, salt, user_id, reminder):
        self.reminder_tasks.pop(salt)
        channel = self.bot.private_loop.run_until_complete(self.bot.discord_bot.guild.get_channel(int(reminder["channel_id"])))
        bot_message = channel.fetch_message(int(reminder["message_id"]))
        message = reminder["message"]
        for reaction in bot_message.reactions:
            if reaction.emoji == self.settings["reaction_emoji"]:
                users = self.bot.private_loop.run_until_complete(reaction.users().flatten())
                sender = self.bot.private_loop.run_until_complete(self.bot.discord_bot.get_user(user_id))
                if sender:
                    users.append(sender)
                for user in users:
                    date_of_reminder = parse_date(reminder["date_of_reminder"])
                    date_reminder_set = parse_date(reminder["date_reminder_set"])
                    seconds = (date_of_reminder - date_reminder_set).total_seconds()
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
                    "5 weeks, 2 days, 3 hours, 5 minutes and 30 seconds"
                    response_str = ", ".join(response[:-1])
                    response_str += f"{'and ' if response_str != '' else ''}{response[-1]}"
                    self.bot.private_message(user, f"Hello! You asked me to remind you this {response_str} ago:\n{message}")
                break

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
                salt = random_string()
                date_of_reminder = reminder["date_of_reminder"]
                if ":" in date_of_reminder[-5:]:
                    date_of_reminder = f"{date_of_reminder[:-5]}{date_of_reminder[-5:-3]}{date_of_reminder[-2:]}"
                date_of_reminder = datetime.strptime(date_of_reminder, "%Y-%m-%d %H:%M:%S.%f%z")
                if date_of_reminder < utils.now():
                    continue
                new_user_reminders.append(reminder)
                self.reminder_tasks[salt] = ScheduleManager.execute_delayed((date_of_reminder-utils.now()).seconds, self.execute_reminder, args=[salt, user_id, reminder])
            new_reminders_list[user_id] = new_user_reminders
        self.redis.set("remind-me-reminders", json.dumps(new_reminders_list))

    def disable(self, bot):
        if not bot:
            return
