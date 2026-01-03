# Enhanced Auto-Optimization System (v2.8.0)

## Overview

FilterMate v2.8.0 introduces an **Enhanced Auto-Optimization System** with:

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
