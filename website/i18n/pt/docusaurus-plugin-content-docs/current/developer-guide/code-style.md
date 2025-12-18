---
sidebar_position: 5
---

# Code Style Guide

Coding standards and best practices for FilterMate development.

## Python Standards

### PEP 8 Compliance

Follow [PEP 8](https://pep8.org/) conventions:

- **Line length:** Maximum 120 characters
- **Indentation:** 4 spaces (no tabs)
- **Blank lines:** 2 between top-level definitions
- **Encoding:** UTF-8

### Naming Conventions

#### Classes
```python
# PascalCase
class FilterMateApp:
    pass

class FilterEngineTask:
    pass
```

#### Functions and Methods
```python
# snake_case
def manage_task(task_type, parameters):
    pass

def get_datasource_connexion_from_layer(layer):
    pass
```

#### Constants
```python
# UPPER_SNAKE_CASE
POSTGRESQL_AVAILABLE = True
MAX_RETRIES = 5
DEFAULT_BUFFER_DISTANCE = 100
```

#### Private Methods
```python
# Prefix with underscore
def _internal_method(self):
    pass

def _validate_input(self, data):
    pass
```

### Import Organization

```python
# 1. Standard library
import os
import sys
from typing import Optional, List, Dict

# 2. Third-party (QGIS, PyQt)
from qgis.core import QgsVectorLayer, QgsProject
from qgis.PyQt.QtCore import Qt, pyqtSignal

# 3. Local application
from .config.config import ENV_VARS
from .modules.appUtils import get_datasource_connexion_from_layer
```

## Critical Patterns

### 1. PostgreSQL Availability Check

**ALWAYS** check before using PostgreSQL:

```python
from modules.appUtils import POSTGRESQL_AVAILABLE

if POSTGRESQL_AVAILABLE and provider_type == 'postgresql':
    # Safe to use psycopg2
    connexion = psycopg2.connect(...)
else:
    # Fallback to Spatialite or OGR
    pass
```

### 2. Provider Type Detection

```python
if layer.providerType() == 'postgres':
    layer_provider_type = 'postgresql'
elif layer.providerType() == 'spatialite':
    layer_provider_type = 'spatialite'
elif layer.providerType() == 'ogr':
    layer_provider_type = 'ogr'
else:
    layer_provider_type = 'unknown'
```

### 3. Signal Blocking

```python
from modules.signal_utils import SignalBlocker

with SignalBlocker(widget):
    # Signals blocked here
    widget.setValue(new_value)
# Signals automatically restored
```

### 4. Resource Management

```python
conn = None
try:
    conn = sqlite3.connect(db_path)
    # operations
    conn.commit()
finally:
    if conn:
        conn.close()
```

## Documentation

### Docstrings

```python
def my_function(param1, param2):
    """
    Brief description of function.
    
    Longer description if needed. Explain the purpose,
    any important details, or caveats.
    
    Args:
        param1 (type): Description
        param2 (type): Description
    
    Returns:
        type: Description of return value
    
    Raises:
        ExceptionType: When this happens
    """
    pass
```

### Comments

```python
# Explain WHY, not WHAT
if layer.featureCount() > 50000:
    # Large dataset: use PostgreSQL for better performance
    backend = PostgreSQLBackend(layer)

# TODO comments for future work
# TODO Phase 3: Implement result caching

# FIXME for known issues
# FIXME: Handle edge case with NULL geometries
```

## Error Handling

### User-Facing Errors

```python
from qgis.utils import iface

# Success (duration is positional argument)
iface.messageBar().pushSuccess(
    "FilterMate",
    "Filter applied successfully",
    3
)

# Warning
iface.messageBar().pushWarning(
    "FilterMate",
    f"Large dataset ({count} features). Consider PostgreSQL.",
    10
)

# Error
iface.messageBar().pushCritical(
    "FilterMate",
    f"Error: {str(error)}",
    5
)
```

### Exception Handling

```python
try:
    result = backend.execute_filter(...)
except DatabaseConnectionError as e:
    show_error(f"Cannot connect: {e}")
except GeometryError as e:
    # Attempt automatic repair
    repaired = repair_geometry(geom)
    result = backend.execute_filter(...)
except Exception as e:
    # Catch-all for unexpected errors
    logger.error(f"Unexpected error: {e}", exc_info=True)
    show_error(f"Operation failed: {e}")
```

## Performance

### Large Dataset Warnings

```python
if layer.featureCount() > 50000 and not POSTGRESQL_AVAILABLE:
    iface.messageBar().pushWarning(
        "FilterMate",
        f"Large dataset ({layer.featureCount()} features) "
        "without PostgreSQL. Performance may be reduced. "
        "Consider installing psycopg2.",
        duration=10
    )
```

### Lazy Evaluation

```python
# Good: Only load when needed
if need_features:
    features = list(layer.getFeatures())

# Avoid: Loading everything upfront
all_features = list(layer.getFeatures())
if need_features:
    # use all_features
```

## Testing

### Unit Test Structure

```python
import unittest
from unittest.mock import Mock, patch

class TestMyFeature(unittest.TestCase):
    def setUp(self):
        """Setup before each test."""
        self.layer = Mock(spec=QgsVectorLayer)
    
    def tearDown(self):
        """Cleanup after each test."""
        pass
    
    def test_something(self):
        """Test description."""
        # Arrange
        expected = True
        
        # Act
        result = my_function()
        
        # Assert
        self.assertEqual(result, expected)
```

## Git Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: Add Spatialite backend support
fix: Correct provider type detection for OGR layers
docs: Update README with installation instructions
test: Add unit tests for Phase 1
refactor: Extract common DB connection logic
perf: Optimize spatial index creation
style: Format code with black
chore: Update dependencies
```

## Common Anti-Patterns

### ❌ DON'T

```python
# Don't import psycopg2 directly
import psycopg2  # Will crash if not installed

# Don't assume PostgreSQL is available
conn = psycopg2.connect(...)  # May fail

# Don't use blocking operations in main thread
for i in range(1000000):
    process(i)  # UI freezes

# Don't forget to close connections
conn = sqlite3.connect(db)
# operations
# No cleanup!
```

### ✅ DO

```python
# Check availability
from modules.appUtils import POSTGRESQL_AVAILABLE
if POSTGRESQL_AVAILABLE:
    import psycopg2

# Provide fallback
if POSTGRESQL_AVAILABLE and provider == 'postgres':
    use_postgresql_backend()
else:
    use_spatialite_backend()

# Use QgsTask for heavy operations
task = FilterEngineTask(...)
QgsApplication.taskManager().addTask(task)

# Always cleanup
try:
    conn = sqlite3.connect(db)
    # operations
finally:
    if conn:
        conn.close()
```

## Code Review Checklist

Before submitting:

- [ ] Code follows PEP 8 style
- [ ] PostgreSQL availability checked where needed
- [ ] Error handling implemented
- [ ] Resources properly cleaned up
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] No debugging code left (print statements, etc.)

## Further Reading

- [Architecture Overview](./architecture)
- [Development Setup](./development-setup)
- [Contributing Guide](./contributing)
- [Testing Guide](./testing)
