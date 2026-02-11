#!/usr/bin/env python3
"""
FilterMate Discord Server Initializer
======================================
One-time setup script to bootstrap a Discord server for the FilterMate QGIS plugin community.

Usage:
    1. Create a Discord bot at https://discord.com/developers/applications
    2. Enable SERVER MEMBERS INTENT + MESSAGE CONTENT INTENT in the bot settings
    3. Invite the bot with Administrator permission:
       https://discord.com/oauth2/authorize?client_id=YOUR_BOT_ID&permissions=8&scope=bot
    4. Set environment variable:  export DISCORD_BOT_TOKEN="your-token-here"
    5. Run:  python discord_server_init.py --guild-id YOUR_SERVER_ID [--dry-run]

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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("filtermate-discord")

# ---------------------------------------------------------------------------
# Server blueprint
# ---------------------------------------------------------------------------

ROLES = [
    # (name, color_hex, hoist, mentionable, description)
    ("Admin", 0xE74C3C, True, False, "Server administrators"),
    ("Moderator", 0xE67E22, True, False, "Community moderators"),
    ("Contributor", 0x2ECC71, True, True, "Code / doc contributors"),
    ("Beta Tester", 0x9B59B6, True, True, "Early feature testers"),
    ("GIS Pro", 0x3498DB, False, True, "Professional GIS users"),
    ("Community", 0x95A5A6, False, False, "Default member role"),
]

# Each category is (name, channels) where channels are (name, type, topic, slowmode_seconds)
CATEGORIES = [
    (
        "WELCOME",
        [
            ("welcome", "text", "Start here — rules, roles, and introductions.", 0),
            ("rules", "text", "Server rules and code of conduct.", 0),
            ("roles", "text", "Pick your roles here.", 0),
            ("introductions", "text", "Tell us about yourself and your GIS work!", 60),
        ],
    ),
    (
        "ANNOUNCEMENTS",
        [
            ("announcements", "text", "Official FilterMate releases and news.", 0),
            ("changelog", "text", "Detailed changelog for each version.", 0),
            ("roadmap", "text", "Upcoming features and development priorities.", 0),
        ],
    ),
    (
        "SUPPORT",
        [
            ("general-help", "text", "Ask anything about FilterMate installation and usage.", 0),
            ("bug-reports", "text", "Report bugs — please include QGIS version, OS, and steps to reproduce.", 10),
            ("feature-requests", "text", "Suggest new features or improvements.", 30),
            ("qgis-tips", "text", "General QGIS tips and tricks from the community.", 0),
        ],
    ),
    (
        "DEVELOPMENT",
        [
            ("dev-general", "text", "Technical discussions about FilterMate development.", 0),
            ("architecture", "text", "Hexagonal architecture, design patterns, and code structure.", 0),
            ("pull-requests", "text", "PR discussions and code review coordination.", 0),
            ("ci-cd", "text", "CI/CD pipeline, testing, and release engineering.", 0),
            ("raster-panel", "text", "Raster dual-panel feature development.", 0),
        ],
    ),
    (
        "GIS COMMUNITY",
        [
            ("showcases", "text", "Share your maps, workflows, and FilterMate use cases!", 0),
            ("datasets", "text", "Open datasets, data sources, and format discussions.", 0),
            ("postgis", "text", "PostGIS, spatial SQL, and database topics.", 0),
            ("remote-sensing", "text", "Raster analysis, LiDAR, point clouds, and satellite imagery.", 0),
            ("cartography", "text", "Map design, symbology, and print layouts.", 0),
        ],
    ),
    (
        "BETA TESTING",
        [
            ("beta-announcements", "text", "New beta builds and testing instructions.", 0),
            ("beta-feedback", "text", "Report issues and share feedback on beta features.", 0),
        ],
    ),
    (
        "VOICE",
        [
            ("General Voice", "voice", None, 0),
            ("Dev Meeting", "voice", None, 0),
            ("Support Call", "voice", None, 0),
        ],
    ),
    (
        "OFF TOPIC",
        [
            ("off-topic", "text", "Anything not GIS-related. Keep it friendly!", 5),
            ("memes", "text", "GIS memes and fun stuff.", 10),
            ("bot-commands", "text", "Interact with bots here.", 0),
        ],
    ),
]

# Permissions to lock read-only channels
READ_ONLY_CHANNELS = {"welcome", "rules", "announcements", "changelog", "roadmap", "beta-announcements"}
BETA_ONLY_CHANNELS = {"beta-announcements", "beta-feedback"}
DEV_CHANNELS = {"dev-general", "architecture", "pull-requests", "ci-cd", "raster-panel"}

WELCOME_MESSAGE = """
# Welcome to the FilterMate Community! :earth_africa:

