import logging

import json
import random
import asyncio
import operator
import regex as re
import discord
from datetime import datetime

from greenbot import utils
from greenbot.managers.schedule import ScheduleManager
from greenbot.managers.db import DBManager
from greenbot.managers.redis import RedisManager
from greenbot.models.command import Command
from greenbot.models.giveaway import Giveaway, GiveawayEntry
from greenbot.modules import BaseModule
from greenbot.modules import ModuleSetting

log = logging.getLogger(__name__)


class GiveawayModule(BaseModule):
    ID = __name__.split(".")[-1]
    NAME = "Giveaway"
    DESCRIPTION = "Create Giveaways"
    CATEGORY = "Feature"

    SETTINGS = [
        ModuleSetting(
            key="level",
            label="Level required to start and stop giveaways",
            type="number",
            placeholder="500",
            default=500,
        ),
        ModuleSetting(
            key="regular_role_id",
            label="Role ID for regular role",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="regular_role_tickets",
            label="Regular role tickets",
            type="number",
            placeholder="",
            default=5,
        ),
        ModuleSetting(
            key="tier1_sub_role_id",
            label="Role ID for tier 1 sub role",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="tier1_sub_role_tickets",
            label="Tier 1 sub role tickets",
            type="number",
            placeholder="",
            default=1,
        ),
        ModuleSetting(
            key="tier2_sub_role_id",
            label="Role ID for tier 2 sub role",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="tier2_sub_role_tickets",
            label="Tier 2 sub role tickets",
            type="number",
            placeholder="",
            default=2,
        ),
        ModuleSetting(
            key="tier3_sub_role_id",
            label="Role ID for tier 3 sub role",
            type="text",
            placeholder="",
            default="",
        ),
        ModuleSetting(
            key="tier3_sub_role_tickets",
            label="Tier 3 sub role tickets",
            type="number",
            placeholder="",
            default=4,
        ),
        ModuleSetting(
            key="valid_channels",
            label="Valid channels for typing commands",
            type="text",
            placeholder="",
            default="",
        ),
    ]

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot

    async def giveaway_info(self, bot, author, channel, message, args):
        embed = discord.Embed(
            description=("Giveaway Info"), colour=discord.Colour.dark_gold()
        )
        with DBManager.create_session_scope() as db_session:
            current_giveaway = Giveaway._get_current_giveaway(db_session)
            embed.add_field(
                name=("Current Giveaway"),
                value=f"**{current_giveaway.giveaway_item}** ending **{current_giveaway.giveaway_deadline}**" if current_giveaway else "No giveaway is running right now",
                inline=False,
            )
        role_dict = {
            "regular_role_id": self.settings["regular_role_tickets"], 
            "tier1_sub_role_id": self.settings["tier1_sub_role_tickets"], 
            "tier2_sub_role_id": self.settings["tier2_sub_role_tickets"], 
            "tier3_sub_role_id": self.settings["tier3_sub_role_tickets"],
        }
        role_dict = dict(sorted(role_dict.items(), key=operator.itemgetter(1)))
        chances_value = "@everyone 1 entry\n"
        for role_name in role_dict:
            role_id = self.settings[role_name]
            if not role_id:
                continue

            role = self.bot.filters.get_role([role_id], None, {})[0] if role_id else None
            if not role:
                continue
            entries = role_dict[role_name]
            chances_value += f"{role.mention} {entries} entr{'ies' if entries > 1 else 'y'}\n"
        embed.add_field(
            name=("Chances to win!"),
            value=chances_value[:-1],
            inline=False,
        )
        
        await self.bot.say(channel=channel, embed=embed)

    async def giveaway_join(self, bot, author, channel, message, args):
        with DBManager.create_session_scope() as db_session:
            current_giveaway = Giveaway._get_current_giveaway(db_session)
            if not current_giveaway:
                await self.bot.say(channel=channel, message=f"{author.mention}, there is no giveaway running right now.", ignore_escape=True)
                return False

            if current_giveaway.locked:
                await self.bot.say(channel=channel, message=f"{author.mention}, the current giveaway is locked.", ignore_escape=True)
                return False

            registered = GiveawayEntry.is_entered(db_session, str(author.id), current_giveaway.id)
            if registered:
                await self.bot.say(channel=channel, message=f"{author.mention}, you already joined the giveaway.", ignore_escape=True)
                return False

            tickets = self.get_highest_ticket_count(author)
            giveaway_entry = GiveawayEntry._create(db_session, str(author.id), current_giveaway.id, tickets)
            if giveaway_entry:
                await self.bot.say(channel=channel, message=f"{author.mention}, you joined the giveaway for **{current_giveaway.giveaway_item}** with **{tickets}** entr{'y' if tickets == 1 else 'ies' }! The giveaway will end **{current_giveaway.giveaway_deadline}** and you will be notified if you win. Good Luck! :wink:", ignore_escape=True)
                return True

            await self.bot.say(channel=channel, message=f"{author.mention} failed to add you to the giveaway dm a mod for help :smile:", ignore_escape=True)
            return False

    def get_highest_ticket_count(self, member):
        role_dict = {
            "regular_role_id": self.settings["regular_role_tickets"], 
            "tier1_sub_role_id": self.settings["tier1_sub_role_tickets"], 
            "tier2_sub_role_id": self.settings["tier2_sub_role_tickets"], 
            "tier3_sub_role_id": self.settings["tier3_sub_role_tickets"],
        }
        role_dict = dict(sorted(role_dict.items(), key=operator.itemgetter(1)))

        tickets = 1
        for role_name in role_dict:
            role_id = self.settings[role_name]
            if not role_id:
                continue

            role = self.bot.filters.get_role([role_id], None, {})[0] if role_id else None
            if not role:
                continue

            tickets = max(tickets, role_dict[role_name]) if role and role in member.roles else tickets

        return tickets

    async def giveaway_start(self, bot, author, channel, message, args):
        with DBManager.create_session_scope() as db_session:
            current_giveaway = Giveaway._get_current_giveaway(db_session)
            if current_giveaway:
                await self.bot.say(channel=channel, message="There is already a giveaway running. Please use !wipegiveaway before you start a new one. (Don't forget to chose a winner before you end!)", ignore_escape=True)
                return False

            desc_array = re.findall(r'"([^"]*)"', message)
            if not len(desc_array) == 2:
                await self.bot.say(channel=channel, message='Please set 2 arguments between quotation marks. `!startgiveaway "<item>" "<deadline>"`\nExample: `!startgiveaway "a new GTX2900" "10 days"`', ignore_escape=True)
                return False

            if Giveaway._create(db_session, str(author.id), desc_array[0], desc_array[1]):
                await self.bot.say(channel=channel, message="New giveaway was started! Use !giveawaywinner to chose a winner when the time has passed.", ignore_escape=True)
                return True

            await self.bot.say(channel=channel, message="An unknown error has occurred, please contact a moderator", ignore_escape=True)
            return False

    async def giveaway_wipe(self, bot, author, channel, message, args):
        with DBManager.create_session_scope() as db_session:
            current_giveaway = Giveaway._get_current_giveaway(db_session)
            if not current_giveaway:
                await self.bot.say(channel=channel, message="There is no giveaway running.")
                return False
            current_giveaway._disable(db_session)
        await self.bot.say(channel=channel, message="The current giveaway has been wiped")
        return True

    async def giveaway_winner(self, bot, author, channel, message, args):
        args_split = message.split(" ")
        try:
            count = int(args_split[0])
        except:
            count = 1

        with DBManager.create_session_scope() as db_session:
            current_giveaway = Giveaway._get_current_giveaway(db_session)
            if not current_giveaway:
                await self.bot.say(channel=channel, message="There is no giveaway running.")
                return False

            if not current_giveaway.locked:
                current_giveaway._lock_state(db_session, True)
                db_session.commit()
            pool = []
            for entry in current_giveaway.entries:
                member = self.bot.filters.get_member([int(entry.user_id)], None, {})[0]
                for _ in range(max(entry.tickets, self.get_highest_ticket_count(member))):
                    pool.append(entry)

            winning_users = []
            while len(winning_users) < count:
                if len(pool) == 0:
                    break
                winning_entry = random.choice(pool)
                winning_user = self.bot.filters.get_member([int(winning_entry.user_id)], None, {})[0]
                if winning_user and winning_user not in winning_users:
                    winning_users.append(winning_user)
                    winning_entry._remove(db_session)
                    pool = list(filter(lambda x: x != winning_entry, pool))

            if len(winning_users) == 0:
                await self.bot.say(channel=channel, message="The giveaway ended but nobody entered!", ignore_escape=True)
                return True

            await self.bot.say(channel=channel, message="Shuffling giveaway list...", ignore_escape=True)
            await asyncio.sleep(5)
            await self.bot.say(channel=channel, message="*Shuffling intensifies...*", ignore_escape=True)
            await asyncio.sleep(5)
            await self.bot.say(channel=channel, message=f"**And the winner{'s are' if count > 1 else ' is'}...**", ignore_escape=True)
            await asyncio.sleep(5)
            for winning_user in winning_users:
                await self.bot.say(channel=channel, message=f"Congratulations {winning_user.mention} you won **{current_giveaway.giveaway_item}**!!!", ignore_escape=True)

        return True

    
    async def giveaway_lock(self, bot, author, channel, message, args):
        with DBManager.create_session_scope() as db_session:
            current_giveaway = Giveaway._get_current_giveaway(db_session)
            if not current_giveaway:
                await self.bot.say(channel=channel, message="There is no giveaway running.")
                return False

            if current_giveaway.locked:
                await self.bot.say(channel=channel, message="The current giveaway has already been locked")
                return False

            current_giveaway.locked = True
        await self.bot.say(channel=channel, message="The current giveaway has been locked")
        return True

    async def giveaway_unlock(self, bot, author, channel, message, args):
        with DBManager.create_session_scope() as db_session:
            current_giveaway = Giveaway._get_current_giveaway(db_session)
            if not current_giveaway:
                await self.bot.say(channel=channel, message="There is no giveaway running.")
                return False

            if not current_giveaway.locked:
                await self.bot.say(channel=channel, message="The current giveaway is not locked")
                return False

            current_giveaway.locked = False
        await self.bot.say(channel=channel, message="The current giveaway has been unlocked")
        return True 

    def load_commands(self, **options):
        self.commands["giveaway"] = Command.multiaction_command(
            delay_all=0,
            delay_user=0,
            default="join",
            can_execute_with_whisper=False,
            command="giveaway",
            commands={
                "join": Command.raw_command(
                    self.giveaway_join,
                    command="giveaway join",
                    delay_all=0,
                    delay_user=0,
                    channels=json.dumps(self.settings["valid_channels"].split(" ")),
                    can_execute_with_whisper=False,
                    description="Joins the current giveaway",
                ),
                "info": Command.raw_command(
                    self.giveaway_info,
                    command="giveaway info",
                    delay_all=0,
                    delay_user=0,
                    channels=json.dumps(self.settings["valid_channels"].split(" ")),
                    can_execute_with_whisper=False,
                    description="Info about the current giveaway",
                )
            },
        )
        self.commands["startgiveaway"] = Command.raw_command(
            self.giveaway_start,
            command="startgiveaway",
            delay_all=0,
            delay_user=0,
            level=self.settings["level"],
            channels=json.dumps(self.settings["valid_channels"].split(" ")),
            can_execute_with_whisper=False,
            description="Start a giveaway",
        )
        self.commands["wipegiveaway"] = Command.raw_command(
            self.giveaway_wipe,
            command="wipegiveaway",
            delay_all=0,
            delay_user=0,
            level=self.settings["level"],
            channels=json.dumps(self.settings["valid_channels"].split(" ")),
            can_execute_with_whisper=False,
            description="Clears the current giveaway",
        )
        self.commands["giveawaywinner"] = Command.raw_command(
            self.giveaway_winner,
            command="giveawaywinner",
            delay_all=0,
            delay_user=0,
            level=self.settings["level"],
            channels=json.dumps(self.settings["valid_channels"].split(" ")),
            can_execute_with_whisper=False,
            description="Chooses a winner(s) for the current giveaway",
        )
        self.commands["lockgiveaway"] = Command.raw_command(
            self.giveaway_lock,
            command="lockgiveaway",
            delay_all=0,
            delay_user=0,
            level=self.settings["level"],
            channels=json.dumps(self.settings["valid_channels"].split(" ")),
            can_execute_with_whisper=False,
            description="Locks the current giveaway",
        )
        self.commands["unlockgiveaway"] = Command.raw_command(
            self.giveaway_unlock,
            command="unlockgiveaway",
            delay_all=0,
            delay_user=0,
            level=self.settings["level"],
            channels=json.dumps(self.settings["valid_channels"].split(" ")),
            can_execute_with_whisper=False,
            description="Unlocks the current giveaway",
        )

    def enable(self, bot):
        if not bot:
            return

    def disable(self, bot):
        if not bot:
            return
