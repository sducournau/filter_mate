# FilterMate - Serena Symbolic Analysis Configuration

## Project Overview

**FilterMate** is a QGIS plugin for advanced vector data filtering and export. This configuration optimizes Serena's symbolic code analysis tools for efficient navigation and modification of the codebase.

## Repository Structure

```
filter_mate/
├── filter_mate.py              # Entry point (305 lines)
├── filter_mate_app.py          # Main app (1038 lines) ⭐
├── modules/
│   ├── appTasks.py            # Task engine (2080 lines) ⭐⭐⭐
│   ├── appUtils.py            # Utilities (55 lines) ⭐
│   ├── widgets.py             # UI widgets
│   └── customExceptions.py    # Custom exceptions
├── config/
│   ├── config.py              # Config loader
│   └── config.json            # Config data
└── .serena/
    ├── project_memory.md      # Complete project memory
    ├── README.md              # Serena usage guide
    └── serena_config.md       # This file
```

⭐ = Critical files for migration (Phase 1-2)

## Optimization Rules for Serena

### 1. Always Start with Overview

Before reading any file, **ALWAYS** use `get_symbols_overview()`:

```python
# ✅ CORRECT
get_symbols_overview("modules/appTasks.py")
# Then: find_symbol() for specific functions

# ❌ WRONG
read_file("modules/appTasks.py", 1, 2080)
# Never read entire large files
```

### 2. Use Targeted Symbol Reads

Read only what you need:

```python
# ✅ CORRECT - Read structure first
find_symbol("FilterTask", relative_path="modules/appTasks.py", depth=1, include_body=False)

# ✅ CORRECT - Then read specific method
find_symbol("FilterTask/run", relative_path="modules/appTasks.py", include_body=True)

# ❌ WRONG - Reading entire class at once
find_symbol("FilterTask", relative_path="modules/appTasks.py", depth=999, include_body=True)
```

### 3. Use Pattern Search for Discovery

When you don't know exact symbol names:

```python
# ✅ CORRECT - Find all PostgreSQL references
search_for_pattern(
    substring_pattern="postgresql|psycopg2",
    relative_path="modules/",
    restrict_search_to_code_files=True
)

# ✅ CORRECT - Find specific SQL patterns
search_for_pattern(
    substring_pattern="CREATE MATERIALIZED VIEW",
    context_lines_before=2,
    context_lines_after=2
)
```

### 4. Use References to Understand Impact

Before modifying a symbol, check its usage:

```python
# ✅ CORRECT - See where function is used
find_referencing_symbols(
    "get_datasource_connexion_from_layer",
    relative_path="modules/appUtils.py"
)
```

### 5. Restrict Searches with relative_path

Always narrow down searches:

```python
# ✅ CORRECT - Search in specific module
search_for_pattern("POSTGRESQL_AVAILABLE", relative_path="modules/")

# ⚠️ LESS EFFICIENT - Search entire project
search_for_pattern("POSTGRESQL_AVAILABLE")
```

## Critical Symbols Map

### filter_mate_app.py

**Class: FilterMateApp**
```python
# Structure overview
find_symbol("FilterMateApp", relative_path="filter_mate_app.py", depth=1, include_body=False)

# Key methods
find_symbol("FilterMateApp/__init__", include_body=True)
find_symbol("FilterMateApp/run", include_body=True)
find_symbol("FilterMateApp/manage_task", include_body=True)
find_symbol("FilterMateApp/update_datasource", include_body=True)  # ⭐ Modified in Phase 1
```

### modules/appTasks.py

**Class: FilterTask**
```python
# Structure overview
find_symbol("FilterTask", relative_path="modules/appTasks.py", depth=1, include_body=False)

# Critical methods for Phase 2
find_symbol("FilterTask/prepare_postgresql_source_geom", include_body=True)  # Line ~389
find_symbol("FilterTask/prepare_ogr_source_geom", include_body=True)        # Line ~466
find_symbol("FilterTask/qgis_expression_to_postgis", include_body=True)     # Line ~362
find_symbol("FilterTask/execute_geometric_filtering", include_body=True)    # Line ~519 ⭐⭐
```

**Key Areas for Phase 2**:
- Line ~347: PostgreSQL availability check
- Line ~390: Location for new `qgis_expression_to_spatialite()`
- Line ~440: Location for new `create_temp_spatialite_table()`
- Line ~569: PostgreSQL geometric filtering (add Spatialite branch)
- Lines 1139, 1188, 1202, 1341: Materialized view creation (needs Spatialite alternative)

### modules/appUtils.py

