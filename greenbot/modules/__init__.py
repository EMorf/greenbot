from greenbot.modules.base import BaseModule
from greenbot.modules.base import ModuleSetting
from greenbot.modules.base import ModuleType

from greenbot.modules.basic import BasicCommandsModule
from greenbot.modules.basic.admincommands import AdminCommandsModule
from greenbot.modules.advancedadminlog import AdvancedAdminLog
from greenbot.modules.activitytracker import ActivityTracker
from greenbot.modules.memes import Memes
from greenbot.modules.movienight import MovieNight
from greenbot.modules.remindme import RemindMe
from greenbot.modules.role_to_level import RoleToLevel
from greenbot.modules.twitch_tracker import TwitchTracker
from greenbot.modules.timeout import TimeoutModule
from greenbot.modules.twitter import Twitter

available_modules = [
    AdminCommandsModule,
    AdvancedAdminLog,
    ActivityTracker,
    BasicCommandsModule,
    Memes,
    MovieNight,
    RemindMe,
    RoleToLevel,
    TimeoutModule,
    TwitchTracker,
    Twitter,
]
