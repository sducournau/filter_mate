# FilterMate Project - Serena Memory

## Project Overview

**Project Name**: FilterMate  
**Type**: QGIS Plugin (Python)  
**Repository**: https://github.com/sducournau/filter_mate  
**Version**: 2.2.5 (December 10, 2025)  
**Primary Language**: Python 3.7+  
**Framework**: QGIS API 3.0+, PyQt5  
**Status**: Production - Automatic Geographic CRS Handling

---

## Project Purpose

FilterMate is a QGIS plugin that provides an intuitive interface for filtering and exporting vector data. It supports multiple data sources (PostgreSQL/PostGIS, Spatialite, OGR) and offers advanced geometric filtering capabilities.

**Key Features**:
- Intuitive entity search and selection
- Expression-based filtering
- Geometric predicates with buffer support
- Layer-specific widget configuration
- Export functionality with various formats
- Subset history management

---

## Architecture

### Core Components

1. **Main Plugin Entry** (`filter_mate.py`)
   - QGIS plugin initialization
   - Toolbar and menu setup
   - Plugin lifecycle management

2. **Application Core** (`filter_mate_app.py`)
   - Main application logic (~1038 lines)
   - Task orchestration
   - Spatialite database management
   - Project and layer management
   - Event handling (layerAdded, layerRemoved, etc.)

3. **Task Engine** (`modules/appTasks.py`)
   - Filtering task execution (~2080 lines)
   - Multi-source support (PostgreSQL, Spatialite, OGR)
   - Geometric filtering logic
   - Materialized views (PostgreSQL)
   - Expression conversion

4. **Utilities** (`modules/appUtils.py`)
   - Database connection management
   - Helper functions
   - PostgreSQL connection handling

5. **UI Components**
   - `filter_mate_dockwidget.py`: Main dock widget
   - `modules/widgets.py`: Custom widgets
   - `filter_mate_dockwidget_base.ui`: Qt Designer UI file

---

## Key Symbols and Functions

### filter_mate_app.py

**Class: FilterMateApp**
- `__init__(dockwidget, iface, plugin_dir)`: Initialization
- `run()`: Start application and connect signals
- `manage_task(task_name, data)`: Task dispatcher
- `init_filterMate_db()`: Initialize Spatialite database
- `update_datasource()`: Manage data sources
- `save_variables_from_layer(layer, properties)`: Save layer config
- `remove_variables_from_layer(layer, properties)`: Remove layer config

**Important Variables**:
- `self.PROJECT_LAYERS`: Dictionary of project layers
- `self.project_datasources`: Data sources by type {'postgresql': {}, 'spatialite': {}, 'ogr': {}}
- `self.db_file_path`: Path to Spatialite database
- `self.CONFIG_DATA`: Configuration dictionary

### modules/appTasks.py

**Class: FilterTask (QgsTask)**
- `__init__(task_parameters)`: Initialize filtering task
- `run()`: Execute task (async)
- `finished(result)`: Task completion callback
- `prepare_postgresql_source_geom()`: Prepare PostgreSQL geometries (line ~389)
- `prepare_ogr_source_geom()`: Prepare OGR/Spatialite geometries (line ~466)
- `qgis_expression_to_postgis(expression)`: Convert QGIS expression to PostGIS (line ~362)
- `execute_geometric_filtering(layer_provider_type, layer, layer_props)`: Main filtering logic (line ~519)

**Critical for Migration**:
- Line 347: PostgreSQL availability check
- Line 569: PostgreSQL geometric filtering
- Line 777: Fallback to QGIS filtering
- Lines 1139, 1188, 1202, 1341: Materialized view creation

### modules/appUtils.py

**Functions**:
- `get_datasource_connexion_from_layer(layer)`: Get PostgreSQL connection
- `get_data_source_uri(layer)`: Extract data source URI
- `truncate(number, digits)`: Math utility

---

## Data Flow

