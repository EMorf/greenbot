import logging

from greenbot.managers.db import DBManager
from greenbot.models.command import Command
from greenbot.models.command import CommandExample
from greenbot.models.module import Module
from greenbot.models.user import User
from greenbot.modules import BaseModule
from greenbot.modules import ModuleType
from greenbot.modules.basic import BasicCommandsModule
from greenbot.utils import split_into_chunks_with_prefix

from sqlalchemy import text

log = logging.getLogger(__name__)


class AdminCommandsModule(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "Basic admin commands"
    DESCRIPTION = "All miscellaneous admin commands"
    CATEGORY = "Feature"
    ENABLED_DEFAULT = True
    MODULE_TYPE = ModuleType.TYPE_ALWAYS_ENABLED
    PARENT_MODULE = BasicCommandsModule

    @staticmethod
    def cmd_module(bot, author, channel, message, whisper, args):
        module_manager = bot.module_manager

        if not message:
            return

        msg_args = message.split(" ")
        if len(msg_args) < 1:
            return

        sub_command = msg_args[0].lower()

        if sub_command == "list":
            messages = split_into_chunks_with_prefix(
                [{"prefix": "Available modules:", "parts": [module.ID for module in module_manager.all_modules]}],
                " ",
                default="No modules available.",
            )

            for message in messages:
                if whisper:
                    bot.private_message(author, message)
                    continue
                bot.say(channel, message)
        elif sub_command == "disable":
            if len(msg_args) < 2:
                return
            module_id = msg_args[1].lower()

            module = module_manager.get_module(module_id)
            if not module:
                if whisper:
                    bot.private_message(author, f"No module with the id {module_id} found")
                    return
                bot.say(channel, f"No module with the id {module_id} found")
                return

            if module.MODULE_TYPE > ModuleType.TYPE_NORMAL:
                if whisper:
                    bot.private_message(author, f"Unable to disable module {module_id}")
                    return
                bot.say(channel, f"Unable to disable module {module_id}")
                return

            if not module_manager.disable_module(module_id):
                if whisper:
                    bot.private_message(author, f"Unable to disable module {module_id}, maybe it's not enabled?")
                    return
                bot.say(channel, f"Unable to disable module {module_id}, maybe it's not enabled?")
                return

            # Rebuild command cache
            bot.commands.rebuild()

            with DBManager.create_session_scope() as db_session:
                db_module = db_session.query(Module).filter_by(id=module_id).one()
                db_module.enabled = False

            # AdminLogManager.post("Module toggled", source, "Disabled", module_id)
            if whisper:
                bot.private_message(author, f"Disabled module {module_id}")
                return

            bot.say(channel, f"Disabled module {module_id}")

        elif sub_command == "enable":
            if len(msg_args) < 2:
                return
            module_id = msg_args[1].lower()

            module = module_manager.get_module(module_id)
            if not module:
                if whisper:
                    bot.private_message(author, f"No module with the id {module_id} found")
                    return
                bot.say(channel, f"No module with the id {module_id} found")
                return

            if module.MODULE_TYPE > ModuleType.TYPE_NORMAL:
                if whisper:
                    bot.private_message(author, f"Unable to enable module {module_id}")
                    return
                bot.say(channel, f"Unable to enable module {module_id}")
                return

            if not module_manager.enable_module(module_id):
                if whisper:
                    bot.private_message(author, f"Unable to enable module {module_id}, maybe it's already enabled?")
                    return
                bot.say(channel, f"Unable to enable module {module_id}, maybe it's already enabled?")
                return

            # Rebuild command cache
            bot.commands.rebuild()

            with DBManager.create_session_scope() as db_session:
                db_module = db_session.query(Module).filter_by(id=module_id).one()
                db_module.enabled = True

            # AdminLogManager.post("Module toggled", source, "Enabled", module_id)

            if whisper:
                bot.private_message(author, "Enabled module {module_id}")
                return
            bot.say(channel, "Enabled module {module_id}")

    def load_commands(self, **options):
        self.commands["module"] = Command.raw_command(
            self.cmd_module, level=500, description="Modify module", delay_all=0, delay_user=0
        )
