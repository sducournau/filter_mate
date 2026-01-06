# Performance Optimizations - FilterMate v2.9.6

**Last Updated:** January 6, 2026

## Overview

FilterMate v2.4.2 includes comprehensive performance optimizations across all backends, achieving 3-45× speedup on typical operations. Phase 4 adds query caching, parallel execution, and streaming exports.

## Latest Optimizations (v2.3.5 - December 17, 2025)

### GeoPackage Spatialite Backend Routing

**Status:** ✅ Implemented  
**File:** `modules/backends/factory.py`  
**Impact:** 10× performance improvement for GeoPackage geometric filtering

**Problem:** GeoPackage layers were using slow OGR algorithms for spatial operations

**Solution:** Automatic backend selection enhancement:
```python
# GeoPackage/SQLite files now use Spatialite backend
if provider_type == 'ogr' and layer_source.endswith(('.gpkg', '.sqlite')):
    return 'spatialite'
```

**Benchmark Results:**
- OGR backend: ~2.0s
- Spatialite backend: ~0.2s
- **Gain: 10.0× faster**

**Applies to:** All GeoPackage layers with geometric filtering

---

## Previous Optimizations (v2.1.0 - v2.3.4)

### 1. Spatial Index Automation (OGR Backend)

**Status:** ✅ Implemented  
**File:** `modules/backends/ogr_backend.py`  
**Lines:** 53-102 (`_ensure_spatial_index`)

**Impact:**
- 4-19× faster spatial queries
- Automatic `.qix` file creation for Shapefiles
- Automatic detection of existing indexes

**Benchmark Results:**
- Without index: 0.80s
- With index: 0.04s
- **Gain: 19.5× faster**

**Implementation:**
```python
def _ensure_spatial_index(self, layer_path):
    """Auto-create spatial index if missing"""
    if layer_path.endswith('.shp'):
        qix_path = layer_path[:-4] + '.qix'
        if not os.path.exists(qix_path):
            # Create spatial index
            processing.run("native:createspatialindex", {...})
```

### 2. Large Dataset Optimization (OGR Backend)

**Status:** ✅ Implemented  
**File:** `modules/backends/ogr_backend.py`  
**Lines:** 337-444 (`_apply_filter_large`)

**Impact:**
- 3× faster on datasets > 50,000 features
- Memory-efficient processing
- Progress tracking

**Threshold:** Activated for layers with > 50,000 features

**Benchmark Results:**
- Standard method: 1.20s
- Optimized method: 0.40s
- **Gain: 3.0× faster**

### 3. Geometry Cache (Multi-Layer Filtering)

**Status:** ✅ Implemented  
**File:** `modules/appTasks.py`  
**Lines:** 173-267 (`SourceGeometryCache`)

**Impact:**
- 5× faster on multi-layer operations
- Reduces redundant geometry fetching
- Memory-efficient with LRU eviction

**Cache Size:** 1000 geometries

**Benchmark Results:**
- Without cache: 0.50s
- With cache: 0.10s
- **Gain: 5.0× faster**

### 4. Temporary Table Optimization (Spatialite Backend)

**Status:** ✅ Implemented  
**File:** `modules/backends/spatialite_backend.py`  
**Lines:** 100-195 (`_create_temp_geometry_table`)

**Impact:**
- 10-45× faster than in-memory filtering
- R-tree spatial index on temp table
- Automatic cleanup

**Benchmark Results:**
- In-memory: 1.38s
- Temp table: 0.03s
- **Gain: 44.6× faster**

### 5. Predicate Ordering Optimization

**Status:** ✅ Implemented (v2.1.0 - 2025-12-04)  
**File:** `modules/backends/spatialite_backend.py`  
**Lines:** 343-365 (in `build_expression`)

**Impact:**
- 2.3× faster query execution
- Optimal query plan selection
- Database engine optimization

**Optimal Order:**
1. **Disjoint** (fastest - eliminates most)
2. **Intersects** (fast with spatial index)
3. **Touches** (fast)
4. **Crosses** (moderate)
5. **Within** (moderate)
6. **Contains** (expensive)
7. **Overlaps** (expensive)
8. **Equals** (most expensive)

