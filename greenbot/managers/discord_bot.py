import logging

import discord
import traceback
import asyncio
import json
from datetime import datetime, timedelta

from greenbot.models.user import User
from greenbot.models.message import Message
from greenbot.managers.db import DBManager
from greenbot.managers.handler import HandlerManager

log = logging.getLogger("greenbot")

class CustomClient(discord.Client):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def on_ready(self):
        self.bot.guild = self.get_guild(int(self.bot.settings["discord_guild_id"]))
        if not self.bot.guild:
            log.error("Discord Guild not found!")
            return
        log.info(f"Discord Bot has started!")
        HandlerManager.trigger("discord_ready")

    async def on_message(self, message):
        member = self.bot.guild.get_member(message.author.id)
        if isinstance(message.author, discord.Member) and (message.guild != self.bot.guild or not message.channel in self.bot.listening_channels):
            return
        user_level = 50
        with DBManager.create_session_scope() as db_session:
            User._create_or_get_by_discord_id(db_session, message.author.id)
            Message._create(db_session, message.id, message.author.id, message.channel.id if isinstance(message.author, discord.Member) else None, message.content)
            HandlerManager.trigger("discord_message", message_raw=message, message=message.content, author=message.author, user_level=member.level, channel=message.channel if isinstance(message.author, discord.Member) else None, whisper=not isinstance(message.author, discord.Member))

    async def on_error(self, event, *args, **kwargs):
        log.error(traceback.format_exc())

class DiscordBotManager:
    def __init__(self, bot, settings, redis, private_loop):
        self.bot = bot
        self.settings = settings
        self.client = CustomClient(self)
        
        self.private_loop = private_loop
        self.redis = redis
        self.listening_channels = []

        self.guild = None
        HandlerManager.add_handler("discord_ready", self.setup, priority=100)

    def setup(self):
        self.private_loop.create_task(self._setup())

    async def _setup(self):
        self.listening_channels = []
        for channel_id in self.settings["channels"]:
            channel = self.guild.get_channel(int(channel_id))
            if not channel:
                log.error(f"Cannot find channel {channel_id}")
                continue
            self.listening_channels.append(channel)

    def private_message(self, user, message, embed=None):
        self.private_loop.create_task(self._private_message(user, message, embed))

    def remove_role(self, user, role):
        self.private_loop.create_task(self._remove_role(user, role))

    def add_role(self, user, role):
        self.private_loop.create_task(self._add_role(user, role))

    def ban(self, user, timeout_in_seconds=0, reason=None, delete_message_days=0):
        self.private_loop.create_task(self._ban(user=user, timeout_in_seconds=timeout_in_seconds, reason=reason, delete_message_days=delete_message_days))

    def unban(self, user_id, reason=None):
        self.private_loop.create_task(self._unban(user_id=user_id, reason=reason))

    def kick(self, user, reason=None):
        self.private_loop.create_task(self._kick(user=user, reason=reason))

    def get_role_id(self, role_name):
        for role in self.guild.roles:
            if role.name == role_name:
                return str(role.id)
        return None

    def get_role(self, role_id):
        try:
            return self.guild.get_role(int(role_id))
        except ValueError:
            return None

    def get_member(self, member_id):
        try:
            return self.guild.get_member(int(member_id))
        except ValueError:
            return None

    def say(self, channel, message, embed=None):
        self.private_loop.create_task(self._say(channel=channel, message=message, embed=embed))
    
    async def _say(self, channel, message, embed=None):
        message = discord.utils.escape_markdown(message)
        if channel:
            if embed:
                message = None
            await channel.send(content=message, embed=embed)

    async def _ban(self, user, timeout_in_seconds=0, reason=None, delete_message_days=0):
        delete_message_days = 7 if delete_message_days > 7 else (0 if delete_message_days < 0 else delete_message_days)

        if not self.guild:
            return
        if not user:
            return
        if timeout_in_seconds > 0:
            reason = f"{reason}\nBanned for {timeout_in_seconds} seconds"
            timeouts = json.loads(self.redis.get("timeouts-discord"))
            """
            {
                discord_id: timeout_in_seconds,
            }
            """
            timeouts[str(user.id)] = timeout_in_seconds
        await self.guild.ban(user=user, reason=reason, delete_message_days=delete_message_days)

    async def _unban(self, user_id, reason=None):
        if not self.guild:
            return
        user = await self.client.fetch_user(user_id)
        await self.guild.unban(user=user, reason=reason)

    async def _kick(self, user, reason=None):
        if not self.guild:
            return
        await self.guild.kick(user=user, reason=reason)

    async def _private_message(self, user, message, embed=None):
        message = discord.utils.escape_markdown(message)
        await user.create_dm()
        if embed:
            message = None
        await user.dm_channel.send(content=message, embed=embed)

    async def _remove_role(self, user, role):
        if not self.guild:
            return
        await user.remove_roles(role)

    async def _add_role(self, user, role):
        if not self.guild:
            return
        await user.add_roles(role)

    async def run_periodically(self, wait_time, func, *args):
        while True:
            await asyncio.sleep(wait_time)
            if not self.client.is_closed():
                try:
                    await func(*args)
                except Exception as e:
                    log.error(e)

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
        except Exception as e:
            log.error(e)

    def stop(self):
        self.private_loop.create_task(self._stop())

    async def _stop(self):
        log.info("Discord closing")
        await self.client.logout()
        try:
            self.client.clear()
        except:
            pass
