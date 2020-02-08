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
from greenbot.models.user import User

import base64
import time

log = logging.getLogger(__name__)


def init(app):
    discord = DiscordOAuth2Session(app)

    @app.route("/login")
    def discord_login():
        session["state"] = request.args.get("n") or request.referrer or "/"
        return discord.create_session()

    @app.route("/login/error")
    def login_error():
        return render_template("login_error.html")

    @app.route("/login/authorized")
    def discord_auth():
        discord.callback()
        user = discord.fetch_user()
        with DBManager.create_session_scope(expire_on_commit=False) as db_session:
            session["user"] = User._create_or_get_by_discord_id(
                db_session, str(user.id), str(user)
            ).jsonify()
        session["user_displayname"] = str(user)
        next_url = session.get("state", "/")
        return redirect(next_url)

    @app.route("/logout")
    def logout():
        discord.revoke()
        session.pop("user_displayname", None)
        session.pop("user", None)
        next_url = request.args.get("n") or request.referrer or "/"
        if next_url.startswith("/admin"):
            next_url = "/"
        return redirect(next_url)
