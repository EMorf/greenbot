import logging
import tweepy

from greenbot.managers.handler import HandlerManager

log = logging.getLogger(__name__)


class MyStreamListener(tweepy.  StreamListener):
    def __init__(self, bot, api):
        self.api = api
        self.bot = bot
        self.me = api.me()

    def on_connect(self):
        log.info("Twitter connected")

    def on_disconnect(self, notice):
        log.info("Twitter disconnected")

    def on_status(self, tweet):
        log.info("tweet recieved")
        self.bot.private_loop.create_task(HandlerManager.trigger("twitter_on_status", tweet=tweet))

    def on_error(self, status):
        log.error("Disconnected from Twitter")
        return False

class TwitterManager:

    def __init__(self, bot, config):
        self.auth = tweepy.OAuthHandler(config["consumer_key"], config["consumer_secret"])
        self.auth.set_access_token(config["access_token"], config["access_token_secret"])
        self.api = tweepy.API(self.auth, wait_on_rate_limit=True, wait_on_rate_limit_notify=True)

        self.tweets_listener = MyStreamListener(bot, self.api)
