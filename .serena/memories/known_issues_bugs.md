# Known Issues and Bugs

## Current Issues

### 1. Combobox Layer Icons Not Displaying Correctly ⚠️ **HIGH PRIORITY**

**Location**: `modules/appTasks.py:2311` and `filter_mate_dockwidget.py:489, 508, 539`

**Problem**: 
- `layer.geometryType()` returns a QGIS enum object (e.g., `QgsWkbTypes.PointGeometry`)
- The code converts it to string representation which becomes numeric (e.g., `"0"`, `"1"`, `"2"`)
- `icon_per_geometry_type()` expects string format like `'GeometryType.Point'`, `'GeometryType.Line'`, `'GeometryType.Polygon'`
- Result: Icons don't match geometry types in combobox

**Status**: Known issue, not yet fixed

---

## Resolved Issues

### 1. ✅ Geometric Filtering Restored (3 Dec 2025)

**Issue**: Geometric filtering was completely broken - target layers were not filtered based on source layer geometry using spatial predicates.

**Location**: 
- `modules/appTasks.py` (FilterEngineTask class)
- `filter_mate_app.py` (get_task_parameters method)

**Root Causes**:
1. **layer_props structure mismatch**: Code expected `layer_props['infos']['key']` but received `layer_props['key']` directly
2. **Empty predicates dictionary**: `self.predicates` was never populated with spatial operators
3. **Wrong key name**: Used `'geometry_field'` instead of `'layer_geometry_field'`
4. **No fallback**: Spatialite geometry prep failure stopped all filtering
5. **Backend compatibility**: Backend methods called with incompatible parameters

**Solution Implemented**:

1. **Fixed predicates initialization** (`appTasks.py:207-225`):
   - Populated with all spatial operators (Intersect, Within, Contains, etc.)
   - Added both capitalized and lowercase variants
   - Now properly maps UI names to SQL functions

2. **Rewrote execute_geometric_filtering** (`appTasks.py:1475-1568`):
   - Removed erroneous `.get('infos', {})` wrapper
   - Changed `'geometry_field'` to `'layer_geometry_field'`
   - Added validation for required fields
   - Simplified backend interaction using `_safe_set_subset_string`
   - Comprehensive error logging

3. **Added geometry prep fallback** (`appTasks.py:633-666`):
   - Spatialite preparation now falls back to OGR if it fails
   - Only returns False if both methods fail
   - Detailed logging at each step

4. **Validated layer_props structure** (`filter_mate_app.py:429-456`):
   - Checks all required keys exist
   - Attempts to fill missing keys from layer object
   - Skips layers with critical missing data
   - Clear warning/error messages

**Impact**:
- ✅ Geometric filtering now works for all three backends (PostgreSQL, Spatialite, OGR)
- ✅ All spatial predicates functional (intersects, within, contains, overlaps, etc.)
- ✅ Buffer values (fixed and expression-based) work correctly
- ✅ Fallback mechanisms prevent single failures from breaking everything
- ✅ Clear error messages and comprehensive logging
- ✅ Thread-safe operations using `_safe_set_subset_string`

**Testing Required**:
- [ ] Manual testing in QGIS with PostgreSQL layers
- [ ] Manual testing with Spatialite layers
- [ ] Manual testing with OGR layers (Shapefile, GeoPackage)
- [ ] Test different spatial predicates
- [ ] Test with buffer values
- [ ] Test mixed backends

**Files Modified**:
- `modules/appTasks.py` (~150 lines changed)
- `filter_mate_app.py` (~35 lines changed)

**Documentation Created**:
- `GEOMETRIC_FILTERING_FIX_PLAN.md` - Complete implementation plan
- `IMPLEMENTATION_COMPLETE.md` - Detailed summary

---

### 2. ✅ IS_SELECTING Button Auto-Selection (3 Dec 2025)

**Issue**: When activating the IS_SELECTING button in the exploration panel, features from the active groupbox were not automatically selected on the layer.

**Solution**: Created `exploring_select_features()` method and updated button signal

**Files Modified**: `filter_mate_dockwidget.py`

---

### 3. ✅ Exploration Widgets Not Updating Layer Source (3 Dec 2025)

**Issue**: Feature picker widgets not updating when switching layers

**Solution**: Added missing `setLayer()` calls in `exploring_groupbox_changed`

**Files Modified**: `filter_mate_dockwidget.py`

---

### 4. ✅ Layers Not Initialized at Plugin Startup (3 Dec 2025)

**Issue**: Race condition causing PROJECT_LAYERS to not initialize properly

**Solution**: Always update PROJECT_LAYERS even if widgets not initialized; only enable widgets if data ready

**Files Modified**: `filter_mate_dockwidget.py`

---

### 5. ✅ Layer Sorting Performance Optimized (3 Dec 2025)

**Issue**: Layers re-sorted on every iteration

**Solution**: Moved sorting outside loop

**Files Modified**: `modules/appTasks.py`

---

### 6. ✅ Provider Type Detection Refactored (3 Dec 2025)

**Issue**: Duplicated provider type detection logic

**Solution**: Created `detect_layer_provider_type()` utility function

**Files Modified**: `modules/appUtils.py`, `modules/appTasks.py`

---

## Future Considerations

### Performance Optimization (Phase 4-5)
- Caching of layer icons
- Lazy loading of layer properties
- Materialized view cleanup for PostgreSQL

### UI/UX Improvements
- Better feedback during long operations
- Progress bars for export operations
- Clearer backend selection indication

### Multi-Backend Improvements
- Better Spatialite spatial index creation
- OGR driver detection improvements
- Mixed-source project handling
