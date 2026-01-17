# Architecture Overview - FilterMate v4.0.3

**Last Updated:** January 17, 2026
**Current Version:** 4.0.3 (v4.0.5 in development)
**Key Features:** Hexagonal architecture complete, Multi-backend filtering, Progressive filtering, modules/ fully removed

## System Architecture (v4.0 Hexagonal - Complete)

FilterMate follows a **complete hexagonal architecture** with clear separation of concerns.
The `modules/` folder has been **fully migrated** to `before_migration/modules/` (archived).

```
+---------------------------------------------------------------+
|                      UI LAYER (5,987 lines)                   |
|  filter_mate_dockwidget.py                                    |
|  -> Delegates to ui/controllers/                              |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              CONTROLLER LAYER (13,143 lines)                  |
|  ui/controllers/                                              |
|  - integration.py (2,971) - Orchestration                     |
|  - exploring_controller.py (2,922)                            |
|  - filtering_controller.py (1,467)                            |
|  - property_controller.py (1,267)                             |
|  - layer_sync_controller.py (1,244)                           |
|  - ... (12 controllers total)                                 |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              APPLICATION LAYER (2,271 lines)                  |
|  filter_mate_app.py                                           |
|  -> Delegates to core/services/ (hexagonal)                   |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|               SERVICE LAYER (14,520 lines)                    |
|  core/services/ (26 services)                                 |
|  - layer_lifecycle_service.py (860)                           |
|  - favorites_service.py (853)                                 |
|  - filter_service.py (785)                                    |
|  - expression_service.py (741)                                |
|  - backend_service.py (735)                                   |
|  - layer_service.py (728)                                     |
|  - ... (20+ more services)                                    |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|                 TASK LAYER (~8,900 lines)                     |
|  core/tasks/                                                  |
|  - filter_task.py (5,217) - Main filtering task               |
|  - layer_management_task.py (1,869)                           |
|  - expression_evaluation_task.py                              |
|  - task_completion_handler.py                                 |
|  + cache/, builders/, collectors/, connectors/                |
|  + dispatchers/, executors/ subdirectories                    |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|               BACKEND LAYER (~4,000 lines)                    |
|  adapters/backends/                                           |
|  - spatialite/filter_executor.py (1,144)                      |
|  - ogr/filter_executor.py (1,033)                             |
|  - postgresql/filter_executor.py (948)                        |
|  - postgresql/filter_actions.py (787)                         |
|  - + memory/ backend                                          |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              INFRASTRUCTURE LAYER (~8,000 lines)              |
|  infrastructure/                                              |
|  - database/ (connection_pool, postgresql/spatialite_support) |
|  - cache/ (cache_manager, geometry_cache, query_cache)        |
|  - utils/ (layer_utils 1,185, complexity_estimator, etc.)     |
|  - logging/, di/, feedback/, parallel/, streaming/            |
|  - state/, config/                                            |
+---------------------------------------------------------------+

ARCHIVED: before_migration/modules/ (legacy code preserved)
```

## Code Statistics by Layer (January 17, 2026)

| Layer | Directory | Lines | Key Files |
|-------|-----------|-------|-----------|
| **Core Tasks** | core/tasks/ | ~8,900 | filter_task.py (5,217) |
| **Core Services** | core/services/ | ~14,520 | 26 services |
| **Core Other** | core/domain,filter,geometry,optimization,ports,strategies | ~5,000 | Domain models, ports |
| **Adapters** | adapters/ | ~15,000 | backends, qgis, repositories |
| **Infrastructure** | infrastructure/ | ~8,000 | cache, database, utils |
| **UI** | ui/ | ~15,000 | controllers, widgets, styles |
| **Root Files** | *.py | ~8,300 | app.py, dockwidget.py |
| **Tests** | tests/ | ~47,600 | 157 test files |
| **TOTAL** | | **~109,000** | **220+ files** |

## Core Files (Current Architecture v4.0)

### 1. Plugin Entry Point
**File:** `filter_mate.py`
**Purpose:** QGIS integration and lifecycle management

### 2. Application Orchestrator
**File:** `filter_mate_app.py` (2,271 lines)
**Purpose:** Central coordinator between UI and backend

### 3. UI Management
**File:** `filter_mate_dockwidget.py` (5,987 lines)
**Purpose:** User interface and interaction handling

