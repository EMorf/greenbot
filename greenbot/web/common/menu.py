import logging

log = logging.getLogger(__name__)


class MenuItem:
    def __init__(self, href, menu_id, caption, level=100):
        self.href = href
        self.id = menu_id
        self.caption = caption
        self.level = level


def init(app):
    nav_bar_header = []
    nav_bar_header.append(MenuItem("/", "home", "Home"))
    nav_bar_header.append(MenuItem("/commands", "commands", "Commands"))
    nav_bar_admin_header = []
    nav_bar_admin_header.append(MenuItem("/", "home", "Home"))
    nav_bar_admin_header.append(MenuItem("/admin", "admin_home", "Admin Home"))
    nav_bar_admin_header.append(
        MenuItem(
            [
                MenuItem("/admin/banphrases", "admin_banphrases", "Banphrases"),
                MenuItem("/admin/links/blacklist", "admin_links_blacklist", "Blacklisted links"),
                MenuItem("/admin/links/whitelist", "admin_links_whitelist", "Whitelisted links"),
            ],
            None,
            "Filters",
        )
    )
    nav_bar_admin_header.append(MenuItem("/admin/commands", "admin_commands", "Commands"))
    nav_bar_admin_header.append(MenuItem("/admin/timers", "admin_timers", "Timers"))
    nav_bar_admin_header.append(MenuItem("/admin/moderators", "admin_moderators", "Moderators"))
    nav_bar_admin_header.append(MenuItem("/admin/modules", "admin_modules", "Modules"))

    @app.context_processor
    def menu():
        data = {"nav_bar_header": nav_bar_header, "nav_bar_admin_header": nav_bar_admin_header}
        return data
