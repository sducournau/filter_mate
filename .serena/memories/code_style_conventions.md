# Code Style Conventions - FilterMate v4.3.10

**Last Updated:** January 22, 2026

## Python Standards

### PEP 8 Compliance
- **Current Status**: 95% compliance (as of January 2026)
- Follow PEP 8 conventions strictly
- Use 4 spaces for indentation (no tabs)
- Maximum line length: 120 characters
- Use docstrings for all classes and functions
- Type hints encouraged but not required (QGIS compatibility)

### Recent Improvements (Phase 1 & 2)
- ✅ 94% wildcard imports eliminated (31/33)
- ✅ 100% bare except clauses fixed (13/13)
- ✅ 100% null comparisons fixed (`!= None` → `is not None`)
- ✅ Redundant imports removed (10+ duplicates)
- ✅ PEP 8 compliance: 85% → 95%

### Import Order
1. Standard library imports
2. Third-party imports (QGIS, PyQt5)
3. Local application imports

**Example:**
```python
import os
import sys
from typing import Optional, Dict, List

from qgis.core import QgsVectorLayer, QgsProject, QgsTask
from qgis.PyQt.QtCore import Qt, pyqtSignal, QObject
from qgis.PyQt.QtWidgets import QWidget, QMessageBox

from .config.config import ENV_VARS
# NEW v4.0: Import from hexagonal locations
from .adapters.backends.postgresql_availability import POSTGRESQL_AVAILABLE
from .infrastructure.utils.layer_utils import get_datasource_connexion_from_layer
from .core.services import FilterService, LayerService
```

### Wildcard Imports (CRITICAL - v2.3.0-alpha)

**Status**: 94% eliminated (2 legitimate re-exports remain)

**NEVER use wildcard imports** except for intentional re-exports:

```python
# ❌ BAD: Wildcard imports
from qgis.PyQt.QtCore import *
from qgis.core import *
from qgis.PyQt.QtWidgets import *

# ✅ GOOD: Explicit imports
from qgis.PyQt.QtCore import (
    Qt, QSettings, QTranslator, QCoreApplication,
    QTimer, pyqtSignal, QObject
)
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsTask,
    QgsMessageLog, Qgis, QgsFeature
)
from qgis.PyQt.QtWidgets import (
    QAction, QApplication, QMenu, QMessageBox,
    QDockWidget, QWidget
)
```

**Legitimate Wildcards (Re-exports Only):**
- `modules/customExceptions.py`: Intentional exception re-export
- `resources.py`: Qt resources re-export (auto-generated)

## Naming Conventions

### Classes
- Use `PascalCase`
- Descriptive names indicating purpose
- Suffix with type when appropriate

**Examples:**
```python
class FilterMateApp:
class FilterEngineTask(QgsTask):
class LayerStateManager:
class PostgreSQLBackend(BaseBackend):
class UIConfig:
class SourceGeometryCache:  # NEW Phase 3a
```

### Functions and Methods
- Use `snake_case`
- Verb-based names for actions
- Noun-based names for getters
- Private methods prefix with `_`

**Examples:**
```python
def manage_task(task_type, params):
def get_datasource_connexion_from_layer(layer):
def apply_subset_filter(layer_id, expression):
def _internal_method():  # Private
def _on_config_item_changed(item):  # Signal handler (private)
def spatialite_connect(db_path):  # Utility function (Phase 3a)
```

### Constants
- Use `UPPER_SNAKE_CASE`
- Group related constants
- Document purpose in comments

**Examples:**
```python
POSTGRESQL_AVAILABLE = True
DEFAULT_BUFFER_DISTANCE = 0
MAX_RETRY_ATTEMPTS = 5
SPATIAL_INDEX_THRESHOLD = 50000
SQLITE_TIMEOUT = 30  # NEW Phase 3a
SQLITE_MAX_RETRIES = 5  # NEW Phase 3a
```

### Variables
- Use `snake_case`
- Descriptive names
- Avoid single-letter names (except loop counters)

**Examples:**
```python
layer_provider_type = 'postgresql'
buffer_distance = 100
selected_feature_ids = [1, 2, 3]
geometry_cache = SourceGeometryCache()  # Phase 3a
```

## Critical Patterns

### 1. PostgreSQL Availability Check

**ALWAYS** check `POSTGRESQL_AVAILABLE` before using PostgreSQL-specific code:

```python
from adapters.backends.postgresql_availability import POSTGRESQL_AVAILABLE

if POSTGRESQL_AVAILABLE and provider_type == 'postgresql':
    # PostgreSQL-specific code
    import psycopg2
    connexion = psycopg2.connect(...)
else:
    # Fallback to Spatialite or OGR
    pass
```

**Location v4.0:** `adapters/backends/postgresql_availability.py`
```python
try:
    import psycopg2
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
```

