# Negative Buffer & WKT Generation - FilterMate

**Last Updated:** December 29, 2025
**Versions Covered:** v2.3.9 - v2.5.5+

## Overview

This document details how FilterMate handles negative buffers (erosion) during WKT generation and SQL expression building for both PostgreSQL and Spatialite backends.

## Critical Architecture Decision

**Buffer is applied via SQL, NOT in Python WKT preparation!**

The `prepare_spatialite_source_geom()` function generates raw WKT geometry **without** buffer. The buffer is then applied via:
- PostgreSQL: `ST_Buffer()` function
- Spatialite: `ST_Buffer()` function  
- OGR: QGIS Processing `native:buffer` algorithm

This design choice avoids:
1. GeometryCollection issues from QGIS buffer
2. Memory overhead of buffering in Python
3. Inconsistent behavior across backends

## PostgreSQL Backend

### Key Functions

| Function | Lines | Purpose |
|----------|-------|---------|
| `_build_st_buffer_with_style()` | 140-190 | Apply buffer with endcap style |
| `_build_simple_wkt_expression()` | 582-663 | WKT mode for <50 features |
| `build_expression()` EXISTS path | 830-950 | Subquery mode for large datasets |

### Negative Buffer SQL Pattern

```sql
-- PostgreSQL pattern (v2.5.4+)
CASE 
    WHEN ST_IsEmpty(ST_MakeValid(ST_Buffer(geom, -10))) 
    THEN NULL 
    ELSE ST_MakeValid(ST_Buffer(geom, -10)) 
END
```

**Safety mechanisms:**
1. `ST_MakeValid()` - Ensures valid geometry after erosion
2. `ST_IsEmpty()` - Detects ALL empty geometry types (not just GEOMETRYCOLLECTION EMPTY)
3. `NULL` return - Prevents false positive matches in spatial queries

### Geographic CRS Handling

For geographic CRS (EPSG:4326), buffer requires transformation:
```sql
ST_Transform(
    ST_Buffer(
        ST_Transform(ST_GeomFromText('WKT', 4326), 3857), 
        -10  -- meters in EPSG:3857
    ), 
    4326
)
```

## Spatialite Backend

### Key Functions

| Function | Lines | Purpose |
|----------|-------|---------|
| `_build_st_buffer_with_style()` | 226-277 | Apply buffer with endcap style |
| `build_expression()` | 986-1405 | Main expression builder |

### Negative Buffer SQL Pattern

```sql
-- Spatialite pattern (v2.5.5+)
-- Note: MakeValid() instead of ST_MakeValid()
-- Note: ST_IsEmpty() = 1 instead of just ST_IsEmpty()
CASE 
    WHEN ST_IsEmpty(MakeValid(ST_Buffer(geom, -10))) = 1 
    THEN NULL 
    ELSE MakeValid(ST_Buffer(geom, -10)) 
END
```

**Spatialite-specific differences:**
- Uses `MakeValid()` (not `ST_MakeValid()`)
- Boolean comparison: `ST_IsEmpty(...) = 1` (integer, not boolean)
- Uses `GeomFromGPB()` for GeoPackage layers

## WKT Preparation Flow

```
Source Layer Selection
         │
         ▼
prepare_spatialite_source_geom()
    - Collects features (respects subset, selection, task_features)
    - Reprojects if needed
    - Collects geometries into single geometry
    - Converts to WKT (NO buffer applied!)
    - Escapes quotes for SQL
         │
         ▼
self.spatialite_source_geom = wkt_escaped
         │
         ▼
Backend.build_expression()
    - Builds GeomFromText(wkt, srid)
    - Applies ST_Buffer() with buffer_value
    - Wraps negative buffers in MakeValid + ST_IsEmpty check
    - Builds spatial predicate
         │
         ▼
layer.setSubsetString(expression)
```

## Version History

### v2.5.5 (December 2025)
- Fixed Spatialite `ST_IsEmpty()` check (returns integer, not boolean)
- Consistent handling across all backends

### v2.5.4 (December 2025)
- Fixed PostgreSQL bug where `NULLIF` only detected `GEOMETRYCOLLECTION EMPTY`
- Now uses `ST_IsEmpty()` to detect all empty geometry types

### v2.4.23
- Initial `ST_IsEmpty()` implementation for empty geometry detection

### v2.3.9
- Added `ST_MakeValid()`/`MakeValid()` wrapping for negative buffers
- Added logging for negative buffer operations

## Test Coverage

File: `tests/test_negative_buffer.py`

| Test Class | Coverage |
|------------|----------|
| `TestNegativeBuffer` | Basic safe_buffer() handling |
| `TestSpatialiteBackendNegativeBuffer` | SQL structure tests |
| `TestOGRBackendNegativeBuffer` | Layer validation tests |
| `TestWKTCacheNegativeBuffer` | Cache key tests |

## Debugging Tips

### Enable Detailed Logging
Negative buffer operations log with emoji:
- `📐 Using negative buffer (erosion): -10m`
- `🛡️ Wrapping negative buffer in MakeValid()`
- `🌍 Geographic CRS detected - applying buffer via EPSG:3857`

### Common Issues

1. **All features disappear after negative buffer**
   - Buffer too large → complete erosion
   - User message displayed via `iface.messageBar().pushWarning()`

2. **SQL syntax error in Spatialite**
   - Check `MakeValid()` vs `ST_MakeValid()`
   - Check `= 1` comparison for boolean

3. **Cache returns wrong geometry**
   - Cache key includes buffer value
   - Negative/positive buffers have different keys
   - Clear cache if WKT type is wrong (LineString when Polygon expected)

## Related Documentation

- [docs/FIX_NEGATIVE_BUFFER_2025-12.md](../docs/FIX_NEGATIVE_BUFFER_2025-12.md)
- [docs/NEGATIVE_BUFFER_FIX_README.md](../docs/NEGATIVE_BUFFER_FIX_README.md)
