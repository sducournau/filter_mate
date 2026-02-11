#!/usr/bin/env python3
"""Create a permanent Discord invite link via the bot."""

import logging
import os
import sys

try:
    import discord
except ImportError:
    print("discord.py is required. Install with:  pip install discord.py>=2.3")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("filtermate-discord-invite")


class InviteBot(discord.Client):
    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)
        self.target_guild_id = guild_id

    async def on_ready(self):
        log.info("Bot connected as %s", self.user)
        guild = self.get_guild(self.target_guild_id)
        if guild is None:
            log.error("Guild %s not found.", self.target_guild_id)
            await self.close()
            return

        # Try to find #welcome, fallback to first text channel
        channel = None
        for ch in guild.text_channels:
            if ch.name == "welcome":
                channel = ch
                break
        if channel is None and guild.text_channels:
            channel = guild.text_channels[0]

        if channel is None:
            log.error("No text channel found to create invite.")
            await self.close()
            return

        try:
            invite = await channel.create_invite(max_age=0, max_uses=0, unique=False)
            log.info("Invite created: %s", invite.url)
            # Print just the URL to stdout for scripting
            print(invite.url)
        except discord.Forbidden:
            log.error("Bot lacks CREATE_INSTANT_INVITE permission.")
            # List bot permissions for debugging
            me = guild.me
            if me:
                perms = channel.permissions_for(me)
                log.info("Bot permissions in #%s: create_instant_invite=%s, manage_channels=%s, administrator=%s",
                         channel.name, perms.create_instant_invite, perms.manage_channels, perms.administrator)
        except discord.HTTPException as e:
            log.error("Failed to create invite: %s", e)
        finally:
            await self.close()


def main():
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: set DISCORD_BOT_TOKEN env var")
        sys.exit(1)

    guild_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if not guild_id:
        print("Usage: python discord_create_invite.py GUILD_ID")
        sys.exit(1)

    bot = InviteBot(guild_id=guild_id)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
