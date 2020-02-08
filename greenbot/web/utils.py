import datetime
import json
import logging
import urllib.parse
from functools import update_wrapper
from functools import wraps

from flask import abort
from flask import make_response
from flask import request
from flask import redirect
from flask import session
from flask_restful import reqparse

import greenbot.exc
import greenbot.managers
from greenbot import utils
from greenbot.managers.db import DBManager
from greenbot.managers.redis import RedisManager
from greenbot.models.module import ModuleManager
from greenbot.models.user import User
from greenbot.utils import time_method
from greenbot.bothelper import BotHelper
from greenbot.managers.command import CommandManager

log = logging.getLogger(__name__)


def requires_level(level, redirect_url="/"):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user" not in session:
                return redirect("/login?n=" + redirect_url)
            with DBManager.create_session_scope() as db_session:
                user = (
                    db_session.query(User)
                    .filter_by(discord_id=session["user"]["discord_id"])
                    .one_or_none()
                )
                if user is None:
                    abort(403)

                if user.level < level:
                    abort(403)

                db_session.expunge(user)
                kwargs["user"] = user

            return f(*args, **kwargs)

        return update_wrapper(decorated_function, f)

    return decorator


def nocache(view):
    @wraps(view)
    def no_cache(*args, **kwargs):
        response = make_response(view(*args, **kwargs))
        response.headers["Last-Modified"] = utils.now()
        response.headers[
            "Cache-Control"
        ] = "no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "-1"
        return response

    return update_wrapper(no_cache, view)


@time_method
def get_cached_commands():
    CACHE_TIME = 30  # seconds

    redis = RedisManager.get()
    commands_key = f"{BotHelper.get_bot_name()}:cache:commands"
    commands = redis.get(commands_key)
    if commands is None:
        log.debug("Updating commands...")
        bot_commands = CommandManager(
            socket_manager=None, module_manager=ModuleManager(None).load(), bot=None
        ).load(load_examples=False)
        bot_commands_list = bot_commands.parse_for_web()

        bot_commands_list.sort(key=lambda x: (x.id or -1, x.main_alias))
        bot_commands_list = [c.jsonify() for c in bot_commands_list]
        redis.setex(
            commands_key,
            value=json.dumps(bot_commands_list, separators=(",", ":")),
            time=CACHE_TIME,
        )
    else:
        bot_commands_list = json.loads(commands)

    return bot_commands_list


def json_serial(obj):
    if isinstance(obj, datetime.datetime):
        serial = obj.isoformat()
        return serial
    try:
        return obj.jsonify()
    except:
        log.exception("Unable to serialize object with `jsonify`")
        raise


def init_json_serializer(api):
    @api.representation("application/json")
    def output_json(data, code, headers=None):
        resp = make_response(json.dumps(data, default=json_serial), code)
        resp.headers.extend(headers or {})
        return resp


def jsonify_query(query):
    return [v.jsonify() for v in query]


def jsonify_list(
    key,
    query,
    base_url=None,
    default_limit=None,
    max_limit=None,
    jsonify_method=jsonify_query,
):
    """ Must be called in the context of a request """
    _total = query.count()

    paginate_args = paginate_parser.parse_args()

    # Set the limit to the limit specified in the parameters
    limit = default_limit

    if paginate_args["limit"] and paginate_args["limit"] > 0:
        # If another limit has been passed through to the query arguments, use it
        limit = paginate_args["limit"]
        if max_limit:
            # If a max limit has been set, make sure we respect it
            limit = min(limit, max_limit)

    # By default we perform no offsetting
    offset = None

    if paginate_args["offset"] and paginate_args["offset"] > 0:
        # If an offset has been specified in the query arguments, use it
        offset = paginate_args["offset"]

    if limit:
        query = query.limit(limit)

    if offset:
        query = query.offset(offset)

    payload = {"_total": _total, key: jsonify_method(query)}

    if base_url:
        payload["_links"] = {}

        payload["_links"]["self"] = base_url

        if request.args:
            payload["_links"]["self"] += "?" + urllib.parse.urlencode(request.args)

        if limit:
            payload["_links"]["next"] = (
                base_url
                + "?"
                + urllib.parse.urlencode(
                    [("limit", limit), ("offset", (offset or 0) + limit)]
                )
            )

            if offset:
                payload["_links"]["prev"] = (
                    base_url
                    + "?"
                    + urllib.parse.urlencode(
                        [("limit", limit), ("offset", max(0, offset - limit))]
                    )
                )

    return payload


paginate_parser = reqparse.RequestParser()
paginate_parser.add_argument("limit", type=int, required=False)
paginate_parser.add_argument("offset", type=int, required=False)
