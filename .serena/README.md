# Serena Configuration for FilterMate

This directory contains configuration and memory files for using Serena (symbolic code analysis tools) with the FilterMate project.

## Quick Start (Windows)

**Serena auto-starts** when you open GitHub Copilot Chat in VS Code!

- ✅ No manual activation needed
- ✅ Project automatically loaded via MCP server
- ✅ All symbolic tools immediately available

See [mcp_windows_setup.md](mcp_windows_setup.md) for detailed setup instructions.

## Files

### mcp_windows_setup.md
Complete guide for configuring Serena MCP server auto-start on Windows:
- Installation steps
- MCP configuration file location and format
- Troubleshooting guide
- Multiple projects setup

### project_memory.md
Complete project memory containing:
- Architecture overview
- Key symbols and functions
- Data flow documentation
- Current migration status
- Code patterns and guidelines
- Quick reference for symbolic tools

## Using Serena with FilterMate

### Basic Commands

#### Get Overview of a File
```python
# Get all top-level symbols in a file
get_symbols_overview("filter_mate_app.py")
```

#### Find Specific Symbol
```python
# Find a class with its methods (depth=1)
find_symbol("FilterMateApp", relative_path="filter_mate_app.py", depth=1, include_body=False)

# Find specific method with body
find_symbol("FilterMateApp/manage_task", relative_path="filter_mate_app.py", include_body=True)

# Find function in modules
find_symbol("get_datasource_connexion_from_layer", relative_path="modules/appUtils.py", include_body=True)
```

#### Search for Patterns
```python
# Find all PostgreSQL references
search_for_pattern("postgresql|psycopg2", substring_pattern=".*", restrict_search_to_code_files=True)

# Find CREATE MATERIALIZED VIEW statements
search_for_pattern("CREATE MATERIALIZED VIEW", context_lines_before=2, context_lines_after=2)

# Find all uses of POSTGRESQL_AVAILABLE flag
search_for_pattern("POSTGRESQL_AVAILABLE")
```

#### Find References
```python
# Find all places where a function is called
find_referencing_symbols("get_datasource_connexion_from_layer", relative_path="modules/appUtils.py")

# Find references to FilterTask class
find_referencing_symbols("FilterTask", relative_path="modules/appTasks.py")
```

#### List Directory
```python
# List modules directory
list_dir("modules", recursive=False, skip_ignored_files=True)

# List all Python files recursively
find_file("*.py", ".")
```

## Workflow Examples

### Example 1: Understanding a New Function

```python
# 1. Get overview of the file
get_symbols_overview("filter_mate_app.py")

# 2. Find the specific function (without body first)
find_symbol("FilterMateApp/manage_task", relative_path="filter_mate_app.py", include_body=False)

# 3. Read the function body
find_symbol("FilterMateApp/manage_task", relative_path="filter_mate_app.py", include_body=True)

# 4. Find where it's called
find_referencing_symbols("manage_task", relative_path="filter_mate_app.py")
```

### Example 2: Modifying PostgreSQL Logic

```python
# 1. Find all PostgreSQL-related code
search_for_pattern("param_source_provider_type.*postgresql", substring_pattern=".*", restrict_search_to_code_files=True)

# 2. Get overview of appTasks.py
get_symbols_overview("modules/appTasks.py")

# 3. Find the prepare_postgresql_source_geom function
find_symbol("prepare_postgresql_source_geom", relative_path="modules/appTasks.py", include_body=True)

# 4. Find all references to understand usage
find_referencing_symbols("prepare_postgresql_source_geom", relative_path="modules/appTasks.py")
```

### Example 3: Adding New Spatialite Function

```python
# 1. Find similar PostgreSQL function for reference
find_symbol("qgis_expression_to_postgis", relative_path="modules/appTasks.py", include_body=True)

# 2. Find where to insert (after line ~390)
get_symbols_overview("modules/appTasks.py")

# 3. Use insert_after_symbol to add new function
insert_after_symbol(
    name_path="qgis_expression_to_postgis",
    relative_path="modules/appTasks.py",
    body="def qgis_expression_to_spatialite(self, expression):\n    \"\"\"Convert QGIS expression to Spatialite SQL\"\"\"\n    # Implementation here\n    pass"
)
```

## Key Locations for Phase 2

### Functions to Create (modules/appTasks.py)

1. **create_temp_spatialite_table** (after line ~440)
   ```python
   find_symbol("prepare_ogr_source_geom", relative_path="modules/appTasks.py")
   # Insert after this function
   ```

2. **qgis_expression_to_spatialite** (after line ~390)
   ```python
   find_symbol("qgis_expression_to_postgis", relative_path="modules/appTasks.py")
   # Insert after this function
   ```

### Areas to Modify

1. **Materialized View Creation** (lines 1139, 1188, 1202, 1341)
   ```python
   search_for_pattern("CREATE MATERIALIZED VIEW")
   # Each location needs conditional logic:
   # if postgresql: create materialized view
   # elif spatialite: create temp table
   ```

2. **Geometric Filtering** (line ~569)
   ```python
   find_symbol("execute_geometric_filtering", relative_path="modules/appTasks.py", include_body=True)
   # Add Spatialite branch between PostgreSQL and fallback
   ```

## Tips for Efficient Use

### Do's ✅
- ✅ Use `get_symbols_overview()` before reading full files
- ✅ Use `find_symbol()` with `include_body=False` first to understand structure
- ✅ Use `depth=1` to see methods of a class
- ✅ Use `find_referencing_symbols()` to understand dependencies
- ✅ Use `search_for_pattern()` for regex searches across codebase
- ✅ Use symbolic editing tools (`replace_symbol_body`, `insert_after_symbol`)

### Don'ts ❌
- ❌ Don't read entire files unless absolutely necessary
- ❌ Don't read same content multiple times
- ❌ Don't use full file reads when symbolic tools can give you what you need
- ❌ Don't forget to use `relative_path` parameter to restrict searches

## Memory Files

### project_memory.md
This is the main memory file. It contains:
- Complete architecture overview
- All key symbols documented
- Migration status (Phase 1 complete)
- Code patterns and guidelines
- Quick references

Update this file when:
- Completing a new phase
- Adding major features
- Discovering new patterns
- Learning new architecture details

### Adding New Memories

Use `write_memory()` to add specialized memories:
```python
write_memory(
    memory_file_name="spatialite_backend.md",
    content="# Spatialite Backend Implementation\n\n..."
)
```

## Current Project Status

✅ **Phase 1 Complete**: PostgreSQL is now optional
- Import conditional implemented
- POSTGRESQL_AVAILABLE flag added
- Graceful degradation working

🔄 **Phase 2 In Progress**: Spatialite backend implementation
- Next: Create `create_temp_spatialite_table()`
- Next: Create `qgis_expression_to_spatialite()`
- Next: Adapt geometric filtering

## Resources

- Main documentation: Root `*.md` files
- Migration guide: `MIGRATION_GUIDE.md`
- Detailed plan: `TODO.md`
- Technical audit: `AUDIT_FILTERMATE.md`

---

**Created**: 2 December 2025  
**For**: Serena symbolic code analysis  
**Project**: FilterMate QGIS Plugin