**Functions**
```python
# All functions overview
get_symbols_overview("modules/appUtils.py")

# Critical function (modified in Phase 1)
find_symbol("get_datasource_connexion_from_layer", include_body=True)  # ⭐ Modified

# Check global flags
search_for_pattern("POSTGRESQL_AVAILABLE", relative_path="modules/appUtils.py")
```

## Common Analysis Patterns

### Pattern 1: Understand Existing Function

```python
# Step 1: Get file overview
get_symbols_overview("modules/appTasks.py")

# Step 2: Find function without body (understand signature)
find_symbol(
    "execute_geometric_filtering",
    relative_path="modules/appTasks.py",
    include_body=False
)

# Step 3: Read function body
find_symbol(
    "execute_geometric_filtering",
    relative_path="modules/appTasks.py",
    include_body=True
)

# Step 4: Find all callers
find_referencing_symbols(
    "execute_geometric_filtering",
    relative_path="modules/appTasks.py"
)
```

### Pattern 2: Find All PostgreSQL Logic

```python
# Step 1: Search for PostgreSQL references
search_for_pattern(
    substring_pattern="postgresql",
    relative_path="modules/",
    restrict_search_to_code_files=True,
    max_answer_chars=50000
)

# Step 2: Search for specific conditions
search_for_pattern(
    substring_pattern="if.*postgresql.*and.*POSTGRESQL_AVAILABLE",
    relative_path="modules/appTasks.py"
)

# Step 3: Find materialized view creation
search_for_pattern(
    substring_pattern="CREATE MATERIALIZED VIEW",
    context_lines_before=3,
    context_lines_after=3
)
```

### Pattern 3: Add New Function (Phase 2)

```python
# Step 1: Find where to insert (after similar function)
find_symbol(
    "qgis_expression_to_postgis",
    relative_path="modules/appTasks.py",
    include_body=True
)

# Step 2: Insert new function after it
insert_after_symbol(
    name_path="FilterTask/qgis_expression_to_postgis",
    relative_path="modules/appTasks.py",
    body='''
    def qgis_expression_to_spatialite(self, expression):
        """
        Convert QGIS expression to Spatialite SQL.
        
        Spatialite spatial functions are ~90% compatible with PostGIS.
        """
        # Implementation
        spatialite_expression = expression
        # Add conversions if needed
        return spatialite_expression
    '''
)
```

### Pattern 4: Modify Existing Function

```python
# Step 1: Read current implementation
find_symbol(
    "execute_geometric_filtering",
    relative_path="modules/appTasks.py",
    include_body=True
)

# Step 2: Find references to understand usage
find_referencing_symbols(
    "execute_geometric_filtering",
    relative_path="modules/appTasks.py"
)

# Step 3: Replace function body
replace_symbol_body(
    name_path="FilterTask/execute_geometric_filtering",
    relative_path="modules/appTasks.py",
    body='''
    def execute_geometric_filtering(self, layer_provider_type, layer, layer_props):
        """Modified to support Spatialite"""
        # New implementation
        if provider == 'postgresql' and POSTGRESQL_AVAILABLE:
            # PostgreSQL path
            pass
        elif provider == 'spatialite':
            # NEW: Spatialite path
            pass
        else:
            # Fallback
            pass
    '''
)
```

## Search Optimization Tips

### Use Specific Include Patterns

```python
# ✅ CORRECT - Search only Python files
search_for_pattern(
    "POSTGRESQL_AVAILABLE",
    paths_include_glob="**/*.py"
)

# ✅ CORRECT - Search only modules
search_for_pattern(
    "FilterTask",
    paths_include_glob="modules/*.py"
)
```

### Use Exclude Patterns

```python
# ✅ CORRECT - Skip test files
search_for_pattern(
    "postgresql",
    paths_exclude_glob="test_*.py"
)

# ✅ CORRECT - Skip documentation
search_for_pattern(
    "PostgreSQL",
    paths_exclude_glob="*.md"
)
```

### Restrict to Code Files

```python
# ✅ CORRECT - Only code symbols
search_for_pattern(
    "create_materialized_view",
    restrict_search_to_code_files=True
)
```

## Symbol Naming Patterns

### Classes
- Pattern: PascalCase
- Examples: `FilterMate`, `FilterMateApp`, `FilterTask`
- Find: `find_symbol("ClassName", include_kinds=[5])`

### Methods
- Pattern: snake_case
- Examples: `manage_task`, `execute_geometric_filtering`, `prepare_postgresql_source_geom`
- Find: `find_symbol("ClassName/method_name", include_kinds=[6])`

### Functions (module-level)
- Pattern: snake_case
- Examples: `get_datasource_connexion_from_layer`, `truncate`, `init_env_vars`
- Find: `find_symbol("function_name", include_kinds=[12])`

