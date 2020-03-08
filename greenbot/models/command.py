import datetime
import json
import logging
import re

from sqlalchemy import INT, BOOLEAN, TEXT
from sqlalchemy import Column
from sqlalchemy import ForeignKey
from sqlalchemy.orm import reconstructor
from sqlalchemy.orm import relationship

from sqlalchemy_utc import UtcDateTime

import greenbot.utils
from greenbot.exc import FailedCommand
from greenbot.managers.db import DBManager, Base
from greenbot.managers.schedule import ScheduleManager
from greenbot.models.action import ActionParser
from greenbot.models.action import RawFuncAction
from greenbot.models.action import Substitution
from greenbot.models.user import User

log = logging.getLogger(__name__)


def parse_command_for_web(alias, command, list):
    import markdown
    from flask import Markup

    if command in list:
        return

    command.json_description = None
    command.parsed_description = ""

    try:
        if command.description is not None:
            command.json_description = json.loads(command.description)
            if "description" in command.json_description:
                command.parsed_description = Markup(
                    markdown.markdown(command.json_description["description"])
                )
            if command.json_description.get("hidden", False) is True:
                return
    except ValueError:
        # Invalid JSON
        pass
    except:
        log.warning(command.json_description)
        log.exception("Unhandled exception BabyRage")
        return

    if command.command is None:
        command.command = alias

    if command.action is not None and command.action.type == "multi":
        if command.command is not None:
            command.main_alias = command.command.split("|")[0]
        for inner_alias, inner_command in command.action.commands.items():
            parse_command_for_web(
                alias
                if command.command is None
                else command.main_alias + " " + inner_alias,
                inner_command,
                list,
            )
    else:
        test = re.compile(r"[^\w]")
        first_alias = command.command.split("|")[0]
        command.resolve_string = test.sub("", first_alias.replace(" ", "_"))
        command.main_alias = "!" + command._parent_command + first_alias
        if not command.parsed_description:
            if command.action is not None:
                if command.action.type == "message":
                    command.parsed_description = command.action.response
            if command.description is not None:
                command.parsed_description = command.description
        list.append(command)


