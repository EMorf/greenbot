import logging

import json
import discord
from datetime import datetime

from greenbot import utils
from greenbot.managers.schedule import ScheduleManager
from greenbot.managers.redis import RedisManager
from greenbot.models.command import Command
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting

log = logging.getLogger(__name__)


class RemindMe(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "RemindMe"
    DESCRIPTION = "Allows users to create reminders"
    CATEGORY = "Feature"

    SETTINGS = [
        ModuleSetting(
            key="max_reminders_per_user",
            label="Maximum reminders per user",
            type="number",
            placeholder="",
            default=3,
        ),
        ModuleSetting(
            key="cost",
            label="Points required to add a reminder",
            type="number",
            placeholder="",
            default="0",
        ),
        ModuleSetting(
            key="emoji",
            label="Emoji for reminder",
            type="text",
            placeholder="🔔",
            default="🔔",
        ),
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.redis = RedisManager.get()
        self.reminder_tasks = {}

    @property
    def help(self):
        help_desc = f"""
        `Syntax: {self.bot.command_prefix}remindme <time> <text>`
        Send you <text> when the time is up.
        Accepts: seconds, minutes, hours, days, weeks
        Examples:
        - {self.bot.command_prefix}remindme 2min Do that thing in 2 minutes
        - {self.bot.command_prefix}remindme 3h40m Do that thing in 3 hours and 40 minutes
        """
        data = discord.Embed(
            title="RemindMe help Menu",
            description=help_desc,
            colour=discord.Colour.red(),
        )
        data.set_thumbnail(url=self.bot.discord_bot.client.user.avatar_url)
        return data

    async def create_reminder(self, bot, author, channel, message, args):
        command_args = message.split(" ") if message else []
        try:
            reminders_list = json.loads(
                self.redis.get(f"{self.bot.bot_name}:remind-me-reminders")
            )
            """
            { 
                user_id: [
                    {
                        "message_id": message_id,
                        "channel_id": channel_id,
                        "message": message,
                        "date_of_reminder": date_of_reminder,
                        "date_reminder_set": date_reminder_set
                    },
                ],
            }
            """
        except:
            self.redis.set(f"{self.bot.bot_name}:remind-me-reminders", json.dumps({}))
            reminders_list = {}
        user_reminders = (
            reminders_list[str(author.id)] if str(author.id) in reminders_list else []
        )
        if len(user_reminders) >= int(self.settings["max_reminders_per_user"]):
            await self.bot.say(
                channel,
                f"{author.mention} you already have {len(user_reminders)} reminders!",
            )
            return False
        if len(command_args) == 0:
            await self.bot.say(channel, embed=self.help)
            return False
        time_delta = utils.parse_timedelta(command_args[0])
        if not time_delta:
            await self.bot.say(
                channel, f"{author.mention} invalid time: {command_args[0]}"
            )
            return False
        await self.bot.say(
            channel,
            f"{author.mention} ill remind you that in {utils.seconds_to_resp(time_delta.total_seconds())}",
        )
        bot_message = await self.bot.say(
            channel,
            f"If anyone else wants to be reminded click the {self.settings['emoji']}",
        )
        salt = utils.random_string()
        await bot_message.add_reaction(self.settings["emoji"])
        reminder = {
            "message_id": bot_message.id,
            "channel_id": bot_message.channel.id,
            "salt": salt,
            "message": " ".join(command_args[1:]),
            "date_of_reminder": str(utils.now() + time_delta),
            "date_reminder_set": str(utils.now()),
        }
        user_reminders.append(reminder)
        reminders_list[str(author.id)] = user_reminders
        self.redis.set(
            f"{self.bot.bot_name}:remind-me-reminders", json.dumps(reminders_list)
        )
        self.reminder_tasks[salt] = ScheduleManager.execute_delayed(
            time_delta.total_seconds(),
            self.execute_reminder,
            args=[salt, author.id, reminder],
        )

    async def forgetme(self, bot, author, channel, message, args):
        try:
            reminders_list = json.loads(
                self.redis.get(f"{self.bot.bot_name}:remind-me-reminders")
            )
            """
            { 
                user_id: [
                    {
                        "message_id": message_id,
                        "channel_id": channel_id,
                        "salt": salt,
                        "message": message,
                        "date_of_reminder": date_of_reminder,
                        "date_reminder_set": date_reminder_set
                    },
                ],
            }
            """
        except:
            self.redis.set(f"{self.bot.bot_name}:remind-me-reminders", json.dumps({}))
            reminders_list = {}
        user_reminders = reminders_list[str(author.id)] if str(author.id) else []
        for reminder in user_reminders:
            self.reminder_tasks.pop(reminder["salt"]).remove()
            try:
                channel = self.bot.discord_bot.guild.get_channel(
                    int(reminder["channel_id"])
                )
                bot_message = await channel.fetch_message(int(reminder["message_id"]))
                await bot_message.delete()
            except Exception as e:
                log.error(f"Failed to delete message from bot: {e}")
        reminders_list[str(author.id)] = []
        self.redis.set(
            f"{self.bot.bot_name}:remind-me-reminders", json.dumps(reminders_list)
        )
        await self.bot.say(channel, f"{author.mention} you have been forgotten")

    def load_commands(self, **options):
        self.commands["remindme"] = Command.raw_command(
            self.create_reminder,
            delay_all=0,
            delay_user=0,
            cost=int(self.settings["cost"]),
            can_execute_with_whisper=False,
            description="Creates a reminder",
        )
        self.commands["forgetme"] = Command.raw_command(
            self.forgetme,
            delay_all=0,
            delay_user=0,
            can_execute_with_whisper=False,
            description="Creates a reminder",
        )

    async def execute_reminder(self, salt, user_id, reminder):
        self.reminder_tasks.pop(salt)
        try:
            channel = self.bot.discord_bot.guild.get_channel(
                int(reminder["channel_id"])
            )
            bot_message = await channel.fetch_message(int(reminder["message_id"]))
        except:
            return
        message = reminder["message"]
        for reaction in bot_message.reactions:
            if reaction.emoji == self.settings["emoji"]:
                users = await reaction.users().flatten()
                users.remove(self.bot.discord_bot.client.user)
                sender = await self.bot.discord_bot.get_user(user_id)
                if sender and sender not in users:
                    users.append(sender)
                for user in users:
                    date_of_reminder = utils.parse_date(reminder["date_of_reminder"])
                    date_reminder_set = utils.parse_date(reminder["date_reminder_set"])
                    seconds = int(
                        round((date_of_reminder - date_reminder_set).total_seconds())
                    )
                    response_str = utils.seconds_to_resp(seconds)
                    await self.bot.private_message(
                        user,
                        f"Hello! You asked me to remind you {response_str} ago:\n{message}",
                    )
                break
        try:
            await bot_message.delete()
        except Exception as e:
            log.error(f"Failed to delete message from bot: {e}")
        try:
            reminders_list = json.loads(
                self.redis.get(f"{self.bot.bot_name}:remind-me-reminders")
            )
            """
            { 
                user_id: [
                    {
                        "message_id": message_id,
                        "channel_id": channel_id,
                        "salt": salt,
                        "message": message,
                        "date_of_reminder": date_of_reminder,
                        "date_reminder_set": date_reminder_set
                    },
                ],
            }
            """
        except:
            self.redis.set(f"{self.bot.bot_name}:remind-me-reminders", json.dumps({}))
            reminders_list = {}
        user_reminders = (
            reminders_list[str(user_id)] if str(user_id) in reminders_list else []
        )
        for _reminder in user_reminders:
            if _reminder == reminder:
                user_reminders.remove(_reminder)
                break
        reminders_list[str(user_id)] = user_reminders
        self.redis.set(
            f"{self.bot.bot_name}:remind-me-reminders", json.dumps(reminders_list)
        )

    def enable(self, bot):
        if not bot:
            return
        try:
            reminders_list = json.loads(
                self.redis.get(f"{self.bot.bot_name}:remind-me-reminders")
            )
            """
            { 
                user_id: [
                    {
                        "message_id": message_id,
                        "channel_id": channel_id,
                        "salt": salt,
                        "message": message,
                        "date_of_reminder": date_of_reminder,
                        "date_reminder_set": date_reminder_set
                    },
                ],
            }
            """
        except:
            self.redis.set(f"{self.bot.bot_name}:remind-me-reminders", json.dumps({}))
            reminders_list = {}
        new_reminders_list = {}
        for user_id in reminders_list:
            user_reminders = reminders_list[user_id]
            new_user_reminders = []
            for reminder in user_reminders:
                salt = reminder["salt"]
                date_of_reminder = utils.parse_date(reminder["date_of_reminder"])
                if date_of_reminder < utils.now():
                    continue
                new_user_reminders.append(reminder)
                self.reminder_tasks[salt] = ScheduleManager.execute_delayed(
                    (date_of_reminder - utils.now()).total_seconds(),
                    self.execute_reminder,
                    args=[salt, user_id, reminder],
                )
            new_reminders_list[user_id] = new_user_reminders
        self.redis.set(
            f"{self.bot.bot_name}:remind-me-reminders", json.dumps(new_reminders_list)
        )

    def disable(self, bot):
        if not bot:
            return
