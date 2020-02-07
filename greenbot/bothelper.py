import collections


class BotHelper:
    bot_name = "Unknown"

    @staticmethod
    def get_bot_name():
        return BotHelper.bot_name

    @staticmethod
    def set_bot_name(bot_name):
        BotHelper.bot_name = bot_name
