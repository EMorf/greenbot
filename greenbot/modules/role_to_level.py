import logging

import json

from greenbot import utils
from greenbot.managers.redis import RedisManager
from greenbot.managers.db import DBManager
from greenbot.models.command import Command
from greenbot.models.user import User
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting

log = logging.getLogger(__name__)


class RoleToLevel(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "RoleToLevel"
    DESCRIPTION = "Gives level based on roles in discord"
    CATEGORY = "Feature"

    SETTINGS = [
        ModuleSetting(
            key="level",
            label="Level required to manage roles",
            type="number",
            placeholder=1500,
            default=1500,
        ),
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.redis = RedisManager.get()
        if self.bot:
            self.bot.roles = {}

    async def add_role_level(self, bot, author, channel, message, args):
        command_args = message.split(" ") if message else []
        role = self.bot.filters.get_role(command_args[0])
        if not role:
            await self.bot.say(channel, f"Invalid role id {command_args[0]}")
            return

        try:
            self.bot.roles = json.loads(
                self.redis.get(f"{self.bot.bot_name}:role-level")
            )
        except:
            self.redis.set(f"{self.bot.bot_name}:role-level", json.dumps({}))
            self.bot.roles = {}

        if str(role.id) in self.bot.roles:
            await self.bot.say(
                channel,
                f"Level, {self.bot.roles.get(str(role.id))} has already been assigned to a {role.mention}",
            )
            return
        level = int(command_args[1])
        if level >= args["user_level"]:
            await self.bot.say(
                channel, f"You cant set a level higher then your current level"
            )
            return
        self.bot.roles[str(role.id)] = level
        self.redis.set(f"{self.bot.bot_name}:role-level", json.dumps(self.bot.roles))
        await self.bot.say(
            channel, f"Level, {command_args[1]} assigned to role, {role.mention}"
        )

    async def remove_role_level(self, bot, author, channel, message, args):
        command_args = message.split(" ") if message else []
        if command_args[0] in self.bot.roles:
            del self.bot.roles[str(command_args[0])]
            self.redis.set(
                f"{self.bot.bot_name}:role-level", json.dumps(self.bot.roles)
            )
            await self.bot.say(channel, f"Removed role with id {command_args[0]}")
            return
        role = self.bot.filters.get_role(command_args[0])
        if not role:
            await self.bot.say(channel, f"Invalid role id {command_args[0]}")
            return

        try:
            self.bot.roles = json.loads(
                self.redis.get(f"{self.bot.bot_name}:role-level")
            )
        except:
            self.redis.set(f"{self.bot.bot_name}:role-level", json.dumps({}))
            self.bot.roles = {}

        if str(role.id) not in self.bot.roles:
            await self.bot.say(channel, f"{role.mention} doesnt have a level assigned")
            return

        del self.bot.roles[str(role.id)]

        self.redis.set(f"{self.bot.bot_name}:role-level", json.dumps(self.bot.roles))
        await self.bot.say(channel, f"{role.mention} no longer has a level")

    def load_commands(self, **options):
        self.commands["addrolelevel"] = Command.raw_command(
            self.add_role_level,
            delay_all=0,
            delay_user=0,
            level=int(self.settings["level"]),
            can_execute_with_whisper=True,
            description="Adds Level to role",
        )
        self.commands["removerolelevel"] = Command.raw_command(
            self.remove_role_level,
            delay_all=0,
            delay_user=0,
            level=int(self.settings["level"]),
            can_execute_with_whisper=True,
            description="Removes Level from role",
        )

    def enable(self, bot):
        if not bot:
            return
        try:
            self.bot.roles = json.loads(
                self.redis.get(f"{self.bot.bot_name}:role-level")
            )
        except:
            self.redis.set(f"{self.bot.bot_name}:role-level", json.dumps({}))
            self.bot.roles = {}

    def disable(self, bot):
        if not bot:
            return
        self.bot.roles = {}
