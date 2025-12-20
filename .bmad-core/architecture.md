# FilterMate - Architecture Document

## 📋 Document Info

| Field | Value |
|-------|-------|
| **Version** | 2.0 |
| **Last Updated** | December 20, 2025 |
| **Architecture Style** | Layered + Factory Pattern |

---

## 1. System Overview

FilterMate follows a **layered architecture** with clear separation of concerns and a **factory pattern** for multi-backend support.

```
┌─────────────────────────────────────────────────────────────────┐
│                      QGIS Plugin Layer                          │
│                     (filter_mate.py)                            │
│   • Plugin lifecycle • QGIS integration • Menu/toolbar          │
└─────────────────────────────┬───────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────────┐
│                  Application Orchestrator                        │
│                  (filter_mate_app.py)                           │
│   • State management • Task coordination • Configuration        │
│   • Filter history • Undo/Redo • Project persistence            │
└───────────┬─────────────────────────────────────┬───────────────┘
            │                                     │
┌───────────▼───────────────┐        ┌────────────▼───────────────┐
│       UI Layer            │        │       Task Layer           │
│  (filter_mate_dockwidget) │        │   (modules/tasks/*.py)     │
│   • Widget management     │        │   • Async operations       │
│   • User interaction      │        │   • QgsTask execution      │
│   • Signal/slot           │        │   • Backend delegation     │
│   • Theme management      │        │   • Progress reporting     │
└───────────────────────────┘        └────────────┬───────────────┘
                                                  │
                                     ┌────────────▼───────────────┐
                                     │    Backend Factory         │
                                     │ (modules/backends/factory) │
                                     │   • Auto backend selection │
                                     │   • Forced backend support │
                                     └─────┬──────┬──────┬────────┘
                                           │      │      │
                            ┌──────────────▼──┐   │   ┌──▼─────────────┐
                            │ PostgreSQL      │   │   │ OGR Backend    │
                            │ Backend         │   │   │ (Fallback)     │
                            │ • Materialized  │   │   │ • QGIS Process │
                            │   views         │   │   │ • Memory layers│
                            │ • GIST indexes  │   │   │ • Universal    │
                            └─────────────────┘   │   └────────────────┘
                                      ┌───────────▼──────────┐
                                      │ Spatialite Backend   │
                                      │ • Temp tables        │
                                      │ • R-tree indexes     │
                                      │ • SQLite built-in    │
                                      └──────────────────────┘
```

---

## 2. Component Details

### 2.1 Plugin Entry Point (`filter_mate.py`)

**Responsibility**: QGIS integration and plugin lifecycle

| Method | Purpose |
|--------|---------|
| `initGui()` | Initialize plugin UI, register with QGIS |
| `unload()` | Cleanup on plugin disable |
| `run()` | Show/hide dockwidget |
| `_handle_project_change()` | React to project load/switch |
| `_handle_project_cleared()` | React to project close |

**Key Patterns**:
- Signal connection to `QgsProject.instance()` signals
- Lazy initialization of dockwidget
- Resource cleanup in `unload()`

### 2.2 Application Orchestrator (`filter_mate_app.py`)

**Responsibility**: Central coordinator between UI and backends

**Size**: ~2048 lines (after Phase 5d refactoring)

| Category | Methods |
|----------|---------|
| Task Management | `manage_task()`, `get_task_parameters()` |
| Callbacks | `filter_engine_task_completed()`, `layer_management_engine_task_completed()` |
| State | `add_layers()`, `remove_layers()`, `apply_subset_filter()` |
| History | `handle_undo()`, `handle_redo()`, `update_undo_redo_buttons()` |
| Database | `init_filterMate_db()`, `_ensure_db_directory()` |

**Key Constants**:
```python
STABILITY_CONSTANTS = {
    'MIN_LAYER_PROCESSING_DELAY': 0.1,
    'PROJECT_INITIALIZATION_TIMEOUT': 30,
    'ADD_LAYERS_DEBOUNCE_MS': 250,
    # ... more timing constants
}
```

### 2.3 UI Layer (`filter_mate_dockwidget.py`)

**Responsibility**: User interface and interaction

**Size**: ~5077 lines (after Phase 4c/4d refactoring)

| Section | Purpose |
|---------|---------|
| Widget Setup | Initialize all UI components |
| Signal/Slot | Connect user actions to application |
| Layer Display | Populate layer lists, icons |
| Configuration | JSON tree view, real-time updates |
| Theming | Dark/light mode, icon adaptation |

**Key Signals Emitted**:
```python
launchingTask = pyqtSignal(str, dict)      # Request task execution
settingLayerVariable = pyqtSignal(dict)    # Save layer config
closingPlugin = pyqtSignal()               # Plugin shutdown
```

