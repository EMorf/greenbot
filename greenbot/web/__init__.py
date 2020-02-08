import os

import logging
from flask import Flask

app = Flask(
    __name__,
    static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__ + "/../..")), "static"),
    template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__ + "/../..")), "templates"),
)

app.url_map.strict_slashes = False

log = logging.getLogger(__name__)


def init(args):
    import subprocess
    import sys

    from flask import request
    from flask import session
    from flask_scrypt import generate_random_salt

    import greenbot.utils
    import greenbot.web.common
    import greenbot.web.routes

    from greenbot.managers.db import DBManager
    from greenbot.managers.redis import RedisManager
    from greenbot.managers.schedule import ScheduleManager
    from greenbot.models.module import ModuleManager
    from greenbot.models.sock import SocketClientManager
    from greenbot.utils import load_config
    from greenbot.web.models import errors
    from greenbot.bothelper import BotHelper

    ScheduleManager.init()

    config = load_config(args.config)

    redis_options = {}
    if "redis" in config:
        redis_options = dict(config["redis"])

    RedisManager.init(**redis_options)

    if "web" not in config:
        log.error("Missing [web] section in config.ini")
        sys.exit(1)
    
    if "secret_key" not in config["web"]:
        salt = generate_random_salt()
        config.set("web", "secret_key", salt.decode("utf-8"))

        with open(args.config, "w") as configfile:
            config.write(configfile)

    bot_name = config["main"]["bot_name"]
    BotHelper.set_bot_name(bot_name)
    SocketClientManager.init(bot_name)

    app.bot_modules = config["web"].get("modules", "").split()
    app.bot_commands_list = []
    app.bot_config = config
    app.secret_key = config["web"]["secret_key"]
    app.bot_dev = "flags" in config and "dev" in config["flags"] and config["flags"]["dev"] == "1"

    DBManager.init(config["main"]["db"])

    app.module_manager = ModuleManager(None).load()

    greenbot.web.routes.admin.init(app)
    greenbot.web.routes.api.init(app)
    greenbot.web.routes.base.init(app)

    greenbot.web.common.filters.init(app)
    greenbot.web.common.assets.init(app)
    greenbot.web.common.menu.init(app)

    errors.init(app, config)

    last_commit = None
    if app.bot_dev:
        try:
            last_commit = subprocess.check_output(["git", "log", "-1", "--format=%cd"]).decode("utf8").strip()
        except:
            log.exception("Failed to get last_commit, will not show last commit")

    default_variables = {
        "last_commit": last_commit,
        "version": "v1.0",
        "bot": {"name": config["main"]["bot_name"]},
        "site": {
            "domain": config["web"]["domain"]
        },
        "modules": app.bot_modules,
        "request": request,
        "session": session,
        "google_analytics": config["web"].get("google_analytics", None),
    }

    @app.context_processor
    def current_time():
        current_time = {}
        current_time["current_time"] = greenbot.utils.now()
        return current_time

    @app.context_processor
    def inject_default_variables():
        return default_variables
