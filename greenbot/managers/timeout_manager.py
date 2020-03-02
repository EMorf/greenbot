import logging
import discord
import json
from datetime import datetime

from greenbot.managers.handler import HandlerManager
from greenbot.managers.db import DBManager
from greenbot.managers.schedule import ScheduleManager
from greenbot.models.message import Message
from greenbot.models.user import User

from greenbot import utils

log = logging.getLogger(__name__)


class TimeoutManager:
    def __init__(self, bot, redis):
        self.bot = bot
        self.redis = redis
        self.settings = {
            "enabled": False,
            "log_timeout": False,
            "log_untimeout": False
        }
        self.untimeout_tasks = {}
        try:
            current_timeouts = json.loads(
                self.redis.get(f"{self.bot.bot_name}:timeouts")
            )
            """
            { 
                user_id: [
                    {
                        "salt": salt,
                        "issued_date": issued_date,
                        "issued_expire": issued_expire,
                        "reason": reason,
                        "channels": [],
                        "issued_by": issued_by
                    },
                ],
            }
            """
        except:
            self.redis.set(f"{self.bot.bot_name}:timeouts", json.dumps({}))
            current_timeouts = {}

        for user_id in current_timeouts:
            for timeout in current_timeouts[user_id]:
                salt = timeout["salt"]
                issued_expire = datetime.strptime(
                    utils.parse_date(timeout["date_of_reminder"]),
                    "%Y-%m-%d %H:%M:%S.%f%z",
                )
                self.untimeout_tasks[salt] = ScheduleManager.execute_delayed(
                    (issued_expire - utils.now()).total_seconds(),
                    self.execute_reminder,
                    args=[salt, user_id, timeout],
                )

    async def execute_reminder(self, salt, user_id, timeout):
        self.untimeout_tasks.pop(salt)
        try:
            current_timeouts = json.loads(
                self.redis.get(f"{self.bot.bot_name}:timeouts")
            )
            """
            { 
                user_id: [
                    {
                        "salt": salt,
                        "issued_date": issued_date,
                        "issued_expire": issued_expire,
                        "reason": reason,
                        "channels": [],
                        "issued_by": issued_by
                    },
                ],
            }
            """
        except:
            self.redis.set(f"{self.bot.bot_name}:timeouts", json.dumps({}))
            current_timeouts = {}
        user_timeouts = current_timeouts.get(str(user_id), [])
        for _timeout in user_timeouts:
            if _timeout == timeout:
                user_timeouts.remove(_timeout)
                break
        current_timeouts[str(user_id)] = user_timeouts
        self.redis.set(
            f"{self.bot.bot_name}:timeouts", json.dumps(current_timeouts)
        )
        member = list(self.bot.filters.get_member_value([user_id], None, {}))[0]
        if not member:
            return

        channels = []
        for x in timeout["channels"]:
            channel = list(self.bot.filters.get_channel([int(x)]))[0]
            if channel:
                channels.append(channel.metion) 

        await self.untimeout_user(member, channels, "Untimed out by timer")

    async def timeout_user(self, member, timedelta, channels, reason=""):
        if not self.settings["enabled"]:
            return

        for channel in channels:
            await channel.set_permissions(member, send_messages=False)

    async def untimeout_user(self, member, channels, reason=""):
        if not self.settings["enabled"]:
            return

        for channel in channels:
            overwrite = channel.overwrites_for(member)
            if overwrite.is_empty():
                continue
            overwrite.update({"send_messages": None})
            await channel.set_permissions(member, overwrite=overwrite)

    def query_timeouts(self, member):
        pass

    def enable(self, settings):
        self.settings = settings

    def disable(self):
        self.settings = {
            "enabled": False,
            "log_timeout": False,
            "log_untimeout": False
        }
