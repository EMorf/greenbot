import argparse
import logging
import re

import sqlalchemy
from datetime import timedelta
from sqlalchemy import BOOLEAN, INT, TEXT
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from unidecode import unidecode

from greenbot.managers.db import Base
from greenbot.managers.db import DBManager
from greenbot.utils import find

log = logging.getLogger("greenbot")


class Banphrase(Base):
    __tablename__ = "banphrase"

    id = Column(INT, primary_key=True)
    name = Column(TEXT, nullable=False, default="")
    phrase = Column(TEXT, nullable=False)
    length = Column(INT, nullable=False, default=300)
    warning = Column(BOOLEAN, nullable=False, default=True)
    case_sensitive = Column(BOOLEAN, nullable=False, default=False)
    remove_accents = Column(BOOLEAN, nullable=False, default=False)
    enabled = Column(BOOLEAN, nullable=False, default=True)
    operator = Column(
        TEXT, nullable=False, default="contains", server_default="contains"
    )

    data = relationship("BanphraseData", uselist=False, cascade="", lazy="joined")

    DEFAULT_TIMEOUT_LENGTH = 300

    def __init__(self, **options):
        self.id = None
        self.name = "No name"
        self.length = self.DEFAULT_TIMEOUT_LENGTH
        self.warning = True
        self.case_sensitive = False
        self.enabled = True
        self.operator = "contains"
        self.remove_accents = False
        self.compiled_regex = None
        self.predicate = None

        self.set(**options)

    def set(self, **options):
        self.name = options.get("name", self.name)
        self.phrase = options.get("phrase", self.phrase)
        self.length = options.get("length", self.length)
        self.warning = options.get("warning", self.warning)
        self.case_sensitive = options.get("case_sensitive", self.case_sensitive)
        self.enabled = options.get("enabled", self.enabled)
        self.operator = options.get("operator", self.operator)
        self.remove_accents = options.get("remove_accents", self.remove_accents)
        self.compiled_regex = None

        self.refresh_operator()

    def format_message(self, message):
        if self.case_sensitive is False:
            message = message.lower()
        if self.remove_accents:
            message = unidecode(message).strip()

        return message

    def get_phrase(self):
        if self.case_sensitive is False:
            return self.phrase.lower()
        return self.phrase

    def refresh_operator(self):
        self.predicate = getattr(self, f"predicate_{self.operator}", None)

        self.compiled_regex = None
        if self.operator == "regex":
            try:
                if self.case_sensitive:
                    self.compiled_regex = re.compile(self.phrase)
                else:
                    self.compiled_regex = re.compile(self.phrase, flags=re.IGNORECASE)
            except Exception:
                log.exception(f"Unable to compile regex: {self.phrase}")

    def predicate_contains(self, message):
        return self.get_phrase() in self.format_message(message)

    def predicate_startswith(self, message):
        return self.format_message(message).startswith(self.get_phrase())

    def predicate_endswith(self, message):
        return self.format_message(message).endswith(self.get_phrase())

    def predicate_exact(self, message):
        return self.format_message(message) == self.get_phrase()

    def predicate_regex(self, message):
        if not self.compiled_regex:
            return False

        return self.compiled_regex.search(self.format_message(message))

    def match(self, message):
        """
        Returns True if message matches our banphrase.
        Otherwise it returns False
        Respects case-sensitiveness option
        """
        if not self.predicate:
            log.warning("Banphrase %s is missing a predicate", self.id)
            return False

        return self.predicate(message)

    def greater_than(self, other):
        return self.length > other.length

    def exact_match(self, message):
        """
        Returns True if message exactly matches our banphrase.
        Otherwise it returns False
        Respects case-sensitiveness option
        """
        if self.case_sensitive:
            return self.phrase == message

        return self.phrase.lower() == message.lower()

    def jsonify(self):
        return {
            "id": self.id,
            "name": self.name,
            "phrase": self.phrase,
            "length": self.length,
            "operator": self.operator,
            "case_sensitive": self.case_sensitive,
        }


