# Fix: OGR Backend Failing with Invalid Source Geometry

## Date
2026-01-06

## Version
v2.9.9

## Problem Description

FilterMate was reporting "Failed layers: Drop Cluster, End Cable. Try OGR backend or check Python console" when filtering multiple OGR layers. The error occurred because:

1. `prepare_ogr_source_geom()` was creating a memory layer for the source geometry
2. This layer passed initial validation but became invalid/empty when reused for subsequent layers
3. The OGR backend continued processing even when source geometry was None or invalid
4. Validation failed deep in `_validate_intersect_layer()` with cryptic error messages

## Root Cause

The issue had two components:

1. **Insufficient error handling**: When `_prepare_source_geometry(PROVIDER_OGR)` returned None (because `ogr_source_geom` was invalid), the code logged errors but didn't return False, allowing execution to continue
2. **Late validation**: The OGR backend only validated source geometry existence but not its validity (isValid(), featureCount() > 0) before attempting to use it
3. **Poor diagnostics**: When geometry validation failed, there was no information about WHY it failed (None, Null, Empty, invalid WKT type)

## Solution

### 1. Early Failure in filter_task.py

Added explicit `return False` when `ogr_source_geom` preparation fails:

**Location**: `filter_task.py` lines ~7499-7508 and ~7798-7809

```python
ogr_source_geom = self._prepare_source_geometry(PROVIDER_OGR)

if ogr_source_geom:
    # ... continue processing
else:
    logger.error(f"✗ OGR source geometry preparation returned None for {layer.name()}")
    logger.error(f"  → Cannot perform geometric filtering without valid source geometry")
    logger.error(f"  → Skipping {layer.name()}")
    return False  # FIX v2.9.9: Explicit failure instead of silent continue
```

### 2. Enhanced Source Validation in ogr_backend.py

Added comprehensive validation of source geometry before attempting to use it:

**Location**: `ogr_backend.py` `apply_filter()` method ~line 765-795

```python
source_layer = getattr(self, 'source_geom', None)

if source_layer is None:
    # Log and return False immediately
    return False
elif not isinstance(source_layer, QgsVectorLayer):
    # Log type error and return False
    return False  
elif not source_layer.isValid():
    # FIX v2.9.9: Check if layer was garbage collected
    return False
elif source_layer.featureCount() == 0:
    # FIX v2.9.9: Check if layer has features
    return False
```

### 3. Enhanced Diagnostic Logging

Added detailed diagnostic messages to understand WHY geometry validation fails:

**Location**: `filter_task.py` `prepare_ogr_source_geom()` ~line 5889-5917

```python
if not has_valid_geom:
    logger.error(f"prepare_ogr_source_geom: Final layer has no valid geometries")
    logger.error(f"  → Layer name: {layer.name()}")
    logger.error(f"  → Layer features: {layer.featureCount()}")
    logger.error(f"  → Last invalid reason: {invalid_reason}")  # NEW
    logger.error(f"  → Source layer name: {self.source_layer.name() if self.source_layer else 'None'}")
    logger.error(f"  → Source layer features: {self.source_layer.featureCount() if self.source_layer else 0}")
    # Also log to QGIS MessageLog for visibility
```

Now logs specific reason: "geometry is None", "geometry is Null", "geometry is Empty", or "wkbType=X (Unknown or NoGeometry)"

## Files Modified

1. **modules/tasks/filter_task.py**
   - Lines ~7499-7508: Added explicit failure return for first OGR fallback path
   - Lines ~7798-7809: Added explicit failure return for second OGR fallback path  
   - Lines ~5889-5917: Enhanced diagnostic logging in `prepare_ogr_source_geom()`

2. **modules/backends/ogr_backend.py**
   - Lines ~765-795: Added comprehensive source geometry validation in `apply_filter()`

## Expected Behavior

**Before**:
```
2026-01-06 12:23:03 CRITICAL FilterLayers: Failed layers: Drop Cluster, End Cable. Try OGR backend or check Python console.
```
(No explanation WHY they failed)

**After**:
```
2026-01-06 12:23:03 ERROR FilterMate: ✗ OGR source geometry preparation returned None for Drop Cluster
2026-01-06 12:23:03 ERROR FilterMate:   → Cannot perform geometric filtering without valid source geometry
2026-01-06 12:23:03 ERROR FilterMate:   → Skipping Drop Cluster
2026-01-06 12:23:03 ERROR FilterMate: prepare_ogr_source_geom: Final layer has no valid geometries
2026-01-06 12:23:03 ERROR FilterMate:   → Layer name: source_from_task
2026-01-06 12:23:03 ERROR FilterMate:   → Layer features: 5
2026-01-06 12:23:03 ERROR FilterMate:   → Last invalid reason: geometry is Empty
2026-01-06 12:23:03 CRITICAL FilterLayers: Failed layers: Drop Cluster, End Cable. (clear errors in Python console)
```

Now users can see:
- WHICH layer failed
- WHEN it failed (during source preparation vs during filtering)
- WHY it failed (geometry is Empty, None, Null, or invalid WKT type)
- WHERE the source came from (source layer name and feature count)

## Testing Recommendations

1. Test multi-layer OGR filtering (GeoPackage with 5+ layers)
2. Test with invalid/empty source geometries
3. Check Python console for detailed error messages
4. Verify QGIS MessageLog shows critical errors
5. Test memory layer garbage collection scenarios

## Prevention

To prevent similar issues in the future:

1. **Always return False explicitly** when preparation fails, don't just log errors
2. **Validate layer validity AND feature count**, not just existence (isValid() + featureCount() > 0)
3. **Log the reason for failure**, not just "validation failed"
4. **Use QGIS MessageLog** for critical errors that users must see
5. **Check for garbage collection** of memory layers between operations

## Related Issues

- v2.8.14: Memory layer garbage collection fix (added to project to prevent GC)
- v2.4.x: Thread safety fixes for OGR operations
- v2.9.7: GeometryCollection RTTOPO error fix

## Notes

This fix does NOT solve the underlying problem of WHY the source geometry becomes empty/invalid. It only provides better error handling and diagnostics. The root cause may be:

- Thread safety issues when copying features to memory layers
- Feature deletion during task execution
- Invalid transformation/reprojection
- Subset string application issues

Further investigation needed if geometry emptiness persists.
