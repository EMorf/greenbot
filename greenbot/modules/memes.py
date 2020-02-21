import logging

import random
import discord
import asyncio
from datetime import datetime

from greenbot import utils
from greenbot.models.command import Command
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting

log = logging.getLogger(__name__)


rainbowcolors = [
    0xFF0000,
    0xFF0F00,
    0xFF1F00,
    0xFF2E00,
    0xFF3D00,
    0xFF4D00,
    0xFF5C00,
    0xFF6B00,
    0xFF7A00,
    0xFF8A00,
    0xFF9900,
    0xFFA800,
    0xFFB800,
    0xFFC700,
    0xFFD600,
    0xFFE500,
    0xFFF500,
    0xFAFF00,
    0xEBFF00,
    0xDBFF00,
    0xCCFF00,
    0xBDFF00,
    0xADFF00,
    0x9EFF00,
    0x8FFF00,
    0x80FF00,
    0x70FF00,
    0x61FF00,
    0x52FF00,
    0x42FF00,
    0x33FF00,
    0x24FF00,
    0x14FF00,
    0x05FF00,
    0x00FF0A,
    0x00FF19,
    0x00FF29,
    0x00FF38,
    0x00FF47,
    0x00FF57,
    0x00FF66,
    0x00FF75,
    0x00FF85,
    0x00FF94,
    0x00FFA3,
    0x00FFB3,
    0x00FFC2,
    0x00FFD1,
    0x00FFE0,
    0x00FFF0,
    0x00FFFF,
    0x00F0FF,
    0x00E0FF,
    0x00D1FF,
    0x00C2FF,
    0x00B2FF,
    0x00A3FF,
    0x0094FF,
    0x0085FF,
    0x0075FF,
    0x0066FF,
    0x0057FF,
    0x0047FF,
    0x0038FF,
    0x0029FF,
    0x0019FF,
    0x000AFF,
    0x0500FF,
    0x1400FF,
    0x2400FF,
    0x3300FF,
    0x4200FF,
    0x5200FF,
    0x6100FF,
    0x7000FF,
    0x8000FF,
    0x8F00FF,
    0x9E00FF,
    0xAD00FF,
    0xBD00FF,
    0xCC00FF,
    0xDB00FF,
    0xEB00FF,
    0xFA00FF,
    0xFF00F5,
    0xFF00E6,
    0xFF00D6,
    0xFF00C7,
    0xFF00B8,
    0xFF00A8,
    0xFF0099,
    0xFF008A,
    0xFF007A,
    0xFF006B,
    0xFF005C,
    0xFF004D,
    0xFF003D,
    0xFF002E,
    0xFF001F,
    0xFF000F,
]

class Memes(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "Memes"
    DESCRIPTION = "Fun Module"
    CATEGORY = "Feature"

    SETTINGS = [
        ModuleSetting(
            key="mod_role_id",
            label="Mod Role ID",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="cost_mod_pride",
            label="Points required to execute the modpride command",
            type="number",
            placeholder="",
            default=0,
        ),
        ModuleSetting(
            key="dank_role_id",
            label="Dank Role ID",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="cost_dank",
            label="Points required to execute the dank command",
            type="number",
            placeholder="",
            default=0,
        ),
        ModuleSetting(
            key="dank_cooldown",
            label="Cooldown for the dank command",
            type="number",
            placeholder="",
            default=0,
        ),
        ModuleSetting(
            key="max_vroom_races",
            label="Max vroom races",
            type="number",
            placeholder="",
            default=3
        ),
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.mod_pride_running = False
        self.vroom_races = []

    async def modpride(self, bot, author, channel, message, args):
        if self.mod_pride_running:
            return False
        self.mod_pride_running = True
        role = self.bot.discord_bot.guild.get_role(int(self.settings["mod_role_id"]))
        r, g, b = role.color.to_rgb()
        for c in rainbowcolors:
            dcol = discord.Colour(c)
            await asyncio.sleep(0.2)
            await role.edit(colour=dcol)
        await role.edit(colour=discord.Colour.from_rgb(r, g, b))
        self.mod_pride_running = False

    async def vroom(self, bot, author, channel, message, args):
        if len(self.vroom_races) < self.settings["max_vroom_races"]:
            start_time = utils.now()
            m = await self.bot.say(channel=channel, message="﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏")
            self.vroom_races.append(m)
            await asyncio.sleep(0.5)
            await m.edit(content=":wheelchair:﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏﹏")
            for _ in range(19):
                newtick = m.content[:-1]
                newtick = "﹏" + newtick
                await asyncio.sleep((random.randint(5, 30) / 10))
                await m.edit(content=newtick)
            elapsed_time = utils.now() - start_time
            await m.edit(content=f"{author.mention} finished in {round(elapsed_time.total_seconds(), 2)}s")
            self.vroom_races.remove(m)
        else:
            await self.bot.say(channel=channel, message=f"{author.mention} there can only be up to {self.settings['max_vroom_races']} races at the same time. Try later...", ignore_escape=True)

    async def dank(self, bot, author, channel, message, args):
        role = self.bot.discord_bot.guild.get_role(int(self.settings["dank_role_id"]))
        dcol = discord.Colour.from_rgb(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        await role.edit(colour=dcol)

    def load_commands(self, **options):
        if self.settings["mod_role_id"]:
            self.commands["modpride"] = Command.raw_command(
                self.modpride,
                delay_all=0,
                delay_user=0,
                cost=self.settings["cost_mod_pride"],
                can_execute_with_whisper=False,
                description="KappaPride Mods",
            )
        if self.settings["dank_role_id"]:
            self.commands["dank"] = Command.raw_command(
                self.modpride,
                delay_all=self.settings["dank_cooldown"],
                delay_user=self.settings["dank_cooldown"],
                cost=self.settings["cost_dank"],
                can_execute_with_whisper=False,
                description="Messes with the dank roles color",
            )
        self.commands["vroom"] = Command.raw_command(
            self.vroom,
            delay_all=0,
            delay_user=0,
            can_execute_with_whisper=False,
            description="VROOOOOOOOOOM",
        )
        

    def enable(self, bot):
        if not bot:
            return

    def disable(self, bot):
        if not bot:
            return
