# Backend Architecture - FilterMate

## Multi-Backend System

FilterMate v2.1+ implements a **factory pattern** for automatic backend selection based on data source and available dependencies.

## Backend Structure

```
modules/backends/
  ├── __init__.py            # Package initialization
  ├── base_backend.py        # Abstract base class (interface)
  ├── postgresql_backend.py  # PostgreSQL/PostGIS implementation
  ├── spatialite_backend.py  # Spatialite implementation
  ├── ogr_backend.py         # Universal OGR fallback
  └── factory.py             # Automatic backend selection logic
```

## Backend Selection Logic

### 1. PostgreSQL Backend (Optimal Performance)

**Conditions:**
- Layer provider type is `postgres`
- `psycopg2` Python package is installed (`POSTGRESQL_AVAILABLE = True`)

**Features:**
- Materialized views for ultra-fast filtering
- Server-side spatial operations
- Native GIST spatial indexes
- Best for datasets > 50,000 features
- Sub-second response on million+ feature datasets

**Key Methods:**
- `create_materialized_view()`: Creates MV with spatial index
- `execute_spatial_query()`: Server-side spatial operations
- `refresh_materialized_view()`: Updates MV data

### 2. Spatialite Backend (Good Performance)

**Conditions:**
- Layer provider type is `spatialite`
- SQLite built-in to Python (always available)

**Features:**
- Temporary tables for filtering
- R-tree spatial indexes
- Good for datasets < 50,000 features
- ~90% PostGIS function compatibility

**Key Methods:**
- `create_temp_spatialite_table()`: Creates temporary tables
- `create_spatial_index()`: R-tree index creation
- `execute_spatial_query()`: Spatialite spatial functions

**Lock Management:**
- Retry mechanism with 5 attempts
- Exponential backoff (0.1s base delay)
- Automatic connection cleanup

### 3. OGR Backend (Universal Fallback)

**Conditions:**
- Layer provider type is `ogr` (Shapefiles, GeoPackage, etc.)
- OR PostgreSQL/Spatialite unavailable/incompatible

**Features:**
- QGIS Processing framework
- Memory-based operations
- Universal compatibility
- Slower on large datasets (< 10,000 features recommended)

**Key Methods:**
- `use_qgis_processing()`: Processing algorithm calls
- `memory_layer_filtering()`: In-memory operations

## Forced Backend System (v2.4+)

### User-Controlled Backend Selection

Users can force a specific backend for any layer via the UI backend indicator.
This overrides automatic backend selection.

**UI Location:** Backend indicator (icon next to layer name in dockwidget)

**Data Flow:**
```
dockwidget.forced_backends = {layer_id: 'postgresql' | 'spatialite' | 'ogr'}
    ↓
filter_mate_app.get_task_parameters()
    → task_parameters["forced_backends"] = dockwidget.forced_backends
    ↓
filter_task._organize_layers_to_filter()
    → PRIORITY 1: Check forced_backends.get(layer_id)
    → PRIORITY 2: PostgreSQL fallback check
    → PRIORITY 3: Auto-detection
    ↓
filter_task._initialize_source_filtering_parameters()
    → Same priority system for source layer
    ↓
BackendFactory.get_backend()
    → Uses forced_backend if provided
```

**Key Files:**
- `filter_mate_dockwidget.py`: `forced_backends` dict, `_set_forced_backend()`, `get_forced_backend_for_layer()`
- `filter_mate_app.py`: `get_task_parameters()` - adds forced_backends to task params
- `modules/tasks/filter_task.py`: `_organize_layers_to_filter()`, `_initialize_source_filtering_parameters()`
- `modules/backends/factory.py`: `get_backend()` respects forced_backends

**Priority System:**
1. **FORCED**: User explicitly selected backend via UI
2. **FALLBACK**: PostgreSQL unavailable → OGR fallback
3. **AUTO**: Automatic detection based on provider type

## Factory Pattern Implementation

### BackendFactory Class

**Location:** `modules/backends/factory.py`

**Key Method:** `get_backend(layer, task_parameters=None)`