**Benchmark Results:**
- Random order: 0.83s
- Optimized order: 0.37s
- **Gain: 2.3× faster**

## Performance Gains Summary

| Optimization | Target | Benchmark | Gain |
|--------------|--------|-----------|------|
| Spatialite Temp Table | 10k+ features | 1.38s → 0.03s | **44.6×** |
| OGR Spatial Index | All OGR layers | 0.80s → 0.04s | **19.5×** |
| GeoPackage Backend | GeoPackage layers | 2.0s → 0.2s | **10.0×** ⭐ NEW |
| Geometry Cache | Multi-layer | 0.50s → 0.10s | **5.0×** |
| Large Dataset (OGR) | 50k+ features | 1.20s → 0.40s | **3.0×** |
| Predicate Ordering | All backends | 0.83s → 0.37s | **2.3×** |

**Overall:** 3-10× faster on typical use cases

## Backend-Specific Optimizations

### PostgreSQL Backend

**Materialized Views:**
- Server-side computation
- GIST spatial indexes with FILLFACTOR tuning
- Primary key index for fast lookups
- Sub-second response on millions of features

**Primary Key Detection (v2.3.0 - December 16, 2025):**
- Skip `uniqueValues()` call on PostgreSQL (avoids freeze on large tables)
- Trust declared PRIMARY KEY constraints
- Fallback to 'ctid' for tables without primary key
- Clear warning messages to users about limitations

**Predicate Ordering (v2.3.1):**
- Predicates sorted by selectivity (most selective first)
- Order: disjoint → intersects → touches → crosses → within → contains → overlaps → equals
- ~2× faster multi-predicate queries

**Adaptive CLUSTER:**
- CLUSTER enabled for datasets < 100k features
- Skipped for very large datasets (slow operation)
- Configurable via ENABLE_MV_CLUSTER flag

**Connection Pooling:**
- Reuse connections
- Reduce overhead
- Thread-safe

### Spatialite Backend

**Temporary Tables:**
- R-tree spatial indexes
- Optimized for 10k-50k features
- Automatic cleanup

**Query Optimization:**
- Predicate ordering
- Index hints
- Prepared statements (planned)

**GeoPackage Enhancement (v2.3.5):** ⭐ NEW
- GeoPackage files automatically routed to Spatialite backend
- Avoids slow OGR processing algorithms
- 10× performance improvement

### OGR Backend

**Spatial Indexes:**
- Automatic `.qix` creation
- Detection of existing indexes
- Fallback for unsupported formats

**Large Dataset Mode:**
- Memory-efficient algorithms
- Progress tracking
- Batch processing

**GeometryCollection Handling (v2.3.5):** ⭐ NEW
- Automatic conversion to MultiPolygon after buffer operations
- Prevents type mismatch errors
- Maintains data integrity

## Performance Monitoring

### Warnings to Users

**Implementation:** `modules/constants.py` (`should_warn_performance`)

**Thresholds:**
- > 50,000 features without PostgreSQL: Warning
- > 100,000 features with OGR: Strong warning
- > 10,000 features in memory: Caution

**User Feedback:**
```python
if feature_count > 50000 and not POSTGRESQL_AVAILABLE:
    iface.messageBar().pushWarning(
        "FilterMate - Performance",
        f"Large dataset ({feature_count} features) detected. "
        "Consider installing psycopg2 for better performance."
    )
```

## Testing & Validation

### Performance Test Suite

**File:** `tests/test_performance.py` (450 lines)

**Test Categories:**
1. Spatial index creation
2. Geometry cache effectiveness
3. Predicate ordering validation
4. Temporary table performance
5. Large dataset handling
6. Regression tests

**Run Tests:**
```bash
pytest tests/test_performance.py -v
```

### Interactive Benchmarks

**File:** `tests/benchmark_simple.py` (350 lines)

**Features:**
- Before/after comparisons
- Real-time measurements
- Visual progress
- Multiple scenarios

**Run Benchmarks:**
```bash
python tests/benchmark_simple.py
```

## Memory Management

### Memory-Efficient Patterns

