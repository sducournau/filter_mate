# Architecture Overview - FilterMate v2.2.5

**Last Updated:** December 10, 2025
**Current Version:** 2.2.5 - Automatic Geographic CRS Handling

## System Architecture

FilterMate follows a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────┐
│                    QGIS Plugin Layer                     │
│                  (filter_mate.py)                        │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│              Application Orchestrator                    │
│              (filter_mate_app.py)                        │
│  - State management                                      │
│  - Task coordination                                     │
│  - Configuration management                              │
└───────┬─────────────────────────────────┬───────────────┘
        │                                 │
┌───────▼──────────────┐         ┌────────▼──────────────┐
│   UI Layer           │         │   Task Layer          │
│   (dockwidget)       │         │   (appTasks.py)       │
│  - User interaction  │         │  - Async operations   │
│  - Widget management │         │  - QgsTask execution  │
│  - Signal/slot       │         │  - Backend delegation │
└──────────────────────┘         └────────┬──────────────┘
                                          │
                              ┌───────────▼───────────────┐
                              │   Backend Factory         │
                              │   (factory.py)            │
                              │  - Auto backend selection │
                              └───┬──────────┬────────┬───┘
                                  │          │        │
                    ┌─────────────▼─┐   ┌────▼─────┐ │
                    │ PostgreSQL    │   │Spatialite│ │
                    │ Backend       │   │Backend   │ │
                    └───────────────┘   └──────────┘ │
                                                     │
                                        ┌────────────▼─┐
                                        │ OGR Backend  │
                                        │ (Fallback)   │
                                        └──────────────┘
```

## Core Files

### 1. Plugin Entry Point
**File:** `filter_mate.py`
**Purpose:** QGIS integration and lifecycle management
**Key Functions:**
- `initGui()`: Initialize plugin UI, add to QGIS interface
- `unload()`: Cleanup on plugin unload
- Plugin metadata registration

**Responsibilities:**
- Register with QGIS plugin manager
- Create dockwidget instance
- Handle QGIS plugin lifecycle events

### 2. Application Orchestrator
**File:** `filter_mate_app.py`
**Lines:** ~1376 (after Phase 5a refactoring - was ~1687)
**Purpose:** Central coordinator between UI and backend

**Key Responsibilities:**
- Task management and dispatch
- Layer state management
- Project configuration persistence
- Database initialization
- Result processing

**Key Methods:**
- `manage_task(task_type, params)`: Central task dispatcher (127 lines after Phase 5a)
- `get_task_parameters()`: Prepares task configuration (134 lines after Phase 5a)
- `layer_management_engine_task_completed()`: Layer operation callback (104 lines after Phase 5a)
- `filter_engine_task_completed()`: Filter operation callback
- `apply_subset_filter()`: Applies filter expression to layers
- `init_filterMate_db()`: Initialize Spatialite metadata database (103 lines after Phase 5a)

**Phase 5a Refactoring (December 10, 2025):**
- **12 Helper Methods Extracted** following Single Responsibility Principle
- **40% Complexity Reduction** (779→468 lines in 4 core methods)
- **Private Helpers**: `_ensure_db_directory()`, `_create_db_file()`, `_initialize_schema()`, 
  `_migrate_schema_if_needed()`, `_load_or_create_project()`, `_build_layers_to_filter()`,
  `_initialize_filter_history()`, `_handle_remove_all_layers()`, `_handle_project_initialization()`,
  `_validate_layer_info()`, `_update_datasource_for_layer()`, `_remove_datasource_for_layer()`
- **Complete Docstrings**: All helpers have Args/Returns documentation
- **Zero Breaking Changes**: 100% backward compatibility maintained

**Signal Handling:**
- Connects to dockwidget signals (launchingTask, etc.)
- Emits signals to dockwidget (layer updates, status)
- Manages QGIS layer registry signals

### 3. UI Management
**File:** `filter_mate_dockwidget.py`
**Lines:** ~2500
**Purpose:** User interface and interaction handling

**Key Responsibilities:**
- Widget initialization and layout
- User input validation
- Layer property management
- Signal/slot connections
- UI state synchronization

**Key Methods:**
- `filtering_populate_layers_chekableCombobox()`: Populates layer selection
- `current_layer_changed()`: Handles layer switching
- `exploring_features_changed()`: Handles feature selection
- `get_project_layers_from_app()`: Receives layer list from app
- `update_ui_from_config()`: Applies configuration to UI

**UI Components:**
- Layer selection (custom checkable combobox)
- Expression builder
- Geometric predicate selector
- Buffer configuration
- Feature explorer
- Export options
- Configuration JSON tree view

### 4. Task Execution Layer
**File:** `modules/appTasks.py`
**Lines:** ~2800
**Purpose:** Asynchronous task execution with QgsTask

**Key Classes:**

#### FilterEngineTask
- Executes filtering operations
- Backend delegation
- Progress reporting
- Cancellation support

#### LayersManagementEngineTask
- Handles layer addition/removal
- Extracts layer metadata
- Detects provider type
- Collects geometry information

#### PopulateListEngineTask
- Asynchronously populates feature lists
- Non-blocking UI during data load
- Supports search/filter

#### ExportEngineTask
- Exports filtered features
- Multiple format support
- Field selection
- CRS transformation

**Backend Integration:**
```python
from modules.backends.factory import BackendFactory

