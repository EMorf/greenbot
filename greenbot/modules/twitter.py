import logging

import json
import tweepy
import sys
import threading
from datetime import datetime

from greenbot import utils
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
        self.process = None
        if not self.bot:
            return

    async def on_status(self, tweet):
        if tweet.in_reply_to_status_id is not None:
            if not self.settings["send_replies"]:
                return
        username = tweet.author.screen_name
        if username not in self.settings["users"].split(" "):
            return
        tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"
        out_channel, _ = await self.bot.functions.func_get_channel(
            args=[int(self.settings["output_channel"])]
        )
        message = self.settings["output_format"].format(
            username=username, tweet_url=tweet_url
        )
        await self.bot.say(channel=out_channel, message=message, ignore_escape=True)

    def load_commands(self, **options):
        if not self.bot:
            return
        if self.process:
            self.process.kill()
            self.process.join()
            self.process = None
        self.stream = tweepy.Stream(
            self.bot.twitter_manager.api.auth, self.bot.twitter_manager.tweets_listener
        )
        self.process = Process(target=self.start_thread)
        self.process.start()

    def start_thread(self):
        self.stream.filter(
            follow=self.get_users_to_follow(self.settings["users"].split(" ")),
            languages=["en"],
        )

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
        if self.stream:
            self.stream.disconnect()
        HandlerManager.remove_handler("twitter_on_status", self.on_status)
        self.process.kill()
        self.process.join()


class Process(threading.Thread):

    # Thread class with a _stop() method.
    # The thread itself has to check
    # regularly for the stopped() condition.

    def __init__(self, *args, **kwargs):
        threading.Thread.__init__(self, *args, **kwargs)
        self.killed = False

    # function using _stop function
    def start(self):
        self.__run_backup = self.run
        self.run = self.__run
        threading.Thread.start(self)

    def __run(self):
        sys.settrace(self.globaltrace)
        self.__run_backup()
        self.run = self.__run_backup

    def globaltrace(self, frame, event, arg):
        if event == "call":
            return self.localtrace
        else:
            return None

    def localtrace(self, frame, event, arg):
        if self.killed:
            if event == "line":
                raise SystemExit()
        return self.localtrace

    def kill(self):
        self.killed = True