**Geometry Cache:**
- LRU eviction policy
- Configurable max size (default: 1000)
- Automatic cleanup on task completion

**Temporary Tables:**
- Created in temp schema
- Automatic cleanup on connection close
- No disk space accumulation

**Connection Pooling:**
- Proper connection closure
- Cleanup on error
- Resource tracking

### Memory Limits

**Default Limits:**
- Geometry cache: 1000 geometries (~10MB)
- Feature batch size: 1000 features
- Temporary table: Database-dependent

## Small PostgreSQL Dataset Optimization (v2.4.0)

**Status:** ✅ Implemented (December 17, 2025)  
**Files:** 
- `modules/backends/factory.py` (BackendFactory, load_postgresql_to_memory)
- `modules/backends/ogr_backend.py` (_apply_filter_with_memory_optimization)
- `modules/constants.py` (SMALL_DATASET_THRESHOLD)
- `config/config.default.json` (SMALL_DATASET_OPTIMIZATION)

**Problem:** For small PostgreSQL datasets, network overhead for spatial queries can be slower than in-memory processing.

**Solution:** For PostgreSQL layers with ≤ 5000 features (configurable):
1. Load all features into a QGIS memory layer
2. Use OGR backend for spatial calculations on memory layer (fast, no network)
3. Transfer selected feature IDs back to PostgreSQL layer as subset filter

**Performance Gain:**
- Small datasets (< 5k features): 2-10× faster
- Eliminates network round-trips for spatial predicates
- Memory layer cached for repeated operations

**Configuration:**
```json
{
  "APP": {
    "OPTIONS": {
      "SMALL_DATASET_OPTIMIZATION": {
        "enabled": true,
        "threshold": 5000,
        "method": "ogr_memory"
      }
    }
  }
}
```

## Phase 4 Performance Optimizations (v2.4.5 - December 2025)

### 1. Query Expression Cache ✅ IMPLEMENTED

**Status:** ✅ Implemented  
**File:** `modules/tasks/query_cache.py` (280 lines)  
**Integration:** `modules/tasks/filter_task.py` (`_build_backend_expression`)

**Impact:**
- 10-20% faster on repeated filtering operations
- LRU eviction (max 100 cached expressions)
- Cache key: layer_id + predicates + buffer + source_hash + provider

**Key Methods:**
```python
cache = get_query_cache()
key = cache.get_cache_key(layer_id, predicates, buffer, source_hash, provider_type)
cached_expr = cache.get(key)  # Returns cached or None
cache.put(key, expression)    # Store for future use
```

**Statistics:**
```python
stats = cache.get_stats()  # hits, misses, hit_rate_percent
```

---

### 2. Parallel Filter Executor ✅ IMPLEMENTED

**Status:** ✅ Implemented  
**File:** `modules/tasks/parallel_executor.py` (300 lines)  
**Integration:** Ready for use in `_filter_all_layers_with_progress`

**Impact:**
- 2-4× faster on multi-core systems (4+ cores)
- ThreadPoolExecutor with configurable worker count
- Auto-detect optimal worker count (CPU cores - 1)

**Key Classes:**
```python
from modules.tasks.parallel_executor import ParallelFilterExecutor, FilterResult

executor = ParallelFilterExecutor(max_workers=4)
results = executor.filter_layers_parallel(
    layers=[(layer1, props1), (layer2, props2)],
    filter_func=execute_geometric_filtering,
    progress_callback=update_progress,
    cancel_check=lambda: self.isCanceled()
)
```

**Configuration:**
```python
ParallelConfig.ENABLED = True           # Enable/disable globally
ParallelConfig.MIN_LAYERS_THRESHOLD = 2 # Min layers for parallel
ParallelConfig.MAX_WORKERS = 0          # 0 = auto-detect
```

**Thread Safety:**
- Each thread gets its own database connection
- Layer modifications via QueuedConnection signals
- Progress callbacks are thread-safe

---

### 3. Result Streaming Exporter ✅ IMPLEMENTED

**Status:** ✅ Implemented  
**File:** `modules/tasks/result_streaming.py` (350 lines)  
**Integration:** Ready for use in export operations

