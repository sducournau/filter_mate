# GitHub Copilot Instructions for FilterMate

You are working on **FilterMate**, a QGIS plugin written in Python that provides advanced filtering and export capabilities for vector data.

## Project Context

- **Type**: QGIS Plugin (Python 3.7+)
- **Framework**: QGIS API, PyQt5
- **Architecture**: Multi-backend support (PostgreSQL/PostGIS, Spatialite, OGR)
- **Current Status**: Phase 1 complete (PostgreSQL optional), Phase 2 in progress (Spatialite backend)

## Code Style Guidelines

### Python Standards
- Follow PEP 8 conventions
- Use 4 spaces for indentation
- Maximum line length: 120 characters
- Use docstrings for classes and functions
- Type hints encouraged but not required (QGIS compatibility)

### Naming Conventions
- Classes: `PascalCase` (e.g., `FilterMateApp`, `FilterTask`)
- Functions/Methods: `snake_case` (e.g., `manage_task`, `get_datasource_connexion_from_layer`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `POSTGRESQL_AVAILABLE`)
- Private methods: prefix with `_` (e.g., `_internal_method`)

### Import Order
1. Standard library imports
2. Third-party imports (QGIS, PyQt5)
3. Local application imports

Example:
```python
import os
import sys
from typing import Optional

from qgis.core import QgsVectorLayer, QgsProject
from qgis.PyQt.QtCore import Qt

from .config.config import ENV_VARS
from .modules.appUtils import get_datasource_connexion_from_layer
```

## Critical Patterns

### 1. PostgreSQL Availability Check
**ALWAYS** check `POSTGRESQL_AVAILABLE` before using PostgreSQL-specific code:

```python
from modules.appUtils import POSTGRESQL_AVAILABLE

if POSTGRESQL_AVAILABLE and provider_type == 'postgresql':
    # PostgreSQL-specific code
    connexion = psycopg2.connect(...)
else:
    # Fallback to Spatialite or OGR
    pass
```

### 2. Provider Type Detection
Use this pattern consistently:

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

### 3. Spatialite Connections
Use this pattern for Spatialite database operations:

```python
import sqlite3

conn = sqlite3.connect(db_path)
conn.enable_load_extension(True)
try:
    conn.load_extension('mod_spatialite')
except:
    conn.load_extension('mod_spatialite.dll')  # Windows fallback

cursor = conn.cursor()
cursor.execute(sql_statement)
conn.commit()
conn.close()
```

### 4. QGIS Task Pattern
For asynchronous operations, inherit from `QgsTask`:

```python
class MyTask(QgsTask):
    def __init__(self, description, task_parameters):
        super().__init__(description, QgsTask.CanCancel)
        self.task_parameters = task_parameters
        self.result_data = None
    
    def run(self):
        # Main task logic
        try:
            # Do work
            return True
        except Exception as e:
            self.exception = e
            return False
    
    def finished(self, result):
        if result:
            # Success handling
            pass
        else:
            # Error handling
            pass
```

## Key Files and Their Purposes

### Core Files
- **filter_mate.py**: Plugin entry point, QGIS integration
- **filter_mate_app.py**: Main application orchestrator (~1038 lines)
- **modules/appTasks.py**: Async filtering tasks (~2080 lines)
- **modules/appUtils.py**: Database connections and utilities

### When Editing These Files
- **appUtils.py**: Keep functions simple, focused on DB connections
- **appTasks.py**: Maintain provider-specific branches (PostgreSQL/Spatialite/OGR)
- **filter_mate_app.py**: Coordinate between UI and tasks, manage state

## Common Functions Reference

### Database Operations
```python
# Get PostgreSQL connection (returns None if unavailable)
connexion, source_uri = get_datasource_connexion_from_layer(layer)

# Spatialite connection
conn = spatialite_connect(db_file_path)
```

### Layer Operations
```python
# Apply filter
layer.setSubsetString(expression)

# Get layer info
provider_type = layer.providerType()
feature_count = layer.featureCount()
crs = layer.crs()
```