@sqlalchemy.event.listens_for(Banphrase, "load")
def on_banphrase_load(target, _context):
    target.refresh_operator()


@sqlalchemy.event.listens_for(Banphrase, "refresh")
def on_banphrase_refresh(target, _context, _attrs):
    target.refresh_operator()


class BanphraseData(Base):
    __tablename__ = "banphrase_data"

    banphrase_id = Column(
        INT, ForeignKey("banphrase.id"), primary_key=True, autoincrement=False
    )
    num_uses = Column(INT, nullable=False, default=0)
    added_by = Column(
        TEXT, ForeignKey("user.discord_id", ondelete="SET NULL"), nullable=True
    )
    edited_by = Column(
        TEXT, ForeignKey("user.discord_id", ondelete="SET NULL"), nullable=True
    )

    user = relationship(
        "User",
        primaryjoin="User.discord_id==BanphraseData.added_by",
        foreign_keys="User.discord_id",
        uselist=False,
        cascade="",
        lazy="noload",
    )

    user2 = relationship(
        "User",
        primaryjoin="User.discord_id==BanphraseData.edited_by",
        foreign_keys="User.discord_id",
        uselist=False,
        cascade="",
        lazy="noload",
    )

    def __init__(self, banphrase_id, **options):
        self.banphrase_id = banphrase_id
        self.num_uses = 0
        self.added_by = None
        self.edited_by = None

        self.set(**options)

    def set(self, **options):
        self.num_uses = options.get("num_uses", self.num_uses)
        self.added_by = options.get("added_by", self.added_by)
        self.edited_by = options.get("edited_by", self.edited_by)


