# FilterMate - Consolidated Project Context

**Version:** 4.3.10 (Production Release)  
**Last Updated:** January 22, 2026  
**Codebase:** 178,539 lines / 490 Python files (126,539 hors tests)

---

## 1. Project Overview

FilterMate is a QGIS plugin providing an intuitive interface for filtering and exporting vector data. It supports multiple backends (PostgreSQL/PostGIS, Spatialite, OGR) with advanced geometric filtering.

**Key Features:**
- Expression-based filtering with geometric predicates
- Multi-backend support (auto-selection)
- Undo/Redo filter history
- Progressive filtering for large datasets
- Export functionality (multiple formats)
- Filter chaining with dynamic buffers
- 21 languages supported

---

## 2. Architecture (Hexagonal v4.3)

```
+---------------------------------------------------------------+
|                      UI LAYER (31,195 lines)                  |
|  filter_mate_dockwidget.py → ui/controllers/                  |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              CONTROLLER LAYER (13 controllers)                |
|  ui/controllers/                                              |
|  - integration.py (3,028) - Orchestration                     |
|  - exploring_controller.py (3,208)                            |
|  - filtering_controller.py                                    |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              APPLICATION LAYER (2,383 lines)                  |
|  filter_mate_app.py → core/services/                          |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|               CORE LAYER (48,667 lines)                       |
|  core/ (28 services, tasks, domain, strategies)               |
|  - services/ (28 services)                                    |
|  - tasks/ (filter_task.py 5,851 lines)                        |
|  - domain/, filter/, geometry/, optimization/                 |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|               ADAPTERS LAYER (33,253 lines)                   |
|  adapters/backends/                                           |
|  - postgresql/ (MV, parallel queries, spatial indexes)        |
|  - spatialite/ (SQL queries, spatial functions)               |
|  - ogr/ (shapefile, GeoJSON, vector formats)                  |
|  - memory/ (in-memory filtering)                              |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              INFRASTRUCTURE LAYER (13,424 lines)              |
|  infrastructure/                                              |
|  - database/, cache/, utils/, logging/, di/, parallel/        |
+---------------------------------------------------------------+
```

---

## 3. Directory Structure (v4.3)

```
filter_mate/
├── filter_mate.py              # Plugin entry (QGIS integration)
├── filter_mate_app.py          # Application orchestrator (2,383 lines)
├── filter_mate_dockwidget.py   # UI management (6,925 lines)
│
├── core/                       # Business Logic (48,667 lines)
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
├── adapters/                   # External Integrations (33,253 lines)
│   ├── backends/               # postgresql/, spatialite/, ogr/, memory/
│   ├── qgis/                   # QGIS adapters (signals, tasks)
│   ├── repositories/           # Data access (LayerRepository)
│   └── app_bridge.py           # DI Container
│
├── infrastructure/             # Cross-cutting (13,424 lines)
│   ├── cache/                  # LRU cache, geometry/query cache
│   ├── database/               # Connection pool, SQL utilities
│   ├── utils/                  # Layer utils, validation
│   └── logging/, di/, parallel/, streaming/
│
├── ui/                         # Presentation (31,195 lines)
│   ├── controllers/            # 13 MVC controllers
│   ├── widgets/                # Custom widgets
│   ├── styles/                 # Theming (IconManager, ThemeWatcher)
│   └── dialogs/                # Configuration dialogs
│
├── tests/                      # Test suite (51,962 lines, 176 tests)
└── config/                     # Configuration files
```

---

## 4. Code Statistics (January 22, 2026)

| Layer | Directory | Lines | % | Files |
|-------|-----------|-------|---|-------|
| Core Domain | core/ | 48,667 | 38.5% | ~100 |
| Adapters | adapters/ | 33,253 | 26.3% | ~70 |
| UI Layer | ui/ | 31,195 | 24.6% | ~55 |
| Infrastructure | infrastructure/ | 13,424 | 10.6% | ~40 |
| Tests | tests/ | 51,962 | - | ~176 |
| **TOTAL (prod)** | | **126,539** | **100%** | **~314** |

### Quality Metrics (v4.3.10)

| Metric | Value | Target |
|--------|-------|--------|
| Test Coverage | ~75% | 80% |
| Automated Tests | ~176 | - |
| Bare Excepts | 0 ✅ | 0 |
| Debug Prints | 0 ✅ | 0 |
| Services | 28 | - |
| Controllers | 13 | - |
| Backends | 4 | - |
| Quality Score | 8.5/10 | 9.0/10 |

---

## 5. Import Guidelines

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

| Backend | Best For | Query Time | Memory |
|---------|----------|------------|--------|
| PostgreSQL | >50k features | <1s (millions) | Low (server) |
| Spatialite | 10k-50k features | 1-10s (100k) | Moderate |
| Memory | <100k features | <0.5s (50k) | High |
| OGR | <10k features | 10-60s (100k) | High |

### Thread Safety
- PostgreSQL/Spatialite: Parallel OK
- OGR: Sequential ONLY (not thread-safe)

---

## 7. Recent Releases (v4.3.x)

### v4.3.10 (22 janvier 2026) - Current
- **Export & Buffer Table Complete Fix Series**
- All v4.3.1-v4.3.9 fixes consolidated
- Export workflow: 100% functional
- Filter chaining with dynamic buffers: Working
- Buffer tables: Properly created and committed
- Debug prints: All removed

### Key Fixes in v4.3.x:
| Version | Fix |
|---------|-----|
| v4.3.9 | Buffer table transaction commit |
| v4.3.8 | Debug prints cleanup |
| v4.3.7 | JUST-IN-TIME sync for export flags |
| v4.3.5 | Buffer expression in filter chain optimizer |
| v4.3.1-3 | Filter chaining flag initialization |

---

## 8. Undo/Redo System

### Architecture
- **FilterState**: Single layer state
- **GlobalFilterState**: Multi-layer state (source + remote)
- **FilterHistory**: Per-layer history stack
- **HistoryManager**: Global history management

### Behavior
- Peeks at history entry to determine operation type
- `layer_count > 1` → global undo/redo
- `layer_count == 1` → layer-only undo/redo
- Stack Size: 100 states per layer/global

---

## 9. Design Patterns

- **Hexagonal Architecture** (Ports & Adapters)
- **Factory Pattern** (BackendFactory, QGISFactory)
- **Strategy Pattern** (Multi-backend, Multi-step filtering)
- **Repository Pattern** (LayerRepository, HistoryRepository)
- **Service Locator** (app_bridge.py)
- **MVC** (UI layer)
- **Observer** (Signal/slot connections)

---

## 10. Roadmap

### v4.3.x Completed ✅
- [x] Export workflow fixes
- [x] Filter chaining with dynamic buffers
- [x] Buffer table transaction fixes
- [x] Code cleanup (bare excepts, debug prints)
- [x] Quality score: 8.5/10

### v5.0 Planned
- [ ] Remove technical debt (TODOs P1)
- [ ] Plugin API for extensibility
- [ ] Parallel processing improvements
- [ ] Test coverage: 80%

---

## 11. File References

| Category | Key Files |
|----------|-----------|
| Entry | `filter_mate.py` |
| App | `filter_mate_app.py` (2,383 lines) |
| UI | `filter_mate_dockwidget.py` (6,925 lines) |
| Main Task | `core/tasks/filter_task.py` (5,851 lines) |
| Services | `core/services/` (28 services) |
| Controllers | `ui/controllers/` (13 controllers) |
| Backends | `adapters/backends/` (4 backends) |
| Tests | `tests/` (~176 tests) |
| Config | `config/config.json` |

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

**Consolidation Date:** January 18, 2026
