# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

**FilterMate** is a production-ready QGIS plugin (v3.0.4) for advanced spatial filtering and export of vector data. It provides an intuitive interface for complex spatial queries across PostgreSQL/PostGIS, Spatialite/GeoPackage, and OGR data sources.

**Language:** Python 3.7+
**Framework:** QGIS API 3.0+, PyQt5
**Architecture:** Multi-backend factory pattern with async task execution
**Status:** Production-stable, 40+ stability fixes consolidated in v3.0

---

## Development Commands

### Build and Package

```bash
# Compile UI files (.ui → .py)
./compile_ui.sh              # Linux/Mac
compile_ui.bat               # Windows

# Create plugin ZIP for distribution
python tools/zip_plugin.py   # Output: dist/filter_mate_vX.X.X.zip
```

### Testing

```bash
# Setup test environment (first time)
./setup_tests.sh             # Linux/Mac
setup_tests.bat              # Windows

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=. --cov-report=html

# Run specific test file
pytest tests/test_config_helpers.py -v
```

### Translation Management

```bash
# Compile translations
python tools/compile_translations_simple.py

# Update translations
python tools/update_translations_v289.py

# Verify all translations
python tools/verify_all_translations.py
```

### Plugin Installation Path

**Development location:**
- **Windows:** `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\filter_mate`
- **Linux:** `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/filter_mate`
- **macOS:** `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/filter_mate`

After code changes, restart QGIS or use Plugin Reloader.

---

## High-Level Architecture

FilterMate uses a **layered architecture** with clear separation of concerns:

### Core Components

```
filter_mate.py                → QGIS plugin entry point
filter_mate_app.py            → Application orchestrator (3000+ lines)
  ├── Task coordination
  ├── State management
  ├── Signal routing
  └── Configuration persistence

filter_mate_dockwidget.py     → UI management (5000+ lines)
  ├── Widget initialization
  ├── User input handling
  ├── Signal/slot connections
  └── Configuration JSON tree view
```

### Multi-Backend System (Factory Pattern)

**Critical Concept:** FilterMate automatically selects optimal backends based on data source type and available dependencies.

```
modules/backends/
  ├── factory.py              → Backend selection logic
  ├── base_backend.py         → Abstract interface
  ├── postgresql_backend.py   → PostgreSQL/PostGIS (optimal, requires psycopg2)
  ├── spatialite_backend.py   → Spatialite/GeoPackage (good, built-in)
  ├── ogr_backend.py          → Universal fallback (compatible)
  └── memory_backend.py       → QGIS memory layers (fast for small data)
```

**Backend Selection Priority:**
1. **User-forced backend** (via UI indicator)
2. **Memory backend** for native memory layers
3. **PostgreSQL** if `layer.providerType() == 'postgres'` AND `psycopg2` available
4. **Spatialite** if `layer.providerType() == 'spatialite'`
5. **OGR** as universal fallback

**Performance Characteristics:**
- PostgreSQL: Best for >50k features (server-side materialized views + GIST indexes)
- Spatialite: Good for 10k-50k features (temp tables + R-tree indexes)
- Memory: Fast for <100k features in RAM (QgsSpatialIndex)
- OGR: Universal but slower for large datasets

### Async Task Execution

All heavy operations use **QgsTask** to prevent UI blocking:

```
modules/tasks/
  ├── filter_task.py           → Filtering operations (950 lines)
  ├── layer_management_task.py → Layer add/remove (1125 lines)
  ├── progressive_filter.py    → Two-phase filtering for large datasets
  ├── parallel_executor.py     → Multi-threaded operations (PostgreSQL/Spatialite only)
  └── query_complexity_estimator.py → SQL complexity analysis for strategy selection
```

**Pattern:**
```python
class FilterEngineTask(QgsTask):
    def run(self):
        # Background thread - no UI access
        backend = BackendFactory.get_backend(layer, task_parameters)
        result = backend.execute_filter(params)
        return True

    def finished(self, result):
        # Main thread - safe for UI updates
        if result:
            self.app.apply_subset_filter(result_data)
```

### Data Flow: Filtering Operation