**Impact:**
- 50-80% memory reduction for large exports (> 100k features)
- Configurable batch sizes (default: 5000 features)
- Progress tracking with ETA

**Key Classes:**
```python
from modules.tasks.result_streaming import StreamingExporter, StreamingConfig

config = StreamingConfig(batch_size=5000)
exporter = StreamingExporter(config)

result = exporter.export_layer_streaming(
    source_layer=layer,
    output_path='/path/to/output.gpkg',
    format='gpkg',
    progress_callback=on_progress
)
```

**Config Presets:**
```python
StreamingConfig.for_large_dataset()       # 10k batch, 1GB memory limit
StreamingConfig.for_memory_constrained()  # 1k batch, 256MB memory limit
```

**Memory Estimation:**
```python
from modules.tasks.result_streaming import estimate_export_memory
mem_bytes = estimate_export_memory(feature_count=1000000, avg_geometry_vertices=100)
```

---

### 4. Prepared Statements ✅ ALREADY IMPLEMENTED

**Status:** ✅ Already exists  
**File:** `modules/prepared_statements.py` (676 lines)  
**Classes:** `PostgreSQLPreparedStatements`, `SpatialitePreparedStatements`

**Available Methods:**
- `insert_subset_history()` - History record insertion
- `delete_subset_history()` - History cleanup
- `insert_layer_properties()` - Layer metadata

**Usage:**
```python
from modules.prepared_statements import create_prepared_statements

ps_manager = create_prepared_statements(connection, 'postgresql')
ps_manager.insert_subset_history(...)
```

---

## Thread Safety Considerations (v2.4.4+) ⚠️ CRITICAL

### OGR Backend Sequential Execution
QGIS `QgsVectorLayer` objects are NOT thread-safe. Starting from v2.4.4:

1. **OGR layers** automatically use sequential execution (not parallel)
2. **Geometric filtering** forces sequential mode for safety
3. **PostgreSQL/Spatialite** can still use parallel execution (database connections are per-thread)

**Impact:** Parallel execution speedup only applies to database backends.

---

## Phase 4 Optimizations (v2.4.2 - December 18, 2025) ⭐ COMPLETE

### 1. Query Expression Cache ✅ INTEGRATED

**Status:** ✅ Implemented & Integrated  
**Files:** 
- `modules/tasks/query_cache.py` (~280 lines)
- `modules/tasks/filter_task.py` (`_build_backend_expression`)

**Impact:**
- 10-20% faster on repeated filtering operations
- LRU eviction with configurable max size (default: 100)
- Hash-based cache keys for efficient lookups

**Cache Key Components:**
- `layer_id`: Target layer identifier
- `predicates`: Spatial predicates hash
- `buffer_value`: Buffer distance
- `source_geometry_hash`: MD5 of source geometry
- `provider_type`: Backend type

### 2. Parallel Filter Execution ✅ INTEGRATED

**Status:** ✅ Implemented & Integrated  
**Files:**
- `modules/tasks/parallel_executor.py` (~300 lines)
- `modules/tasks/filter_task.py` (`_filter_all_layers_with_progress`)

**New Methods Added to FilterEngineTask:**
- `_filter_all_layers_parallel()`: Parallel execution using ThreadPoolExecutor
- `_filter_all_layers_sequential()`: Sequential fallback (original behavior)
- `_log_filtering_summary()`: Centralized logging

**Configuration (config.default.json → APP.OPTIONS):**
```json
"PARALLEL_FILTERING": {
    "enabled": {"value": true},
    "min_layers": {"value": 2},
    "max_workers": {"value": 0}  // 0 = auto-detect CPU cores
}
```

**Impact:**
- 2-4× faster on multi-core systems
- Auto-detects optimal worker count (CPU cores - 1)
- Thread-safe progress tracking

### 3. Result Streaming (Export) ✅ INTEGRATED

**Status:** ✅ Implemented & Integrated  
**Files:**
- `modules/tasks/result_streaming.py` (~350 lines)
- `modules/tasks/filter_task.py` (`execute_exporting`)

