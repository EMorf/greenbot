from flask_restful import Api

import greenbot.web.routes.api.banphrases
import greenbot.web.routes.api.commands
import greenbot.web.routes.api.common
import greenbot.web.routes.api.modules
import greenbot.web.routes.api.social
import greenbot.web.routes.api.timers
import greenbot.web.routes.api.twitter
import greenbot.web.routes.api.users
import greenbot.web.routes.api.playsound


def init(app):
    # Initialize the v1 api
    # /api/v1
    api = Api(app, prefix="/api/v1", catch_all_404s=False)

    # Initialize any common settings and routes
    greenbot.web.routes.api.common.init(api)

    # /users
    greenbot.web.routes.api.users.init(api)

    # /commands
    greenbot.web.routes.api.commands.init(api)

    # /timers
    greenbot.web.routes.api.timers.init(api)

    # /banphrases
    greenbot.web.routes.api.banphrases.init(api)

    # /modules
    greenbot.web.routes.api.modules.init(api)
