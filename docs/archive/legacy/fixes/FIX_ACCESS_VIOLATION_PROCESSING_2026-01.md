# FIX: Windows Access Violation in processing.run() - 2026-01

## Problem Description

**Symptom:** Windows fatal exception (access violation) causing complete QGIS crash during geometric filtering.

**Error Location:**
```python
File "ogr_backend.py", line 1967 in _safe_select_by_location
    select_result = processing.run("native:selectbylocation", {
```

**Stack Trace:**
```
Windows fatal exception: access violation
Current thread 0x000066a4 (most recent call first):
  File "...\processing\core\Processing.py", line 215 in runAlgorithm
    ok, msg = alg.checkParameterValues(parameters, context)
```

**Severity:** CRITICAL - Crashes QGIS at C++ level, cannot be caught by Python try-except

## Root Cause Analysis

### 1. C++ Object Lifecycle Issue

The crash occurred because temporary QgsVectorLayer objects (memory layers) were being garbage collected by Python or Qt BEFORE they were used in `processing.run()`.

**Sequence of Events:**

1. `_apply_buffer()` creates temporary memory layer (`buffered_layer`)
2. `create_geos_safe_layer()` creates another temporary layer (`safe_intersect`)
3. Python's garbage collector or Qt's QObject deletion mechanism destroys the C++ object
4. Python variable still holds a reference to the deleted C++ object
5. `processing.run("native:selectbylocation", {'INTERSECT': safe_intersect})` passes deleted object
6. QGIS C++ code calls `checkParameterValues()` which accesses the deleted object
7. **Access violation** → QGIS crash

### 2. Why Python try-except Cannot Catch This

```python
# This CANNOT catch C++ access violations:
try:
    processing.run("native:selectbylocation", ...)
except Exception as e:
    # Never executed - QGIS already crashed!
    pass
```

The crash happens at the C++ level in QGIS's Processing framework, BEFORE Python's exception handling can intercede. The crash occurs in:
- `QgsProcessingAlgorithm::checkParameterValues()` (C++ function)
- Called by `Processing.runAlgorithm()` (Python → C++ boundary)

### 3. Contributing Factors

**Factor A: Delayed Reference Storage**
```python
# PROBLEMATIC (before fix):
buffered_layer = self._apply_buffer(source_layer, buffer_value)
# ... buffered_layer may be GC'd here ...
self._temp_layers_keep_alive.append(buffered_layer)  # Too late!
```

**Factor B: None Returns**
```python
# PROBLEMATIC (before fix):
if feature_count == 0:
    return None  # Causes "intersect_layer is None" errors downstream
```

**Factor C: No C++ Wrapper Validation**
```python
# MISSING (before fix):
# No check if C++ object still exists before passing to processing.run()
```

## Solution Implementation

### Defense Layer 1: C++ Wrapper Validation (Pre-Flight Check)

**Location:** `ogr_backend.py:_safe_select_by_location()` (before `processing.run()`)

```python
# FIX v2.9.11: Validate C++ wrappers before processing.run
try:
    # Force access to C++ objects - raises RuntimeError if deleted
    _ = actual_input.name()
    _ = safe_intersect.name()
    _ = actual_input.dataProvider().name()
    _ = safe_intersect.dataProvider().name()
except RuntimeError as wrapper_error:
    # C++ object deleted - abort before crash!
    self.log_error(f"C++ wrapper deleted: {wrapper_error}")
    return False
```