```
User clicks "Filter" button
    ↓
FilterMateDockWidget.launchTaskEvent signal
    ↓
FilterMateApp.manage_task('filter')
    ↓
FilterEngineTask.run() [background thread]
    ├─ BackendFactory.get_backend(layer)
    ├─ backend.execute_filter(params)
    │   ├─ PostgreSQL: CREATE MATERIALIZED VIEW + GIST index
    │   ├─ Spatialite: CREATE TEMP TABLE + R-tree index
    │   └─ OGR: QGIS processing + memory layer
    └─ Return filtered feature IDs
    ↓
Task.taskCompleted signal
    ↓
FilterMateApp.filter_engine_task_completed() [main thread]
    ↓
FilterMateApp.apply_subset_filter()
    └─ layer.setSubsetString(expression)
    ↓
QGIS canvas updates
```

---

## Critical Patterns and Conventions

### 1. PostgreSQL Availability Check

**ALWAYS check before using psycopg2:**

```python
from modules.appUtils import POSTGRESQL_AVAILABLE

if POSTGRESQL_AVAILABLE and layer.providerType() == 'postgres':
    # Safe to use psycopg2
    backend = PostgreSQLBackend(layer)
else:
    # Use fallback
    backend = OGRBackend(layer)
```

### 2. Thread Safety

**CRITICAL:** `QgsVectorLayer` objects are NOT thread-safe.

- PostgreSQL/Spatialite: Can use parallel execution (database connections are per-thread)
- OGR layers (Shapefiles, GeoPackage): MUST use sequential execution
- Never access `QgsVectorLayer` methods from background threads
- Extract all needed data in main thread before creating QgsTask

**Example:**
```python
# ✅ GOOD: Extract data in main thread
layer_id = layer.id()
crs_authid = layer.crs().authid()
task = FilterEngineTask(layer_id, crs_authid)

# ❌ BAD: Accessing layer in background thread
def run(self):
    crs = self.layer.crs()  # CRASHES!
```

### 3. Signal Management

Use utilities to prevent signal loops:

```python
from modules.signal_utils import SignalBlocker

with SignalBlocker(widget):
    widget.setValue(new_value)  # No signals emitted
# Signals restored automatically
```

### 4. User Feedback

**CRITICAL:** QGIS message bar methods only accept 2 arguments (title, message).

```python
from qgis.utils import iface

# ✅ CORRECT
iface.messageBar().pushSuccess("FilterMate", "Filter applied successfully")
iface.messageBar().pushWarning("FilterMate", "Large dataset detected")
iface.messageBar().pushCritical("FilterMate", f"Error: {error}")

# ❌ WRONG - No duration parameter
iface.messageBar().pushSuccess("FilterMate", "Message", 5)  # Will error
```

### 5. Database Connection Management

**Always close connections:**

```python
# PostgreSQL (psycopg2)
conn = None
try:
    conn = psycopg2.connect(...)
    cursor = conn.cursor()
    cursor.execute(sql)
    conn.commit()
finally:
    if conn:
        conn.close()

# Spatialite (sqlite3)
conn = None
try:
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    conn.load_extension('mod_spatialite')  # or 'mod_spatialite.dll' on Windows
    cursor = conn.cursor()
    cursor.execute(sql)
    conn.commit()
finally:
    if conn:
        conn.close()
```

### 6. Layer Provider Detection

```python
provider_type = layer.providerType()

if provider_type == 'postgres':
    layer_provider_type = 'postgresql'
elif provider_type == 'spatialite':
    layer_provider_type = 'spatialite'
elif provider_type == 'ogr':
    layer_provider_type = 'ogr'
elif provider_type == 'memory':
    layer_provider_type = 'memory'
```

### 7. Configuration System

Configuration stored in `config/config.json` with ChoicesType pattern:

```python
from modules.config_helpers import get_config_value, set_config_value

# Read with ChoicesType extraction
value = get_config_value('UI_PROFILE', default='auto')  # Returns: 'auto'

# With choices: {"value": "auto", "choices": ["auto", "compact", "normal"]}
# Without choices: "auto"

# Write
set_config_value('UI_PROFILE', 'compact')
```

