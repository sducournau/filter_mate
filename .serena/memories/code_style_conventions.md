# Code Style Conventions - FilterMate

## Python Standards

### PEP 8 Compliance
- Follow PEP 8 conventions strictly
- Use 4 spaces for indentation (no tabs)
- Maximum line length: 120 characters
- Use docstrings for all classes and functions
- Type hints encouraged but not required (QGIS compatibility)

### Import Order
1. Standard library imports
2. Third-party imports (QGIS, PyQt5)
3. Local application imports

**Example:**
```python
import os
import sys
from typing import Optional, Dict, List

from qgis.core import QgsVectorLayer, QgsProject
from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import QWidget

from .config.config import ENV_VARS
from .modules.appUtils import get_datasource_connexion_from_layer
from .modules.config_helpers import get_config_value
```

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
```

## Critical Patterns

### 1. PostgreSQL Availability Check

**ALWAYS** check `POSTGRESQL_AVAILABLE` before using PostgreSQL-specific code:

```python
from modules.appUtils import POSTGRESQL_AVAILABLE

if POSTGRESQL_AVAILABLE and provider_type == 'postgresql':
    # PostgreSQL-specific code
    import psycopg2
    connexion = psycopg2.connect(...)
else:
    # Fallback to Spatialite or OGR
    pass
```

**Location:** `modules/appUtils.py` (top of file)
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

### 4. Spatialite Database Connections

Use this pattern for Spatialite operations:

```python
import sqlite3

def spatialite_operation(db_path, sql_statement):
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

**Critical:** Always use try/finally for connection cleanup

### 5. SQLite Lock Handling (v2.1.0+)

Implement retry mechanism for locked databases:

```python
def safe_sqlite_operation(db_path, operation):
    max_retries = 5
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(db_path)
            result = operation(conn)
            return result
            
        except sqlite3.OperationalError as e:
            if "locked" in str(e) and attempt < max_retries - 1:
                time.sleep(0.1 * (2 ** attempt))  # Exponential backoff
                continue
            else:
                raise
        finally:
            if conn:
                conn.close()
```

### 6. Field Name Quoting (v2.2.4 Critical)

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

### 7. QGIS Task Pattern

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

### 8. Signal Blocking Pattern (v2.1.0+)

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

### 9. WCAG Color Contrast (v2.2.3+)

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
        # Operation that might fail
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

### Geometry Caching

```python
class GeometryCache:
    """Cache geometries for reuse."""
    
    def __init__(self):
        self._cache = {}
    
    def get_or_load(self, feature_id, loader_func):
        if feature_id not in self._cache:
            self._cache[feature_id] = loader_func(feature_id)
        return self._cache[feature_id]
    
    def clear(self):
        self._cache.clear()
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

fix(spatialite): Preserve field name quotes in expressions

Fixed critical bug where double quotes around field names were
incorrectly removed during expression conversion, causing filters
to fail on case-sensitive fields.

Fixes #156

---

docs(color): Add WCAG compliance documentation

Added comprehensive documentation for color harmonization changes
and WCAG 2.1 accessibility compliance.

---

test(expressions): Add comprehensive quote preservation tests

Added test suite for Spatialite expression conversion with focus
on field name quote preservation for case-sensitive fields.

---

perf(ogr): Optimize spatial index creation

Improved OGR backend performance by 19× through automatic
spatial index creation and large dataset optimization.
```

## Code Review Checklist

Before submitting code:

- [ ] Follows PEP 8 style guide
- [ ] Has descriptive function/class names
- [ ] Includes docstrings for public functions
- [ ] Checks `POSTGRESQL_AVAILABLE` before PostgreSQL operations
- [ ] Uses config helpers for configuration access
- [ ] Preserves field name quotes (v2.2.4 critical)
- [ ] Implements proper error handling
- [ ] Includes user feedback for operations
- [ ] Has unit tests for new functionality
- [ ] Updates documentation
- [ ] Follows existing patterns in codebase
- [ ] No hardcoded values (use constants)
- [ ] Proper resource cleanup (connections, files)
- [ ] Meets WCAG color contrast requirements (UI changes)

## Common Pitfalls to Avoid

❌ **DON'T** import psycopg2 directly without try/except
✅ **DO** use the `POSTGRESQL_AVAILABLE` flag

❌ **DON'T** assume PostgreSQL is available
✅ **DO** provide Spatialite/OGR fallback

❌ **DON'T** use blocking operations in main thread
✅ **DO** use QgsTask for heavy operations

❌ **DON'T** forget to close database connections
✅ **DO** use try/finally or context managers

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

## Version-Specific Patterns

### v2.2.4+ (Current)
- **Field name quotes**: Must be preserved in all expression conversions
- **Test coverage**: Add tests for case-sensitive field handling

### v2.2.3+
- **Color definitions**: Must meet WCAG 2.1 AA/AAA standards
- **Contrast validation**: Use automated tests

### v2.2.2+
- **Configuration access**: Use config_helpers, not direct ENV_VARS
- **ChoicesType**: Implement dropdown support for new config fields

### v2.1.0+
- **Backend operations**: Use factory pattern for backend selection
- **Signal management**: Use SignalBlocker utilities
- **SQLite operations**: Implement retry mechanism for locks
