import logging
import discord

from greenbot.managers.handler import HandlerManager
from greenbot.managers.db import DBManager
from greenbot.models.message import Message
from greenbot.models.user import User

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
            self.new_message(db_session, message)
            user_level = self.bot.psudo_level_member(db_session, member)

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
        Message._create(
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
            message.edit_message(db_session, payload.data.get("content", ""))
