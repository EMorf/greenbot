import logging

import discord
import traceback
import asyncio
import json
import time
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
        log.info(f"discord.py {discord.__version__}")
        log.info(f"Discord Bot has started with id {self.user.id}")
        while not ScheduleManager.ready:
            await asyncio.sleep(0.1)
        await HandlerManager.trigger("discord_ready")

    async def on_connect(self):
        await HandlerManager.trigger("discord_connect")

    async def on_disconnect(self):
        await HandlerManager.trigger("discord_disconnect")

    async def on_shard_ready(self, shard_id):
        await HandlerManager.trigger("discord_disconnect", shard_id=shard_id)

    async def on_resumed(self):
        await HandlerManager.trigger("discord_resumed")

    async def on_error(self, event, *args, **kwargs):
        log.error(traceback.format_exc())
        log.error(event)

    async def on_socket_raw_receive(self, payload):
        await HandlerManager.trigger("discord_error", payload=payload)

    async def on_socket_raw_send(self, payload):
        await HandlerManager.trigger("discord_socket_raw_send", payload=payload)

    async def on_typing(self, channel, user, when):
        await HandlerManager.trigger(
            "discord_socket_raw_send", channel=channel, user=user, when=when
        )

    async def on_message(self, message):
        await HandlerManager.trigger("discord_message", message=message)

    async def on_message_delete(self, message):
        await HandlerManager.trigger("discord_message_delete", message=message)

    async def on_bulk_message_delete(self, messages):
        await HandlerManager.trigger("discord_bulk_message_delete", messages=messages)

    async def on_raw_message_delete(self, payload):
        await HandlerManager.trigger("discord_raw_message_delete", payload=payload)

    async def on_raw_bulk_message_delete(self, payload):
        await HandlerManager.trigger("discord_raw_bulk_message_delete", payload=payload)

    async def on_message_edit(self, before, after):
        await HandlerManager.trigger("discord_message_edit", before=before, after=after)

    async def on_raw_message_edit(self, payload):
        await HandlerManager.trigger("discord_raw_message_edit", payload=payload)

    async def on_reaction_add(self, reaction, user):
        await HandlerManager.trigger(
            "discord_reaction_add", reaction=reaction, user=user
        )

    async def on_reaction_remove(self, reaction, user):
        await HandlerManager.trigger(
            "discord_reaction_remove", reaction=reaction, user=user
        )

    async def on_raw_reaction_remove(self, payload):
        await HandlerManager.trigger("discord_reaction_remove", payload=payload)

    async def on_reaction_clear(self, message, reactions):
        await HandlerManager.trigger(
            "discord_reaction_clear", message=message, reactions=reactions
        )

    async def on_raw_reaction_clear(self, payload):
        await HandlerManager.trigger("discord_raw_reaction_clear", payload=payload)

    async def on_reaction_clear_emoji(self, reaction):
        await HandlerManager.trigger("discord_reaction_clear_emoji", reaction=reaction)

    async def on_raw_reaction_clear_emoji(self, payload):
        await HandlerManager.trigger(
            "discord_raw_reaction_clear_emoji", payload=payload
        )

    async def on_private_channel_delete(self, channel):
        await HandlerManager.trigger("discord_private_channel_delete", channel=channel)

    async def on_private_channel_create(self, channel):
        await HandlerManager.trigger("discord_private_channel_create", channel=channel)

    async def on_private_channel_update(self, before, after):
        await HandlerManager.trigger(
            "discord_private_channel_update", before=before, after=after
        )

    async def on_private_channel_pins_update(self, channel, last_pin):
        await HandlerManager.trigger(
            "discord_private_channel_pins_update", channel=channel, last_pin=last_pin
        )

    async def on_guild_channel_delete(self, channel):
        await HandlerManager.trigger("discord_guild_channel_delete", channel=channel)

    async def on_guild_channel_create(self, channel):
        await HandlerManager.trigger("discord_guild_channel_create", channel=channel)

    async def on_guild_channel_update(self, before, after):
        await HandlerManager.trigger(
            "discord_guild_channel_update", before=before, after=after
        )

    async def on_guild_channel_pins_update(self, channel, last_pin):
        await HandlerManager.trigger(
            "discord_guild_channel_pins_update", channel=channel, last_pin=last_pin
        )

    async def on_guild_integrations_update(self, guild):
        await HandlerManager.trigger("discord_guild_integrations_update", guild=guild)

    async def on_webhooks_update(self, channel):
        await HandlerManager.trigger("discord_webhooks_update", channel=channel)

    async def on_member_join(self, member):
        await HandlerManager.trigger("discord_member_join", member=member)

    async def on_member_remove(self, member):
        await HandlerManager.trigger("discord_member_remove", member=member)

    async def on_member_update(self, before, after):
        await HandlerManager.trigger(
            "discord_member_update", before=before, after=after
        )

    async def on_user_update(self, before, after):
        await HandlerManager.trigger("discord_user_update", before=before, after=after)

    async def on_guild_join(self, guild):
        await HandlerManager.trigger("discord_guild_join", guild=guild)

    async def on_guild_remove(self, guild):
        await HandlerManager.trigger("discord_guild_remove", guild=guild)

    async def on_guild_update(self, before, after):
        await HandlerManager.trigger("discord_guild_update", before=before, after=after)

    async def on_guild_role_create(self, role):
        await HandlerManager.trigger("discord_guild_role_create", role=role)

    async def on_guild_role_delete(self, role):
        await HandlerManager.trigger("discord_guild_role_delete", role=role)

    async def on_guild_role_update(self, before, after):
        await HandlerManager.trigger(
            "discord_guild_role_update", before=before, after=after
        )

    async def on_guild_emojis_update(self, guild, before, after):
        await HandlerManager.trigger(
            "discord_guild_emojis_update", guild=guild, before=before, after=after
        )

    async def on_guild_available(self, guild):
        await HandlerManager.trigger("discord_guild_available", guild=guild)

    async def on_guild_unavailable(self, guild):
        await HandlerManager.trigger("discord_guild_unavailable", guild=guild)

    async def on_voice_state_update(self, member, before, after):
        await HandlerManager.trigger(
            "discord_voice_state_update", member=member, before=before, after=after
        )

    async def on_member_ban(self, guild, user):
        await HandlerManager.trigger("discord_member_ban", guild=guild, user=user)

    async def on_member_unban(self, guild, user):
        await HandlerManager.trigger("discord_member_unban", guild=guild, user=user)

    async def on_invite_create(self, invite):
        await HandlerManager.trigger("discord_invite_create", invite=invite)

    async def on_invite_delete(self, invite):
        await HandlerManager.trigger("discord_invite_delete", invite=invite)

    async def on_group_join(self, channel, user):
        await HandlerManager.trigger("discord_group_join", channel=channel, user=user)

    async def on_group_remove(self, channel, user):
        await HandlerManager.trigger("discord_group_remove", channel=channel, user=user)

    async def on_relationship_add(self, relationship):
        await HandlerManager.trigger(
            "discord_relationship_add", relationship=relationship
        )

    async def on_relationship_remove(self, relationship):
        await HandlerManager.trigger(
            "discord_relationship_remove", relationship=relationship
        )

    async def discord_relationship_update(self, before, after):
        await HandlerManager.trigger(
            "discord_relationship_remove", before=before, after=after
        )


