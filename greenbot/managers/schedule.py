import datetime
import logging
import asyncio

from greenbot.managers.handler import HandlerManager
from greenbot import utils

log = logging.getLogger(__name__)


class ScheduledJob:
    def __init__(self, run_type, method, interval=1, run_date=utils.now(), args=[], kwargs={}):
        self.run_type = run_type
        self.method = method
        self.run_date = run_date
        self.interval = interval
        self.args = args
        self.kwargs = kwargs
        self.paused = False
        self.last_run = None

    @property
    def should_run(self):
        if self.paused:
            return False
        if self.run_type == "date":
            return self.run_date < utils.now()
        else:
            return (utils.now() - self.last_run).total_seconds() > self.interval

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def remove(self):
        ScheduleManager.schedules.remove(self)

    async def run(self):
        await self.method(*self.args, **self.kwargs)
        if self.run_type == "date":
            self.remove()
        else:
            self.last_run = utils.now()

    

class ScheduleManager:
    schedules = []
    ready = False

    @staticmethod
    def init(private_loop):
        private_loop.create_task(ScheduleManager.process_schedules())

    @staticmethod
    def execute_now(method, args=[], kwargs={}):
        return ScheduledJob("date", method, run_date=utils.now(), args=args, kwargs=kwargs)

    @staticmethod
    def execute_delayed(delay, method, args=[], kwargs={}):
        return ScheduledJob("date", method, run_date=(utils.now() + datetime.datetime.timedelta(seconds=delay)), args=args, kwargs=kwargs)

    @staticmethod
    def execute_every(interval, method, args=[], kwargs={}):
        return ScheduledJob("interval", method, interval=interval, args=args, kwargs=kwargs)

    @staticmethod
    async def process_schedules():
        ScheduleManager.ready = True
        while True:
            for schedule in ScheduleManager.schedules[:]:
                if schedule.should_run:
                    await schedule.run()
            await asyncio.sleep(0.2)
