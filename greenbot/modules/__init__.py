from greenbot.modules.base import BaseModule
from greenbot.modules.base import ModuleSetting
from greenbot.modules.base import ModuleType

from greenbot.modules.basic import BasicCommandsModule
from greenbot.modules.basic.admincommands import AdminCommandsModule
from greenbot.modules.activitytracker import ActivityTracker

available_modules = [
    AdminCommandsModule,
    ActivityTracker,
    BasicCommandsModule,
]
