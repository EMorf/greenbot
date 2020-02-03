import logging

import discord
import asyncio
import json
from datetime import datetime, timedelta

from greenbot.managers.db import DBManager
from greenbot.managers.handler import HandlerManager

log = logging.getLogger(__name__)

class CustomClient(discord.Client):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def on_ready(self):
        self.bot.guild = self.get_guild(int(self.settings["discord_guild"]))
        if not self.bot.guild:
            log.error("Discord Guild not found!")
            return
        log.info(f"Discord Bot has started!")
        HandlerManager.trigger("discord_ready")

    async def on_message(self, message):
        member = self.guild.get_member(message.author.id)
        if isinstance(message.author, discord.Member) and (message.guild != self.guild or not message.channel.id in self.setings["channels"]):
            return
        is_admin = False if not member else any(role in self.admin_roles for role in member.roles)
        HandlerManager.trigger("discord_message", message.content, message.author, is_admin, isinstance(message.author, discord.Member))
        log.info(message.content)
        log.info(is_admin)
        log.info(f"{message.author.name}#{message.author.discriminator}\nDiscordID:{message.author.id}")


class DiscordBotManager:
    def __init__(self, bot, settings, redis, private_loop):
        self.bot = bot
        self.settings = settings
        self.client = CustomClient(self)
        
        self.private_loop = private_loop
        self.redis = redis
        self.admin_roles = {}

        self.guild = None
        HandlerManager.add_handler("discord_ready", self.setup_roles, priority=100)

    def setup_roles(self):
        self.private_loop.create_task(self._setup_roles())

    async def _setup_roles(self):
        self.admin_roles = {}
        for role_level in self.admin_roles:
            role_id = role_level["role_id"]
            level = role_level["level"]

            role = self.guild.get_role(role_id)
            if not role:
                log.error(f"Cannot find role {role_id}")
                continue
            self.admin_roles[role] = level

    async def private_message(self, member, message):
        message = discord.utils.escape_markdown(message)
        await self._private_message(member, message)

    async def remove_role(self, member, role):
        await self._remove_role(member, role)

    async def add_role(self, member, role):
        await self._add_role(member, role)

    async def _private_message(self, member, message):
        await member.create_dm()
        await member.dm_channel.send(message)

    async def _remove_role(self, member, role):
        await member.remove_roles(role)

    async def _add_role(self, member, role):
        await member.add_roles(role)

    async def run_periodically(self, wait_time, func, *args):
        while True:
            await asyncio.sleep(wait_time)
            if not self.client.is_closed():
                try:
                    await func(*args)
                except Exception as e:
                    log.error(e)

    def ban(self, user_id, timeout_in_seconds=0, reason=None, delete_message_days=0):
        self.private_loop.create_task(self._ban(user_id=user_id, timeout_in_seconds=timeout_in_seconds, reason=reason, delete_message_days=delete_message_days))

    def unban(self, user_id, reason=None):
        self.private_loop.create_task(self._unban(user_id=user_id, reason=reason))

    async def _ban(self, user_id, timeout_in_seconds=0, reason=None, delete_message_days=0):
        delete_message_days = 7 if delete_message_days > 7 else (0 if delete_message_days < 0 else delete_message_days)

        if not self.guild:
            return
        member = self.guild.get_member(user_id)
        if not member:
            return
        if timeout_in_seconds > 0:
            reason = f"{reason}\nBanned for {timeout_in_seconds} seconds"
            timeouts = json.loads(self.redis.get("timeouts-discord"))
            """
            {
                discord_id: timeout_in_seconds,
            }
            """
            timeouts[member.id] = timeout_in_seconds
        self.guild.ban(member, reason=reason, delete_message_days=delete_message_days)

    async def _unban(self, user_id, reason=None):
        if not self.guild:
            return
        try:
            member = await self.client.fetch_user(user_id)
        except (discord.NotFound, discord.HTTPException):
            return
        self.guild.unban(member, reason)

    def schedule_task_periodically(self, wait_time, func, *args):
        return self.private_loop.create_task(self.run_periodically(wait_time, func, *args))

    async def cancel_scheduled_task(self, task):
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def connect(self):
        self.private_loop.create_task(self._connect())

    async def _connect(self):
        try:
            await self.client.start(self.settings["discord_token"])
        except:
            pass

    def stop(self):
        self.private_loop.create_task(self._stop())

    async def _stop(self):
        log.info("Discord closing")
        await self.client.logout()
        try:
            self.client.clear()
        except:
            pass
