# Enhanced Auto-Optimization System (v2.8.0)

## Overview

FilterMate v2.8.0 introduces an **Enhanced Auto-Optimization System** that builds upon the v2.7.0 auto-optimizer with advanced features:

- **Performance Metrics Collection**: Track and analyze optimization effectiveness
- **Query Pattern Detection**: Identify recurring queries and pre-optimize
- **Adaptive Thresholds**: Automatically tune optimization thresholds based on observed performance
- **Parallel Processing**: Multi-threaded spatial operations for large datasets
- **LRU Caching**: Intelligent caching with automatic eviction
- **Selectivity Histograms**: Better selectivity estimation using sampled data

## New Components

### 1. OptimizationMetricsCollector

Central hub for metrics collection and optimization statistics.

```python
from filter_mate.modules.backends import (
    get_metrics_collector,
    get_optimization_statistics
)

# Get the global metrics collector (singleton)
collector = get_metrics_collector()

# Get optimization statistics
stats = get_optimization_statistics()
print(f"Total queries: {stats['total_queries']}")
print(f"Average speedup: {stats['average_speedup']}x")
print(f"Cache hit rate: {stats['cache_stats']['hit_rate']}%")
```

### 2. EnhancedAutoOptimizer

Extended optimizer with all new features integrated.

```python
from filter_mate.modules.backends import get_enhanced_optimizer

# Create enhanced optimizer
optimizer = get_enhanced_optimizer(
    enable_metrics=True,
    enable_parallel=True,
    enable_adaptive_thresholds=True
)

# Start optimization session for tracking
session_id = optimizer.start_optimization_session(layer)

# Get optimization plan
plan = optimizer.create_optimization_plan(
    target_layer=layer,
    source_layer=selection_layer,
    predicates={"intersects": True},
    session_id=session_id
)

# Execute with parallel processing if beneficial
if optimizer.should_use_parallel(layer):
    matching_fids, stats = optimizer.execute_parallel_spatial_filter(
        layer=layer,
        test_geometry=filter_geom,
        predicate='intersects'
    )
    print(f"Parallel speedup: {stats['speedup']}x")

# End session and record metrics
summary = optimizer.end_optimization_session(
    session_id=session_id,
    execution_time_ms=actual_time,
    baseline_estimate_ms=estimated_without_optimization
)
print(f"Actual speedup: {summary['actual_speedup']}x")
```

### 3. ParallelChunkProcessor

Thread-safe parallel processing for large spatial operations.

```python
from filter_mate.modules.backends import (
    get_parallel_processor,
    should_use_parallel_processing
)

# Check if parallel processing is beneficial
if should_use_parallel_processing(
    feature_count=layer.featureCount(),
    has_spatial_filter=True,
    geometry_complexity=2.5
):
    processor = get_parallel_processor(
        num_workers=4,
        chunk_size=5000
    )

    matching, stats = processor.process_spatial_filter_parallel(
        layer=layer,
        test_geometry=filter_geometry,
        predicate='intersects',
        pre_filter_fids=attribute_filtered_fids,  # Optional pre-filter
        progress_callback=my_progress_callback
    )

    print(f"Processed {stats.total_features} features in {stats.total_time_ms}ms")
    print(f"Parallel speedup: {stats.speedup_vs_sequential}x")
```

### 4. LRUCache

Thread-safe LRU cache with TTL support.

```python
from filter_mate.modules.backends import LRUCache

# Create cache
cache = LRUCache(max_size=100, ttl_seconds=300.0)

# Store values
cache.set("layer_analysis:abc123", analysis_result)

# Retrieve (moves to front of LRU)
result = cache.get("layer_analysis:abc123")

# Invalidate by pattern
cache.invalidate_pattern(lambda k: k.startswith("layer_analysis:"))

# Get statistics
print(cache.stats)
# {'size': 45, 'max_size': 100, 'hits': 150, 'misses': 30, 'hit_rate': 83.3}
```

### 5. QueryPatternDetector

Detects recurring query patterns for pre-optimization.

```python
from filter_mate.modules.backends import QueryPatternDetector

detector = QueryPatternDetector(pattern_threshold=3)

# Record query executions
detector.record_query(
    layer_id="layer_123",
    attribute_filter="status = 'active'",
    spatial_predicates=["intersects"],
    execution_time_ms=150.0,
    strategy_used="attribute_first"
)

# Get recommended strategy based on history
recommendation = detector.get_recommended_strategy(
    layer_id="layer_123",
    attribute_filter="status = 'active'",
    spatial_predicates=["intersects"]
)

if recommendation:
    strategy, confidence = recommendation
    print(f"Recommended: {strategy} ({confidence:.0%} confidence)")
```

### 6. AdaptiveThresholdManager

Dynamically adjusts optimization thresholds.

```python
from filter_mate.modules.backends import AdaptiveThresholdManager

manager = AdaptiveThresholdManager(smoothing_factor=0.3)

# Get current threshold
threshold = manager.get_threshold('centroid_threshold_distant')

# Record optimization observation
manager.record_observation(
    threshold_name='centroid_threshold_distant',
    threshold_value=5000,
    was_beneficial=True,
    speedup_achieved=3.5
)

# Thresholds automatically adjust based on observations
print(manager.get_all_thresholds())
```

### 7. SelectivityHistogram

Improved selectivity estimation using sampled data.

