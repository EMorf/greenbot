import logging
import discord

from greenbot.managers.handler import HandlerManager
from greenbot.managers.db import DBManager
from greenbot.managers.timeout import TimeoutManager
from greenbot.models.message import Message
from greenbot.models.user import User
from greenbot.models.timeout import Timeout
from greenbot.models.banphrase import BanphraseManager

log = logging.getLogger(__name__)


class MessageManager:
    def __init__(self, bot):
        self.bot = bot
        HandlerManager.add_handler("discord_message", self.on_message)
        HandlerManager.add_handler(
            "discord_raw_message_edit", self.edit_message, priority=1000
        )

    async def on_message(self, message):
        member = self.bot.discord_bot.get_member(message.author.id)
        not_whisper = isinstance(message.author, discord.Member)
        if not_whisper and (message.guild != self.bot.discord_bot.guild):
            return

        if not member:
            return

        with DBManager.create_session_scope() as db_session:
            User._create_or_get_by_discord_id(db_session, str(member.id), str(member))
            db_session.commit()
            if self.new_message(db_session, message) is None:
                log.error("Discord api running slow?")
                return

            db_session.commit()
            current_timeout = Timeout._is_timedout(db_session, str(member.id))
            if current_timeout and not_whisper:
                await message.delete()
                await self.bot.timeout_manager.apply_timeout(member, current_timeout)
                return

            user_level = self.bot.psudo_level_member(db_session, member)
        if message.author.id == self.bot.discord_bot.client.user.id:
            return

        if user_level < 500:
            matched_phrase = self.bot.banphrase_manager.check_message(message.content)
            if matched_phrase:
                await self.bot.banphrase_manager.punish(member, matched_phrase)
                await message.delete()
                return

        await HandlerManager.trigger(
            "parse_command_from_message",
            message=message,
            content=message.content,
            user_level=user_level,
            author=message.author,
            not_whisper=not_whisper,
            channel=message.channel,
        )

    def new_message(self, db_session, message):
        return Message._create(
            db_session,
            message.id,
            message.author.id,
            message.channel.id if isinstance(message.author, discord.Member) else None,
            [message.content],
        )

    async def edit_message(self, payload):
        with DBManager.create_session_scope() as db_session:
            message = Message._get(db_session, payload.message_id)
            if not message:
                return

            new_content = payload.data.get("content", "")
            message.edit_message(db_session, new_content)
            member = self.bot.discord_bot.get_member(message.user_id)
            user_level = self.bot.psudo_level_member(db_session, member) if member else 0
            if user_level < 500:
                matched_phrase = self.bot.banphrase_manager.check_message(new_content)
                if matched_phrase:
                    await self.bot.banphrase_manager.punish(member, matched_phrase)
                    channel = await self.bot.discord_bot.get_channel(message.channel_id)
                    message = await channel.fetch_message(int(message.message_id))
                    await message.delete()
