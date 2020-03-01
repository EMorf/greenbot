import collections
import json
import logging
import sys

import regex as re
import requests
import discord

from greenbot.managers.schedule import ScheduleManager

log = logging.getLogger(__name__)


class ActionParser:
    bot = None

    @staticmethod
    def parse(raw_data=None, data=None):
        from greenbot.dispatch import Dispatch

        if not data:
            data = json.loads(raw_data)
        if data["type"] == "reply":
            action = ReplyAction(
                data["message"], ActionParser.bot, functions=data.get("functions", "")
            )
        elif data["type"] == "privatemessage":
            action = PrivateMessageAction(
                data["message"], ActionParser.bot, functions=data.get("functions", "")
            )
        elif data["type"] == "func":
            action = FuncAction(getattr(Dispatch, data["cb"]))
        elif data["type"] == "multi":
            action = MultiAction(data["args"], data["default"])
        else:
            raise Exception(f"Unknown action type: {data['type']}")
        return action


class Function:
    function_regex = re.compile(
        r"(?<!\\)\$\((\w+);\[((((\"([^\"]|\\[\$\"])*\")|(\d+)),?\s?)*)\]\)"
    )

    args_sub_regex = re.compile(r"\"([^\"]*)\"|(?:(?<=,)|^)")

    @staticmethod
    async def run_functions(_input, args, extra, author, channel, private_message, bot):
        _input = list(Substitution.apply_subs(_input, args, extra))[0]
        for sub_key in Function.function_regex.finditer(_input):
            func_name = sub_key.group(1)
            args = sub_key.group(2)
            array_args = []
            for arg in Substitution.args_sub_regex.finditer(args):
                array_args.append(arg.group(1))
            if func_name not in MappingMethods.func_methods():
                log.error(f"function {func_name} not found!")
                continue

            resp, embed = await MappingMethods.func_methods()[func_name](
                array_args, extra
            )
            if private_message:
                await bot.private_message(user=author, message=resp, embed=embed)
            else:
                await bot.say(channel=channel, message=resp, embed=embed)


class Substitution:
    substitution_regex = re.compile(
        r"(?<!\\)\$\((\w+);\[((((\"([^\"]|\\[\$\"])*\")|(\d+)),?)*)\]:(\w*)\)"
    )

    args_sub_regex = re.compile(r"\"([^\"]*)\"|(?:(?<=,)|^)")

    user_args_sub_regex = re.compile(r"(?<!\\)\$\((\d+)(\+?)\)")

    @staticmethod
    def apply_subs(_input, args, extra):
        count = 0
        embeds = []
        log.info(_input)
        for user_sub_key in Substitution.user_args_sub_regex.finditer(_input):
            needle = user_sub_key.group(0)
            index = int(user_sub_key.group(1)) - 1
            additions = user_sub_key.group(2)
            _input = _input.replace(
                needle,
                (
                    " ".join(args[index:])
                    if additions
                    else args[index]
                    if len(args) >= index + 1
                    else ""
                ),
                1,
            )
            count += 1

        for sub_key in Substitution.substitution_regex.finditer(_input):
            needle = sub_key.group(0)
            filter_name = sub_key.group(1)
            args = sub_key.group(2)
            key = sub_key.group(8)
            array_args = []
            for arg in Substitution.args_sub_regex.finditer(args):
                array_args.append(
                    list(Substitution.apply_subs(arg.group(1) if arg.group(1) else "", args, extra))[0]
                )

            final_sub = needle
            if filter_name in MappingMethods.subs_methods():
                log.info(filter_name)
                resp, embed = MappingMethods.subs_methods()[filter_name](args=array_args, key=key, extra=extra)
                if embed != None:
                    embeds.append(embed)
                final_sub = resp
            _input = _input.replace(needle, str(final_sub), 1)
            count += 1
        if count > 0:
            _input, embeds_ = Substitution.apply_subs(_input, args, extra)
            embeds += embeds_
        return _input, embeds


class MappingMethods:
    bot = None

    @staticmethod
    def init(bot):
        MappingMethods.bot = bot

    @staticmethod
    def subs_methods():
        method_mapping = {}
        bot = MappingMethods.bot
        try:
            method_mapping["role"] = bot.filters.get_role if bot else None
            method_mapping["_role"] = bot.filters.get_role_value if bot else None
            method_mapping["_member"] = bot.filters.get_member if bot else None
            method_mapping["member"] = bot.filters.get_member_value if bot else None
            method_mapping["currency"] = bot.filters.get_currency if bot else None
            method_mapping["user"] = bot.filters.get_user if bot else None
            method_mapping["userinfo"] = bot.filters.get_user_info if bot else None
            method_mapping["roleinfo"] = bot.filters.get_role_info if bot else None
            method_mapping["commands"] = bot.filters.get_commands if bot else None
            method_mapping["commandinfo"] = (
                bot.filters.get_command_info if bot else None
            )
            method_mapping["time"] = bot.filters.get_time_value if bot else None
            method_mapping["command"] = bot.filters.get_command_value if bot else None
            method_mapping["author"] = bot.filters.get_author_value if bot else None
            method_mapping["_channel"] = bot.filters.get_channel_value if bot else None
            method_mapping["channel"] = bot.filters.get_channel if bot else None
        except AttributeError:
            pass
        return method_mapping

    @staticmethod
    def func_methods():
        method_mapping = {}
        bot = MappingMethods.bot
        try:
            method_mapping["kick"] = bot.functions.func_kick_member if bot else None
            method_mapping["ban"] = bot.functions.func_ban_member if bot else None
            method_mapping["unban"] = bot.functions.func_unban_member if bot else None
            method_mapping["addrole"] = (
                bot.functions.func_add_role_member if bot else None
            )
            method_mapping["removerole"] = (
                bot.functions.func_remove_role_member if bot else None
            )
            method_mapping["level"] = bot.functions.func_level if bot else None
            method_mapping["setpoints"] = (
                bot.functions.func_set_balance if bot else None
            )
            method_mapping["adjpoints"] = (
                bot.functions.func_adj_balance if bot else None
            )
            method_mapping["output"] = bot.functions.func_output if bot else None
            method_mapping["embed"] = bot.functions.func_embed_image if bot else None
        except AttributeError:
            pass
        return method_mapping


