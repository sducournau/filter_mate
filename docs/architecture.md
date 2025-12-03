# FilterMate Architecture Overview

## System Architecture

### High-Level Component Diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│                         QGIS Application                               │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐│
│  │                    QGIS Plugin Manager                            ││
│  └────────────────────────────┬─────────────────────────────────────┘│
└───────────────────────────────┼──────────────────────────────────────┘
                                │
                                ▼
┌───────────────────────────────────────────────────────────────────────┐
│                         FilterMate Plugin                              │
│                                                                        │
│  ┌─────────────────┐                                                  │
│  │ filter_mate.py  │  Plugin Entry Point                              │
│  │                 │  - initGui()                                     │
│  │                 │  - unload()                                      │
│  └────────┬────────┘                                                  │
│           │                                                            │
│           ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────────┐ │
│  │                    FilterMateApp                                 │ │
│  │                  (Main Orchestrator)                             │ │
│  │                                                                   │ │
│  │  - PROJECT_LAYERS (state management)                             │ │
│  │  - manage_task() (task dispatcher)                               │ │
│  │  - layer_management_engine_task_completed()                      │ │
│  │  - filter_engine_task_completed()                                │ │
│  │  - init_filterMate_db() (Spatialite metadata)                    │ │
│  └──────────┬────────────────────────────┬─────────────────────────┘ │
│             │                            │                            │
│             ▼                            ▼                            │
│  ┌──────────────────────┐    ┌──────────────────────────────────┐   │
│  │ FilterMateDockWidget │    │        appTasks                  │   │
│  │   (UI Management)    │    │   (Async Execution)              │   │
│  │                      │    │                                  │   │
│  │ - Widget init        │    │ - FilterEngineTask              │   │
│  │ - Signal handling    │    │ - LayersManagementEngineTask    │   │
│  │ - User input         │    │ - PopulateListEngineTask        │   │
│  │ - Property mgmt      │    │                                  │   │
│  └──────────────────────┘    └───────────────┬──────────────────┘   │
│                                               │                       │
│                                               ▼                       │
│                                  ┌────────────────────────────────┐  │
│                                  │    Backend System              │  │
│                                  │                                │  │
│                                  │  ┌──────────────────────────┐ │  │
│                                  │  │  BackendFactory          │ │  │
│                                  │  │  (Backend Selection)     │ │  │
│                                  │  └────────┬─────────────────┘ │  │
│                                  │           │                   │  │
│                                  │  ┌────────▼────────┐          │  │
│                                  │  │                 │          │  │
│                                  │  │  PostgreSQL ◄───┼──────┐   │  │
│                                  │  │   Backend       │      │   │  │
│                                  │  │                 │      │   │  │
│                                  │  └─────────────────┘      │   │  │
│                                  │                           │   │  │
│                                  │  ┌─────────────────┐      │   │  │
│                                  │  │  Spatialite  ◄──┼──────┤   │  │
│                                  │  │   Backend       │      │   │  │
│                                  │  │                 │      │   │  │
│                                  │  └─────────────────┘      │   │  │
│                                  │                           │   │  │
│                                  │  ┌─────────────────┐      │   │  │
│                                  │  │   OGR Backend ◄─┼──────┘   │  │
│                                  │  │   (Fallback)    │          │  │
│                                  │  │                 │          │  │
│                                  │  └─────────────────┘          │  │
│                                  │                                │  │
│                                  │  All inherit from:             │  │
│                                  │  GeometricFilterBackend        │  │
│                                  └────────────────────────────────┘  │
│                                                                       │
│  Supporting Modules:                                                 │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │ appUtils   │  │ state_manager│  │ logging      │                │
│  │ (DB Utils) │  │ (State Mgmt) │  │ (Logging)    │                │
│  └────────────┘  └──────────────┘  └──────────────┘                │
└───────────────────────────────────────────────────────────────────────┘
```

## Data Flow Diagrams

### 1. Layer Addition Flow

```
┌──────────────┐
│ User adds    │
│ layer to     │
│ QGIS project │
└──────┬───────┘
       │
       ▼