### 2. Provider Type Detection

Use this pattern consistently across the codebase:

```python
provider = layer.providerType()

if provider == 'postgres':
    layer_provider_type = 'postgresql'
elif provider == 'spatialite':
    layer_provider_type = 'spatialite'
elif provider == 'ogr':
    layer_provider_type = 'ogr'
else:
    layer_provider_type = 'unknown'
```

**Note:** QGIS returns `'postgres'` but we normalize to `'postgresql'`

### 3. Configuration Value Access (v2.2.2+)

Always use config helpers for ChoicesType support:

```python
from modules.config_helpers import get_config_value, set_config_value

# CORRECT: Extracts value from ChoicesType
ui_profile = get_config_value('UI_PROFILE')  # Returns 'auto', not {'value': 'auto', ...}

# INCORRECT: Direct access doesn't handle ChoicesType
ui_profile = ENV_VARS['UI_PROFILE']  # May return dict instead of string
```

**Key Functions:**
```python
get_config_value(key, default=None)      # Read with ChoicesType extraction
set_config_value(key, value)             # Write with validation
get_config_choices(key)                  # Get available choices
validate_config_value(key, value)        # Validate before setting
is_choices_type(value)                   # Check if value is ChoicesType format
```

### 4. Spatialite Database Connections (Phase 3a Updated)

**NEW**: Use `spatialite_connect()` from `modules/tasks/task_utils.py`:

```python
from modules.tasks.task_utils import spatialite_connect

# Use context manager for automatic cleanup
with spatialite_connect(db_path) as conn:
    cursor = conn.cursor()
    cursor.execute(sql_statement)
    result = cursor.fetchall()
    conn.commit()
    # Connection automatically closed
```

**Old Pattern (still works but prefer new):**
```python
import sqlite3

conn = None
try:
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    try:
        conn.load_extension('mod_spatialite')
    except sqlite3.OperationalError:
        conn.load_extension('mod_spatialite.dll')  # Windows fallback
    
    cursor = conn.cursor()
    cursor.execute(sql_statement)
    result = cursor.fetchall()
    conn.commit()
    return result
    
finally:
    if conn:
        conn.close()
```

**Critical:** Always use try/finally for connection cleanup or use the new utility function

### 5. SQLite Lock Handling (Phase 3a - v2.3.0-alpha)

**NEW**: Use `sqlite_execute_with_retry()` from `modules/tasks/task_utils.py`:

```python
from modules.tasks.task_utils import sqlite_execute_with_retry

def safe_operation(db_path, sql_statement):
    def operation(conn):
        cursor = conn.cursor()
        cursor.execute(sql_statement)
        return cursor.fetchall()
    
    # Automatic retry with exponential backoff
    result = sqlite_execute_with_retry(db_path, operation)
    return result
```

**Implementation Details:**
- Max 5 retry attempts
- Exponential backoff: 0.1s, 0.2s, 0.4s, 0.8s, 1.6s
- Automatic database lock detection
- WAL mode enabled for better concurrency

**Old Pattern (manual retry - avoid):**
```python
max_retries = 5
for attempt in range(max_retries):
    try:
        conn = sqlite3.connect(db_path)
        # operation
        break
    except sqlite3.OperationalError as e:
        if "locked" in str(e) and attempt < max_retries - 1:
            time.sleep(0.1 * (2 ** attempt))
        else:
            raise
```

### 6. Field Name Quoting (v2.2.4 CRITICAL)

**ALWAYS preserve field name quotes** for case-sensitive fields:

```python
# CORRECT: Preserves quotes
def convert_expression(expr):
    # Don't strip quotes around field names
    # "HOMECOUNT" > 100 must stay quoted
    return expr

# INCORRECT: Removes quotes (BUG in pre-v2.2.4)
def convert_expression_wrong(expr):
    return expr.replace('"', '')  # DON'T DO THIS
```

**Test Case:**
```python
# Must pass this test
def test_field_name_quotes_preserved():
    expr = '"HOMECOUNT" > 100'
    converted = qgis_expression_to_spatialite(expr)
    assert '"HOMECOUNT"' in converted
```

### 7. CRS Utilities (v2.5.7 - NEW MODULE)

**Use the new `crs_utils` module** for CRS operations:

```python
from modules.crs_utils import (
    is_geographic_crs,
    is_metric_crs,
    get_optimal_metric_crs,
    CRSTransformer,
    calculate_utm_zone
)

# Check CRS type
if is_geographic_crs(layer.crs()):
    # Convert to metric for buffer operations
    metric_crs = get_optimal_metric_crs(layer.extent(), layer.crs())
    
# Use CRSTransformer for geometry operations
transformer = CRSTransformer(source_crs, target_crs, project)
transformed_geom = transformer.transform(geometry)
```

