# FilterMate Project Overview

**Last Updated:** January 6, 2026  
**Version:** 2.9.6  
**Status:** Production - Active Development

## Recent Changes (v2.9.x Series - January 2026)

### v2.9.6 - Invalid Geometry Handling (January 6, 2026)
- 🐛 FIX: Spatialite filtering now handles invalid source geometries correctly
- 🔧 Added `MakeValid()` wrapper to ALL geometry insertions and expressions
- ✅ Layers from same GeoPackage now filter correctly
- 🛡️ Invalid geometries no longer cause 0 results on valid datasets

### v2.9.5 - Shutdown Crash Fix (January 5, 2026)
- 🐛 FIX: Windows crash during QGIS shutdown (fatal access violation)
- 🔧 Task cancellation now uses Python logger instead of QgsMessageLog
- ✅ Safe shutdown: Avoids calling destroyed C++ objects during QgsTaskManager::cancelAll()

### v2.9.4 - Spatialite Subquery Fix (January 5, 2026)
- 🐛 FIX: Spatialite large dataset filtering now works correctly (≥20K features)
- 🔧 Replaced SQL subquery with range-based filter for OGR compatibility
- ✅ Filter expressions now use BETWEEN/IN() instead of unsupported subqueries
- ⚠️ DEPRECATED: `_build_fid_table_filter()` method

### v2.9.2 - Centroid & Simplification Optimizations (January 4, 2026)
- 🎯 NEW: ST_PointOnSurface() for accurate polygon centroids (guaranteed inside)
- 📐 NEW: Adaptive simplification before buffer operations
- 🔧 Configurable CENTROID_MODE: 'point_on_surface' | 'centroid' | 'auto'
- ⚡ Simplification reduces vertex count 50-90% before buffer

### v2.9.1 - PostgreSQL MV Optimizations (January 4, 2026)
- 🚀 INCLUDE clause in GIST indexes (PostgreSQL 11+) - 10-30% faster
- 📊 Bbox column for fast pre-filtering on large datasets (≥10K features)
- ⏳ Async CLUSTER for medium datasets (50k-100k) - non-blocking
- 📈 Extended statistics for better query plans (PostgreSQL 10+)

## Critical Fixes (v2.8.x Series - January 2026)

### v2.8.9 - MV Management UI (January 4, 2026)
- ✨ Real-time MV status widget with count and session info
- 🧹 One-click cleanup actions (Session / Orphaned / All)
- 🔄 Simplified optimization confirmation popup

### v2.8.8 - Selection Sync Initialization Fix (January 4, 2026)
- 🐛 FIX: Selection Auto-Sync not working on project load
- ✅ Explicit initialization of selection sync in `_reconnect_layer_signals()`

### v2.8.7 - Complex Expression Materialization (January 4, 2026)
- 🐛 FIX: Slow canvas rendering with complex spatial expressions
- 🚀 Automatic detection and materialization of expensive expressions
- ♻️ Centralized psycopg2 imports (`modules/psycopg2_availability.py`)
- ♻️ Deduplicated buffer methods to base_backend.py (~230 lines removed)

### v2.8.1 - Orphaned MV Recovery (January 3, 2026)
- 🐛 FIX: PostgreSQL "relation does not exist" errors after QGIS restart
- ✅ Automatic MV reference detection and cleanup on project load

## Architecture

- **Multi-backend:** PostgreSQL, Spatialite, OGR, Memory
- **Factory pattern** with automatic backend selection + forced backend override
- **QgsTask** for async operations
- **Thread safety:** OGR forced sequential, PostgreSQL/Spatialite parallel

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `filter_mate_app.py` | Application orchestrator | ~3000+ |
| `filter_mate_dockwidget.py` | UI management | ~5100+ |
| `modules/backends/` | Multi-backend implementations | |
| `modules/tasks/filter_task.py` | Core filtering task | ~950 |
| `modules/constants.py` | Centralized constants | ~120+ |
| `modules/psycopg2_availability.py` | Centralized psycopg2 handling | NEW v2.8.7 |

## See Also

- Memory: `enhanced_optimizer_v2.8.0` - Detailed v2.8.0 documentation
- Memory: `backend_architecture` - Multi-backend system details
- Memory: `known_issues_bugs` - Bug fixes and known issues
- Docs: `docs/FIX_INVALID_GEOMETRY_SPATIALITE_2026-01.md` - v2.9.6 fix
- Docs: `docs/FIX_SPATIALITE_SUBQUERY_2026-01.md` - v2.9.4 fix