# Backend Architecture - FilterMate

**Last Updated:** January 6, 2026
**Current Version:** 2.9.6

## Multi-Backend System

FilterMate v2.1+ implements a **factory pattern** for automatic backend selection based on data source and available dependencies.

## Thread Safety (v2.4.4+)

**CRITICAL**: QGIS `QgsVectorLayer` objects are NOT thread-safe.

### Parallel Execution Rules
- **PostgreSQL/Spatialite**: Can run in parallel (database connections are per-thread)
- **OGR (Shapefiles, GeoPackage)**: MUST use sequential execution
- **Geometric filtering**: Auto-detects and forces sequential mode

### ParallelFilterExecutor (modules/tasks/parallel_executor.py)
- Auto-detects OGR layers and forces sequential execution
- Thread tracking with concurrent access warnings
- Clear logging about execution mode chosen

## Backend Structure

```
modules/backends/
  ├── __init__.py            # Package initialization
  ├── base_backend.py        # Abstract base class (interface)
  ├── postgresql_backend.py  # PostgreSQL/PostGIS implementation
  ├── spatialite_backend.py  # Spatialite implementation
  ├── ogr_backend.py         # Universal OGR fallback
  ├── memory_backend.py      # Optimized QGIS memory layer backend (v2.5.8)
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

### 3. Memory Backend (Native Memory Layers) - v2.5.8

**Conditions:**
- Layer provider type is `memory`
- OR small PostgreSQL datasets (< 5000 features) optimization

**Features:**
- Uses `QgsSpatialIndex` for O(log n) spatial queries
- Direct DataProvider operations (no signals overhead)
- Accurate feature counting with iteration fallback
- Cached spatial indices per layer
- No disk/network I/O

**Key Methods:**
- `get_accurate_feature_count()`: Reliable counting for memory layers
- `_get_or_create_spatial_index()`: LRU-cached QgsSpatialIndex
- `_perform_spatial_selection()`: Two-phase spatial selection (broad + narrow)
- `_test_predicates()`: Direct geometry predicate testing

**Performance:**
- Best for: < 100,000 features (in RAM)
- Query time: < 0.5s for 50k features with spatial index
- Memory usage: High (all data in RAM)
- Requires: Nothing (built-in)

### 4. OGR Backend (Universal Fallback)

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

## Forced Backend System (v2.3.5+)

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
2. **MEMORY**: Native memory layers → Memory backend (v2.5.8)
3. **SMALL_PG**: Small PostgreSQL datasets → Memory backend optimization
4. **FALLBACK**: PostgreSQL unavailable → OGR fallback
5. **AUTO**: Automatic detection based on provider type

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

### Memory Backend (v2.5.8)
- **Best for:** < 100,000 features (native memory layers)
- **Query time:** < 0.5s for 50k features (with spatial index)
- **Memory usage:** High (all data in RAM)
- **Requires:** Nothing (built-in)
- **Special:** Accurate featureCount() with iteration fallback

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

## Negative Buffer (Erosion) Handling

**Critical:** Buffer is applied via SQL `ST_Buffer()`, NOT in Python WKT preparation!

See [negative_buffer_wkt_handling.md](negative_buffer_wkt_handling.md) for full details.

### PostgreSQL Pattern (v2.5.5+)
```sql
-- ✅ ST_IsEmpty detects ALL empty geometry types (POLYGON EMPTY, MULTIPOLYGON EMPTY, etc.)
CASE WHEN ST_IsEmpty(ST_MakeValid(ST_Buffer(geom, -10))) THEN NULL 
     ELSE ST_MakeValid(ST_Buffer(geom, -10)) END

-- ❌ OLD (pre-v2.5.5): Only detected GEOMETRYCOLLECTION EMPTY
-- NULLIF(ST_MakeValid(ST_Buffer(geom, -10)), 'GEOMETRYCOLLECTION EMPTY'::geometry)
```

### Spatialite Pattern (v2.5.5+)  
```sql
-- Note: MakeValid() instead of ST_MakeValid()
-- Note: = 1 for boolean comparison (Spatialite returns integer)
CASE WHEN ST_IsEmpty(MakeValid(ST_Buffer(geom, -10))) = 1 THEN NULL 
     ELSE MakeValid(ST_Buffer(geom, -10)) END
```

### OGR Backend (v2.5.4+)
```python
# Memory layer feature counting now uses iteration instead of featureCount()
# featureCount() returns 0 immediately after memory layer creation
for feat in layer.getFeatures():
    count += 1  # More reliable for memory layers