### 4. Task Execution Layer
**Location:** `core/tasks/`
**Files:**
- `filter_task.py` (5,217 lines) - Main filtering task
- `layer_management_task.py` (1,869 lines) - Layer operations
- `expression_evaluation_task.py` - Expression evaluation
- `task_completion_handler.py` - Task completion handling
**Subdirectories:**
- `builders/` - Subset string builders
- `cache/` - Expression and geometry cache
- `collectors/` - Feature collectors
- `connectors/` - Backend connectors
- `dispatchers/` - Action dispatchers
- `executors/` - Attribute/spatial filter executors

### 5. Service Layer (Hexagonal)
**Location:** `core/services/` (26 services, 14,520 lines)
**Top Services by Size:**
- `layer_lifecycle_service.py` (860) - Layer lifecycle management
- `favorites_service.py` (853) - Filter favorites
- `filter_service.py` (785) - Core filtering logic
- `expression_service.py` (741) - Expression handling
- `backend_service.py` (735) - Backend coordination
- `layer_service.py` (728) - Layer management
- `geometry_preparer.py` (703) - Geometry preparation
- `postgres_session_manager.py` (698) - PostgreSQL sessions
- `app_initializer.py` (696) - Application initialization
- `auto_optimizer.py` (678) - Auto optimization
- `history_service.py` (625) - Undo/Redo history

### 6. Controller Layer (MVC)
**Location:** `ui/controllers/` (12 controllers, ~13,143 lines)
**Key Controllers:**
- `integration.py` (2,971) - UI orchestration
- `exploring_controller.py` (2,922) - Feature explorer
- `filtering_controller.py` (1,467) - Filter operations
- `property_controller.py` (1,267) - Layer properties
- `layer_sync_controller.py` (1,244) - Layer synchronization
- `exporting_controller.py` (975) - Export operations
- `backend_controller.py` (974) - Backend management

### 7. Backend Layer
**Location:** `adapters/backends/`
**Backends:**
- `postgresql/` - PostgreSQL/PostGIS (optimal for large datasets)
- `spatialite/` - Spatialite (good for medium datasets)
- `ogr/` - OGR fallback (shapefiles, GeoPackage)
- `memory/` - In-memory processing

### 8. Infrastructure Layer
**Location:** `infrastructure/`
**Modules:**
- `database/` - connection_pool (995), postgresql_support, spatialite_support
- `cache/` - cache_manager, geometry_cache, query_cache, exploring_cache
- `utils/` - layer_utils (1,185), complexity_estimator, validation_utils
- `logging/` - setup_logger, safe_log
- `di/` - Dependency injection container
- `feedback/` - User feedback utilities
- `parallel/` - Parallel executor
- `streaming/` - Result streaming
- `state/` - Flag manager, state manager

## God Classes - Migration COMPLETE ✅

| File | Peak (Legacy) | Current | Reduction |
|------|---------------|---------|-----------|
| filter_task.py | 12,894 | 5,217 | -60% |
| dockwidget.py | 12,000+ | 5,987 | -50% |
| app.py | 5,900+ | 2,271 | -62% |
| **TOTAL** | ~30,794 | 13,475 | **-56%** |

*Note: Current numbers higher than v4.0.0-alpha due to new features added.*

## Import Guidelines (v4.0+)

### Standard Imports
```python
# PostgreSQL availability
from adapters.backends.postgresql_availability import POSTGRESQL_AVAILABLE

# Tasks
from core.tasks import FilterEngineTask, LayersManagementEngineTask

# Backends
from adapters.backends import BackendFactory, PostgreSQLBackend, SpatialiteBackend

# Utilities
from infrastructure.utils import get_datasource_connexion_from_layer
from infrastructure.utils.layer_utils import is_layer_valid

# Services
from core.services import FilterService, LayerService, ExpressionService

# Domain
from core.domain import FilterResult, LayerInfo, FilterExpression
```

## Next Steps (v5.0)

1. ✅ modules/ folder removed (now in before_migration/)
2. ⏳ 80% test coverage target (currently ~75%)
3. ⏳ Performance optimization (caching layer)
4. ⏳ Plugin API for extensibility

---

**Last Updated:** January 17, 2026
**Status:** v4.0.3 Production, Hexagonal Architecture Complete