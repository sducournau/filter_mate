# Enhanced Auto-Optimization System (v2.8.0 - v2.9.6)

**Last Updated:** January 6, 2026

## Overview

FilterMate v2.8.0+ introduces an **Enhanced Auto-Optimization System** with:

- **Performance Metrics Collection**: Track optimization effectiveness
- **Query Pattern Detection**: Identify recurring queries and pre-optimize
- **Adaptive Thresholds**: Automatically tune thresholds based on observed performance
- **Parallel Processing**: Multi-threaded spatial operations for large datasets
- **LRU Caching**: Intelligent caching with automatic eviction
- **Selectivity Histograms**: Better selectivity estimation

## New Modules

### modules/backends/optimizer_metrics.py
- `OptimizationMetricsCollector` - Central metrics hub (singleton)
- `LRUCache` - Thread-safe LRU cache with TTL
- `QueryPatternDetector` - Detect recurring query patterns
- `AdaptiveThresholdManager` - Dynamic threshold tuning
- `SelectivityHistogram` - Selectivity estimation via sampling

### modules/backends/parallel_processor.py
- `ParallelChunkProcessor` - Thread-safe parallel spatial filtering
- `GeometryBatch` - Batch geometry operations for workers
- `ParallelAttributeProcessor` - Parallel attribute filtering

### modules/backends/auto_optimizer.py (enhanced)
- `EnhancedAutoOptimizer` - Extends AutoOptimizer with all v2.8.0 features
- `get_enhanced_optimizer()` - Factory function for enhanced optimizer

## Key Changes in v2.7.x → v2.8.0

### Critical Fixes
1. **v2.7.2**: PostgreSQL target + OGR source now correctly uses WKT mode
   - Previously created invalid table references for non-PostgreSQL sources
   - Fixed in `_prepare_geometries_by_provider()` and `get_source_geometry_for_backend()`

2. **v2.7.3**: WKT mode decision uses SELECTED feature count
   - Now uses `task_features` count from task_parameters
   - Enables WKT mode for 1 selected commune out of 930

3. **v2.7.4**: Improved diagnostic logging for geometric filtering
   - All layers now logged with selection status
   - Enhanced troubleshooting for "distant layers not filtered" issues

4. **v2.7.5**: CASE WHEN wrapper parsing for negative buffers
   - PostgreSQL backend now correctly parses negative buffer expressions

### Configuration Changes
- `get_small_dataset_config()` now reads directly from config.json file
- Small dataset optimization DISABLED by default (return False)
- Progressive chunking is now DEFAULT behavior (removed from recommendations)

## Usage Examples

```python
from filter_mate.modules.backends import get_enhanced_optimizer

# Create enhanced optimizer
optimizer = get_enhanced_optimizer(
    enable_metrics=True,
    enable_parallel=True,
    enable_adaptive_thresholds=True
)

# Start session
session_id = optimizer.start_optimization_session(layer)

# Get plan
plan = optimizer.create_optimization_plan(target_layer=layer, ...)

# Parallel processing
if optimizer.should_use_parallel(layer):
    matching, stats = optimizer.execute_parallel_spatial_filter(...)

# End session
summary = optimizer.end_optimization_session(session_id, execution_time_ms)
```

## Cache Key Enhancement (v2.5.14-15)

Query cache now includes centroid flags for invalidation:
```python
cache_key = cache.get_cache_key(
    layer_id, predicates, buffer_value, source_hash, provider_type,
    source_filter_hash,
    use_centroids=True,        # v2.5.14: distant layer centroid flag
    use_centroids_source=True  # v2.5.15: source layer centroid flag
)
```

## Thread Safety

**Safe in worker threads:**
- `LRUCache` all methods
- `QueryPatternDetector` all methods
- `ParallelChunkProcessor.process_spatial_filter_parallel()`
- `QgsGeometry` operations

**Main thread only:**
- `QgsVectorLayer` access
- QGIS API calls
- Expression evaluation with QGIS context

## v2.9.x PostgreSQL Advanced Optimizations

### Materialized View Enhancements (v2.9.1)

**INCLUDE Clause (PostgreSQL 11+):**
- Covering indexes include primary key column
- Avoids table lookups during spatial queries
- 10-30% faster query performance
- Config: `MV_ENABLE_INDEX_INCLUDE = True`

**Bbox Column (≥10k features):**
- Pre-computed `ST_Envelope(geom)` column
- Dedicated GIST index for `&&` operator
- 2-5x faster for large datasets
- Config: `MV_ENABLE_BBOX_COLUMN = True`

**Async CLUSTER (50k-100k features):**
- Non-blocking CLUSTER in background thread
- Config: `MV_ENABLE_ASYNC_CLUSTER = True`
- Threshold: `MV_ASYNC_CLUSTER_THRESHOLD = 50000`

**Extended Statistics (PostgreSQL 10+):**
- Auto-creation on pk + geom columns
- Better query plans for complex joins
- Config: `MV_ENABLE_EXTENDED_STATS = True`

### Complex Expression Materialization (v2.8.7)

Automatic detection and materialization of expensive expressions:

**Patterns Detected:**
- `EXISTS` clause with spatial predicates (ST_Intersects, ST_Contains, etc.)
- `EXISTS` clause with `ST_Buffer`
- Multi-step filters combining MV references with EXISTS clauses
- `__source` alias patterns with spatial predicates

**Benefits:**
- 10-100x faster canvas rendering for complex multi-step filters
- Expensive spatial operations executed ONCE during MV creation
- Simple `"fid" IN (SELECT pk FROM mv_result)` for setSubsetString

### Centroid Optimization (v2.9.2)

**ST_PointOnSurface for Polygons:**
```python
CENTROID_MODE_DEFAULT = 'point_on_surface'  # Guaranteed inside polygon
```

| Mode | Function | Use Case |
|------|----------|----------|
| `point_on_surface` | `ST_PointOnSurface()` | Default for polygons (accurate) |
| `centroid` | `ST_Centroid()` | Legacy, faster for simple shapes |
| `auto` | Adaptive | PointOnSurface for polygons, Centroid for lines |

### Adaptive Simplification (v2.9.2)

Automatic geometry simplification before buffer operations:
```python
SIMPLIFY_BEFORE_BUFFER_ENABLED = True
SIMPLIFY_TOLERANCE_FACTOR = 0.1         # tolerance = buffer × factor
SIMPLIFY_MIN_TOLERANCE = 0.5            # meters
SIMPLIFY_MAX_TOLERANCE = 10.0           # meters
SIMPLIFY_PRESERVE_TOPOLOGY = True
```

**Performance:**
- Reduces vertex count by 50-90% before buffer
- ST_Buffer runs 2-10x faster on simplified geometry

### MV Management UI (v2.8.9)

**MV Status Widget:**
- Real-time display of active materialized views count
- Shows session views vs. other sessions views
- Color-coded status (Clean ✅, Active 📊, Error ⚠️)

**Quick Cleanup Actions:**
- 🧹 Session: Cleanup MVs from current session only
- 🗑️ Orphaned: Cleanup MVs from inactive sessions
- ⚠️ All: Cleanup all MVs (with confirmation)

---

## Tests

New test file: `tests/test_enhanced_optimizer.py`
- TestLRUCache
- TestQueryPatternDetector
- TestAdaptiveThresholdManager
- TestSelectivityHistogram
- TestOptimizationMetricsCollector
- TestParallelProcessing
- TestEnhancedAutoOptimizer
- TestIntegration