```

### Key Functions
| Backend | Function | Purpose |
|---------|----------|---------|
| PostgreSQL | `_build_st_buffer_with_style()` | Apply buffer with style + empty check |
| PostgreSQL | `_build_simple_wkt_expression()` | WKT mode for small datasets |
| Spatialite | `_build_st_buffer_with_style()` | Apply buffer with Spatialite syntax |
| Spatialite | `build_expression()` | Full expression builder |

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

## Pre-flight Validation (v2.4.5+)

Before calling `processing.run()`, OGR backend performs three-tier validation:

1. **`_validate_input_layer()`**: Tests layer.id(), layer.crs(), layer.wkbType(), provider methods
2. **`_validate_intersect_layer()`**: Same + geometry validity sampling
3. **`_preflight_layer_check()`**: Tests exact operations that checkParameterValues performs

This prevents C++ level crashes that Python cannot catch.

## Future Enhancements

### Planned
- Caching layer for repeated queries
- Query plan optimization
- Result streaming for very large datasets
- Custom backend plugins support

**Note:** Parallel execution for OGR is NOT planned due to thread safety constraints.

---

## v2.8.0 Enhanced Optimization System

### New Modules

**optimizer_metrics.py:**
- `OptimizationMetricsCollector`: Central metrics hub (singleton)
- `LRUCache`: Thread-safe LRU cache with TTL
- `QueryPatternDetector`: Detect recurring query patterns
- `AdaptiveThresholdManager`: Dynamic threshold tuning
- `SelectivityHistogram`: Selectivity estimation via sampling

**parallel_processor.py:**
- `ParallelChunkProcessor`: Thread-safe parallel spatial filtering
- `GeometryBatch`: Batch geometry operations for worker threads
- Uses WKB for thread-safe geometry operations

**psycopg2_availability.py (v2.8.7):**
- Centralized psycopg2 import handling
- `get_psycopg2_version()` and `check_psycopg2_for_feature()` utilities
- Used by 8+ modules

### EnhancedAutoOptimizer
Extends AutoOptimizer with:
- Session-based metrics tracking
- Query pattern detection for recurring optimizations  
- Adaptive threshold tuning based on observed performance
- Parallel processing for large datasets (>10k features)
- LRU caching with TTL and pattern-based invalidation

### Critical Fixes in v2.7.x - v2.9.x

1. **v2.7.2**: PostgreSQL target + OGR source now uses WKT mode correctly
2. **v2.7.3**: WKT decision uses SELECTED feature count (not total)
3. **v2.7.5**: CASE WHEN wrapper parsing for negative buffers in PostgreSQL
4. **v2.8.7**: Auto-materialization of expensive spatial expressions
5. **v2.8.7**: Centralized psycopg2 imports, deduplicated buffer methods
6. **v2.9.1**: PostgreSQL MV optimizations (INCLUDE, CLUSTER async, bbox column)
7. **v2.9.2**: ST_PointOnSurface for accurate polygon centroids
8. **v2.9.4**: Range-based filter instead of FID subquery for Spatialite
9. **v2.9.6**: MakeValid() wrapper on ALL source geometries

---

## v2.9.x PostgreSQL Advanced Optimizations

### Materialized View Enhancements (v2.9.1)

**INCLUDE Clause (PostgreSQL 11+):**
```sql
CREATE INDEX idx_mv_geom ON mv USING GIST (geom) INCLUDE (pk);
```
- Covering indexes avoid table lookups during spatial queries
- 10-30% faster query performance

**Bbox Column (≥10k features):**
```sql
CREATE TABLE mv AS SELECT pk, geom, ST_Envelope(geom) AS bbox FROM ...;
CREATE INDEX idx_mv_bbox ON mv USING GIST (bbox);
```
- Pre-computed bounding boxes for ultra-fast `&&` pre-filtering
- 2-5x faster for large datasets

**Async CLUSTER (50k-100k features):**
- Non-blocking CLUSTER in background thread
- Threshold-based strategy: sync (<50k), async (50k-100k), skip (>100k)

**Extended Statistics (PostgreSQL 10+):**
```sql
CREATE STATISTICS mv_stats ON pk, geom FROM mv;
```
- Better query plans for complex joins

### Configuration Constants (constants.py)
```python
MV_ENABLE_INDEX_INCLUDE = True      # PostgreSQL 11+ covering indexes
MV_ENABLE_EXTENDED_STATS = True     # PostgreSQL 10+ extended statistics
MV_ENABLE_ASYNC_CLUSTER = True      # Background CLUSTER for medium datasets
MV_ASYNC_CLUSTER_THRESHOLD = 50000  # Threshold for async CLUSTER
MV_ENABLE_BBOX_COLUMN = True        # Bbox column for fast pre-filtering
```

---

## v2.9.x Centroid & Simplification

### ST_PointOnSurface (v2.9.2)

**Problem:** `ST_Centroid()` can return a point OUTSIDE concave polygons.

**Solution:**
```python
CENTROID_MODE_DEFAULT = 'point_on_surface'  # 'centroid' | 'point_on_surface' | 'auto'
```

| Mode | Function | Use Case |
|------|----------|----------|
| `point_on_surface` | `ST_PointOnSurface()` | Default for polygons (accurate) |
| `centroid` | `ST_Centroid()` | Legacy, faster for simple shapes |
| `auto` | Adaptive | PointOnSurface for polygons, Centroid for lines |

### Adaptive Simplification (v2.9.2)

```python
SIMPLIFY_BEFORE_BUFFER_ENABLED = True
SIMPLIFY_TOLERANCE_FACTOR = 0.1         # tolerance = buffer × factor
SIMPLIFY_MIN_TOLERANCE = 0.5            # meters
SIMPLIFY_MAX_TOLERANCE = 10.0           # meters
SIMPLIFY_PRESERVE_TOPOLOGY = True
```
- Reduces vertex count by 50-90% before buffer
- ST_Buffer runs 2-10x faster on simplified geometry

---

## v2.9.x Spatialite Improvements

### Range-Based Filter (v2.9.4)

**DEPRECATED:** `_build_fid_table_filter()` (subquery not supported by OGR)

**NEW:** `_build_range_based_filter()`
```sql
-- Optimized expression for consecutive FID ranges
("fid" BETWEEN 1 AND 500) OR ("fid" BETWEEN 502 AND 1000) OR "fid" IN (503, 507)
```
- Detects consecutive FID ranges and uses BETWEEN clauses
- Groups non-consecutive FIDs into IN() chunks of ≤1000
- Compatible with all OGR providers

### MakeValid Wrapper (v2.9.6)

All source geometries are now wrapped in `MakeValid()`:
```python
# Before (v2.9.5)
source_geom_expr = f"GeomFromText('{source_geom}', {source_srid})"

# After (v2.9.6)
source_geom_expr = f"MakeValid(GeomFromText('{source_geom}', {source_srid}))"
```
- Applied in `build_expression()` and `_create_permanent_source_table()`
- Prevents 0 results from invalid source geometries
