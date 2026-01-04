# FIX: Spatialite GeoPackage Freeze on Complex Geometries

**Version**: 2.8.8  
**Date**: January 5, 2026  
**Issue**: QGIS freezes when filtering Spatialite/GeoPackage with complex geometries (e.g., Toulouse commune)

## Problem Description

When using FilterMate with:

- **Backend**: Spatialite
- **Data Source**: GeoPackage (.gpkg)
- **Source Geometry**: Complex polygon (e.g., administrative boundary like "Toulouse")

QGIS would freeze (show "Ne répond pas") at **TWO stages**:

### Stage 1: Geometry Insertion (FIXED in v2.8.7)

- `GeomFromText()` on very complex WKT (100KB+ with thousands of vertices) blocks indefinitely
- The geometry insertion in `_create_permanent_source_table()` was NOT using the interruptible query mechanism

### Stage 2: setSubsetString Application (FIXED in v2.8.7)

- After spatial query returns 235,367 matching FIDs for "batiment" layer
- Building expression `fid IN (1,2,3,...235367)` creates ~1.5MB string
- `setSubsetString()` parsing this massive expression blocks the main thread

### Stage 3: Re-filtering Returns ALL Features (FIXED in v2.8.8)

**NEW BUG FIXED**: When re-filtering with buffer (e.g., second filter pass), layers in DIRECT SQL or SOURCE TABLE mode would return ALL features from the table instead of respecting the previous filter.

**Symptom**: First filter returns 229 features, second filter with buffer returns 9961 features (total table count).

**Root Cause**: The SQL query in both `_apply_filter_direct_sql()` and `_apply_filter_with_source_table()` did not include the `old_subset` (previous FID filter) in the WHERE clause:

```python
# BEFORE (v2.8.7) - queries entire table
select_query = f'SELECT "{pk_col}" FROM "{table_name}" WHERE {expression}'

# AFTER (v2.8.8) - respects previous FID filter
select_query = f'SELECT "{pk_col}" FROM "{table_name}" WHERE ({old_subset}) AND {expression}'
```

## Root Cause

### Problem 1: Geometry Insertion

```python
# BEFORE (blocking - could freeze indefinitely)
cursor.execute(f'''
    INSERT INTO "{table_name}" (source_fid, geom)
    VALUES (0, GeomFromText(?, ?))
''', (source_wkt, source_srid))
```

### Problem 2: Massive FID IN Expression

```python
# BEFORE - generates ~1.5MB expression for 235K FIDs
fid_expression = f'"{pk_col}" IN ({", ".join(str(fid) for fid in matching_fids)})'
# Result: fid IN (1, 2, 3, ... 235367) <- QGIS freezes parsing this
```

**Note**: We initially tried using a FID table with subquery
(`fid IN (SELECT fid FROM _fm_fids_xxx)`), but OGR `setSubsetString()` does NOT
support subqueries - it can only parse simple expressions.

## Solution

### 1. Python-Side Geometry Simplification

Added `_simplify_wkt_if_needed()` method that:

- Detects WKT > 100KB (threshold: `SPATIALITE_WKT_SIMPLIFY_THRESHOLD`)
- Counts vertices and simplifies if > 5000 (threshold: `SPATIALITE_WKT_MAX_POINTS`)
- Uses QGIS `QgsGeometry.simplify()` with adaptive tolerance
- Runs BEFORE sending to SQLite, making it interruptible

### 2. Interruptible Geometry Insertion

Changed geometry insertion to use `InterruptibleSQLiteQuery`:

```python
# AFTER (with timeout and cancellation support)
insert_sql = f'''
    INSERT INTO "{table_name}" (source_fid, geom)
    VALUES (0, GeomFromText('{simplified_wkt}', {source_srid}))
'''
interruptible = InterruptibleSQLiteQuery(conn, insert_sql)
_, error = interruptible.execute(
    timeout=SPATIALITE_GEOM_INSERT_TIMEOUT,  # 30 seconds
    cancel_check=self._is_task_canceled
)
```

### 3. Range-Based FID Filter (v2.8.7 - Stage 2 Fix)

Added `_build_range_based_filter()` method that converts FID lists to BETWEEN ranges:

