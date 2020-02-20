import logging
import requests
import json
import discord

from greenbot import utils
from greenbot.managers.schedule import ScheduleManager
from greenbot.managers.redis import RedisManager
from greenbot.models.command import Command
from greenbot.modules import BaseModule

from greenbot.modules import ModuleSetting

log = logging.getLogger(__name__)


class TwitchTracker(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "TwitchTracker"
    DESCRIPTION = "Tracks when twitch channels go live"
    CATEGORY = "Feature"

    SETTINGS = [
        ModuleSetting(
            key="client_id",
            label="Client-ID From Twitch",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="output_channel",
            label="Channel id to broadcast live notifications",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="channels",
            label="Twitch Channel Logins to track seperated by a space",
            type="text",
            placeholder="",
            default="",
        ),
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.process_checker_job = None
        self.redis = RedisManager.get()
        self.twitch_streamers_tracked = self.redis.get("twitch-streams-tracked")
        if not self.twitch_streamers_tracked:
            self.redis.set("twitch-streams-tracked", json.dumps({}))
            self.twitch_streamers_tracked = json.dumps({})
        self.twitch_streamers_tracked = json.loads(self.twitch_streamers_tracked)
        

    def load_commands(self, **options):
        if self.bot:
            settings_streamers = self.settings["channels"].split(" ")
            return_twitch_streamers_tracked = {}
            for streamer in settings_streamers:
                return_twitch_streamers_tracked[streamer.lower()] = self.twitch_streamers_tracked.get(streamer.lower(), False)
            self.redis.set("twitch-streams-tracked", json.dumps(return_twitch_streamers_tracked))
            self.twitch_streamers_tracked = return_twitch_streamers_tracked

    @property
    def headers(self):
        return {"Client-ID": self.settings["client_id"]}

    async def process_checker(self):
        response = self.get_response_from_twitch(self.settings["channels"].split(" "))
        channels_updated = []
        for channel in response:
            if channel["type"] != "live" or self.twitch_streamers_tracked[channel["user_name"].lower()]:
                continue
            self.twitch_streamers_tracked[channel["user_name"].lower()] = True
            await self.broadcast_live(channel["user_name"], channel["title"])
            channels_updated.append(channel["user_name"].lower())
        for streamer in self.twitch_streamers_tracked:
            if streamer not in channels_updated:
                self.twitch_streamers_tracked[streamer] = False
        self.redis.set("twitch-streams-tracked", json.dumps(self.twitch_streamers_tracked))

    async def broadcast_live(self, streamer_name, stream_title):
        data = discord.Embed(description=f"Streamer {streamer_name} went live!", colour=discord.Colour.from_rgb(128, 0, 128), url=f"https://twitch.tv/{streamer_name.lower()}")
        data.add_field(name=("Title"), value=stream_title)
        channel, _  = self.bot.functions.func_get_channel(int(self.settings["output_channel"]))
        await self.bot.say(channel, embed=data)

    def get_response_from_twitch(self, streamers):
        final_response = []
        if not streamers:
            return []
        if len(streamers) > 100:
            final_response = final_response + self.get_response_from_twitch(streamers[100:])
        final_response += requests.get(f'https://api.twitch.tv/helix/streams?user_login={streamers[0]}' + '&user_login='.join(streamers[1:]), headers=self.headers).json()["data"]
        return final_response

    def enable(self, bot):
        if not bot:
            return
        ScheduleManager.execute_now(self.process_checker)
        self.process_messages_job = ScheduleManager.execute_every(
            300, self.process_checker
        )  # Checks every hour

    def disable(self, bot):
        if not bot:
            return
        self.process_messages_job.remove()
        self.process_messages_job = None
