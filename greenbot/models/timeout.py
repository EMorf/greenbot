import logging

import sqlalchemy
from sqlalchemy import or_
from sqlalchemy import BOOLEAN, INT, TEXT
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy_utc import UtcDateTime

from greenbot.managers.db import Base
from greenbot.managers.db import DBManager

from greenbot import utils

log = logging.getLogger("greenbot")

class Timeout(Base):
    __tablename__ = "timeouts"

    id = Column(INT, primary_key=True, autoincrement=False)
    active = Column(BOOLEAN, default=True, nullable=False)
    user_id = Column(
        TEXT, ForeignKey("user.discord_id", ondelete="CASCADE"), nullable=False
    )
    issued_by_id = Column(
        TEXT, ForeignKey("user.discord_id", ondelete="SET NULL"), nullable=True
    )
    unbanned_by_id = Column(
        TEXT, ForeignKey("user.discord_id", ondelete="SET NULL"), nullable=True
    )
    ban_reason = Column(TEXT, nullable=True)
    unban_reason = Column(TEXT, nullable=True)
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

    unbanned_by = relationship(
        "User",
        primaryjoin="User.discord_id==Timeout.unbanned_by_id",
        foreign_keys="User.discord_id",
        uselist=False,
        cascade="",
        lazy="noload",
    )

    @property
    def time_left(self):
        return (self.until - utils.now()).total_seconds() if self.until > utils.now() else 0

    def check_lengths(self, _date):
        if not self.until:
            return False

        return self.until < _date if _date else True

    def unban(self, db_session, unbanned_by_id, unban_reason):
        self.active = False
        self.unbanned_by_id = unbanned_by_id,
        self.unban_reason = unban_reason
        db_session.merge(self)
        return self

    @staticmethod
    def _active_timeouts(db_session):
        return db_session.query(Timeout).filter_by(active=True).all()

    @staticmethod
    def _create(db_session, user_id, issued_by_id, until, ban_reason):
        timeout = Timeout(active=True, user_id=user_id, issued_by_id=issued_by_id, until=until, created_at=utils.now(), ban_reason=ban_reason)
        db_session.add(timeout)
        return timeout
    
    @staticmethod
    def _is_timedout(db_session, user_id):
        return db_session.query(Timeout).filter_by(user_id=user_id).filter_by(active=True).filter(or_(Timeout.until == None, Timeout.until < utils.now())).one_or_none()

    @staticmethod
    def _by_user_id(db_session, user_id):
        return db_session.query(Timeout).filter_by(user_id=user_id).all()

    @staticmethod
    def _by_id(db_session, _id):
        return db_session.query(Timeout).filter_by(id=_id).one_or_none()