```python
# BEFORE - 235K FIDs = ~1.5MB expression
fid IN (1, 2, 3, 4, 5, 8, 9, 10, 15, ...)

# AFTER - same FIDs = ~10KB expression (99% reduction!)
("fid" BETWEEN 1 AND 5) OR ("fid" BETWEEN 8 AND 10) OR "fid" IN (15, ...)
```

This works because:

- Spatial data often has consecutive FIDs for nearby features
- BETWEEN ranges are trivial for QGIS to parse
- Compression ratio depends on data, but typically 90-99% reduction

### 4. Include Previous FID Filter in SQL Query (v2.8.8 - Stage 3 Fix)

**NEW FIX**: Both `_apply_filter_direct_sql()` and `_apply_filter_with_source_table()` now analyze `old_subset` and include simple FID filters in the SQL query:

```python
# v2.8.8: Detect if old_subset is a simple FID filter (not spatial predicate)
old_subset_sql_filter = ""
if old_subset:
    has_spatial_predicate = any(pred in old_subset.upper() for pred in [
        'ST_INTERSECTS', 'ST_CONTAINS', 'GEOMFROMTEXT', ...
    ])

    if not has_spatial_predicate:
        # Include previous FID filter in SQL query
        old_subset_sql_filter = f"({old_subset}) AND "

select_query = f'SELECT "{pk_col}" FROM "{table_name}" WHERE {old_subset_sql_filter}{expression}'
```

This ensures that when re-filtering (e.g., adding buffer), only the **previously filtered features** are queried, not the entire table.

### 4. New Constants

```python
# v2.8.7: Thresholds
SPATIALITE_WKT_SIMPLIFY_THRESHOLD = 100000  # 100KB - trigger Python simplification
SPATIALITE_WKT_MAX_POINTS = 5000  # Max points before aggressive simplification
SPATIALITE_GEOM_INSERT_TIMEOUT = 30  # Timeout for geometry insertion (seconds)
LARGE_FID_TABLE_THRESHOLD = 20000  # Use range-based filter above this count
```

## Files Modified

- `modules/backends/spatialite_backend.py`:
  - Added constants for simplification thresholds
  - Added `_simplify_wkt_if_needed()` method
  - Added `_build_range_based_filter()` method (converts FIDs to BETWEEN ranges)
  - Modified `_create_permanent_source_table()` to use simplification and interruptible queries
  - Modified `_apply_filter_direct_sql()` to use range-based filter for large FID sets
  - Modified `_apply_filter_with_source_table()` to use range-based filter
  - Changed SQLite connection to use `check_same_thread=False` for thread support

## Testing

1. Load a GeoPackage with commune boundaries
2. Select "Toulouse" (or any complex polygon)
3. Apply geometric filter to multiple layers (including large layers like "batiment")
4. Verify:
   - No freeze occurs during geometry insertion
   - No freeze occurs during filter application
   - Logs show "📊 RANGE filter" or "📊 FID analysis" messages
   - Logs show compression ratio (e.g., "1,500,000 → 10,000 chars (99.3% reduction)")
   - Filter completes successfully

## Performance Impact

- **Small geometries (< 100KB)**: No change
- **Large geometries (> 100KB)**:

  - Python simplification adds ~1-2s processing time
  - Prevents indefinite freeze

- **Small FID sets (< 20K)**: No change
- **Large FID sets (> 20K)**:
  - Range-based filter dramatically reduces expression size
  - QGIS parses the expression almost instantly
  - Actual filtering performance unchanged (SQLite handles BETWEEN efficiently)

## Fallback Behavior

If geometry insertion still times out after 30 seconds:

1. Error is logged to QGIS MessageLog
2. Error message suggests using OGR backend instead
3. Filter operation fails gracefully (no crash)

If FID distribution is very sparse (few consecutive FIDs):

1. Range-based filter still works but with less compression
2. Fallback to chunked IN filter if needed
3. Warning suggests using PostgreSQL for better performance

## Related Issues

- `FIX_FREEZE_LARGE_EXPRESSIONS_2025-06.md` - Similar freeze issue with large expressions
- `PERFORMANCE_OPTIMIZATION_v2.5.10.md` - R-tree optimization for large datasets
