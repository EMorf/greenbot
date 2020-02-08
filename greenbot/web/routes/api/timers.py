import logging

from flask_restful import Resource
from flask_restful import reqparse

import greenbot.modules
import greenbot.utils
import greenbot.web.utils
from greenbot.managers.adminlog import AdminLogManager
from greenbot.managers.db import DBManager
from greenbot.models.sock import SocketClientManager
from greenbot.models.timer import Timer

log = logging.getLogger(__name__)


class APITimerRemove(Resource):
    @greenbot.web.utils.requires_level(500)
    def get(self, timer_id, **options):
        with DBManager.create_session_scope() as db_session:
            timer = db_session.query(Timer).filter_by(id=timer_id).one_or_none()
            if timer is None:
                return {"error": "Invalid timer ID"}, 404
            AdminLogManager.post("Timer removed", options["user"].discord_id, timer.name)
            db_session.delete(timer)
            SocketClientManager.send("timer.remove", {"id": timer.id})
            return {"success": "good job"}


class APITimerToggle(Resource):
    def __init__(self):
        super().__init__()

        self.post_parser = reqparse.RequestParser()
        self.post_parser.add_argument("new_state", required=True)

    @greenbot.web.utils.requires_level(500)
    def post(self, row_id, **options):
        args = self.post_parser.parse_args()

        try:
            new_state = int(args["new_state"])
        except (ValueError, KeyError):
            return {"error": "Invalid `new_state` parameter."}, 400

        with DBManager.create_session_scope() as db_session:
            row = db_session.query(Timer).filter_by(id=row_id).one_or_none()

            if not row:
                return {"error": "Timer with this ID not found"}, 404

            row.enabled = True if new_state == 1 else False
            db_session.commit()
            payload = {"id": row.id, "new_state": row.enabled}
            AdminLogManager.post(
                "Timer toggled",
                options["user"].discord_id,
                "Enabled" if row.enabled else "Disabled",
                row.name,
            )
            SocketClientManager.send("timer.update", payload)
            return {"success": "successful toggle", "new_state": new_state}


def init(api):
    api.add_resource(APITimerRemove, "/timers/remove/<int:timer_id>")
    api.add_resource(APITimerToggle, "/timers/toggle/<int:row_id>")