**Key Functions:**
- `is_geographic_crs(crs)`: Returns True for lat/lon coordinate systems
- `is_metric_crs(crs)`: Returns True for projected metric CRS
- `get_optimal_metric_crs(extent, source_crs)`: Returns best UTM zone or EPSG:3857
- `calculate_utm_zone(extent)`: Calculate optimal UTM zone from extent

### 8. Geographic CRS Handling (v2.2.5 CRITICAL)

**NEW**: Automatic EPSG:3857 conversion for geographic coordinate systems:

```python
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform

def buffer_operation(layer, buffer_distance):
    layer_crs = layer.crs()
    
    # Check if geographic CRS (lat/lon)
    if layer_crs.isGeographic() and buffer_distance > 0:
        # Auto-convert to metric CRS for accurate buffer
        work_crs = QgsCoordinateReferenceSystem("EPSG:3857")
        transform = QgsCoordinateTransform(layer_crs, work_crs, project)
        
        # Transform geometry to metric CRS
        geom = QgsGeometry(feature.geometry())  # COPY!
        geom.transform(transform)
        
        # Apply buffer in meters
        buffered = geom.buffer(buffer_distance, 5)
        
        # Transform back to original CRS
        inverse_transform = QgsCoordinateTransform(work_crs, layer_crs, project)
        buffered.transform(inverse_transform)
        
        return buffered
    else:
        # Already metric or no buffer needed
        return feature.geometry().buffer(buffer_distance, 5)
```

**Key Points:**
- Always use `QgsGeometry()` copy constructor
- Never modify geometry in-place
- Log CRS conversions with 🌍 indicator
- Minimal overhead (~1ms per feature)

### 8. Geometry Caching (Phase 3a - v2.3.0-alpha)

**NEW**: Use `SourceGeometryCache` for multi-layer operations:

```python
from modules.tasks.geometry_cache import SourceGeometryCache

# Create cache instance
cache = SourceGeometryCache()

# Cache key: (feature_ids, buffer_value, target_crs)
cache_key = (frozenset(feature_ids), buffer_distance, target_crs_authid)

# Try to get from cache
cached_geom = cache.get(cache_key)

if cached_geom is not None:
    # Cache hit - reuse geometry
    source_geom = cached_geom
else:
    # Cache miss - compute and store
    source_geom = compute_source_geometry(features, buffer_distance, target_crs)
    cache.put(cache_key, source_geom)

# Clear cache when done
cache.clear()
```

**Benefits:**
- 5× speedup for multi-layer filtering
- FIFO eviction (max 10 entries)
- Automatic cache invalidation

### 9. QGIS Task Pattern

For asynchronous operations, inherit from `QgsTask`:

```python
from qgis.core import QgsTask

class MyTask(QgsTask):
    def __init__(self, description, task_parameters):
        super().__init__(description, QgsTask.CanCancel)
        self.task_parameters = task_parameters
        self.result_data = None
        self.exception = None
    
    def run(self):
        """Execute in background thread."""
        try:
            # Heavy processing here
            self.result_data = self._do_work()
            return True
            
        except Exception as e:
            self.exception = e
            return False
    
    def finished(self, result):
        """Execute in main thread after run()."""
        if result and self.result_data:
            # Success: Update UI
            self._handle_success()
        else:
            # Error: Show message
            self._handle_error()
    
    def cancel(self):
        """Handle cancellation."""
        super().cancel()
        # Cleanup resources
```

**Key Points:**
- `run()` executes in background thread (no UI access)
- `finished()` executes in main thread (can update UI)
- Always handle exceptions in `run()`
- Store results in instance variables

### 10. Signal Blocking Pattern (v2.1.0+)

Use `SignalBlocker` for batch UI updates:

```python
from modules.signal_utils import SignalBlocker, SignalBlockerGroup

# Single widget
with SignalBlocker(widget):
    widget.setValue(new_value)
    # No signal emitted

# Multiple widgets
widgets = [combobox1, combobox2, lineedit]
with SignalBlockerGroup(widgets):
    for widget, value in zip(widgets, values):
        widget.setValue(value)
# One update signal after all changes
```

**Benefits:**
- Prevents cascade updates
- Reduces UI flicker
- Improves performance

### 11. Canvas Refresh for Complex Filters (v2.5.19-v2.5.20)

**For PostgreSQL/Spatialite/OGR backends with complex spatial filters:**