### Expression Conversion
```python
# Convert QGIS expression to PostGIS SQL
postgis_expr = self.qgis_expression_to_postgis(qgis_expr)

# TODO Phase 2: Convert to Spatialite SQL
spatialite_expr = self.qgis_expression_to_spatialite(qgis_expr)
```

## Phase 2 Implementation Guidelines

### Creating Spatialite Alternatives

When adding Spatialite alternatives to PostgreSQL functions:

1. **Check existing PostgreSQL implementation**
2. **Create parallel Spatialite function**
3. **Add conditional logic**:
   ```python
   if provider == 'postgresql' and POSTGRESQL_AVAILABLE:
       # PostgreSQL optimized path
       create_materialized_view(...)
   elif provider == 'spatialite':
       # NEW: Spatialite alternative
       create_temp_spatialite_table(...)
   else:
       # Fallback: QGIS processing
       use_qgis_processing(...)
   ```

### Required New Functions (Phase 2)

#### 1. create_temp_spatialite_table
```python
def create_temp_spatialite_table(self, db_path, table_name, sql_query, geom_field='geometry'):
    """
    Create temporary table in Spatialite as alternative to PostgreSQL materialized views.
    
    Args:
        db_path: Path to Spatialite database
        table_name: Name for temporary table
        sql_query: SELECT query to populate table
        geom_field: Geometry column name
    
    Returns:
        bool: Success status
    """
    # Implementation here
    pass
```

#### 2. qgis_expression_to_spatialite
```python
def qgis_expression_to_spatialite(self, expression):
    """
    Convert QGIS expression to Spatialite SQL.
    
    Note: Spatialite spatial functions are ~90% compatible with PostGIS.
    
    Args:
        expression: QGIS expression string
    
    Returns:
        str: Spatialite SQL expression
    """
    # Implementation here
    pass
```

## Error Handling

### User-Facing Errors
Use QGIS message bar for user feedback:

```python
from qgis.utils import iface

# Success
iface.messageBar().pushSuccess("FilterMate", "Filter applied successfully")

# Info
iface.messageBar().pushInfo("FilterMate", "Using Spatialite backend")

# Warning
iface.messageBar().pushWarning(
    "FilterMate", 
    "Large dataset detected. Consider using PostgreSQL for better performance.",
    duration=10
)

# Error
iface.messageBar().pushCritical("FilterMate", f"Error: {str(error)}")
```

### Development Errors
Use print statements for debugging (visible in QGIS Python console):

```python
print(f"FilterMate Debug: {variable_name} = {value}")
```

## Performance Considerations

### Large Datasets
- PostgreSQL: Best for > 100k features
- Spatialite: Good for < 100k features
- QGIS Memory: Avoid for > 10k features

### When to Warn Users
```python
if layer.featureCount() > 50000 and not POSTGRESQL_AVAILABLE:
    iface.messageBar().pushWarning(
        "FilterMate - Performance",
        f"Large dataset ({layer.featureCount()} features) without PostgreSQL. "
        "Performance may be reduced. Consider installing psycopg2.",
        duration=10
    )
```

## Testing Guidelines

### Unit Tests
Place in root directory: `test_*.py`

```python
import unittest
from unittest.mock import Mock, patch

class TestMyFeature(unittest.TestCase):
    def setUp(self):
        # Mock QGIS dependencies
        pass
    
    def test_something(self):
        # Test implementation
        self.assertTrue(result)
```

### Manual Testing Checklist
1. Test without psycopg2 installed
2. Test with Shapefile/GeoPackage
3. Test with PostgreSQL (if available)
4. Test with large datasets (performance)
5. Verify error messages are clear

## Documentation

### Docstring Format
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
- Explain **why**, not **what**
- Use TODO comments for future work: `# TODO Phase 2: Implement Spatialite version`
- Use FIXME for known issues: `# FIXME: Handle edge case XYZ`

## Git Commit Messages

Follow conventional commits:

```
feat: Add Spatialite backend support
fix: Correct provider type detection for OGR layers
docs: Update README with installation instructions
test: Add unit tests for Phase 1
refactor: Extract common DB connection logic
perf: Optimize spatial index creation
```

