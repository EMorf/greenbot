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
    def parse(raw_data=None, data=None, command=""):
        from greenbot.dispatch import Dispatch

        if not data:
            data = json.loads(raw_data)
        if data["type"] == "reply":
            action = ReplyAction(
                data["message"], ActionParser.bot, functions=data.get("functions", [])
            )
        elif data["type"] == "privatemessage":
            action = PrivateMessageAction(
                data["message"], ActionParser.bot, functions=data.get("functions", [])
            )
        elif data["type"] == "func":
            action = FuncAction(getattr(Dispatch, data["cb"]))
        elif data["type"] == "multi":
            action = MultiAction(data["args"], data["default"])
        else:
            raise Exception(f"Unknown action type: {data['type']}")
        return action


def apply_substitutions(text, substitutions, bot, extra):
    embed = None
    for needle, sub in substitutions.items():
        if sub.key and sub.argument:
            param = sub.key
            extra["argument"] = MessageAction.get_argument_value(
                extra["message"], sub.argument - 1
            )
        elif sub.key:
            param = sub.key
        elif sub.argument:
            param = MessageAction.get_argument_value(extra["message"], sub.argument - 1)
        else:
            param = None
        value = sub.cb(param, extra)
        if isinstance(value, discord.embeds.Embed):
            text = text.replace(needle, "")
            embed = value
            continue
        if value is None:
            return None
        try:
            for f in sub.filters:
                value = bot.apply_filter(value, f)
        except:
            log.exception("Exception caught in filter application")
        if value is None:
            return None
        text = text.replace(needle, str(value))

    return text, embed


class Function:
    function_regex = re.compile(r"\$\(([a-z_]+)(;\$\(\w+(;\d+)?(:\w+)?\)|;\w+)*\)")
    args_regex = re.compile(r"(;\$\(\w+(;\d)?(:\w+)?\)|;\w+)")

    def __init__(self, cb, arguments=[]):
        self.cb = cb
        self.arguments = arguments


class Substitution:
    argument_substitution_regex = re.compile(r"\$\((\d+)\)")
    substitution_regex = re.compile(
        r'\$\(([a-z_]+)(\;[0-9]+)?(\:[\w\.\/ -]+|\:\$\([\w_:;\._\/ -]+\))?(\|[\w]+(\([\w%:/ +-]+\))?)*(\,[\'"]{1}[\w \|$;_\-:()\.]+[\'"]{1}){0,2}\)'
    )
    # https://stackoverflow.com/a/7109208
    urlfetch_substitution_regex = re.compile(
        r"\$\(urlfetch ([A-Za-z0-9\-._~:/?#\[\]@!$%&\'()*+,;=]+)\)"
    )
    urlfetch_substitution_regex_all = re.compile(r"\$\(urlfetch (.+?)\)")

    def __init__(self, cb, needle, key=None, argument=None, filters=[]):
        self.cb = cb
        self.key = key
        self.argument = argument
        self.filters = filters
        self.needle = needle


class SubstitutionFilter:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments


class BaseAction:
    type = None
    subtype = None

    def reset(self):
        pass


class FuncAction(BaseAction):
    type = "func"

    def __init__(self, cb):
        self.cb = cb

    def run(self, bot, author, channel, message, args):
        try:
            return self.cb(
                bot=bot, author=author, channel=channel, message=message, args=args
            )
        except:
            log.exception("Uncaught exception in FuncAction")


class RawFuncAction(BaseAction):
    type = "rawfunc"

    def __init__(self, cb):
        self.cb = cb

    def run(self, bot, author, channel, message, args):
        return self.cb(
            bot=bot, author=author, channel=channel, message=message, args=args
        )


def get_argument_substitutions(string):
    """
    Returns a list of `Substitution` objects that are found in the passed `string`.
    Will not return multiple `Substitution` objects for the same number.
    This means string "$(1) $(1) $(2)" will only return two Substitutions.
    """

    argument_substitutions = []

    for sub_key in Substitution.argument_substitution_regex.finditer(string):
        needle = sub_key.group(0)
        argument_num = int(sub_key.group(1))

        found = False
        for sub in argument_substitutions:
            if sub.argument == argument_num:
                # We already matched this argument variable
                found = True
                break
        if found:
            continue
        argument_substitutions.append(
            Substitution(None, needle=needle, argument=argument_num)
        )

    return argument_substitutions


