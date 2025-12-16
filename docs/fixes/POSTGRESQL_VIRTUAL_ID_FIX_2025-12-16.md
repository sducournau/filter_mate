# PostgreSQL Virtual ID Error Fix

**Date:** 2025-12-16  
**Severity:** CRITICAL  
**Component:** Layer Management Task  
**Issue:** PostgreSQL queries failing with "column virtual_id does not exist"

## Problem Description

FilterMate was attempting to use a virtual field (`virtual_id`) in SQL queries executed on PostgreSQL, causing database errors:

```
ERROR: column Distribution Cluster.virtual_id does not exist
LINE 1: ...LECT * FROM "public"."Distribution Cluster" WHERE "Distribut...
```

### Root Cause

When a PostgreSQL layer lacks a unique field or primary key, `search_primary_key_from_layer()` attempted to create a fallback `virtual_id` field using QGIS's `addExpressionField()`:

```python
# PROBLEMATIC CODE (before fix)
new_field = QgsField('virtual_id', QMetaType.Type.LongLong)
layer.addExpressionField('@row_number', new_field)
return ('virtual_id', layer.fields().indexFromName('virtual_id'), new_field.typeName(), True)
```

**The Critical Flaw:**
- `addExpressionField()` creates a **client-side virtual field** that only exists in QGIS memory
- This field is **NOT stored in the PostgreSQL database**
- When FilterMate builds SQL queries like `WHERE "table"."virtual_id" IN (...)`, PostgreSQL rejects them because the column doesn't exist in the actual database schema

### Where It Failed

The virtual field was stored as `primary_key_name` in layer properties, then used in SQL queries:

```python
# Example from filter_task.py:3824
query = f"""
    WHERE {primary_key_name} IN ({sql_subset_string})
"""
```

When `primary_key_name = "virtual_id"`, PostgreSQL received:
```sql
SELECT * FROM "public"."Distribution Cluster" 
WHERE "Distribution Cluster"."virtual_id" IN (...)
-- ERROR: column virtual_id does not exist
```

## Solution

### Code Changes

Modified `LayersManagementEngineTask.search_primary_key_from_layer()` in `modules/tasks/layer_management_task.py`:

```python
# AFTER: lines ~781-790
# CRITICAL: For PostgreSQL layers, we CANNOT use virtual fields in SQL queries
# Virtual fields only exist in QGIS memory, not in the actual database
layer_provider = layer.providerType()
if layer_provider == 'postgres':
    error_msg = (
        f"Couche PostgreSQL '{layer.name()}' : Aucun champ unique trouvé.\n\n"
        f"FilterMate ne peut pas utiliser de champ virtuel (virtual_id) avec PostgreSQL "
        f"car les champs virtuels n'existent que dans QGIS, pas dans la base de données.\n\n"
        f"Solution : Ajoutez une contrainte PRIMARY KEY ou utilisez une colonne unique dans votre table PostgreSQL."
    )
    logger.error(error_msg)
    raise ValueError(error_msg)
    
# For non-PostgreSQL layers (memory, shapefile, etc.), create virtual ID
new_field = QgsField('virtual_id', QMetaType.Type.LongLong)
layer.addExpressionField('@row_number', new_field)
logger.warning(f"Layer {layer.name()}: No unique field found, created virtual_id (only works for non-database layers)")
return ('virtual_id', layer.fields().indexFromName('virtual_id'), new_field.typeName(), True)
```

### Behavior Changes

| Layer Type | Has Unique Field | Old Behavior | New Behavior |
|------------|------------------|--------------|--------------|
| PostgreSQL | ✅ Yes | Uses real field | ✅ Uses real field (unchanged) |
| PostgreSQL | ❌ No | Creates `virtual_id` → **SQL error** | ⚠️ **Raises ValueError with helpful message** |
| Shapefile/GeoPackage | ❌ No | Creates `virtual_id` (works) | ✅ Creates `virtual_id` (unchanged) |

### User Experience

**Before Fix:**
```
ERROR: column Distribution Cluster.virtual_id does not exist
[Cryptic PostgreSQL error in logs]
```

**After Fix:**
```
FilterMate Error:
Couche PostgreSQL 'Distribution Cluster' : Aucun champ unique trouvé.

FilterMate ne peut pas utiliser de champ virtuel (virtual_id) avec PostgreSQL 
car les champs virtuels n'existent que dans QGIS, pas dans la base de données.

Solution : Ajoutez une contrainte PRIMARY KEY ou utilisez une colonne unique dans votre table PostgreSQL.
```

