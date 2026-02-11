#!/usr/bin/env python3
"""
FilterMate Discord Server Reset
================================
Wipes all channels, categories, and custom roles from a Discord server,
then recreates everything from the blueprint defined in discord_server_init.py.

Usage:
    1. Ensure the bot has Administrator permission on the server
    2. Enable SERVER MEMBERS INTENT in the developer portal
    3. Set environment variable:  export DISCORD_BOT_TOKEN="your-token-here"
    4. Run:  python discord_server_reset.py --guild-id YOUR_SERVER_ID [--dry-run]

    Without --yes, the script will ask for interactive confirmation before wiping.

Requirements:
    pip install discord.py>=2.3
"""

import argparse
import asyncio
import logging
import os
import sys

try:
    import discord
except ImportError:
    print("discord.py is required. Install with:  pip install discord.py>=2.3")
    sys.exit(1)

# Re-use the blueprint from the init script
from discord_server_init import (
    CATEGORIES,
    ROLES,
    READ_ONLY_CHANNELS,
    BETA_ONLY_CHANNELS,
    WELCOME_MESSAGE,
    RULES_MESSAGE,
    ROLES_MESSAGE,
    ServerInitializer,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("filtermate-discord-reset")


# ---------------------------------------------------------------------------
# Reset logic
# ---------------------------------------------------------------------------


class ServerResetter:
    """Deletes all user-created channels, categories, and roles, then reinitializes."""

    # Roles that must never be deleted
    PROTECTED_ROLE_NAMES = {"@everyone"}

    def __init__(self, guild: discord.Guild, dry_run: bool = False):
        self.guild = guild
        self.dry_run = dry_run

    async def run(self):
        log.info(
            "=== RESET server: %s (id=%s) dry_run=%s ===",
            self.guild.name,
            self.guild.id,
            self.dry_run,
        )

        await self.delete_all_channels()
        await self.delete_custom_roles()

        log.info("--- Wipe complete. Rebuilding from blueprint... ---")

        initializer = ServerInitializer(self.guild, dry_run=self.dry_run)
        await initializer.run()

        log.info("=== Reset complete! ===")

    # -- Delete channels & categories ----------------------------------------

    async def delete_all_channels(self):
        """Delete every channel and category in the guild."""
        # Delete non-category channels first, then categories
        channels = [ch for ch in self.guild.channels if not isinstance(ch, discord.CategoryChannel)]
        categories = list(self.guild.categories)

        log.info("Deleting %d channels...", len(channels))
        for ch in channels:
            log.info("  Deleting channel: #%s (%s)", ch.name, ch.__class__.__name__)
            if not self.dry_run:
                try:
                    await ch.delete(reason="FilterMate server reset")
                except discord.Forbidden:
                    log.warning("    Missing permission to delete #%s", ch.name)
                except discord.HTTPException as e:
                    log.warning("    Failed to delete #%s: %s", ch.name, e)

        log.info("Deleting %d categories...", len(categories))
        for cat in categories:
            log.info("  Deleting category: %s", cat.name)
            if not self.dry_run:
                try:
                    await cat.delete(reason="FilterMate server reset")
                except discord.Forbidden:
                    log.warning("    Missing permission to delete category '%s'", cat.name)
                except discord.HTTPException as e:
                    log.warning("    Failed to delete category '%s': %s", cat.name, e)

    # -- Delete roles --------------------------------------------------------

    async def delete_custom_roles(self):
        """Delete all roles except @everyone and the bot's own managed roles."""
        bot_top_role = self.guild.me.top_role if self.guild.me else None

        deletable = []
        for role in self.guild.roles:
            # Never touch @everyone
            if role.name in self.PROTECTED_ROLE_NAMES:
                continue
            # Never touch managed roles (bot roles, integrations, boosts)
            if role.managed:
                continue
            # Can't delete roles higher than or equal to the bot's top role
            if bot_top_role and role >= bot_top_role:
                log.info("  Skipping role '%s' (higher than bot's top role)", role.name)
                continue
            deletable.append(role)

        log.info("Deleting %d custom roles...", len(deletable))
        for role in deletable:
            log.info("  Deleting role: %s", role.name)
            if not self.dry_run:
                try:
                    await role.delete(reason="FilterMate server reset")
                except discord.Forbidden:
                    log.warning("    Missing permission to delete role '%s'", role.name)
                except discord.HTTPException as e:
                    log.warning("    Failed to delete role '%s': %s", role.name, e)


# ---------------------------------------------------------------------------
# Bot client
# ---------------------------------------------------------------------------


class ResetBot(discord.Client):
    def __init__(self, guild_id: int, dry_run: bool, skip_confirm: bool):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        super().__init__(intents=intents)
        self.target_guild_id = guild_id
        self.dry_run = dry_run
        self.skip_confirm = skip_confirm

    async def on_ready(self):
        log.info("Bot connected as %s", self.user)
        guild = self.get_guild(self.target_guild_id)
        if guild is None:
            log.error("Guild %s not found. Is the bot a member?", self.target_guild_id)
            await self.close()
            return

        # Safety summary
        channels_count = len(guild.channels)
        roles_count = len([r for r in guild.roles if r.name != "@everyone" and not r.managed])
        members_count = guild.member_count or "?"

        log.warning("========================================")
        log.warning("  SERVER: %s", guild.name)
        log.warning("  Channels to delete: %d", channels_count)
        log.warning("  Roles to delete:    %d", roles_count)
        log.warning("  Members:            %s", members_count)
        log.warning("========================================")

        if self.dry_run:
            log.info("[DRY RUN] No changes will be made.")
        elif not self.skip_confirm:
            # Ask for confirmation in the terminal
            log.warning("This will DELETE ALL channels and roles, then recreate from blueprint.")
            try:
                answer = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: input("Type 'RESET' to confirm: ")
                )
            except EOFError:
                answer = ""
            if answer.strip() != "RESET":
                log.info("Aborted by user.")
                await self.close()
                return

        try:
            resetter = ServerResetter(guild, dry_run=self.dry_run)
            await resetter.run()
        except Exception:
            log.exception("Reset failed")
        finally:
            await self.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Reset FilterMate Discord server")
    parser.add_argument("--guild-id", type=int, required=True, help="Discord server (guild) ID")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying them")
    parser.add_argument("--yes", action="store_true", help="Skip interactive confirmation (dangerous!)")
    parser.add_argument("--token", type=str, default=None, help="Bot token (or set DISCORD_BOT_TOKEN env var)")
    args = parser.parse_args()

    token = args.token or os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: provide bot token via --token or DISCORD_BOT_TOKEN env var")
        sys.exit(1)

    bot = ResetBot(guild_id=args.guild_id, dry_run=args.dry_run, skip_confirm=args.yes)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
