# Key Architecture Components

## Core Files

### 1. filter_mate.py
**Purpose**: Plugin entry point and QGIS integration
**Key Functions**:
- `initGui()`: Initialize plugin UI
- `unload()`: Cleanup on plugin unload  
- Connects to QGIS plugin manager

### 2. filter_mate_app.py (~1038 lines)
**Purpose**: Main application orchestrator
**Key Responsibilities**:
- Manages application state
- Coordinates between UI (dockwidget) and backend (tasks)
- Handles layer management
- Manages project configuration
- Database initialization

**Key Classes/Methods**:
- `FilterMateApp` class
- `manage_task()`: Central task dispatcher
- `layer_management_engine_task_completed()`: Callback for layer operations
- `get_task_parameters()`: Prepares task configuration
- `init_filterMate_db()`: Initializes Spatialite database for metadata

### 3. filter_mate_dockwidget.py (~2446 lines)
**Purpose**: UI management and user interactions
**Key Responsibilities**:
- Widget initialization and management
- User input handling
- Layer property management
- Signal/slot connections

**Key Methods**:
- `filtering_populate_layers_chekableCombobox()`: Populates layer selection (ISSUE: icon display)
- `icon_per_geometry_type()`: Returns icon for geometry type (ISSUE: string format mismatch)
- `current_layer_changed()`: Updates UI when active layer changes
- `exploring_features_changed()`: Handles feature selection changes
- `get_project_layers_from_app()`: Receives layers from app orchestrator

### 4. modules/appTasks.py (~2772 lines)
**Purpose**: Asynchronous task execution
**Key Classes**:
- `FilterEngineTask`: Handles filtering operations
- `LayersManagementEngineTask`: Manages layer addition/removal (ISSUE: geometry type at line 2311)
- `PopulateListEngineTask`: Populates feature lists

**Backend Selection Logic**:
```python
if provider_type == 'postgresql' and POSTGRESQL_AVAILABLE:
    # PostgreSQL optimized path
elif provider_type == 'spatialite':
    # Spatialite alternative
else:
    # OGR/QGIS processing fallback
```

### 5. modules/appUtils.py
**Purpose**: Database connections and utility functions
**Key Functions**:
- `get_datasource_connexion_from_layer()`: Gets PostgreSQL connection
- `get_data_source_uri()`: Extracts data source URI from layer
- `create_temp_spatialite_table()`: Creates temporary Spatialite tables
- `get_spatialite_datasource_from_layer()`: Gets Spatialite connection

**Critical Constant**:
```python
POSTGRESQL_AVAILABLE = True/False  # Set on module load
```

### 6. modules/widgets.py
**Purpose**: Custom widget implementations
**Key Classes**:
- `QgsCheckableComboBoxLayer`: Custom combobox with checkboxes for layers
- `ItemDelegate`: Custom rendering for combobox items
- `QgsCheckableComboBoxFeaturesListPickerWidget`: Feature selection widget
- `PopulateListEngineTask`: Async task for populating lists

**Key Methods in QgsCheckableComboBoxLayer**:
- `addItem(icon, text, data)`: Adds layer item with icon
- `createMenuContext()`: Creates right-click menu
- `select_by_geometry()`: Filters layers by geometry type

## Data Flow

### Layer Addition Flow
```
QGIS Layer Added Event
    ↓
MapLayerStore.layersAdded signal
    ↓
FilterMateApp.manage_task('add_layers')
    ↓
LayersManagementEngineTask.run()
    - Detects provider type
    - Gets geometry type (ISSUE HERE at line 2311)
    - Collects layer metadata
    ↓
FilterMateApp.layer_management_engine_task_completed()
    ↓
FilterMateDockWidget.get_project_layers_from_app()
    ↓
FilterMateDockWidget.filtering_populate_layers_chekableCombobox()
    - Gets icon via icon_per_geometry_type() (ISSUE HERE)
    - Adds item to combobox
```

### Filtering Flow
```
User selects layers and filter options
    ↓
FilterMateDockWidget.launchTaskEvent('filter')
    ↓
FilterMateApp.manage_task('filter')
    ↓
FilterEngineTask.run()
    - Backend selection
    - SQL query generation
    - Spatial operations
    ↓
FilterMateApp.filter_engine_task_completed()
    ↓
FilterMateApp.apply_subset_filter()
    - Applies filter to layer
```

## Configuration Structure

### Project Configuration (ENV_VARS)
- Stored in `config/config.json`
- Loaded by `config/config.py`
- Contains UI colors, backend preferences, paths

### Layer Properties Structure
```python
PROJECT_LAYERS = {
    "layer_id": {
        "infos": {
            "layer_name": str,
            "layer_id": str,
            "layer_geometry_type": str,  # ISSUE: Format mismatch
            "layer_provider_type": str,  # postgresql/spatialite/ogr
            "layer_crs_authid": str,
            "primary_key_name": str,
            # ...
        },
        "exploring": {
            "single_selection_expression": str,
            "multiple_selection_expression": str,
            # ...
        },
        "filtering": {
            "layers_to_filter": list,
            "geometric_predicates": list,
            # ...
        }
    }
}
```

## Backend Architecture

### PostgreSQL Backend
- Uses `psycopg2` for connection
- Creates materialized views for performance
- Server-side spatial operations
- Best for > 100k features

### Spatialite Backend  
- Uses Python's `sqlite3` module
- Creates temporary tables
- R-tree spatial indexes
- Good for < 100k features

### OGR Backend
- Uses QGIS processing framework
- Memory-based operations
- Universal compatibility
- Slower on large datasets

## Signal/Slot Architecture
Key signals emitted by FilterMateDockWidget:
- `launchingTask`: Triggers task execution
- `settingLayerVariable`: Saves layer properties
- `resettingLayerVariable`: Removes layer properties
- `settingProjectVariables`: Saves project configuration
- `closingPlugin`: Plugin cleanup

## Critical Patterns

### Resource Management
```python
# Database connections
try:
    conn = sqlite3.connect(db_path)
    # operations
finally:
    conn.close()
```

### Error Handling
```python
try:
    # risky operation
except (AttributeError, KeyError, RuntimeError) as e:
    # graceful degradation
    pass
```

### Async Task Management
```python
task = MyTask(description, parameters)
task.taskCompleted.connect(callback)
QgsApplication.taskManager().addTask(task)
```