┌─────────────────────────────────┐
│ QGIS emits layersAdded signal   │
└──────┬──────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ FilterMateApp receives signal           │
│ - Connected in __init__()               │
│ - Calls manage_task('add_layers')      │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ Creates LayersManagementEngineTask      │
│ - Task runs in background thread        │
│ - Extracts layer metadata               │
│ - Determines provider type              │
│ - Gets geometry type                    │
│ - Finds primary key                     │
│ - Collects field information            │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ Task completed callback                 │
│ - layer_management_engine_task_completed│
│ - Updates PROJECT_LAYERS dictionary     │
│ - Stores metadata in Spatialite DB      │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ Updates UI (FilterMateDockWidget)       │
│ - get_project_layers_from_app()         │
│ - Populates layer comboboxes            │
│ - Updates layer count                   │
│ - Refreshes backend indicator           │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ Layer ready for filtering               │
└─────────────────────────────────────────┘
```

### 2. Filtering Operation Flow

```
┌──────────────────────┐
│ User configures      │
│ filter options:      │
│ - Source layer       │
│ - Target layers      │
│ - Predicates         │
│ - Buffer             │
└──────┬───────────────┘
       │
       ▼
┌────────────────────────────────────┐
│ User clicks Filter button          │
└──────┬─────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ FilterMateDockWidget.launchTaskEvent()  │
│ - Emits launchingTask signal            │
│ - Passes task name and parameters       │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ FilterMateApp.manage_task('filter')     │
│ - Validates input                       │
│ - Prepares task parameters              │
│ - Gets layer properties from            │
│   PROJECT_LAYERS                        │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ Creates FilterEngineTask                │
│ - Runs in background thread             │
│ - Executes in run() method              │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ Backend Selection                       │
│ BackendFactory.get_backend()            │
│                                         │
│ IF layer.providerType() == 'postgres'  │
│    AND POSTGRESQL_AVAILABLE:           │
│    → PostgreSQLGeometricFilter          │
│                                         │
│ ELIF layer.providerType() == 'spatialite':│
│    → SpatialiteGeometricFilter          │
│                                         │
│ ELSE:                                   │
│    → OGRGeometricFilter (fallback)      │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ Backend builds filter expression       │
│ backend.build_expression()              │
│                                         │
│ For each target layer:                 │
│   1. Get geometry field                │
│   2. Apply buffer if specified         │
│   3. Build predicate expressions       │
│   4. Combine with OR/AND               │
│                                         │
│ Example output:                         │
│ PostgreSQL:                             │
│   ST_Intersects(                        │
│     ST_Buffer("geom", 100),             │
│     ST_GeomFromText('...')              │
│   )                                     │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ Backend applies filter                  │
│ backend.apply_filter()                  │
│                                         │
│ Sets layer subset string or             │
│ applies provider-specific filter        │
│                                         │
│ layer.setSubsetString(expression)       │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ Task completion callback                │
│ filter_engine_task_completed()          │
│                                         │
│ - Updates layer extents                 │
│ - Triggers layer repaint                │
│ - Saves filter to database              │
│ - Shows success message                 │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ UI updates                              │
│ - Map refreshes                         │
│ - Feature count updates                 │
│ - Widgets re-enable                     │
└──────┬──────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────┐
│ Filtered layer visible in map          │
└─────────────────────────────────────────┘
```

### 3. State Management Flow

```
┌─────────────────────────────────────┐
│ Layer State (PROJECT_LAYERS)        │
│                                     │
│ {                                   │
│   "layer_id": {                     │
│     "infos": {                      │
│       "layer_name": str,            │
│       "provider_type": str,         │
│       "geometry_type": str,         │
│       ...                           │
│     },                              │
│     "exploring": {                  │
│       "single_selection_expr": str, │
│       "is_tracking": bool,          │
│       ...                           │
│     },                              │
│     "filtering": {                  │
│       "layers_to_filter": list,     │
│       "predicates": list,           │
│       ...                           │
│     }                               │
│   }                                 │
│ }                                   │
└────────┬────────────────────────────┘
         │
         ├─────────────────────────────┐
         │                             │
         ▼                             ▼
┌──────────────────┐        ┌──────────────────┐
│ Runtime Storage  │        │ Persistent       │
│ (In Memory)      │        │ Storage          │
│                  │        │ (Spatialite DB)  │
│ - Fast access    │        │                  │
│ - Lost on close  │        │ - Survives       │
│                  │        │   sessions       │
│ FilterMateApp.   │        │ - Tables:        │
│ PROJECT_LAYERS   │        │   fm_projects    │
│                  │        │   fm_layers_props│
│                  │        │   fm_subset_hist │
└──────────────────┘        └──────────────────┘
         │                             │
         │                             │
         ▼                             ▼
