import collections
import logging

from flask import render_template

from greenbot.managers.redis import RedisManager
from greenbot.streamhelper import StreamHelper

log = logging.getLogger(__name__)


def init(app):
    @app.route("/")
    def home():
        custom_content = ""

        return render_template(
            "home.html",
            custom_content=custom_content
        )
