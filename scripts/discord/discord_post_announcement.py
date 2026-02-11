#!/usr/bin/env python3
"""
FilterMate Discord Announcement Poster
=======================================
Posts formatted announcements to #announcements, #showcases, and #raster-panel.

Usage:
    export DISCORD_BOT_TOKEN="your-token-here"
    python discord_post_announcement.py --guild-id YOUR_SERVER_ID [--dry-run]
    python discord_post_announcement.py --guild-id YOUR_SERVER_ID --only videos [--dry-run]
    python discord_post_announcement.py --guild-id YOUR_SERVER_ID --only raster [--dry-run]

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
log = logging.getLogger("filtermate-discord-announce")

# ---------------------------------------------------------------------------
# Raster announcement content
# ---------------------------------------------------------------------------

# Split into chunks to stay under Discord's 2000-char limit per message.
RASTER_ANNOUNCEMENT_PARTS = [
    """
# :satellite: Raster Support is Coming to FilterMate

We're excited to share what's cooking on our development branch — **full raster-vector integration** is on its way to FilterMate!

## What's Being Built

FilterMate has always been about powerful **vector filtering**. Now we're extending that philosophy to **raster layers**, bridging the gap between vector and raster workflows directly inside QGIS.

### :white_check_mark: Already Working (dev branch)

- **Dual-Mode Panel** — Automatic vector/raster detection with a toggle switch. Select a raster layer and the UI adapts instantly.
- **Layer Info** — Raster metadata at a glance: bands, resolution, extent, CRS, data type, no-data values.
- **Raster Value Sampling** — Sample raster values at vector feature locations and filter by predicate. *"Show me all buildings where elevation > 500m."*
- **Interactive Histogram** — Per-band histogram with range sliders and real-time preview.
- **Band Viewer** — Band table with preset compositions (True Color, CIR, NDVI…) and spectral index formulas.
""".strip(),
    """
### :construction: Coming Next

| Feature | What It Does | Status |
|---------|-------------|--------|
| **Zonal Stats as Filter** | Filter vectors by raster stats under geometry | In design |
| **Raster-Driven Highlighting** | Real-time highlight as you adjust range sliders | Planned |
| **Raster Clip & Export** | Export raster clipped by filtered vector selection | Planned |
| **Multi-Band Composite** | Filter on multiple bands with AND/OR operators | Roadmap |

## :dart: Why This Matters

**Zonal Stats as Filter** is a game-changer — no other QGIS plugin does interactive zonal-statistics-based filtering with undo/redo support. Think of it as bringing the power of `QgsZonalStatistics` directly into FilterMate's filtering workflow.

## :wrench: Technical Highlights

- Built on FilterMate's **hexagonal architecture** — clean separation of domain, infrastructure, and UI
- **Thread-safe** raster processing (layers recreated in worker threads, never shared)
- Smart CRS handling — automatic reprojection of vector geometries to raster CRS
- Uses `pointOnSurface()` instead of `centroid()` for accurate sampling on concave polygons
- **235 unit tests** already covering the new code
""".strip(),
    """
## :calendar: Tentative Roadmap

```
v5.5 (March 2026)
  - Raster Value Sampling (foundation)
  - Raster Clip & Export

v5.6 (April 2026)
  - Zonal Stats as Filter (the differentiator)
  - Raster-Driven Highlighting

v6.0 (Q2-Q3 2026)
  - Multi-Band Composite Filtering
  - Object Detection (template matching, SAM integration)
```

## :speech_balloon: Get Involved

