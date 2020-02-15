import logging

import json
import random
import discord
import string
from datetime import timedelta
import regex as re
from datetime import datetime

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


class AdvancedAdminLog(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "AdvancedAdminLog"
    DESCRIPTION = "Logs Everything"
    CATEGORY = "Feature"

    SETTINGS = [
        # ModuleSetting(
        #     key="max_reminders_per_user",
        #     label="Maximum reminders per user",
        #     type="int",
        #     placeholder="",
        #     default=3,
        # ),
        # ModuleSetting(
        #     key="cost",
        #     label="Points required to add a reminder",
        #     type="number",
        #     placeholder="",
        #     default="0",
        # ),
        # ModuleSetting(
        #     key="emoji",
        #     label="Emoji for reminder",
        #     type="text",
        #     placeholder="🔔",
        #     default="🔔",
        # ),
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    async def create_reminder(self, bot, author, channel, message, args):
        pass

    def load_commands(self, **options):
        # self.commands["remindme"] = Command.raw_command(
        #     self.create_reminder,
        #     delay_all=0,
        #     delay_user=0,
        #     cost=int(self.settings["cost"]),
        #     can_execute_with_whisper=False,
        #     description="Creates a reminder",
        # )
        pass

    def enable(self, bot):
        if not bot:
            return

    def disable(self, bot):
        if not bot:
            return