┌─────────────────────────────────────────┐
│ NEW: State Manager                       │
│ (modules/state_manager.py)              │
│                                         │
│ LayerStateManager:                      │
│ - add_layer()                           │
│ - remove_layer()                        │
│ - get_layer_properties()                │
│ - update_layer_property()               │
│                                         │
│ ProjectStateManager:                    │
│ - set_config()                          │
│ - get_config()                          │
│ - add_datasource()                      │
│ - get_datasource()                      │
└─────────────────────────────────────────┘
```

## Backend Architecture

### Backend Class Hierarchy

```
GeometricFilterBackend (ABC)
├── Abstract Methods:
│   ├── build_expression()
│   ├── apply_filter()
│   ├── supports_layer()
│   └── get_backend_name()
│
├── Helper Methods:
│   ├── prepare_geometry_expression()
│   ├── validate_layer_properties()
│   ├── build_buffer_expression()
│   ├── combine_expressions()
│   └── Logging methods
│
└── Implementations:
    │
    ├── PostgreSQLGeometricFilter
    │   ├── Uses PostGIS functions
    │   ├── ST_Intersects, ST_Buffer, etc.
    │   ├── Requires psycopg2
    │   └── Best for > 100k features
    │
    ├── SpatialiteGeometricFilter
    │   ├── Uses Spatialite functions
    │   ├── 90% compatible with PostGIS
    │   ├── Python sqlite3 module
    │   └── Good for < 100k features
    │
    └── OGRGeometricFilter
        ├── Fallback for all providers
        ├── Uses QGIS processing
        ├── Memory-based operations
        └── Universal compatibility
```

### Backend Selection Logic

```
┌─────────────────────────────────┐
│ BackendFactory.get_backend()    │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ Check layer.providerType()              │
└────────┬────────────────────────────────┘
         │
         ├──► provider == 'postgres' ?
         │    │
         │    ├── Yes → Check POSTGRESQL_AVAILABLE
         │    │         │
         │    │         ├── True  → PostgreSQLGeometricFilter
         │    │         └── False → SpatialiteGeometricFilter
         │    │
         │    └── No ──┐
         │             │
         ├──► provider == 'spatialite' ?
         │    │
         │    ├── Yes → SpatialiteGeometricFilter
         │    │
         │    └── No ──┐
         │             │
         └──► Default → OGRGeometricFilter (fallback)
```

## Component Interactions

### Signal/Slot Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    FilterMateDockWidget                          │
│                                                                  │
│  PyQt5 Signals (emitted):                                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ launchingTask → FilterMateApp.manage_task()             │  │
│  │ settingLayerVariable → FilterMateApp.save_variables...()│  │
│  │ resettingLayerVariable → FilterMateApp.remove_variables│  │
│  │ settingProjectVariables → FilterMateApp.save_project... │  │
│  │ closingPlugin → FilterMate.unload()                     │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                  │
│  PyQt5 Slots (connected):                                       │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ Widget signals:                                          │  │
│  │ - combobox.currentLayerChanged                          │  │
│  │ - button.clicked                                        │  │
│  │ - checkable_combobox.checkedItemsChanged               │  │
│  │ - field_expression.fieldChanged                         │  │
│  │                                                          │  │
│  │ QGIS signals:                                            │  │
│  │ - layer.selectionChanged                                │  │
│  │ - layer_tree_view.currentLayerChanged                   │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    FilterMateApp                                 │
│                                                                  │
│  Connected to:                                                   │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ QGIS Project signals:                                    │  │
│  │ - MapLayerStore.layersAdded                             │  │
│  │ - MapLayerStore.layersRemoved                           │  │
│  │                                                          │  │
│  │ Dockwidget signals (see above)                          │  │
│  │                                                          │  │
│  │ Task signals:                                            │  │
│  │ - QgsTask.taskCompleted                                 │  │
│  │ - QgsTask.taskTerminated                                │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Task Execution Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Thread (UI)                          │
│                                                              │
│  ┌────────────────┐                                         │
│  │ User Action    │                                         │
│  └───────┬────────┘                                         │
│          │                                                   │
│          ▼                                                   │
│  ┌────────────────────────────┐                            │
│  │ Create QgsTask             │                            │
│  │ - FilterEngineTask         │                            │
│  │ - LayersManagementTask     │                            │
│  │ - PopulateListTask         │                            │
│  └───────┬────────────────────┘                            │
│          │                                                   │
│          ▼                                                   │
│  ┌────────────────────────────┐                            │
│  │ QgsApplication.taskManager()│                            │
│  │ .addTask(task)             │                            │
│  └───────┬────────────────────┘                            │
│          │                                                   │
└──────────┼───────────────────────────────────────────────────┘
           │
           │  Task handed to background thread
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                  Background Thread                           │
│                                                              │
│  ┌────────────────────────────┐                            │
│  │ QgsTask.run()              │                            │
│  │                            │                            │
│  │ - Backend selection        │                            │
│  │ - Expression building      │                            │
│  │ - Heavy computation        │                            │
│  │ - Database operations      │                            │
│  │                            │                            │
│  │ Returns True/False         │                            │
│  └───────┬────────────────────┘                            │
│          │                                                   │
│          │  Task completes                                  │
│          │                                                   │
└──────────┼───────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│                Main Thread (UI) - Callback                   │
│                                                              │
│  ┌────────────────────────────┐                            │
│  │ QgsTask.finished(result)   │                            │
│  │                            │                            │
│  │ - Update UI                │                            │
│  │ - Show messages            │                            │
│  │ - Refresh layers           │                            │
│  │ - Re-enable controls       │                            │
│  └────────────────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema

### Spatialite Metadata Database

FilterMate uses a Spatialite database for storing metadata and configuration.

**Location**: `<project_directory>/.filterMate/<project_name>.db`

```sql
-- Project metadata
CREATE TABLE fm_projects (
    project_id VARCHAR(255) PRIMARY KEY,
    _created_at DATETIME NOT NULL,
    _updated_at DATETIME NOT NULL,
    project_name VARCHAR(255) NOT NULL,
    project_path VARCHAR(255) NOT NULL,
    project_settings TEXT NOT NULL  -- JSON
);

