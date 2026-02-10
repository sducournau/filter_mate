# FilterMate Project Overview

**Last Updated:** February 10, 2026
**Version:** Main branch (Production)
**Status:** Production - Hexagonal Architecture Complete, Vector filtering only

> **Raster Audit (2026-02-10):** No raster features exist on `main`. Previous claims of
> "v5.4.0 Raster Exploring Tool Buttons" were branch-only (never merged).
> See memory `raster_integration_plan_atlas_2026_02_10` for the raster roadmap.

## Current State on `main`

### Raster Support: NONE on `main`
- Only: `RasterLayer = 1` enum (layer type detection), type hints in `crs_utils.py`
- NO raster files, NO raster widgets, NO histogram, NO raster services
- Raster features existed only on dev branch `fix/widget-visibility-and-styles-2026-02-02`

### Recent Releases (v4.4.x)

| Version | Date | Key Changes |
|---------|------|-------------|
| **4.4.5** | Jan 25, 2026 | FIX: Dynamic buffer fails on tables without "id" PK column |
| **4.4.4** | Jan 25, 2026 | Unified `fm_temp_*` naming for PostgreSQL temp objects |
| **4.4.0** | Jan 22, 2026 | Major quality release - 396 unit tests, 75% coverage, hexagonal architecture |

## Architecture v5.4 (Hexagonal)

```
filter_mate.py              → Plugin entry point
filter_mate_app.py          → Application orchestrator (~2,383 lines)
filter_mate_dockwidget.py   → UI management (~6,925 lines)
ui/controllers/             → MVC Controllers (13 controllers)
core/
├── tasks/                  → Async operations (filter_task.py: ~5,851 lines)
├── services/               → Hexagonal services (28 services)
├── domain/                 → Domain models
├── filter/                 → Filter domain logic
├── geometry/               → Geometry utilities
├── optimization/           → Query optimization
├── ports/                  → Port interfaces
├── strategies/             → Filter strategies
├── export/                 → Export functionality
adapters/
├── backends/               → Multi-backend (postgresql/spatialite/ogr/memory)
│   ├── postgresql/         → MV, parallel queries, PK detection
│   ├── spatialite/         → SQL queries, spatial functions
│   ├── ogr/                → Shapefile, GeoJSON, vector formats
│   └── memory/             → In-memory filtering
├── qgis/                   → QGIS adapters (signals, tasks)
└── repositories/           → Data access
infrastructure/
├── logging/, cache/, utils/, database/
├── di/, feedback/, parallel/, streaming/
ui/
├── controllers/            → 13 MVC controllers
├── widgets/                → Custom widgets (DockwidgetSignalManager)
├── tools/                  → Map tools (empty - raster tools not yet on main)
└── styles/                 → Theming, icon management
```

## Code Statistics (February 1, 2026)

| Metric | Value |
|--------|-------|
| **Total Files** | 529 Python files |
| **Total Lines** | ~243,284 lines (all code) |
| **Production Code** | ~130,000 lines (est.) |
| **Test Code** | ~52,000 lines (396 tests) |
| **Test Coverage** | 75% (target: 80%) |
| **Quality Score** | 8.5/10 |

### Key Layers

| Layer | Lines (est.) | Files | % |
|-------|--------------|-------|---|
| Core Domain | ~50,000 | ~100 | 38% |
| Adapters | ~33,000 | ~70 | 25% |
| UI Layer | ~32,000 | ~55 | 25% |
| Infrastructure | ~15,000 | ~40 | 12% |

## Key Features

### Multi-Backend Support
- **PostgreSQL/PostGIS**: Optimized with materialized views, parallel queries, automatic PK detection
- **Spatialite**: SQL queries with R-tree indexes, spatial functions
- **OGR**: Universal fallback (shapefiles, GeoJSON, GeoPackage, WFS)
- **Memory**: In-memory filtering for small datasets

### Raster Support: NOT YET on `main`
- EPIC-3 raster features were developed on branch only (never merged)
- See memory `raster_integration_plan_atlas_2026_02_10` for roadmap
- Planned: Raster Value Sampling → Zonal Stats as Filter → Raster Export

### Advanced Features
- **Undo/Redo** filter history (100-state stack)
- **Filter Chaining** with dynamic buffer expressions
- **Favorites** system with spatial context
- **Progressive Filtering** for large datasets
- **Export** to GeoPackage with style preservation
- **21 Languages** supported (96% FR/EN, 48% DE, 45% ES)
- **Dark Mode** with theme auto-detection

## Key Metrics

| Metric | Value | Target |
|--------|-------|--------|
| Test Coverage | 75% | 80% |
| Unit Tests | 396 | - |
| Backend Variants | 4 | - |
| Languages | 22 | - |
| Services | 28 | - |
| Controllers | 13 | - |
| Bare Excepts | 0 ✅ | 0 |
| Debug Prints | 0 ✅ | 0 |
| Quality Score | 8.5/10 | 9.0/10 |

## Key Files (Lines of Code)

| File | Purpose | Lines |
|------|---------|-------|
| `filter_mate_app.py` | Application orchestrator | 2,383 |
| `filter_mate_dockwidget.py` | UI management | 6,925 |
| `core/tasks/filter_task.py` | Main filtering task | 5,851 |
| `ui/controllers/integration.py` | UI orchestration | 3,028 |
| `ui/controllers/exploring_controller.py` | Feature explorer | 3,208 |
| `ui/widgets/dockwidget_signal_manager.py` | Signal management | 778 |

## Recent Improvements (2026)

### ~~v5.4.0 - Raster Tool Buttons~~ (BRANCH ONLY - never merged to main)

### v4.4.5 - Primary Key Detection
- ✅ Automatic PK detection from PostgreSQL metadata
- ✅ Fallback to common PK names (id, fid, ogc_fid, cleabs, gid)
- ✅ Fixes dynamic buffer on BDTopo/OSM tables

### v4.4.0 - Quality Release
- ✅ 396 standalone unit tests
- ✅ DockwidgetSignalManager extracted (778 lines)
- ✅ Hexagonal architecture complete
- ✅ Test coverage: 75%

## Current Focus (Q1 2026)

### Active Development
- **EPIC-3**: Raster-Vector Filter Integration - NOT on main (branch only, never merged)
- **Raster Roadmap**: Sampling → Zonal Stats → Export (see `raster_integration_plan_atlas_2026_02_10`)
- **EPIC-4**: Raster Export UI (planned, pairs with Raster Clip by Vector)
- **Translation Coverage**: Improve DE/ES coverage (48%/45% → 70%+)
- **Test Coverage**: 75% → 80%

### Technical Debt
- [ ] Reduce dockwidget.py complexity (~6,925 lines)
- [ ] Improve documentation coverage
- [ ] Refactor remaining god classes
- [ ] Performance optimization for very large datasets

## See Also

- Memory: `CONSOLIDATED_PROJECT_CONTEXT` - Full architectural context
- Memory: `code_style_conventions` - Coding guidelines
- Memory: `ui_system` - UI architecture details
- CHANGELOG.md - Complete version history
- _bmad-output/ - BMAD planning artifacts
