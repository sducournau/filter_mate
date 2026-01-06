# Fix: Spatialite FID Subquery Filter Not Working (v2.8.9)

**Date:** January 2026  
**Version:** v2.8.9  
**Issue:** Filtered layers show no features when using Spatialite backend with large datasets

## Problem Description

When filtering layers with the Spatialite backend on datasets with ≥20,000 matching features, the filter expression generated was:

```sql
"fid" IN (SELECT fid FROM "_fm_fids_1767613249_f9e935")
```

This subquery-based filter **does NOT work** with QGIS's OGR provider because:

1. The expression is passed to `layer.setSubsetString()` which interprets it as an OGR SQL filter
2. OGR's SQL parser does not support subqueries in filter expressions
3. The `_fm_fids_xxx` temporary table exists in the GeoPackage file, but the OGR provider cannot access it via subquery

## Symptoms

- Layer filter appears to be applied but shows 0 features (or incorrect features)
- Log shows: `"fid" IN (SELECT fid FROM "_fm_fids_xxx")`
- Works correctly for smaller datasets (<20K features) that don't trigger the FID table optimization

## Root Cause

In v2.8.7, the `_build_fid_table_filter()` method was introduced to avoid QGIS freezing when parsing very long IN() expressions with >20K FIDs. It created a temporary table with FIDs and used a subquery to reference it.

However, this approach only works with **direct SQLite connections**, not with **QGIS setSubsetString()** which uses the OGR provider's SQL parser.

## Solution

Modified the filtering logic to use `_build_range_based_filter()` instead of `_build_fid_table_filter()` for large datasets:

- **Before (v2.8.7-v2.8.8):** `"fid" IN (SELECT fid FROM "_fm_fids_xxx")` ❌
- **After (v2.8.9):** `("fid" BETWEEN 1 AND 500) OR ("fid" BETWEEN 502 AND 1000) OR ...` ✅

The range-based approach:

1. Detects consecutive FID ranges and uses BETWEEN clauses
2. Groups non-consecutive FIDs into IN() chunks of ≤1000
3. Is compatible with all OGR providers (GeoPackage, Shapefile, etc.)
4. Provides significant compression for typical datasets

## Changes Made

### `modules/backends/spatialite_backend.py`

1. **Line ~2982** (`_apply_filter_direct_sql`): Changed to use `_build_range_based_filter()` directly
2. **Line ~3708** (`_apply_filter_with_source_table`): Changed to use `_build_range_based_filter()` directly
3. **Deprecated** `_build_fid_table_filter()` method with documentation explaining the limitation

## Testing

1. Load a GeoPackage with >20K features
2. Apply a spatial filter using Spatialite backend
3. Verify the filter expression uses BETWEEN/IN() clauses instead of subquery
4. Confirm features are correctly filtered

## Related Files

- `modules/backends/spatialite_backend.py` - Main fix location
- `docs/FIX_SPATIALITE_FREEZE_2026-01.md` - Previous freeze fix documentation