### Filtering Workflow
1. User selects layer and defines filter
2. `FilterMateApp.manage_task('filter', data)` called
3. `FilterTask` created with parameters
4. Task determines provider type: 'postgresql' | 'spatialite' | 'ogr'
5. Appropriate geometry preparation method called
6. For PostgreSQL: Create materialized view with spatial index
7. For Spatialite/OGR: Use QGIS processing or direct SQL
8. Apply subset string to layer
9. Update history in Spatialite database

### Layer Management
1. QGIS signals trigger `manage_task('add_layers', layers)`
2. Layer properties analyzed and stored in `PROJECT_LAYERS`
3. Data source type detected and registered in `project_datasources`
4. Layer-specific configuration loaded from Spatialite

---

## Database Structure

### Spatialite Database (`filterMate_db.sqlite`)
**Location**: `QGIS3/profiles/default/FilterMate/filterMate_db.sqlite`

**Purpose**:
- Store project metadata
- Layer filtering history
- Widget configurations per layer
- Subset history for undo/redo

**Tables** (to be documented):
- Project metadata
- Layer history
- Configuration storage

---

## Configuration

### config/config.json
**Structure**:
```json
{
  "APP": {
    "DOCKWIDGET": {...},
    "OPTIONS": {
      "APP_SQLITE_PATH": "path/to/FilterMate",
      "FRESH_RELOAD_FLAG": false
    }
  },
  "CURRENT_PROJECT": {
    "OPTIONS": {
      "ACTIVE_POSTGRESQL": "",
      "IS_ACTIVE_POSTGRESQL": false
    },
    "EXPORTING": {...},
    "FILTERING": {...}
  }
}
```

### config/config.py
**Functions**:
- `init_env_vars()`: Initialize global ENV_VARS dictionary
- `merge(a, b)`: Merge configuration dictionaries

**Global Variables**:
- `ENV_VARS`: Contains PROJECT, PLATFORM, DIR_CONFIG, CONFIG_DATA, etc.

---

## Dependencies

### Required
- QGIS >= 3.0
- Python >= 3.7
- PyQt5 (provided by QGIS)
- qgis.core, qgis.gui, qgis.utils

### Optional (Phase 1 completed)
- **psycopg2**: PostgreSQL support (now optional!)
- Spatialite support (built into QGIS)

### Standard Library
- os, sys, json, re, math, uuid, collections, zipfile, pathlib

---

## Current Migration Status

### Phase 1: ✅ COMPLETED (2 December 2025)
**Objective**: Make PostgreSQL optional

**Changes Implemented**:
1. Conditional import of psycopg2 in:
   - `modules/appUtils.py`
   - `modules/appTasks.py`
2. Global flag `POSTGRESQL_AVAILABLE`
3. Adapted functions:
   - `get_datasource_connexion_from_layer()`: Returns None if PostgreSQL unavailable
   - `prepare_postgresql_source_geom()`: Only called if PostgreSQL available
   - `execute_geometric_filtering()`: Checks POSTGRESQL_AVAILABLE
   - `update_datasource()`: Warning if PostgreSQL layers without psycopg2

**Result**: Plugin can start without psycopg2 installed!

### Phase 2: TODO (Next)
**Objective**: Implement Spatialite backend alternative

**Functions to Create**:
1. `create_temp_spatialite_table(db_path, table_name, sql_query, geom_field)`
   - Replace PostgreSQL materialized views
   - Create temporary tables with spatial indexes
   - Location: `modules/appTasks.py` after line ~440

2. `qgis_expression_to_spatialite(expression)`
   - Convert QGIS expressions to Spatialite SQL
   - Similar to `qgis_expression_to_postgis()`
   - Location: `modules/appTasks.py` after line ~390

**Modifications Required**:
- Lines 1139, 1188, 1202, 1341: Replace CREATE MATERIALIZED VIEW
- Line 569: Add Spatialite branch in geometric filtering
- Adapt buffer and transformation expressions

---

## Provider Detection Pattern

```python
# Used throughout codebase
if layer.providerType() == 'postgres':
    layer_provider_type = 'postgresql'
elif layer.providerType() == 'spatialite':
    layer_provider_type = 'spatialite'
elif layer.providerType() == 'ogr':
    layer_provider_type = 'ogr'
```

