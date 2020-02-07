import greenbot.web.routes.base.commands
import greenbot.web.routes.base.home
import greenbot.web.routes.base.login
import greenbot.web.routes.base.user


def init(app):
    greenbot.web.routes.base.commands.init(app)
    greenbot.web.routes.base.home.init(app)
    greenbot.web.routes.base.login.init(app)
    greenbot.web.routes.base.user.init(app)
