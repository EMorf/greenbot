import json
import logging

from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from flask_discord import DiscordOAuth2Session
import re

from greenbot.managers.db import DBManager
from greenbot.managers.redis import RedisManager

import base64
import time

log = logging.getLogger(__name__)


def init(app):
    discord = DiscordOAuth2Session(app)

    @app.route("/login")
    def discord_login():
        return discord.create_session()

    @app.route("/login/error")
    def login_error():
        return render_template("login_error.html")

    @app.route("/login/authorized")
    def discord_auth():
        discord.callback()
        return redirect(url_for(".me"))

    @app.route("/me/")
    def me():
        user = discord.fetch_user()
        return f"""
        <html>
            <head>
                <title>{user}</title>
            </head>
            <body>
                <img src='{user.avatar_url}' />
            </body>
        </html>"""

    def get_next_url(request, key="n"):
        next_url = request.args.get(key, "/")
        if next_url.startswith("//"):
            return "/"
        return next_url

    @app.route("/logout")
    def logout():
        session.pop("steam_id", None)
        session.pop("discord_token", None)
        session.pop("discord_id", None)
        session.pop("discord_username", None)
        next_url = get_next_url(request)
        if next_url.startswith("/admin"):
            next_url = "/"
        return redirect(next_url)
