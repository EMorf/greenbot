import logging
import json

from contextlib import contextmanager

from sqlalchemy import INT, TEXT, BOOLEAN
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy import func
from sqlalchemy.orm import relationship
from sqlalchemy_utc import UtcDateTime

from greenbot.exc import FailedCommand
from greenbot.managers.db import Base
import greenbot.utils as utils

from datetime import timedelta


log = logging.getLogger(__name__)


class Giveaway(Base):
    __tablename__ = "giveaways"

    id = Column(INT, primary_key=True, autoincrement=True)
    started_by_id = Column(TEXT, ForeignKey("user.discord_id", ondelete="NULL"))
    started_by = relationship("User", foreign_keys=[started_by_id])
    ended_by_id = Column(TEXT, ForeignKey("user.discord_id", ondelete="NULL"), nullable=True)
    ended_by = relationship("User", foreign_keys=[ended_by_id])
    giveaway_deadline = Column(TEXT, nullable=False)
    giveaway_item = Column(TEXT, nullable=False)
    locked = Column(BOOLEAN, nullable=False, default=False)
    winner_id = Column(TEXT, ForeignKey("user.discord_id", ondelete="NULL"))
    winner = relationship("User", foreign_keys=[winner_id])
    entries = relationship("GiveawayEntry", back_populates="giveaway", foreign_keys=[])

    enabled = Column(BOOLEAN, nullable=False, default=True)

    def _lock_state(self, db_session, lock):
        self.locked = lock
        db_session.merge(self)
        return self

    def _disable(self, db_session):
        self.active = False
        db_session.merge(self)
        return self

    @staticmethod
    def _create(db_session, started_by_id, giveaway_item, giveaway_deadline):
        if Giveaway._get_current_giveaway(db_session):
            return None

        giveaway = Giveaway(started_by_id=started_by_id, giveaway_item=giveaway_item, giveaway_deadline=giveaway_deadline)
        db_session.add(giveaway)
        return giveaway

    @staticmethod
    def _get_current_giveaway(db_session):
        return db_session.query(Giveaway).filter_by(enabled=True).one_or_none()

    
class GiveawayEntry(Base):
    __tablename__ = "giveaway_entries"

    id = Column(INT, primary_key=True, autoincrement=True)
    user_id = Column(TEXT, ForeignKey("user.discord_id", ondelete="CASCADE"))
    user = relationship("User")
    giveaway_id = Column(INT, ForeignKey('giveaways.id', ondelete="CASCADE"))
    giveaway = relationship("Giveaway", back_populates="entries")
    date_entered = Column(UtcDateTime(), nullable=False)
    tickets = Column(INT, nullable=False, default=1)

    @staticmethod
    def _create(db_session, user_id, giveaway_id, tickets):
        if GiveawayEntry.is_entered(db_session, user_id, giveaway_id):
            return None
        
        giveaway_entry = GiveawayEntry(user_id=user_id, giveaway_id=giveaway_id, date_entered=utils.now(), tickets=tickets)
        db_session.add(giveaway_entry)
        return giveaway_entry

    @staticmethod
    def is_entered(db_session, user_id, giveaway_id):
        return db_session.query(GiveawayEntry).filter_by(user_id=user_id).filter_by(giveaway_id=giveaway_id).one_or_none()
    