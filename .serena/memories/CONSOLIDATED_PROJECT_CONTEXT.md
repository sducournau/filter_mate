# FilterMate - Consolidated Project Context

**Version:** 6.0.0-dev (Consolidation In Progress — Phases 1-4 COMPLETE)  
**Last Updated:** February 9, 2026  
**Codebase:** ~243,284 lines / 549 Python files (~130,000 production + ~52,000 tests)
**Consolidation v6.0:** ~4,500 lines reduced so far (Phases 1-4 of 6 complete, target: ~19,000)

---

## 1. Project Overview

FilterMate is a QGIS plugin providing an intuitive interface for filtering and exporting vector and raster data. It supports multiple backends (PostgreSQL/PostGIS, Spatialite, OGR) with advanced geometric filtering and now includes comprehensive raster support.

**Key Features:**
- Expression-based filtering with geometric predicates
- Multi-backend support with auto-selection
- **NEW:** Interactive raster value selection tools (v5.4.0)
- Undo/Redo filter history (100-state stack)
- Progressive filtering for large datasets
- Export functionality (multiple formats with style preservation)
- Filter chaining with dynamic buffers
- 22 languages supported (96% FR/EN coverage)
- Dark/light theme support

---

## 2. Architecture (Hexagonal v5.4)

```
+---------------------------------------------------------------+
|                      UI LAYER (~32,000 lines)                 |
|  filter_mate_dockwidget.py → ui/controllers/ → ui/tools/      |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              CONTROLLER LAYER (13 controllers)                |
|  ui/controllers/                                              |
|  - integration.py (3,028) - Orchestration                     |
|  - exploring_controller.py (3,208) - Feature explorer         |
|  - filtering_controller.py - Filter operations                |
|  - raster_controller.py - Raster operations (NEW v5.4)        |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              APPLICATION LAYER (~2,383 lines)                 |
|  filter_mate_app.py → core/services/                          |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|               CORE LAYER (~50,000 lines)                      |
|  core/ (28 services, tasks, domain, strategies)               |
|  - services/ (28 services)                                    |
|  - tasks/ (filter_task.py 4,499 lines + handlers/)             |
|  - domain/, filter/, geometry/, optimization/                 |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|               ADAPTERS LAYER (~33,000 lines)                  |
|  adapters/backends/                                           |
|  - postgresql/ (MV, parallel, PK detection, spatial indexes)  |
|  - spatialite/ (SQL queries, R-tree, spatial functions)       |
|  - ogr/ (shapefile, GeoJSON, vector formats)                  |
|  - memory/ (in-memory filtering)                              |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              INFRASTRUCTURE LAYER (~15,000 lines)             |
|  infrastructure/                                              |
|  - database/, cache/, utils/, logging/, di/, parallel/        |
+---------------------------------------------------------------+
```

---

## 3. Directory Structure (v5.4)

