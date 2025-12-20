# FilterMate - Quality Standards

## 📋 Document Info

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Last Updated** | December 20, 2025 |

---

## 1. Code Quality Standards

### 1.1 Python Style Guide

**Standard**: PEP 8 with FilterMate extensions

| Rule | Description | Current Compliance |
|------|-------------|-------------------|
| Line length | Max 120 characters | ✅ 95% |
| Indentation | 4 spaces (no tabs) | ✅ 100% |
| Imports | Grouped and sorted | ✅ 95% |
| Docstrings | All public functions | ✅ 90% |
| Type hints | Encouraged | 🔄 Partial |

### 1.2 Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Classes | PascalCase | `FilterMateApp` |
| Functions | snake_case | `get_layer_info()` |
| Constants | UPPER_SNAKE_CASE | `POSTGRESQL_AVAILABLE` |
| Private | _prefix | `_internal_method()` |
| Protected | __prefix | `__very_private()` |

### 1.3 Import Order

```python
# 1. Standard library
import os
import sys
from typing import Optional

# 2. Third-party
from qgis.core import QgsVectorLayer
from qgis.PyQt.QtCore import Qt

# 3. Local application
from .config.config import ENV_VARS
from .modules.appUtils import get_datasource_connexion_from_layer
```

---

## 2. Testing Standards

### 2.1 Test Coverage Requirements

| Category | Minimum Coverage | Current |
|----------|-----------------|---------|
| Backend modules | 80% | 75% 🔄 |
| Configuration | 90% | 85% ✅ |
| UI utilities | 70% | 60% 🔄 |
| Overall | 80% | ~70% 🔄 |

### 2.2 Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_backends.py         # Backend unit tests
├── test_config*.py          # Configuration tests
├── test_filter_history.py   # History functionality
├── test_expression_*.py     # Expression conversion
├── test_performance.py      # Performance benchmarks
└── integration/             # Integration tests
```

### 2.3 Test Naming Convention

```python
def test_<function_name>_<scenario>_<expected_result>():
    """Test description."""
    pass

# Examples:
def test_get_backend_postgresql_returns_postgresql_backend():
    pass

def test_filter_history_undo_restores_previous_state():
    pass
```

### 2.4 Running Tests

```bash
# All tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=modules --cov-report=html

# Specific category
pytest tests/test_config*.py -v

# Fast tests only (skip slow)
pytest tests/ -v -m "not slow"
```

---

## 3. Documentation Standards

### 3.1 Docstring Format

```python
def function_name(param1: str, param2: int = 10) -> dict:
    """
    Brief one-line description.
    
    Longer description if needed. Explain purpose,
    important details, or caveats.
    
    Args:
        param1: Description of param1
        param2: Description of param2 (default: 10)
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When param1 is empty
        DatabaseError: When connection fails
    
    Example:
        >>> result = function_name("test", 20)
        >>> print(result)
        {'status': 'ok'}
    """
    pass
```

### 3.2 Comment Standards

```python
# Good: Explain WHY
# Use exponential backoff to avoid overwhelming locked database
for attempt in range(max_retries):
    time.sleep(0.1 * (2 ** attempt))

# Bad: Explain WHAT (obvious from code)
# Increment counter by 1
counter += 1

# TODO format
# TODO Phase 3: Implement caching layer

# FIXME format
# FIXME: Handle edge case when layer has no features
```

### 3.3 Module-Level Documentation

```python
"""
Module name and brief description.

This module provides... (longer description)

Classes:
    ClassName: Brief description
    AnotherClass: Brief description

Functions:
    function_name: Brief description

Constants:
    CONSTANT_NAME: Brief description

Example:
    >>> from module import ClassName
    >>> obj = ClassName()

Note:
    Important usage notes or warnings.
"""
```

---

## 4. Error Handling Standards

### 4.1 Exception Hierarchy

```python
class FilterMateException(Exception):
    """Base exception for FilterMate."""
    pass

class DatabaseConnectionError(FilterMateException):
    """Database connection failed."""
    pass

class GeometryError(FilterMateException):
    """Geometry operation failed."""
    pass
```

### 4.2 Error Handling Pattern

```python
# Good: Specific handling with recovery
try:
    connection = get_database_connection()
except sqlite3.OperationalError as e:
    if "locked" in str(e):
        time.sleep(0.1)
        connection = get_database_connection()  # Retry
    else:
        raise DatabaseConnectionError(f"Failed: {e}") from e