```python
from qgis.PyQt.QtCore import QTimer

def _delayed_canvas_refresh(self, layer, filter_expression):
    """Delayed refresh for complex filter expressions."""
    
    def do_refresh():
        # Check if layer still valid
        if not layer or not layer.isValid():
            return
            
        # Detect complex filters that need aggressive refresh
        needs_aggressive = self._is_complex_filter(filter_expression, layer.providerType())
        
        if needs_aggressive:
            # Force data provider reload
            layer.dataProvider().reloadData()
            layer.updateExtents()
        
        layer.triggerRepaint()
        iface.mapCanvas().refresh()
    
    # Schedule delayed refresh
    QTimer.singleShot(800, do_refresh)
    
    # Schedule final refresh for reliability
    QTimer.singleShot(2000, self._final_canvas_refresh)

def _is_complex_filter(self, expr, provider_type):
    """Detect filters that need aggressive refresh."""
    expr_upper = expr.upper()
    
    if provider_type == 'postgres':
        return any(p in expr_upper for p in ['EXISTS', 'ST_BUFFER', '__SOURCE'])
    elif provider_type == 'spatialite':
        return any(p in expr_upper for p in ['ST_', 'INTERSECTS(', 'CONTAINS(', 'WITHIN('])
    elif provider_type == 'ogr':
        # Large IN clauses from selectbylocation fallback
        return expr.count(',') > 50
    return False
```

**Key Points:**
- Use 800ms initial delay for provider sync
- Use 2000ms final delay for reliability
- Force `dataProvider().reloadData()` for complex filters
- Always call `updateExtents()` after data changes

### 12. WCAG Color Contrast (v2.2.3+)

When defining colors, ensure WCAG compliance:

```python
# Text colors (must meet WCAG standards)
PRIMARY_TEXT = "#1A1A1A"    # Contrast: 17.4:1 (AAA)
SECONDARY_TEXT = "#4A4A4A"  # Contrast: 8.86:1 (AAA)
DISABLED_TEXT = "#888888"   # Contrast: 4.6:1 (AA)

# Background colors (must have visible separation)
FRAME_BG = "#EFEFEF"       # Dark enough to contrast with white
WIDGET_BG = "#FFFFFF"      # White (maximum contrast)
BORDER = "#D0D0D0"         # 40% darker than previous

# Calculate contrast ratio
def calculate_contrast(color1, color2):
    # Implementation per WCAG 2.1 standard
    pass

# Validate contrast
assert calculate_contrast(PRIMARY_TEXT, WIDGET_BG) >= 7.0  # AAA
```

**Test File:** `tests/test_color_contrast.py`

### 13. Progressive Filtering (v2.5.9 - PostgreSQL Optimization)

**For complex PostgreSQL queries, use the progressive filtering system:**

```python
from modules.tasks.query_complexity_estimator import QueryComplexityEstimator
from modules.tasks.progressive_filter import (
    ProgressiveFilterExecutor, LazyResultIterator, TwoPhaseFilter
)

# Estimate query complexity
estimator = QueryComplexityEstimator()
result = estimator.estimate_complexity(sql_expression)

print(f"Score: {result.total_score}")           # e.g., 185
print(f"Strategy: {result.recommended_strategy}")  # e.g., "TWO_PHASE"

# Execute with appropriate strategy
executor = ProgressiveFilterExecutor(connection, query_cache)
filter_result = executor.filter_with_strategy(
    layer_props=layer_props,
    source_geometry=source_geom,
    buffer_value=buffer_value,
    predicates=predicates,
    feature_count=layer.featureCount(),
    complexity_score=result.total_score
)

# For very large datasets (> 50k features), use lazy cursor
with LazyResultIterator(connection, sql_query, chunk_size=5000) as iterator:
    for batch in iterator:
        process_batch(batch)  # Yields chunks of IDs
```

**Strategy Thresholds:**
- `score < 50`: DIRECT - Simple query, standard execution
- `50 ≤ score < 150`: MATERIALIZED - Use materialized view
- `150 ≤ score < 500`: TWO_PHASE - Bbox pre-filter + full predicate
- `score ≥ 500`: PROGRESSIVE - Lazy cursor streaming

**Operation Costs (for complexity estimation):**
| Operation | Cost | Reason |
|-----------|------|--------|
| ST_Buffer | 12 | Creates new geometry |
| ST_Transform | 10 | Coordinate reprojection |
| ST_Intersects | 5 | Can use GIST index |
| EXISTS | 20 | Subquery execution |
| IN (subquery) | 15 | Subquery + lookup |

## Backend Implementation Patterns

### Backend Selection via Factory

```python
from modules.backends.factory import BackendFactory

def filter_operation(layer, params):
    # Get appropriate backend automatically
    backend = BackendFactory.get_backend(layer)
    
    try:
        # Execute operation
        result = backend.execute_filter(params)
        return result
        
    finally:
        # Always cleanup
        backend.cleanup()
```

### Backend Interface Implementation

When creating a new backend:

