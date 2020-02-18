import logging
import json
import discord

from greenbot.managers.db import DBManager
from greenbot.managers.handler import HandlerManager
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting
from greenbot.models.message import Message

import greenbot.utils as utils 

log = logging.getLogger(__name__)


class AdvancedAdminLog(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "AdvancedAdminLog"
    DESCRIPTION = "Logs Everything"
    CATEGORY = "Feature"

    SETTINGS = [
        ModuleSetting(
            key="ingore_channels",
            label="Channels to ignore for message edit/delete seperated by a space",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="output_channel",
            label="Channels to send logs to",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(key="log_edit_message", label="Log Edit Message Event", type="boolean", placeholder="", default=True),
        ModuleSetting(key="log_delete_message", label="Log Delete Message Event", type="boolean", placeholder="", default=True),
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    async def message_delete(self, payload):
        if not self.settings["log_delete_message"]:
            return
        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        message_id = payload.message_id
        with DBManager.create_session_scope() as db_session:
            db_message = Message._get(db_session, message_id)
            if not db_message:
                return
            content = json.loads(db_message.content)
            author_id = db_message.user_id
        sent_in_channel, _ = await self.bot.functions.func_get_channel(args=[int(payload.channel_id)])
        author = self.bot.discord_bot.get_member(int(author_id))
        embed = discord.Embed(
            description=content[-1],
            colour=discord.Colour.red(),
        )

        embed.add_field(name="Channel", value=sent_in_channel)
        action = discord.AuditLogAction.message_delete
        perp = None
        async for _log in self.bot.discord_bot.guild.audit_logs(limit=2, action=action):
            log.info(_log)
            same_chan = _log.extra.channel.id == sent_in_channel.id
            if _log.target.id == author_id and same_chan:
                perp = f"{_log.user}({_log.user.id})"
                break
        if perp:
            embed.add_field(name="Deleted by", value=perp)
        embed.set_footer(text="User ID: " + str(author_id))
        embed.set_author(
            name="{member} ({m_id})- Deleted Message".format(member=author, m_id=author.id),
            icon_url=str(author.avatar_url),
        )
        await self.bot.say(channel, message="Testing", embed=embed)

    async def message_edit(self, payload):
        if not self.settings["log_edit_message"]:
            return
        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        sent_in_channel, _ = await self.bot.functions.func_get_channel(args=[int(payload.data["channel_id"])])
        if not channel:
            log.error("Channel not found")
            return
        channels = self.settings["ingore_channels"].split(" ") if self.settings["ingore_channels"] != "" else []
        if len(channels) > 0 and sent_in_channel not in channels:
            return
        message_id = payload.message_id
        guild_id = payload.data.get("guild_id", None)
        
        message = await sent_in_channel.fetch_message(int(message_id))
        if not guild_id or self.bot.discord_bot.guild.id != int(guild_id):
            return

        with DBManager.create_session_scope() as db_session:
            db_message = Message._get(db_session, str(message_id))
            if not db_message:
                return
            content = json.loads(db_message.content)
            author_id = db_message.user_id
        author = self.bot.discord_bot.get_member(int(author_id))
        embed = discord.Embed(
            description=content[-2],
            colour=discord.Colour.red(),
        )
        jump_url = f"[Click to see new message]({message.jump_url})"
        embed.add_field(name="After Message:", value=jump_url)
        embed.add_field(name="Channel:", value=sent_in_channel.mention)
        embed.set_footer(text="User ID: " + str(author.id))
        embed.set_author(
            name="{member} ({m_id}) - Edited Message".format(
                member=author, m_id=author.id
            ),
            icon_url=str(author.avatar_url),
        )
        await self.bot.say(channel, message="Testing", embed=embed)

    def enable(self, bot):
        if not bot:
            return

        HandlerManager.add_handler("discord_raw_message_edit", self.message_edit)
        HandlerManager.add_handler("discord_raw_message_delete", self.message_delete)

    def disable(self, bot):
        if not bot:
            return

        HandlerManager.remove_handler("discord_raw_message_edit", self.message_edit)
        HandlerManager.remove_handler("discord_raw_message_delete", self.message_delete)