finally:
    if connection:
        connection.close()

# Bad: Bare except
try:
    do_something()
except:
    pass  # Silent failure
```

### 4.3 User Feedback

```python
from modules.feedback_utils import show_error, show_warning, show_success

# Success - no duration parameter
show_success("Filter applied successfully")

# Warning - no duration parameter
show_warning("Large dataset may be slow")

# Error - no duration parameter
show_error(f"Failed: {error}")
```

---

## 5. Performance Standards

### 5.1 Query Performance Targets

| Backend | Dataset Size | Max Time |
|---------|--------------|----------|
| PostgreSQL | 1M features | 1s |
| PostgreSQL | 100k features | 0.5s |
| Spatialite | 100k features | 10s |
| Spatialite | 10k features | 1s |
| OGR | 10k features | 30s |
| OGR | 1k features | 3s |

### 5.2 Memory Usage Targets

| Operation | Max Memory |
|-----------|------------|
| Layer loading | 100MB per 100k features |
| Filtering | 200MB peak |
| Export | 500MB peak |

### 5.3 UI Responsiveness

| Operation | Max Blocking Time |
|-----------|-------------------|
| Button click | 100ms |
| Layer switch | 200ms |
| Config change | 100ms |
| Any operation | Use QgsTask if >500ms |

---

## 6. Security Standards

### 6.1 Database Security

```python
# Good: Parameterized query
cursor.execute(
    "SELECT * FROM table WHERE id = ?",
    (user_input,)
)

# Bad: String interpolation (SQL injection risk)
cursor.execute(f"SELECT * FROM table WHERE id = {user_input}")
```

### 6.2 File Path Security

```python
# Good: Validate paths
import os

def safe_path(user_path: str, base_dir: str) -> str:
    """Validate path is within allowed directory."""
    full_path = os.path.abspath(os.path.join(base_dir, user_path))
    if not full_path.startswith(os.path.abspath(base_dir)):
        raise ValueError("Path traversal detected")
    return full_path
```

### 6.3 Credential Handling

```python
# Good: Use QGIS credential store
from qgis.core import QgsCredentials

credentials = QgsCredentials.instance()
credentials.get(uri, username, password)

# Bad: Hardcoded credentials
connection = psycopg2.connect(password="hardcoded123")
```

---

## 7. Git Standards

### 7.1 Commit Message Format

```
<type>: <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `test`: Adding tests
- `perf`: Performance improvement
- `chore`: Maintenance

**Examples**:
```
feat: Add Spatialite backend support

Implements SpatialiteBackend class with temp table creation,
R-tree indexes, and expression conversion.

Closes #123

---

fix: Correct provider type detection for OGR layers

GeoPackage layers were incorrectly identified as unknown.

---

docs: Update README with installation instructions
```

### 7.2 Branch Naming

```
<type>/<short-description>

Examples:
feature/spatialite-backend
fix/ogr-provider-detection
docs/installation-guide
refactor/task-extraction
```

### 7.3 Pull Request Template

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Manual testing performed
- [ ] All tests passing

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No breaking changes (or documented)
```

---

## 8. Review Checklist

### 8.1 Code Review Checklist

- [ ] Code follows PEP 8 and naming conventions
- [ ] Docstrings present for public methods
- [ ] Error handling is appropriate
- [ ] No hardcoded values (use constants)
- [ ] No debug print statements left
- [ ] Tests added for new functionality
- [ ] Performance considered for large datasets
- [ ] Security considerations addressed
- [ ] Backwards compatibility maintained

### 8.2 Pre-Release Checklist

- [ ] All tests passing
- [ ] Test coverage meets targets
- [ ] CHANGELOG updated
- [ ] Version number updated
- [ ] Documentation updated
- [ ] Translation files updated
- [ ] Manual testing completed
- [ ] Performance benchmarks run

---

## 9. Quality Metrics Dashboard

### Current Status (December 2025)

| Metric | Target | Current | Trend |
|--------|--------|---------|-------|
| Code Quality Score | ≥8.5/10 | 9.0/10 | ✅ ↑ |
| Test Coverage | ≥80% | ~70% | 🔄 → |
| PEP 8 Compliance | ≥95% | 95% | ✅ → |
| Docstring Coverage | ≥90% | 90% | ✅ → |
| Open Issues | <10 | TBD | - |
| Build Success | 100% | 100% | ✅ → |