**New Methods Added to FilterEngineTask:**
- `_calculate_total_features()`: Count features across layers
- `_export_with_streaming()`: Streaming export with batch processing

**Configuration (config.default.json → APP.OPTIONS):**
```json
"STREAMING_EXPORT": {
    "enabled": {"value": true},
    "feature_threshold": {"value": 10000},
    "chunk_size": {"value": 5000}
}
```

**Impact:**
- 50-80% memory reduction for exports > 10k features
- Automatic activation based on feature count threshold
- Progress tracking with real-time updates

### 4. Prepared Statements (Already Available)

**Status:** ✅ Already Implemented  
**File:** `modules/prepared_statements.py` (~676 lines)

**Classes:**
- `PostgreSQLPreparedStatements`: Named prepared statements
- `SpatialitePreparedStatements`: Parameterized SQLite queries

### Phase 4 Tests

**File:** `tests/test_phase4_optimizations.py`  
**Tests:** 27 unit tests (all passing)  
**Coverage:**
- QueryExpressionCache (10 tests)
- ParallelFilterExecutor (4 tests)
- ParallelConfig (3 tests)
- StreamingExporter (7 tests)
- GlobalCacheFunction (1 test)

---

## Future Optimizations (Post v2.4.5)

## Best Practices for Users

### Optimal Performance Tips

1. **Use PostgreSQL for large datasets**
   - Install psycopg2
   - Host data on PostgreSQL server
   - 10-100× faster on 100k+ features

2. **Use GeoPackage for medium datasets** ⭐ NEW
   - Automatically uses fast Spatialite backend
   - 10× faster than Shapefiles on spatial operations
   - Better for 10k-100k features

3. **Enable spatial indexes**
   - Automatic for Shapefiles (v2.1.0+)
   - Create manually for GeoPackage if needed
   - Essential for spatial queries

4. **Filter incrementally**
   - Apply simple filters first
   - Add complex predicates after
   - Reduce intermediate result size

5. **Use appropriate backend**
   - PostgreSQL: > 50k features
   - GeoPackage/Spatialite: 10k-50k features
   - Shapefile/OGR: < 10k features

6. **Monitor performance warnings**
   - Read message bar recommendations
   - Consider alternative backends
   - Optimize data source if needed

## Performance Documentation

### Related Documentation Files

- `docs/IMPLEMENTATION_STATUS.md`: Optimization implementation status
- `tests/README.md`: Performance testing guide
- `.github/copilot-instructions.md`: Performance considerations section
- `docs/PERFORMANCE_STABILITY_IMPROVEMENTS_2025-12-17.md`: v2.3.5 improvements

## PostgreSQL Layer Initialization Optimization (v2.4.1)

**Status:** ✅ Implemented (December 17, 2025)  
**File:** `modules/tasks/layer_management_task.py`  

**Problem:** PostgreSQL layer initialization was slow due to:
1. CLUSTER operation on each table (very slow, can take minutes on large tables)
2. ANALYZE VERBOSE on each table (slow, verbose output not needed)
3. CREATE INDEX IF NOT EXISTS (runs even when indexes exist)
4. Opening/closing PostgreSQL connections for each layer (redundant)

**Solution - Optimizations in `create_spatial_index_for_postgresql_layer()`:**

1. **Check index existence before creating** (lines 979-1012):
   ```python
   # Query pg_indexes to check if GIST index exists
   cursor.execute("SELECT 1 FROM pg_indexes WHERE ...")
   if not gist_exists:
       cursor.execute('CREATE INDEX ...')
   ```

2. **Remove CLUSTER at init** (deferred to filter time if beneficial):
   - CLUSTER reorganizes disk pages - very expensive
   - Not needed at initialization
   - Will be considered during heavy filtering if statistics show benefit

3. **Conditional ANALYZE** (only if table has no statistics):
   ```python
   # Check pg_statistic for existing stats
   cursor.execute("SELECT 1 FROM pg_statistic ...")
   if not has_stats:
       cursor.execute('ANALYZE ...')
   ```

4. **Connection caching per datasource** (`_postgresql_connection_cache`):
   - Cache connection availability per host:port:database
   - Avoids redundant connection tests for layers from same database