# Get appropriate backend
backend = BackendFactory.get_backend(layer)

# Execute operation
result = backend.execute_filter(params)

# Cleanup
backend.cleanup()
```

### 5. Utility Functions
**File:** `modules/appUtils.py`
**Lines:** ~800
**Purpose:** Database connections and helper functions

**Key Functions:**
- `get_datasource_connexion_from_layer()`: PostgreSQL connection
- `get_spatialite_datasource_from_layer()`: Spatialite connection
- `get_data_source_uri()`: Extract data source URI
- `spatialite_connect()`: Connect to Spatialite with spatial extension
- `get_icon_for_geometry()`: Icon cache for geometry types
- `repair_geometry()`: Geometry validation and repair

**Critical Constants:**
```python
# Set at module load
POSTGRESQL_AVAILABLE = True/False  # psycopg2 availability check
```

**Pattern:**
```python
try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
```

## Data Flow Diagrams

### Layer Addition Flow
```
QGIS Layer Added
    ↓
QgsProject.instance().layersAdded signal
    ↓
FilterMateApp.manage_task('add_layers')
    ↓
LayersManagementEngineTask.run()
    ├─ Detect provider type (postgres/spatialite/ogr)
    ├─ Get geometry type
    ├─ Extract CRS
    ├─ Identify primary key
    └─ Collect field metadata
    ↓
Task.taskCompleted signal
    ↓
FilterMateApp.layer_management_engine_task_completed()
    ↓
FilterMateApp.getProjectLayersEvent signal
    ↓
FilterMateDockWidget.get_project_layers_from_app()
    ↓
FilterMateDockWidget.filtering_populate_layers_chekableCombobox()
    └─ Add to UI with icon
```

### Filtering Operation Flow
```
User configures filter
    ├─ Select layers
    ├─ Enter expression
    ├─ Choose geometric predicates
    └─ Set buffer distance
    ↓
User clicks "Filter" button
    ↓
FilterMateDockWidget.launchTaskEvent('filter') signal
    ↓
FilterMateApp.manage_task('filter')
    ├─ Get task parameters
    └─ Create FilterEngineTask
    ↓
FilterEngineTask.run()
    ├─ BackendFactory.get_backend(layer)
    ├─ backend.execute_filter(params)
    │   ├─ PostgreSQL: Materialized view + GIST index
    │   ├─ Spatialite: Temp table + R-tree index
    │   └─ OGR: QGIS processing + memory layer
    └─ Return filtered feature IDs
    ↓
Task.taskCompleted signal
    ↓
FilterMateApp.filter_engine_task_completed()
    ↓
FilterMateApp.apply_subset_filter()
    └─ layer.setSubsetString(expression)
    ↓
Layer filtered in QGIS map canvas
```

### Configuration Update Flow (v2.2.2)
```
User edits JSON tree view
    ↓
JsonModel.itemChanged signal
    ↓
FilterMateDockWidget._on_config_item_changed()
    ├─ Detect configuration path
    ├─ Extract new value (handle ChoicesType)
    └─ Determine change type
    ↓
Apply configuration change
    ├─ UI_PROFILE → update_ui_dimensions()
    ├─ ACTIVE_THEME → apply_theme()
    ├─ ICON_PATH → reload_icons()
    └─ Other → update_setting()
    ↓
Save to config.json
    ↓
