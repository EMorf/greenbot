from flask import Blueprint

import greenbot.web.routes.admin.banphrases
import greenbot.web.routes.admin.commands
import greenbot.web.routes.admin.home
import greenbot.web.routes.admin.links
import greenbot.web.routes.admin.moderators
import greenbot.web.routes.admin.modules
import greenbot.web.routes.admin.timers


def init(app):
    page = Blueprint("admin", __name__, url_prefix="/admin")

    greenbot.web.routes.admin.banphrases.init(page)
    greenbot.web.routes.admin.commands.init(page)
    greenbot.web.routes.admin.home.init(page)
    greenbot.web.routes.admin.links.init(page)
    greenbot.web.routes.admin.moderators.init(page)
    greenbot.web.routes.admin.modules.init(page)
    greenbot.web.routes.admin.timers.init(page)

    app.register_blueprint(page)