**Performance Gain:**
- Before: ~2-5 seconds per PostgreSQL layer (with CLUSTER + ANALYZE)
- After: ~0.1-0.5 seconds per layer (check-before-create + caching)
- **Gain: 5-50× faster** depending on table size and index existence

**Applies to:** All PostgreSQL layers at project load / layer add

## Phase 5 Advanced PostgreSQL Optimizations (v2.5.9 - January 2025) ⭐ NEW

### 1. Progressive/Two-Phase Filtering ✅ IMPLEMENTED

**Status:** ✅ Implemented  
**File:** `modules/tasks/progressive_filter.py` (~750 lines)  
**Integration:** `modules/backends/postgresql_backend.py`

**Problem:** Complex spatial expressions (ST_Buffer, ST_Intersects, nested subqueries) on large PostgreSQL datasets cause:
- Memory exhaustion (fetching all results at once)
- Slow execution (full predicate evaluation on every row)

**Solution - Two-Phase Filtering:**
1. **Phase 1 (Bbox Pre-filter):** Uses `geom && ST_Envelope(source_geom)` with GIST index
   - Eliminates 80-95% of candidate rows using fast bounding box intersection
   - Returns candidate IDs only
2. **Phase 2 (Full Predicate):** Applies expensive predicates only on candidates
   - `WHERE id IN (phase1_ids) AND full_complex_expression`

**Key Classes:**
```python
from modules.tasks.progressive_filter import (
    ProgressiveFilterExecutor, TwoPhaseFilter, LazyResultIterator
)

executor = ProgressiveFilterExecutor(connection, query_cache)
result = executor.filter_with_strategy(
    layer_props, source_geometry, buffer_value, predicates,
    feature_count=150000, complexity_score=180
)
```

**Strategies:**
- `DIRECT`: Simple predicates, small datasets (score < 50)
- `MATERIALIZED`: Medium complexity, moderate size (50 ≤ score < 150)
- `TWO_PHASE`: Complex predicates, any size (150 ≤ score < 500)
- `PROGRESSIVE`: Very complex + large datasets (score ≥ 500)

**Performance Gain:**
- Two-phase filtering: 3-10× faster on complex expressions
- Bbox pre-filter eliminates 80-95% candidates before expensive operations

---

### 2. Query Complexity Estimator ✅ IMPLEMENTED

**Status:** ✅ Implemented  
**File:** `modules/tasks/query_complexity_estimator.py` (~450 lines)  
**Integration:** `modules/backends/postgresql_backend.py`

**Purpose:** Dynamically analyze SQL expressions to estimate computational cost and select optimal strategy.

**Key Class:**
```python
from modules.tasks.query_complexity_estimator import QueryComplexityEstimator

estimator = QueryComplexityEstimator()
result = estimator.estimate_complexity(sql_expression)

print(result.total_score)       # e.g., 185
print(result.recommended_strategy)  # "TWO_PHASE"
print(result.breakdown)         # Detailed cost factors
```

**Operation Costs (weighted):**
| Operation | Cost | Reason |
|-----------|------|--------|
| ST_Buffer | 12 | Creates new geometry |
| ST_Transform | 10 | Coordinate reprojection |
| ST_Intersects | 5 | Can use GIST index |
| ST_Within | 6 | Containment test |
| EXISTS | 20 | Subquery execution |
| IN (subquery) | 15 | Subquery + lookup |

**Strategy Thresholds:**
- score < 50: `DIRECT` (simple, use standard query)
- 50 ≤ score < 150: `MATERIALIZED` (use materialized view)
- 150 ≤ score < 500: `TWO_PHASE` (bbox + full predicate)
- score ≥ 500: `PROGRESSIVE` (chunked streaming)

---

### 3. Lazy Cursor Streaming ✅ IMPLEMENTED

**Status:** ✅ Implemented  
**File:** `modules/tasks/progressive_filter.py` (in `LazyResultIterator`)  
**Threshold:** 50,000+ features

**Purpose:** Memory-efficient iteration over large PostgreSQL result sets using server-side cursors.