def get_substitution_arguments(sub_key):
    sub_string = sub_key.group(0)
    path = sub_key.group(1)
    argument = sub_key.group(2)
    if argument is not None:
        argument = int(argument[1:])
    key = sub_key.group(3)
    if key is not None:
        key = key[1:]
    matched_filters = sub_key.captures(4)
    matched_filter_arguments = sub_key.captures(5)

    filters = []
    filter_argument_index = 0
    for f in matched_filters:
        f = f[1:]
        filter_arguments = []
        if "(" in f:
            f = f[: -len(matched_filter_arguments[filter_argument_index])]
            filter_arguments = [matched_filter_arguments[filter_argument_index][1:-1]]
            filter_argument_index += 1

        f = SubstitutionFilter(f, filter_arguments)
        filters.append(f)

    if_arguments = sub_key.captures(6)

    return sub_string, path, argument, key, filters, if_arguments


def get_function_arguments(sub_key):
    path = sub_key.group(1)
    match = sub_key.string
    arguments = Function.args_regex.findall(match)
    arguments = [x[0][1:] for x in arguments]
    return path, arguments


def get_urlfetch_substitutions(string, all=False):
    substitutions = {}

    if all:
        r = Substitution.urlfetch_substitution_regex_all
    else:
        r = Substitution.urlfetch_substitution_regex

    for sub_key in r.finditer(string):
        substitutions[sub_key.group(0)] = sub_key.group(1)

    return substitutions


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

    def run(self, bot, author, channel, message, args):
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
                return cmd.run(bot, author, channel, extra_msg, args)

            log.info(
                f"User {author} tried running a sub-command he had no access to ({command})."
            )

        return None


class MessageAction(BaseAction):
    type = "message"

    def __init__(self, response, bot, functions=[]):
        self.response = response
        self.functions_raw = functions
        self.functions = (
            get_functions(self.functions_raw, bot) if self.functions_raw else []
        )

        if bot:
            self.argument_subs = get_argument_substitutions(self.response)
            self.num_urlfetch_subs = len(
                get_urlfetch_substitutions(self.response, all=True)
            )
            self.subs = get_substitutions(self.response, bot)
        else:
            self.argument_subs = []
            self.num_urlfetch_subs = 0
            self.subs = {}

    @staticmethod
    def get_argument_value(message, index):
        if not message:
            return ""
        msg_parts = message.split(" ")
        try:
            return msg_parts[index]
        except:
            pass
        return ""

    def get_response(self, bot, extra):
        resp = self.response

        resp, embed = apply_substitutions(resp, self.subs, bot, extra)

        if resp is None:
            return None

        for sub in self.argument_subs:
            needle = sub.needle
            value = str(
                MessageAction.get_argument_value(extra["message"], sub.argument - 1)
            )
            resp = resp.replace(needle, value)
            log.debug(f"Replacing {needle} with {value}")
        return resp, embed

    @property
    def web_functions(self):
        return " ".join(self.functions_raw)

    @staticmethod
    def get_extra_data(author, channel, message, args):
        return {"author": author, "channel": channel, "message": message, **args}

    def run(self, bot, author, channel, message, args):
        raise NotImplementedError("Please implement the run method.")


def urlfetch_msg(method, message, num_urlfetch_subs, bot, extra={}, args=[], kwargs={}):
    urlfetch_subs = get_urlfetch_substitutions(message)

    if len(urlfetch_subs) > num_urlfetch_subs:
        log.error(f"HIJACK ATTEMPT {message}")
        return False

    for needle, url in urlfetch_subs.items():
        try:
            headers = {
                "Accept": "text/plain",
                "Accept-Language": "en-US, en;q=0.9, *;q=0.5",
                "User-Agent": bot.user_agent,
            }
            r = requests.get(url, allow_redirects=True, headers=headers)
            r.raise_for_status()
            value = r.text.strip().replace("\n", "").replace("\r", "")[:400]
        except:
            return False
        message = message.replace(needle, value)

    args.append(message)

    method(*args, **kwargs)


