# FilterMate - Consolidated Project Context

**Version:** 4.1.0 (Production Release)
**Last Updated:** January 18, 2026
**Codebase:** 271,837 lines / 546 Python files

---

## 1. Project Overview

FilterMate is a QGIS plugin providing an intuitive interface for filtering and exporting vector data. It supports multiple backends (PostgreSQL/PostGIS, Spatialite, OGR) with advanced geometric filtering.

**Key Features:**
- Expression-based filtering with geometric predicates
- Multi-backend support (auto-selection)
- Undo/Redo filter history
- Progressive filtering for large datasets
- Export functionality (multiple formats)
- 21 languages supported

---

## 2. Architecture (Hexagonal v4.0)

```
+---------------------------------------------------------------+
|                      UI LAYER (5,987 lines)                   |
|  filter_mate_dockwidget.py → ui/controllers/                  |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              CONTROLLER LAYER (13,143 lines)                  |
|  ui/controllers/ (13 controllers)                             |
|  - integration.py (2,971) - Orchestration                     |
|  - exploring_controller.py (2,922)                            |
|  - filtering_controller.py (1,467)                            |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              APPLICATION LAYER (2,271 lines)                  |
|  filter_mate_app.py → core/services/                          |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|               SERVICE LAYER (14,520 lines)                    |
|  core/services/ (27 services)                                 |
|  - layer_lifecycle_service.py, favorites_service.py           |
|  - filter_service.py, expression_service.py                   |
|  - backend_service.py, history_service.py, ...                |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|                 TASK LAYER (~8,900 lines)                     |
|  core/tasks/                                                  |
|  - filter_task.py (5,217) - Main filtering                    |
|  - layer_management_task.py (1,869)                           |
|  + builders/, cache/, executors/, dispatchers/                |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|               BACKEND LAYER (~4,000 lines)                    |
|  adapters/backends/                                           |
|  - postgresql/ (MV, parallel queries, spatial indexes)        |
|  - spatialite/ (SQL queries, spatial functions)               |
|  - ogr/ (shapefile, GeoJSON, vector formats)                  |
|  - memory/ (in-memory filtering)                              |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              INFRASTRUCTURE LAYER (~8,000 lines)              |
|  infrastructure/                                              |
|  - database/, cache/, utils/, logging/, di/, parallel/        |
+---------------------------------------------------------------+
```

---

## 3. Directory Structure

```
filter_mate/
├── filter_mate.py              # Plugin entry (QGIS integration)
├── filter_mate_app.py          # Application orchestrator (2,271 lines)
├── filter_mate_dockwidget.py   # UI management (5,987 lines)
│
├── core/                       # Business Logic (33.2% - 43,477 lines)
│   ├── domain/                 # Domain models (LayerInfo, FilterResult, etc.)
│   ├── services/               # 27 hexagonal services
│   ├── tasks/                  # Async tasks (filter, layer management)
│   ├── filter/                 # Expression building/sanitizing
│   ├── geometry/               # Buffer, CRS, spatial index
│   ├── optimization/           # Query optimization, performance advisor
│   ├── ports/                  # Port interfaces (hexagonal)
│   └── strategies/             # Multi-step, progressive filtering
│
├── adapters/                   # External Integrations (19.4% - 26,723 lines)
│   ├── backends/               # postgresql/, spatialite/, ogr/, memory/
│   ├── qgis/                   # QGIS adapters (signals, tasks)
│   ├── repositories/           # Data access (LayerRepository)
│   └── app_bridge.py           # DI Container
│
├── infrastructure/             # Cross-cutting (9.8% - 12,067 lines)
│   ├── cache/                  # LRU cache, geometry/query cache
│   ├── database/               # Connection pool, SQL utilities
│   ├── utils/                  # Layer utils, validation
│   └── logging/, di/, parallel/, streaming/
│
├── ui/                         # Presentation (23.2% - 29,202 lines)
│   ├── controllers/            # 13 MVC controllers
│   ├── widgets/                # Custom widgets
│   ├── styles/                 # Theming (IconManager, ThemeWatcher)
│   └── dialogs/                # Configuration dialogs
│
├── tests/                      # Test suite (106 tests, 85% coverage)
├── before_migration/           # ARCHIVED: Legacy modules/ code
└── config/                     # Configuration files
```

---

## 4. Code Statistics