-- Layer properties (persistent storage of PROJECT_LAYERS)
CREATE TABLE fm_project_layers_properties (
    id VARCHAR(255) PRIMARY KEY,
    _updated_at DATETIME NOT NULL,
    fk_project VARCHAR(255) NOT NULL,
    layer_id VARCHAR(255) NOT NULL,
    meta_type VARCHAR(255) NOT NULL,     -- 'infos', 'exploring', 'filtering'
    meta_key VARCHAR(255) NOT NULL,
    meta_value TEXT NOT NULL,
    FOREIGN KEY (fk_project) REFERENCES fm_projects(project_id),
    UNIQUE(fk_project, layer_id, meta_type, meta_key) ON CONFLICT REPLACE
);

-- Subset string history (filter history)
CREATE TABLE fm_subset_history (
    id VARCHAR(255) PRIMARY KEY,
    _updated_at DATETIME NOT NULL,
    fk_project VARCHAR(255) NOT NULL,
    layer_id VARCHAR(255) NOT NULL,
    layer_source_id VARCHAR(255) NOT NULL,
    seq_order INTEGER NOT NULL,
    subset_string TEXT NOT NULL,
    FOREIGN KEY (fk_project) REFERENCES fm_projects(project_id)
);
```

## Configuration Management

### Configuration Hierarchy

```
┌─────────────────────────────────────────────────────────┐
│                   config/config.json                     │
│                                                          │
│  {                                                       │
│    "APP": {                                              │
│      "OPTIONS": {                                        │
│        "FRESH_RELOAD_FLAG": false,                      │
│        ...                                               │
│      }                                                   │
│    },                                                    │
│    "CURRENT_PROJECT": {                                  │
│      "OPTIONS": {                                        │
│        "ACTIVE_POSTGRESQL": "",                         │
│        "IS_ACTIVE_POSTGRESQL": false,                   │
│        ...                                               │
│      },                                                  │
│      "FILTER": { ... },                                  │
│      "EXPLORING": { ... }                                │
│    }                                                     │
│  }                                                       │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              config/config.py (Loader)                   │
│                                                          │
│  ENV_VARS = load_config()                               │
│                                                          │
│  - Reads JSON file                                       │
│  - Validates structure                                   │
│  - Sets defaults                                         │
│  - Detects platform                                      │
└────────┬────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│              Global ENV_VARS                             │
│                                                          │
│  Used throughout application:                            │
│  - FilterMateApp.CONFIG_DATA                            │
│  - FilterMateDockWidget.CONFIG_DATA                     │
│  - Backend configuration                                 │
└─────────────────────────────────────────────────────────┘
```

## Performance Considerations

### Backend Performance Profiles

```
Feature Count    PostgreSQL      Spatialite      OGR
─────────────   ──────────────  ─────────────  ─────────────
< 1,000         ✓ Fast          ✓ Fast         ✓ Fast
1,000 - 10,000  ✓ Fast          ✓ Fast         ✓ Acceptable
10,000 - 100k   ✓ Fast          ✓ Good         ⚠ Slow
100k - 1M       ✓ Fast          ⚠ Moderate     ✗ Very Slow
> 1M            ✓ Fast          ✗ Slow         ✗ Very Slow

