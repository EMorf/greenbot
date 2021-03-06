import logging

from sqlalchemy.orm import joinedload

from greenbot import utils
from greenbot.exc import InvalidPointAmount
from greenbot.managers.db import DBManager
from greenbot.managers.schedule import ScheduleManager
from greenbot.models.command import Command
from greenbot.models.message import Message
from greenbot.models.user import User
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting

log = logging.getLogger(__name__)


class ActivityTracker(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "ActivityTracker"
    DESCRIPTION = "Gives points for being active"
    CATEGORY = "Feature"

    SETTINGS = [
        ModuleSetting(
            key="sub_role_id",
            label="ID of the sub role",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="regular_role_id",
            label="ID of the regular role",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="channels_to_listen_in",
            label="Channel IDs to listen in seperated by a ' '",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="hourly_credit",
            label="If he wrote enough messages this hour, the hour will be credited with this many points",
            type="number",
            placeholder="",
            default="8",
        ),
        ModuleSetting(
            key="daily_max_msgs",
            label="Maximum hours(msgs) that can be credited per day",
            type="number",
            placeholder="",
            default="12",
        ),
        ModuleSetting(
            key="daily_limit",
            label="If user reached daily max msgs he will get this many points",
            type="number",
            placeholder="",
            default="10",
        ),
        ModuleSetting(
            key="min_msgs_per_week",
            label="If user can't keep up this many credited hours per week he loses the role",
            type="number",
            placeholder="",
            default="10",
        ),
        ModuleSetting(
            key="min_regular_points",
            label="Points required for the regular role",
            type="number",
            placeholder="",
            default="10",
        ),
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.process_messages_job = None

    async def process_messages(self):
        with DBManager.create_session_scope() as db_session:
            regular_role = self.bot.filters.get_role([self.settings["regular_role_id"]], None, {})[0]
            sub_role = self.bot.filters.get_role([self.settings["sub_role_id"]], None, {})[0]
            counts_by_week = Message._get_week_count_by_user(db_session)
            for member in regular_role.members:
                count = counts_by_week.get(str(member.id), 0)
                if (
                    count < self.settings["min_msgs_per_week"]
                    or sub_role not in member.roles
                ):
                    await self.bot.remove_role(member, regular_role, "They failed to meet the requirements to keep the role")
            channels_to_listen_in = (
                self.settings["channels_to_listen_in"].split(" ")
                if len(self.settings["channels_to_listen_in"]) != 0
                else None
            )
            messages = Message._get_last_hour(db_session, channels_to_listen_in)
            counts_by_day = Message._get_day_count_by_user(db_session)
            for message in messages:
                count = counts_by_day.get(message.user_id, 0)
                if message.user_id != str(self.bot.bot_id):
                    if count < self.settings["daily_max_msgs"] - 1:
                        message.user.points += self.settings["hourly_credit"]
                    elif count == self.settings["daily_max_msgs"] - 1:
                        message.user.points += self.settings["daily_limit"]
                message.credited = True
                counts_by_day[message.user_id] = count + 1

            for user in User._get_users_with_points(
                db_session, self.settings["min_regular_points"]
            ):
                member = self.bot.filters.get_member([user.discord_id], None, {})[
                    0
                ]
                if not member:
                    continue

                count = counts_by_week.get(str(member.id), 0)
                if (
                    sub_role not in member.roles
                    or (regular_role in member.roles
                    or count < self.settings["min_msgs_per_week"])
                ):
                    continue
                await self.bot.add_role(member, regular_role, "They met the requirements to get the role")

    def enable(self, bot):
        if not bot:
            return
        self.process_messages_job = ScheduleManager.execute_every(
            3600, self.process_messages
        )  # Checks every hour

    def disable(self, bot):
        if not bot:
            return
        self.process_messages_job.remove()
        self.process_messages_job = None
