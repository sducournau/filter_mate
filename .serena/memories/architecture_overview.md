# Architecture Overview - FilterMate v4.0-alpha

**Last Updated:** January 12, 2026
**Current Version:** 4.0-alpha (EPIC-1 Migration Complete)
**Key Features:** Hexagonal architecture, Multi-backend filtering, Progressive filtering, God classes eliminated (-67%), modules/ deprecated

## System Architecture (v4.0 Hexagonal)

FilterMate follows a **hexagonal architecture** with clear separation of concerns.
The `modules/` folder contains ONLY backward compatibility shims (to be removed in v5.0).

```
+---------------------------------------------------------------+
|                      UI LAYER (2,494 lines)                   |
|  filter_mate_dockwidget.py                                    |
|  -> Delegates to ui/controllers/                              |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              CONTROLLER LAYER (13,143 lines)                  |
|  ui/controllers/                                              |
|  - integration.py (2,471) - Orchestration                     |
|  - exploring_controller.py (2,397)                            |
|  - filtering_controller.py (1,305)                            |
|  - ... (10 controllers total)                                 |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              APPLICATION LAYER (1,667 lines)                  |
|  filter_mate_app.py                                           |
|  -> Delegates to core/services/ (hexagonal)                   |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|               SERVICE LAYER (10,528 lines)                    |
|  core/services/                                               |
|  - filter_service.py, layer_service.py                        |
|  - expression_service.py, history_service.py                  |
|  - ... (20 services total)                                    |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|                 TASK LAYER (~7,800 lines)                     |
|  core/tasks/                                                  |
|  - filter_task.py (6,022) - Main filtering task               |
|  - layer_management_task.py (~1,800)                          |
|  - expression_evaluation_task.py                              |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|               BACKEND LAYER (~2,900 lines)                    |
|  adapters/backends/                                           |
|  - postgresql/filter_executor.py (~900)                       |
|  - spatialite/filter_executor.py (~1,100)                     |
|  - ogr/filter_executor.py (~900)                              |
+---------------------------+-----------------------------------+
                            |
+---------------------------v-----------------------------------+
|              INFRASTRUCTURE LAYER                             |
|  infrastructure/                                              |
|  - logging/, cache/, utils/, database/                        |
|  - di/, feedback/, parallel/, streaming/                      |
+---------------------------------------------------------------+

DEPRECATED: modules/ (~1,978 lines - shims only)
   -> All code migrated to core/, adapters/, infrastructure/
   -> Will be removed in v5.0
```

## Core Files (Current Architecture v4.0)

### 1. Plugin Entry Point
**File:** \`filter_mate.py\`
**Purpose:** QGIS integration and lifecycle management

### 2. Application Orchestrator
**File:** \`filter_mate_app.py\` (1,667 lines)
**Purpose:** Central coordinator between UI and backend

### 3. UI Management
**File:** \`filter_mate_dockwidget.py\` (2,494 lines)
**Purpose:** User interface and interaction handling

### 4. Task Execution Layer
**Location:** \`core/tasks/\`
**Files:**
- \`filter_task.py\` (6,022 lines) - Main filtering task
- \`layer_management_task.py\` (~1,800 lines) - Layer operations
- \`expression_evaluation_task.py\` - Expression evaluation

### 5. Service Layer (Hexagonal)
**Location:** \`core/services/\` (20 services, 10,528 lines)
**Key Services:**
- \`filter_service.py\` (785) - Core filtering logic
- \`layer_service.py\` (545) - Layer management
- \`expression_service.py\` (850) - Expression handling
- \`history_service.py\` (488) - Undo/Redo history
- \`favorites_service.py\` (808) - Filter favorites
- \`backend_service.py\` (726) - Backend coordination

### 6. Controller Layer (MVC)
**Location:** \`ui/controllers/\` (10 controllers, 13,143 lines)
**Key Controllers:**
- \`integration.py\` (2,471) - Orchestration
- \`exploring_controller.py\` (2,397) - Feature explorer
- \`filtering_controller.py\` (1,305) - Filter operations
- \`property_controller.py\` (1,251) - Layer properties
- \`layer_sync_controller.py\` (1,170) - Layer synchronization

### 7. Backend Layer
**Location:** \`adapters/backends/\`
**Backends:**
- \`postgresql/\` - PostgreSQL/PostGIS (optimal for large datasets)
- \`spatialite/\` - Spatialite (good for medium datasets)
- \`ogr/\` - OGR fallback (shapefiles, GeoPackage)

### 8. Infrastructure Layer
**Location:** \`infrastructure/\`
**Modules:**
- \`logging/\` - setup_logger, safe_log
- \`cache/\` - query_cache, geometry_cache
- \`utils/\` - layer_utils, task_utils
- \`database/\` - prepared_statements
- \`constants.py\` - global constants

## DEPRECATED: modules/ Folder

The \`modules/\` folder now contains **ONLY compatibility shims** (~1,978 lines).
All code has been migrated to:
- \`modules/appUtils.py\` -> \`infrastructure/utils/\`
- \`modules/appTasks.py\` -> \`core/tasks/\`
- \`modules/backends/\` -> \`adapters/backends/\`
- \`modules/constants.py\` -> \`infrastructure/constants.py\`

## Import Guidelines

### DEPRECATED (will be removed in v5.0)
\`\`\`python
# DON'T use these
from modules.appUtils import POSTGRESQL_AVAILABLE
from modules.tasks import FilterEngineTask
from modules.backends import BackendFactory
\`\`\`

### NEW IMPORTS (use these)
\`\`\`python
# PostgreSQL availability
from adapters.backends.postgresql_availability import POSTGRESQL_AVAILABLE

# Tasks
from core.tasks import FilterEngineTask, LayersManagementEngineTask

# Backends
from adapters.backends import BackendFactory, PostgreSQLBackend, SpatialiteBackend

# Utilities
from infrastructure.utils import get_datasource_connexion_from_layer

# Services
from core.services import FilterService, LayerService, ExpressionService
\`\`\`

## God Classes - Migration Complete

| File | Peak (Legacy) | Current | Reduction |
|------|---------------|---------|-----------|
| filter_task.py | 12,894 | 6,022 | -53% |
| dockwidget.py | 12,000+ | 2,494 | -79% |
| app.py | 5,900+ | 1,667 | -72% |
| **TOTAL** | ~30,794 | 10,184 | **-67%** |

## Next Steps (v5.0)

1. Remove \`modules/\` folder entirely
2. Update all external imports
3. Performance optimization (caching layer)
4. 80% test coverage target

---

**Last Updated:** January 12, 2026
**Status:** EPIC-1 Complete, v5.0 Cleanup Ready