User feedback notification
```

## Configuration System

### Storage
**File:** `config/config.json`
**Format:** JSON with nested structure
**Loader:** `config/config.py` → `ENV_VARS` global

### Structure
```json
{
  "UI_PROFILE": {"value": "auto", "choices": ["auto", "compact", "normal"]},
  "ACTIVE_THEME": {"value": "auto", "choices": ["auto", "default", "dark", "light"]},
  "THEME_SOURCE": {"value": "qgis", "choices": ["config", "qgis", "system"]},
  "ICON_PATH": "icons/",
  "POSTGRESQL_AVAILABLE": true,
  "ENABLE_DEBUG_LOGGING": false,
  "STYLES_TO_EXPORT": {"value": "QML", "choices": ["QML", "SLD", "None"]},
  "DATATYPE_TO_EXPORT": {"value": "GPKG", "choices": ["GPKG", "SHP", "GEOJSON", "KML", "DXF", "CSV"]}
}
```

### ChoicesType Pattern (v2.2.2)
Values can be simple or choice-based:
- Simple: `"ICON_PATH": "icons/"`
- ChoicesType: `"UI_PROFILE": {"value": "auto", "choices": [...]}`

### Configuration Helpers
**File:** `modules/config_helpers.py`

**Key Functions:**
- `get_config_value(key, default)`: Read with ChoicesType extraction
- `set_config_value(key, value)`: Write with validation
- `get_config_choices(key)`: Get available options
- `validate_config_value(key, value)`: Validate before setting

## Layer Properties Persistence

### Storage
**Format:** QGIS project custom properties
**Key:** `filterMate_layers`
**Type:** JSON string

### Structure
```python
PROJECT_LAYERS = {
    "layer_id_123": {
        "infos": {
            "layer_name": "My Layer",
            "layer_id": "layer_id_123",
            "layer_geometry_type": "Polygon",
            "layer_provider_type": "postgresql",
            "layer_crs_authid": "EPSG:4326",
            "primary_key_name": "id",
            "source_table_name": "my_table",
            "source_schema_name": "public"
        },
        "exploring": {
            "single_selection_expression": "",
            "multiple_selection_expression": "",
            "selected_fields": []
        },
        "filtering": {
            "layers_to_filter": ["layer_id_456"],
            "geometric_predicates": ["intersects"],
            "buffer_distance": 100,
            "filter_expression": ""
        }
    }
}
```

### Persistence Operations
- **Save:** `QgsProject.instance().setCustomProperty('filterMate_layers', json.dumps(data))`
- **Load:** `json.loads(QgsProject.instance().readCustomProperty('filterMate_layers', '{}'))`

## Signal/Slot Architecture

### Key Signals (FilterMateDockWidget → FilterMateApp)
- `launchingTask(str, dict)`: Request task execution
- `settingLayerVariable(dict)`: Save layer properties
- `resettingLayerVariable(str)`: Delete layer properties
- `settingProjectVariables(dict)`: Save project configuration
- `closingPlugin()`: Plugin cleanup

### Key Signals (FilterMateApp → FilterMateDockWidget)
- `getProjectLayersEvent(dict)`: Send layer list to UI
- `taskCompletedEvent(str, dict)`: Task result notification

### Signal Management Utilities
**File:** `modules/signal_utils.py`

**Classes:**
- `SignalBlocker`: Context manager for blocking signals
- `SignalConnection`: Temporary signal connection
- `SignalBlockerGroup`: Block multiple widgets
- `ConnectionManager`: Manage multiple connections

**Pattern:**
```python
from modules.signal_utils import SignalBlocker

with SignalBlocker(widget):
    # Signals blocked here
    widget.setValue(new_value)
# Signals automatically restored
```

## State Management

### State Manager
**File:** `modules/state_manager.py`

**Classes:**

#### LayerStateManager
- Tracks layer states
- Manages layer metadata
- Handles layer removal

#### FilterHistoryManager
- Maintains filter history
- Undo/redo operations
- In-memory history storage

**Pattern:**
```python
from modules.state_manager import LayerStateManager

manager = LayerStateManager()
manager.add_layer(layer_id, metadata)
state = manager.get_layer_state(layer_id)
manager.remove_layer(layer_id)
```

## Error Handling Patterns

### Exception Hierarchy
**File:** `modules/customExceptions.py`

**Custom Exceptions:**
- `FilterMateException`: Base exception
- `DatabaseConnectionError`: Connection failures
- `GeometryError`: Geometry operation failures
- `BackendError`: Backend-specific errors
- `ConfigurationError`: Configuration issues

### Error Recovery Strategies

#### 1. Database Lock Retry (Spatialite)
```python
max_retries = 5
for attempt in range(max_retries):
    try:
        conn = sqlite3.connect(db_path)
        # operation
        break
    except sqlite3.OperationalError as e:
        if "locked" in str(e) and attempt < max_retries - 1:
            time.sleep(0.1 * (2 ** attempt))  # Exponential backoff
        else:
            raise