### Constants
- Pattern: UPPER_SNAKE_CASE
- Examples: `POSTGRESQL_AVAILABLE`, `MESSAGE_TASKS_CATEGORIES`
- Find: `search_for_pattern("^[A-Z_]+\\s*=")`

## LSP Symbol Kinds Reference

Use with `include_kinds` and `exclude_kinds`:

```python
# Classes only
find_symbol("FilterTask", include_kinds=[5])

# Functions only (no methods)
find_symbol("get_datasource_connexion_from_layer", include_kinds=[12])

# Methods only
find_symbol("FilterTask/run", include_kinds=[6])

# Variables and constants
find_symbol("POSTGRESQL_AVAILABLE", include_kinds=[13, 14])
```

**Kind Values**:
- 5 = Class
- 6 = Method
- 12 = Function
- 13 = Variable
- 14 = Constant

## Efficiency Metrics

### Token-Efficient Workflow

✅ **GOOD** (~500 tokens):
```python
get_symbols_overview("modules/appTasks.py")
find_symbol("FilterTask/run", include_body=True)
```

❌ **BAD** (~50,000 tokens):
```python
read_file("modules/appTasks.py", 1, 2080)
```

**Efficiency gain**: 100x less tokens!

### Targeted Modifications

✅ **GOOD** (modify only what's needed):
```python
replace_symbol_body("FilterTask/run", body="...")
```

❌ **BAD** (read entire file, modify, write back):
```python
content = read_file(...)
modified = content.replace(...)
write_file(...)
```

## Phase 2 Roadmap for Serena

### Step 1: Create Spatialite Table Function
```python
# Find insertion point
find_symbol("FilterTask/prepare_ogr_source_geom", include_body=False)

# Insert after
insert_after_symbol(
    name_path="FilterTask/prepare_ogr_source_geom",
    relative_path="modules/appTasks.py",
    body="<new_function_code>"
)
```

### Step 2: Create Expression Converter
```python
# Find insertion point
find_symbol("FilterTask/qgis_expression_to_postgis", include_body=True)

# Insert after
insert_after_symbol(
    name_path="FilterTask/qgis_expression_to_postgis",
    relative_path="modules/appTasks.py",
    body="<new_function_code>"
)
```

### Step 3: Modify Geometric Filtering
```python
# Read current
find_symbol("FilterTask/execute_geometric_filtering", include_body=True)

# Find all usages
find_referencing_symbols("execute_geometric_filtering")

# Replace
replace_symbol_body(
    name_path="FilterTask/execute_geometric_filtering",
    relative_path="modules/appTasks.py",
    body="<modified_code>"
)
```

### Step 4: Update Materialized Views
```python
# Find all locations
search_for_pattern("CREATE MATERIALIZED VIEW")

# For each location, wrap with condition:
# if postgresql: CREATE MATERIALIZED VIEW
# elif spatialite: create_temp_spatialite_table()
```

## Memory Files

### Primary Memory
- **File**: `.serena/project_memory.md`
- **Use**: Complete reference, updated after each phase
- **Read when**: Starting new task, need architecture overview

### Specialized Memories (Future)

Create when needed:
```python
write_memory(
    memory_file_name="spatialite_implementation.md",
    content="Details of Spatialite backend implementation..."
)

write_memory(
    memory_file_name="performance_benchmarks.md",
    content="Performance comparison PostgreSQL vs Spatialite..."
)
```

## Quick Commands Reference

```python
# Overview
get_symbols_overview(relative_path)

# Find symbol
find_symbol(name_path, relative_path, include_body=False, depth=0)

# Search pattern
search_for_pattern(substring_pattern, relative_path="", restrict_search_to_code_files=True)

# Find references
find_referencing_symbols(name_path, relative_path)

# Edit
replace_symbol_body(name_path, relative_path, body)
insert_after_symbol(name_path, relative_path, body)
insert_before_symbol(name_path, relative_path, body)

# Memory
write_memory(memory_file_name, content)
read_memory(memory_file_name)
list_memories()
```

## Best Practices Summary

1. ✅ **ALWAYS** start with `get_symbols_overview()`
2. ✅ **ALWAYS** use `relative_path` to narrow searches
3. ✅ **ALWAYS** check `include_body=False` first to see structure
4. ✅ **ALWAYS** use `find_referencing_symbols()` before modifying
5. ✅ **NEVER** read entire large files (>500 lines)
6. ✅ **NEVER** use symbolic tools after reading full file
7. ✅ **PREFER** `find_symbol()` over `read_file()`
8. ✅ **PREFER** symbolic edits over string replacements

---

**Optimized for**: Serena symbolic analysis tools  
**Project**: FilterMate QGIS Plugin  
**Version**: 1.0  
**Last Updated**: 2 December 2025