class DiscordBotManager:
    def __init__(self, bot, settings, redis, private_loop):
        self.bot = bot
        self.settings = settings
        self.client = CustomClient(self)

        self.private_loop = private_loop
        self.redis = redis

        self.guild = None
        if not self.redis.get(
            f"{self.bot.bot_name}:timeouts-discord"
        ) or not json.loads(self.redis.get(f"{self.bot.bot_name}:timeouts-discord")):
            self.redis.set(f"{self.bot.bot_name}:timeouts-discord", json.dumps({}))
        HandlerManager.add_handler("discord_ready", self.initial_unbans)

    async def initial_unbans(self):
        try:
            data = json.loads(self.redis.get(f"{self.bot.bot_name}:timeouts-discord"))
            for user in data:
                unban_date = utils.parse_date(data[user]["unban_date"])
                time_now = utils.now()
                resp_timeout = data.get("resp_timeout", "")
                resp_timeout += " after " if resp_timeout else ""
                if unban_date < time_now:
                    ScheduleManager.execute_now(
                        method=self.unban,
                        args=[
                            data[user]["discord_id"],
                            f"Unbanned by timer{resp_timeout}",
                        ],
                    )
                    continue
                ScheduleManager.execute_delayed(
                    delay=(unban_date - time_now).seconds,
                    method=self.unban,
                    args=[data[user]["discord_id"], f"Unbanned by timer{resp_timeout}"],
                )
        except Exception as e:
            log.exception(e)
            self.redis.set(f"{self.bot.bot_name}:timeouts-discord", json.dumps({}))

        with DBManager.create_session_scope() as db_session:
            unnamed_users = db_session.query(User).filter_by(user_name="").all()
            for user in unnamed_users:
                member = self.get_member(int(user.discord_id))
                if not member:
                    db_session.delete(user)
                    continue

                user.user_name = str(member)

    async def get_channel(self, channel_id):
        return await self.guild.get_channel(int(channel_id))

    def get_role_by_name(self, role_name):
        for role in self.guild.roles:
            if role.name == role_name:
                return role
        return None

    def get_role(self, role_id):
        try:
            return self.guild.get_role(int(role_id))
        except:
            return None

    async def say(self, channel, message=None, embed=None, file=None, ignore_escape=False):
        if message and not ignore_escape:
            message = discord.utils.escape_markdown(message, as_needed=True)
        if not channel or (message is None and embed is None and file is None):
            return
        return await channel.send(content=message, embed=embed, file=file)

    async def ban(self, user, timeout_in_seconds=0, reason=None, delete_message_days=0):
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
            resp_timeout = utils.seconds_to_resp(timeout_in_seconds)
            reason += (
                f" for {resp_timeout}!" if timeout_in_seconds > 0 else " Permanently!"
            )
            await self.guild.ban(
                user=user, reason=reason, delete_message_days=delete_message_days
            )
            if timeout_in_seconds > 0:
                timeouts = json.loads(
                    self.redis.get(f"{self.bot.bot_name}:timeouts-discord")
                )
                timeouts[str(user.id)] = {
                    "discord_id": str(user.id),
                    "unban_date": str(
                        utils.now() + timedelta(seconds=timeout_in_seconds)
                    ),
                    "resp_timeout": resp_timeout,
                    "reason": str(reason),
                }
                self.redis.set(
                    f"{self.bot.bot_name}:timeouts-discord", json.dumps(timeouts)
                )
                ScheduleManager.execute_delayed(
                    delay=timeout_in_seconds,
                    method=self.unban,
                    args=[user.id, f"Unbanned by timer after {resp_timeout}"],
                )
        except:
            return False
        return True

    def get_member_by_name(self, member_name):
        for member in self.guild.members:
            if (str(member).lower() == member_name.lower() or str(member.display_name).lower() == member_name.lower()) or str(member.name).lower() == member_name.lower():
                return member
        return None

    def get_member(self, member_id):
        try:
            return self.guild.get_member(int(member_id))
        except:
            return None

    async def unban(self, user_id, reason=None):
        if not self.guild:
            return False
        try:
            user = await self.client.fetch_user(int(user_id))
        except:
            return False
        timeouts = json.loads(self.redis.get(f"{self.bot.bot_name}:timeouts-discord"))
        if str(user_id) in timeouts:
            del timeouts[str(user_id)]
            self.redis.set(
                f"{self.bot.bot_name}:timeouts-discord", json.dumps(timeouts)
            )
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

    async def private_message(
        self, user, message=None, embed=None, file=None, ignore_escape=False
    ):
        if (message is None and embed is None and file is None) or user is None:
            return None
        try:
            if message and not ignore_escape:
                message = discord.utils.escape_markdown(message, as_needed=True)
            await user.create_dm()
            return await user.dm_channel.send(content=message, embed=embed, file=file)
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

    def connect(self):
        self.private_loop.create_task(self._connect())

    async def _connect(self):
        try:
            await self.client.start(self.settings["discord_token"])
        except Exception as e:
            log.error(e)
