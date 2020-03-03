import logging

import sqlalchemy
from datetime import timedelta
from sqlalchemy import BOOLEAN, INT, TEXT
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy_utc import UtcDateTime
from unidecode import unidecode

from greenbot.managers.db import Base
from greenbot.managers.db import DBManager
from greenbot.utils import find

from greenbot import utils

log = logging.getLogger("greenbot")

class Timeout(Base):
    __tablename__ = "timeouts"

    id = Column(INT, primary_key=True, autoincrement=False)
    user_id = Column(
        TEXT, ForeignKey("user.discord_id", ondelete="CASCADE"), nullable=True
    )
    issued_by_id = Column(
        TEXT, ForeignKey("user.discord_id", ondelete="SET NULL"), nullable=True
    )
    until = Column(UtcDateTime(), nullable=True, server_default="NULL")
    created_at = Column(UtcDateTime(), nullable=False, default=utils.now())

    user = relationship(
        "User",
        primaryjoin="User.discord_id==Timeout.user_id",
        foreign_keys="User.discord_id",
        uselist=False,
        cascade="",
        lazy="noload",
    )

    issued_by = relationship(
        "User",
        primaryjoin="User.discord_id==Timeout.issued_by_id",
        foreign_keys="User.discord_id",
        uselist=False,
        cascade="",
        lazy="noload",
    )

    @staticmethod
    def _create(db_session, user_id, issued_by_id, until, created_at):
        timeout = Timeout(user_id=user_id, issued_by_id=issued_by_id, until=until, created_at=created_at)
        db_session.add(timeout)
        return timeout
    
    @staticmethod
    def _is_timedout(db_session, user_id):
        