**Key Class:**
```python
from modules.tasks.progressive_filter import LazyResultIterator

with LazyResultIterator(connection, sql_query, chunk_size=5000) as iterator:
    for batch in iterator:
        process_batch(batch)  # Yields chunks of 5000 IDs
```

**Benefits:**
- Never loads full result set into memory
- Server-side cursor (PostgreSQL `DECLARE ... CURSOR`)
- Configurable chunk size (default: 5000 IDs)
- Progress tracking support

**Performance Gain:**
- Memory usage: 50-80% reduction for large exports
- Enables processing of 1M+ feature datasets

---

### 4. Enhanced Query Cache ✅ ENHANCED

**Status:** ✅ Enhanced (v2.5.9)  
**File:** `modules/tasks/query_cache.py`  

**New Features:**
- **TTL Support:** Cache entries expire after configurable time
- **Result Count Caching:** Avoid expensive COUNT queries
- **Complexity Score Caching:** Don't re-analyze same expressions
- **Hot Entries Tracking:** Statistics on most-accessed queries
- **Execution Time Logging:** Track query performance over time

**New Methods:**
```python
cache = get_query_cache()

# Get cached with count
expr, count = cache.get_with_count(key)

# Put with metadata
cache.put(key, expr, result_count=15000, complexity_score=125)

# Evict expired entries
removed = cache.evict_expired()

# Get hot (frequently accessed) entries
hot = cache.get_hot_entries(limit=10)
```

**Configuration (config.default.json):**
```json
"QUERY_CACHE": {
    "enabled": {"value": true},
    "max_size": {"value": 100},
    "ttl_seconds": {"value": 0},  // 0 = no expiration
    "cache_result_counts": {"value": true},
    "cache_complexity_scores": {"value": true}
}
```

---

### 5. PostgreSQL Backend Integration ✅ INTEGRATED

**Status:** ✅ Integrated  
**File:** `modules/backends/postgresql_backend.py`

**New Constants:**
```python
TWO_PHASE_COMPLEXITY_THRESHOLD = 100  # Minimum score for two-phase
LAZY_CURSOR_THRESHOLD = 50000         # Features for streaming cursor
```

**New Method:** `_apply_with_progressive_filter()`
- Checks complexity score and feature count
- Routes to appropriate strategy (direct, two-phase, lazy)
- Falls back gracefully on errors

**Integration Points:**
- `apply_filter()` now checks complexity before standard execution
- Automatic strategy selection based on estimator

---

### Phase 5 Performance Summary

| Optimization | Target | Impact |
|--------------|--------|--------|
| Two-Phase Filtering | Complex expressions | 3-10× faster |
| Lazy Cursor | 50k+ features | 50-80% less memory |
| Query Complexity Estimator | All queries | Optimal strategy selection |
| Enhanced Cache | Repeated queries | 20-40% faster (cache hits) |

**Overall:** Up to 10× faster on complex PostgreSQL queries with reduced memory footprint.

---

## v2.9.x PostgreSQL Advanced MV Optimizations (January 2026) ⭐ NEW

### Covering GIST Indexes (v2.9.1)

**Status:** ✅ Implemented  
**Requirement:** PostgreSQL 11+

```sql
CREATE INDEX idx_mv_geom ON mv USING GIST (geom) INCLUDE (pk);
```

**Impact:** 10-30% faster spatial queries (avoids table lookups)

---

### Bbox Pre-filter Column (v2.9.1)

**Status:** ✅ Implemented  
**Threshold:** ≥10k features

```sql
CREATE TABLE mv AS SELECT pk, geom, ST_Envelope(geom) AS bbox FROM ...;
CREATE INDEX idx_mv_bbox ON mv USING GIST (bbox);
```

**Impact:** 2-5x faster for `&&` operator pre-filtering

---

### Async CLUSTER (v2.9.1)

**Status:** ✅ Implemented  
**Thresholds:**
- < 50k: Synchronous CLUSTER
- 50k-100k: Async CLUSTER (background thread, non-blocking)
- > 100k: Skip CLUSTER (too expensive)

---

### ST_PointOnSurface (v2.9.2)

