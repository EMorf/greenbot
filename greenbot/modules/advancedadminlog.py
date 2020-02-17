import logging

from greenbot.managers.db import DBManager
from greenbot.managers.handler import HandlerManager
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting

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

    async def message_edit(self, before, after):
        channel, _  = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        if not channel:
            log.error("Channel not found")
            return
        await self.bot.say(channel, f"before: {before}\after:{after}")

    def enable(self, bot):
        if not bot:
            return

        HandlerManager.add_handler("discord_message_edit", self.message_edit)

    def disable(self, bot):
        if not bot:
            return

        HandlerManager.remove_handler("discord_message_edit", self.message_edit)
