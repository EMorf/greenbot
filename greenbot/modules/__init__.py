from greenbot.modules.base import BaseModule
from greenbot.modules.base import ModuleSetting
from greenbot.modules.base import ModuleType

from greenbot.modules.basic import BasicCommandsModule
from greenbot.modules.basic.admincommands import AdminCommandsModule
from greenbot.modules.advancedadminlog import AdvancedAdminLog
from greenbot.modules.activitytracker import ActivityTracker
from greenbot.modules.memes import Memes
from greenbot.modules.remindme import RemindMe
from greenbot.modules.twitch_tracker import TwitchTracker

available_modules = [
    AdminCommandsModule,
    AdvancedAdminLog,
    ActivityTracker,
    BasicCommandsModule,
    Memes,
    RemindMe,
    TwitchTracker,
]