**Why This Works:**
- Accessing `.name()` or `.dataProvider()` triggers C++ method call
- If C++ object is deleted, PyQt raises `RuntimeError: wrapped C/C++ object has been deleted`
- Python CAN catch `RuntimeError` (it's a Python exception, not C++ crash)
- We detect the problem BEFORE passing to `processing.run()`

### Defense Layer 2: Immediate Reference Storage

**Location:** `ogr_backend.py:_apply_buffer()` and `_apply_filter_standard()`

```python
# FIX v2.9.11: Store reference IMMEDIATELY after creation
buffered_layer = self._convert_geometry_collection_to_multipolygon(buffered_layer)

# CRITICAL: Keep alive BEFORE any other operations
if not hasattr(self, '_temp_layers_keep_alive'):
    self._temp_layers_keep_alive = []
self._temp_layers_keep_alive.append(buffered_layer)

return buffered_layer
```

**Why This Works:**
- Reference stored in Python list BEFORE function returns
- List is an instance attribute (survives across method calls)
- Python GC won't collect objects with active references
- Qt QObject parent-child relationship preserved

### Defense Layer 3: Improved Error Handling

**Location:** `ogr_backend.py:_safe_select_by_location()`

```python
# FIX v2.9.11: Specific exception handling for C++ errors
try:
    select_result = processing.run("native:selectbylocation", {...})
except RuntimeError as cpp_error:
    # C++ level error (access violation, etc.)
    self.log_error(f"C++ error: {cpp_error}")
    input_layer.removeSelection()
    return False
except Exception as proc_error:
    # Other processing errors
    self.log_error(f"Processing error: {proc_error}")
    return False
```

**Why This Works:**
- Distinguishes C++ errors (`RuntimeError`) from Python errors
- Cleaner error messages for debugging
- Ensures selection is cleared even on error

### Defense Layer 4: Safe Fallbacks

**Location:** `modules/geometry_safety.py:create_geos_safe_layer()`

```python
# FIX v2.9.11: Return original layer instead of None
if not isinstance(layer, QgsVectorLayer):
    logger.error(f"Not a QgsVectorLayer: {type(layer)}")
    return layer  # Not None! Caller will validate

if feature_count == 0:
    logger.warning("No features")
    return layer  # Not None! Empty layer is valid

# Test C++ wrapper validity
try:
    _ = layer.name()
    _ = layer.featureCount()
except RuntimeError as wrapper_error:
    logger.error(f"C++ wrapper deleted: {wrapper_error}")
    return None  # Cannot use deleted layer
```

**Why This Works:**
- Avoids `None` being passed to `processing.run()` (causes instant crash)
- Original layer returned when GEOS-safe layer creation fails
- C++ wrapper tested before processing

## Testing & Verification

### Test Case: Multi-Layer Geometric Filtering

**Before Fix:**
```
Layer 1: ✅ Success
Layer 2: 💥 Windows fatal exception: access violation
```

**After Fix:**
```
Layer 1: ✅ Success
Layer 2: ✅ Success (or clean error message if issue persists)
Layer 3-8: ✅ Success
```

### Manual Testing Checklist

1. **Single Layer Filtering:**
   - ✅ Small dataset (<1k features)
   - ✅ Medium dataset (1k-10k features)
   - ✅ Large dataset (>10k features)

2. **Multi-Layer Filtering:**
   - ✅ 2 layers from same GeoPackage
   - ✅ 5+ layers from same GeoPackage
   - ✅ Layers from different sources

3. **Edge Cases:**
   - ✅ Buffer with 0 value
   - ✅ Negative buffer (polygon erosion)
   - ✅ Source layer with single feature
   - ✅ Source layer with complex geometries

4. **Error Handling:**
   - ✅ Invalid source geometry
   - ✅ Empty source layer
   - ✅ Mismatched CRS

## Prevention Guidelines

### For Future Development

**DO:**
- ✅ Store temporary layer references IMMEDIATELY after creation
- ✅ Test C++ wrapper validity before passing to Qt/QGIS functions
- ✅ Use specific exception types (`RuntimeError` for C++ errors)
- ✅ Return original layer as fallback instead of `None`
- ✅ Clear temporary references at START of each iteration

**DON'T:**
- ❌ Assume temporary memory layers will persist without references
- ❌ Return `None` for layers that will be used in `processing.run()`
- ❌ Pass layers to Qt/QGIS functions without C++ wrapper validation
- ❌ Use generic `except Exception` for C++ errors
- ❌ Accumulate temporary references across iterations

### Code Pattern: Safe Temporary Layer Usage

```python
def create_and_use_temp_layer(self):
    # 1. Create instance reference list if needed
    if not hasattr(self, '_temp_layers_keep_alive'):
        self._temp_layers_keep_alive = []
    
    # 2. Create temporary layer
    temp_layer = processing.run("native:buffer", {...})['OUTPUT']
    
    # 3. IMMEDIATELY store reference
    self._temp_layers_keep_alive.append(temp_layer)
    
    # 4. Validate C++ wrapper before use
    try:
        _ = temp_layer.name()
        _ = temp_layer.dataProvider().name()
    except RuntimeError as e:
        self.log_error(f"Layer already deleted: {e}")
        return False
    
    # 5. Use the layer (safe now!)
    result = processing.run("native:selectbylocation", {
        'INTERSECT': temp_layer
    })
    
    # 6. Clear references at start of NEXT iteration
    # (in the calling function, not here)
    
    return True
```

## Related Issues

- **v2.9.10:** Fixed temporary layer GC across iterations
- **v2.8.14:** Added extensive logging for debugging layer validity
- **v2.4.18:** Fixed feature ID mapping for safe layers

## Technical References

- **Qt QObject Ownership:** https://doc.qt.io/qt-5/objecttrees.html
- **PyQt Memory Management:** https://www.riverbankcomputing.com/static/Docs/PyQt5/gotchas.html
- **QGIS Processing API:** https://qgis.org/pyqgis/latest/core/QgsProcessingAlgorithm.html

## Conclusion

This fix prevents Windows access violations by ensuring temporary QgsVectorLayer objects:

1. **Persist** - References stored immediately in instance list
2. **Validate** - C++ wrapper checked before use in Qt/QGIS functions  
3. **Fallback** - Original layer returned instead of `None`
4. **Clean** - References cleared at start of each iteration

The multi-layer defense ensures even if one layer fails validation, it's caught as a Python exception with clean error handling, rather than a catastrophic C++ crash.

**Status:** ✅ RESOLVED - No more access violations in production testing