class IfSubstitution:
    def __call__(self, key, extra={}):
        if self.sub.key is None:
            msg = MessageAction.get_argument_value(
                extra.get("message", ""), self.sub.argument - 1
            )
            if msg:
                return self.get_true_response(extra)

            return self.get_false_response(extra)

        res = self.sub.cb(self.sub.key, extra)
        if res:
            return self.get_true_response(extra)

        return self.get_false_response(extra)

    def get_true_response(self, extra):
        return apply_substitutions(self.true_response, self.true_subs, self.bot, extra)

    def get_false_response(self, extra):
        return apply_substitutions(
            self.false_response, self.false_subs, self.bot, extra
        )

    def __init__(self, key, arguments, bot):
        self.bot = bot
        subs = get_substitutions(key, bot)
        if len(subs) == 1:
            self.sub = list(subs.values())[0]
        else:
            subs = get_argument_substitutions(key)
            if len(subs) == 1:
                self.sub = subs[0]
            else:
                self.sub = None
        self.true_response = arguments[0][2:-1] if arguments else "Yes"
        self.false_response = arguments[1][2:-1] if len(arguments) > 1 else "No"

        self.true_subs = get_substitutions(self.true_response, bot)
        self.false_subs = get_substitutions(self.false_response, bot)


def get_substitutions(string, bot):
    """
    Returns a dictionary of `Substitution` objects thare are found in the passed `string`.
    Will not return multiple `Substitution` objects for the same string.
    This means "You have $(source:points) points xD $(source:points)" only returns one Substitution.
    """

    substitutions = collections.OrderedDict()

    for sub_key in Substitution.substitution_regex.finditer(string):
        (
            sub_string,
            path,
            argument,
            key,
            filters,
            if_arguments,
        ) = get_substitution_arguments(sub_key)

        if sub_string in substitutions:
            # We already matched this variable
            continue

        try:
            if path == "if":
                if if_arguments:
                    if_substitution = IfSubstitution(key, if_arguments, bot)
                    if if_substitution.sub is None:
                        continue
                    sub = Substitution(
                        if_substitution,
                        needle=sub_string,
                        key=key,
                        argument=argument,
                        filters=filters,
                    )
                    substitutions[sub_string] = sub
        except:
            log.exception("BabyRage")

    method_mapping = method_subs(bot)

    for sub_key in Substitution.substitution_regex.finditer(string):
        (
            sub_string,
            path,
            argument,
            key,
            filters,
            if_arguments,
        ) = get_substitution_arguments(sub_key)

        if sub_string in substitutions:
            # We already matched this variable
            continue

        if path in method_mapping:
            sub = Substitution(
                method_mapping[path],
                needle=sub_string,
                key=key,
                argument=argument,
                filters=filters,
            )
            substitutions[sub_string] = sub

    return substitutions


def get_functions(_functions, bot):
    functions = []
    method_mapping = method_func(bot)
    for func_name in _functions:
        func = Function.function_regex.search(func_name)
        if not func:
            # log.info(f"Function not found in {func_name}")
            continue
        function, arguments = get_function_arguments(func)
        if function not in method_mapping:
            log.info(f"Function not in method mapping {function}")
            continue
        functions.append(Function(method_mapping[function], arguments))
    return functions


def method_func(bot):
    method_mapping = {}
    try:
        method_mapping["kick"] = bot.func_kick_member if bot else None
        method_mapping["setpoints"] = bot.func_set_balance if bot else None
        method_mapping["adjpoints"] = bot.func_adj_balance if bot else None
        method_mapping["banmember"] = bot.func_ban_member if bot else None
        method_mapping["unbanmember"] = bot.func_unban_member if bot else None
    except AttributeError:
        pass
    return method_mapping


def method_subs(bot):
    method_mapping = {}
    try:
        method_mapping["author"] = bot.get_author_value if bot else None
        method_mapping["channel"] = bot.get_channel_value if bot else None
        method_mapping["time"] = bot.get_time_value if bot else None
        method_mapping["args"] = bot.get_args_value if bot else None
        method_mapping["strictargs"] = bot.get_strictargs_value if bot else None
        method_mapping["command"] = bot.get_command_value if bot else None
        method_mapping["member"] = bot.get_member_value if bot else None
        method_mapping["role"] = bot.get_role_value if bot else None
        method_mapping["userinfo"] = bot.get_user_info if bot else None
        method_mapping["roleinfo"] = bot.get_role_info if bot else None
        method_mapping["commands"] = bot.get_commands if bot else None
        method_mapping["commandinfo"] = bot.get_command_info if bot else None
        method_mapping["user"] = bot.get_user if bot else None
        method_mapping["currency"] = bot.get_currency if bot else None
    except AttributeError:
        pass
    return method_mapping


