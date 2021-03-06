import logging
import requests
import json
import itertools
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
            key="broadcast_message",
            label="Message to send {streamer_name} is the streamers name",
            type="text",
            placeholder="@everyone {streamer_name} is now live on Twitch!",
            default="@everyone {streamer_name} is now live on Twitch!",
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
        self.redis = RedisManager.get()
        if self.bot:
            self.twitch_streamers_tracked = self.redis.get(
                f"{self.bot.bot_name}:twitch-streams-tracked"
            )
            if not self.twitch_streamers_tracked:
                self.redis.set(
                    f"{self.bot.bot_name}:twitch-streams-tracked", json.dumps({})
                )
                self.twitch_streamers_tracked = json.dumps({})
            self.twitch_streamers_tracked = json.loads(self.twitch_streamers_tracked)
            self.process_messages_job = ScheduleManager.execute_every(
                300, self.process_checker
            )
            self.process_messages_job.pause()

    def load_commands(self, **options):
        if self.bot:
            return_twitch_streamers_tracked = {}
            for streamer in self.settings["channels"].split(" "):
                return_twitch_streamers_tracked[
                    streamer.lower()
                ] = self.twitch_streamers_tracked.get(streamer.lower(), False)
            self.redis.set(
                f"{self.bot.bot_name}:twitch-streams-tracked",
                json.dumps(return_twitch_streamers_tracked),
            )
            self.twitch_streamers_tracked = return_twitch_streamers_tracked

    @property
    def headers(self):
        return {"Client-ID": self.settings["client_id"]}

    def get_games_playing(self, game_ids):
        final_response = {}
        if not game_ids:
            return {}
        if len(game_ids) > 100:
            final_response.update(self.get_games_playing(game_ids[100:]))
        final_response.update(
            {
                item["id"]: item
                for item in requests.get(
                    f"https://api.twitch.tv/helix/games?id=" + "&id=".join(game_ids),
                    headers=self.headers,
                ).json()["data"]
            }
        )
        return final_response

    async def process_checker(self):
        channels = self.get_response_from_twitch(self.settings["channels"].split(" "))
        game_ids = list(
            id
            for id, _ in itertools.groupby(channel["game_id"] for channel in channels)
        )
        games = self.get_games_playing(game_ids)
        users = self.get_users([channel["user_name"].lower() for channel in channels])
        channels_updated = []
        for channel in channels:
            if channel["type"] != "live":
                continue
            if self.twitch_streamers_tracked[channel["user_name"].lower()]:
                channels_updated.append(channel["user_name"].lower())
                continue
            self.twitch_streamers_tracked[channel["user_name"].lower()] = True
            await self.broadcast_live(
                streamer_name=channel["user_name"],
                stream_title=channel["title"],
                image_url=channel["thumbnail_url"],
                icon_url=users[channel["user_name"].lower()]["profile_image_url"],
                game=games[channel["game_id"]]["name"]
                if channel["game_id"]
                else "Just Chatting",
                viewers=channel["viewer_count"],
            )
            channels_updated.append(channel["user_name"].lower())
        for streamer in self.twitch_streamers_tracked:
            if streamer not in channels_updated:
                self.twitch_streamers_tracked[streamer] = False
        self.redis.set(
            f"{self.bot.bot_name}:twitch-streams-tracked",
            json.dumps(self.twitch_streamers_tracked),
        )

    async def broadcast_live(
        self, streamer_name, stream_title, image_url, icon_url, game, viewers
    ):
        data = discord.Embed(
            description=f"[**{stream_title}**](https://twitch.tv/{streamer_name.lower()})\n\nPlaying {game} for {viewers} viewers\n[Watch Stream](https://twitch.tv/{streamer_name.lower()})",
            colour=discord.Colour.from_rgb(128, 0, 128),
        )
        data.timestamp = utils.now()
        data.set_image(url=image_url.format(width=1920, height=1080))
        data.set_author(
            name=f"{streamer_name} is now live on twitch!",
            url=f"https://twitch.tv/{streamer_name.lower()}",
            icon_url=icon_url,
        )
        channel = self.bot.filters.get_channel(
                [int(self.settings["output_channel"])], None, {}
            )[0]
        await self.bot.say(
            channel,
            message=self.settings["broadcast_message"].format(
                streamer_name=streamer_name
            ),
            embed=data,
        )

    def get_response_from_twitch(self, streamers):
        final_response = []
        if not streamers:
            return []
        if len(streamers) > 100:
            final_response = final_response + self.get_response_from_twitch(
                streamers[100:]
            )
        final_response += requests.get(
            f"https://api.twitch.tv/helix/streams?user_login="
            + "&user_login=".join(streamers),
            headers=self.headers,
        ).json()["data"]
        return final_response

    def get_users(self, streamers):
        final_response = {}
        if not streamers:
            return {}
        if len(streamers) > 100:
            final_response.update(self.get_users(streamers[100:]))
        final_response.update(
            {
                item["login"]: item
                for item in requests.get(
                    f"https://api.twitch.tv/helix/users?login="
                    + "&login=".join(streamers),
                    headers=self.headers,
                ).json()["data"]
            }
        )
        return final_response

    def enable(self, bot):
        if not bot:
            return
        ScheduleManager.execute_now(self.process_checker)
        self.process_messages_job.resume()

    def disable(self, bot):
        if not bot:
            return
        self.process_messages_job.pause()
