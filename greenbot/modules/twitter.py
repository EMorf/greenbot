import logging

import json
import tweepy
import sys
import threading
from datetime import datetime

from greenbot import utils
from greenbot.managers.redis import RedisManager
from greenbot.managers.handler import HandlerManager
from greenbot.managers.schedule import ScheduleManager
from greenbot.models.command import Command
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting

log = logging.getLogger(__name__)


class Twitter(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "Twitter"
    DESCRIPTION = "Fetches Tweets from users and displays them"
    CATEGORY = "Feature"

    SETTINGS = [
        ModuleSetting(
            key="users",
            label="Users to follow",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="output_format",
            label="Format for output, where {username} is the username and {tweet_url} is the url of the tweet",
            type="text",
            placeholder="@here {username} just tweeted {tweet_url}",
            default="@here {username} just tweeted {tweet_url}",
        ),
        ModuleSetting(
            key="output_channel",
            label="Channel ID to output to",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="send_replies",
            label="Log Replies to Tweets",
            type="boolean",
            placeholder="",
            default=True,
        ),
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.redis = RedisManager.get()
        self.stream = None
        self.process = None
        if not self.bot:
            return

    async def on_status(self, tweet):
        try:
            if tweet.in_reply_to_status_id is not None:
                if not self.settings["send_replies"]:
                    return
            username = tweet.author.screen_name
            tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"
            out_channel, _ = list(self.bot.filters.get_channel([int(self.settings["output_channel"])], None, {}))[0]
            )
            message = self.settings["output_format"].format(
                username=username, tweet_url=tweet_url
            )
            await self.bot.say(channel=out_channel, message=message, ignore_escape=True)
        except Exception as e:
            log.error(e)


    def load_commands(self, **options):
        if not self.bot:
            return

        ScheduleManager.execute_now(self.update_manager)

    async def update_manager(self):
        await HandlerManager.trigger("twitter_follows", usernames=self.settings["users"].split(" ") if self.settings["users"] else [])

    def get_users_to_follow(self, usernames):
        return [
            str(self.bot.twitter_manager.api.get_user(username).id)
            for username in usernames
        ]

    def enable(self, bot):
        if not bot:
            return
        HandlerManager.add_handler("twitter_on_status", self.on_status)

    def disable(self, bot):
        if not bot:
            return
        HandlerManager.remove_handler("twitter_on_status", self.on_status)

