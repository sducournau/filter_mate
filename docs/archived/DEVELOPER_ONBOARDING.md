# FilterMate Developer Onboarding Guide

Welcome to the FilterMate development team! This guide will help you get started with contributing to the project.

## Table of Contents

1. [Overview](#overview)
2. [Development Environment Setup](#development-environment-setup)
3. [Project Structure](#project-structure)
4. [Architecture Understanding](#architecture-understanding)
5. [Coding Guidelines](#coding-guidelines)
6. [Common Tasks](#common-tasks)
7. [Testing](#testing)
8. [Debugging](#debugging)
9. [Contributing](#contributing)
10. [Resources](#resources)

## Overview

FilterMate is a QGIS plugin that provides advanced filtering and export capabilities for vector data. It supports multiple backends (PostgreSQL/PostGIS, Spatialite, OGR) and offers a user-friendly interface for complex spatial queries.

### Key Features

- Multi-backend architecture (PostgreSQL, Spatialite, OGR)
- Geometric filtering with spatial predicates
- Dynamic buffering
- Layer exploration and feature selection
- Data export capabilities
- Persistent layer configurations

### Technology Stack

- **Language**: Python 3.7+
- **Framework**: QGIS Plugin API (PyQGIS)
- **UI**: PyQt5
- **Databases**: PostgreSQL/PostGIS, Spatialite
- **Testing**: pytest
- **Version Control**: Git

## Development Environment Setup

### Prerequisites

1. **QGIS Installation**
   - Install QGIS 3.x (LTS recommended)
   - Windows: https://qgis.org/en/site/forusers/download.html
   - Linux: `sudo apt install qgis` or use package manager
   - macOS: Download from QGIS website

2. **Python Environment**
   - QGIS comes with its own Python interpreter
   - Python 3.7+ required
   - Access QGIS Python console: `Plugins > Python Console`

3. **IDE Setup** (Recommended: VS Code)
   ```bash
   # Install VS Code extensions
   - Python
   - Pylance
   - GitLens
   ```

### Clone the Repository

```bash
git clone https://github.com/yourusername/filter_mate.git
cd filter_mate
```

### Install in QGIS

#### Method 1: Symlink (Development - Recommended)

**Windows (PowerShell as Administrator):**
```powershell
$pluginDir = "$env:APPDATA\QGIS\QGIS3\profiles\default\python\plugins"
New-Item -ItemType SymbolicLink -Path "$pluginDir\filter_mate" -Target "C:\path\to\filter_mate"
```

**Linux/macOS:**
```bash
ln -s /path/to/filter_mate ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/filter_mate
```

#### Method 2: Copy Files

Copy the entire `filter_mate` directory to your QGIS plugins directory:
- Windows: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
- Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
- macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

### Install Dependencies

#### Required Python Packages

```python
# Most are included with QGIS, but for testing:
pip install pytest pytest-cov pytest-qgis
```

#### Optional: PostgreSQL Support

```bash
pip install psycopg2-binary
```

### Verify Installation

1. Start QGIS
2. Go to `Plugins > Manage and Install Plugins`
3. Enable "FilterMate" in Installed Plugins
4. A new dock widget should appear

## Project Structure

```
filter_mate/
├── __init__.py                    # Plugin entry point
├── filter_mate.py                 # QGIS plugin integration
├── filter_mate_app.py             # Main application orchestrator
├── filter_mate_dockwidget.py      # UI management
├── filter_mate_dockwidget_base.ui # UI design file
├── metadata.txt                   # Plugin metadata
├── LICENSE                        # GPL-3.0 license
├── README.md                      # User documentation
├── ROADMAP.md                     # Development roadmap
├── CHANGELOG.md                   # Version history
│
├── config/                        # Configuration files
│   ├── config.json               # Runtime configuration
│   └── config.py                 # Config loader
│
├── modules/                       # Core modules
│   ├── appTasks.py               # Asynchronous task execution
│   ├── appUtils.py               # Database utilities
│   ├── constants.py              # Global constants
│   ├── logging_config.py         # Logging setup
│   ├── signal_utils.py           # Qt signal helpers
│   ├── ui_styles.py              # UI styling
│   ├── widgets.py                # Custom widgets
│   ├── state_manager.py          # State management (NEW)
│   │
│   └── backends/                 # Backend system
│       ├── __init__.py
│       ├── base_backend.py       # Abstract base class
│       ├── factory.py            # Backend factory
│       ├── postgresql_backend.py # PostGIS backend
│       ├── spatialite_backend.py # Spatialite backend
│       └── ogr_backend.py        # OGR fallback
│
├── docs/                          # Documentation
│   ├── BACKEND_API.md            # Backend API reference
│   ├── DEVELOPER_ONBOARDING.md   # This file
│   └── architecture.md           # System architecture
│
├── tests/                         # Unit tests
│   ├── conftest.py               # pytest configuration
│   ├── test_appUtils.py
│   ├── test_backends.py
│   └── requirements-test.txt
│
├── icons/                         # UI icons
├── i18n/                         # Translations
└── resources/                     # Resources (styles, etc.)
```

### Key Files to Understand

| File | Purpose | When to Modify |
|------|---------|----------------|
| `filter_mate_app.py` | Application logic, layer management | Adding app-level features |
| `filter_mate_dockwidget.py` | UI management, widget handling | UI changes, widget behavior |
| `modules/appTasks.py` | Async task execution | Task processing logic |
| `modules/backends/` | Database backend implementations | Adding/modifying backends |
| `modules/state_manager.py` | State management | Refactoring state handling |

## Architecture Understanding

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    QGIS Application                      │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  FilterMate Plugin                       │
│                                                           │
│  ┌────────────────┐         ┌─────────────────────┐    │
│  │  filter_mate.py│────────▶│ FilterMateApp       │    │
│  │  (Entry Point) │         │ (Orchestrator)      │    │
│  └────────────────┘         └──────────┬──────────┘    │
│                                         │               │
│              ┌──────────────────────────┼────────────┐ │
│              │                          │            │ │
│              ▼                          ▼            ▼ │
│  ┌───────────────────┐     ┌─────────────┐  ┌──────────┐
│  │FilterMateDockWidget│     │  appTasks   │  │ Backends ││
│  │   (UI Manager)     │     │  (Workers)  │  │ (Data)   ││
│  └───────────────────┘     └─────────────┘  └──────────┘
└─────────────────────────────────────────────────────────┘
```

### Component Responsibilities

#### 1. **filter_mate.py** - Plugin Entry Point
- Initializes plugin in QGIS
- Creates dock widget
- Registers menu actions
- Handles plugin lifecycle

#### 2. **FilterMateApp** - Application Orchestrator  
- Manages application state (PROJECT_LAYERS)
- Coordinates between UI and backends
- Handles layer management
- Database initialization
- Task management

#### 3. **FilterMateDockWidget** - UI Management
- Widget initialization
- User input handling
- Signal/slot connections
- Layer property management
- Visual feedback

#### 4. **appTasks** - Async Task Execution
- FilterEngineTask: Filtering operations
- LayersManagementEngineTask: Layer add/remove
- PopulateListEngineTask: Feature list population
- Background processing to keep UI responsive

#### 5. **Backend System** - Data Access
- Abstract interface in `base_backend.py`
- PostgreSQL: Server-side operations
- Spatialite: Local database operations
- OGR: Universal fallback
- Factory pattern for selection

### Data Flow

#### Layer Addition Flow

```
QGIS Layer Added
    ↓
MapLayerStore.layersAdded signal
    ↓
FilterMateApp.manage_task('add_layers')
    ↓
LayersManagementEngineTask.run()
    - Detect provider type
    - Get geometry type
    - Collect layer metadata
    ↓
FilterMateApp.layer_management_engine_task_completed()
    ↓
FilterMateDockWidget.get_project_layers_from_app()
    ↓
UI Updated (layers combobox populated)
```

#### Filtering Flow

```
User selects layers + options
    ↓
FilterMateDockWidget.launchTaskEvent('filter')
    ↓
FilterMateApp.manage_task('filter')
    ↓
FilterEngineTask.run()
    - Backend selection (Factory)
    - build_expression()
    - apply_filter()
    ↓
FilterMateApp.filter_engine_task_completed()
    ↓
Layer repaint + UI update
```

### State Management

**PROJECT_LAYERS Structure:**
```python
{
    "layer_id": {
        "infos": {
            "layer_name": str,
            "layer_provider_type": str,
            "layer_geometry_type": str,
            "geometry_field": str,
            "primary_key_name": str,
            ...
        },
        "exploring": {
            "single_selection_expression": str,
            "is_tracking": bool,
            ...
        },
        "filtering": {
            "layers_to_filter": list,
            "geometric_predicates": list,
            ...
        }
    }
}
```

**NEW: State Manager (modules/state_manager.py)**
- `LayerStateManager`: Encapsulates layer state
- `ProjectStateManager`: Encapsulates project config
- Reduces coupling with global dictionary

## Coding Guidelines

### Python Style

Follow PEP 8 with these specifics:

```python
# Imports
import os
import sys
from typing import Optional

from qgis.core import QgsVectorLayer
from qgis.PyQt.QtCore import Qt

from .config.config import ENV_VARS
from .modules.appUtils import get_datasource_connexion_from_layer


# Naming
class MyClass:              # PascalCase for classes
    MY_CONSTANT = 42        # UPPER_SNAKE_CASE for constants
    
    def my_method(self):    # snake_case for functions/methods
        local_var = 1       # snake_case for variables
        return local_var


# Docstrings
def my_function(param1: str, param2: int) -> bool:
    """
    Brief description of function.
    
    Longer description if needed. Explain the purpose,
    any important details, or caveats.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    
    Raises:
        ValueError: When this happens
    """
    pass
```

### QGIS/PyQt Patterns

```python
# Check for PostgreSQL availability
from modules.appUtils import POSTGRESQL_AVAILABLE

if POSTGRESQL_AVAILABLE:
    # Safe to use psycopg2
    import psycopg2

# Layer provider detection
provider_type = layer.providerType()
if provider_type == 'postgres':
    layer_provider_type = 'postgresql'
elif provider_type == 'spatialite':
    layer_provider_type = 'spatialite'

# Safe signal connections
try:
    layer.selectionChanged.connect(self.on_selection_changed)
except (TypeError, RuntimeError):
    pass  # Signal not available or layer deleted

# Message bar (duration is positional)
from qgis.utils import iface
iface.messageBar().pushSuccess("FilterMate", "Operation successful", 3)
iface.messageBar().pushWarning("FilterMate", "Warning message", 5)
iface.messageBar().pushCritical("FilterMate", "Error occurred", 0)  # 0 = indefinite

# Async tasks
from qgis.core import QgsTask, QgsApplication

class MyTask(QgsTask):
    def run(self):
        # Background work
        return True
    
    def finished(self, result):
        # Callback on main thread
        if result:
            pass  # Success

task = MyTask("Task description", params)
QgsApplication.taskManager().addTask(task)
```

### Backend Development

When working with backends:

```python
# Always inherit from base class
from modules.backends.base_backend import GeometricFilterBackend

class MyBackend(GeometricFilterBackend):
    def supports_layer(self, layer):
        return layer.providerType() == 'mytype'
    
    def build_expression(self, layer_props, predicates, **kwargs):
        # Validate properties first
        is_valid, missing, error = self.validate_layer_properties(layer_props)
        if not is_valid:
            self.log_error(error)
            return ""
        
        # Build expression
        expression = "..."
        return expression
    
    def apply_filter(self, layer, expression, **kwargs):
        try:
            layer.setSubsetString(expression)
            return True
        except Exception as e:
            self.log_error(f"Failed to apply filter: {e}")
            return False
```

### Error Handling

```python
# Database connections
try:
    conn = sqlite3.connect(db_path)
    # operations
finally:
    if conn:
        conn.close()

# Widget operations
try:
    self.widget.setValue(value)
except (AttributeError, KeyError, RuntimeError):
    # Widget may not be initialized or already destroyed
    pass

# Layer operations
if layer is None or not isinstance(layer, QgsVectorLayer):
    return

if layer.id() not in self.PROJECT_LAYERS:
    return
```

## Common Tasks

### Adding a New Feature

1. **Identify the component** (UI, app logic, backend)
2. **Plan the data flow** (signals, tasks, callbacks)
3. **Implement incrementally**:
   - Add UI elements (dockwidget.ui)
   - Add widget initialization (dockwidget.py)
   - Add app logic (filter_mate_app.py)
   - Add task processing (appTasks.py if async)
4. **Test thoroughly**
5. **Update documentation**

### Modifying the UI

1. **Edit UI file**: `filter_mate_dockwidget_base.ui`
   - Use Qt Designer or edit XML directly
   
2. **Regenerate Python UI**: (if needed)
   ```bash
   pyuic5 filter_mate_dockwidget_base.ui -o filter_mate_dockwidget_base.py
   ```

3. **Update dockwidget.py**:
   - Initialize new widgets in `setupUiCustom()`
   - Add signal connections in `connect_widgets_signals()`
   - Add event handlers

4. **Update styling** in `manage_ui_style()` if needed

### Adding a Backend

See [Backend API Documentation](docs/BACKEND_API.md) for details.

1. Create `modules/backends/my_backend.py`
2. Inherit from `GeometricFilterBackend`
3. Implement abstract methods
4. Add to factory in `modules/backends/factory.py`
5. Write tests in `tests/test_backends.py`
6. Update documentation

### Debugging a Bug

1. **Reproduce the issue**
2. **Enable debug logging**:
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```
3. **Check QGIS Python console** for errors
4. **Use print() statements** (visible in console)
5. **Check log file** (if logging configured)
6. **Use Qt Creator debugger** (advanced)

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_backends.py

# Run with coverage
pytest --cov=modules --cov-report=html

# Run specific test
pytest tests/test_backends.py::test_postgresql_backend -v
```

## Testing

### Test Structure

```python
# tests/test_my_feature.py
import pytest
from unittest.mock import Mock, patch
from qgis.core import QgsVectorLayer

def test_my_function():
    """Test my_function with valid input."""
    result = my_function(valid_input)
    assert result == expected_output

@pytest.fixture
def mock_layer():
    """Fixture providing a mock layer."""
    layer = Mock(spec=QgsVectorLayer)
    layer.id.return_value = "test_layer_id"
    return layer

def test_with_fixture(mock_layer):
    """Test using fixture."""
    assert mock_layer.id() == "test_layer_id"
```

### Testing Backends

```python
def test_backend_build_expression():
    """Test expression building."""
    backend = MyBackend({})
    
    expression = backend.build_expression(
        layer_props={'layer_name': 'test'},
        predicates={'intersects': 'ST_Intersects'}
    )
    
    assert 'ST_Intersects' in expression
    assert 'test' in expression
```

### Manual Testing Checklist

- [ ] Test without psycopg2 installed
- [ ] Test with PostgreSQL layer
- [ ] Test with Spatialite layer
- [ ] Test with Shapefile
- [ ] Test filter operations
- [ ] Test buffer operations
- [ ] Test large datasets (performance)
- [ ] Test error messages
- [ ] Test UI responsiveness

## Debugging

### QGIS Python Console

Access via `Plugins > Python Console` or `Ctrl+Alt+P`

```python
# Test plugin methods
from qgis.utils import plugins
fm = plugins['filter_mate']
print(fm.app.PROJECT_LAYERS)

# Test layer
layer = iface.activeLayer()
print(layer.providerType())
print(layer.featureCount())

# Test backend
from modules.backends.factory import BackendFactory
backend = BackendFactory.get_backend(layer, {})
print(backend.get_backend_name())
```

### Print Debugging

```python
# Prints appear in QGIS Python Console
print(f"FilterMate DEBUG: variable = {variable}")

# Log to file
import logging
logger = logging.getLogger(__name__)
logger.debug("Debug message")
logger.info("Info message")
logger.warning("Warning message")
logger.error("Error message")
```

### Common Issues

**Plugin not loading**
- Check metadata.txt
- Check for syntax errors
- Look in QGIS Plugin Manager > Settings > Show also experimental plugins

**Import errors**
- Check QGIS Python environment
- Verify file paths and module structure
- Check __init__.py files exist

**UI not updating**
- Check signal connections
- Verify widget initialization order
- Look for recursive call prevention flags

**Backend not working**
- Check POSTGRESQL_AVAILABLE flag
- Verify layer provider type
- Check backend factory logic

## Contributing

### Git Workflow

1. **Create a branch**:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Make changes and commit**:
   ```bash
   git add .
   git commit -m "feat: Add new feature

   - Implement feature X
   - Update documentation
   - Add tests"
   ```

3. **Push and create PR**:
   ```bash
   git push origin feature/my-new-feature
   ```

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type: Brief description

Longer description if needed.

- Bullet points for details
- Another detail

Closes #123
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Adding/updating tests
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `style`: Code style changes (formatting)
- `chore`: Maintenance tasks

### Code Review Checklist

Before submitting:
- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] No console warnings/errors
- [ ] Performance acceptable
- [ ] Works with all backends
- [ ] Error handling implemented

## Resources

### Documentation

- [Backend API Reference](docs/BACKEND_API.md)
- [Architecture Overview](docs/architecture.md)
- [QGIS Plugin Development](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/)
- [PyQGIS API](https://qgis.org/pyqgis/latest/)

### QGIS Resources

- [QGIS Python Console](https://docs.qgis.org/latest/en/docs/user_manual/plugins/python_console.html)
- [QGIS Task Manager](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/tasks.html)
- [QgsVectorLayer](https://qgis.org/pyqgis/latest/core/QgsVectorLayer.html)

### Spatial Databases

- [PostGIS Documentation](https://postgis.net/documentation/)
- [Spatialite Documentation](https://www.gaia-gis.it/fossil/libspatialite/)
- [OGR SQL Dialect](https://gdal.org/user/ogr_sql_dialect.html)

### Python Resources

- [PEP 8 Style Guide](https://pep8.org/)
- [Python Type Hints](https://docs.python.org/3/library/typing.html)
- [pytest Documentation](https://docs.pytest.org/)

## Getting Help

- **Issues**: Check GitHub Issues for known problems
- **Discussions**: GitHub Discussions for questions
- **Code**: Read inline comments and docstrings
- **Documentation**: Refer to docs/ directory
- **Community**: QGIS community forums

## Next Steps

1. ✅ Complete environment setup
2. ✅ Read this guide
3. ✅ Explore the codebase
4. ✅ Run the tests
5. ✅ Make a small change
6. ✅ Test your change
7. ✅ Submit your first PR

Welcome aboard! 🎉
