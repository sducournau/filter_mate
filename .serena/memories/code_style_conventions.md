# Code Style and Conventions

## Python Standards
- **Style Guide**: PEP 8
- **Indentation**: 4 spaces
- **Line Length**: Maximum 120 characters
- **Docstrings**: Required for classes and functions
- **Type Hints**: Encouraged but not required (QGIS compatibility)

## Naming Conventions
### Classes
- **Format**: `PascalCase`
- **Examples**: 
  - `FilterMateApp`
  - `FilterTask`
  - `QgsCheckableComboBoxLayer`
  - `LayersManagementEngineTask`

### Functions/Methods
- **Format**: `snake_case`
- **Examples**:
  - `manage_task()`
  - `get_datasource_connexion_from_layer()`
  - `filtering_populate_layers_chekableCombobox()`
  - `icon_per_geometry_type()`

### Constants
- **Format**: `UPPER_SNAKE_CASE`
- **Examples**:
  - `POSTGRESQL_AVAILABLE`
  - `PROVIDER_POSTGRES`
  - `PROVIDER_SPATIALITE`
  - `PROVIDER_OGR`

### Private Methods
- **Format**: Prefix with `_`
- **Examples**:
  - `_internal_method()`
  - `_process_layer()`

## Import Order
1. Standard library imports
2. Third-party imports (QGIS, PyQt5)
3. Local application imports

### Example
```python
import os
import sys
from typing import Optional

from qgis.core import QgsVectorLayer, QgsProject
from qgis.PyQt.QtCore import Qt

from .config.config import ENV_VARS
from .modules.appUtils import get_datasource_connexion_from_layer
```

## QGIS-Specific Patterns
### Provider Type Detection
```python
if layer.providerType() == 'postgres':
    layer_provider_type = 'postgresql'
elif layer.providerType() == 'spatialite':
    layer_provider_type = 'spatialite'
elif layer.providerType() == 'ogr':
    layer_provider_type = 'ogr'
```

### PostgreSQL Availability Check
```python
from modules.appUtils import POSTGRESQL_AVAILABLE

if POSTGRESQL_AVAILABLE and provider_type == 'postgresql':
    # PostgreSQL-specific code
    connexion = psycopg2.connect(...)
else:
    # Fallback to Spatialite or OGR
    pass
```

### Async Task Pattern
```python
class MyTask(QgsTask):
    def __init__(self, description, task_parameters):
        super().__init__(description, QgsTask.CanCancel)
        self.task_parameters = task_parameters
        self.result_data = None
    
    def run(self):
        try:
            # Task logic
            return True
        except Exception as e:
            self.exception = e
            return False
    
    def finished(self, result):
        if result:
            # Success
            pass
        else:
            # Error handling
            pass
```

## Error Handling
### User-Facing Errors
Use QGIS message bar:
```python
from qgis.utils import iface

iface.messageBar().pushSuccess("FilterMate", "Filter applied successfully")
iface.messageBar().pushWarning("FilterMate", "Warning message", duration=10)
iface.messageBar().pushCritical("FilterMate", f"Error: {str(error)}")
```

### Development Errors
Use print statements for debugging (visible in QGIS Python console):
```python
print(f"FilterMate Debug: {variable_name} = {value}")
```

## Comments and Documentation
- Explain **why**, not **what**
- Use TODO comments: `# TODO Phase 2: Implement Spatialite version`
- Use FIXME for known issues: `# FIXME: Handle edge case XYZ`

## Performance Considerations
- PostgreSQL: Best for > 100k features
- Spatialite: Good for < 100k features  
- QGIS Memory: Avoid for > 10k features