```
filter_mate/
├── filter_mate.py              # Plugin entry (QGIS integration)
├── filter_mate_app.py          # Application orchestrator (2,383 lines)
├── filter_mate_dockwidget.py   # UI management (6,925 lines)
│
├── core/                       # Business Logic (~50,000 lines)
│   ├── domain/                 # Domain models (LayerInfo, FilterResult, etc.)
│   ├── services/               # 28 hexagonal services
│   ├── tasks/                  # Async tasks (filter, layer management)
│   ├── filter/                 # Expression building/sanitizing
│   ├── geometry/               # Buffer, CRS, spatial index
│   ├── optimization/           # Query optimization, performance advisor
│   ├── ports/                  # Port interfaces (hexagonal)
│   ├── strategies/             # Multi-step, progressive filtering
│   └── export/                 # Export functionality
│
├── adapters/                   # External Integrations (~33,000 lines)
│   ├── backends/               # postgresql/, spatialite/, ogr/, memory/
│   │   └── postgresql/
│   │       ├── expression_builder.py  # PK detection, dynamic buffers
│   │       ├── optimizer.py           # Materialized views
│   │       └── ...
│   ├── qgis/                   # QGIS adapters (signals, tasks)
│   ├── repositories/           # Data access (LayerRepository)
│   └── app_bridge.py           # DI Container
│
├── infrastructure/             # Cross-cutting (~15,000 lines)
│   ├── cache/                  # LRU cache, geometry/query cache
│   ├── database/               # Connection pool, SQL utilities
│   ├── utils/                  # Layer utils, validation
│   └── logging/, di/, parallel/, streaming/
│
├── ui/                         # Presentation (~32,000 lines)
│   ├── controllers/            # 13 MVC controllers
│   │   ├── integration.py      # Main UI orchestration
│   │   ├── exploring_controller.py  # Feature/raster explorer
│   │   └── ...
│   ├── widgets/                # Custom widgets
│   │   └── dockwidget_signal_manager.py  # Signal management (778 lines)
│   ├── tools/                  # Map tools
│   │   └── raster_pixel_picker_tool.py   # Raster value picking (NEW v5.4)
│   ├── styles/                 # Theming (IconManager, ThemeWatcher)
│   └── dialogs/                # Configuration dialogs
│
├── tests/                      # Test suite (~52,000 lines, 396 tests)
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── regression/             # Regression tests
│
├── config/                     # Configuration files
│   ├── config.json             # User configuration
│   └── config_metadata.py      # Config metadata v2.0
│
├── i18n/                       # 22 language translations
│   ├── FilterMate_fr.ts        # French (96% coverage)
│   ├── FilterMate_en.ts        # English (96% coverage)
│   └── ...
│
└── _bmad/                      # BMAD project management
    ├── core/                   # BMAD core (agents, workflows)
    ├── bmm/                    # BMAD BMM module
    └── _config/                # Task/workflow manifests
```

---

## 4. Code Statistics (February 1, 2026)

| Layer | Directory | Lines | % | Files |
|-------|-----------|-------|---|-------|
| Core Domain | core/ | ~50,000 | 38% | ~100 |
| Adapters | adapters/ | ~33,000 | 25% | ~70 |
| UI Layer | ui/ | ~32,000 | 25% | ~55 |
| Infrastructure | infrastructure/ | ~15,000 | 12% | ~40 |
| Tests | tests/ | ~52,000 | - | ~176 |
| **TOTAL (prod)** | | **~130,000** | **100%** | **~314** |
| **TOTAL (all)** | | **~243,284** | - | **529** |

### Quality Metrics (v6.0.0-dev)

| Metric | Value | Target |
|--------|-------|--------|
| Test Coverage | 75% | 80% |
| Automated Tests | 396 | - |
| Bare Excepts | 0 ✅ | 0 |
| Debug Prints | 0 ✅ | 0 |
| Services | 28 (30 pre-consolidation) | 18-20 (P5) |
| Controllers | 13 | - |
| Backends | 4 | - |
| Languages | 22 | - |
| Quality Score | 8.5/10 | 9.0/10 |

---

## 5. Import Guidelines (v5.4)

```python
# PostgreSQL availability
from adapters.backends.postgresql_availability import POSTGRESQL_AVAILABLE

# Tasks
from core.tasks import FilterEngineTask, LayersManagementEngineTask

# Services
from core.services import FilterService, LayerService, ExpressionService

# Backends
from adapters.backends import BackendFactory, PostgreSQLBackend, SpatialiteBackend

# Utilities
from infrastructure.utils.layer_utils import is_layer_valid
from infrastructure.utils import get_datasource_connexion_from_layer

# Domain
from core.domain import FilterResult, LayerInfo, FilterExpression

# UI Tools (NEW v5.4)
from ui.tools.raster_pixel_picker_tool import RasterPixelPickerTool

# UI Widgets
from ui.widgets.dockwidget_signal_manager import DockwidgetSignalManager
```

