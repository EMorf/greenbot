import datetime
import logging

from apscheduler.schedulers.background import BackgroundScheduler

from greenbot import utils

log = logging.getLogger(__name__)


class ScheduledJob:
    def __init__(self, job):
        self.job = job

    def pause(self, *args, **kwargs):
        if self.job:
            self.job.pause(*args, **kwargs)

    def resume(self, *args, **kwargs):
        if self.job:
            self.job.resume(*args, **kwargs)

    def remove(self, *args, **kwargs):
        if self.job:
            self.job.remove(*args, **kwargs)


class ScheduleManager:
    base_scheduler = None
    bot = None

    @staticmethod
    def init(bot):
        if not ScheduleManager.base_scheduler:
            ScheduleManager.base_scheduler = BackgroundScheduler(daemon=True)
            ScheduleManager.base_scheduler.start()
        if not ScheduleManager.bot:
            ScheduleManager.bot = bot

    @staticmethod
    def execute_now(method, args=[], kwargs={}, scheduler=None):
        if scheduler is None:
            scheduler = ScheduleManager.base_scheduler

        if scheduler is None:
            raise ValueError("No scheduler available")
        if not ScheduleManager.bot:
            job = scheduler.add_job(
                method, "date", run_date=utils.now(), args=args, kwargs=kwargs
            )
            return ScheduledJob(job)
        job = scheduler.add_job(
            ScheduleManager.run_async_task,
            "date",
            run_date=utils.now(),
            args=[method, *args],
            kwargs=kwargs,
        )
        return ScheduledJob(job)

    @staticmethod
    def execute_delayed(delay, method, args=[], kwargs={}, scheduler=None):
        if scheduler is None:
            scheduler = ScheduleManager.base_scheduler

        if scheduler is None:
            raise ValueError("No scheduler available")

        if not ScheduleManager.bot:
            job = scheduler.add_job(
                method,
                "date",
                run_date=utils.now() + datetime.timedelta(seconds=delay),
                args=args,
                kwargs=kwargs,
            )
            return ScheduledJob(job)

        job = scheduler.add_job(
            ScheduleManager.run_async_task,
            "date",
            run_date=utils.now() + datetime.timedelta(seconds=delay),
            args=[method, *args],
            kwargs=kwargs,
        )
        return ScheduledJob(job)

    @staticmethod
    def execute_every(
        interval, method, args=[], kwargs={}, scheduler=None, jitter=None
    ):
        if scheduler is None:
            scheduler = ScheduleManager.base_scheduler

        if scheduler is None:
            raise ValueError("No scheduler available")

        if not ScheduleManager.bot:
            job = scheduler.add_job(
                method,
                "interval",
                seconds=interval,
                args=args,
                kwargs=kwargs,
                jitter=jitter,
            )
            return ScheduledJob(job)

        job = scheduler.add_job(
            ScheduleManager.run_async_task,
            "interval",
            seconds=interval,
            args=[method, *args],
            kwargs=kwargs,
            jitter=jitter,
        )
        return ScheduledJob(job)

    @staticmethod
    def run_async_task(method, *args, **kwargs):
        ScheduleManager.bot.private_loop.run_until_complete(method(*args, **kwargs))
