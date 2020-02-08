import logging

from contextlib import contextmanager

from sqlalchemy import INT, TEXT
from sqlalchemy import Column

from greenbot.exc import FailedCommand
from greenbot.managers.db import Base

log = logging.getLogger(__name__)


class User(Base):
    __tablename__ = "user"

    discord_id = Column(TEXT, primary_key=True, autoincrement=False)
    user_name = Column(TEXT, nullable=False)
    points = Column(INT, nullable=False, default=0)
    level = Column(INT, nullable=False, default=100)

    def jsonify(self):
        return {
            "discord_id": self.discord_id,
            "points": self.points,
            "level": self.level,
            "user_name": self.user_name
        }

    def can_afford(self, points):
        return not self.points < points

    @staticmethod
    def _create(db_session, discord_id, points=0, level=100, user_name=""):
        user = User(user_name=user_name, discord_id=str(discord_id), points=points, level=level)
        db_session.add(user)
        return user

    @staticmethod
    def _create_or_get_by_discord_id(db_session, discord_id, user_name=""):
        user = db_session.query(User).filter_by(discord_id=str(discord_id)).one_or_none() or User._create(db_session, discord_id=discord_id, user_name=user_name)
        user.user_name = user_name
        db_session.merge(user)
        return user

    @staticmethod
    def _get_users_with_points(db_session, points):
        return db_session.query(User).filter(User.points >= points).all()

    @contextmanager
    def spend_currency_context(self, points):
        try:
            with self._spend_currency_context(points, "points"):
                yield
        except FailedCommand:
            pass

    @contextmanager
    def _spend_currency_context(self, amount, currency):
        # self.{points,tokens} -= spend_amount
        setattr(self, currency, getattr(self, currency) - amount)

        try:
            yield
        except:
            setattr(self, currency, getattr(self, currency) + amount)
            raise
