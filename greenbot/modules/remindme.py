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
            default="3",
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
        pass

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

    def execute_reminder(self, salt, reminder):
        self.reminder_tasks.pop(salt)

    def enable(self, bot):
        if not bot:
            return
        try:
            reminders_list = json.loads(self.redis.get("remind-me-reminders"))
            """
            { 
                user_id: {
                    "message_id": message_id,
                    "message": message,
                    "date_of_reminder": date_of_reminder,
                },
            }
            """
        except:
            self.redis.set("remind-me-reminders", json.dumps({}))
            reminders_list = {}
        new_reminders_list = {}
        for user in reminders_list:
            user_reminders = reminders_list[user]
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
                self.reminder_tasks[salt] = ScheduleManager.execute_delayed((date_of_reminder-utils.now()).seconds, self.execute_reminder, args=[salt, reminder])

    def disable(self, bot):
        if not bot:
            return
