#!/usr/bin/env python3
"""Posts the updated welcome message in #welcome (deletes old bot messages first)."""

import logging
import os
import sys

try:
    import discord
except ImportError:
    print("discord.py is required.")
    sys.exit(1)

from discord_server_init import WELCOME_MESSAGE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("filtermate-discord-welcome")


class WelcomeUpdateBot(discord.Client):
    def __init__(self, guild_id: int):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)
        self.target_guild_id = guild_id

    async def on_ready(self):
        log.info("Bot connected as %s", self.user)
        guild = self.get_guild(self.target_guild_id)
        if guild is None:
            log.error("Guild not found.")
            await self.close()
            return

        channel = discord.utils.get(guild.text_channels, name="welcome")
        if channel is None:
            log.error("#welcome not found.")
            await self.close()
            return

        try:
            # Delete previous bot messages in #welcome
            deleted = 0
            async for msg in channel.history(limit=50):
                if msg.author == self.user:
                    await msg.delete()
                    deleted += 1
            log.info("Deleted %d old bot messages in #welcome", deleted)

            # Post and pin new welcome message
            msg = await channel.send(WELCOME_MESSAGE)
            try:
                await msg.pin()
                log.info("New welcome message posted and pinned in #welcome")
            except discord.HTTPException:
                log.warning("Posted but could not pin")
        except Exception:
            log.exception("Failed")
        finally:
            await self.close()


def main():
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: set DISCORD_BOT_TOKEN env var")
        sys.exit(1)
    guild_id = int(sys.argv[1]) if len(sys.argv) > 1 else None
    if not guild_id:
        print("Usage: python discord_update_welcome.py GUILD_ID")
        sys.exit(1)
    bot = WelcomeUpdateBot(guild_id=guild_id)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
