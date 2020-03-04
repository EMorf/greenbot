import logging
import discord

from greenbot.managers.handler import HandlerManager
from greenbot.managers.db import DBManager
from greenbot.managers.schedule import ScheduleManager
from greenbot.models.timeout import Timeout
from greenbot.models.user import User

from greenbot import utils

log = logging.getLogger(__name__)


class TimeoutManager:
    def __init__(self, bot):
        self.bot = bot
        self.settings = {
            "enabled": False,
            "log_timeout": False,
            "log_untimeout": False,
            "log_timeout_update": False,
            "punished_role_id": "",
        }
        self.salt = ""

    def enable(self, settings):
        self.settings = settings
        self.salt = utils.random_string()
        with DBManager.create_session_scope() as db_session:
            current_timeouts = Timeout._active_timeouts(db_session)
            for timeout in current_timeouts:
                ScheduleManager.execute_delayed(
                    timeout.time_left + 1,
                    self.auto_untimeout,
                    args=[timeout.id, self.salt],
                )
    def update_settings(self, settings):
        self.settings = settings

    def disable(self):
        self.settings = {
            "enabled": False,
            "log_timeout": False,
            "log_untimeout": False,
            "log_timeout_update": False,
            "punished_role_id": "",
        }
        self.salt = None

    async def auto_untimeout(self, timeout_id, salt):
        if self.salt != salt:
            return

        with DBManager.create_session_scope() as db_session:
            timeout = Timeout._by_id(db_session, timeout_id)
            if not timeout.active:
                return

            member = list(
                self.bot.filters.get_member([int(timeout.user_id)], None, {})
            )[0]
            if member:
                await self.untimeout_user(db_session, member, None, "Timeout removed by timer")
                return
            timeout.unban(db_session, None, "Timeout removed by timer")
            if self.settings["log_untimeout"]:  # TODO
                pass
        return

    async def timeout_user(self, db_session, member, banner, until, ban_reason):
        if not self.settings["enabled"]:
            return False, "Module is not enabled"
        current_timeout = Timeout._is_timedout(db_session, str(member.id))
        new_timeout = None
        if current_timeout is not None:
            if current_timeout.check_lengths(until):
                current_timeout.active = False
                new_timeout = Timeout._create(
                    db_session, str(member.id), str(banner.id), until, ban_reason
                )
                db_session.commit()
                current_timeout.unban(
                    db_session,
                    None,
                    f"Timeout overwritten by Timeout #{new_timeout.id}",
                )
                db_session.commit()
            else:
                return (
                    False,
                    f"{member} is currently timedout by Timeout #{current_timeout.id}",
                )
        if not new_timeout:
            new_timeout = Timeout._create(
                db_session, str(member.id), str(banner.id), until, ban_reason
            )
            db_session.commit()

        role = list(self.bot.filters.get_role([self.settings["punished_role_id"]], None, {}))[0]
        self.bot.add_role(member, role, f"Timedout by Timeout #{new_timeout.id}")
        if self.settings["log_timeout"]:
            embed = discord.Embed(
                title="Member has been timedout",
                timestamp=new_timeout.created_at,
                colour=member.colour,
            )
            embed.set_author(
                name=f"{member} ({member.id})- Timeout Removed",
                icon_url=str(member.avatar_url),
            )
            embed.add_field(
                name="Banned on",
                value=str(new_timeout.created_at.strftime("%b %d %Y %H:%M:%S %Z")),
                inline=False,
            )
            if new_timeout.issued_by_id:
                issued_by = list(
                    self.bot.filters.get_member(
                        [int(new_timeout.issued_by_id)], None, {}
                    )
                )[0]
                embed.add_field(
                    name="Banned by",
                    value=issued_by.mention
                    if issued_by
                    else f"{new_timeout.issued_by_id}",
                    inline=False,
                )
            if new_timeout.ban_reason:
                embed.add_field(
                    name="Ban Reason", value=str(new_timeout.ban_reason), inline=False
                )
            await HandlerManager.trigger("aml_custom_log", embed=embed)
        ScheduleManager.execute_delayed(
            new_timeout.time_left + 5,
            self.auto_untimeout,
            args=[new_timeout.id, self.salt],
        )
        return True, None

    async def untimeout_user(self, db_session, member, unbanner, unban_reason):
        if not self.settings["enabled"]:
            return False, "Module is not enabled"
        current_timeout = Timeout._is_timedout(db_session, str(member.id))
        if not current_timeout:
            return False, f"{member} is not currently timedout!"

        current_timeout.unban(
            db_session, str(unbanner.id) if unbanner else None, unban_reason
        )
        db_session.commit()
        role = list(self.bot.filters.get_role([self.settings["punished_role_id"]], None, {}))[0]
        self.bot.remove_role(member, role, f"Untimedout by Timeout #{current_timeout.id}")

        if self.settings["log_untimeout"]:
            embed = discord.Embed(
                title="Member timedout has been removed",
                timestamp=current_timeout.unbanned_at,
                colour=member.colour,
            )
            embed.set_author(
                name=f"{member} ({member.id})- Timeout Removed",
                icon_url=str(member.avatar_url),
            )
            embed.add_field(
                name="Banned on",
                value=str(current_timeout.created_at.strftime("%b %d %Y %H:%M:%S %Z")),
                inline=False,
            )
            embed.add_field(
                name="Unbanned on",
                value=str(current_timeout.unbanned_at.strftime("%b %d %Y %H:%M:%S %Z")),
                inline=False,
            )
            if current_timeout.issued_by_id:
                issued_by = list(
                    self.bot.filters.get_member(
                        [int(current_timeout.issued_by_id)], None, {}
                    )
                )[0]
                embed.add_field(
                    name="Banned by",
                    value=issued_by.mention
                    if issued_by
                    else f"{current_timeout.issued_by_id}",
                    inline=False,
                )
            if current_timeout.ban_reason:
                embed.add_field(
                    name="Ban Reason", value=str(current_timeout.ban_reason), inline=False
                )
            if current_timeout.unban_reason:
                embed.add_field(
                    name="Unban Reason",
                    value=str(current_timeout.unban_reason),
                    inline=False,
                )
            if current_timeout.unbanned_by_id:
                unbanned_by = list(
                    self.bot.filters.get_member(
                        [int(current_timeout.unbanned_by_id)], None, {}
                    )
                )[0]
                embed.add_field(
                    name="Unban By",
                    value=unbanned_by.mention
                    if unbanned_by
                    else f"{current_timeout.unbanned_by_id}",
                    inline=False,
                )
            await HandlerManager.trigger("aml_custom_log", embed=embed)
        return True, None
