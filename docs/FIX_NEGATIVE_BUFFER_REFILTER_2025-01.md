# FIX: Negative Buffer Refiltering Returns All Features (v2.7.10)

## Issue Summary

When applying a negative buffer (erosion, e.g., -500m) to a single selected feature (e.g., commune fid=135) during **refiltering** (second filter operation), the result incorrectly returned ALL features instead of only the features intersecting the eroded geometry.

### Symptoms

1. **First filter (no buffer)**: Works correctly - returns expected number of features (e.g., 116 batiment)
2. **Second filter (-500m buffer)**: Returns ALL features in the distant layer (e.g., 738,254 batiment)

### User Report

```
- Source layer: commune (PostgreSQL, 930 features)
- Single selection: Toulouse (fid=135)
- Buffer: -500 meters (erosion/shrink)
- CRS: EPSG:2154 (French Lambert-93)
- Distant layer: batiment (738,254 features total)
```

Expected: ~100 features intersecting the shrunk commune polygon
Actual: 738,254 features (ALL batiment)

## Root Cause Analysis

### Technical Flow

1. **First filter**: Creates EXISTS expression on source layer

   - Source layer subsetString = `EXISTS (SELECT 1 FROM "public"."commune" AS __source WHERE ST_Intersects(...))`

2. **Second filter (with -500m buffer)**:
   - WKT becomes 4.6M characters (exceeds MAX_WKT_LENGTH of 100K)
   - PostgreSQL backend switches from simple WKT mode to EXISTS subquery mode
   - `source_subset = layer.subsetString()` returns the EXISTS expression from step 1
   - `source_filter = source_subset` (the EXISTS expression)
3. **Bug location**: In `postgresql_backend.build_expression()` (lines 1143-1148):
   ```python
   skip_filter = any(pattern in source_filter_upper for pattern in [
       '__SOURCE',
       'EXISTS(',
       'EXISTS ('
   ])
   ```
4. **Result**: The source_filter containing EXISTS is SKIPPED
   - EXISTS subquery has NO filter on source features
   - Matches ALL source features (all 930 communes)
   - Distant layer filter matches ALL features that intersect ANY commune

### The Fix (v2.7.10)

In `filter_task.py` `_build_backend_expression()`, before using source_subset as source_filter, check if it contains patterns that would be skipped in the backend:

```python
# CRITICAL FIX v2.7.10: Check if source_subset contains patterns that would be SKIPPED
# in postgresql_backend.build_expression(). If so, we should NOT use it as source_filter
# because it would be skipped anyway, leaving no filter and matching ALL features.
# Instead, fall through to generate filter from task_features.

skip_source_subset = False
if source_subset:
    source_subset_upper = source_subset.upper()
    skip_source_subset = any(pattern in source_subset_upper for pattern in [
        '__SOURCE',
        'EXISTS(',
        'EXISTS ('
    ])
    # Also check for MV references
    if not skip_source_subset:
        skip_source_subset = bool(re.search(
            r'IN\s*\(\s*SELECT.*FROM\s+["\']?filter_mate_temp["\']?\s*\.\s*["\']?mv_',
            source_subset,
            re.IGNORECASE | re.DOTALL
        ))

    if skip_source_subset:
        logger.info("⚠️ PostgreSQL EXISTS: Source subset contains patterns that would be skipped")
        logger.info("   → Falling through to generate filter from task_features instead")

if source_subset and not skip_source_subset:
    source_filter = source_subset  # Use as-is
else:
    # Fall through to generate filter from task_features
    # This creates: "commune"."fid" IN (135)
```

## Affected Files

1. **modules/tasks/filter_task.py** - Added skip_source_subset check in `_build_backend_expression()`

## Testing

### Manual Test Case

1. Load PostgreSQL layers: commune (source) and batiment (distant)
2. Select single commune (e.g., Toulouse, fid=135)
3. Apply first filter (no buffer) - verify correct feature count (~116)
4. Apply second filter with -500m buffer - verify reduced feature count (not ALL features)

### Expected Log Output

With the fix:

```
⚠️ PostgreSQL EXISTS: Source subset contains patterns that would be skipped
   Subset preview: 'EXISTS (SELECT 1 FROM "public"."commune" AS __source WHERE ST_Intersects...'
   → Falling through to generate filter from task_features instead
🎯 PostgreSQL EXISTS: Generated selection filter from 1 features
   Filter: "commune"."fid" IN (135)...
```

## Related Issues

- v2.7.5: PostgreSQL geometric filtering with negative buffer causes "missing FROM-clause entry" SQL error
- v2.7.6: PostgreSQL EXISTS subquery ignores selected features when WKT is too long

## Date

January 2025