**FilterMate** is a powerful QGIS plugin for **advanced spatial filtering** — vector, raster, PostGIS and more.

## Quick Links
- **GitHub**: <https://github.com/imagodata/filter_mate>
- **Documentation**: <https://imagodata.github.io/filter_mate/>
- **YouTube**: <https://www.youtube.com/@imagodata>
- **Invite a friend**: <https://discord.gg/Z8hsCVndUd>
- **Bug Reports**: Use `#bug-reports` with your QGIS version, OS, and reproduction steps
- **Feature Requests**: Head to `#feature-requests`

## Getting Started
1. Read the `#rules`
2. Grab your roles in `#roles`
3. Say hi in `#introductions`
4. Ask questions in `#general-help`

## What FilterMate Does
- Multi-layer spatial filtering with an intuitive UI
- Attribute and geometry-based filter expressions
- PostGIS / SpatiaLite / GeoPackage support
- Raster layer info and value sampling *(new!)*
- Export filtered datasets in multiple formats

Happy filtering!
""".strip()

RULES_MESSAGE = """
# Server Rules

**1. Be Respectful**
Treat everyone with courtesy. No harassment, discrimination, or personal attacks.

**2. Stay On Topic**
Use the right channel for your message. Off-topic chat goes in `#off-topic`.

**3. No Spam**
No excessive posting, self-promotion, or unsolicited DMs.

**4. Search Before Asking**
Check existing messages and GitHub Issues before posting a new question.

**5. Bug Reports — Include Context**
When reporting a bug, always include:
- QGIS version and OS
- FilterMate version
- Steps to reproduce
- Error log if available (`View > Panels > Log Messages`)

**6. English Only**
To keep the community accessible, please use English in all public channels.

**7. No Piracy or Illegal Content**
Do not share pirated software, cracked plugins, or illegal datasets.

**8. Follow Discord TOS**
<https://discord.com/terms>

*Moderators reserve the right to warn, mute, or ban members who violate these rules.*
""".strip()

ROLES_MESSAGE = """
# Pick Your Roles

React to this message to get a role:

:hammer_pick: **GIS Pro** — Professional GIS user
:bug: **Beta Tester** — Test pre-release features
:wrench: **Contributor** — Active code or doc contributor

