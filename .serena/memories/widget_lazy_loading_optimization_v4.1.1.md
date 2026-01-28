# Widget Lazy Loading & Expression Optimization - v4.1.1

**Date:** January 27, 2026  
**Version:** 4.1.1

## Summary

Implementation of lazy loading and expression-aware optimization for FilterMate widgets to improve UI responsiveness when dealing with large datasets.

## New Components

### 1. UniqueValuesTask (`core/tasks/unique_values_task.py`)

**Purpose:** Async QgsTask for loading unique field values without UI freeze.

**Key Features:**
- Thread-safe using `dataProvider().featureSource()`
- Two extraction methods:
  - Fast: `uniqueValues()` for small layers (<10k features)
  - Memory-efficient: Feature iteration for large layers
- Pagination support (`max_values`, `offset`)
- Progress signals for UI feedback
- `UniqueValuesManager` singleton for lifecycle management

**Usage:**
```python
from core.tasks import get_unique_values_manager

manager = get_unique_values_manager()
manager.fetch_async(
    layer=my_layer,
    field_name="category",
    on_complete=lambda values: update_ui(values),
    max_values=500,
)
```

### 2. ExpressionTypeDetector (`infrastructure/utils/expression_type_detector.py`)

**Purpose:** Analyze QGIS expressions to determine if feature iteration is needed.

**Expression Types:**
- `SIMPLE_FIELD`: Just a quoted field name (e.g., `"category"`) → NO iteration needed
- `DISPLAY_EXPRESSION`: COALESCE, CONCAT, etc. → NO iteration needed
- `FILTER_EXPRESSION`: Boolean expressions → Iteration required
- `AGGREGATE_EXPRESSION`: count(), sum(), etc. → Iteration required
- `SPATIAL_EXPRESSION`: intersects(), within(), etc. → Iteration required

**Optimization Impact:**
- When user selects a field name in custom selection, skip `getFeatures()` entirely
- Returns `ExpressionAnalysis` with optimization hints

**Usage:**
```python
from infrastructure.utils import analyze_expression, ExpressionType

analysis = analyze_expression('"my_field"')
if analysis.expr_type == ExpressionType.SIMPLE_FIELD:
    # Use uniqueValues() - no feature iteration
    values = layer.uniqueValues(field_index)
elif analysis.requires_features:
    # Must iterate features
    request = QgsFeatureRequest().setFilterExpression(expr)
```

### 3. LazyFeatureIterator (`core/tasks/lazy_feature_iterator.py`)

**Purpose:** Memory-efficient feature loading with pagination.

**Key Features:**
- Configurable page size (default: 500)
- On-demand loading (only loads when requested)
- Progress callbacks for UI
- Cancellation support
- Cache for loaded pages

**Use Cases:**
- Virtual scrolling in feature list widgets
- Processing large result sets
- Responsive UI while data loads

**Usage:**
```python
from core.tasks import LazyFeatureIterator

iterator = LazyFeatureIterator(
    layer=my_layer,
    page_size=500,
    expression='"status" = 1'
)

# Get first page immediately
first_page = iterator.get_page(0)
update_ui(first_page)

# Load more as user scrolls
if iterator.has_more_pages():
    next_page = iterator.get_next_page()
```

## Modified Components

### ExploringController (`ui/controllers/exploring_controller.py`)

**Changes:**
1. `_populate_features_list()`: Now uses async for layers >10k features
2. `_populate_features_list_async()`: New method for async loading
3. `_get_unique_values()`: Added threshold warning for large layers

### FilterMateDockWidget (`filter_mate_dockwidget.py`)

**Changes:**
- `exploring_custom_selection()`: 
  - Uses `ExpressionTypeDetector` to skip fetch for simple expressions
  - Limits sync fetch to 10k features for UI responsiveness
  - Logs recommendations for async processing

## Performance Impact

| Scenario | Before | After |
|----------|--------|-------|
| Simple field expression | Fetch all features | Skip fetch (0ms) |
| COALESCE/CONCAT expression | Fetch all features | Skip fetch (0ms) |
| Large layer unique values | UI freeze 2-10s | Async, no freeze |
| Complex filter on 100k features | UI freeze | Limited to 10k + warning |

## Configuration

No new config options. Thresholds are hardcoded:
- `ASYNC_THRESHOLD`: 10,000 features
- `MAX_SYNC_FEATURES`: 10,000 features
- `DEFAULT_PAGE_SIZE`: 500 features

## Testing

Run these scenarios:
1. Select a field name in custom selection → Should NOT fetch features
2. Select COALESCE expression → Should NOT fetch features
3. Load large layer (50k+ features) → Should use async, no UI freeze
4. Filter expression on large layer → Should show warning about limit

## Related Memories

- `performance_optimizations.md`: General performance documentation
- `ui_system.md`: UI widget documentation