---

## 6. Backend System

### Selection Priority
1. **FORCED**: User UI selection
2. **MEMORY**: Native memory layers
3. **SMALL_PG**: Small PostgreSQL (<5k) → Memory optimization
4. **FALLBACK**: PostgreSQL unavailable → OGR
5. **AUTO**: Provider type detection

### Performance Characteristics

| Backend | Best For | Query Time | Memory | Thread Safety |
|---------|----------|------------|--------|---------------|
| PostgreSQL | >50k features | <1s (millions) | Low (server) | ✅ Parallel OK |
| Spatialite | 10k-50k features | 1-10s (100k) | Moderate | ✅ Parallel OK |
| Memory | <100k features | <0.5s (50k) | High | ✅ Parallel OK |
| OGR | <10k features | 10-60s (100k) | High | ❌ Sequential ONLY |

### PostgreSQL Optimizations (v4.4.5+)

- **Automatic Primary Key Detection**: Queries `pg_index` to find actual PK column
- **Fallback PK Names**: id, fid, ogc_fid, cleabs, gid, objectid
- **Dynamic Buffers**: Creates `fm_temp_buf_*` tables with detected PK
- **Materialized Views**: `fm_temp_mv_*` for complex queries
- **Parallel Queries**: Multi-threaded execution for large datasets
- **Spatial Indexes**: Automatic GIST index creation

---

## 7. Recent Releases (v4.4.x - v5.4.0)

### v5.4.0 (February 1, 2026) - **CURRENT**
**NEW: Raster Exploring Tool Buttons**
- ✅ 5 new interactive raster tools (Pixel Picker, Rectangle Range, Sync Histogram, All Bands Info, Reset Range)
- ✅ Consistent UI pattern with vector exploring panel
- ✅ Checkable button mutual exclusion
- ✅ Theme-aware icons and tooltips
- ✅ Integration with existing RasterPixelPickerTool

**Files Changed:**
- `filter_mate_dockwidget_base.py`: Added `widget_raster_keys` with 5 tool buttons
- `filter_mate_dockwidget.py`: Added `_connect_raster_tool_buttons()` and handlers
- `ui/tools/raster_pixel_picker_tool.py`: Enhanced with new modes

### v4.4.5 (January 25, 2026)
**FIX: Dynamic buffer fails on tables without "id" column**
- ✅ Automatic PK detection from PostgreSQL `pg_index` metadata
- ✅ Fallback to common PK names (id, fid, ogc_fid, cleabs, gid, objectid)
- ✅ Graceful handling when no PK found
- ✅ Fixes dynamic buffer on BDTopo/OSM tables

**Root Cause:** Buffer table creation was hardcoded with `"id" as source_id`

### v4.4.4 (January 25, 2026)
**Unified `fm_temp_*` naming convention**
- ✅ All temp objects use `fm_temp_*` prefix (MV, buffer tables, indexes)
- ✅ Simplified cleanup and identification
- ✅ Consistent naming across PostgreSQL backend

### v4.4.0 (January 22, 2026)
**Major Quality Release**
- ✅ 396 standalone unit tests (previously: fragmented test structure)
- ✅ DockwidgetSignalManager extracted (778 lines)
- ✅ Hexagonal architecture complete
- ✅ Test coverage: 75%
- ✅ Quality score: 8.5/10

---

## 8. Undo/Redo System

### Architecture
- **FilterState**: Single layer state snapshot
- **GlobalFilterState**: Multi-layer state (source + remote layers)
- **FilterHistory**: Per-layer history stack (100 states max)
- **HistoryManager**: Global history management

### Behavior
```python
# Peek at history entry to determine operation type
if history_entry.layer_count > 1:
    # Global undo/redo (source + remote layers)
    restore_global_state(history_entry)
else:
    # Layer-only undo/redo (single layer)
    restore_layer_state(history_entry)
```

