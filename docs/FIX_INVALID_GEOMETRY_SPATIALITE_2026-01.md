# Fix: Invalid Source Geometry Handling (v2.9.6)

## Date: January 6, 2026

## Problem

Filtering multiple layers from the same GeoPackage with Spatialite backend was returning 0 results for some layers, even though valid features existed within the filter zone.

### Symptoms

```
WARNING    🔍 structures DIAG: source_geom valid=0, empty=0, type=MULTIPOLYGON, npoints=106
WARNING    ⚠️ structures: Source geometry is INVALID - this explains 0 results!
```

- Layer `structures`: 0 features (should have matched many)
- Layer `sheaths`: 0 features  
- Layer `zone_drop`: 0 features
- Other layers like `ducts`, `subducts`: worked correctly

### Root Cause

The source geometry (the filtering polygon selected in the UI) was **geometrically invalid** according to spatial database validation functions. Common reasons:

1. Self-intersecting polygons
2. Duplicate points in polygon rings
3. Improperly closed rings
4. Geometry artifacts from previous operations

When an invalid geometry is used in spatial predicates (`ST_Intersects`, etc.), databases return 0 results instead of failing gracefully.

## Solution

Added geometry validation (`MakeValid()`/`ST_MakeValid()`) to **all** source geometry expressions across all backends.

---

## Backend-Specific Changes

### 1. Spatialite Backend (`spatialite_backend.py`)

#### `build_expression()` - Inline WKT expressions

```python
# Before (v2.9.5):
source_geom_expr = f"GeomFromText('{source_geom}', {source_srid})"

# After (v2.9.6):
source_geom_expr = f"MakeValid(GeomFromText('{source_geom}', {source_srid}))"
```

#### `_create_permanent_source_table()` - All INSERT statements

All geometry insertions now use `MakeValid()`:

```python
INSERT INTO "{table_name}" (source_fid, geom, geom_buffered)
VALUES ({fid}, MakeValid(GeomFromText('...', {srid})), 
        ST_Buffer(MakeValid(GeomFromText('...', {srid})), {buffer}))
```

---

### 2. PostgreSQL Backend (`postgresql_backend.py`)

#### `_build_simple_wkt_expression()` - WKT geometry construction

```python
# Before (v2.9.5):
source_geom_sql = f"ST_GeomFromText('{source_wkt}', {source_srid})"

# After (v2.9.6):
source_geom_sql = f"ST_MakeValid(ST_GeomFromText('{source_wkt}', {source_srid}))"
```

#### Raw WKT Wrapping (Strategy 2)

```python
# Before:
source_geom_sql = f"ST_GeomFromText('{source_geom}', {fallback_srid})"

# After:
source_geom_sql = f"ST_MakeValid(ST_GeomFromText('{source_geom}', {fallback_srid}))"
```

---

### 3. OGR Backend (`ogr_backend.py`)

The OGR backend **already handles** invalid geometries correctly:

- Uses `create_geos_safe_layer()` which calls `geom.makeValid()` on each geometry
- Processing context set to `GeometrySkipInvalid` for graceful handling
- No changes required for this fix

---

## Technical Notes

### MakeValid() vs ST_MakeValid()

| Database   | Function       | Notes                                    |
|------------|----------------|------------------------------------------|
| Spatialite | `MakeValid()`  | Without ST_ prefix                       |
| PostgreSQL | `ST_MakeValid()` | Standard PostGIS function              |
| QGIS/OGR   | `geom.makeValid()` | Python QgsGeometry method            |

### Performance Impact

- `MakeValid()` / `ST_MakeValid()` adds minimal overhead (~1-5ms per geometry)
- Most source geometries are already valid, so it's essentially a no-op
- The alternative (0 results on valid data) is unacceptable

### What MakeValid() Does

1. Removes self-intersections
2. Fixes ring orientations (outer CCW, inner CW)
3. Removes duplicate consecutive points
4. Closes unclosed rings
5. Returns valid geometry or EMPTY if unfixable

---

## Files Modified

| File | Changes |
|------|---------|
| `modules/backends/spatialite_backend.py` | Added `MakeValid()` to `build_expression()` and `_create_permanent_source_table()` |
| `modules/backends/postgresql_backend.py` | Added `ST_MakeValid()` to `_build_simple_wkt_expression()` and raw WKT wrapping |
| `modules/backends/ogr_backend.py` | Already uses `create_geos_safe_layer()` - no changes |
| `metadata.txt` | Version 2.9.6 |

---

## Testing

### Before Fix

```
structures: 0 features (source_geom valid=0)
sheaths: 0 features
zone_drop: 0 features
```

### After Fix

All layers should return correct feature counts based on spatial intersection with the filter zone.

---

## Related Issues

- v2.3.9: Initial MakeValid() support for negative buffers only
- v2.8.11: Extended MakeValid() to negative buffer geometries
- v2.9.6: Extended to **all** source geometries (this fix)

## Version History

| Version | Change |
|---------|--------|
| v2.9.6 | Added MakeValid()/ST_MakeValid() to all source geometry insertions and expressions |
| v2.8.11 | Added MakeValid() to negative buffer geometries only |
| v2.3.9 | Initial MakeValid() support for negative buffers in PostgreSQL |
