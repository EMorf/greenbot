import logging
import operator

from greenbot.utils import find

log = logging.getLogger("greenbot")


class HandlerManager:
    handlers = {}

    @staticmethod
    def init_handlers():
        HandlerManager.handlers = {}

        # When the discord bot is ready!
        HandlerManager.create_handler("discord_ready")

        # When the discord bot recieves a message!
        HandlerManager.create_handler("discord_message")

        # When the managers are loaded!
        HandlerManager.create_handler("manager_loaded")

        # on_quit
        HandlerManager.create_handler("on_quit")

    @staticmethod
    def create_handler(event):
        """ Create an empty list for the given event """
        HandlerManager.handlers[event] = []

    @staticmethod
    def add_handler(event, method, priority=0):
        try:
            HandlerManager.handlers[event].append((method, priority))
            HandlerManager.handlers[event].sort(
                key=operator.itemgetter(1), reverse=True
            )
        except KeyError:
            # No handlers for this event found
            log.error(f"add_handler No handler for {event} found.")

    @staticmethod
    def method_matches(h, method):
        return h[0] == method

    @staticmethod
    def remove_handler(event, method):
        handler = None
        try:
            handler = find(
                lambda h: HandlerManager.method_matches(h, method),
                HandlerManager.handlers[event],
            )
            if handler is not None:
                HandlerManager.handlers[event].remove(handler)
        except KeyError:
            # No handlers for this event found
            log.error(f"remove_handler No handler for {event} found.")

    @staticmethod
    async def trigger(event_name, stop_on_false=True, *args, **kwargs):
        if event_name not in HandlerManager.handlers:
            log.error(f"No handler set for event {event_name}")
            return False

        for handler, _ in HandlerManager.handlers[event_name]:
            res = None
            try:
                res = await handler(*args, **kwargs)
            except:
                log.exception(f"Unhandled exception from {handler} in {event_name}")

            if res is False and stop_on_false is True:
                # Abort if handler returns false and stop_on_false is enabled
                return False
        return True
