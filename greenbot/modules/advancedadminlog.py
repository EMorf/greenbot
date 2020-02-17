import logging
import json

from greenbot.managers.db import DBManager
from greenbot.managers.handler import HandlerManager
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting
from greenbot.models.message import Message


log = logging.getLogger(__name__)


class AdvancedAdminLog(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "AdvancedAdminLog"
    DESCRIPTION = "Logs Everything"
    CATEGORY = "Feature"

    SETTINGS = [
        ModuleSetting(
            key="ingore_channels",
            label="Channels to ignore seperated by a space",
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
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    async def message_edit(self, payload):
        channel, _  = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        sent_in_channel = await self.bot.functions.func_get_channel(args=[int(payload.data["channel_id"])])
        if not channel:
            log.error("Channel not found")
            return
        channels = self.settings["ingore_channels"].split(" ") if self.settings["ingore_channels"] != "" else []
        if len(channels) > 0 and sent_in_channel not in channels:
            return
        message_id = payload.message_id
        with DBManager.create_session_scope() as db_session:
            message = Message._get(db_session, message_id)
            if not message:
                return
            content = json.loads(message.content)
            await self.bot.say(channel, f"MessageID: {message_id}\n from: {content[-2]}\nto: {content[-1]}")

    def enable(self, bot):
        if not bot:
            return

        HandlerManager.add_handler("discord_raw_message_edit", self.message_edit)

    def disable(self, bot):
        if not bot:
            return

        HandlerManager.remove_handler("discord_raw_message_edit", self.message_edit)
