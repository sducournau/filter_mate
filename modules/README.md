# FilterMate Modules

This directory contains the core modules of the FilterMate plugin.

## Module Overview

### Core Modules

#### `constants.py`
**Purpose:** Centralized constants for the entire codebase  
**Key Components:**
- Provider types: `PROVIDER_POSTGRES`, `PROVIDER_SPATIALITE`, `PROVIDER_OGR`
- Geometry types with helper `get_geometry_type_string()`
- Spatial predicates: `PREDICATE_INTERSECTS`, `PREDICATE_WITHIN`, etc.
- Performance thresholds with `should_warn_performance()`
- Task actions, buffer types, UI constants

**Why it exists:** Eliminates magic strings, provides type safety, single source of truth

#### `appUtils.py`
**Purpose:** Utility functions for layer detection, database connections  
**Key Functions:**
- `detect_layer_provider_type()`: Consistent provider detection
- `get_datasource_connexion_from_layer()`: PostgreSQL connection management
- `geometry_type_to_string()`: Convert QGIS geometry types to strings
- `get_icon_for_geometry()`: Icon caching for UI

**Pattern:** Pure utility functions with no side effects

#### `appTasks.py`
**Purpose:** Asynchronous task execution (QgsTask-based)  
**Key Classes:**
- `FilterEngineTask`: Main filtering task executor
- Handles filter/unfilter/reset operations
- Manages materialized views (PostgreSQL) and temp tables (Spatialite)
- Thread-safe layer operations

**Pattern:** Long-running operations in background threads

#### `signal_utils.py`
**Purpose:** Context managers for safe Qt signal management  
**Key Components:**
- `SignalBlocker`: Exception-safe signal blocking
- `SignalConnection`: Temporary signal connections
- `SignalBlockerGroup`: Manage widget groups

**Pattern:** RAII (Resource Acquisition Is Initialization) pattern

#### `ui_styles.py`
**Purpose:** UI styling and theme management  
**Key Functions:**
- `load_qss_stylesheet()`: Load external QSS files
- `get_color_for_theme()`: Theme-aware colors
- Separates presentation from logic

**Pattern:** Externalized styles, theme-agnostic code

### Backend Architecture

#### `backends/`
**Purpose:** Multi-backend architecture for different data sources

##### `base_backend.py`
Abstract base class defining the backend interface

##### `postgresql_backend.py`
PostgreSQL/PostGIS backend - Best performance for large datasets

##### `spatialite_backend.py`
Spatialite backend - Good performance for medium datasets

##### `ogr_backend.py`
OGR backend - Universal compatibility, fallback for all formats

##### `factory.py`
Factory pattern for backend selection

**Pattern:** Strategy pattern - runtime backend selection

### Configuration

#### `logging_config.py`
**Purpose:** Centralized logging configuration  
**Features:**
- Rotating file handlers (10MB max, 5 backups)
- Separate loggers for app, tasks, and utils
- Safe stream handler (prevents QGIS shutdown crashes)

### Widget Components

#### `widgets.py`
**Purpose:** Custom Qt widgets  
**Key Widgets:**
- `QgsCheckableComboBoxFeaturesListPickerWidget`: Multi-select feature picker
- `QgsCheckableComboBoxLayer`: Layer selection widget

#### `qt_json_view/`
**Purpose:** JSON viewer widget for layer properties  
**Pattern:** Model-View architecture

### Utilities

#### `customExceptions.py`
**Purpose:** Custom exception classes  
**Key Exceptions:**
- `SignalStateChangeError`: Signal connection failures

## Architecture Patterns

### 1. Constants Pattern
```python
from modules.constants import PROVIDER_POSTGRES, PREDICATE_INTERSECTS

if provider == PROVIDER_POSTGRES:
    # Type-safe, no magic strings
```

### 2. Backend Selection
```python
from modules.backends import BackendFactory

backend = BackendFactory.get_backend(provider_type, layer, task_params)
result = backend.apply_filter(layer, expression)
```

### 3. Safe Signal Management
```python
from modules.signal_utils import SignalBlocker

with SignalBlocker(widget):
    # Signals blocked here
    widget.setValue(new_value)
# Signals automatically restored, even if exception occurs
```

### 4. Logging
```python
from modules.logging_config import get_app_logger

logger = get_app_logger()
logger.info("Operation started")
logger.warning("Performance concern")
logger.error("Operation failed")
```

## Testing

Tests are located in `../tests/`:
- `test_constants.py` - 29 tests for constants module
- `test_signal_utils.py` - 23 tests for signal utilities
- `test_backends.py` - Backend architecture tests
- `test_appUtils.py` - Utility function tests

Run tests:
```bash
pytest tests/ -v
```

## Dependencies

### Required
- QGIS 3.x API
- PyQt5
- Python 3.7+

### Optional
- `psycopg2`: PostgreSQL support (recommended for large datasets)

## Code Quality Standards

1. **No magic strings** - Use constants from `constants.py`
2. **Proper logging** - Use loggers, never `print()`
3. **Type hints** - Where appropriate (QGIS compatibility first)
4. **Docstrings** - All public functions and classes
5. **Error handling** - Specific exceptions, never bare `except:`
6. **Thread safety** - QgsTask for long operations

## Performance Considerations

### Backend Performance
| Backend      | Best For            | Feature Count | Operations      |
|--------------|---------------------|---------------|-----------------|
| PostgreSQL   | Large datasets      | > 50k         | Server-side     |
| Spatialite   | Medium datasets     | 10k - 50k     | Local DB        |
| OGR          | Small datasets      | < 10k         | Memory-based    |

### Optimization Tips
1. Use PostgreSQL for > 50k features
2. Batch operations when possible
3. Use materialized views (PostgreSQL) or temp tables (Spatialite)
4. Create spatial indexes for filtered results
5. Use QgsTask for non-blocking operations

## Contributing

When adding new modules:
1. Add constants to `constants.py`
2. Use existing logging infrastructure
3. Add tests in `../tests/`
4. Update this README
5. Follow existing code patterns

## See Also

- [FilterMate Main README](../README.md)
- [CHANGELOG](../CHANGELOG.md)
- [ROADMAP](../ROADMAP.md)
