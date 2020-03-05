import logging

import random
import discord
import json
import asyncio
import time
from datetime import datetime

from greenbot import utils
from greenbot.models.command import Command
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting
from greenbot.managers.handler import HandlerManager

log = logging.getLogger(__name__)


class MovieNight(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "MovieNight"
    DESCRIPTION = "Fun Module"
    CATEGORY = "Feature"

    SETTINGS = [
        ModuleSetting(
            key="cdn_stream_key",
            label="Stream key for cdn",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="cdn_username",
            label="Username for cdn",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="cdn_password",
            label="Password for cdn",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="valid_channels",
            label="Channel IDs commands can be executed in",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="valid_channels",
            label="Channel IDs commands can be executed in",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="player_domain",
            label="Playser Hosting Domain",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="logo_url",
            label="Discord Bot Logo URL",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="alert_channel_id",
            label="Alert Channel ID",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="level",
            label="Level required to execute mod commands",
            type="number",
            placeholder="500",
            default=500,
        ),
        ModuleSetting(
            key="valid_channels",
            label="Channel IDs commands can be executed in",
            type="text",
            placeholder="",
            default="",
        ),
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    async def movienight(self, bot, author, channel, message, args):
        # query api, returns is_online, is_ull, key 
        is_online, is_ull, key = self.bot.movienight_api.is_online()
        if not is_online:
            await self.bot.say.send(channel=channel, message="Movienight is offline right now :(")
            return False

        if is_ull:
            embed = discord.Embed(
                title="Movienight is online!",
                color=0x0600FF,
                description="Try the normal player if you are having problems with the low latency one.",
            )
            if self.settings["logo_url"]:
                embed.set_thumbnail(url=self.settings["logo_url"])
            embed.add_field(
                name="Web (low latency):",
                value=f"https://{self.settings['player_domain']}/ull_player.html?key={key}",
                inline=False,
            )
            embed.add_field(
                name="Web:",
                value=f"https://{self.settings['player_domain']}/ull_player-hls-forced.html?key={key}",
                inline=True,
            )
        else:
            embed = discord.Embed(
                title="Movienight is online!",
                color=0x0600FF,
                description="Use the following link to watch: ",
            )
            if self.settings["logo_url"]:
                embed.set_thumbnail(url=self.settings["logo_url"])
            embed.add_field(
                name="Web:",
                value=f"https://{self.settings['player_domain']}/cdn_player.html?key={key}",
                inline=True,
            )
        await self.bot.say.send(channel=channel, embed=embed)
        return True

    async def moviestart_ull(self, bot, author, channel, message, args):
        server, stream_key = self.bot.movienight_api.create_ull_target()

        embed = discord.Embed(
            title="A new Wowza ULL target has been created! Use the following OBS settings:",
            color=0x008000,
        )
        embed.set_author(name="Movienight (ULL)")
        embed.add_field(name="Server:", value=server, inline=False)
        embed.add_field(name="Stream Key:", value=stream_key, inline=False)
        embed.add_field(name="Authentication:", value="Disabled", inline=False)

        await self.bot.private_message(user=author, embed=embed)
        return True

    async def moviestart_cdn(self, bot, author, channel, message, args):
        await self.bot.private_message(user=author, message="Starting transcoder, this usually takes less than a minute...")

        start_transcoder = await self.bot.movienight_api.start_cdn_target()
        if start_transcoder:
            embed = discord.Embed(
                title="Wowza CDN target ready. Here are the OBS settings:",
                color=0x008000,
            )
            embed.set_author(name="Movienight (CDN)")
            embed.add_field(
                name="Server:", value="rtmp://entrypoint...", inline=False #TODO
            )
            embed.add_field(name="Stream Key:", value=self.settings["cdn_stream_key"] if self.settings["cdn_stream_key"] else "Not Specified", inline=False)
            embed.add_field(name="Authentication:", value="Enabled", inline=False)
            embed.add_field(name="Username:", value=self.settings["cdn_username"] if self.settings["cdn_username"] else "Not Specified", inline=False)
            embed.add_field(name="Password:", value=self.settings["cdn_password"] if self.settings["cdn_password"] else "Not Specified", inline=False)

            await self.bot.private_message(user=author, message="Target Ready!", embed=embed)
            return True

        await self.bot.private_message(user=author, message="Was unable to start the transcoder, please check logs")
        return False

    async def movie_night_started_event(self):
        if not self.bot.movienight_api.active:
            log.error("API is not running!")
            return

        is_online, is_ull, key = self.bot.movienight_api.is_online()
        if not is_online:
            return

        out_chnanel = list(self.bot.filters.get_channel([self.settings["alert_channel_id"]], None, {}))[0]
        if is_ull:
            embed = discord.Embed(
                title="Movienight is online!",
                color=0x0600FF,
                description="Use the normal player if you are having problems with the low latency one.",
            )
            embed.add_field(
                name="Web (low latency):",
                value=f"https://movie.admiralbulldog.live/ull_player.html?key={key}",
                inline=False,
            )
            embed.add_field(
                name="Web:",
                value=f"https://movie.admiralbulldog.live/ull_player-hls-forced.html?key={key}",
                inline=True,
            )
        else:
            embed = discord.Embed(
                title="Movienight is about to start!",
                color=0x0600FF,
                description="Use the following link to watch: ",
            )
            embed.add_field(
                name="Web:",
                value=f"https://movie.admiralbulldog.live/cdn_player.html?key={key}",
                inline=True,
            )
        if self.settings["logo_url"]:
            embed.set_thumbnail(url=self.settings["logo_url"])
        await self.bot.say(channel=out_chnanel, embed=embed)

    def load_commands(self, **options):
        if not self.bot.movienight_api.active:
            log.error("API is not running!")
            return

        self.commands["movienight"] = Command.raw_command(
            self.movienight,
            delay_all=0,
            delay_user=0,
            can_execute_with_whisper=False,
            channels=json.dumps(self.settings["valid_channels"].split(" ")),
            description="Shows thge movienight links",
        )
        self.commands["moviestart"] = Command.multiaction_command(
            delay_all=0,
            delay_user=0,
            default=None,
            can_execute_with_whisper=False,
            level=self.settings["level"],
            command="moviestart",
            commands={
                "ull": Command.raw_command(
                    self.moviestart_ull,
                    delay_all=0,
                    delay_user=0,
                    level=self.settings["level"],
                    can_execute_with_whisper=False,
                    channels=json.dumps(self.settings["valid_channels"].split(" ")),
                    description="Creates an ultra-low-latency target (lowest latency, source quality only)",
                ),
                "cdn": Command.raw_command(
                    self.moviestart_cdn,
                    delay_all=0,
                    delay_user=0,
                    level=self.settings["level"],
                    can_execute_with_whisper=False,
                    channels=json.dumps(self.settings["valid_channels"].split(" ")),
                    description="Starts a normal cdn target with transcoder (higher latency, adaptive bitrate)",
                ),
            },
        )

    def enable(self, bot):
        if not bot:
            return
        if not self.bot.movienight_api.active:
            log.error("API is not running!")
            return
        
        HandlerManager.add_handler("movie_night_started", self.movie_night_started_event)

    def disable(self, bot):
        if not bot:
            return

        HandlerManager.remove_handler("movie_night_started", self.movie_night_started_event)