```python
from modules.backends.base_backend import BaseBackend

class MyBackend(BaseBackend):
    """Custom backend implementation."""
    
    def __init__(self, layer):
        super().__init__(layer)
        self.connection = None
    
    def execute_filter(self, expression, predicates, buffer_distance):
        """Implement filtering logic."""
        # Backend-specific implementation
        pass
    
    def get_feature_count(self):
        """Return filtered feature count."""
        pass
    
    def create_export_layer(self, output_path, selected_fields):
        """Export filtered features."""
        pass
    
    def cleanup(self):
        """Clean up resources."""
        if self.connection:
            self.connection.close()
```

## Error Handling Patterns

### Exception Handling (Phase 2 - 100% Complete)

**NEVER use bare except** - always specify exception types:

```python
# ❌ BAD: Bare except
try:
    operation()
except:  # Don't do this
    pass

# ✅ GOOD: Specific exceptions
try:
    operation()
except (OSError, PermissionError) as e:
    logger.error(f"File operation failed: {e}")
except ValueError as e:
    logger.error(f"Invalid value: {e}")
except Exception as e:
    logger.error(f"Unexpected error: {e}")
```

**Common Exception Types:**
- `ImportError, AttributeError`: Dynamic imports
- `OSError, PermissionError`: File operations
- `ValueError, IndexError`: Parsing/conversions
- `KeyError`: Dictionary access
- `RuntimeError`: Geometry operations
- `sqlite3.OperationalError`: Database operations

### Custom Exceptions

Use custom exceptions from `modules/customExceptions.py`:

```python
from modules.customExceptions import (
    FilterMateException,
    DatabaseConnectionError,
    GeometryError,
    BackendError
)

def risky_operation():
    try:
        result = database_operation()
        
    except psycopg2.Error as e:
        raise DatabaseConnectionError(f"Failed to connect: {e}")
        
    except Exception as e:
        raise FilterMateException(f"Unexpected error: {e}")
```

### User Feedback

Use feedback utilities for user-facing messages:

```python
from modules.feedback_utils import (
    show_info,
    show_warning,
    show_error,
    show_success
)

# Success message
show_success("Filter applied successfully")

# Info message (3 second duration)
show_info("Using Spatialite backend", duration=3)

# Warning with duration (positional argument)
show_warning(
    "Large dataset detected. Performance may be reduced.",
    10  # Duration in seconds (positional, not keyword!)
)

# Error message
show_error(f"Failed to apply filter: {error}")
```

**IMPORTANT:** Duration is a **positional argument**, not a keyword argument:
```python
# CORRECT
show_warning("Message", 10)

# INCORRECT
show_warning("Message", duration=10)  # Will cause error
```

### Geometry Repair Pattern

```python
from modules.appUtils import repair_geometry

def geometry_operation(geometry):
    try:
        # Try operation
        result = process_geometry(geometry)
        return result
        
    except GeometryError:
        # Attempt repair
        repaired = repair_geometry(geometry)
        result = process_geometry(repaired)
        return result
```

## Documentation Patterns

### Function Docstrings

```python
def my_function(param1, param2, optional_param=None):
    """
    Brief description of function purpose.
    
    Longer description if needed. Explain the purpose,
    any important details, or caveats.
    
    Args:
        param1 (type): Description of param1
        param2 (type): Description of param2
        optional_param (type, optional): Description. Defaults to None.
    
    Returns:
        type: Description of return value
    
    Raises:
        ExceptionType: When this exception occurs
    
    Example:
        >>> result = my_function('value1', 'value2')
        >>> print(result)
    """
    pass
```

### Class Docstrings

```python
class MyClass:
    """
    Brief description of class purpose.
    
    Longer description of the class functionality,
    its role in the system, and usage patterns.
    
    Attributes:
        attribute1 (type): Description of attribute1
        attribute2 (type): Description of attribute2
    
    Example:
        >>> obj = MyClass(param)
        >>> obj.method()
    """
    
    def __init__(self, param):
        """
        Initialize MyClass.
        
        Args:
            param (type): Description
        """
        self.attribute1 = param
```

### Inline Comments

```python
# GOOD: Explain WHY, not WHAT
# Use exponential backoff to avoid overwhelming the database
time.sleep(0.1 * (2 ** attempt))

# BAD: States the obvious
# Sleep for exponentially increasing time
time.sleep(0.1 * (2 ** attempt))
```

### TODO and FIXME Comments

```python
# TODO: Implement caching for repeated queries (Phase 3)
# TODO v2.3: Add support for custom backends

# FIXME: Handle edge case with empty geometries
# FIXME: Race condition possible with rapid layer switching
```

## Performance Patterns

### Large Dataset Warnings

```python
def check_performance(layer):
    feature_count = layer.featureCount()
    
    if feature_count > 50000 and not POSTGRESQL_AVAILABLE:
        show_warning(
            f"Large dataset ({feature_count:,} features) without PostgreSQL. "
            "Performance may be reduced. Consider installing psycopg2.",
            10
        )
```

### Spatial Index Automation

