# Fix: Zoom and Identification for Imported GPKG Layers

## Problem Description

When importing layers from GeoPackage files with different display names (e.g., "Distribution Cluster") and table names (e.g., "mro_woluwe_03_pop_033"), the zoom and identification features were not working correctly.

### Root Cause

The plugin was using `layer.name()` (display name in QGIS) for database queries, but this doesn't always match the actual source table name. For layers imported from GeoPackage files, the display name can differ from the actual table name in the file.

## Solution

### 1. New Function: `get_source_table_name()`

Added a new utility function in `modules/appUtils.py` that extracts the actual source table name from a layer's data source URI:

```python
def get_source_table_name(layer):
    """
    Extract the actual source table name from a layer's data source.
    
    Supports:
    - PostgreSQL layers
    - Spatialite layers  
    - OGR/GeoPackage layers (with |layername= parameter)
    - Shapefiles (uses filename)
    
    Returns the source table name, or layer.name() as fallback.
    """
```

### 2. New Property: `layer_table_name`

Added a new field `layer_table_name` to layer properties that stores the actual source table name, separate from `layer_name` (display name).

**Modified files:**
- `modules/appTasks.py`: 
  - Updated `json_template_layer_infos` to include `layer_table_name`
  - Modified `_build_new_layer_properties()` to extract and store source table name
  - Updated `_migrate_legacy_geometry_field()` to add `layer_table_name` for existing layers
  - Modified `_load_existing_layer_properties()` to handle property count changes gracefully

### 3. Backend Updates

Updated all backends to use `layer_table_name` instead of `layer_name` for SQL queries:

**Modified files:**
- `modules/backends/spatialite_backend.py`: Line 322
- `modules/backends/postgresql_backend.py`: Line 83

Both backends now use:
```python
table = layer_props.get("layer_table_name") or layer_props.get("layer_name")
```

This provides backward compatibility with layers that don't have `layer_table_name` yet.

### 4. Automatic Migration

Existing layers without `layer_table_name` will be automatically migrated:
- When a layer is loaded, the migration function checks for missing `layer_table_name`
- Extracts the source table name using `get_source_table_name()`
- Adds it to the database and layer variables
- Sets the QGIS layer variable `filterMate_infos_layer_table_name`

## Testing

### Test Cases

1. **New GeoPackage layers**: Table name extracted correctly on import
2. **Existing layers**: Automatically migrated with correct table name
3. **PostgreSQL layers**: Schema and table extracted correctly
4. **Shapefiles**: Filename used as table name
5. **Memory layers**: Fallback to display name

### Manual Testing Steps

1. Create a new QGIS project
2. Import a GeoPackage layer with different display name and table name
3. Apply a filter using FilterMate
4. Use the zoom and identify buttons in the exploring panel
5. Verify that zoom and identification work correctly

## Impact

- **Backward Compatible**: Existing projects will work without modification
- **Automatic Migration**: No user intervention required
- **Performance**: No performance impact (table name extracted once at layer load)

## Files Changed

1. `modules/appUtils.py`: Added `get_source_table_name()` function
2. `modules/appTasks.py`: Added `layer_table_name` property and migration logic
3. `modules/backends/spatialite_backend.py`: Updated to use `layer_table_name`
4. `modules/backends/postgresql_backend.py`: Updated to use `layer_table_name`
5. `tests/test_source_table_name.py`: Added unit tests

## Related Issues

This fix resolves issues where:
- Zoom to features doesn't work for imported GPKG layers
- Identification doesn't work for imported GPKG layers
- SQL queries fail because table name doesn't match display name

## Future Improvements

- Add validation to warn users if table name extraction fails
- Add a UI element to show both display name and source table name
- Consider renaming `layer_name` to `layer_display_name` for clarity (major refactoring)