def get_substitutions_array(array, bot, extra):
    """
    Returns a dictionary of `Substitution` objects thare are found in the passed `string`.
    Will not return multiple `Substitution` objects for the same string.
    This means "You have $(source:points) points xD $(source:points)" only returns one Substitution.
    """

    return_array = []
    method_mapping = method_subs(bot)

    for string in array:
        if not string or not isinstance(string, str):
            return_array.append(string)
            continue
        sub_key = Substitution.substitution_regex.search(string)
        if not sub_key:
            return_array.append(string)
            continue

        (
            sub_string,
            path,
            argument,
            key,
            filters,
            if_arguments,
        ) = get_substitution_arguments(sub_key)

        if path not in method_mapping:
            return_array.append(string)
            continue

        if key and argument:
            param = key
            extra["argument"] = MessageAction.get_argument_value(
                extra["message"], argument - 1
            )
        elif key:
            param = key
        elif argument:
            param = MessageAction.get_argument_value(extra["message"], argument - 1)
        else:
            param = None
        value = method_mapping[path](param, extra)
        try:
            for f in filters:
                value = bot.apply_filter(value, f)
        except:
            log.exception("Exception caught in filter application")
        if value is None:
            return_array.append(None)
        return_array.append(value)

    return return_array


def get_argument_substitutions_array(array, extra):
    return_array = []
    for string in array:
        if not string or not isinstance(string, str):
            return_array.append(string)
            continue
        sub_key = Substitution.argument_substitution_regex.search(string)
        if not sub_key:
            return_array.append(string)
            continue
        return_array.append(
            str(
                MessageAction.get_argument_value(
                    extra["message"], int(sub_key.group(1)) - 1
                )
            )
        )
    return return_array


def run_functions(
    functions, bot, extra, author, channel, args, num_urlfetch_subs, private_message
):
    for func in functions:
        final_args = get_argument_substitutions_array(
            get_substitutions_array(func.arguments, bot, extra), extra
        )
        resp, embed = func.cb(final_args, extra)
        if num_urlfetch_subs == 0:

            return (
                bot.private_message(author, resp, embed)
                if private_message
                else bot.say(channel, resp, embed)
            )

        return ScheduleManager.execute_now(
            urlfetch_msg,
            args=[],
            kwargs={
                "args": [author if private_message else channel],
                "kwargs": {},
                "method": bot.private_message if private_message else bot.say,
                "bot": bot,
                "extra": extra,
                "message": resp,
                "embed": embed,
                "num_urlfetch_subs": num_urlfetch_subs,
            },
        )


class ReplyAction(MessageAction):
    subtype = "Reply"

    def run(self, bot, author, channel, message, args):
        extra = self.get_extra_data(author, channel, message, args)
        if self.functions:
            run_functions(
                self.functions,
                bot,
                extra,
                author,
                channel,
                args,
                self.num_urlfetch_subs,
                args["whisper"],
            )

        resp, embed = self.get_response(bot, extra)
        if not resp and not embed:
            return False

        if self.num_urlfetch_subs == 0:
            if args["whisper"]:
                return bot.private_message(author, resp, embed)
            return bot.say(channel, resp, embed)

        return ScheduleManager.execute_now(
            urlfetch_msg,
            args=[],
            kwargs={
                "args": [author if args["whisper"] else channel],
                "kwargs": {},
                "method": bot.private_message if args["whisper"] else bot.say,
                "bot": bot,
                "extra": extra,
                "message": resp,
                "embed": embed,
                "num_urlfetch_subs": self.num_urlfetch_subs,
            },
        )


class PrivateMessageAction(MessageAction):
    subtype = "Private Message"

    def run(self, bot, author, channel, message, args):
        extra = self.get_extra_data(author, channel, message, args)
        resp, embed = self.get_response(bot, extra)
        if self.functions:
            run_functions(
                self.functions,
                bot,
                extra,
                author,
                channel,
                args,
                self.num_urlfetch_subs,
                True,
            )

        if not resp and embed:
            return False

        if self.num_urlfetch_subs == 0:
            return bot.private_message(author, resp, embed)

        return ScheduleManager.execute_now(
            urlfetch_msg,
            args=[],
            kwargs={
                "args": [author],
                "kwargs": {},
                "method": bot.private_message,
                "bot": bot,
                "extra": extra,
                "message": resp,
                "embed": embed,
                "num_urlfetch_subs": self.num_urlfetch_subs,
            },
        )