```python
def ensure_spatial_index(layer_path):
    """Create spatial index if it doesn't exist."""
    index_path = layer_path + '.qix'
    
    if not os.path.exists(index_path):
        # Create index
        processing.run("native:createspatialindex", {
            'INPUT': layer_path
        })
```

### Geometry Caching (Phase 3a NEW)

```python
from modules.tasks.geometry_cache import SourceGeometryCache

class GeometryProcessor:
    def __init__(self):
        self.cache = SourceGeometryCache()
    
    def process_with_cache(self, feature_ids, buffer_val, target_crs):
        cache_key = (frozenset(feature_ids), buffer_val, target_crs.authid())
        
        # Try cache first
        cached = self.cache.get(cache_key)
        if cached:
            return cached
        
        # Compute and cache
        result = self._compute_geometry(feature_ids, buffer_val, target_crs)
        self.cache.put(cache_key, result)
        return result
    
    def cleanup(self):
        self.cache.clear()
```

## Testing Patterns

### Unit Test Structure

```python
import pytest
from unittest.mock import Mock, patch

class TestMyFeature:
    """Tests for MyFeature functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_data = create_test_data()
    
    def teardown_method(self):
        """Clean up after tests."""
        cleanup_test_data()
    
    def test_basic_functionality(self):
        """Test basic functionality."""
        result = my_function(self.test_data)
        assert result is not None
        assert isinstance(result, ExpectedType)
    
    @pytest.mark.slow
    def test_performance(self):
        """Test performance with large dataset."""
        # Performance test implementation
        pass
    
    @pytest.mark.skipif(not POSTGRESQL_AVAILABLE, reason="PostgreSQL not available")
    def test_postgresql_specific(self):
        """Test PostgreSQL-specific functionality."""
        # PostgreSQL test implementation
        pass
```

### Mocking QGIS Dependencies

```python
@patch('qgis.core.QgsVectorLayer')
def test_with_mock_layer(mock_layer_class):
    """Test with mocked QGIS layer."""
    mock_layer = Mock()
    mock_layer.providerType.return_value = 'postgres'
    mock_layer.featureCount.return_value = 1000
    
    mock_layer_class.return_value = mock_layer
    
    # Test implementation
    result = function_using_layer(mock_layer)
    assert result == expected_value
```

## Git Commit Messages

Follow conventional commits format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Test additions/changes
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `style`: Code style changes (formatting)
- `chore`: Build/tooling changes

**Examples:**
```
feat(backends): Add Spatialite backend support

Implemented Spatialite backend with R-tree indexes and temporary
geometry tables for improved performance on medium-sized datasets.

Closes #42

---

refactor: Phase 3a - Extract utilities and cache from appTasks.py

Extracted 474 lines of common utilities to new modules/tasks/ directory:
- task_utils.py: Database connections, CRS helpers (328 lines)
- geometry_cache.py: SourceGeometryCache for 5× speedup (146 lines)
- __init__.py: Backwards-compatible re-exports (67 lines)

Zero breaking changes. All existing imports continue to work.

---

fix(spatialite): Preserve field name quotes in expressions

Fixed critical bug where double quotes around field names were
incorrectly removed during expression conversion, causing filters
to fail on case-sensitive fields.

Fixes #156

---

style(pep8): replace != None with is not None

Updated 27 instances across filter_mate_app.py and 
filter_mate_dockwidget.py for PEP 8 compliance.
```

## Code Review Checklist

Before submitting code:

- [ ] Follows PEP 8 style guide (95% compliance target)
- [ ] Has descriptive function/class names
- [ ] Includes docstrings for public functions
- [ ] Checks `POSTGRESQL_AVAILABLE` before PostgreSQL operations
- [ ] Uses config helpers for configuration access
- [ ] Preserves field name quotes (v2.2.4 critical)
- [ ] Implements proper error handling (no bare except)
- [ ] Uses `is not None` instead of `!= None`
- [ ] No wildcard imports (except legitimate re-exports)
- [ ] Includes user feedback for operations
- [ ] Has unit tests for new functionality
- [ ] Updates documentation
- [ ] Follows existing patterns in codebase
- [ ] No hardcoded values (use constants)
- [ ] Proper resource cleanup (connections, files)
- [ ] Meets WCAG color contrast requirements (UI changes)
- [ ] Tests geographic CRS handling (v2.2.5)
- [ ] Uses geometry cache for multi-layer ops (Phase 3a)

## Common Pitfalls to Avoid

❌ **DON'T** import psycopg2 directly without try/except
✅ **DO** use the `POSTGRESQL_AVAILABLE` flag

❌ **DON'T** assume PostgreSQL is available
✅ **DO** provide Spatialite/OGR fallback

❌ **DON'T** use blocking operations in main thread
✅ **DO** use QgsTask for heavy operations