*Roles help us ping the right people and keep channels organized.*
""".strip()


# ---------------------------------------------------------------------------
# Init logic
# ---------------------------------------------------------------------------


class ServerInitializer:
    def __init__(self, guild: discord.Guild, dry_run: bool = False):
        self.guild = guild
        self.dry_run = dry_run
        self.created_roles: dict[str, discord.Role] = {}
        self.created_channels: dict[str, discord.abc.GuildChannel] = {}

    async def run(self):
        log.info("Initializing server: %s (id=%s) dry_run=%s", self.guild.name, self.guild.id, self.dry_run)

        await self.create_roles()
        await self.create_categories_and_channels()
        await self.set_channel_permissions()
        await self.post_welcome_messages()
        await self.configure_server_settings()

        log.info("Server initialization complete!")

    # -- Roles ---------------------------------------------------------------

    async def create_roles(self):
        existing = {r.name: r for r in self.guild.roles}

        for name, color, hoist, mentionable, _desc in ROLES:
            if name in existing:
                log.info("  Role '%s' already exists — skipping", name)
                self.created_roles[name] = existing[name]
                continue

            log.info("  Creating role: %s", name)
            if not self.dry_run:
                role = await self.guild.create_role(
                    name=name,
                    color=discord.Color(color),
                    hoist=hoist,
                    mentionable=mentionable,
                )
                self.created_roles[name] = role
            else:
                log.info("    [DRY RUN] would create role '%s'", name)

    # -- Categories and channels ---------------------------------------------

    async def create_categories_and_channels(self):
        existing_categories = {c.name.upper(): c for c in self.guild.categories}
        existing_channels = {c.name: c for c in self.guild.channels if not isinstance(c, discord.CategoryChannel)}

        for cat_name, channels in CATEGORIES:
            if cat_name in existing_categories:
                category = existing_categories[cat_name]
                log.info("  Category '%s' already exists", cat_name)
            else:
                log.info("  Creating category: %s", cat_name)
                if not self.dry_run:
                    category = await self.guild.create_category(cat_name)
                else:
                    category = None
                    log.info("    [DRY RUN] would create category '%s'", cat_name)

            for ch_name, ch_type, topic, slowmode in channels:
                if ch_name in existing_channels:
                    log.info("    Channel '#%s' already exists — skipping", ch_name)
                    self.created_channels[ch_name] = existing_channels[ch_name]
                    continue

                log.info("    Creating channel: #%s (%s)", ch_name, ch_type)
                if not self.dry_run:
                    if ch_type == "voice":
                        ch = await self.guild.create_voice_channel(name=ch_name, category=category)
                    else:
                        ch = await self.guild.create_text_channel(
                            name=ch_name,
                            category=category,
                            topic=topic,
                            slowmode_delay=slowmode,
                        )
                    self.created_channels[ch_name] = ch
                else:
                    log.info("      [DRY RUN] would create %s channel '#%s'", ch_type, ch_name)

    # -- Permissions ---------------------------------------------------------

    async def set_channel_permissions(self):
        everyone = self.guild.default_role
        beta_role = self.created_roles.get("Beta Tester")
        mod_role = self.created_roles.get("Moderator")
        admin_role = self.created_roles.get("Admin")

        for ch_name, channel in self.created_channels.items():
            if not isinstance(channel, discord.TextChannel):
                continue

            # Read-only channels: deny Send Messages for @everyone
            if ch_name in READ_ONLY_CHANNELS:
                log.info("  Locking #%s as read-only", ch_name)
                if not self.dry_run:
                    await channel.set_permissions(everyone, send_messages=False)
                    if mod_role:
                        await channel.set_permissions(mod_role, send_messages=True)
                    if admin_role:
                        await channel.set_permissions(admin_role, send_messages=True)

            # Beta-only channels: hidden from non-beta members
            if ch_name in BETA_ONLY_CHANNELS:
                log.info("  Restricting #%s to Beta Tester role", ch_name)
                if not self.dry_run:
                    await channel.set_permissions(everyone, view_channel=False)
                    if beta_role:
                        await channel.set_permissions(beta_role, view_channel=True)
                    if admin_role:
                        await channel.set_permissions(admin_role, view_channel=True)

    # -- Welcome messages ----------------------------------------------------

    async def post_welcome_messages(self):
        message_map = {
            "welcome": WELCOME_MESSAGE,
            "rules": RULES_MESSAGE,
            "roles": ROLES_MESSAGE,
        }

        for ch_name, content in message_map.items():
            channel = self.created_channels.get(ch_name)
            if channel and isinstance(channel, discord.TextChannel):
                log.info("  Posting message in #%s", ch_name)
                if not self.dry_run:
                    msg = await channel.send(content)
                    # Pin the message
                    try:
                        await msg.pin()
                    except discord.HTTPException:
                        log.warning("    Could not pin message in #%s", ch_name)
                else:
                    log.info("    [DRY RUN] would post and pin message in '#%s'", ch_name)

    # -- Server settings -----------------------------------------------------

    async def configure_server_settings(self):
        log.info("  Configuring server settings")
        if self.dry_run:
            log.info("    [DRY RUN] would update server icon, verification level, etc.")
            return

        try:
            await self.guild.edit(
                verification_level=discord.VerificationLevel.medium,
                default_notifications=discord.NotificationLevel.only_mentions,
                explicit_content_filter=discord.ContentFilter.all_members,
            )
        except discord.Forbidden:
            log.warning("    Missing permissions to edit server settings")


# ---------------------------------------------------------------------------
# Bot client
# ---------------------------------------------------------------------------


class InitBot(discord.Client):
    def __init__(self, guild_id: int, dry_run: bool):
        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True
        super().__init__(intents=intents)
        self.target_guild_id = guild_id
        self.dry_run = dry_run

    async def on_ready(self):
        log.info("Bot connected as %s", self.user)
        guild = self.get_guild(self.target_guild_id)
        if guild is None:
            log.error("Guild %s not found. Is the bot a member?", self.target_guild_id)
            await self.close()
            return

        try:
            initializer = ServerInitializer(guild, dry_run=self.dry_run)
            await initializer.run()
        except Exception:
            log.exception("Initialization failed")
        finally:
            await self.close()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Initialize FilterMate Discord server")
    parser.add_argument("--guild-id", type=int, required=True, help="Discord server (guild) ID")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying them")
    parser.add_argument("--token", type=str, default=None, help="Bot token (or set DISCORD_BOT_TOKEN env var)")
    args = parser.parse_args()

    token = args.token or os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: provide bot token via --token or DISCORD_BOT_TOKEN env var")
        sys.exit(1)

    bot = InitBot(guild_id=args.guild_id, dry_run=args.dry_run)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