✓ Recommended    ⚠ Use with caution    ✗ Not recommended
```

### Optimization Strategies

1. **PostgreSQL Backend**
   - Server-side spatial indexing
   - Materialized views
   - Query optimization
   - Parallel processing support

2. **Spatialite Backend**
   - R-tree spatial indexes
   - Temporary tables
   - VACUUM for optimization
   - Smaller datasets only

3. **OGR Backend**
   - Warn users for large datasets
   - Use QGIS spatial index when available
   - Consider converting to database format

## Error Handling Strategy

```
┌─────────────────────────────────────────────┐
│           Error Handling Layers              │
│                                             │
│  ┌───────────────────────────────────────┐ │
│  │ User-Facing (UI)                      │ │
│  │ - QGIS message bar                    │ │
│  │ - Dialog boxes                        │ │
│  │ - Status indicators                   │ │
│  └───────────────────────────────────────┘ │
│                    │                         │
│                    ▼                         │
│  ┌───────────────────────────────────────┐ │
│  │ Application Level                     │ │
│  │ - Try/except blocks                   │ │
│  │ - Graceful degradation                │ │
│  │ - Fallback mechanisms                 │ │
│  └───────────────────────────────────────┘ │
│                    │                         │
│                    ▼                         │
│  ┌───────────────────────────────────────┐ │
│  │ Backend Level                         │ │
│  │ - Backend validation                  │ │
│  │ - SQL error handling                  │ │
│  │ - Connection management               │ │
│  └───────────────────────────────────────┘ │
│                    │                         │
│                    ▼                         │
│  ┌───────────────────────────────────────┐ │
│  │ Logging                               │ │
│  │ - Debug logs                          │ │
│  │ - Error logs                          │ │
│  │ - Performance logs                    │ │
│  └───────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
```

## Future Architecture Improvements

### Planned Enhancements

1. **State Management**
   - ✅ Created `LayerStateManager` and `ProjectStateManager`
   - TODO: Migrate from PROJECT_LAYERS dict to StateManager
   - TODO: Add state persistence layer
   - TODO: Implement undo/redo functionality

2. **Backend System**
   - TODO: Add backend plugin system
   - TODO: Support custom user backends
   - TODO: Add backend configuration UI

3. **Performance**
   - TODO: Add caching layer
   - TODO: Implement query result caching
   - TODO: Add background prefetching

4. **Testing**
   - TODO: Increase test coverage to > 80%
   - TODO: Add integration tests
   - TODO: Add performance benchmarks

5. **Documentation**
   - ✅ Created Backend API docs
   - ✅ Created Developer Onboarding guide
   - TODO: Add video tutorials
   - TODO: Create interactive examples

## Architectural Principles

### Design Patterns Used

1. **Factory Pattern** - Backend selection
2. **Strategy Pattern** - Different backends for different providers
3. **Observer Pattern** - Qt signals and slots
4. **Singleton Pattern** - Configuration management
5. **Template Method** - Base backend class

### SOLID Principles

1. **Single Responsibility** - Each class has one clear purpose
2. **Open/Closed** - Backend system open for extension
3. **Liskov Substitution** - All backends interchangeable
4. **Interface Segregation** - Small, focused interfaces
5. **Dependency Inversion** - Depend on abstractions (GeometricFilterBackend)

### Code Organization

- **Separation of Concerns** - UI, logic, and data layers separated
- **Modularity** - Self-contained modules with clear boundaries
- **Testability** - Components designed for unit testing
- **Maintainability** - Clear naming, documentation, and structure

---

For more details:
- [Backend API Documentation](BACKEND_API.md)
- [Developer Onboarding Guide](DEVELOPER_ONBOARDING.md)
- [GitHub Copilot Instructions](../.github/copilot-instructions.md)