## User Action Required

### If You're Seeing This Error NOW (Existing Corrupted Layers)

Your FilterMate database contains corrupted layer properties from before this fix was applied. **Use the cleanup tool:**

```bash
# From command line
cd /path/to/filter_mate/tools
python cleanup_postgresql_virtual_id.py

# Or from QGIS Python console
exec(open('/path/to/filter_mate/tools/cleanup_postgresql_virtual_id.py').read())
```

The cleanup tool will:
1. ✅ Automatically detect corrupted PostgreSQL layers
2. 💾 Create a backup of your database
3. 🧹 Remove corrupted layer properties
4. 📋 Show you which PostgreSQL tables need PRIMARY KEY constraints

### After Cleanup or For New Layers

If you encounter this error, **one of these solutions** is required:

### Option 1: Add Primary Key (Recommended)
```sql
-- Add a proper primary key to your PostgreSQL table
ALTER TABLE "Distribution Cluster" 
ADD COLUMN id SERIAL PRIMARY KEY;
```

### Option 2: Use Existing Unique Column
```sql
-- If you have a column that should be unique
ALTER TABLE "Distribution Cluster"
ADD CONSTRAINT distribution_cluster_pkey PRIMARY KEY (existing_id_column);
```

### Option 3: Add Unique Constraint
```sql
-- If you have a unique field but no primary key declared
ALTER TABLE "Distribution Cluster"
ADD CONSTRAINT distribution_cluster_unique UNIQUE (unique_field);
```

### Option 4: Use OGR/Shapefile Format
If you cannot modify the PostgreSQL schema, export the layer to a client-side format:
- Shapefile
- GeoPackage
- Memory layer

These formats support `virtual_id` because they don't execute server-side SQL.

## Testing

Added test case in `tests/test_postgresql_layer_handling.py`:

```python
def test_postgresql_layer_without_primary_key_rejected(self):
    """
    Test that PostgreSQL layers without a unique field are rejected.
    
    Virtual fields (like virtual_id) cannot be used in SQL queries that 
    execute on the PostgreSQL server, so layers without a real unique 
    field must be rejected.
    """
    # Test implementation...
```

## Technical Background

### Why Virtual Fields Exist

QGIS virtual fields (created via `addExpressionField()`) are useful for:
- Client-side calculations (e.g., `@row_number`, geometry area)
- Display-only fields in attribute tables
- Fields derived from expressions

### Why They Fail with PostgreSQL

```
┌─────────────────────────────────┐
│ QGIS Application (Client)       │
│                                  │
│ Virtual Field: virtual_id        │ ← Only exists here
│ Expression: @row_number          │
└─────────────┬───────────────────┘
              │ SQL Query
              │ WHERE "table"."virtual_id" IN (...)
              ▼
┌─────────────────────────────────┐
│ PostgreSQL Server               │
│                                  │
│ Table Schema:                    │
│   - name VARCHAR                 │
│   - status VARCHAR               │
│   ❌ virtual_id (DOES NOT EXIST) │ ← Error!
└─────────────────────────────────┘
```

When FilterMate sends `WHERE "table"."virtual_id" IN (...)` to PostgreSQL, the server looks for a column named `virtual_id` in the actual table schema. Since it doesn't exist, PostgreSQL returns an error.

### Why It Works with Shapefiles

```
┌─────────────────────────────────┐
│ QGIS Application (Client)       │
│                                  │
│ Shapefile in Memory              │
│ Virtual Field: virtual_id        │
│ Expression: @row_number          │
│                                  │
│ ✅ All filtering done client-side │
│ ✅ Virtual fields accessible      │
└─────────────────────────────────┘
```

With shapefiles/GeoPackage/memory layers, QGIS does all filtering client-side, so virtual fields are accessible.

## Related Issues

- Logs showing: `reparamètrage de la connexion incorrecte` (connection reconfiguration warnings)
- SQL queries with `IN (None)` indicate missing/invalid primary key values

## Prevention

1. **Always define primary keys** on PostgreSQL tables used with FilterMate
2. **Use unique columns** (id, uuid, serial) for all feature tables
3. **Test layer properties** after adding to project to verify unique field detection

## References

- QGIS API: [`QgsVectorLayer.addExpressionField()`](https://qgis.org/pyqgis/latest/core/QgsVectorLayer.html#qgis.core.QgsVectorLayer.addExpressionField)
- PostgreSQL Documentation: [Primary Keys](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-PRIMARY-KEYS)
- FilterMate Layer Management: `modules/tasks/layer_management_task.py`