### Stack Limits
- **Per-layer**: 100 states
- **Global**: 100 states
- **Auto-pruning**: FIFO when limit reached

---

## 9. Raster Support (EPIC-3 - v5.4.0)

### New Tool Buttons (v5.4.0)

| Button | Function | Mode | Shortcut |
|--------|----------|------|----------|
| 🔬 **Pixel Picker** | Click to pick single value | Checkable | Ctrl+click = extend range |
| ⬛ **Rectangle Range** | Drag rectangle for area stats | Checkable | Auto-calculate min/max |
| 🔄 **Sync Histogram** | Sync spinbox ↔ histogram | Action | Bidirectional sync |
| 📊 **All Bands Info** | Show all band values | Checkable | Multi-band display |
| 🎯 **Reset Range** | Reset to data range | Action | From statistics |

### UI Pattern
```
┌────────────────────────────────────────────┐
│ 🏔️ RASTER                                  │
├────────┬───────────────────────────────────┤
│ [🔬]   │  Band: [1 - Band 1           ▼]   │
│ [⬛]   │  📊 Statistics                    │
│ [🔄]   │  📈 Value Selection (Histogram)   │
│ [📊]   │     Min/Max spinboxes             │
│ [🎯]   │     Predicate dropdown            │
└────────┴───────────────────────────────────┘
```

### Integration
- **Tool**: `RasterPixelPickerTool` (ui/tools/)
- **Controller**: `RasterController` (ui/controllers/)
- **Signals**: `DockwidgetSignalManager` handles connections
- **State**: Mutual exclusion for checkable buttons

---

## 10. Translation System (i18n/)

### Coverage Summary (Feb 1, 2026)

| Language | Code | Coverage | Status |
|----------|------|----------|--------|
| 🇫🇷 Français | fr | **96%** (560/578) | ✅ Excellent |
| 🇬🇧 English | en | **96%** (560/578) | ✅ Excellent |
| 🇩🇪 Deutsch | de | 48% (283/578) | ⚠️ Needs work |
| 🇪🇸 Español | es | 45% (262/578) | ⚠️ Needs work |
| 🇮🇹 Italiano | it | 40% (235/578) | ⚠️ Needs work |
| 19 others | - | ~29% (168/578) | ⚠️ Basic |

### Translation Files
- **Source**: `i18n/FilterMate_*.ts` (22 files)
- **Compiled**: `i18n/FilterMate_*.qm` (22 files)
- **Active Messages**: 578 (non-obsolete)
- **Obsolete Messages**: 407 (can be cleaned with `lupdate -no-obsolete`)

### UI Translatable Strings
- **filter_mate_dockwidget_base.ui**: 121 strings
- **Python code (self.tr)**: ~460 calls
- **Hardcoded remaining**: ~35 (mostly Unicode symbols)

---

## 11. Design Patterns

- **Hexagonal Architecture** (Ports & Adapters) - Clean separation of concerns
- **Factory Pattern** (BackendFactory, QGISFactory) - Dynamic backend selection
- **Strategy Pattern** (Multi-backend, Multi-step filtering) - Pluggable algorithms
- **Repository Pattern** (LayerRepository, HistoryRepository) - Data access abstraction
- **Service Locator** (app_bridge.py) - Dependency injection container
- **MVC** (UI layer) - Model-View-Controller separation
- **Observer** (Signal/slot connections) - Event-driven UI updates
- **Command Pattern** (Undo/Redo) - Action encapsulation

---

## 12. Roadmap

### v5.4.x Completed ✅
- [x] Raster exploring tool buttons (v5.4.0)
- [x] Primary key detection (v4.4.5)
- [x] Unified naming convention (v4.4.4)
- [x] Quality improvements (v4.4.0)
- [x] Test coverage: 75%
- [x] Quality score: 8.5/10

