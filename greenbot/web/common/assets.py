import logging

from flask_assets import Bundle
from flask_assets import Environment

log = logging.getLogger(__name__)


def init(app):
    assets = Environment(app)

    # Basic CSS and Javascript:
    # Available under: base_css, base_js
    base_css = Bundle(
        "css/base.scss", filters="pyscss,cssmin", output="gen/css/base.%(version)s.css"
    )
    base_js = Bundle(
        "scripts/base.js", filters="jsmin", output="gen/scripts/base.%(version)s.js"
    )
    assets.register("base_css", base_css)
    assets.register("base_js", base_js)

    datetime_js = Bundle(
        "scripts/datetime.js",
        filters="jsmin",
        output="gen/scripts/datetime.%(version)s.js",
    )
    assets.register("datetime", datetime_js)

    # Admin site
    # Availabe under: admin_create_banphrase, admin_create_command,
    #                 admin_create_row, admin_edit_command
    admin_create_banphrase = Bundle(
        "scripts/admin/create_banphrase.js",
        filters="jsmin",
        output="gen/scripts/admin/create_banphrase.%(version)s.js",
    )
    admin_create_command = Bundle(
        "scripts/admin/create_command.js",
        filters="jsmin",
        output="gen/scripts/admin/create_command.%(version)s.js",
    )
    admin_create_row = Bundle(
        "scripts/admin/create_row.js",
        filters="jsmin",
        output="gen/scripts/admin/create_row.%(version)s.js",
    )
    admin_edit_command = Bundle(
        "scripts/admin/edit_command.js",
        filters="jsmin",
        output="gen/scripts/admin/edit_command.%(version)s.js",
    )
    assets.register("admin_create_banphrase", admin_create_banphrase)
    assets.register("admin_create_command", admin_create_command)
    assets.register("admin_create_row", admin_create_row)
    assets.register("admin_edit_command", admin_edit_command)

    notifications_subscribers = Bundle(
        "scripts/notifications/subscribers.js",
        filters="jsmin",
        output="gen/scripts/notifications/subscribers.%(version)s.js",
    )
    assets.register("notifications_subscribers", notifications_subscribers)

    # Third party libraries
    # Available under: autolinker
    autolinker = Bundle(
        "scripts/autolinker.js",
        filters="jsmin",
        output="gen/scripts/autolinker.%(version)s.js",
    )
    assets.register("autolinker", autolinker)

    # Commands
    # Available under: commands_js
    commands_js = Bundle(
        "scripts/commands.js",
        filters="jsmin",
        output="gen/scripts/commands.%(version)s.js",
    )
    assets.register("commands_js", commands_js)

    # Pagination script
    # Available under: paginate_js
    paginate_js = Bundle(
        "scripts/paginate.js",
        filters="jsmin",
        output="gen/scripts/paginate.%(version)s.js",
    )
    assets.register("paginate_js", paginate_js)

    # range slider for semantic UI
    range_slider_js = Bundle(
        "scripts/range.js", filters="jsmin", output="gen/scripts/range.%(version)s.js"
    )
    assets.register("range_slider_js", range_slider_js)
    range_slider_css = Bundle(
        "css/range.css", filters="cssmin", output="gen/css/range.%(version)s.css"
    )
    assets.register("range_slider_css", range_slider_css)

    assets.init_app(app)
