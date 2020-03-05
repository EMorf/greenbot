import logging
import requests
import json
import asyncio

from greenbot.managers.handler import HandlerManager
from greenbot.managers.schedule import ScheduleManager

from datetime import datetime
from akamai.edgeauth import EdgeAuth, EdgeAuthError

log = logging.getLogger(__name__)


class MovieNightAPI:
    def __init__(self, bot, wsc_config, wowza_cdn_config):
        self.bot = bot
        self.wsc_api_key = wsc_config.get("wsc_api_key", None)
        self.wsc_access_key = wsc_config.get("wsc_access_key", None)
        self.wsc_host = wsc_config.get("wsc_host", None)
        self.wsc_version = wsc_config.get("wsc_version", None)

        self.wowza_cdn_expiration_time = wowza_cdn_config.get("wowza_cdn_expiration_time", None)
        self.wowza_cdn_live_stream_id = wowza_cdn_config.get("wowza_cdn_live_stream_id", None)
        self.wowza_cdn_trusted_shared_secret = wowza_cdn_config.get("wowza_cdn_trusted_shared_secret")

        self.ull_stream_running = False
        self.cdn_stream_running = False
        self.ull_playback_key = ""
        self.cdn_playback_key = ""

        if self.wsc_api_key\
            and self.wsc_access_key\
            and self.wsc_host\
            and self.wsc_version\
            and self.wowza_cdn_expiration_time\
            and self.wowza_cdn_live_stream_id\
            and self.wowza_cdn_trusted_shared_secret:
            self.schedule_job = ScheduleManager.execute_every(interval=30, method=self.stream_check)
            self.active = True
        else:
            self.active = False
    @property
    def header(self):
        return {
            "Content-Type": "application/json",
            "wsc-api-key": self.wsc_api_key,
            "wsc-access-key": self.wsc_access_key,
        }

    @property
    def host_version(self):
        return f"{self.wsc_host}{self.wsc_version}"

    @property
    def key(self):
        return self.ull_playback_key if self.ull_stream_running else (self.cdn_playback_key if self.cdn_stream_running else None)

    @property
    def online(self):
        return self.ull_stream_running or self.cdn_stream_running

    def is_online(self):
        return self.online, self.ull_stream_running if self.online else None, self.key

    def create_ull_fetch_targets_request(self, target_id=None):
        return {
            "header": self.header,
            f"url": f"{self.host_version}/stream_targets/ull" + f"/{target_id}" if target_id else "",
        }

    def create_stream_state_request(self, target_id):
        return {
            "header": self.header,
            "url": f"{self.host_version}/live_streams/{target_id}/state",
        }

    def create_ull_target_request(self, name):
        return {
            "header": self.header,
            "payload": {
                "stream_target_ull": {
                    "name": name,
                    "source_delivery_method": "push",
                    "enable_hls": True,
                }
            },
            "url": f"{self.host_version}/stream_targets/ull",
        }

    def transcoder_request(self, state):
        return {
            "header": self.header,
            "url": f"{self.host_version}/transcoders/trans_id/{state}",
        }

    def fetch_latest_ull_target_id(self):
        req = self.create_ull_fetch_targets_request()
        res = requests.get(req["url"], headers=req["header"])
        jres = json.loads(res.content)

        latest_target = None

        for target in jres["stream_targets_ull"]:
            if latest_target is None:
                latest_target = target
            elif datetime.strptime(
                latest_target["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ"
            ) < datetime.strptime(target["created_at"], "%Y-%m-%dT%H:%M:%S.%fZ"):
                latest_target = target
        if latest_target:
            return latest_target["id"]

        return None

    def fetch_cdn_stream_state(self):
        req = self.create_stream_state_request(self.wowza_cdn_live_stream_id)
        res = requests.get(req["url"], headers=req["header"])
        return json.loads(res.content)

    def create_ull_target(self):
        stream_name = "Movienight(ULL)-{}".format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        req = self.create_ull_target_request(stream_name)
        res = requests.post(
            req["url"], data=json.dumps(req["payload"]), headers=req["header"]
        )
        jres = json.loads(res.content)

        endpoint = jres["stream_target_ull"]["primary_url"]
        server = "/".join(endpoint.split("/")[:4])
        stream_key = endpoint.split("/")[4]

        return server, stream_key

    async def start_cdn_target(self):
        req = self.transcoder_request("state")
        res = requests.get(req["url"], headers=req["header"])
        jres = json.loads(res.content)

        if not res.status_code == 200:
            log.error("Unable to fetch transcoder")

        if jres["transcoder"]["state"] == "started":
            log.warning("Transcoder is already running")
            return True

        req = self.transcoder_request("start")
        res = requests.put(req["url"], headers=req["header"])
        jres = json.loads(res.content)

        if not res.status_code == 200:
            log.error("Transcoder start request failed")
        else:
            req = self.transcoder_request("state")
            for _ in range(30):
                res = requests.get(req["url"], headers=req["header"])
                jres = json.loads(res.content)

                if jres["transcoder"]["state"] == "started":
                    return True
                await asyncio.sleep(1)
            log.error("Transcoder startup timed out")

        return False

    async def stream_check(self):
        log.info("Running stream check")

        # check for ULL stream
        # -----------------------------------------
        target_id = self.fetch_latest_ull_target_id()
        req = self.create_ull_fetch_targets_request(target_id)
        res = requests.get(req["url"], headers=req["header"])
        jres = json.loads(res.content)

        log.info("ULL state: " + jres["stream_target_ull"]["state"])

        if jres["stream_target_ull"]["state"] == "started":
            if not self.ull_stream_running:
                self.ull_playback_key = jres["stream_target_ull"]["playback_urls"]["ws"][1].split("/")[
                    5
                ]
                log.info(f"Detected ull stream (playback key {self.ull_playback_key})")
                await HandlerManager.trigger("movie_night_started")
                self.ull_stream_running = True
            return
        else:
            self.ull_stream_running = False

        # check for CDN stream
        # -----------------------------------------
        jres = self.fetch_cdn_stream_state()

        log.info("CDN state: " + jres["live_stream"]["state"])

        if jres["live_stream"]["state"] == "started":
            if not self.cdn_stream_running:
                self.cdn_playback_key = self.generate_cdn_token()
                log.info(f"Detected cnd stream (playback key {self.cdn_playback_key})")
                await HandlerManager.trigger("movie_night_started")
                self.cdn_stream_running = True
        else:
            self.cdn_stream_running = False

    def generate_cdn_token(self):
        try:
            generator = EdgeAuth(
                window_seconds=self.wowza_cdn_expiration_time,
                acl_delimiter="*",
                key=self.wowza_cdn_trusted_shared_secret,
                verbose=True,
            )
            token = generator.generateToken()
            if generator.warnings:
                log.warning("\n".join(generator.warnings))
            log.info("%s" % token)

            return token

        except EdgeAuthError as ex:
            log.error("%s\n" % ex)
        except Exception as ex:
            log.error(str(ex))