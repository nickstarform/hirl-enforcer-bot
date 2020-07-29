import asyncio
import discord
import datetime
import string
import time
from discord.ext import commands
import os, glob
from sys import exit, version
import argparse
from asyncio import get_event_loop
from logging import Formatter, INFO, StreamHandler, getLogger
import pickle
import json

__cwd__ = os.getcwd()
__version__ = float(version[:3])

print(f'Python Version: {__version__}, CWD: {__cwd__}')


class Config:
    def __init__(self, inp):
        self.base = dir(self)
        if isinstance(inp, dict):
            for key, value in inp.items():
                setattr(self, key, value)
        else:
            for key in dir(inp):
                if '__' not in key and key not in self.base:
                    setattr(self, key, getattr(inp, key))

    def to_dict(self):
        ret = {}
        for key in dir(self):
            if '__' not in key and key not in self.base:
                val = getattr(self, key)
                ret[key] = val if not isinstance(val, set) else list(val)
        return ret


def loader(basename):
    basename = basename.strip('.pkl').strip('.pickle')
    assert '.py' not in basename
    if '/' not in basename:
        basename = __cwd__ + '/' + basename
    listoffiles = glob.glob(f'{basename}.p*k*')
    fname = max(listoffiles, key=os.path.getctime)
    print(f'Running on file: {fname}')

    try:
        with open(fname, 'rb') as f:
            cf = pickle.load(f)
        cf['filename'] = basename
        save_py(basename, cf)
        return Config(cf)
    except Exception as e:
        print(f'Error loading pickle: {e}')
        return


def save_pkl(basename, cf):
    with open(basename + '.pickle', 'wb') as f:
        pickle.dump(cf, f)
    pass


def save_py(basename, cf):
    with open(basename + '.py', 'w') as f:
        for key, val in cf.items():
            if isinstance(val, str):
                val = f'''"""{val}"""'''
            f.write(f"""{key} = {val}\n""")
    pass


class Lewd(commands.Bot):
    def __init__(self, config, logger):
        """Initialization."""
        self._loaded_extensions = []
        self.start_time = datetime.datetime.utcnow()
        self.logger = logger
        self.status = ['with Python', 'prefix (.y.)']
        self.config = config
        self._members = {self.config.airl_guild_id, self.config.hirl_guild_id}
        prefix = '(.y.)' if 'prefix' not in dir(config) else config.prefix
        super().__init__(command_prefix=prefix)

    @classmethod
    async def get_instance(cls, config):
        """Generator for db/cache."""
        # setup logger
        logger = getLogger('lewd-bot')
        console_handler = StreamHandler()
        console_handler.setFormatter(Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))  # noqa
        logger.addHandler(console_handler)
        logger.setLevel(INFO)
        return cls(config, logger)

    async def on_ready(self):
        """Gather settings."""
        print('Bot Loading')
        self.hirl = self.get_guild(self.config.hirl_guild_id)
        self.airl = self.get_guild(self.config.airl_guild_id)
        for gid in self._members:
            print(f'Loading {gid}')
            guild = self.get_guild(gid)
            members = await self.fetch_members(guild)
            print(f'Loaded guild {guild.name} with {len(members)}')

    async def async_fetch_members(self, guild):
        members = []
        async for m in guild.fetch_members(limit=None):
            members.append(m)
        return members

    async def fetch_members(self, guild):
        if guild.chunked:
            print(f'Guild: {guild.name}| members: {len(guild.members)}')
            return guild.members
        else:
            members = await self.async_fetch_members(guild)
            print(f'Guild: {guild.name}| members: {len(members)}')
            return members


    async def on_message(self, message):
        if not await self.is_owner(message.author):
            return
        channel = message.channel
        if self.config.client in [f.id for f in message.mentions] and ('prefix' in message.content or 'help' in message.content):
            await channel.send(f'The bot prefix is {self.config.prefix}')
            return
        await self.process_commands(message)
        return

    def save_config(self):
        save_pkl(self.config.filename, self.config.to_dict())
        save_py(self.config.filename, self.config.to_dict())
        pass

    def refresh_config(self):
        cf = loader(self.config.filename)
        self.config = cf

async def shutdown(bot, *, reason=None):
    """Somewhat clean shutdown with basic debug info."""
    await bot.logout()

    print(f'\n\nShutting down due to {type(reason).__name__}...\n{"="*30}\n')
    print(f'{datetime.datetime.utcnow()} || UTC\n\nPython: {sys.version}\nPlatform: {sys.platform}/{os.name}\n'
          f'Discord: {discord.__version__}\n\n{"="*30}\n')

    await asyncio.sleep(1)

    if isinstance(reason, KeyboardInterrupt):
        sys.exit(1)  # Systemd will think it failed and restart our service cleanly.
    sys.exit(0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Startup the bot')
    parser.add_argument('--input', type=str, help='name of the config file', dest='input')
    args = parser.parse_args()
    if args.input:
        config = loader(args.input)
    else:
        exit(1)

    loop = get_event_loop()
    try:
        bot = loop.run_until_complete(Lewd.get_instance(config))
    except Exception as e:
        print('Error on startup:', str(e))
        _ = loop.run_until_complete(shutdown(bot, reason=e))
        exit(1)
    # bot.add_cog(Extension(bot))
    for cog in ['cogs.enforce', ]:
        bot.load_extension(cog)
        bot._loaded_extensions.append(cog)

    try:
        loop.run_until_complete(bot.run(config.token, reconnect=True))
    except KeyboardInterrupt as e:
        _ = loop.run_until_complete(shutdown(bot, reason=e))
        exit(1)

    client.run(config.token)