- **Beta testers wanted!** — Head to `#beta-feedback` to sign up for early access
- **Feature requests** — Tell us what raster workflows matter most to you in `#feature-requests`
- **Developers** — Branch `refactor/quick-wins-2026-02-10` on [GitHub](https://github.com/sducournau/filter_mate). PRs welcome in `#pull-requests`
- **Deep dive** — Technical discussions in `#raster-panel`

Stay tuned — this is just the beginning of FilterMate's raster journey! :rocket:
""".strip(),
]

DEV_CHANNEL_TEASER = """
# :satellite: Raster Branch Status Update

The `refactor/quick-wins-2026-02-10` branch now includes:

**New files (15+):**
- `core/domain/raster_filter_criteria.py` — Frozen dataclass for raster filter predicates
- `core/tasks/raster_sampling_task.py` — Thread-safe raster sampling worker
- `infrastructure/raster/` — sampling, histogram, band_utils modules
- `ui/controllers/raster_exploring_controller.py` — 1300-line raster panel controller
- `ui/widgets/dual_mode_toggle.py` — Segment control for vector/raster switch
- `ui/widgets/raster_histogram_widget.py` — Interactive histogram with matplotlib

**Stats:** +22,294 lines added, -4,493 removed across 205 files.

**Architecture decisions:**
- Orchestrator-Handler pattern for FilterEngineTask decomposition
- Context Object for shared state (inspired by QGIS Processing)
- Hexagonal ports for raster infrastructure (sampling, zonal stats, masking)

Full discussion and review coordination here. See `#announcements` for the user-facing summary.
""".strip()

# ---------------------------------------------------------------------------
# Technical bulletin content (audit & refactoring results)
# ---------------------------------------------------------------------------

TECHNICAL_ANNOUNCEMENT_PARTS = [
    """
# :wrench: FilterMate v4.4.6 — Technical Bulletin

Hello everyone!

Here is a complete progress update on FilterMate.

## AUDIT & MAJOR REFACTORING

**Quality score: 6.5/10 --> 8.5/10 (+30%)**

19 commits on main, covering 4 phases:

### P0 - Tests restored
- 311 unit tests in 18 files (was: 0)
- Working pytest configuration

### P1 - Quick Wins
- 8 handlers extracted and restored
- AutoOptimizer unified, critical bug fixed (it was silently broken)
- Dead code removed: -659 lines (legacy_adapter + compat)
""".strip(),
    """
### P2 - God Classes decomposition
- **filter_task.py**: 5,884 --> 3,970 lines (-32%)
  - ExpressionFacadeHandler extracted (-197 lines)
  - MaterializedViewHandler extracted (-411 lines)
- **dockwidget.py**: 7,130 --> 6,504 lines (-8.8%)
  - 4 managers extracted (DockwidgetSignalManager, etc.)
- SignalBlocker systematized: 24 occurrences, 9 files

### P3 - Security & Robustness
- qgisMinimumVersion: 3.0 --> 3.22
- CRS_UTILS_AVAILABLE removed (6 files, -48 lines)
- except Exception: 39 --> 8 safety nets in filter_task (annotated)
- sanitize_sql_identifier applied to 30+ identifiers (1 CRITICAL PK bug fixed)
- Missing f-strings fixed in SQL templates
""".strip(),
    """
## KEY FIGURES

| Metric | Before | After |
|---|---|---|
| Quality score | 6.5/10 | 8.5/10 |
| Unit tests | 0 | 311 |
| filter_task.py | 5,884 lines | 3,970 lines |
| dockwidget.py | 7,130 lines | 6,504 lines |
| except Exception | ~80 | 8 (annotated) |
| Unsecured SQL | ~30 | 0 |
| Auto-optimizer | Broken | Working |
""".strip(),
    """
## BACKLOG RASTER & POINT CLOUD V1

The backlog for Raster and Point Cloud support has been developed:

- 8 EPICs, 17 User Stories, 5 sprints
- Estimate: 55-75 development days

### Priorities:
- **MUST**: R0 (raster foundations) --> R1 (sampling) --> R2 (zonal stats -- unique differentiator)
- **SHOULD**: R3 (raster highlight) + PC1 (point cloud classification/attributes/Z)
- **COULD**: R4 (raster clip) + PC2 (advanced PDAL)

Sprint 0 is ready: US-R0.1 (cherry-pick foundations) and US-R0.2 (pass 3 refactoring) can be parallelized.
""".strip(),
    """
## i18n — TRANSLATION STATUS

FilterMate supports 22 languages with 450 translated messages per language:
am, da, de, en, es, fi, fr, hi, id, it, nb, nl, pl, pt, ru, sl, sv, tl, tr, uz, vi, zh

All .ts and .qm files are present. French and English are 100% complete.

Recent fix: 19 user-facing strings wrapped in `tr()`/`QCoreApplication.translate()` across 5 files.

## NEXT STEPS

1. **filter_task.py Pass 3**: target < 3,000 lines (2-3 days)
2. **Dockwidget Phase 2**: extract ~700 additional lines (3-5 days)
3. **Sprint 0 Raster**: foundations + cherry-pick (parallelizable with refactoring)
4. **Integration tests**: 4 backends (PostgreSQL, SpatiaLite, GeoPackage, OGR)
5. **CI/CD**: automated pytest pipeline

Questions or suggestions? Feel free to react! :point_down:
""".strip(),
]

# ---------------------------------------------------------------------------
# Video tutorials content
# ---------------------------------------------------------------------------

# Split into chunks to stay under Discord's 2000-char limit per message.
VIDEOS_ANNOUNCEMENT_PARTS = [
    """
# :clapper: FilterMate Video Tutorials — Learn by Watching

We've published a series of video tutorials showcasing FilterMate's core capabilities on real-world datasets. Whether you're just getting started or looking to master advanced workflows, these walkthroughs have you covered.

:point_right: **YouTube channel**: <https://www.youtube.com/@imagodata>
""".strip(),
    """
### :one: Getting Started — Classic Multi-Step Filtering
> *How to build multi-step attribute filters on IGN's BD TOPO dataset.*

Learn the fundamentals: select a layer, pick attributes, chain multiple filter criteria, and watch your map update in real time. A perfect starting point for new users.

:film_frames: https://www.youtube.com/watch?v=oQq45xZkzDc
""".strip(),
    """
### :two: Spatial Filtering — Roads and Surrounding Features
> *Filter road networks and automatically select nearby features.*

Discover how FilterMate combines attribute filtering with spatial queries. Filter a road by name, then use geometry-based filtering to grab every feature within a given distance.

:film_frames: https://www.youtube.com/watch?v=P0G2x-ggtVQ
""".strip(),
    """
### :three: Intuitive Exploration — Filter from a Map Selection
> *Select features on the map, then use them as a filter source across multiple layers.*

Skip the forms — just click on the map. This video shows how to use an interactive selection to drive filtering across your entire project, making data exploration fast and visual.

:film_frames: https://www.youtube.com/watch?v=YwEalDjgEdY
""".strip(),
    """
### :four: Deep Exploration — Major Road Networks and Connected Areas
> *Explore large road datasets and filter areas connected to your selection.*

A more advanced workflow: start from a road network, drill down into classification attributes, and propagate your filter to connected administrative or land-use layers.

:film_frames: https://www.youtube.com/watch?v=svElL8cDpWE
""".strip(),
    """
### :five: Geometry Filters — Negative Buffer with Attribute Selection
> *Apply a -500m negative buffer combined with multi-attribute filtering on BD TOPO.*

See how FilterMate handles geometry transformations as part of the filtering pipeline. Apply a negative buffer to shrink polygons, combine it with attribute criteria, and preview results live.

:film_frames: https://www.youtube.com/watch?v=9rZb-9A-tko
""".strip(),
    """
### :six: Export Workflow — Filtered Data to GeoPackage with Styles
> *Export a filtered area (Toulouse) with negative buffer to a single GPKG, styles included.*

The full pipeline from filter to delivery: apply spatial and attribute filters, export the result as a GeoPackage with embedded QGIS styles — ready to share with colleagues or load into another project.

:film_frames: https://www.youtube.com/watch?v=gPLi2OudKcI
""".strip(),
    """
:bulb: **Tip**: All tutorials use open data from **IGN BD TOPO** — you can follow along with your own copy!

Have questions about a workflow? Head to `#general-help`. Want to share your own use case? Post it in `#showcases`!
""".strip(),
]

SHOWCASES_VIDEOS = """
# :movie_camera: FilterMate in Action — Video Showcase

Here's a collection of tutorials demonstrating what FilterMate can do on real GIS data. Each video is a standalone workflow you can replicate on your own projects.

| # | Tutorial | Key Features | Link |
|---|----------|-------------|------|
| 1 | Classic multi-step filtering | Attribute filters, chaining, BD TOPO | [Watch](https://www.youtube.com/watch?v=oQq45xZkzDc) |
| 2 | Roads and surrounding features | Spatial filtering, distance queries | [Watch](https://www.youtube.com/watch?v=P0G2x-ggtVQ) |
| 3 | Explore from map selection | Interactive selection, multi-layer | [Watch](https://www.youtube.com/watch?v=YwEalDjgEdY) |
| 4 | Major roads and connected areas | Deep exploration, network analysis | [Watch](https://www.youtube.com/watch?v=svElL8cDpWE) |
| 5 | Negative buffer + attribute filter | Geometry transforms, -500m buffer | [Watch](https://www.youtube.com/watch?v=9rZb-9A-tko) |
| 6 | Export to GPKG with styles | Full pipeline, styled GeoPackage | [Watch](https://www.youtube.com/watch?v=gPLi2OudKcI) |

All videos use **IGN BD TOPO** open data. Try it yourself and share your results here! :point_down:
""".strip()


# ---------------------------------------------------------------------------
# Bot client
# ---------------------------------------------------------------------------


class AnnouncementBot(discord.Client):
    def __init__(self, guild_id: int, dry_run: bool, only: str | None = None):
        intents = discord.Intents.default()
        intents.guilds = True
        super().__init__(intents=intents)
        self.target_guild_id = guild_id
        self.dry_run = dry_run
        self.only = only

    async def on_ready(self):
        log.info("Bot connected as %s", self.user)
        guild = self.get_guild(self.target_guild_id)
        if guild is None:
            log.error("Guild %s not found.", self.target_guild_id)
            await self.close()
            return

        try:
            await self.post_announcements(guild)
        except Exception:
            log.exception("Failed to post announcements")
        finally:
            await self.close()

    async def _send_and_pin(self, channel: discord.TextChannel, content: str, pin: bool = False):
        """Send a message and optionally pin it."""
        if self.dry_run:
            log.info("  [DRY RUN] would post in #%s (%d chars)", channel.name, len(content))
            return
        msg = await channel.send(content)
        if pin:
            try:
                await msg.pin()
                log.info("  Pinned in #%s", channel.name)
            except discord.HTTPException:
                log.warning("  Could not pin in #%s", channel.name)

    async def post_announcements(self, guild: discord.Guild):
        channels = {ch.name: ch for ch in guild.text_channels}
        post_raster = self.only in (None, "raster")
        post_videos = self.only in (None, "videos")
        post_technical = self.only in (None, "technical")

        # --- Technical bulletin ---
        if post_technical:
            announcements_ch = channels.get("announcements")
            if announcements_ch:
                log.info("Posting technical bulletin in #announcements (%d parts)", len(TECHNICAL_ANNOUNCEMENT_PARTS))
                for i, part in enumerate(TECHNICAL_ANNOUNCEMENT_PARTS):
                    await self._send_and_pin(announcements_ch, part, pin=(i == 0))
                    log.info("  Part %d/%d sent", i + 1, len(TECHNICAL_ANNOUNCEMENT_PARTS))
            else:
                log.warning("#announcements channel not found")

        # --- Raster announcements ---
        if post_raster:
            announcements_ch = channels.get("announcements")
            if announcements_ch:
                log.info("Posting raster announcement in #announcements (%d parts)", len(RASTER_ANNOUNCEMENT_PARTS))
                for i, part in enumerate(RASTER_ANNOUNCEMENT_PARTS):
                    await self._send_and_pin(announcements_ch, part, pin=(i == 0))
                    log.info("  Part %d/%d sent", i + 1, len(RASTER_ANNOUNCEMENT_PARTS))
            else:
                log.warning("#announcements channel not found")

            raster_ch = channels.get("raster-panel")
            if raster_ch:
                log.info("Posting dev update in #raster-panel")
                await self._send_and_pin(raster_ch, DEV_CHANNEL_TEASER)
            else:
                log.warning("#raster-panel channel not found")

        # --- Video tutorials ---
        if post_videos:
            announcements_ch = channels.get("announcements")
            if announcements_ch:
                log.info("Posting video tutorials in #announcements (%d parts)", len(VIDEOS_ANNOUNCEMENT_PARTS))
                for i, part in enumerate(VIDEOS_ANNOUNCEMENT_PARTS):
                    # Pin only the first part (the header)
                    await self._send_and_pin(announcements_ch, part, pin=(i == 0))
                    log.info("  Part %d/%d sent", i + 1, len(VIDEOS_ANNOUNCEMENT_PARTS))
            else:
                log.warning("#announcements channel not found")

            showcases_ch = channels.get("showcases")
            if showcases_ch:
                log.info("Posting video showcase in #showcases")
                await self._send_and_pin(showcases_ch, SHOWCASES_VIDEOS, pin=True)
            else:
                log.warning("#showcases channel not found")

        log.info("All announcements posted!")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Post FilterMate announcements")
    parser.add_argument("--guild-id", type=int, required=True, help="Discord server (guild) ID")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument(
        "--only",
        choices=["raster", "videos", "technical"],
        default=None,
        help="Post only a specific announcement set (default: all)",
    )
    parser.add_argument("--token", type=str, default=None, help="Bot token (or set DISCORD_BOT_TOKEN env var)")
    args = parser.parse_args()

    token = args.token or os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        print("Error: provide bot token via --token or DISCORD_BOT_TOKEN env var")
        sys.exit(1)

    bot = AnnouncementBot(guild_id=args.guild_id, dry_run=args.dry_run, only=args.only)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    main()