| Layer | Directory | Lines | % | Files |
|-------|-----------|-------|---|-------|
| Core Domain | core/ | 43,477 | 33.2% | 95 |
| Adapters | adapters/ | 26,723 | 19.4% | 68 |
| UI Layer | ui/ | 29,202 | 23.2% | 55 |
| Infrastructure | infrastructure/ | 12,067 | 9.8% | 37 |
| Tests | tests/ | 47,600 | - | 106 |
| **TOTAL** | | **271,837** | **100%** | **546** |

### Quality Metrics (v4.1.0)

| Metric | Value | Target |
|--------|-------|--------|
| Test Coverage | 85% | 80% |
| Automated Tests | 106 | - |
| Logging Compliance | 88% | - |
| Services | 27 | - |
| Controllers | 13 | - |
| Backends | 4 | - |

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

**DEPRECATED (remove in v5.0):**
```python
# DON'T use these
from modules.appUtils import ...
from modules.tasks import ...
from modules.backends import ...
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

## 7. Performance Optimizers (v4.1.0)

1. **Auto Backend Selector** (2-5x speedup)
   - Intelligent backend selection by dataset size
   - Thresholds: PostgreSQL ≥10k, Spatialite 100-50k, OGR >100k

2. **Multi-Step Filter Optimizer** (2-8x speedup)
   - Filter decomposition: Spatial → Attribute → Complex
   - Per-step selectivity estimation

3. **Exploring Features Cache** (100-500x on cache hits)
   - TTL: 300s, LRU eviction

4. **Async Expression Evaluation** (UI non-blocking)
   - Auto-async threshold: >10,000 features

---

## 8. Undo/Redo System

### Architecture
- **FilterState**: Single layer state
- **GlobalFilterState**: Multi-layer state (source + remote)
- **FilterHistory**: Per-layer history stack
- **HistoryManager**: Global history management

### Behavior (v4.1.3)
- Peeks at history entry to determine operation type
- `layer_count > 1` → global undo/redo
- `layer_count == 1` → layer-only undo/redo

### Stack Size
- Per-layer: 100 states
- Global: 100 states

---

## 9. Known Issues & Critical Fixes

### Recent Fixes (v4.1.x)

| Version | Issue | Status |
|---------|-------|--------|
| v4.1.6 | Signal handler stale lambdas | Fixed |
| v4.1.5 | User actions blocked after filter | Fixed |
| v4.1.4 | OGR distant layer geometric filtering | Fixed |
| v4.1.3 | Undo/redo respects history entry type | Fixed |

### Critical Safety Modules
- `modules/object_safety.py`: Safe wrappers for C++ operations
  - `is_qgis_alive()`, `is_valid_layer()`, `safe_set_layer_variable()`

### Performance Audit Issues

**Immediate (Before Release):**
1. Remove 16 print DEBUG statements
2. Remove UI DEBUG message
3. Add tests for REGRESSION FIX areas

**Duplications to Merge:**
- `prepare_spatialite_source_geom()` - 3 implementations
- `prepare_ogr_source_geom()` - 2 implementations
- `legacy_adapter.py` - 2 files

---

## 10. Design Patterns

- **Hexagonal Architecture** (Ports & Adapters)
- **Factory Pattern** (BackendFactory, QGISFactory)
- **Strategy Pattern** (Multi-backend, Multi-step filtering)
- **Repository Pattern** (LayerRepository, HistoryRepository)
- **Service Locator** (app_bridge.py)
- **MVC** (UI layer)
- **Observer** (Signal/slot connections)

---

## 11. Roadmap

### v4.1.0 Completed
- [x] Performance optimizers (4 new)
- [x] 85% test coverage
- [x] 88% logging compliance
- [x] Hexagonal architecture complete

### v5.0 Planned
- [ ] Plugin API for extensibility
- [ ] Remove modules/ shims completely
- [ ] Parallel processing improvements (2x on 1M+ features)
- [ ] WebSocket real-time updates

---

## 12. File References

| Category | Key Files |
|----------|-----------|
| Entry | `filter_mate.py` |
| App | `filter_mate_app.py` (2,271 lines) |
| UI | `filter_mate_dockwidget.py` (5,987 lines) |
| Main Task | `core/tasks/filter_task.py` (5,217 lines) |
| Services | `core/services/` (27 services) |
| Controllers | `ui/controllers/` (13 controllers) |
| Backends | `adapters/backends/` (4 backends) |
| Tests | `tests/` (106 tests) |
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
