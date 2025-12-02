# Serena Project Configuration

## Project Information
- **Name**: FilterMate
- **Type**: QGIS Plugin (Python)
- **Language**: Python 3.7+
- **Framework**: QGIS API, PyQt5

## Project Root
`/windows/c/Users/Simon/OneDrive/Documents/GitHub/filter_mate`

## Source Directories
- `./` - Main plugin files
- `./modules/` - Core modules
- `./config/` - Configuration files
- `./icons/` - Icon resources
- `./i18n/` - Translations

## Key Files for Analysis

### Priority 1 (Core)
- `filter_mate.py` - Plugin entry point
- `filter_mate_app.py` - Main application (1038 lines)
- `modules/appTasks.py` - Task engine (2080 lines)
- `modules/appUtils.py` - Utilities

### Priority 2 (UI)
- `filter_mate_dockwidget.py` - Main dock widget
- `modules/widgets.py` - Custom widgets

### Priority 3 (Config)
- `config/config.py` - Configuration loader
- `config/config.json` - Configuration data

## Patterns to Search

### PostgreSQL Related
- `postgresql`
- `psycopg2`
- `POSTGRESQL_AVAILABLE`
- `CREATE MATERIALIZED VIEW`
- `postgis`

### Spatialite Related
- `spatialite`
- `spatialite_connect`
- `sqlite3`

### Provider Detection
- `providerType()`
- `layer_provider_type`
- `param_source_provider_type`

### Filtering
- `FilterTask`
- `execute_geometric_filtering`
- `setSubsetString`
- `geometric_predicates`

## Symbol Naming Conventions

### Classes
- `FilterMate` - Main plugin class
- `FilterMateApp` - Application class
- `FilterMateDockWidget` - Dock widget class
- `FilterTask` - Async task class (QgsTask)

### Methods (common patterns)
- `__init__()` - Constructors
- `run()` - Execution methods
- `manage_task()` - Task management
- `prepare_*_source_geom()` - Geometry preparation
- `execute_*_filtering()` - Filtering execution

### Functions
- `get_*` - Getter functions
- `truncate()` - Utility function
- `init_env_vars()` - Initialization

## Code Structure

### Modules Structure
```
modules/
├── appTasks.py          # FilterTask class
├── appUtils.py          # Utility functions
├── widgets.py           # Custom Qt widgets
├── customExceptions.py  # Custom exceptions
└── qt_json_view/        # JSON viewer (external)
```

### Import Hierarchy
```
filter_mate.py
  └── filter_mate_app.py
      ├── config/config.py
      ├── modules/appTasks.py
      │   ├── modules/appUtils.py
      │   └── config/config.py
      └── modules/widgets.py
```

## LSP Symbol Kinds Reference

For `include_kinds` / `exclude_kinds` parameters:

- 1 = File
- 2 = Module
- 3 = Namespace
- 4 = Package
- 5 = Class
- 6 = Method
- 7 = Property
- 8 = Field
- 9 = Constructor
- 10 = Enum
- 11 = Interface
- 12 = Function
- 13 = Variable
- 14 = Constant

Common filters:
- Classes only: `include_kinds=[5]`
- Functions only: `include_kinds=[12]`
- Methods only: `include_kinds=[6]`
- Classes and functions: `include_kinds=[5, 12]`

## Typical Analysis Workflows

### 1. Understand a Module
```python
# Step 1: Get overview
get_symbols_overview("modules/appTasks.py")

# Step 2: Find main class
find_symbol("FilterTask", relative_path="modules/appTasks.py", depth=1, include_body=False)

# Step 3: Read specific methods
find_symbol("FilterTask/run", relative_path="modules/appTasks.py", include_body=True)
```

### 2. Find All PostgreSQL Usage
```python
# Step 1: Pattern search
search_for_pattern("postgresql", substring_pattern=".*", restrict_search_to_code_files=True)

# Step 2: Check specific conditions
search_for_pattern("if.*postgresql.*and.*POSTGRESQL_AVAILABLE")
```

### 3. Prepare for Editing
```python
# Step 1: Find symbol to edit
find_symbol("execute_geometric_filtering", relative_path="modules/appTasks.py", include_body=True)

# Step 2: Find references
find_referencing_symbols("execute_geometric_filtering", relative_path="modules/appTasks.py")

# Step 3: Replace or insert
replace_symbol_body("execute_geometric_filtering", relative_path="modules/appTasks.py", body="...")
```

## Ignore Patterns

Files to skip in analysis:
- `*.ui` - Qt Designer files (XML)
- `*.qrc` - Qt Resource files
- `*.ts` - Translation source files
- `resources.py` - Generated resources
- `__pycache__/` - Python cache
- `.git/` - Git directory
- `*.pyc` - Compiled Python

## Testing Files

- `test_phase1_optional_postgresql.py` - Phase 1 tests
- Future: `test_phase2_spatialite_backend.py`
- Future: `test_integration_*.py`

## Documentation Files

All `*.md` files are documentation:
- `README.md` - Project readme
- `AUDIT_FILTERMATE.md` - Technical audit
- `MIGRATION_GUIDE.md` - Migration guide
- `TODO.md` - Task tracking
- `SERENA_PROJECT_CONFIG.md` - Serena config documentation
- `PHASE1_IMPLEMENTATION.md` - Phase 1 report
- And more...

## Memory Management

### When to Create New Memories

Create specialized memories for:
- Complex subsystems (e.g., "spatialite_backend.md")
- Performance optimizations (e.g., "performance_tuning.md")
- Known issues (e.g., "known_issues.md")
- Architecture decisions (e.g., "architecture_decisions.md")

### When to Update project_memory.md

Update main memory when:
- Completing migration phases
- Adding major features
- Discovering new patterns
- Significant refactoring

## Quick Reference

### Most Used Commands
```python
# Overview
get_symbols_overview(relative_path)

# Find
find_symbol(name_path, relative_path, include_body=True, depth=0)

# Search
search_for_pattern(substring_pattern, relative_path="", restrict_search_to_code_files=True)

# References
find_referencing_symbols(name_path, relative_path)

# Edit
replace_symbol_body(name_path, relative_path, body)
insert_after_symbol(name_path, relative_path, body)
insert_before_symbol(name_path, relative_path, body)
```

---

**Configuration Version**: 1.0  
**Created**: 2 December 2025  
**Compatible with**: Serena symbolic analysis tools
