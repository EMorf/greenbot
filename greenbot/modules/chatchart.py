import logging
import discord
import heapq
from io import BytesIO
import matplotlib

matplotlib.use("agg")
import matplotlib.pyplot as plt

from greenbot import utils
from greenbot.managers.db import DBManager
from greenbot.models.command import Command
from greenbot.models.message import Message
from greenbot.modules import BaseModule

log = logging.getLogger(__name__)


class ChatChart(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "ChatChart"
    DESCRIPTION = "Generates a chart in said channel"
    CATEGORY = "Feature"

    SETTINGS = []

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    def create_chart(self, top, others, channel):
        plt.clf()
        sizes = [x[1] for x in top]
        labels = ["{} {:g}%".format(x[0], x[1]) for x in top]
        if len(top) >= 20:
            sizes = sizes + [others]
            labels = labels + ["Others {:g}%".format(others)]
        if len(channel.name) >= 19:
            channel_name = "{}...".format(channel.name[:19])
        else:
            channel_name = channel.name
        title = plt.title("Stats in #{}".format(channel_name), color="white")
        title.set_va("top")
        title.set_ha("center")
        plt.gca().axis("equal")
        colors = [
            "r",
            "darkorange",
            "gold",
            "y",
            "olivedrab",
            "green",
            "darkcyan",
            "mediumblue",
            "darkblue",
            "blueviolet",
            "indigo",
            "orchid",
            "mediumvioletred",
            "crimson",
            "chocolate",
            "yellow",
            "limegreen",
            "forestgreen",
            "dodgerblue",
            "slateblue",
            "gray",
        ]
        pie = plt.pie(sizes, colors=colors, startangle=0)
        plt.legend(
            pie[0],
            labels,
            bbox_to_anchor=(0.7, 0.5),
            loc="center",
            fontsize=10,
            bbox_transform=plt.gcf().transFigure,
            facecolor="#ffffff",
        )
        plt.subplots_adjust(left=0.0, bottom=0.1, right=0.45)
        image_object = BytesIO()
        plt.savefig(image_object, format="PNG", facecolor="#36393E")
        image_object.seek(0)
        return image_object

    async def chatchart(self, bot, author, channel, message, args):
        embed = discord.Embed(description="Loading...", colour=0x00ccff)
        embed.set_thumbnail(url="https://i.imgur.com/vSp4xRk.gif")
        sent_message = await self.bot.say(channel=channel, embed=embed)

        message_args = message.split(" ")

        requested_channel = (self.bot.filters.get_channel([message[0]], None, {})[0] if len(message) > 0 else None) or channel
        limit = message[1] if len(message) > 1 else 5000
        limit = None if limit == "all" else limit

        history = []
        if not requested_channel.permissions_for(author).read_messages == True:
            await sent_message.delete()
            await self.bot.say(channel=channel, message="You're not allowed to access that channel.")
            return False

        try:
            async for message in requested_channel.history(limit=limit):
                history.append(message)
        except discord.errors.Forbidden:
            await sent_message.delete()
            await self.bot.say(channel=channel, message="No permissions to read that channel.")
            return False

        message_data = {"total count": 0, "users": {}}

        for message in history:
            if len(message.author.name) >= 20:
                short_name = "{}...".format(message.author.name[:20]).replace("$", "\\$")
            else:
                short_name = message.author.name.replace("$", "\\$")
            whole_name = "{}#{}".format(short_name, message.author.discriminator)
            if message.author.bot:
                pass

            elif whole_name in message_data["users"]:
                message_data["users"][whole_name]["msgcount"] += 1
                message_data["total count"] += 1
            else:
                message_data["users"][whole_name] = {}
                message_data["users"][whole_name]["msgcount"] = 1
                message_data["total count"] += 1

        if message_data['users'] == {}:
            await sent_message.delete()
            return await self.bot.say(channel=channel, message=f'Only bots have sent messages in {requested_channel.mention}')

        for usr in message_data["users"]:
            pd = float(message_data["users"][usr]["msgcount"]) / float(message_data["total count"])
            message_data["users"][usr]["percent"] = round(pd * 100, 1)

        top_ten = heapq.nlargest(
            20,
            [
                (x, message_data["users"][x]["percent"])
                for x in message_data["users"]
            ],
            key=lambda x: x[1],
        )
        others = 100 - sum(x[1] for x in top_ten)
        img = self.create_chart(top_ten, others, requested_channel)
        await sent_message.delete()
        await self.bot.say(channel=channel, file=discord.File(img, "chart.png"))
        return True

    def load_commands(self, **options):
        self.commands["chatchart"] = Command.raw_command(
            self.chatchart,
            command="chatchart",
            delay_all=0,
            delay_user=0,
            can_execute_with_whisper=False,
            description="Generates a pie chart, representing messages in the specified channel.",
        )

    def enable(self, bot):
        if not bot:
            return

    def disable(self, bot):
        if not bot:
            return
