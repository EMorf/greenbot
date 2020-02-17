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
        HandlerManager.add_handler("discord_raw_message_edit", self.edit_message, priority=1000)

    async def on_message(self, message):
        member = self.bot.discord_bot.get_member(message.author.id)
        if isinstance(message.author, discord.Member) and (message.guild != self.bot.discord_bot.guild):
            return
        with DBManager.create_session_scope() as db_session:
            user = User._create_or_get_by_discord_id(
                db_session,
                message.author.id,
                user_name=str(member) if member else str(message.author),
            )
            user_level = user.level
            self.new_message(db_session, message)
        await HandlerManager.trigger("parse_command_from_message", message=message, content=message.content, user_level=user_level, author=message.author, not_whisper=not_whisper, channel=message.channel)

    def new_message(self, db_session, message):
        Message._create(
            db_session,
            message.id,
            message.author.id,
            message.channel.id if isinstance(message.author, discord.Member) else None,
            [message.content],
        )

    def edit_message(self, payload):
        log.info(payload)
