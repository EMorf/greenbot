import logging
import json
import discord
import datetime

from greenbot.managers.db import DBManager
from greenbot.managers.handler import HandlerManager
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting
from greenbot.models.message import Message

import greenbot.utils as utils 

log = logging.getLogger(__name__)


class AdvancedAdminLog(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "AdvancedAdminLog"
    DESCRIPTION = "Logs Everything"
    CATEGORY = "Feature"

    SETTINGS = [
        ModuleSetting(
            key="ingore_channels",
            label="Channels to ignore for message edit/delete seperated by a space",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="output_channel",
            label="Channels to send logs to",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(key="log_edit_message", label="Log Edit Message Event", type="boolean", placeholder="", default=True),
        ModuleSetting(key="log_delete_message", label="Log Delete Message Event", type="boolean", placeholder="", default=True),
        ModuleSetting(key="log_member_update", label="Log Member Update Event", type="boolean", placeholder="", default=True),
        ModuleSetting(key="log_member_update_nickname", label="Log Member Update Nickname Event", type="boolean", placeholder="", default=True),
        ModuleSetting(key="log_role_update", label="Log Role Update Event", type="boolean", placeholder="", default=True),
        ModuleSetting(key="log_role_create", label="Log Role Create Event", type="boolean", placeholder="", default=True),
        ModuleSetting(key="log_voice_change", label="Log Role Create Event", type="boolean", placeholder="", default=True),
        ModuleSetting(key="log_member_join", label="Log Role Create Event", type="boolean", placeholder="", default=True),
        ModuleSetting(key="log_member_remove", label="Log Role Create Event", type="boolean", placeholder="", default=True),
        ModuleSetting(key="log_channel_update", label="Log Channel Update Event", type="boolean", placeholder="", default=True),
        ModuleSetting(key="log_channel_create", label="Log Channel Create Event", type="boolean", placeholder="", default=True),
        ModuleSetting(key="log_channel_delete", label="Log Channel Delete Event", type="boolean", placeholder="", default=True),
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    async def message_delete(self, payload):
        if not self.settings["log_delete_message"]:
            return
        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        message_id = payload.message_id
        with DBManager.create_session_scope() as db_session:
            db_message = Message._get(db_session, message_id)
            if not db_message:
                return
            content = json.loads(db_message.content)
            author_id = db_message.user_id
        sent_in_channel, _ = await self.bot.functions.func_get_channel(args=[int(payload.channel_id)])
        author = self.bot.discord_bot.get_member(int(author_id))
        embed = discord.Embed(
            description=content[-1],
            colour=discord.Colour.red(),
            timestamp=utils.now()
        )

        embed.add_field(name="Channel", value=sent_in_channel)
        action = discord.AuditLogAction.message_delete
        perp = None
        async for _log in self.bot.discord_bot.guild.audit_logs(limit=2, action=action):
            log.info(_log)
            same_chan = _log.extra.channel.id == sent_in_channel.id
            if _log.target.id == int(author_id) and same_chan:
                perp = f"{_log.user}({_log.user.id})"
                break
        if perp:
            embed.add_field(name="Deleted by", value=perp)
        embed.set_footer(text="User ID: " + str(author_id))
        embed.set_author(
            name=f"{author} ({author.id})- Deleted Message",
            icon_url=str(author.avatar_url),
        )
        await self.bot.say(channel, embed=embed)

    async def message_edit(self, payload):
        if not self.settings["log_edit_message"]:
            return
        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        sent_in_channel, _ = await self.bot.functions.func_get_channel(args=[int(payload.data["channel_id"])])
        if not channel:
            log.error("Channel not found")
            return
        channels = self.settings["ingore_channels"].split(" ") if self.settings["ingore_channels"] != "" else []
        if len(channels) > 0 and sent_in_channel not in channels:
            return
        message_id = payload.message_id
        guild_id = payload.data.get("guild_id", None)
        
        message = await sent_in_channel.fetch_message(int(message_id))
        if not guild_id or self.bot.discord_bot.guild.id != int(guild_id):
            return

        with DBManager.create_session_scope() as db_session:
            db_message = Message._get(db_session, str(message_id))
            if not db_message:
                return
            content = json.loads(db_message.content)
            author_id = db_message.user_id
        author = self.bot.discord_bot.get_member(int(author_id))
        if int(author_id) == self.bot.discord_bot.client.user.id:
            return
        embed = discord.Embed(
            description=f"Old Message: {content[-2]}",
            colour=discord.Colour.red(),
            timestamp=utils.now()
        )
        jump_url = f"[Click to see new message]({message.jump_url})"
        embed.add_field(name="After Message:", value=jump_url)
        embed.add_field(name="Channel:", value=sent_in_channel.mention)
        embed.set_footer(text="User ID: " + str(author.id))
        embed.set_author(
            name=f"{author} ({author.id}) - Edited Message",
            icon_url=str(author.avatar_url),
        )
        await self.bot.say(channel, embed=embed)

    async def member_update(self, before, after):
        if not self.settings["log_member_update"]:
            return
        guild = before.guild
        if guild != self.bot.discord_bot.guild:
            return

        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        embed = discord.Embed(colour=discord.Color.green(), timestamp=utils.now())
        emb_msg = f"{before} ({before.id}) updated"
        embed.set_author(name=emb_msg, icon_url=before.avatar_url)
        member_updates = {"nick": "Nickname:", "roles": "Roles:"}
        perp = None
        reason = None
        worth_sending = False
        for attr, name in member_updates.items():
            if attr == "nick" and not self.settings["log_member_update"]:
                continue
            before_attr = getattr(before, attr)
            after_attr = getattr(after, attr)
            if before_attr != after_attr:
                worth_sending = True
                if attr == "roles":
                    b = set(before.roles)
                    a = set(after.roles)
                    before_roles = [list(b - a)][0]
                    after_roles = [list(a - b)][0]
                    if before_roles:
                        for role in before_roles:
                            embed.description = role.mention + " Role removed."
                    if after_roles:
                        for role in after_roles:
                            embed.description = role.mention + " Role applied."
                        action = discord.AuditLogAction.member_role_update
                        async for log in self.bot.discord_bot.guild.audit_logs(limit=5, action=action):
                            if log.target.id == before.id:
                                perp = log.user
                                if log.reason:
                                    reason = log.reason
                                break
                else:
                    action = discord.AuditLogAction.member_update
                    async for log in self.bot.discord_bot.guild.audit_logs(limit=5, action=action):
                        if log.target.id == before.id:
                            perp = log.user
                            if log.reason:
                                reason = log.reason
                            break
                    embed.add_field(name="Before " + name, value=str(before_attr)[:1024])
                    embed.add_field(name="After " + name, value=str(after_attr)[:1024])
        if not worth_sending:
            return
        if perp:
            embed.add_field(name="Updated by ", value=perp.mention)
        if reason:
            embed.add_field(name="Reason", value=reason)
        await self.bot.say(channel=channel, embed=embed)
        
    async def role_update(self, before, after):
        if not self.settings["log_role_update"]:
            return
        guild = before.guild
        if guild != self.bot.discord_bot.guild:
            return
        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        perp = None
        reason = None
        action = discord.AuditLogAction.role_update
        async for log in guild.audit_logs(limit=5, action=action):
            if log.target.id == before.id:
                perp = log.user
                if log.reason:
                    reason = log.reason
                break
        embed = discord.Embed(description=after.mention, colour=after.colour, timestamp=utils.now())
        if after is guild.default_role:
            embed.set_author(name="Updated @everyone role ")
        else:
            embed.set_author(
                name=f"Updated {before.name} ({before.id}) role "
            )
        if perp:
            embed.add_field(name="Updated by ", value=perp.mention)
        if reason:
            embed.add_field(name="Reason ", value=reason)
        role_updates = {
            "name": "Name:",
            "color": "Colour:",
            "mentionable": "Mentionable:",
            "hoist": "Is Hoisted:",
        }
        worth_updating = False
        for attr, name in role_updates.items():
            before_attr = getattr(before, attr)
            after_attr = getattr(after, attr)
            if before_attr != after_attr:
                worth_updating = True
                if before_attr == "":
                    before_attr = "None"
                if after_attr == "":
                    after_attr = "None"
                embed.add_field(name="Before " + name, value=str(before_attr))
                embed.add_field(name="After " + name, value=str(after_attr))
        p_msg = await self.get_role_permission_change(before, after)
        if p_msg != "":
            worth_updating = True
            embed.add_field(name="Permissions", value=p_msg[:1024])
        if not worth_updating:
            return
        await self.bot.say(channel=channel, embed=embed)

    async def role_create(self, role):
        if not self.settings["log_role_create"]:
            return
        guild = role.guild
        if guild != self.bot.discord_bot.guild:
            return
        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        perp = None
        reason = None
        action = discord.AuditLogAction.role_create
        async for log in guild.audit_logs(limit=5, action=action):
            if log.target.id == role.id:
                perp = log.user
                if log.reason:
                    reason = log.reason
                break
        embed = discord.Embed(
            description=role.mention,
            colour=role.colour,
            timestamp=utils.now(),
        )
        embed.set_author(
            name=f"Role created {role.name} ({role.id})"
        )
        if perp:
            embed.add_field(name="Created by", value=perp.mention)
        if reason:
            embed.add_field(name="Reason ", value=reason)
        await self.bot.say(channel=channel, embed=embed)

    async def role_delete(self, role):
        if not self.settings["log_role_create"]:
            return
        guild = role.guild
        if guild != self.bot.discord_bot.guild:
            return
        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        perp = None
        reason = None
        action = discord.AuditLogAction.role_create
        async for log in guild.audit_logs(limit=5, action=action):
            if log.target.id == role.id:
                perp = log.user
                if log.reason:
                    reason = log.reason
                break
        embed = discord.Embed(
            description=role.name,
            colour=role.colour,
            timestamp=utils.now(),
        )
        embed.set_author(
            name=f"Role deleted {role.name} ({role.id})"
        )
        if perp:
            embed.add_field(name="Deleted by", value=perp.mention)
        if reason:
            embed.add_field(name="Reason ", value=reason)
        await self.bot.say(channel=channel, embed=embed)
    
    async def voice_change(self, member, before, after):
        if not self.settings["log_voice_change"]:
            return
        guild = before.guild
        if guild != self.bot.discord_bot.guild:
            return
        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        embed = discord.Embed(
            timestamp=utils.now(), colour=discord.Colour.gold(),
        )
        embed.set_author(
            name=f"{member} ({member.id}) Voice State Update"
        )
        change_type = None
        worth_updating = False
        if before.deaf != after.deaf:
            worth_updating = True
            change_type = "deaf"
            if after.deaf:
                embed.description = member.mention + " was deafened. "
            else:
                embed.description = member.mention + " was undeafened. "
        if before.mute != after.mute:
            worth_updating = True
            change_type = "mute"
            if after.mute:
                embed.description = member.mention + " was muted. "
            else:
                embed.description = chan_msg = member.mention + " was unmuted. "
        if before.channel != after.channel:
            worth_updating = True
            change_type = "channel"
            if before.channel is None:
                embed.description = member.mention + " has joined " + after.channel.name
            elif after.channel is None:
                embed.description = member.mention + " has left " + before.channel.name
            else:
                embed.description = chan_msg = (
                    member.mention
                    + " has moved from "
                    + before.channel.name
                    + " to "
                    + after.channel.name
                )
        if not worth_updating:
            return
        perp = None
        reason = None
        action = discord.AuditLogAction.member_update
        async for log in guild.audit_logs(limit=5, action=action):
            is_change = getattr(log.after, change_type, None)
            if log.target.id == member.id and is_change:
                perp = log.user
                if log.reason:
                    reason = log.reason
                break
        if perp:
            embed.add_field(name="Updated by", value=perp.mention)
        if reason:
            embed.add_field(name="Reason ", value=reason)
        await self.bot.say(channel=channel, embed=embed)

    async def member_join(self, member):
        if not self.settings["log_member_join"]:
            return
        guild = member.guild
        if guild != self.bot.discord_bot.guild:
            return
        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        users = len(guild.members)
        created_at = member.created_at.replace(tzinfo=datetime.timezone.utc)
        since_created = (utils.now() - created_at).days
        user_created = created_at.strftime("%d %b %Y %H:%M")

        created_on = f"{user_created}\n({since_created} days ago)"

        embed = discord.Embed(
            description=member.mention,
            colour=discord.Color.gold(),
            timestamp=member.joined_at if member.joined_at else utils.now(),
        )
        embed.add_field(name="Total Users:", value=str(users))
        embed.add_field(name="Account created on:", value=created_on)
        embed.set_footer(text="User ID: " + str(member.id))
        embed.set_author(
            name=f"{member} ({member.id}) has joined the guild"
            url=member.avatar_url,
            icon_url=member.avatar_url,
        )
        embed.set_thumbnail(url=member.avatar_url)
        await self.bot.say(channel=channel, embed=embed)

    async def member_remove(self, member):
        if not self.settings["log_member_remove"]:
            return
        guild = member.guild
        if guild != self.bot.discord_bot.guild:
            return
        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])

        embed = discord.Embed(
            description=member.mention,
            colour=discord.Color.gold(),
            timestamp=utils.now(),
        )
        perp = None
        reason = None
        banned = False
        action = discord.AuditLogAction.kick
        async for log in guild.audit_logs(limit=5, action=action):
            if log.target.id == member.id:
                perp = log.user
                reason = log.reason
                break
        if not perp:
            action = discord.AuditLogAction.ban
            async for log in guild.audit_logs(limit=5, action=action):
                if log.target.id == member.id:
                    perp = log.user
                    reason = log.reason
                    banned = True
                    break
        embed.add_field(name="Total Users:", value=str(len(guild.members)))
        if perp:
            embed.add_field(name="Kicked By" if not banned else "Banned By", value=perp.mention)
        if reason:
            embed.add_field(name="Reason", value=str(reason))
        embed.set_footer(text="User ID: " + str(member.id))
        embed.set_author(
            name=f"{member} ({member.id}) has left the guild"
            url=member.avatar_url,
            icon_url=member.avatar_url,
        )
        embed.set_thumbnail(url=member.avatar_url)
        await self.bot.say(channel=channel, embed=embed)

    async def channel_update(self, before, after):
        if not self.settings["log_channel_update"]:
            return
        guild = before.guild
        if guild != self.bot.discord_bot.guild:
            return
        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        channel_type = str(after.type).title()
        embed = discord.Embed(
            description=after.mention,
            timestamp=utils.now(),
            colour=discord.Colour.gold(),
        )
        embed.set_author(
            name="{channel_type} Channel Updated {before.name} ({before.id})"
        )
        perp = None
        reason = None
        worth_updating = False
        action = discord.AuditLogAction.channel_update
        async for log in guild.audit_logs(limit=5, action=action):
            if log.target.id == before.id:
                perp = log.user
                if log.reason:
                    reason = log.reason
                break
        if type(before) == discord.TextChannel:
            text_updates = {
                "name": "Name:",
                "topic": "Topic:",
                "category": "Category:",
                "slowmode_delay": "Slowmode delay:",
            }

            for attr, name in text_updates.items():
                before_attr = getattr(before, attr)
                after_attr = getattr(after, attr)
                if before_attr != after_attr:
                    worth_updating = True
                    if before_attr == "":
                        before_attr = "None"
                    if after_attr == "":
                        after_attr = "None"
                    embed.add_field(name="Before " + name, value=str(before_attr)[:1024])
                    embed.add_field(name="After " + name, value=str(after_attr)[:1024])
            if before.is_nsfw() != after.is_nsfw():
                worth_updating = True
                embed.add_field(name="Before " + "NSFW", value=str(before.is_nsfw()))
                embed.add_field(name="After " + "NSFW", value=str(after.is_nsfw()))
            p_msg = await self.get_permission_change(before, after)
            if p_msg != "":
                worth_updating = True
                embed.add_field(name="Permissions", value=p_msg[:1024])

        if type(before) == discord.VoiceChannel:
            voice_updates = {
                "name": "Name:",
                "position": "Position:",
                "category": "Category:",
                "bitrate": "Bitrate:",
                "user_limit": "User limit:",
            }
            for attr, name in voice_updates.items():
                before_attr = getattr(before, attr)
                after_attr = getattr(after, attr)
                if before_attr != after_attr:
                    worth_updating = True
                    embed.add_field(name="Before " + name, value=str(before_attr))
                    embed.add_field(name="After " + name, value=str(after_attr))
            p_msg = await self.get_permission_change(before, after)
            if p_msg != "":
                worth_updating = True
                embed.add_field(name="Permissions", value=p_msg[:1024])

        if perp:
            embed.add_field(name="Updated by ", value=perp.mention)
        if reason:
            embed.add_field(name="Reason ", value=reason)
        if not worth_updating:
            return
        await self.bot.say(channel=channel, embed=embed)

    async def channel_create(self, channel):
        if not self.settings["log_channel_create"]:
            return
        guild = channel.guild
        if guild != self.bot.discord_bot.guild:
            return
        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        channel_type = str(channel.type).title()
        embed = discord.Embed(
            description=f"{channel.mention} {channel.name}",
            timestamp=utils.now(),
            colour=discord.Colour.gold(),
        )
        embed.set_author(
            name=f"{channel_type} Channel Created {channel.name} ({channel.id})"
        )
        perp = None
        reason = None
        action = discord.AuditLogAction.channel_create
        async for log in guild.audit_logs(limit=2, action=action):
            if log.target.id == channel.id:
                perp = log.user
                if log.reason:
                    reason = log.reason
                break
        embed.add_field(name="Type", value=channel_type)
        if perp:
            embed.add_field(name="Created by ", value=perp.mention)
        if reason:
            embed.add_field(name="Reason ", value=reason)
        await self.bot.say(channel=channel, embed=embed)

    async def channel_delete(self, channel):
        if not self.settings["log_channel_delete"]:
            return
        guild = channel.guild
        if guild != self.bot.discord_bot.guild:
            return
        channel, _ = await self.bot.functions.func_get_channel(args=[int(self.settings["output_channel"])])
        channel_type = str(channel.type).title()
        embed = discord.Embed(
            description=f"{channel.mention} {channel.name}",
            timestamp=utils.now(),
            colour=discord.Colour.gold(),
        )
        embed.set_author(
            name=f"{channel_type} Channel Deleted {channel.name} ({channel.id})"
        )
        perp = None
        reason = None
        action = discord.AuditLogAction.channel_delete
        async for log in guild.audit_logs(limit=2, action=action):
            if log.target.id == channel.id:
                perp = log.user
                if log.reason:
                    reason = log.reason
                break
        embed.add_field(name="Type", value=channel_type)
        if perp:
            embed.add_field(name="Deleted by ", value=perp.mention)
        if reason:
            embed.add_field(name="Reason ", value=reason)
        await self.bot.say(channel=channel, embed=embed)

    async def get_permission_change(self, before, after):
        p_msg = ""
        before_perms = {}
        after_perms = {}
        for o, p in before.overwrites.items():
            before_perms[str(o.id)] = [i for i in p]
        for o, p in after.overwrites.items():
            after_perms[str(o.id)] = [i for i in p]
        for entity in before_perms:
            entity_obj = before.guild.get_role(int(entity))
            if not entity_obj:
                entity_obj = before.guild.get_member(int(entity))
            if entity not in after_perms:
                p_msg += f"{entity_obj.mention} Overwrites removed.\n"
                continue
            if after_perms[entity] != before_perms[entity]:
                a = set(after_perms[entity])
                b = set(before_perms[entity])
                a_perms = list(a - b)
                for diff in a_perms:
                    p_msg += f"{entity_obj.mention} {diff[0]} Set to {diff[1]}\n"
        for entity in after_perms:
            entity_obj = after.guild.get_role(int(entity))
            if not entity_obj:
                entity_obj = after.guild.get_member(int(entity))
            if entity not in before_perms:
                p_msg += f"{entity_obj.mention} Overwrites added.\n"
                continue
        return p_msg

    async def get_role_permission_change(self, before, after):
        permission_list = [
            "create_instant_invite",
            "kick_members",
            "ban_members",
            "administrator",
            "manage_channels",
            "manage_guild",
            "add_reactions",
            "view_audit_log",
            "priority_speaker",
            "read_messages",
            "send_messages",
            "send_tts_messages",
            "manage_messages",
            "embed_links",
            "attach_files",
            "read_message_history",
            "mention_everyone",
            "external_emojis",
            "connect",
            "speak",
            "mute_members",
            "deafen_members",
            "move_members",
            "use_voice_activation",
            "change_nickname",
            "manage_nicknames",
            "manage_roles",
            "manage_webhooks",
            "manage_emojis",
        ]
        p_msg = ""
        for p in permission_list:
            if getattr(before.permissions, p) != getattr(after.permissions, p):
                change = getattr(after.permissions, p)
                p_msg += f"{p} Set to {change}\n"
        return p_msg

    def enable(self, bot):
        if not bot:
            return

        HandlerManager.add_handler("discord_raw_message_edit", self.message_edit)
        HandlerManager.add_handler("discord_raw_message_delete", self.message_delete)
        HandlerManager.add_handler("discord_member_update", self.member_update)
        HandlerManager.add_handler("discord_guild_role_update", self.role_update)
        HandlerManager.add_handler("discord_guild_role_create", self.role_create)
        HandlerManager.add_handler("discord_guild_role_delete", self.role_delete)
        HandlerManager.add_handler("discord_voice_state_update", self.voice_change)
        HandlerManager.add_handler("discord_member_remove", self.member_remove)
        HandlerManager.add_handler("discord_member_join", self.member_join)
        HandlerManager.add_handler("discord_guild_channel_update", self.channel_update)
        HandlerManager.add_handler("discord_guild_channel_create", self.channel_create)
        HandlerManager.add_handler("discord_guild_channel_delete", self.channel_delete)

    def disable(self, bot):
        if not bot:
            return

        HandlerManager.remove_handler("discord_raw_message_edit", self.message_edit)
        HandlerManager.remove_handler("discord_raw_message_delete", self.message_delete)
        HandlerManager.remove_handler("discord_member_update", self.member_update)
        HandlerManager.remove_handler("discord_guild_role_update", self.role_update)
        HandlerManager.remove_handler("discord_guild_role_create", self.role_create)
        HandlerManager.remove_handler("discord_guild_role_delete", self.role_delete)
        HandlerManager.remove_handler("discord_voice_state_update", self.voice_change)
        HandlerManager.remove_handler("discord_member_remove", self.member_remove)
        HandlerManager.remove_handler("discord_member_join", self.member_join)
        HandlerManager.remove_handler("discord_guild_channel_update", self.channel_update)
        HandlerManager.remove_handler("discord_guild_channel_create", self.channel_create)
        HandlerManager.remove_handler("discord_guild_channel_delete", self.channel_delete)
