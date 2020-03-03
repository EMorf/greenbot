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
            "log_timeout_update": False
        }
        self.salt = ""

    def enable(self, settings):
        self.settings = settings
        self.salt = utils.random_string()
        with DBManager.create_session_scope() as db_session:
            current_timeouts = Timeout._active_timeouts(db_session)
            for timeout in current_timeouts:
                ScheduleManager.execute_delayed(timeout.time_left + 1, self.auto_untimeout, args=[timeout.id, self.salt])

    def disable(self):
        self.settings = {
            "enabled": False,
            "log_timeout": False,
            "log_untimeout": False,
            "log_timeout_update": False
        }
        self.salt = None

    async def auto_untimeout(self, timeout_id, salt):
        log.info(timeout_id)
        log.info(salt)
        if self.salt != salt:
            return

        with DBManager.create_session_scope() as db_session:
            timeout = Timeout._by_id(db_session, timeout_id)
            if not timeout.active:
                log.info("timeout already ended!")
                return

            member = list(self.bot.filters.get_member([int(timeout.user_id)], None, {}))[0]
            if member:
                log.info(list(await self.untimeout_user(db_session, member, None, "Timeout removed by timer")))
                log.info("removed timeout with member")
                return
            log.info("removed timeout without member")
            timeout.unban(db_session, None, "Timeout removed by timer")
            if self.settings["log_untimeout"]: #TODO
                pass
        return

    async def timeout_user(self, db_session, member, banner, until, ban_reason):
        if not self.settings["enabled"]:
            return False, "Module is not enabled"
        current_timeout = Timeout._is_timedout(db_session, str(member.id))
        if current_timeout:
            if current_timeout.check_lengths(until):
                new_timeout = Timeout._create(db_session, str(member.id), str(banner.id), until, ban_reason)
                db_session.commit()
                current_timeout.unban(db_session, None, f"Timeout overwritten by Timeout #{new_timeout.id}")
                db_session.commit()
                if self.settings["log_timeout_update"]: #TODO
                    pass
            else:
                return False, f"{member} is currently timedout by Timeout #{current_timeout.id}"
        new_timeout = Timeout._create(db_session, str(member.id), str(banner.id), until, ban_reason)
        db_session.commit()
        for channel in self.bot.discord_bot.guild.text_channels:
            await channel.set_permissions(target=member, send_messages=False, reason=f"Timedout #{new_timeout.id}")

        if self.settings["log_timeout"]: #TODO
            pass
        log.info(f"{member} timed out")
        ScheduleManager.execute_delayed(new_timeout.time_left + 5, self.auto_untimeout, args=[new_timeout.id, self.salt])
        return True, None

    async def untimeout_user(self, db_session, member, unbanner, unban_reason):
        if not self.settings["enabled"]:
            return False, "Module is not enabled"
        current_timeout = Timeout._is_timedout(db_session, str(member.id))
        if not current_timeout:
            return False, f"{member} is not currently timedout!"
        
        current_timeout.unban(db_session, str(unbanner.id) if unbanner else None, unban_reason)
        db_session.commit()
        for channel in self.bot.discord_bot.guild.text_channels:
            overwrite = channel.overwrites_for(member)
            overwrite.send_messages = None
            if overwrite.is_empty():
                overwrite = None
            await channel.set_permissions(target=member, overwrite=overwrite, reason=f"Timedout #{current_timeout.id}")

        if self.settings["log_untimeout"]: #TODO
            pass
        return True, None