```

#### 2. Geometry Repair
```python
from modules.appUtils import repair_geometry

try:
    result = operation(geometry)
except GeometryError:
    repaired = repair_geometry(geometry)
    result = operation(repaired)
```

#### 3. Graceful Degradation
```python
if POSTGRESQL_AVAILABLE and provider == 'postgres':
    # Optimal path
    use_postgresql_backend()
elif provider == 'spatialite':
    # Good path
    use_spatialite_backend()
else:
    # Fallback path
    use_ogr_backend()
```

### User Feedback
**File:** `modules/feedback_utils.py`

**Functions:**
- `show_info(message)`: Info notification
- `show_warning(message, duration)`: Warning with custom duration
- `show_error(message)`: Error notification
- `show_success(message)`: Success notification

**Pattern:**
```python
from modules.feedback_utils import show_warning

if layer.featureCount() > 50000 and not POSTGRESQL_AVAILABLE:
    show_warning(
        "Large dataset without PostgreSQL. "
        "Performance may be reduced.",
        duration=10
    )
```

## Resource Management

### Database Connections
**Pattern:**
```python
conn = None
try:
    conn = connect_to_database()
    # operations
    conn.commit()
finally:
    if conn:
        conn.close()
```

### QGIS Layers
**Temporary Layers:**
```python
temp_layer = QgsVectorLayer("Point?crs=epsg:4326", "temp", "memory")
# Must add to project or will be garbage collected
QgsProject.instance().addMapLayer(temp_layer)
```

**Layer Removal:**
```python
QgsProject.instance().removeMapLayer(layer_id)
```

### Task Cleanup
**Pattern:**
```python
class MyTask(QgsTask):
    def finished(self, result):
        # Cleanup resources
        if self.backend:
            self.backend.cleanup()
        if self.connection:
            self.connection.close()
```

## Performance Optimizations

### 1. Spatial Index Automation
- OGR: Automatic .qix file generation
- Spatialite: R-tree index on temp tables
- PostgreSQL: GIST index on materialized views

### 2. Source Geometry Caching
**File:** `modules/appTasks.py` (SourceGeometryCache class)
- Cache source geometries for multi-layer operations
- 5× speedup on repeated geometric predicates
- Automatic cache invalidation

### 3. Predicate Ordering
**Strategy:** Order predicates by computational cost
1. `within` (cheapest)
2. `contains`
3. `intersects`
4. `crosses` (most expensive)

### 4. Large Dataset Optimization
- OGR: Separate method for > 50k features
- Spatialite: Temporary geometry tables
- PostgreSQL: Materialized views

### 5. Icon Caching
- Icons loaded once and cached
- Faster UI updates on layer switching

## Testing Architecture

### Test Structure
```
tests/
├── conftest.py              # Pytest fixtures
├── test_appUtils.py         # Utility functions
├── test_backends.py         # Backend tests
├── test_config_*.py         # Configuration tests
├── test_filter_history.py   # History tests
├── test_performance.py      # Performance benchmarks
└── benchmark_simple.py      # Simple benchmarks
```

### Test Patterns
- Mock QGIS dependencies
- Fixture-based layer creation
- Isolated test databases
- Performance benchmarking

## Logging System

### Configuration
**File:** `modules/logging_config.py`

**Levels:**
- DEBUG: Detailed diagnostic information
- INFO: General informational messages
- WARNING: Warning messages
- ERROR: Error messages
- CRITICAL: Critical failures

**Output:**
- QGIS Python console
- Optional file logging
- Structured log format

**Pattern:**
```python
import logging

logger = logging.getLogger(__name__)
logger.info("Operation started")
logger.error(f"Failed: {error}")
```

## Extension Points

### Adding New Backends
1. Inherit from `GeometricFilterBackend`
2. Implement abstract methods
3. Register in `BackendFactory`

### Adding New Task Types
1. Create class inheriting `QgsTask`
2. Implement `run()` and `finished()`
3. Add to `FilterMateApp.manage_task()`

### Adding Configuration Fields
1. Add to `config/config.json`
2. Add handler in dockwidget
3. Update configuration helpers

## Critical Code Locations

### Backend Selection
- `modules/backends/factory.py:21-50` (BackendFactory)

### Task Dispatch
- `filter_mate_app.py:200-350` (manage_task method)

### UI Updates
- `filter_mate_dockwidget.py:1800-2000` (layer population)

### Configuration Reactivity
- `filter_mate_dockwidget.py:1600-1700` (_on_config_item_changed)

### Filter History
- `modules/filter_history.py:50-150` (FilterHistory class)