## Common Pitfalls to Avoid

❌ **DON'T** import psycopg2 directly without try/except
✅ **DO** use the POSTGRESQL_AVAILABLE flag

❌ **DON'T** assume PostgreSQL is available
✅ **DO** provide Spatialite fallback

❌ **DON'T** use blocking operations in main thread
✅ **DO** use QgsTask for heavy operations

❌ **DON'T** forget to close database connections
✅ **DO** use try/finally or context managers

❌ **DON'T** read entire files when using Serena
✅ **DO** use get_symbols_overview() and find_symbol()

## Resource Management

### Database Connections
```python
# Always close connections
try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # operations
    conn.commit()
finally:
    if conn:
        conn.close()
```

### QGIS Layers
```python
# Temporary layers should be added to project or will be garbage collected
temp_layer = QgsVectorLayer("Point?crs=epsg:4326", "temp", "memory")
QgsProject.instance().addMapLayer(temp_layer)
```

## Useful QGIS API Patterns

### Get Current Project
```python
project = QgsProject.instance()
layers = project.mapLayers().values()
```

### Vector Layer Features
```python
# Iterate features
for feature in layer.getFeatures():
    geom = feature.geometry()
    attrs = feature.attributes()

# Get selected features
selected = layer.selectedFeatures()

# Filter with expression
layer.setSubsetString("population > 10000")
```

### Coordinate Transform
```python
from qgis.core import QgsCoordinateReferenceSystem, QgsCoordinateTransform

source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
dest_crs = QgsCoordinateReferenceSystem("EPSG:3857")
transform = QgsCoordinateTransform(source_crs, dest_crs, project)

transformed_geom = geom.transform(transform)
```

## Phase-Specific Notes

### Phase 1 (✅ Complete)
- PostgreSQL is optional
- POSTGRESQL_AVAILABLE flag in place
- Graceful degradation working

### Phase 2 (🔄 In Progress)
- Focus: Spatialite backend implementation
- Create alternatives to materialized views
- Maintain PostgreSQL performance when available

### Phase 3-5 (📋 Planned)
- Tests and documentation
- Optimization and caching
- Beta testing and deployment

## Quick Reference

### Import PostgreSQL Support Flag
```python
from modules.appUtils import POSTGRESQL_AVAILABLE
```

### Check If Layer Is PostgreSQL
```python
is_postgres = layer.providerType() == 'postgres'
```

### Safe PostgreSQL Operation
```python
if POSTGRESQL_AVAILABLE and layer.providerType() == 'postgres':
    # Safe to use psycopg2
    pass
```

---

## Serena Configuration (Windows)

### Auto-Start Serena on Chat Activation

When working on Windows, Serena MCP server must be started before using symbolic tools. The configuration ensures automatic startup:

**Prerequisites:**
- Serena installed via: `uv tool install serena`
- MCP configuration in `%APPDATA%/Code/User/globalStorage/github.copilot.chat.mcp/config.json`

**Configuration:**
```json
{
  "mcpServers": {
    "serena": {
      "command": "uvx",
      "args": ["serena"],
      "env": {
        "SERENA_PROJECT": "C:/Users/Simon/OneDrive/Documents/GitHub/filter_mate"
      }
    }
  }
}
```

**Automatic Activation:**
- Serena activates automatically when Copilot Chat is opened in VS Code
- Project path is set via `SERENA_PROJECT` environment variable
- No manual activation needed - tools are immediately available

**Verify Activation:**
```python
# First command in new chat should confirm Serena is active
get_current_config()  # Shows active project and available tools
```

**Troubleshooting:**
- If tools unavailable: Check MCP server logs in VS Code Output panel
- Verify `uvx serena` works from PowerShell/CMD
- Ensure path uses forward slashes or escaped backslashes in JSON

---

**Remember**: Always prioritize multi-backend support. PostgreSQL for performance, Spatialite for simplicity, OGR for compatibility.

When in doubt, check existing patterns in the codebase or consult `.serena/project_memory.md`.
