import logging
import re

# from greenbot.managers.adminlog import AdminLogManager
from greenbot.managers.db import DBManager
from greenbot.models.user import User

log = logging.getLogger(__name__)


class Dispatch:
    """
    Methods in this class accessible from commands
    """

    @staticmethod
    def add_command(bot, user_id, message, whisper, args):
        """Dispatch method for creating commands.
        Usage: !add command ALIAS [options] RESPONSE
        See greenbot/managers/command.py parse_command_arguments for available options
        """

        if not message:
            return False

        # Make sure we got both an alias and a response
        message_parts = message.split()
        if len(message_parts) < 2:
            bot.private_message(user_id, "Usage: !add command ALIAS [options] RESPONSE")
            return False

        options, response = bot.commands.parse_command_arguments(message_parts[1:])

        if options is False:
            bot.private_message(user_id, "Invalid command")
            return False

        options["added_by"] = user_id

        alias_str = message_parts[0].replace("!", "").lower()
        type = "channelmessage"
        if options["privatemessage"] is True:
            type = "privatemessage"
        elif options["channelmessage"] is True:
            type = "channelmessage"
        elif options["whisper"] is False or options["reply"] is False:
            type = "channelmessage"
        action = {"type": type, "message": response}

        add_role_id = options.get("addrole_name", None)
        remove_role_id = options.get("removerole_names", None)

        del options["addrole_name"]
        del options["removerole_names"]

        options["add_role_id"] = bot.get_role_id(add_role_id) if add_role_id else None
        options["remove_role_id"] = bot.get_role_id(remove_role_id) if remove_role_id else None

        options.po

        command, new_command, alias_matched = bot.commands.create_command(alias_str, action=action, **options)
        if new_command is True:
            bot.private_message(user_id, f"Added your command (ID: {command.id})")

            log_msg = f"The !{command.command.split('|')[0]} command has been created"
            # AdminLogManager.add_entry("Command created", user_id, log_msg)
            return True

        # At least one alias is already in use, notify the user to use !edit command instead
        bot.private_message(
            user_id,
            f"The alias {alias_matched} is already in use. To edit that command, use !edit command instead of !add command.",
        )
        return False

    @staticmethod
    def edit_command(bot, user_id, message, event, args):
        """Dispatch method for editing commands.
        Usage: !edit command ALIAS [options] RESPONSE
        See greenbot/managers/command.py parse_command_arguments for available options
        """

        if message:
            # Make sure we got both an alias and a response
            message_parts = message.split()
            if len(message_parts) < 2:
                bot.private_message(user_id, "Usage: !add command ALIAS [options] RESPONSE")
                return False

            options, response = bot.commands.parse_command_arguments(message_parts[1:])

            options["edited_by"] = user_id

            if options is False:
                bot.whisper(user_id, "Invalid command")
                return False

            alias = message_parts[0].replace("!", "").lower()
            type = "say"
            if options["whisper"] is True:
                type = "whisper"
            elif options["reply"] is True:
                type = "reply"
            elif response.startswith("/me") or response.startswith(".me"):
                type = "me"
                response = " ".join(response.split(" ")[1:])
            elif options["whisper"] is False or options["reply"] is False:
                type = "say"
            action = {"type": type, "message": response}

            command = bot.commands.get(alias, None)

            if command is None:
                bot.private_message(
                    user_id,
                    f"No command found with the alias {alias}. Did you mean to create the command? If so, use !add command instead.",
                )
                return False

            old_message = ""
            new_message = ""

            if len(action["message"]) > 0:
                options["action"] = action
                old_message = command.action.response
                new_message = action["message"]
            elif not type == command.action.subtype:
                options["action"] = {"type": type, "message": command.action.response}
            bot.commands.edit_command(command, **options)
            bot.private_message(user_id, f"Updated the command (ID: {command.id})")

            if len(new_message) > 0:
                log_msg = f'The !{command.command.split("|")[0]} command has been updated from "{old_message}" to "{new_message}"'
            else:
                log_msg = f"The !{command.command.split('|')[0]} command has been updated"

            # AdminLogManager.add_entry(
                # "Command edited", user_id, log_msg, data={"old_message": old_message, "new_message": new_message}
            # )

    @staticmethod
    def add_funccommand(bot, user_id, message, event, args):
        """Dispatch method for creating function commands.
        Usage: !add funccommand ALIAS [options] CALLBACK
        See greenbot/managers/command.py parse_command_arguments for available options
        """

        if message:
            # Make sure we got both an alias and a response
            message_parts = message.split(" ")
            if len(message_parts) < 2:
                bot.whisper(user_id, "Usage: !add funccommand ALIAS [options] CALLBACK")
                return False

            options, response = bot.commands.parse_command_arguments(message_parts[1:])

            options["added_by"] = user_id

            if options is False:
                bot.whisper(user_id, "Invalid command")
                return False

            alias_str = message_parts[0].replace("!", "").lower()
            action = {"type": "func", "cb": response.strip()}

            command, new_command, alias_matched = bot.commands.create_command(alias_str, action=action, **options)
            if new_command is True:
                bot.whisper(user_id, f"Added your command (ID: {command.id})")
                return True

            # At least one alias is already in use, notify the user to use !edit command instead
            bot.whisper(
                user_id,
                f"The alias {alias_matched} is already in use. To edit that command, use !edit command instead of !add funccommand.",
            )
            return False

    @staticmethod
    def edit_funccommand(bot, user_id, message, event, args):
        """Dispatch method for editing function commands.
        Usage: !edit funccommand ALIAS [options] CALLBACK
        See greenbot/managers/command.py parse_command_arguments for available options
        """

        if message:
            # Make sure we got both an alias and a response
            message_parts = message.split(" ")
            if len(message_parts) < 2:
                bot.whisper(user_id, "Usage: !add funccommand ALIAS [options] CALLBACK")
                return False

            options, response = bot.commands.parse_command_arguments(message_parts[1:])

            options["edited_by"] = user_id

            if options is False:
                bot.whisper(user_id, "Invalid command")
                return False

            alias = message_parts[0].replace("!", "").lower()
            action = {"type": "func", "cb": response.strip()}

            command = bot.commands.get(alias, None)

            if command is None:
                bot.whisper(
                    user_id,
                    f"No command found with the alias {alias}. Did you mean to create the command? If so, use !add funccommand instead.",
                )
                return False

            if len(action["cb"]) > 0:
                options["action"] = action
            bot.commands.edit_command(command, **options)
            bot.whisper(user_id, f"Updated the command (ID: {command.id})")

    @staticmethod
    def add_alias(bot, user_id, message, event, args):
        """Dispatch method for adding aliases to already-existing commands.
        Usage: !add alias EXISTING_ALIAS NEW_ALIAS_1 NEW_ALIAS_2 ...
        """

        if message:
            message = message.replace("!", "").lower()
            # Make sure we got both an existing alias and at least one new alias
            message_parts = message.split()
            if len(message_parts) < 2:
                bot.private_message(user_id, "Usage: !add alias existingalias newalias")
                return False

            existing_alias = message_parts[0]
            new_aliases = re.split(r"\|| ", " ".join(message_parts[1:]))
            added_aliases = []
            already_used_aliases = []

            if existing_alias not in bot.commands:
                bot.private_message(user_id, f'No command called "{existing_alias}" found')
                return False

            command = bot.commands[existing_alias]

            # error out on commands that are not from the DB, e.g. module commands like !8ball that cannot have
            # aliases registered. (command.command and command.data are None on those commands)
            if command.data is None or command.command is None:
                bot.private_message(user_id, "That command cannot have aliases added to.")
                return False

            for alias in set(new_aliases):
                if alias in bot.commands:
                    already_used_aliases.append(alias)
                else:
                    added_aliases.append(alias)
                    bot.commands[alias] = command

            if len(added_aliases) > 0:
                new_aliases = f"{command.command}|{'|'.join(added_aliases)}"
                bot.commands.edit_command(command, command=new_aliases)

                bot.private_message(user_id, f"Successfully added the aliases {', '.join(added_aliases)} to {existing_alias}")
                log_msg = f"The aliases {', '.join(added_aliases)} has been added to {existing_alias}"
                # AdminLogManager.add_entry("Alias added", user_id, log_msg)
            if len(already_used_aliases) > 0:
                bot.private_message(user_id, f"The following aliases were already in use: {', '.join(already_used_aliases)}")
        else:
            bot.private_message(user_id, "Usage: !add alias existingalias newalias")

    @staticmethod
    def remove_alias(bot, user_id, message, event, args):
        """Dispatch method for removing aliases from a command.
        Usage: !remove alias EXISTING_ALIAS_1 EXISTING_ALIAS_2"""
        if message:
            aliases = re.split(r"\|| ", message.lower())
            log.info(aliases)
            if len(aliases) < 1:
                bot.private_message(user_id, "Usage: !remove alias EXISTINGALIAS")
                return False

            num_removed = 0
            commands_not_found = []
            for alias in aliases:
                if alias not in bot.commands:
                    commands_not_found.append(alias)
                    continue

                command = bot.commands[alias]

                # error out on commands that are not from the DB, e.g. module commands like !8ball that cannot have
                # aliases registered. (command.command and command.data are None on those commands)
                if command.data is None or command.command is None:
                    bot.private_message(user_id, "That command cannot have aliases removed from.")
                    return False

                current_aliases = command.command.split("|")
                current_aliases.remove(alias)

                if len(current_aliases) == 0:
                    bot.private_message(user_id, f"{alias} is the only remaining alias for this command and can't be removed.")
                    continue

                new_aliases = "|".join(current_aliases)
                bot.commands.edit_command(command, command=new_aliases)

                num_removed += 1
                del bot.commands[alias]
                log_msg = f"The alias {alias} has been removed from {new_aliases.split('|')[0]}"
                # AdminLogManager.add_entry("Alias removed", user_id, log_msg)

            whisper_str = ""
            if num_removed > 0:
                whisper_str = f"Successfully removed {num_removed} aliases."
            if len(commands_not_found) > 0:
                whisper_str += f" Aliases {', '.join(commands_not_found)} not found"
            if len(whisper_str) > 0:
                bot.whisper(user_id, whisper_str)
        else:
            bot.private_message(user_id, "Usage: !remove alias EXISTINGALIAS")

    @staticmethod
    def remove_command(bot, user_id, message, event, args):
        if message:
            id = None
            command = None
            try:
                id = int(message)
            except Exception:
                pass

            if id is None:
                potential_cmd = "".join(message.split(" ")[:1]).lower().replace("!", "")
                if potential_cmd in bot.commands:
                    command = bot.commands[potential_cmd]
            else:
                for key, check_command in bot.commands.items():
                    if check_command.id == id:
                        command = check_command
                        break

            if command is None:
                bot.private_message(user_id, "No command with the given parameters found")
                return False

            if command.id == -1:
                bot.private_message(user_id, "That command is an internal command, it cannot be removed.")
                return False

            if user_id.level < 2000:
                if command.action is not None and not command.action.type == "message":
                    bot.private_message(user_id, "That command is not a normal command, it cannot be removed by you.")
                    return False

            bot.private_message(user_id, f"Successfully removed command with id {command.id}")
            log_msg = f"The !{command.command.split('|')[0]} command has been removed"
            # AdminLogManager.add_entry("Command removed", user_id, log_msg)
            bot.commands.remove_command(command)
        else:
            bot.private_message(user_id, "Usage: !remove command (COMMAND_ID|COMMAND_ALIAS)")