❌ **DON'T** forget to close database connections
✅ **DO** use try/finally or `spatialite_connect()` context manager (Phase 3a)

❌ **DON'T** access ENV_VARS directly for ChoicesType fields
✅ **DO** use `get_config_value()` from config_helpers

❌ **DON'T** strip quotes from field names in expressions
✅ **DO** preserve field name quotes for case sensitivity

❌ **DON'T** use `duration=X` for message bar (keyword argument)
✅ **DO** use `show_warning("msg", 10)` (positional argument)

❌ **DON'T** define colors without checking WCAG contrast
✅ **DO** validate contrast ratios meet AA/AAA standards

❌ **DON'T** read entire files when using Serena
✅ **DO** use `get_symbols_overview()` and symbolic tools

❌ **DON'T** use wildcard imports
✅ **DO** use explicit imports (Phase 2 requirement)

❌ **DON'T** use bare except clauses
✅ **DO** specify exception types (Phase 2 requirement)

❌ **DON'T** use `!= None` comparisons
✅ **DO** use `is not None` (PEP 8)

❌ **DON'T** modify geometry in-place
✅ **DO** use `QgsGeometry()` copy constructor (v2.2.5)

❌ **DON'T** assume buffer values are in correct units
✅ **DO** check geographic CRS and convert to EPSG:3857 (v2.2.5)

❌ **DON'T** rely on `triggerRepaint()` alone for complex filters
✅ **DO** use `dataProvider().reloadData()` + delayed refresh (v2.5.19)

❌ **DON'T** run complex PostgreSQL queries without complexity estimation
✅ **DO** use `QueryComplexityEstimator` for strategy selection (v2.5.9)

❌ **DON'T** load all results at once for large PostgreSQL datasets
✅ **DO** use `LazyResultIterator` for > 50k features (v2.5.9)

## Version-Specific Patterns

### v2.9.6 (Current - January 2026)
- **MakeValid geometry**: All source geometries wrapped in `MakeValid()`/`ST_MakeValid()`
- **Spatialite geometry fix**: Invalid source geometries now handled automatically
- **Range-based filter**: Use `_build_range_based_filter()` instead of FID subquery

### v2.9.x (January 2026)
- **ST_PointOnSurface**: Use for accurate polygon centroids (`CENTROID_MODE_DEFAULT = 'point_on_surface'`)
- **Adaptive simplification**: Auto-simplify before buffer (`SIMPLIFY_BEFORE_BUFFER_ENABLED = True`)
- **PostgreSQL MV optimizations**: INCLUDE clause, bbox column, async CLUSTER
- **psycopg2 centralization**: Use `modules/psycopg2_availability.py` for all imports

### v2.8.x (January 2026)
- **Complex expression materialization**: `_has_expensive_spatial_expression()` auto-detects
- **Safe shutdown**: Task `cancel()` uses Python logger, not QgsMessageLog

### v2.5.20 (December 2025)
- **Multi-backend canvas refresh**: Use `_delayed_canvas_refresh()` with pattern detection
- **Spatialite/OGR refresh**: Detect complex filters and force `dataProvider().reloadData()`
- **Double-pass refresh**: 800ms + 2000ms for guaranteed display

### v2.5.9+ (Production)
- **Progressive filtering**: Use `QueryComplexityEstimator` for PostgreSQL
- **Lazy cursors**: Use `LazyResultIterator` for > 50k features
- **Two-phase filtering**: Bbox pre-filter for complex expressions
- **Enhanced cache**: TTL support, result count caching

### v2.5.7+ (Production)
- **CRS utilities**: Use `modules/crs_utils.py` for CRS operations
- **Automatic metric conversion**: Use `get_optimal_metric_crs()` for buffers

### v2.5.6+ (Production)
- **Bidirectional sync**: Widgets ↔ QGIS selection with anti-loop protection
- **Complete sync**: Check AND uncheck based on selection state

### v2.3.0-alpha (Phase 5a Complete)
- **Task Module**: Import utilities from `modules/tasks/task_utils.py`
- **Geometry Cache**: Use `SourceGeometryCache` for multi-layer operations
- **Layer Management**: `LayersManagementEngineTask` now in separate file
- **Backwards Compatibility**: All imports via `modules/tasks/__init__.py` still work
- **Method Extraction**: 12 helper methods in filter_mate_app.py following `_verb_noun` pattern
- **Refactoring Achievement**: 40% complexity reduction (779→468 lines in core methods)

### v2.2.5+ (Production)
- **Geographic CRS**: Auto-convert to EPSG:3857 for metric operations
- **Geometry Copy**: Always use `QgsGeometry()` constructor, never modify in-place
- **CRS Logging**: Use 🌍 indicator for geographic conversions

