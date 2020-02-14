import logging

import discord
import traceback
import asyncio
import json
from datetime import datetime, timedelta

from greenbot.models.user import User
from greenbot.models.message import Message
from greenbot.managers.db import DBManager
from greenbot.managers.schedule import ScheduleManager
from greenbot.managers.handler import HandlerManager
import greenbot.utils as utils

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
        log.info(f"Discord Bot has started with id {self.user.id}")
        HandlerManager.trigger("discord_ready")

    async def on_message(self, message):
        member = self.bot.guild.get_member(message.author.id)
        if isinstance(message.author, discord.Member) and (
            message.guild != self.bot.guild
        ):
            return
        with DBManager.create_session_scope() as db_session:
            user = User._create_or_get_by_discord_id(
                db_session,
                message.author.id,
                user_name=str(member) if member else str(message.author),
            )
            Message._create(
                db_session,
                message.id,
                message.author.id,
                message.channel.id
                if isinstance(message.author, discord.Member)
                else None,
                message.content,
            )
            db_session.commit()
            await HandlerManager.trigger(
                "discord_message",
                message_raw=message,
                message=message.content,
                author=message.author,
                user_level=user.level if user else 50,
                channel=message.channel
                if isinstance(message.author, discord.Member)
                else None,
                whisper=not isinstance(message.author, discord.Member),
            )

    async def on_error(self, event, *args, **kwargs):
        log.error(traceback.format_exc())


class DiscordBotManager:
    def __init__(self, bot, settings, redis, private_loop):
        self.bot = bot
        self.settings = settings
        self.client = CustomClient(self)

        self.private_loop = private_loop
        self.redis = redis

        self.guild = None
        if not self.redis.get("timeouts-discord") or not json.loads(self.redis.get("timeouts-discord")):
            self.redis.set("timeouts-discord", json.dumps({}))
        
        HandlerManager.add_handler("discord_ready", self.initial_unbans)

    def initial_unbans(self):
        try:
            data = json.loads(self.redis.get("timeouts-discord"))
            for user in data:
                unban_date = data[user]["unban_date"]
                if ":" in unban_date[-5:]:
                    unban_date = f"{unban_date[:-5]}{unban_date[-5:-3]}{unban_date[-2:]}"
                unban_date = datetime.strptime(unban_date, "%Y-%m-%d %H:%M:%S.%f%z")
                time_now = utils.now()
                if unban_date < time_now:
                    ScheduleManager.execute_now(method=self.unban, args=[data[user]["discord_id"], "Unbanned by timer"])
                    continue
                ScheduleManager.execute_delayed(delay=(unban_date - time_now).seconds, method=self.unban, args=[data[user]["discord_id"], "Unbanned by timer"])
        except Exception as e:
            log.exception(e)
            self.redis.set("timeouts-discord", json.dumps({}))

    def get_role_id(self, role_name):
        for role in self.guild.roles:
            if role.name == role_name:
                return str(role.id)
        return None

    def get_role(self, role_id):
        try:
            return self.guild.get_role(int(role_id))
        except:
            return None

    def get_member(self, member_id):
        try:
            return self.guild.get_member(int(member_id))
        except:
            return None

    async def say(self, channel, message, embed=None):
        message = discord.utils.escape_markdown(message)
        if channel and (message or embed):
            return await channel.send(content=message, embed=embed)

    async def ban(
        self, user, timeout_in_seconds=0, reason=None, delete_message_days=0
    ):
        delete_message_days = (
            7
            if delete_message_days > 7
            else (0 if delete_message_days < 0 else delete_message_days)
        )

        if not self.guild:
            return False
        if not user:
            return False
        try:
            ban = await self.guild.fetch_ban(user)
            if ban:
                return False
        except:
            return False
        try:
            await self.guild.ban(
                user=user, reason=reason, delete_message_days=delete_message_days
            )
            if timeout_in_seconds > 0:
                reason = f"{reason} for {timeout_in_seconds} seconds"
                timeouts = json.loads(self.redis.get("timeouts-discord"))
                timeouts[str(user.id)] = {
                    "discord_id": str(user.id),
                    "unban_date": str(utils.now() + timedelta(seconds=timeout_in_seconds)),
                    "reason": str(reason)
                }
                self.redis.set("timeouts-discord", json.dumps(timeouts))
                ScheduleManager.execute_delayed(delay=timeout_in_seconds, method=self.unban, args=[user.id, "Unbanned by timer"])
        except:
            return False
        return True

    async def unban(self, user_id, reason=None):
        if not self.guild:
            return False
        try:
            user = await self.client.fetch_user(int(user_id))
        except:
            return False
        timeouts = json.loads(self.redis.get("timeouts-discord"))
        if str(user_id) in timeouts:
            del timeouts[str(user_id)]
            self.redis.set("timeouts-discord", json.dumps(timeouts))
        try:
            ban = await self.guild.fetch_ban(user)
            if ban:
                await self.guild.unban(user=user, reason=reason)
        except:
            return False
        return True

    async def get_user(self, user_id):
        try:
            return await self.client.fetch_user(int(user_id))
        except:
            return None

    async def kick(self, user, reason=None):
        try:
            if not self.guild:
                return
            await self.guild.kick(user=user, reason=reason)
        except:
            return False
        return True

    async def private_message(self, user, message, embed=None):
        try:
            message = discord.utils.escape_markdown(message)
            await user.create_dm()
            if embed:
                message = None
            if not message and not embed:
                return None
            return await user.dm_channel.send(content=message, embed=embed)
        except:
            return None

    async def remove_role(self, user, role, reason=None):
        if not self.guild:
            return False
        try:
            await user.remove_roles(role, reason=reason)
        except:
            return False
        return True

    async def add_role(self, user, role, reason=None):
        if not self.guild:
            return
        try:
            await user.add_roles(role, reason=reason)
        except:
            return False
        return True

    async def run_periodically(self, wait_time, func, *args):
        while True:
            await asyncio.sleep(wait_time)
            if not self.client.is_closed():
                try:
                    await func(*args)
                except Exception as e:
                    log.error(e)

    def schedule_task_periodically(self, wait_time, func, *args):
        return self.private_loop.create_task(
            self.run_periodically(wait_time, func, *args)
        )

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
