import logging
import operator

from greenbot.utils import find

log = logging.getLogger("greenbot")


class HandlerManager:
    handlers = {}

    @staticmethod
    def init_handlers():
        HandlerManager.handlers = {}

        # When the managers are loaded!
        HandlerManager.create_handler("manager_loaded")

        # on_quit
        HandlerManager.create_handler("on_quit")

        # parse_command_from_message
        HandlerManager.create_handler("parse_command_from_message")

        # discord event handles
        # discord.on_ready()
        HandlerManager.create_handler("discord_ready")

        # discord.on_connect()
        HandlerManager.create_handler("discord_connect")

        # discord.on_disconnect()
        HandlerManager.create_handler("discord_disconnect")

        # discord.on_shard_ready(shard_id)
        HandlerManager.create_handler("discord_shard_ready")

        # discord.on_resumed()
        HandlerManager.create_handler("discord_resumed")

        # discord.on_error(event, *args, **kwargs)
        HandlerManager.create_handler("discord_error")

        # discord.on_socket_raw_receive(payload)
        HandlerManager.create_handler("discord_socket_raw_receive")

        # discord.on_socket_raw_send(payload)
        HandlerManager.create_handler("discord_socket_raw_send")

        # discord.on_typing(channel, user, when)
        HandlerManager.create_handler("discord_typing")

        # discord.on_message(message)
        HandlerManager.create_handler("discord_message")

        # discord.on_message_delete(message)
        HandlerManager.create_handler("discord_message_delete")

        # discord.on_bulk_message_delete(messages)
        HandlerManager.create_handler("discord_bulk_message_delete")

        # discord.on_raw_message_delete(payload)
        HandlerManager.create_handler("discord_raw_message_delete")

        # discord.on_raw_bulk_message_delete(payload)
        HandlerManager.create_handler("discord_raw_bulk_message_delete")

        # discord.on_message_edit(before, after)
        HandlerManager.create_handler("discord_message_edit")

        # discord.on_raw_message_edit(payload)
        HandlerManager.create_handler("discord_raw_message_edit")

        # discord.on_reaction_add(reaction, user)
        HandlerManager.create_handler("discord_reaction_add")

        # discord.on_reaction_remove(reaction, user)
        HandlerManager.create_handler("discord_reaction_remove")

        # discord.on_raw_reaction_remove(payload)
        HandlerManager.create_handler("discord_raw_reaction_remove")

        # discord.on_reaction_clear(message, reactions)
        HandlerManager.create_handler("discord_reaction_clear")

        # discord.on_raw_reaction_clear(payload)
        HandlerManager.create_handler("discord_raw_reaction_clear")

        # discord.on_reaction_clear_emoji(reaction)
        HandlerManager.create_handler("discord_reaction_clear_emoji")

        # discord.on_raw_reaction_clear_emoji(payload)
        HandlerManager.create_handler("discord_raw_reaction_clear_emoji")

        # discord.on_private_channel_delete(channel)
        HandlerManager.create_handler("discord_private_channel_delete")

        # discord.on_private_channel_create(channel)
        HandlerManager.create_handler("discord_private_channel_create")

        # discord.on_private_channel_update(before, after)
        HandlerManager.create_handler("discord_private_channel_update")

        # discord.on_private_channel_pins_update(channel, last_pin)
        HandlerManager.create_handler("discord_private_channel_pins_update")

        # discord.on_guild_channel_delete(channel)
        HandlerManager.create_handler("discord_guild_channel_delete")

        # discord.on_guild_channel_create(channel)
        HandlerManager.create_handler("discord_guild_channel_create")

        # discord.on_guild_channel_update(before, after)
        HandlerManager.create_handler("discord_guild_channel_update")

        # discord.on_guild_channel_pins_update(channel, last_pin)
        HandlerManager.create_handler("discord_guild_channel_pins_update")

        # discord.on_guild_integrations_update(guild)
        HandlerManager.create_handler("discord_guild_integrations_update")

        # discord.on_webhooks_update(channel)
        HandlerManager.create_handler("discord_webhooks_update")

        # discord.on_member_join(member)
        HandlerManager.create_handler("discord_member_join")

        # discord.on_member_remove(member)
        HandlerManager.create_handler("discord_member_remove")

        # discord.on_member_update(before, after)
        HandlerManager.create_handler("discord_member_update")

        # discord.on_user_update(before, after)
        HandlerManager.create_handler("discord_user_update")

        # discord.on_guild_join(guild)
        HandlerManager.create_handler("discord_guild_join")

        # discord.on_guild_remove(guild)
        HandlerManager.create_handler("discord_guild_remove")

        # discord.on_guild_update(before, after)
        HandlerManager.create_handler("discord_guild_update")

        # discord.on_guild_role_create(role)
        HandlerManager.create_handler("discord_guild_role_create")

        # discord.on_guild_role_delete(role)
        HandlerManager.create_handler("discord_guild_role_delete")

        # discord.on_guild_role_update(before, after)
        HandlerManager.create_handler("discord_guild_role_update")

        # discord.on_guild_emojis_update(guild, before, after)
        HandlerManager.create_handler("discord_guild_emojis_update")

        # discord.on_guild_available(guild)
        HandlerManager.create_handler("discord_guild_available")

        # discord.on_guild_unavailable(guild)
        HandlerManager.create_handler("discord_guild_unavailable")

        # discord.on_voice_state_update(member, before, after)
        HandlerManager.create_handler("discord_voice_state_update")

        # discord.on_member_ban(guild, user)
        HandlerManager.create_handler("discord_member_ban")

        # discord.on_member_unban(guild, user)
        HandlerManager.create_handler("discord_member_unban")

        # discord.on_invite_create(invite)
        HandlerManager.create_handler("discord_invite_create")

        # discord.on_invite_delete(invite)
        HandlerManager.create_handler("discord_invite_delete")

        # discord.on_group_join(channel, user)
        HandlerManager.create_handler("discord_group_join")

        # discord.on_group_remove(channel, user)
        HandlerManager.create_handler("discord_group_remove")

        # discord.on_relationship_add(relationship)
        HandlerManager.create_handler("discord_relationship_add")

        # discord.on_relationship_remove(relationship)
        HandlerManager.create_handler("discord_relationship_remove")

        # discord.on_relationship_update(before, after)
        HandlerManager.create_handler("discord_relationship_update")

        #Twitter

        # tweepy.StreamListener.on_status(tweet)
        HandlerManager.create_handler("twitter_on_status")

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
        if event_name == "twitter_on_status":
            log.info("Trigger Complete")
        return True