### v5.5 Planned (Q1 2026)
- [ ] **EPIC-4**: Raster Export UI
- [ ] Improve DE/ES translation coverage (48%/45% → 70%+)
- [ ] Test coverage: 75% → 80%
- [ ] Performance optimization for very large rasters
- [ ] Documentation improvements

### v6.0 IN PROGRESS (Consolidation — February 2026)
- [x] **P1**: Cleanup — ~110 unused imports, dead files, deprecation markers (`213e794`)
- [x] **P2**: Expression builders — PredicateRegistry, dead code removal, PK consolidation (`21ebb47`..`519d4d3`)
- [x] **P3.1**: Extract RasterExploringManager from dockwidget (-1,822 lines) (`1ff21fd`)
- [x] **P4**: Extract backend handlers from FilterEngineTask (-1,371 lines) (`70886b5`)
- [ ] **P5**: Merge redundant services (30 → 18-20)
- [ ] **P6**: Remove dual toolbox system (-5,000 lines expected)
- **Total reduced so far:** ~4,500 lines / ~19,000 target

---

## 13. File References

| Category | Key Files | Lines |
|----------|-----------|-------|
| Entry | `filter_mate.py` | ~300 |
| App | `filter_mate_app.py` | 2,383 |
| UI | `filter_mate_dockwidget.py` | 9,994 (was 11,836) |
| Main Task | `core/tasks/filter_task.py` | 4,499 (was 5,870) |
| PG Handler | `core/tasks/handlers/postgresql_handler.py` | 851 (NEW v6.0-P4) |
| SL Handler | `core/tasks/handlers/spatialite_handler.py` | 348 (NEW v6.0-P4) |
| OGR Handler | `core/tasks/handlers/ogr_handler.py` | 224 (NEW v6.0-P4) |
| Raster Mgr | `ui/managers/raster_exploring_manager.py` | 1,462 (NEW v6.0-P3.1) |
| PostgreSQL Backend | `adapters/backends/postgresql/expression_builder.py` | ~1,500 |
| Raster Tools | `ui/tools/raster_pixel_picker_tool.py` | ~800 |
| Signal Manager | `ui/widgets/dockwidget_signal_manager.py` | 778 |
| Controllers | `ui/controllers/integration.py` | 3,028 |
| Controllers | `ui/controllers/exploring_controller.py` | 3,208 |

---

## 14. BMAD Integration

FilterMate uses **BMAD v6.0.0-Beta.4** for project management.

### Key Directories
- **_bmad/core/**: Core BMAD agents and workflows
- **_bmad/bmm/**: BMM (Business Model Management) module
- **_bmad-output/**: Generated artifacts (PRDs, user stories, specs)

### Configuration
```yaml
# _bmad/core/config.yaml
user_name: Simon
communication_language: French
document_output_language: English
output_folder: "{project-root}/_bmad-output"
```

### Key Agents
- @bmad-master: Orchestrator
- @dev (Amelia): Development
- @architect (Winston): Architecture
- @analyst (Mary): Business analysis
- @pm (John): Product management

### Recent Artifacts
- `STORY-RASTER-EXPLORING-TOOLS-BUTTONS.md` - Raster tools specification
- `TRANSLATION-AUDIT-20260201-COMPLETE.md` - Translation status
- `EPIC-3-UI-SPECIFICATION.md` - Raster-vector integration
- `EPIC-4-RASTER-EXPORT-USER-STORIES.md` - Export functionality

---

**Consolidated from:**
- project_memory.md
- architecture_overview.md
- repository_structure.md
- current_project_state_2026_01_18.md
- known_issues_bugs.md
- backend_architecture.md
- undo_redo_system.md
- performance_audit_2026_01_18.md
- CHANGELOG.md (v5.4.0)
- metadata.txt (v4.4.5)
- Translation audit (Feb 1, 2026)

**Last Consolidation:** February 9, 2026 (v6.0 Phases 1-4 complete)