### v2.2.4+ (Production)
- **Field name quotes**: Must be preserved in all expression conversions
- **Test coverage**: Add tests for case-sensitive field handling

### v2.2.3+ (Production)
- **Color definitions**: Must meet WCAG 2.1 AA/AAA standards
- **Contrast validation**: Use automated tests

### v2.2.2+ (Production)
- **Configuration access**: Use config_helpers, not direct ENV_VARS
- **ChoicesType**: Implement dropdown support for new config fields

### v2.1.0+ (Production)
- **Backend operations**: Use factory pattern for backend selection
- **Signal management**: Use SignalBlocker utilities
- **SQLite operations**: Implement retry mechanism for locks

## Serena MCP Integration

### Efficient Code Reading
- **Use `get_symbols_overview()`** before reading large files
- **Use `find_symbol()`** for targeted symbol reads
- **Avoid `read_file()`** for entire source files (token inefficient)
- **Use `search_for_pattern()`** when symbol name/location uncertain

### Symbolic Tools (Phase 3+)
```python
# Get overview of file symbols
get_symbols_overview('modules/appTasks.py')

# Find specific symbol
find_symbol(name_path='FilterEngineTask/run', include_body=True)

# Search for pattern
search_for_pattern('spatialite_connect', relative_path='modules/tasks/')
```

### Memory Management
- Read relevant memories at conversation start
- Update memories after significant changes
- Check `.serena/` directory for project-specific configuration

## Phase 3 Refactoring Guidelines (v2.3.0-alpha)

### Module Extraction Pattern
When extracting code from large files:

1. **Identify cohesive units** (utilities, classes, related functions)
2. **Create new module** in appropriate directory
3. **Move code** with minimal modifications
4. **Add backwards-compatible imports** in `__init__.py`
5. **Update documentation** (README.md in module directory)
6. **Test thoroughly** (ensure zero breaking changes)
7. **Commit atomically** with descriptive message

### Phase 5a Method Extraction Pattern (NEW - December 2025)
When refactoring large methods (>140 lines):

1. **Identify logical sections** within method
2. **Extract as private helper methods** with `_verb_noun` naming
3. **Add complete docstrings** with Args/Returns sections
4. **Maintain call order** and data flow
5. **Validate syntax** with `python -m py_compile`
6. **Test thoroughly** (ensure zero regressions)
7. **Document metrics** (lines before/after, % reduction)
8. **Commit incrementally** (one method at a time)

**Example: init_filterMate_db() Refactoring**
```python
# BEFORE (227 lines)
def init_filterMate_db(self):
    # Database directory creation logic (20 lines)
    # File creation logic (25 lines)
    # Schema initialization (35 lines)
    # Migration logic (40 lines)
    # Project loading (50 lines)
    # Additional initialization (57 lines)
    pass

# AFTER (103 lines + 5 helpers)
def init_filterMate_db(self):
    \"\"\"Initialize or load FilterMate database.\"\"\"
    self._ensure_db_directory()
    self._create_db_file()
    self._initialize_schema()
    self._migrate_schema_if_needed()
    return self._load_or_create_project()

def _ensure_db_directory(self):
    \"\"\"Ensure database directory exists.\"\"\"
    # 20 lines

def _create_db_file(self):
    \"\"\"Create database file if it doesn't exist.\"\"\"
    # 25 lines

# etc...
```

**Benefits:**
- ✅ -55% complexity (227→103 lines)
- ✅ Each helper has single responsibility
- ✅ Easier to test individual steps
- ✅ Better code organization
- ✅ Improved maintainability

### Example: Task Utilities Extraction (Phase 3a)
```python
# OLD: modules/appTasks.py (lines scattered throughout 5678 lines)
def spatialite_connect(db_path):
    # Implementation
    pass

class SourceGeometryCache:
    # Implementation
    pass

# NEW: modules/tasks/task_utils.py (328 lines, focused)
def spatialite_connect(db_path):
    # Implementation (same)
    pass

# NEW: modules/tasks/geometry_cache.py (146 lines, focused)
class SourceGeometryCache:
    # Implementation (same)
    pass

# NEW: modules/tasks/__init__.py (backwards compatibility)
from .task_utils import spatialite_connect
from .geometry_cache import SourceGeometryCache
# Legacy imports still work!
```

### Benefits of Extraction
- ✅ Better organization and discoverability
- ✅ Easier testing (isolated units)
- ✅ Reduced file size (improved readability)
- ✅ Clearer dependencies
- ✅ Maintained backwards compatibility

## Next Steps

### Planned Improvements
- **Phase 3c**: Extract remaining tasks from appTasks.py (FilterEngineTask, etc.)
- **Phase 4**: Decompose filter_mate_dockwidget.py (~3877 lines) into UI components
- **Phase 5**: Additional testing and documentation
- **Phase 6**: Performance optimization and final polish