---

## Common Code Patterns

### Spatialite Connection
```python
from pyspatialite import dbapi2 as spatialite
conn = spatialite_connect(self.db_file_path)
cursor = conn.cursor()
cursor.execute(sql_statement)
conn.commit()
conn.close()
```

### PostgreSQL Connection (now conditional)
```python
if POSTGRESQL_AVAILABLE:
    connexion = psycopg2.connect(
        user=username, password=password, 
        host=host, port=port, database=dbname
    )
```

### Layer Subset Application
```python
layer.setSubsetString(expression)
```

---

## Testing

### Test Files
- `test_phase1_optional_postgresql.py`: Phase 1 validation tests

### Test Scenarios
1. Import without psycopg2
2. Filtering with Shapefile
3. Filtering with GeoPackage
4. PostgreSQL regression tests
5. Performance benchmarks

---

## Documentation

### Created Documents
- `AUDIT_FILTERMATE.md`: Complete technical analysis
- `SERENA_PROJECT_CONFIG.md`: Project configuration for Serena
- `MIGRATION_GUIDE.md`: Step-by-step migration guide
- `TODO.md`: Detailed action plan (5 phases)
- `RESUME_EXECUTIF.md`: Executive summary
- `PHASE1_IMPLEMENTATION.md`: Phase 1 completion report
- `INDEX_DOCUMENTATION.md`: Documentation index

---

## Known Issues

### Active
None currently - Phase 1 completed successfully

### To Monitor
- Performance on large datasets without PostgreSQL
- Spatialite extension loading on different platforms (Windows/Linux/Mac)
- Compatibility with QGIS versions 3.x

---

## Development Guidelines

### Code Style
- Follow existing patterns in codebase
- Use descriptive variable names
- Add docstrings to new functions
- Maintain backward compatibility

### Symbolic Tool Usage
- Use `get_symbols_overview()` before reading full files
- Use `find_symbol()` with specific name paths
- Use `find_referencing_symbols()` to understand dependencies
- Use `search_for_pattern()` for regex searches

### When Adding Features
1. Check if PostgreSQL available: `if POSTGRESQL_AVAILABLE:`
2. Provide Spatialite alternative
3. Fallback to QGIS processing if needed
4. Update tests
5. Document changes

---

## Important File Locations

### Source Code
- Main plugin: `filter_mate.py`
- Application: `filter_mate_app.py`
- Tasks: `modules/appTasks.py`
- Utils: `modules/appUtils.py`
- Widgets: `modules/widgets.py`
- Exceptions: `modules/customExceptions.py`

### Configuration
- Main config: `config/config.json`
- Config loader: `config/config.py`

### Resources
- Icons: `icons/`
- UI files: `*.ui`
- Translations: `i18n/`

### Documentation
- All `*.md` files in root directory

### Tests
- `test_phase1_optional_postgresql.py`
- More to be added in Phase 2-5

---

## Quick Reference Commands

### Find Symbol
```python
# Find class with methods
find_symbol("FilterMateApp", relative_path="filter_mate_app.py", depth=1)

# Find specific method
find_symbol("FilterMateApp/manage_task", relative_path="filter_mate_app.py", include_body=True)
```

### Search Pattern
```python
# Find all PostgreSQL references
search_for_pattern("postgresql|psycopg2", substring_pattern=".*")

# Find materialized views
search_for_pattern("CREATE MATERIALIZED VIEW")
```

### List Directory
```python
# List modules
list_dir("modules", recursive=False)
```

---

## Next Steps (Phase 2)

1. Create `create_temp_spatialite_table()` function
2. Create `qgis_expression_to_spatialite()` function
3. Adapt geometric filtering logic
4. Replace materialized view creation
5. Add Spatialite-specific tests
6. Benchmark performance vs PostgreSQL
7. Update documentation

---

**Memory Created**: 2 December 2025  
**Last Updated**: 2 December 2025  
**Status**: Phase 1 Complete, Phase 2 Ready to Start  
**Maintainer**: GitHub Copilot / Development Team
