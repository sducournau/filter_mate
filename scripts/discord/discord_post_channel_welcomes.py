#!/usr/bin/env python3
"""
FilterMate Discord Channel Welcome Messages
=============================================
Posts a pinned welcome message in each text channel to explain its purpose
and set expectations for the conversation.

Usage:
    export DISCORD_BOT_TOKEN="your-token-here"
    python discord_post_channel_welcomes.py --guild-id YOUR_SERVER_ID [--dry-run]

Requirements:
    pip install discord.py>=2.3
"""

import argparse
import logging
import os
import sys

try:
    import discord
except ImportError:
    print("discord.py is required. Install with:  pip install discord.py>=2.3")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("filtermate-discord-welcomes")

# ---------------------------------------------------------------------------
# Channel welcome messages
# ---------------------------------------------------------------------------
# Channels already handled by discord_server_init.py (welcome, rules, roles)
# are excluded — they already have their own pinned messages.

CHANNEL_WELCOMES = {
    # ── WELCOME ────────────────────────────────────────────────────────────
    "introductions": """
# :wave: Introductions

Welcome aboard! This is the place to say hello and tell us a bit about yourself.

**Feel free to share:**
- Your name or handle
- Where you're based
- What you do with GIS (job, research, hobby…)
- How you discovered FilterMate
- What you hope to get from this community

Don't be shy — every GIS journey is interesting! :earth_africa:
""".strip(),

    # ── ANNOUNCEMENTS ──────────────────────────────────────────────────────
    "announcements": """
# :mega: Announcements

This is the official channel for **FilterMate news**.

You'll find here:
- New version releases and download links
- Major feature announcements
- Community milestones
- Event and meeting notices

This channel is **read-only** — discussions go in `#general-help` or `#dev-general`.
""".strip(),

    "changelog": """
# :scroll: Changelog

Detailed release notes for every FilterMate version.

Each entry covers:
- New features and enhancements
- Bug fixes
- Breaking changes (if any)
- Minimum QGIS version requirements

Looking for the latest release? Check [GitHub Releases](https://github.com/imagodata/filter_mate/releases).
""".strip(),

    "roadmap": """
# :world_map: Roadmap

A look at what's coming next for FilterMate.

This channel tracks:
- Upcoming features and priorities
- Development milestones and timelines
- Strategic direction and long-term vision

Want to influence the roadmap? Share your ideas in `#feature-requests`!
""".strip(),

    # ── SUPPORT ────────────────────────────────────────────────────────────
    "general-help": """
# :raising_hand: General Help

Need help with FilterMate? You're in the right place.

**Before posting, please check:**
- The [documentation](https://imagodata.github.io/filter_mate/)
- Existing messages in this channel — your question may already be answered

**When asking a question, include:**
- Your QGIS version (`Help > About`)
- Your OS (Windows, macOS, Linux)
- FilterMate version (`Plugins > Manage Plugins`)
- What you're trying to do and what happens instead

The community and maintainers are here to help! :handshake:
""".strip(),

    "bug-reports": """
# :bug: Bug Reports

Found something broken? Report it here so we can fix it.

**Please include:**
1. **QGIS version** and **OS**
2. **FilterMate version**
3. **Steps to reproduce** — what exactly did you do?
4. **Expected behavior** — what should have happened?
5. **Actual behavior** — what happened instead?
6. **Error log** (if available): `View > Panels > Log Messages` in QGIS

For confirmed bugs, we may ask you to open a [GitHub Issue](https://github.com/imagodata/filter_mate/issues).
""".strip(),

    "feature-requests": """
# :bulb: Feature Requests

Have an idea to make FilterMate better? We'd love to hear it.

**A good feature request includes:**
- **What** you'd like to do (the goal, not the solution)
- **Why** it matters for your workflow
- **Context** — dataset type, layer count, data source…

Popular requests get prioritized on the `#roadmap`. The more detail and use cases you provide, the better we can evaluate and plan.
""".strip(),

    "qgis-tips": """
# :mortar_board: QGIS Tips & Tricks

A community space for sharing QGIS knowledge beyond FilterMate.

**Great topics for this channel:**
- Useful keyboard shortcuts
- Expression tricks and custom functions
- Print layout techniques
- Plugin recommendations
- Processing toolbox workflows
- Performance tips for large datasets

Share what you know, ask what you don't! :books:
""".strip(),

    # ── DEVELOPMENT ────────────────────────────────────────────────────────
    "dev-general": """
# :hammer_and_wrench: Dev General

The main channel for FilterMate development discussions.

**Topics:**
- Implementation questions and code discussions
- Development environment setup
- Debugging sessions
- Release planning and coordination

**Repo**: <https://github.com/imagodata/filter_mate>
**Stack**: Python, PyQt5, QGIS API, hexagonal architecture
""".strip(),

    "architecture": """
# :classical_building: Architecture

Deep dives into FilterMate's code structure and design decisions.

**Topics:**
- Hexagonal architecture (ports & adapters)
- Multi-backend system (PostgreSQL, SpatiaLite, OGR, Memory)
- Domain model and service layer design
- Performance optimization strategies
- Code patterns and conventions

This is where we discuss the *why* behind the code, not just the *how*.
""".strip(),

    "pull-requests": """
# :twisted_rightwards_arrows: Pull Requests

Coordination channel for code reviews and PR discussions.

**Workflow:**
1. Open a PR on [GitHub](https://github.com/imagodata/filter_mate/pulls)
2. Post a summary here for visibility
3. Discuss approach, request reviews
4. Merge once approved

Please keep PR-specific technical discussions in the GitHub PR comments — use this channel for coordination and high-level review.
""".strip(),

    "ci-cd": """
# :gear: CI/CD

Everything about our continuous integration and delivery pipeline.

**Topics:**
- GitHub Actions workflows
- Test suite status and coverage
- Release packaging and deployment
- Plugin repository publishing
- Build issues and debugging

Current stack: GitHub Actions, pytest, QGIS plugin repository.
""".strip(),

    "raster-panel": """
# :artificial_satellite: Raster Panel

Dedicated channel for the **raster dual-panel** feature development.

This is where we discuss:
- Raster-vector integration architecture
- Value sampling, histograms, and band viewer
- Zonal statistics as filter (the differentiator)
- Raster export and clipping
- UI/UX for the raster exploring panel

Dev branch: `refactor/quick-wins-2026-02-10`
See `#announcements` for the public roadmap.
""".strip(),

    # ── GIS COMMUNITY ─────────────────────────────────────────────────────
    "showcases": """
# :frame_photo: Showcases

Show off your work! This is the place to share maps, workflows, and creative uses of FilterMate.

**Share anything:**
- Screenshots of your filtered maps
- Before/after comparisons
- Workflow descriptions
- Export results
- Integration with other tools

Seeing real-world use cases helps everyone learn and inspires new features. Don't hesitate to post! :sparkles:
""".strip(),

    "datasets": """
# :floppy_disk: Datasets

Discuss and share open data sources for GIS work.

**Great topics:**
- Open data portals (IGN, OSM, Copernicus, USGS…)
- Dataset recommendations for specific use cases
- File format tips (GeoPackage, Shapefile, GeoJSON, COG…)
- Data quality and preprocessing advice
- API endpoints for spatial data

Sharing is caring — if you found a great dataset, tell us about it!
""".strip(),

    "postgis": """
# :elephant: PostGIS

All things PostGIS, spatial SQL, and database-driven GIS.

**Topics:**
- Spatial queries and indexing
- PostGIS + FilterMate integration tips
- Database schema design for spatial data
- Performance tuning and `EXPLAIN ANALYZE`
- SpatiaLite and GeoPackage discussions too!

FilterMate supports PostGIS as a first-class backend — share your SQL tricks here.
""".strip(),

    "remote-sensing": """
# :satellite: Remote Sensing

Raster analysis, satellite imagery, LiDAR, point clouds, and more.

**Topics:**
- Satellite imagery sources and processing
- NDVI, spectral indices, and band math
- LiDAR and point cloud workflows
- DEM/DTM analysis
- Raster-vector integration with FilterMate

As FilterMate expands into raster support, this channel will become increasingly relevant! :rocket:
""".strip(),

    "cartography": """
# :art: Cartography

Map design, symbology, and visual communication.

**Topics:**
- Symbology and color ramp design
- Print layout techniques
- Label placement strategies
- Atlas generation
- Cartographic conventions and best practices
- Exporting for print vs. web

Beautiful maps tell better stories — share your design tips and ask for feedback!
""".strip(),

    # ── BETA TESTING ───────────────────────────────────────────────────────
    "beta-announcements": """
# :test_tube: Beta Announcements

New pre-release builds and testing instructions are posted here.

Each beta announcement includes:
- Download link or branch name
- What's new in this build
- Known issues
- What to test and how to report back

This channel is **read-only** — share your feedback in `#beta-feedback`.
""".strip(),

    "beta-feedback": """
# :clipboard: Beta Feedback

Thank you for being a beta tester! Your feedback shapes FilterMate.

**When reporting an issue:**
1. Which beta build are you testing?
2. What did you do? (steps to reproduce)
3. What happened? (actual behavior)
4. What did you expect? (expected behavior)
5. Screenshots or logs if possible

**Positive feedback is welcome too!** Tell us what works well, what feels intuitive, and what you'd like to see more of.
""".strip(),

    # ── OFF TOPIC ──────────────────────────────────────────────────────────
    "off-topic": """
# :speech_balloon: Off Topic

A space to chat about anything that isn't GIS-related. Keep it friendly and respectful!

Tech, music, games, food, travel — whatever's on your mind. Just follow the server `#rules`.
""".strip(),

    "memes": """
# :laughing: Memes

GIS humor, map fails, projection jokes, and general fun.

*"There are only two hard problems in GIS: projections, edge cases, and off-by-one errors."*

Share your best finds! Keep it SFW and respectful.
""".strip(),

    "bot-commands": """
# :robot: Bot Commands

Use this channel to interact with server bots without cluttering other channels.

Test commands, check bot features, and have fun experimenting here.
""".strip(),
}