class CommandData(Base):
    __tablename__ = "command_data"

    command_id = Column(
        INT,
        ForeignKey("command.id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
    )
    num_uses = Column(INT, nullable=False, default=0)
    added_by = Column(
        TEXT, ForeignKey("user.discord_id", ondelete="SET NULL"), nullable=True
    )
    edited_by = Column(
        TEXT, ForeignKey("user.discord_id", ondelete="SET NULL"), nullable=True
    )
    _last_date_used = Column(
        "last_date_used", UtcDateTime(), nullable=True, default=None
    )

    user = relationship(
        "User",
        primaryjoin="User.discord_id==CommandData.edited_by",
        foreign_keys="User.discord_id",
        uselist=False,
        cascade="",
        lazy="noload",
    )

    user2 = relationship(
        "User",
        primaryjoin="User.discord_id==CommandData.added_by",
        foreign_keys="User.discord_id",
        uselist=False,
        cascade="",
        lazy="noload",
    )

    def __init__(self, command_id, **options):
        self.command_id = command_id
        self.num_uses = 0
        self.added_by = None
        self.edited_by = None
        self._last_date_used = None

        self.set(**options)

    def set(self, **options):
        self.num_uses = options.get("num_uses", self.num_uses)
        self.added_by = options.get("added_by", self.added_by)
        self.edited_by = options.get("edited_by", self.edited_by)
        self._last_date_used = options.get("last_date_used", self._last_date_used)

    @property
    def last_date_used(self):
        if isinstance(self._last_date_used, datetime.datetime):
            return self._last_date_used

        return None

    @last_date_used.setter
    def last_date_used(self, value):
        self._last_date_used = value

    def jsonify(self):
        return {
            "num_uses": self.num_uses,
            "added_by": self.added_by,
            "edited_by": self.edited_by,
            "last_date_used": self.last_date_used.isoformat()
            if self.last_date_used
            else None,
        }


class CommandExample(Base):
    __tablename__ = "command_example"

    id = Column(INT, primary_key=True)
    command_id = Column(
        INT, ForeignKey("command.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(TEXT, nullable=False)
    chat = Column(TEXT, nullable=False)
    description = Column(TEXT, nullable=False)

    def __init__(self, command_id, title, chat="", description=""):
        self.id = None
        self.command_id = command_id
        self.title = title
        self.chat = chat
        self.description = description
        self.chat_messages = []

    @reconstructor
    def init_on_load(self):
        self.parse()

    def add_chat_message(self, type, message, user_from, user_to=None):
        chat_message = {
            "source": {"type": type, "from": user_from, "to": user_to},
            "message": message,
        }
        self.chat_messages.append(chat_message)

    def parse(self):
        self.chat_messages = []
        for line in self.chat.split("\n"):
            users, message = line.split(":", 1)
            if ">" in users:
                user_from, user_to = users.split(">", 1)
                self.add_chat_message("whisper", message, user_from, user_to=user_to)
            else:
                self.add_chat_message("say", message, users)
        return self

    def jsonify(self):
        return {
            "id": self.id,
            "command_id": self.command_id,
            "title": self.title,
            "description": self.description,
            "messages": self.chat_messages,
        }


class Command(Base):
    __tablename__ = "command"

    id = Column(INT, primary_key=True)
    level = Column(INT, nullable=False, default=100)
    action_json = Column("action", TEXT, nullable=False)
    extra_extra_args = Column("extra_args", TEXT)
    command = Column(TEXT, nullable=False)
    parent_command = Column(TEXT, nullable=False)
    description = Column(TEXT, nullable=True)
    delay_all = Column(INT, nullable=False, default=5)
    delay_user = Column(INT, nullable=False, default=15)
    enabled = Column(BOOLEAN, nullable=False, default=True)
    cost = Column(INT, nullable=False, default=0)
    can_execute_with_whisper = Column(BOOLEAN)
    long_description = ""
    channels = Column(TEXT, nullable=False, default="[]")
    data = relationship("CommandData", uselist=False, cascade="", lazy="joined")
    examples = relationship("CommandExample", uselist=True, cascade="", lazy="noload")

    BYPASS_DELAY_LEVEL = 1500

    DEFAULT_CD_ALL = 5
    DEFAULT_CD_USER = 15
    DEFAULT_LEVEL = 100

    notify_on_error = False

    def __init__(self, **options):
        self.id = options.get("id", None)

        self.level = Command.DEFAULT_LEVEL
        self.action = None
        self.extra_args = {"command": self}
        self.delay_all = Command.DEFAULT_CD_ALL
        self.delay_user = Command.DEFAULT_CD_USER
        self.description = None
        self.enabled = True
        self.type = "?"  # XXX: What is this?
        self.cost = 0
        self.can_execute_with_whisper = False
        self.run_through_banphrases = False
        self.command = None
        self.parent_command = None
        self.channels = "[]"

        self.last_run = 0
        self.last_run_by_user = {}

        self.data = None
        self.run_in_thread = False
        self.notify_on_error = False

        self.set(**options)

    def set(self, **options):
        self.level = options.get("level", self.level)
        if "action" in options:
            self.action_json = json.dumps(options["action"])
            self.action = ActionParser.parse(self.action_json)
        if "extra_args" in options:
            self.extra_args = {"command": self}
            self.extra_args.update(options["extra_args"])
            self.extra_extra_args = json.dumps(options["extra_args"])
        self.command = options.get("command", self.command)
        self.parent_command = options.get("parent_command", self.parent_command)
        self.description = options.get("description", self.description)
        self.delay_all = options.get("delay_all", self.delay_all)
        if self.delay_all < 0:
            self.delay_all = 0
        self.delay_user = options.get("delay_user", self.delay_user)
        if self.delay_user < 0:
            self.delay_user = 0
        self.enabled = options.get("enabled", self.enabled)
        self.cost = int(self.cost)
        self.cost = options.get("cost", self.cost)
        self.channels = options.get("channels", self.channels)
        if self.cost < 0:
            self.cost = 0
        self.can_execute_with_whisper = options.get(
            "can_execute_with_whisper", self.can_execute_with_whisper
        )
        self.examples = options.get("examples", self.examples)
        self.run_in_thread = options.get("run_in_thread", self.run_in_thread)
        self.notify_on_error = options.get("notify_on_error", self.notify_on_error)

    def __str__(self):
        return f"Command(!{self._parent_command}{self.command})"

    @property
    def _parent_command(self):
        return self.parent_command + " " if self.parent_command else ""

    @property
    def channels_web(self):
        return " ".join(json.loads(self.channels))

    @reconstructor
    def init_on_load(self):
        self.last_run = 0
        self.last_run_by_user = {}
        self.extra_args = {"command": self}
        self.action = ActionParser.parse(self.action_json)
        self.run_in_thread = False
        if self.extra_extra_args:
            try:
                self.extra_args.update(json.loads(self.extra_extra_args))
            except:
                log.exception(
                    f"Unhandled exception caught while loading Command extra arguments ({self.extra_extra_args})"
                )

    @classmethod
    def from_json(cls, json_object):
        cmd = cls()
        if "level" in json_object:
            cmd.level = json_object["level"]
        cmd.action = ActionParser.parse(data=json_object["action"])
        return cmd

    @classmethod
    def dispatch_command(cls, cb, **options):
        cmd = cls(**options)
        cmd.action = ActionParser.parse('{"type": "func", "cb": "' + cb + '"}')
        return cmd

    @classmethod
    def raw_command(cls, cb, **options):
        cmd = cls(**options)
        try:
            cmd.action = RawFuncAction(cb)
        except:
            log.exception(
                "Uncaught exception in Command.raw_command. catch the following exception manually!"
            )
            cmd.enabled = False
        return cmd

    @classmethod
    def greenbot_command(cls, bot, method_name, level=1000, **options):
        cmd = cls(**options)
        cmd.level = level
        cmd.description = options.get("description", None)
        cmd.can_execute_with_whisper = True
        try:
            cmd.action = RawFuncAction(getattr(bot, method_name))
        except:
            pass
        return cmd

    @classmethod
    def multiaction_command(cls, default=None, fallback=None, **options):
        from greenbot.models.action import MultiAction

        cmd = cls(**options)
        cmd.action = MultiAction.ready_built(
            options.get("commands"), default=default, fallback=fallback
        )
        return cmd

    def load_args(self, level, action):
        self.level = level
        self.action = action

    def is_enabled(self):
        return self.enabled == 1 and self.action is not None

    async def run(self, bot, author, channel, message, args):
        if self.action is None:
            log.warning("This command is not available.")
            return False

        if args["user_level"] < self.level:
            # User does not have a high enough power level to run this command
            return False

        if args["whisper"] and self.can_execute_with_whisper is False:
            # This user cannot execute the command through a whisper
            return False

        cd_modifier = 0.2 if args["user_level"] >= 500 else 1.0
        load_channels = json.loads(self.channels)
        if channel and str(channel.id) not in load_channels and len(load_channels) > 0:
            return False

        cur_time = greenbot.utils.now().timestamp()
        time_since_last_run = (cur_time - self.last_run) / cd_modifier

        if (
            time_since_last_run < self.delay_all
            and args["user_level"] < Command.BYPASS_DELAY_LEVEL
        ):
            await bot.private_message(user=author, message=f"The command **{self.command}** was executed too recently please try again in {greenbot.utils.seconds_to_resp(int(self.delay_all-time_since_last_run))}", ignore_escape=True)
            return False

        time_since_last_run_user = (
            cur_time - self.last_run_by_user.get(str(author.id), 0)
        ) / cd_modifier

        if (
            time_since_last_run_user < self.delay_user
            and args["user_level"] < Command.BYPASS_DELAY_LEVEL
        ):
            await bot.private_message(user=author, message=f"You executed the command **{self.command}** too recently please try again in {greenbot.utils.seconds_to_resp(int(self.delay_user-time_since_last_run_user))}", ignore_escape=True)
            return False
        with DBManager.create_session_scope() as db_session:
            user = User._create_or_get_by_discord_id(
                db_session, str(author.id), str(author)
            )
            if self.cost > 0 and not user.can_afford(self.cost) and args["user_level"] < Command.BYPASS_DELAY_LEVEL:
                # User does not have enough points to use the command
                await bot.private_message(user=author, message=f"You need {self.cost} points to execute that command", ignore_escape=True)
                return False

            args.update(self.extra_args)
            if self.run_in_thread:
                log.debug(f"Running {self} in a thread")
                await ScheduleManager.execute_now(
                    self.run_action, args=[bot, author, channel, message, args]
                )
            else:
                await self.run_action(bot, author, channel, message, args)

        return True

    async def run_action(self, bot, author, channel, message, args):
        cur_time = greenbot.utils.now().timestamp()
        with DBManager.create_session_scope() as db_session:
            user = User._create_or_get_by_discord_id(
                db_session, str(author.id), str(author)
            )
            with user.spend_currency_context(self.cost if args["user_level"] < Command.BYPASS_DELAY_LEVEL else 0):
                ret = await self.action.run(bot, author, channel, message, args)
                if not ret:
                    raise FailedCommand("return currency")

                # Only spend points, and increment num_uses if the action succeded
                if self.data is not None:
                    self.data.num_uses += 1
                    self.data.last_date_used = greenbot.utils.now()

                # TODO: Will this be an issue?
                self.last_run = cur_time
                self.last_run_by_user[args["user_level"]] = cur_time

                if ret == "return currency":
                    db_session.commit()
                    raise FailedCommand("return currency")

    def jsonify(self):
        """ jsonify will only be called from the web interface.
        we assume that commands have been run throug the parse_command_for_web method """
        payload = {
            "id": self.id,
            "level": self.level,
            "main_alias": self.main_alias,
            "parent_command": self.parent_command,
            "aliases": self.command.split("|"),
            "description": self.description,
            "channels": self.channels,
            "long_description": self.long_description,
            "cd_all": self.delay_all,
            "cd_user": self.delay_user,
            "enabled": self.enabled,
            "cost": self.cost,
            "can_execute_with_whisper": self.can_execute_with_whisper,
            "resolve_string": self.resolve_string,
        }

        if self.data:
            payload["data"] = self.data.jsonify()
        else:
            payload["data"] = None

        return payload