class BanphraseManager:
    def __init__(self, bot):
        self.bot = bot
        self.banphrases = []
        self.enabled_banphrases = []
        self.db_session = DBManager.create_session(expire_on_commit=False)

        if self.bot:
            self.bot.socket_manager.add_handler(
                "banphrase.update", self.on_banphrase_update
            )
            self.bot.socket_manager.add_handler(
                "banphrase.remove", self.on_banphrase_remove
            )

    def on_banphrase_update(self, data):
        try:
            banphrase_id = int(data["id"])
        except (KeyError, ValueError):
            log.warning("No banphrase ID found in on_banphrase_update")
            return False

        updated_banphrase = find(
            lambda banphrase: banphrase.id == banphrase_id, self.banphrases
        )
        if updated_banphrase:
            with DBManager.create_session_scope(expire_on_commit=False) as db_session:
                db_session.add(updated_banphrase)
                db_session.refresh(updated_banphrase)
                db_session.expunge(updated_banphrase)
        else:
            with DBManager.create_session_scope(expire_on_commit=False) as db_session:
                updated_banphrase = (
                    db_session.query(Banphrase).filter_by(id=banphrase_id).one_or_none()
                )
                db_session.expunge_all()
                if updated_banphrase is not None:
                    self.db_session.add(updated_banphrase.data)

        if updated_banphrase:
            if updated_banphrase not in self.banphrases:
                self.banphrases.append(updated_banphrase)
            if (
                updated_banphrase.enabled is True
                and updated_banphrase not in self.enabled_banphrases
            ):
                self.enabled_banphrases.append(updated_banphrase)

        for banphrase in self.enabled_banphrases:
            if banphrase.enabled is False:
                self.enabled_banphrases.remove(banphrase)

    def on_banphrase_remove(self, data):
        try:
            banphrase_id = int(data["id"])
        except (KeyError, ValueError):
            log.warning("No banphrase ID found in on_banphrase_remove")
            return False

        removed_banphrase = find(
            lambda banphrase: banphrase.id == banphrase_id, self.banphrases
        )
        if removed_banphrase:
            if removed_banphrase.data and removed_banphrase.data in self.db_session:
                self.db_session.expunge(removed_banphrase.data)

            if removed_banphrase in self.enabled_banphrases:
                self.enabled_banphrases.remove(removed_banphrase)

            if removed_banphrase in self.banphrases:
                self.banphrases.remove(removed_banphrase)

    def load(self):
        self.banphrases = self.db_session.query(Banphrase).all()
        for banphrase in self.banphrases:
            self.db_session.expunge(banphrase)
        self.enabled_banphrases = [
            banphrase for banphrase in self.banphrases if banphrase.enabled is True
        ]
        return self

    def commit(self):
        self.db_session.commit()

    def create_banphrase(self, phrase, **options):
        for banphrase in self.banphrases:
            if banphrase.phrase == phrase:
                return banphrase, False

        banphrase = Banphrase(phrase=phrase, **options)
        banphrase.data = BanphraseData(
            banphrase.id, added_by=options.get("added_by", None)
        )

        self.db_session.add(banphrase)
        self.db_session.add(banphrase.data)
        self.commit()
        self.db_session.expunge(banphrase)

        self.banphrases.append(banphrase)
        self.enabled_banphrases.append(banphrase)

        return banphrase, True

    def remove_banphrase(self, banphrase):
        self.banphrases.remove(banphrase)
        if banphrase in self.enabled_banphrases:
            self.enabled_banphrases.remove(banphrase)

        self.db_session.expunge(banphrase.data)
        self.db_session.delete(banphrase)
        self.db_session.delete(banphrase.data)
        self.commit()

    async def punish(self, user, banphrase):
        """
        This method is responsible for calculating
        what sort of punishment a user deserves.
        """

        if banphrase.data is not None:
            banphrase.data.num_uses += 1

        if banphrase.length == 0:
            return

        reason = f"Banned phrase {banphrase.id} ({banphrase.name})"

        # Finally, time out the user for whatever timeout length was required.
        await self.bot.timeout(member=user, duration=banphrase.length, reason=reason)

    def check_message(self, message):
        matched_banphrase = None
        for banphrase in self.enabled_banphrases:
            if banphrase.match(message):
                if not matched_banphrase:
                    matched_banphrase = banphrase
                    continue

                if banphrase.greater_than(matched_banphrase):
                    matched_banphrase = banphrase
                    continue

        return matched_banphrase or False

    def find_match(self, message, banphrase_id=None):
        match = None
        if banphrase_id is not None:
            match = find(
                lambda banphrase: banphrase.id == banphrase_id, self.banphrases
            )
        if match is None:
            match = find(
                lambda banphrase: banphrase.exact_match(message), self.banphrases
            )
        return match

    @staticmethod
    def parse_banphrase_arguments(message):
        parser = argparse.ArgumentParser()
        parser.add_argument("--length", dest="length", type=int)
        parser.add_argument("--time", dest="length", type=int)
        parser.add_argument("--duration", dest="length", type=int)
        parser.add_argument(
            "--casesensitive", dest="case_sensitive", action="store_true"
        )
        parser.add_argument(
            "--no-casesensitive", dest="case_sensitive", action="store_false"
        )
        parser.add_argument("--warning", dest="warning", action="store_true")
        parser.add_argument("--no-warning", dest="warning", action="store_false")
        parser.add_argument(
            "--removeaccents", dest="remove_accents", action="store_true"
        )
        parser.add_argument(
            "--no-removeaccents", dest="remove_accents", action="store_false"
        )
        parser.add_argument("--operator", dest="operator", type=str)
        parser.add_argument("--name", nargs="+", dest="name")
        parser.set_defaults(
            length=None,
            case_sensitive=None,
            warning=None,
            remove_accents=None,
            operator="contains",
        )

        try:
            args, unknown = parser.parse_known_args(message.split())
        except SystemExit:
            return False, False
        except:
            log.exception("Unhandled exception in add_command")
            return False, False

        # Strip options of any values that are set as None
        options = {k: v for k, v in vars(args).items() if v is not None}
        response = " ".join(unknown)

        if "name" in options:
            options["name"] = " ".join(options["name"])

        return options, response