**Status:** ✅ Implemented  
**Problem:** `ST_Centroid()` can return point OUTSIDE concave polygons

**Solution:**
```python
CENTROID_MODE_DEFAULT = 'point_on_surface'  # 'centroid' | 'point_on_surface' | 'auto'
```

**Impact:** More accurate centroid-based filtering for complex polygons

---

### Adaptive Simplification (v2.9.2)

**Status:** ✅ Implemented

```python
SIMPLIFY_BEFORE_BUFFER_ENABLED = True
SIMPLIFY_TOLERANCE_FACTOR = 0.1         # tolerance = buffer × 0.1
SIMPLIFY_MIN_TOLERANCE = 0.5            # meters
SIMPLIFY_MAX_TOLERANCE = 10.0           # meters
```

**Impact:** 
- Reduces vertex count 50-90% before buffer operations
- ST_Buffer runs 2-10x faster on simplified geometry

---

### Complex Expression Materialization (v2.8.7)

**Status:** ✅ Implemented

Automatic detection and materialization of expensive spatial expressions:
- EXISTS clause with spatial predicates
- EXISTS clause with ST_Buffer
- Multi-step filters with MV + EXISTS combinations

**Impact:** 10-100x faster canvas rendering for complex multi-step filters

---

## v2.9.x Spatialite Optimizations ⭐ NEW

### Range-Based Filter (v2.9.4)

**Status:** ✅ Implemented  
**Problem:** SQL subqueries not supported by OGR setSubsetString()

**Solution:** `_build_range_based_filter()` replaces `_build_fid_table_filter()`

```sql
-- Before (v2.8.7): NOT WORKING with OGR
"fid" IN (SELECT fid FROM "_fm_fids_xxx")

-- After (v2.9.4): WORKING with all providers
("fid" BETWEEN 1 AND 500) OR ("fid" BETWEEN 502 AND 1000) OR "fid" IN (503, 507)
```

**Impact:** Large dataset filtering (≥20k features) now works correctly

---

### MakeValid Wrapper (v2.9.6)

**Status:** ✅ Implemented  
**Problem:** Invalid source geometries cause 0 results

**Solution:** All source geometries wrapped in MakeValid():
```sql
MakeValid(GeomFromText('{wkt}', {srid}))
```

**Impact:** Layers from same GeoPackage now filter correctly

---

## Version History

- **v2.9.6** (Jan 6, 2026): MakeValid wrapper for all source geometries
- **v2.9.5** (Jan 5, 2026): QGIS shutdown crash fix (QgsMessageLog)
- **v2.9.4** (Jan 5, 2026): Range-based filter for Spatialite large datasets
- **v2.9.2** (Jan 4, 2026): ST_PointOnSurface, adaptive simplification
- **v2.9.1** (Jan 4, 2026): PostgreSQL MV optimizations (INCLUDE, async CLUSTER, bbox)
- **v2.8.9** (Jan 4, 2026): MV management UI, simplified popup
- **v2.8.7** (Jan 4, 2026): Complex expression materialization, psycopg2 centralization
- **v2.8.1** (Jan 3, 2026): Orphaned MV recovery
- **v2.5.20** (Jan 3, 2026): Multi-backend extended canvas refresh
- **v2.5.19** (Jan 3, 2026): PostgreSQL complex filter display fix
- **v2.5.9** (Dec 31, 2025): Progressive filtering, complexity estimation, enhanced cache
- **v2.5.7** (Dec 31, 2025): CRS utilities module, automatic metric conversion
- **v2.5.6** (Dec 30, 2025): Bidirectional selection sync
- **v2.5.5** (Dec 29, 2025): PostgreSQL ST_IsEmpty fix for all empty geometry types
- **v2.4.1** (Dec 17, 2025): PostgreSQL init optimization (5-50× gain)
- **v2.3.5** (Dec 17, 2025): GeoPackage Spatialite routing (10× gain)
- **v2.3.4** (Dec 16, 2025): PostgreSQL 2-part table reference fix
- **v2.3.0** (Dec 13, 2025): Primary key detection optimization
- **v2.1.0** (Dec 04, 2025): Predicate ordering, spatial indexes, geometry cache
