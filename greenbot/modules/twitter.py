import logging

import json
import tweepy
import threading
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
        self.process = None
        if not self.bot:
            return

    async def on_status(self, tweet):
        if tweet.in_reply_to_status_id is not None:
            if not self.settings["send_replies"]:
                return
        username = tweet.author.screen_name
        tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"
        out_channel, _ = await self.bot.functions.func_get_channel(
            args=[int(self.settings["output_channel"])]
        )
        message = self.settings["output_format"].format(username=username, tweet_url=tweet_url)
        log.info(message)
        await self.bot.say(channel=out_channel, message=message)

    def load_commands(self, **options):
        if not self.bot:
            return
        if self.process:
            self.process.stop()
            self.process.join()
            self.process = None
        self.stream = tweepy.Stream(self.bot.twitter_manager.api.auth, self.bot.twitter_manager.tweets_listener)
        self.process = Process(self.stream, self.get_users_to_follow(self.settings["users"].split(" ")))
        self.process.start()

    def get_users_to_follow(self, usernames):
        return [str(self.bot.twitter_manager.api.get_user(username).id) for username in usernames]

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
        self.process.stop()
        self.process.join()


class Process(threading.Thread): 
  
    # Thread class with a _stop() method.  
    # The thread itself has to check 
    # regularly for the stopped() condition. 
  
    def __init__(self, stream, follow,*args, **kwargs): 
        super(Process, self).__init__(*args, **kwargs) 
        self._stop = threading.Event() 
        self.stream = stream
        self.follow = follow
  
    # function using _stop function 
    def stop(self): 
        self._stop.set() 
  
    def stopped(self): 
        return self._stop.isSet() 
  
    def run(self): 
        self.stream.filter(follow=self.follow, languages=["en"])