### 2.4 Task Layer (`modules/tasks/`)

**Structure**:
```
modules/tasks/
├── __init__.py
├── filter_task.py           # FilterEngineTask (~950 lines)
├── layer_management_task.py # LayersManagementEngineTask (~1125 lines)
├── task_utils.py            # Shared utilities (~328 lines)
└── geometry_cache.py        # SourceGeometryCache (~146 lines)
```

**Pattern**: All tasks inherit from `QgsTask`

```python
class FilterEngineTask(QgsTask):
    def __init__(self, description, task_parameters):
        super().__init__(description, QgsTask.CanCancel)
        self.task_parameters = task_parameters
        
    def run(self):
        # Main task logic (runs in background thread)
        backend = BackendFactory.get_backend(self.layer)
        result = backend.execute_filter(...)
        return True
        
    def finished(self, result):
        # Called on main thread when done
        self.taskCompleted.emit(result)
```

### 2.5 Backend System (`modules/backends/`)

**Structure**:
```
modules/backends/
├── __init__.py
├── base_backend.py          # Abstract interface
├── factory.py               # Backend selection logic
├── postgresql_backend.py    # PostgreSQL/PostGIS
├── spatialite_backend.py    # Spatialite
└── ogr_backend.py           # OGR fallback
```

**Factory Selection Logic**:
```python
def get_backend(layer, task_parameters=None):
    # Priority 1: Forced backend (user choice)
    forced = task_parameters.get('forced_backends', {}).get(layer.id())
    if forced:
        return create_forced_backend(forced, layer)
    
    # Priority 2: Auto-detection by provider
    provider = layer.providerType()
    if provider == 'postgres' and POSTGRESQL_AVAILABLE:
        return PostgreSQLBackend(layer)
    elif provider == 'spatialite':
        return SpatialiteBackend(layer)
    else:
        return OGRBackend(layer)  # Fallback
```

---

## 3. Data Flow Diagrams

### 3.1 Filter Operation Flow

```
User Input (Expression + Predicates + Buffer)
    │
    ▼
┌─────────────────────────────┐
│ DockWidget validates input  │
│ Emits launchingTask signal  │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ App.manage_task('filter')   │
│ Prepares task parameters    │
│ Creates FilterEngineTask    │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ QgsApplication.taskManager()│
│ .addTask(task)              │
└─────────────┬───────────────┘
              │ (Background Thread)
              ▼
┌─────────────────────────────┐
│ FilterEngineTask.run()      │
│ 1. Get backend from factory │
│ 2. Execute spatial query    │
│ 3. Build feature ID list    │
│ 4. Return result            │
└─────────────┬───────────────┘
              │ (Main Thread)
              ▼
┌─────────────────────────────┐
│ App.filter_completed()      │
│ 1. Save to history          │
│ 2. Apply subset string      │
│ 3. Update UI buttons        │
│ 4. Notify user              │
└─────────────────────────────┘
```

### 3.2 Configuration Update Flow

```
User edits JSON in Config Tab
    │
    ▼
┌─────────────────────────────┐
│ JsonModel.itemChanged       │
│ signal emitted              │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ _on_config_item_changed()   │
│ 1. Detect config path       │
│ 2. Validate new value       │
│ 3. Extract from ChoicesType │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Apply change by type:       │
│ • UI_PROFILE → resize       │
│ • THEME → apply_theme()     │
│ • Other → update setting    │
└─────────────┬───────────────┘
              │
              ▼
┌─────────────────────────────┐
│ Save to config.json         │
│ Show user feedback          │
└─────────────────────────────┘
```

---

## 4. Database Schema

### 4.1 Spatialite Metadata Database

**Location**: `~/.filtermate/filtermate_metadata.db`

```sql
-- Layer metadata cache
CREATE TABLE layer_metadata (
    layer_id TEXT PRIMARY KEY,
    layer_name TEXT,
    geometry_type TEXT,
    provider_type TEXT,
    crs_authid TEXT,
    primary_key TEXT,
    field_info TEXT,  -- JSON
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- Filter history
CREATE TABLE filter_history (
    id INTEGER PRIMARY KEY,
    project_id TEXT,
    layer_id TEXT,
    filter_expression TEXT,
    predicates TEXT,  -- JSON
    buffer_distance REAL,
    timestamp TIMESTAMP,
    is_current BOOLEAN
);

-- Filter favorites
CREATE TABLE filter_favorites (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE,
    description TEXT,
    filter_config TEXT,  -- JSON
    tags TEXT,           -- JSON array
    use_count INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    last_used_at TIMESTAMP
);
```

### 4.2 QGIS Project Properties

**Key**: `filterMate_layers`
**Type**: JSON string in project custom properties