---

## Important Implementation Details

### Negative Buffer (Erosion) Handling

**Critical:** Buffer is applied via SQL `ST_Buffer()`, NOT in Python.

PostgreSQL pattern:
```sql
CASE WHEN ST_IsEmpty(ST_MakeValid(ST_Buffer(geom, -10))) THEN NULL
     ELSE ST_MakeValid(ST_Buffer(geom, -10)) END
```

Spatialite pattern:
```sql
CASE WHEN ST_IsEmpty(MakeValid(ST_Buffer(geom, -10))) = 1 THEN NULL
     ELSE MakeValid(ST_Buffer(geom, -10)) END
```

### Geometry Validation

Always wrap source geometries in validation:

```python
# PostgreSQL
source_geom_expr = f"ST_MakeValid(ST_GeomFromText('{wkt}', {srid}))"

# Spatialite
source_geom_expr = f"MakeValid(GeomFromText('{wkt}', {srid}))"
```

### Materialized View Optimizations (PostgreSQL)

v2.9.1+ includes advanced optimizations:
- **INCLUDE clause** (PostgreSQL 11+): Covering indexes for 10-30% speedup
- **Bbox column** (≥10k features): Pre-computed bounding boxes for 2-5x speedup
- **Async CLUSTER** (50k-100k features): Non-blocking index clustering
- **Extended statistics** (PostgreSQL 10+): Better query plans

Configuration in `modules/constants.py`:
```python
MV_ENABLE_INDEX_INCLUDE = True
MV_ENABLE_BBOX_COLUMN = True
MV_ENABLE_ASYNC_CLUSTER = True
MV_ASYNC_CLUSTER_THRESHOLD = 50000
```

### Canvas Refresh Strategy

For complex filters (EXISTS, ST_BUFFER patterns), use delayed refresh:

```python
# 800ms delay for initial refresh
QTimer.singleShot(800, self._delayed_canvas_refresh)

# 2000ms delay for final refresh
QTimer.singleShot(2000, self._final_canvas_refresh)
```

This ensures correct display after materialized view creation.

---

## Code Style and Conventions

### Naming

- **Classes:** `PascalCase` (e.g., `FilterMateApp`, `FilterEngineTask`)
- **Functions/Methods:** `snake_case` (e.g., `manage_task`, `get_datasource_connexion_from_layer`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `POSTGRESQL_AVAILABLE`)
- **Private methods:** `_prefix` (e.g., `_internal_method`)

### Import Order

1. Standard library
2. Third-party (QGIS, PyQt5)
3. Local application

```python
import os
import sys
from typing import Optional

from qgis.core import QgsVectorLayer, QgsProject
from qgis.PyQt.QtCore import Qt

from .config.config import ENV_VARS
from .modules.appUtils import get_datasource_connexion_from_layer
```

### Documentation

Use Google-style docstrings:

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

---

## Common Pitfalls to Avoid

❌ **DON'T** import psycopg2 directly without checking `POSTGRESQL_AVAILABLE`
✅ **DO** use the availability flag for conditional imports

❌ **DON'T** access QgsVectorLayer in background threads
✅ **DO** extract all needed data in main thread before QgsTask

❌ **DON'T** use blocking operations in main thread
✅ **DO** use QgsTask for heavy operations

❌ **DON'T** forget to close database connections
✅ **DO** use try/finally blocks

❌ **DON'T** add duration parameter to iface.messageBar() methods
✅ **DO** use only 2 parameters (title, message)

❌ **DON'T** assume PostgreSQL is always available
✅ **DO** provide Spatialite or OGR fallback paths

---

## Key Files Reference

### Core Application
- `filter_mate.py:initGui()` - Plugin initialization
- `filter_mate_app.py:manage_task()` - Central task dispatcher (line ~200-350)
- `filter_mate_dockwidget.py:current_layer_changed()` - Layer switching logic

### Backend System
- `modules/backends/factory.py:get_backend()` - Backend selection (line ~21-50)
- `modules/backends/postgresql_backend.py` - PostgreSQL implementation (167KB)
- `modules/backends/spatialite_backend.py` - Spatialite implementation (240KB)
- `modules/backends/ogr_backend.py` - OGR fallback (170KB)