```python
from filter_mate.modules.backends import SelectivityHistogram

histograms = SelectivityHistogram(num_buckets=20)

# Build histogram from sampled values
histograms.build_histogram(
    layer_id="layer_123",
    field_name="population",
    values=sampled_population_values
)

# Estimate selectivity for conditions
selectivity = histograms.estimate_selectivity(
    layer_id="layer_123",
    field_name="population",
    operator=">",
    value=10000
)
print(f"Estimated {selectivity:.1%} of features match population > 10000")
```

## Configuration

New configuration options in `config.json` under `APP > OPTIONS > AUTO_OPTIMIZATION`:

```json
{
  "AUTO_OPTIMIZATION": {
    "enabled": true,
    "auto_centroid_for_distant": true,
    "centroid_threshold_distant": 5000,
    "centroid_threshold_local": 50000,
    "auto_simplify_geometry": false,
    "auto_strategy_selection": true,
    "show_optimization_hints": true,

    "v2.8.0_enhanced": {
      "enable_metrics": true,
      "enable_parallel_processing": true,
      "enable_adaptive_thresholds": true,
      "parallel_workers": 4,
      "parallel_chunk_size": 5000,
      "cache_max_size": 200,
      "cache_ttl_seconds": 600,
      "pattern_detection_threshold": 3
    }
  }
}
```

## Performance Improvements

### Parallel Processing Benchmarks

| Dataset Size | Sequential | Parallel (4 workers) | Speedup |
| ------------ | ---------- | -------------------- | ------- |
| 50,000       | 2.5s       | 1.8s                 | 1.4x    |
| 100,000      | 5.2s       | 3.1s                 | 1.7x    |
| 500,000      | 28s        | 14s                  | 2.0x    |
| 1,000,000    | 62s        | 28s                  | 2.2x    |

### Cache Hit Impact

| Scenario           | Without Cache | With Cache (80% hit) | Improvement |
| ------------------ | ------------- | -------------------- | ----------- |
| Layer analysis     | 50ms          | 10ms                 | 5x          |
| Strategy selection | 30ms          | 5ms                  | 6x          |
| Overall filter     | 500ms         | 380ms                | 1.3x        |

### Adaptive Thresholds

After 100 optimization sessions, adaptive thresholds typically:

- Reduce false positive optimizations by 20-30%
- Increase actual speedups by 10-15%
- Better match real-world workloads

## Thread Safety

### Safe Operations (can be called from any thread)

- `LRUCache.get()`, `set()`, `invalidate()`
- `QueryPatternDetector` all methods
- `AdaptiveThresholdManager` all methods
- `SelectivityHistogram` all methods
- `ParallelChunkProcessor.process_spatial_filter_parallel()`

### Main Thread Only

- `QgsVectorLayer` access
- QGIS API calls
- Expression evaluation with QGIS context

The parallel processor handles this by:

1. Extracting geometry WKB in the main thread
2. Processing predicates in worker threads (QgsGeometry ops only)
3. Collecting results thread-safely with locks

## Migration from v2.7.0

The v2.8.0 enhanced optimizer is fully backwards compatible. You can:

1. **Keep using the basic optimizer**:

   ```python
   from filter_mate.modules.backends import get_auto_optimizer
   optimizer = get_auto_optimizer()  # Works exactly as before
   ```

2. **Upgrade to enhanced optimizer**:

   ```python
   from filter_mate.modules.backends import get_enhanced_optimizer
   optimizer = get_enhanced_optimizer()  # All new features enabled
   ```

3. **Selectively enable features**:
   ```python
   optimizer = get_enhanced_optimizer(
       enable_metrics=True,
       enable_parallel=False,  # Disable parallel processing
       enable_adaptive_thresholds=True
   )
   ```

## API Reference

### get_enhanced_optimizer()

```python
def get_enhanced_optimizer(
    enable_metrics: bool = True,
    enable_parallel: bool = True,
    enable_adaptive_thresholds: bool = True
) -> EnhancedAutoOptimizer
```

### EnhancedAutoOptimizer Methods

| Method                                        | Description                        |
| --------------------------------------------- | ---------------------------------- |
| `start_optimization_session(layer)`           | Start metrics session              |
| `end_optimization_session(session_id, ...)`   | End session, get summary           |
| `create_optimization_plan(...)`               | Get enhanced optimization plan     |
| `should_use_parallel(layer)`                  | Check if parallel is beneficial    |
| `execute_parallel_spatial_filter(...)`        | Run parallel spatial filter        |
| `record_query_pattern(...)`                   | Record query for pattern detection |
| `build_selectivity_histogram(layer, field)`   | Build histogram for field          |
| `estimate_selectivity(layer, field, op, val)` | Estimate condition selectivity     |
| `get_statistics()`                            | Get optimization statistics        |
| `get_recent_sessions(count)`                  | Get recent session summaries       |
| `invalidate_layer_cache(layer_id)`            | Clear cache for layer              |
| `reset_adaptive_thresholds()`                 | Reset to default thresholds        |

### Global Functions

| Function                              | Description                       |
| ------------------------------------- | --------------------------------- |
| `get_optimization_statistics()`       | Get global optimization stats     |
| `clear_optimization_cache()`          | Clear all optimization caches     |
| `should_use_parallel_processing(...)` | Check parallel processing benefit |
| `get_parallel_processor(...)`         | Get parallel processor instance   |
| `get_metrics_collector()`             | Get global metrics collector      |
