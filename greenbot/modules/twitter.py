import logging

import json
import tweepy
from datetime import datetime

from greenbot import utils
from greenbot.managers.schedule import ScheduleManager
from greenbot.managers.redis import RedisManager
from greenbot.managers.handler import HandlerManager
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
        if not self.bot:
            return
        self.stream = tweepy.Stream(self.bot.twitter_manager.api.auth, self.bot.twitter_manager.tweets_listener)

    async def on_status(self, tweet):
        if tweet.in_reply_to_status_id is not None:
            if not self.settings["send_replies"]:
                return
        username = tweet.author.screen_name
        tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"
        out_channel, _ = await self.bot.functions.func_get_channel(
            args=[int(self.settings["output_channel"])]
        )
        await self.bot.say(channel=out_channel, message=self.settings["output_format"].format(username=username, tweet_url=tweet_url))

    def load_commands(self, **options):
        if not self.bot:
            return

    def get_users_to_follow(self, usernames):
        return [str(self.bot.twitter_manager.api.get_user(username).id) for username in usernames]

    def enable(self, bot):
        if not bot:
            return
        if self.settings["users"]:
            self.stream.filter(follow=self.get_users_to_follow(self.settings["users"].split(" ")), languages=["en"], is_async=True)
        HandlerManager.add_handler("twitter_on_status", self.on_status)


    def disable(self, bot):
        if not bot:
            return
        if self.stream:
            self.stream.disconnect()
        HandlerManager.remove_handler("twitter_on_status", self.on_status)