class BaseAction:
    type = None
    subtype = None

    def reset(self):
        pass


class FuncAction(BaseAction):
    type = "func"

    def __init__(self, cb):
        self.cb = cb

    async def run(self, bot, author, channel, message, args):
        try:
            return await self.cb(
                bot=bot, author=author, channel=channel, message=message, args=args
            )
        except:
            log.exception("Uncaught exception in FuncAction")


class RawFuncAction(BaseAction):
    type = "rawfunc"

    def __init__(self, cb):
        self.cb = cb

    async def run(self, bot, author, channel, message, args):
        return await self.cb(
            bot=bot, author=author, channel=channel, message=message, args=args
        )


class MultiAction(BaseAction):
    type = "multi"

    def __init__(self, args, default=None, fallback=None):
        from greenbot.models.command import Command

        self.commands = {}
        self.default = default
        self.fallback = fallback

        for command in args:
            cmd = Command.from_json(command)
            for alias in command["command"].split("|"):
                if alias not in self.commands:
                    self.commands[alias] = cmd
                else:
                    log.error(f"Alias {alias} for this multiaction is already in use.")

        import copy

        self.original_commands = copy.copy(self.commands)

    def reset(self):
        import copy

        self.commands = copy.copy(self.original_commands)

    def __iadd__(self, other):
        if other is not None and other.type == "multi":
            self.commands.update(other.commands)
        return self

    @classmethod
    def ready_built(cls, commands, default=None, fallback=None):
        """ Useful if you already have a dictionary
        with commands pre-built.
        """

        multiaction = cls(args=[], default=default, fallback=fallback)
        multiaction.commands = commands
        import copy

        multiaction.original_commands = copy.copy(commands)
        return multiaction

    async def run(self, bot, author, channel, message, args):
        """ If there is more text sent to the multicommand after the
        initial alias, we _ALWAYS_ assume it's trying the subaction command.
        If the extra text was not a valid command, we try to run the fallback command.
        In case there's no extra text sent, we will try to run the default command.
        """

        cmd = None
        if message:
            msg_lower_parts = message.lower().split(" ")
            command = msg_lower_parts[0]
            cmd = self.commands.get(command, None)
            extra_msg = " ".join(message.split(" ")[1:])
            if cmd is None and self.fallback:
                cmd = self.commands.get(self.fallback, None)
                extra_msg = message
        elif self.default:
            command = self.default
            cmd = self.commands.get(command, None)
            extra_msg = None

        if cmd:
            if args["user_level"] >= cmd.level:
                return await cmd.run(bot, author, channel, extra_msg, args)

            log.info(
                f"User {author} tried running a sub-command he had no access to ({command})."
            )

        return None


class MessageAction(BaseAction):
    type = "message"

    def __init__(self, response, bot, functions=""):
        self.response = response
        self.functions = functions

    def get_response(self, bot, extra):
        MappingMethods.init(bot)
        if not self.response:
            return None, None
        
        return Substitution.apply_subs(
            self.response, extra["message"].split(" "), extra
        )

    @staticmethod
    def get_extra_data(author, channel, message, args):
        return {"author": author, "channel": channel, "message": message, **args}

    async def run(self, bot, author, channel, message, args):
        raise NotImplementedError("Please implement the run method.")


class ReplyAction(MessageAction):
    subtype = "Reply"

    async def run(self, bot, author, channel, message, args):
        extra = self.get_extra_data(author, channel, message, args)
        MappingMethods.init(bot)
        await Function.run_functions(
            self.functions,
            extra["message"].split(" "),
            extra,
            author,
            channel,
            args["whisper"],
            bot,
        )

        resp, embeds = self.get_response(bot, extra)
        if not resp and not embeds:
            return False

        messages = [await bot.private_message(author, resp) if args["whisper"] else await bot.say(channel, resp)]
        for embed in embeds:
            messages.append(await bot.private_message(author, embed=embed) if args["whisper"] else await bot.say(channel, embed=embed))
        return messages

class PrivateMessageAction(MessageAction):
    subtype = "Private Message"

    async def run(self, bot, author, channel, message, args):
        extra = self.get_extra_data(author, channel, message, args)
        MappingMethods.init(bot)
        await Function.run_functions(
            self.functions,
            extra["message"].split(" "),
            extra,
            author,
            channel,
            args["whisper"],
            bot,
        )

        resp, embeds = self.get_response(bot, extra)
        if not resp and not embeds:
            return False

        messages = [await bot.private_message(author, resp)]
        for embed in embeds:
            messages.append(await bot.private_message(author, embed=embed))
        return messages
