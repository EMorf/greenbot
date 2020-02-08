import logging

from contextlib import contextmanager

from sqlalchemy import TEXT, BOOLEAN
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


class Message(Base):
    __tablename__ = "message"

    message_id = Column(TEXT, primary_key=True, autoincrement=False)
    user_id = Column(TEXT, ForeignKey("user.discord_id", ondelete="CASCADE"))
    channel_id = Column(TEXT, nullable=True)
    content = Column(TEXT, nullable=False)
    time_sent = Column(UtcDateTime(), nullable=True, server_default="NULL")
    credited = Column(BOOLEAN, nullable=False, default=False)
    user = relationship("User")

    @staticmethod
    def _create(db_session, message_id, user_id, channel_id, content):
        user = Message(
            message_id=str(message_id),
            user_id=str(user_id),
            channel_id=str(channel_id),
            content=content,
            time_sent=utils.now(),
        )
        db_session.add(user)
        return user

    @staticmethod
    def _get_messages(db_session, user_id):
        return db_session.query(Message).filter_by(user_id=str(user_id)).all()

    @staticmethod
    def _get_messages_since(db_session, user_id, time_since):
        return (
            db_session.query(Message)
            .filter_by(user_id=str(user_id))
            .filter(Message.time_sent > time_since)
            .all()
        )

    @staticmethod
    def _get_messages_count(db_session, user_id):
        return (
            db_session.query(func.count(Message.message_id))
            .filter(Message.user_id == str(user_id))
            .scalar()
        )

    @staticmethod
    def _get_messages_since_count(db_session, user_id, time_since):
        return (
            db_session.query(func.count(Message.message_id))
            .filter(Message.user_id == str(user_id))
            .filter(Message.time_sent > time_since)
            .scalar()
        )

    @staticmethod
    def _get_last_hour(db_session):
        return (
            db_session.query(Message)
            .filter_by(credited=False)
            .filter(Message.time_sent > utils.now() - timedelta(hours=1))
            .all()
        )

    @staticmethod
    def _get_day_count_user(db_session, user_id):
        return (
            db_session.query(func.count(Message.message_id))
            .filter(Message.credited == True)
            .filter(Message.user_id == str(user_id))
            .filter(Message.time_sent > utils.now() - timedelta(day=1))
            .scalar()
        )

    @staticmethod
    def _get_week_count_user(db_session, user_id):
        return (
            db_session.query(func.count(Message.message_id))
            .filter(Message.user_id == str(user_id))
            .filter(Message.time_sent > utils.now() - timedelta(day=7))
            .scalar()
        )