### Task Execution
- `modules/tasks/filter_task.py:run()` - Filtering logic (612KB)
- `modules/tasks/layer_management_task.py` - Layer operations (87KB)
- `modules/tasks/progressive_filter.py` - Two-phase filtering (31KB)
- `modules/tasks/parallel_executor.py` - Multi-threaded execution (25KB)

### Utilities
- `modules/appUtils.py` - Database connections, geometry repair
- `modules/config_helpers.py` - Configuration management
- `modules/signal_utils.py` - Signal blocking utilities
- `modules/feedback_utils.py` - User notifications
- `modules/crs_utils.py` - CRS handling and coordinate precision

### Configuration
- `config/config.py` - Configuration loader (`ENV_VARS` global)
- `config/config.json` - User settings with ChoicesType pattern
- `modules/constants.py` - Backend optimization constants

---

## Testing

Tests use pytest with QGIS fixtures:

```python
# Run all tests
pytest tests/

# Common test patterns
def test_feature(mock_qgs_project):
    """Test using QGIS project fixture."""
    from modules.module import function

    result = function(input_data)
    assert result == expected_value
```

**Important test files:**
- `tests/conftest.py` - Pytest fixtures for QGIS mocking
- `tests/test_backends/` - Backend-specific tests
- `tests/test_config_*.py` - Configuration system tests
- `tests/test_filter_preservation.py` - Filter history tests

---

## Documentation and Development Tools

### Serena Integration

FilterMate uses **Serena** for code navigation (if available):

```python
# Use symbolic tools for efficient navigation
get_symbols_overview("modules/appTasks.py")
find_symbol("FilterTask", depth=1, include_body=False)
find_symbol("FilterTask/run", include_body=True)
```

### BMAD Integration

FilterMate uses **BMAD v6.0.0-alpha.22** for development management. Agents and workflows are in `_bmad/` directory (excluded from plugin distribution).

### Memory and Documentation

- `.serena/memories/` - Architecture and pattern documentation
- `docs/` - User-facing documentation
- `.github/copilot-instructions.md` - Detailed coding standards

---

## Important Context

### Version History
- **v3.0.4** (January 2026) - Current stable release
- **v3.0.0** - Major milestone: 40+ stability fixes consolidated
- **v2.9.x** - PostgreSQL MV optimizations, centroid handling
- **v2.8.x** - Enhanced auto-optimizer, performance metrics
- **v2.7.x** - WKT coordinate precision optimization
- **v2.5.x** - Thread safety, bidirectional sync, memory backend

### Performance Optimizations
- 99% match optimization (skip redundant filters)
- Adaptive geometry simplification (2-10x faster buffers)
- Smart caching (up to 80% cache hit rate)
- Parallel processing (2x speedup on 1M+ features)

### Signal Management
Critical to prevent UI freezes after filtering operations. All signal reconnections are handled through utilities to prevent loops.

### Undo/Redo System
Complete filter history with intelligent context detection:
- Source-only undo (current layer only)
- Global undo (all layers in session)
- Context-aware button state management

---

## Quick Reference

**Check PostgreSQL availability:**
```python
from modules.appUtils import POSTGRESQL_AVAILABLE
```

**Get backend for layer:**
```python
from modules.backends.factory import BackendFactory
backend = BackendFactory.get_backend(layer, task_parameters)
```

**Create async task:**
```python
from qgis.core import QgsTask
class MyTask(QgsTask):
    def run(self):  # Background thread
        return True
    def finished(self, result):  # Main thread
        pass
```

**Show user feedback:**
```python
from qgis.utils import iface
iface.messageBar().pushSuccess("FilterMate", "Operation complete")
```

**Block signals temporarily:**
```python
from modules.signal_utils import SignalBlocker
with SignalBlocker(widget):
    widget.setValue(value)
```

---

**Remember:** FilterMate prioritizes multi-backend support. PostgreSQL for performance, Spatialite for simplicity, OGR for universal compatibility.