**Selection Logic:**
```python
def get_backend(layer, task_parameters=None):
    # PRIORITY 1: Check for forced backend
    forced_backends = task_parameters.get('forced_backends', {}) if task_parameters else {}
    forced_backend = forced_backends.get(layer.id())
    
    if forced_backend:
        if forced_backend == 'postgresql' and POSTGRESQL_AVAILABLE:
            return PostgreSQLBackend(layer)
        elif forced_backend == 'spatialite':
            return SpatialiteBackend(layer)
        elif forced_backend == 'ogr':
            return OGRBackend(layer)
    
    # PRIORITY 2-3: Auto-detection
    provider_type = layer.providerType()
    
    if provider_type == 'postgres' and POSTGRESQL_AVAILABLE:
        return PostgreSQLBackend(layer)
    elif provider_type == 'spatialite':
        return SpatialiteBackend(layer)
    elif provider_type == 'ogr':
        return OGRBackend(layer)
    else:
        # Fallback to OGR for unknown providers
        return OGRBackend(layer)
```

## Base Backend Interface

### Abstract Methods (must be implemented)

```python
class BaseBackend(ABC):
    @abstractmethod
    def execute_filter(self, expression, predicates, buffer_distance):
        """Execute filtering operation"""
        pass
    
    @abstractmethod
    def get_feature_count(self):
        """Get filtered feature count"""
        pass
    
    @abstractmethod
    def create_export_layer(self, output_path, selected_fields):
        """Export filtered features"""
        pass
    
    @abstractmethod
    def cleanup(self):
        """Clean up resources"""
        pass
```

## Performance Characteristics

### PostgreSQL Backend
- **Best for:** > 50,000 features
- **Query time:** < 1s for millions of features
- **Memory usage:** Low (server-side)
- **Requires:** PostgreSQL server + psycopg2

### Spatialite Backend
- **Best for:** 10,000 - 50,000 features
- **Query time:** 1-10s for 100k features
- **Memory usage:** Moderate (temp tables)
- **Requires:** Nothing (built-in)

### OGR Backend
- **Best for:** < 10,000 features
- **Query time:** 10-60s for 100k features
- **Memory usage:** High (in-memory)
- **Requires:** Nothing (built-in)

## Warning Thresholds

FilterMate displays performance warnings:

```python
if layer.featureCount() > 50000 and not POSTGRESQL_AVAILABLE:
    # Warning: Large dataset without PostgreSQL
    # Recommendation: Install psycopg2 or use smaller dataset
```

## Expression Conversion

Each backend converts QGIS expressions to backend-specific SQL:

### PostgreSQL
```python
qgis_expression_to_postgis(expression)
# Example: "$area > 1000" → "ST_Area(geometry) > 1000"
```

### Spatialite
```python
qgis_expression_to_spatialite(expression)
# Example: "$area > 1000" → "Area(geometry) > 1000"
# Note: ~90% compatible with PostGIS functions
```

### OGR
```python
# Uses QGIS expression engine directly
# No conversion needed
```

## Error Handling

### Geometry Repair
All backends include automatic geometry repair:

```python
try:
    result = backend.execute_filter(...)
except GeometryError:
    # Auto-repair with ST_MakeValid / MakeValid
    repaired_geom = repair_geometry(geom)
    result = backend.execute_filter(...)
```

### Database Locks (Spatialite)
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

## Integration Points

### Usage in appTasks.py

```python
from modules.backends.factory import BackendFactory

class FilterEngineTask(QgsTask):
    def run(self):
        # Get appropriate backend
        backend = BackendFactory.get_backend(self.layer)
        
        # Execute filtering
        result = backend.execute_filter(
            expression=self.filter_expression,
            predicates=self.spatial_predicates,
            buffer_distance=self.buffer
        )
        
        # Cleanup
        backend.cleanup()
        
        return result
```

## Future Enhancements

### Planned (Phase 3-5)
- Caching layer for repeated queries
- Query plan optimization
- Parallel execution for multi-layer filtering
- Result streaming for very large datasets
- Custom backend plugins support