```json
{
  "layer_id_123": {
    "infos": {
      "layer_name": "My Layer",
      "layer_id": "layer_id_123",
      "layer_geometry_type": "Polygon",
      "layer_provider_type": "postgresql",
      "layer_crs_authid": "EPSG:4326",
      "primary_key_name": "id"
    },
    "filtering": {
      "layers_to_filter": ["layer_id_456"],
      "geometric_predicates": ["intersects"],
      "buffer_distance": 100
    }
  }
}
```

---

## 5. Security Considerations

### 5.1 Database Connections

| Concern | Mitigation |
|---------|------------|
| SQL Injection | Parameterized queries only |
| Credential Storage | Uses QGIS connection manager |
| Connection Pooling | Single connection per operation |
| Lock Prevention | Retry with exponential backoff |

### 5.2 File Operations

| Concern | Mitigation |
|---------|------------|
| Path Traversal | Validate all paths |
| Temp File Cleanup | Try/finally blocks |
| Permission Issues | Graceful error handling |

---

## 6. Performance Optimizations

### 6.1 Query Optimizations

| Backend | Optimization | Impact |
|---------|--------------|--------|
| PostgreSQL | UNLOGGED materialized views | 30-50% faster |
| PostgreSQL | Fast count via pg_stat_user_tables | 500× faster |
| PostgreSQL | GIST spatial indexes | Sub-second queries |
| Spatialite | R-tree spatial indexes | 10× faster |
| Spatialite | Temp tables (not views) | Lock prevention |
| OGR | QGIS processing framework | Native optimization |

### 6.2 Caching Strategies

| Cache | Purpose | Location |
|-------|---------|----------|
| Source Geometry Cache | Multi-layer operations | In-memory (task) |
| Icon Cache | Fast UI updates | In-memory (app) |
| Layer Metadata Cache | Reduce DB queries | Spatialite DB |
| Configuration Cache | Fast config access | ENV_VARS global |

### 6.3 Predicate Ordering

Predicates ordered by computational cost:
1. `within` (cheapest)
2. `contains`
3. `intersects`
4. `overlaps`
5. `touches`
6. `crosses` (most expensive)

---

## 7. Error Handling Strategy

### 7.1 Exception Hierarchy

```python
FilterMateException (base)
├── DatabaseConnectionError
├── GeometryError
├── BackendError
│   ├── PostgreSQLError
│   ├── SpatialiteError
│   └── OGRError
└── ConfigurationError
```

### 7.2 Recovery Strategies

| Error Type | Strategy |
|------------|----------|
| Database Lock | Retry 5× with exponential backoff |
| Invalid Geometry | Auto-repair with ST_MakeValid |
| Connection Failure | Fallback to next backend |
| Config Corruption | Reset with backup |

---

## 8. Deployment Architecture

### 8.1 Installation

```
QGIS Plugin Directory/
└── filter_mate/
    ├── *.py              # Core Python files
    ├── config/           # Configuration
    ├── modules/          # Backend modules
    ├── icons/            # UI icons
    ├── i18n/             # Translations
    └── metadata.txt      # Plugin metadata
```

### 8.2 Dependencies

| Dependency | Required | Installation |
|------------|----------|--------------|
| QGIS 3.0+ | ✅ Yes | Host application |
| PyQt5 | ✅ Yes | Bundled with QGIS |
| sqlite3 | ✅ Yes | Python stdlib |
| psycopg2 | ❌ Optional | `pip install psycopg2` |

---

## 9. Extension Points

### 9.1 Adding New Backend

1. Create `modules/backends/new_backend.py`
2. Inherit from `BaseBackend`
3. Implement abstract methods
4. Register in `factory.py`

### 9.2 Adding New Task Type

1. Create task class inheriting `QgsTask`
2. Implement `run()` and `finished()`
3. Add case in `App.manage_task()`

### 9.3 Adding Configuration Option

1. Add to `config/config.default.json`
2. Add handler in dockwidget
3. Update config helpers if needed

---

## 10. Monitoring & Observability

### 10.1 Logging

**Configuration**: `modules/logging_config.py`

| Level | Use Case |
|-------|----------|
| DEBUG | Detailed diagnostics |
| INFO | Operation progress |
| WARNING | Performance issues |
| ERROR | Operation failures |

### 10.2 Performance Metrics

| Metric | Tracking |
|--------|----------|
| Query time | Logged per operation |
| Feature count | Displayed to user |
| Backend used | Status bar indicator |
| Memory usage | QGIS monitoring |

---

## 11. Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2023 | Initial architecture |
| 1.5 | Oct 2024 | Multi-backend pattern |
| 2.0 | Dec 2025 | Configuration v2.0, Task refactoring |
