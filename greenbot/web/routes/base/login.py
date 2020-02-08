import json
import logging

from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from greenbot.oauth_client_edit import OAuthEdited
from flask_oauthlib.client import OAuthException
from flask_openid import OpenID
import re

from greenbot.managers.db import DBManager
from greenbot.managers.redis import RedisManager

import base64
import time

log = logging.getLogger(__name__)


def init(app):
    oauth = OAuthEdited(app)

    discord = oauth.remote_app(
        "discord",
        consumer_key=app.bot_config["discord"]["client_id"],
        consumer_secret=app.bot_config["discord"]["client_secret"],
        request_token_params={},
        base_url="https://discordapp.com/api",
        request_token_url=None,
        access_token_method="POST",
        access_token_url="https://discordapp.com/api/oauth2/token",
        authorize_url="https://discordapp.com/api/oauth2/authorize",
    )

    streamer_scopes = ["user_read", "channel:read:subscriptions", "bits:read"]  # remove this later
    """Request these scopes on /streamer_login"""
    spotify_scopes = [
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "user-read-email",
        "user-read-private",
    ]

    @app.route("/login")
    def discord_login():
        callback_url = (
            app.bot_config["discord"]["redirect_uri"]
            if "redirect_uri" in app.bot_config["discord"]
            else url_for("authorized", _external=True)
        )
        state = request.args.get("n") or request.referrer or None
        return discord.authorize(callback=callback_url, state=state, scope="identify", force_verify="true")

    @app.route("/login/error")
    def login_error():
        return render_template("login_error.html")

    @app.route("/login/authorized")
    def discord_auth():
        try:
            resp = discord.authorized_response(discord=True)
        except OAuthException as e:
            log.error(e)
            log.exception("An exception was caught while authorizing")
            next_url = get_next_url(request, "state")
            return redirect(next_url)
        except Exception as e:
            log.error(e)
            log.exception("Unhandled exception while authorizing")
            return render_template("login_error.html")
        if resp is None:
            if "error" in request.args and "error_description" in request.args:
                log.warning(
                    f"Access denied: reason={request.args['error']}, error={request.args['error_description']}"
                )
            next_url = get_next_url(request, "state")
            return redirect(next_url)
        elif type(resp) is OAuthException:
            log.warning(resp.message)
            log.warning(resp.data)
            log.warning(resp.type)
            next_url = get_next_url(request, "state")
            return redirect(next_url)

        session["discord_token"] = (resp["access_token"],)
        me_api_response = discord.get(url="api/users/@me", discord=True)
        session["discord_id"] = me_api_response["id"]
        session["discord_username"] = me_api_response["username"]
        next_url = get_next_url(request, "state")
        return redirect(next_url)

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

    @discord.tokengetter
    def get_discord_oauth_token():
        return session.get("discord_token")
