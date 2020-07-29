import asyncio
import discord
from discord.ext import commands
from discord.utils import snowflake_time
import random
import datetime
import re

reactions = {
    'yes': r'✅',
    'no': r'❌',
    True: r'🔔',
    False: r'🔕',
}


async def add_react(message, reacts: list=[]):
    for react in reacts:
        if react not in reactions:
            continue
        await message.add_reaction(reactions[react])


def check_staff(config, roles):
    return any([role.name.lower() in config.staff for role in roles])


def timediff(dt1, dt2):
    delta = dt2 - dt1 if dt2 > dt1 else dt1 - dt2
    micro = delta.microseconds
    micro += delta.seconds * 1e6
    micro += delta.days * 86400 * 1e6
    return micro / (1e6)


DISCORD = 'https://discordapp.com/invite/anime'

def is_owner():
    async def pred(ctx):
        return await ctx.bot.is_owner(ctx.author)
    return commands.check(pred)


class Enforce(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.__run = datetime.datetime(2001, 1, 1, 0, 0, 0)
        super().__init__()
        self.hirl = self.bot.get_guild(self.bot.config.hirl_guild_id)
        self.airl = self.bot.get_guild(self.bot.config.airl_guild_id)


    async def kick_member(self, member, guild):
        # build embed
        if isinstance(member, int):
            member = self.bot.get_user(member)
        if member.bot:
            return
        embed = discord.Embed(title = f"""You ({member.name}) have been kicked from {guild.name}""",
                              color=0xD01F00,
                              description=f'[Click here]({DISCORD}) to join the parent server.'
        )
        embed.set_footer(text=datetime.datetime.now())
        # send embed
        print(f'Kicking member {member.name}#{member.discriminator} | {member.id} for not being in parent guild.')
        if self.bot.config.testing:
            return
        if not member.dm_channel:
            await member.create_dm()
        try:
            channel = member.dm_channel
        except Exception as e:
            print(f'Error getting dm member: {member.id}, {e}')
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f'Error sending dm member: {member.id}, {e}')
        # kick
        if not self.bot.config.testing:
            try:
                await guild.kick(member.id)
                channel = guild.get_channel(self.bot.config.logchan)
                await channel.send(f'Kicked member {member.name}#{member.discriminator} | {member.id} for not being in parent guild.')
            except Exception as e:
                print(f'Error kicking member: {member.id}, {e}')

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != self.bot.hirl.id:
            return
        airlmembers, hirlmembers = await self.get_members()
        if len(airlmembers) > 0 and member not in airlmembers:
            # kick member from hirl
            await self.kick_member(member, self.bot.hirl)
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild.id == self.bot.airl.id:
            await self.kick_member(member, self.bot.hirl)

    @commands.Cog.listener()
    async def on_message(self, ctx):
        if ctx.author.bot:
            return
        if self.__run + datetime.timedelta(hours=24) < datetime.datetime.now():
            self.__run = datetime.datetime.now()
            # run check to compare and remove
            airlmembers, hirlmembers = await self.get_members()
            kicking = []
            for member in hirlmembers:
                if len(airlmembers) > 0 and member not in airlmembers:
                    kicking.append(member)
                    await self.kick_member(member, self.bot.hirl)
            print(f'kicked {len(kicking)}: {kicking}')

    @commands.command()
    @is_owner()
    async def runprune(self, ctx):
        """Check the current config.
        """
        if not await confirm(ctx, f"Which manually toggles the hirl prune. Test mode is {self.bot.config.testing}", 20):
            return
        await ctx.send('Pruning starting.... this might take a bit')
        airlmembers, hirlmembers = await self.get_members()
        kicking = []
        for member in hirlmembers:
            if len(airlmembers) > 0 and member not in airlmembers:
                kicking.append(member)
                await self.kick_member(member, self.bot.hirl)
            print(f'kicked {len(kicking)}: {kicking}')
        await ctx.send('Finished pruning')
    

    async def async_fetch_members(self, guild):
        members = []
        async for m in guild.fetch_members(limit=None):
            members.append(m.id)
        return members

    async def fetch_members(self, guild):
        if guild.chunked:
            print(f'Guild: {guild.name}| members: {len(guild.members)}')
            return [m.id for m in guild.members]
        else:
            members = await self.async_fetch_members(guild)
            print(f'Guild: {guild.name}| members: {len(members)}')
            return members

    async def get_members(self):
        members = []
        for guild in [self.bot.airl, self.bot.hirl]:
            members.append(await self.fetch_members(guild))
        return members

def setup(bot):
    bot.add_cog(Enforce(bot))
    print('Loaded Enforce')



async def confirm(ctx: commands.Context, message: str, timeout: int):
    """Generic confirmation embedder.

    Serves as a confirm/deny embed builder with a Xs timeout

    Parameters
    ----------
    ctx: :func: commands.Context
        the context command object
    message: str
        the message to display
    timeout: int
        the timeout in seconds before cancel

    Returns
    -------
    bool
        success true false
    """
    confirmdialog = f'\nAttempting to **{ctx.command}**:\n'\
                    f'{message}'\
                    f'\n➡️ Type `confirm` to **{ctx.command}**'\
                    ' or literally anything else to cancel.'\
                    f'\n\n**You have {timeout}s...**'
    embed = discord.Embed(title=r'❗ Confirmation Request ❗',
                            description=confirmdialog, color=0x9ED031)
    embed.set_footer(text=datetime.datetime.now())
    request = await ctx.send(embed=embed, delete_after=timeout)
    try:
        message = await ctx.bot.wait_for("message",
                                         timeout=timeout,
                                         check=lambda message:
                                         message.author == ctx.message.author)
    except asyncio.TimeoutError:
        try:
            await respond(ctx, False)
        except Exception:
            pass
        return False
    try:
        await respond(ctx, message.content.lower() == 'confirm')
        await request.delete()
        await message.delete()
    except Exception as e:
        print(f'Error in deleting message: {e}')
    return message.content.lower() == 'confirm'


async def respond(ctx: commands.Context, status: bool, message: discord.Message=None):
    """Respond/react to message.

    Parameters
    ----------
    ctx: :func: commands.Context
        the context command object
    status: bool
        status to react with

    Returns
    -------
    bool
        success true false
    """
    try:
        if status:
            if not isinstance(message, type(None)):
                await message.add_reaction(r'✅')
            else:
                await ctx.message.add_reaction(r'✅')
        else:
            if not isinstance(message, type(None)):
                await message.add_reaction(r'❌')
            else:
                await ctx.message.add_reaction(r'❌')
        return True
    except Exception as e:
        print(f'Error in responding to message message: {e}')
        return False
        pass