# ---------------------------------------------------------------------------
# Bot client
# ---------------------------------------------------------------------------


class WelcomeBot(discord.Client):
    def __init__(self, guild_id: int, dry_run: bool):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)
        self.target_guild_id = guild_id
        self.dry_run = dry_run

    async def on_ready(self):
        log.info("Bot connected as %s", self.user)
        guild = self.get_guild(self.target_guild_id)
        if guild is None:
            log.error("Guild %s not found.", self.target_guild_id)
            await self.close()
            return

        try:
            await self.post_welcomes(guild)
        except Exception:
            log.exception("Failed to post welcome messages")
        finally:
            await self.close()

    async def post_welcomes(self, guild: discord.Guild):
        channels = {ch.name: ch for ch in guild.text_channels}
        posted = 0
        skipped = 0

        for ch_name, content in CHANNEL_WELCOMES.items():
            channel = channels.get(ch_name)
            if not channel:
                log.warning("  Channel #%s not found — skipping", ch_name)
                skipped += 1
                continue

            log.info("  Posting welcome in #%s", ch_name)
            if not self.dry_run:
                try:
                    msg = await channel.send(content)
                    await msg.pin()
                    posted += 1
                except discord.Forbidden:
                    log.warning("    No permission to post in #%s", ch_name)
                    skipped += 1
                except discord.HTTPException as e:
                    log.warning("    Failed in #%s: %s", ch_name, e)
                    skipped += 1
            else:
                log.info("    [DRY RUN] would post %d chars", len(content))
                posted += 1

        log.info("Done! Posted: %d, Skipped: %d", posted, skipped)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Post welcome messages in all FilterMate Discord channels")
    parser.add_argument("--guild-id", type=int, required=True, help="Discord server (guild) ID")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--token", type=str, default=None, help="Bot token (or set DISCORD_BOT_TOKEN env var)")
    args = parser.parse_args()

    token = args.token or os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: provide bot token via --token or DISCORD_BOT_TOKEN env var")
        sys.exit(1)

    bot = WelcomeBot(guild_id=args.guild_id, dry_run=args.dry_run)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
