# Geometric Filtering Fix Plan
**Date**: 3 December 2025  
**Status**: Implementation Ready  
**Priority**: CRITICAL

---

## Executive Summary

Geometric filtering functionality is currently broken for all three backends (PostgreSQL, Spatialite, OGR). This document outlines the issues identified, root causes, and implementation plan to restore full functionality.

---

## Problem Statement

### Current Behavior
- Expression filtering on source layer works ✓
- Feature selection works ✓
- Geometric filtering of target layers fails ✗
- No error messages shown to users ✗

### Expected Behavior
When a user:
1. Selects features in exploration panel (single/multi/custom)
2. Enables "Has Layers to Filter" with target layers selected
3. Enables "Has Geometric Predicates" with predicates selected (intersects, within, etc.)
4. Optionally configures buffer distance
5. Clicks "Filter" button

The system should:
- Filter the source layer by the selected features/expression
- Apply geometric predicates to filter target layers based on source layer geometry
- Support all three backends (PostgreSQL, Spatialite, OGR) transparently

---

## Critical Issues Identified

### Issue #1: layer_props Structure Mismatch ⚠️ CRITICAL
**Location**: `modules/appTasks.py:1456, 1494-1497`

**Problem**:
```python
# Code expects nested structure:
layer_props.get('infos', {}).get('layer_name')

# But actually receives flat structure:
layer_props.get('layer_name')
```

**Root Cause**:
In `filter_mate_app.py:437`, layers_to_filter is built with:
```python
layers_to_filter.append(self.PROJECT_LAYERS[key]["infos"])
```
This passes the `infos` dict directly, not wrapped in another dict.

**Impact**: KeyError prevents geometric filtering from executing.

---

### Issue #2: Empty Predicates Dictionary ⚠️ CRITICAL
**Location**: `modules/appTasks.py:210, 1567-1577`

**Problem**:
```python
# __init__ creates empty dict:
self.predicates = {}

# execute_filtering tries to use it:
for key in source_predicates:
    if key in self.predicates:  # Always False!
        index = list(self.predicates).index(key)
```

**Root Cause**:
The predicates dictionary is initialized empty and never populated with spatial operators.

**Impact**: `self.current_predicates` stays empty, no geometric filtering applied.

---

### Issue #3: Wrong Geometry Field Key Name ⚠️ CRITICAL
**Location**: `modules/appTasks.py:1497`

**Problem**:
```python
# Code uses:
layer_props.get("geometry_field")  # Returns None

# Should use:
layer_props.get("layer_geometry_field")  # Correct key
```

**Root Cause**:
Inconsistent naming in PROJECT_LAYERS structure.

**Impact**: manage_layer_subset_strings receives None for geometry field.

---

### Issue #4: No Fallback for Geometry Preparation ⚠️ HIGH
**Location**: `modules/appTasks.py:612-642`

**Problem**:
If `prepare_spatialite_source_geom()` fails, the entire filtering stops:
```python
if not hasattr(self, 'spatialite_source_geom') or self.spatialite_source_geom is None:
    logger.error("Failed to prepare Spatialite source geometry")
    return False  # Stops everything!
```

**Root Cause**:
No fallback mechanism to OGR geometry preparation.

**Impact**: Single failure prevents all layers from being filtered.

---

### Issue #5: Backend Method Compatibility ⚠️ HIGH
**Location**: `modules/appTasks.py:1481-1486`

**Problem**:
Backend `apply_filter` may not support all parameters:
```python
result = backend.apply_filter(
    layer=layer,
    expression=expression,
    old_subset=old_subset,
    combine_operator=combine_operator  # May not be supported
)
```

**Root Cause**:
Backend interface not fully standardized across implementations.

**Impact**: TypeError when calling backend methods.

---

### Issue #6: Missing Backend build_expression Implementation ⚠️ HIGH
**Location**: Backend classes may not fully implement spatial predicate building

**Problem**:
Backend classes may have incomplete `build_expression` implementations for spatial operations.

**Impact**: No SQL/expression generated for geometric filtering.

---

## Data Flow Analysis

### Current (Broken) Flow:
```
User clicks Filter
  ↓
FilterMateApp.manage_task('filter')
  ↓
get_task_parameters() builds:
  - task_parameters["task"]["layers"] = [infos_dict1, infos_dict2, ...]
  ↓
FilterEngineTask.run()
  ↓
execute_filtering()
  ↓
execute_source_layer_filtering() ✓ WORKS
  ↓
manage_distant_layers_geometric_filtering()
  ↓
prepare_postgresql/spatialite/ogr_source_geom() ⚠️ May fail
  ↓
For each target layer:
  execute_geometric_filtering(layer_provider_type, layer, layer_props)
    ↓
    backend = BackendFactory.get_backend(...) ✓
    ↓
    layer_props.get('infos', {}).get('layer_name') ✗ FAILS - KeyError
    ↓
    backend.build_expression(...) ✗ NEVER REACHED
    ↓
    backend.apply_filter(...) ✗ NEVER REACHED
```

### Target (Fixed) Flow:
```
User clicks Filter
  ↓
FilterMateApp.manage_task('filter')
  ↓
get_task_parameters() builds:
  - task_parameters["task"]["layers"] = [infos_dict1, infos_dict2, ...]
  - Validates all required keys present
  ↓
FilterEngineTask.run()
  ↓
execute_filtering()
  ↓
execute_source_layer_filtering() ✓ WORKS
  ↓
manage_distant_layers_geometric_filtering()
  ↓
prepare_source_geom with fallback ✓ WORKS
  ↓
For each target layer:
  execute_geometric_filtering(layer_provider_type, layer, layer_props)
    ↓
    backend = BackendFactory.get_backend(...) ✓
    ↓
    Extract fields: layer_props.get('layer_name') ✓ WORKS
    ↓
    backend.build_expression(layer_props, predicates, source_geom) ✓ WORKS
    ↓
    Apply filter with thread-safe method ✓ WORKS
    ↓
    Store in history ✓ WORKS
```

---

## Implementation Plan

### Phase 1: Core Fixes (CRITICAL)
**Priority**: Immediate
**Estimated Time**: 2 hours

#### 1.1 Fix layer_props Structure Access
**File**: `modules/appTasks.py`
**Method**: `execute_geometric_filtering`
**Changes**:
- Remove `.get('infos', {})` wrapper
- Access layer_props keys directly
- Use correct key name: `layer_geometry_field`

#### 1.2 Initialize Predicates Dictionary
**File**: `modules/appTasks.py`
**Method**: `FilterEngineTask.__init__`
**Changes**:
```python
self.predicates = {
    'intersects': 'ST_Intersects',
    'within': 'ST_Within',
    'contains': 'ST_Contains',
    'overlaps': 'ST_Overlaps',
    'touches': 'ST_Touches',
    'crosses': 'ST_Crosses',
    'disjoint': 'ST_Disjoint',
    'equals': 'ST_Equals'
}
```

#### 1.3 Rewrite execute_geometric_filtering
**File**: `modules/appTasks.py`
**Method**: `execute_geometric_filtering`
**Changes**:
- Extract layer properties correctly
- Validate required fields exist
- Use thread-safe subset string application
- Proper error handling with logging

---

### Phase 2: Resilience Improvements (HIGH)
**Priority**: Same session
**Estimated Time**: 1 hour

#### 2.1 Add Fallback for Geometry Preparation
**File**: `modules/appTasks.py`
**Method**: `manage_distant_layers_geometric_filtering`
**Changes**:
- Try Spatialite geometry preparation
- On failure, fall back to OGR geometry
- Only return False if all methods fail

#### 2.2 Validate layer_props in get_task_parameters
**File**: `filter_mate_app.py`
**Method**: `get_task_parameters`
**Changes**:
- Verify all required keys exist before adding to layers_to_filter
- Add logging for missing keys
- Provide sensible defaults where possible

---

### Phase 3: Backend Compatibility (HIGH)
**Priority**: Follow-up
**Estimated Time**: 2 hours

#### 3.1 Standardize Backend Interface
**Files**: `modules/backends/*.py`
**Changes**:
- Ensure all backends implement build_expression with spatial predicates
- Standardize apply_filter signature
- Add comprehensive documentation

#### 3.2 Simplify Backend Calls
**File**: `modules/appTasks.py`
**Method**: `execute_geometric_filtering`
**Changes**:
- Build final expression with combine operator before calling backend
- Use _safe_set_subset_string directly instead of backend.apply_filter
- Simplify error handling

---

### Phase 4: Testing & Validation (MEDIUM)
**Priority**: Post-implementation
**Estimated Time**: 2 hours

#### 4.1 Unit Tests
- Test layer_props structure handling
- Test predicate initialization
- Test geometry preparation with fallback
- Test all three backends

#### 4.2 Integration Tests
- Test full filtering workflow
- Test with PostgreSQL layers
- Test with Spatialite layers
- Test with OGR layers (Shapefiles, GeoPackage)
- Test with buffer values
- Test with multiple predicates

---

## Code Changes

### Change 1: Fix execute_geometric_filtering (CRITICAL)

**File**: `modules/appTasks.py` (lines 1438-1507)

**Before**:
```python
def execute_geometric_filtering(self, layer_provider_type, layer, layer_props):
    # ... docstring ...
    try:
        logger.info(f"Executing geometric filtering for {layer.name()} ({layer_provider_type})")
        
        # WRONG: layer_props doesn't have 'infos' key
        self._verify_and_create_spatial_index(layer, layer_props.get('infos', {}).get('layer_name'))
        
        backend = BackendFactory.get_backend(layer_provider_type, layer, self.task_parameters)
        
        # ... rest of method with bugs ...
```

**After**:
```python
def execute_geometric_filtering(self, layer_provider_type, layer, layer_props):
    """
    Execute geometric filtering on layer using spatial predicates.
    
    Args:
        layer_provider_type: Provider type ('postgresql', 'spatialite', 'ogr')
        layer: QgsVectorLayer to filter
        layer_props: Dict containing layer info (IS the infos dict directly)
        
    Returns:
        bool: True if filtering succeeded, False otherwise
    """
    try:
        logger.info(f"Executing geometric filtering for {layer.name()} ({layer_provider_type})")
        
        # FIXED: layer_props IS the infos dict, access directly
        layer_name = layer_props.get('layer_name')
        primary_key = layer_props.get('primary_key_name')
        geom_field = layer_props.get('layer_geometry_field')  # FIXED: correct key
        
        # Validate required fields
        if not all([layer_name, primary_key, geom_field]):
            logger.error(f"Missing required fields in layer_props for {layer.name()}: "
                        f"name={layer_name}, pk={primary_key}, geom={geom_field}")
            return False
        
        # Verify spatial index
        self._verify_and_create_spatial_index(layer, layer_name)
        
        # Get backend
        backend = BackendFactory.get_backend(layer_provider_type, layer, self.task_parameters)
        
        # Get current subset and combine operator
        old_subset = layer.subsetString() if layer.subsetString() != '' else None
        combine_operator = self._get_combine_operator()
        
        # Prepare source geometry
        source_geom = self._prepare_source_geometry(layer_provider_type)
        if not source_geom:
            logger.error(f"Failed to prepare source geometry for {layer.name()}")
            return False
        
        # Build filter expression
        expression = backend.build_expression(
            layer_props=layer_props,
            predicates=self.current_predicates,
            source_geom=source_geom,
            buffer_value=self.param_buffer_value if hasattr(self, 'param_buffer_value') else None,
            buffer_expression=self.param_buffer_expression if hasattr(self, 'param_buffer_expression') else None
        )
        
        if not expression:
            logger.warning(f"No expression generated for {layer.name()}")
            return False
        
        # Combine with old subset if needed
        if old_subset and combine_operator:
            final_expression = f"({old_subset}) {combine_operator} ({expression})"
        else:
            final_expression = expression
        
        logger.debug(f"Final filter expression for {layer.name()}: {final_expression}")
        
        # Apply filter using thread-safe method
        result = self._safe_set_subset_string(layer, final_expression)
        
        if result:
            # Store in history for undo/redo
            self.manage_layer_subset_strings(
                layer,
                final_expression,
                primary_key,
                geom_field,
                False
            )
            feature_count = layer.featureCount()
            logger.info(f"✓ Successfully filtered {layer.name()}: {feature_count:,} features")
        else:
            logger.error(f"✗ Failed to apply filter to {layer.name()}")
        
        return result
        
    except Exception as e:
        safe_log(logger, logging.ERROR, 
                f"Error in execute_geometric_filtering for {layer.name()}: {e}", 
                exc_info=True)
        return False
```

---

### Change 2: Initialize Predicates Dictionary (CRITICAL)

**File**: `modules/appTasks.py` (line ~210)

**Before**:
```python
self.predicates = {}
```

**After**:
```python
# Initialize with standard spatial predicates
# These map user-friendly names to SQL spatial functions
self.predicates = {
    'intersects': 'ST_Intersects',
    'within': 'ST_Within',
    'contains': 'ST_Contains',
    'overlaps': 'ST_Overlaps',
    'touches': 'ST_Touches',
    'crosses': 'ST_Crosses',
    'disjoint': 'ST_Disjoint',
    'equals': 'ST_Equals',
    'covers': 'ST_Covers',
    'coveredby': 'ST_CoveredBy'
}
```

---

### Change 3: Add Geometry Preparation Fallback (HIGH)

**File**: `modules/appTasks.py` (lines 612-642)

**Before**:
```python
if 'spatialite' in provider_list:
    logger.info("Preparing Spatialite source geometry...")
    try:
        self.prepare_spatialite_source_geom()
        if not hasattr(self, 'spatialite_source_geom') or self.spatialite_source_geom is None:
            logger.error("Failed to prepare Spatialite source geometry - no geometry generated")
            return False  # STOPS EVERYTHING
    except Exception as e:
        logger.error(f"Error preparing Spatialite source geometry: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return False  # STOPS EVERYTHING
```

**After**:
```python
if 'spatialite' in provider_list:
    logger.info("Preparing Spatialite source geometry...")
    spatialite_success = False
    try:
        self.prepare_spatialite_source_geom()
        if hasattr(self, 'spatialite_source_geom') and self.spatialite_source_geom is not None:
            spatialite_success = True
            logger.info("✓ Spatialite source geometry prepared successfully")
        else:
            logger.warning("Spatialite geometry preparation returned None")
    except Exception as e:
        logger.warning(f"Spatialite geometry preparation failed: {e}")
        import traceback
        logger.debug(f"Traceback: {traceback.format_exc()}")
    
    # Fallback to OGR if Spatialite failed
    if not spatialite_success:
        logger.info("Falling back to OGR geometry preparation...")
        try:
            self.prepare_ogr_source_geom()
            if hasattr(self, 'ogr_source_geom') and self.ogr_source_geom is not None:
                # Use OGR geometry as Spatialite geometry
                self.spatialite_source_geom = self.ogr_source_geom
                logger.info("✓ Successfully used OGR geometry as fallback")
            else:
                logger.error("OGR fallback also failed - no geometry available")
                return False
        except Exception as e2:
            logger.error(f"OGR fallback failed: {e2}")
            return False
```

---

### Change 4: Validate layer_props Keys (HIGH)

**File**: `filter_mate_app.py` (line ~437)

**Before**:
```python
for key in self.PROJECT_LAYERS[current_layer.id()]["filtering"]["layers_to_filter"]:
    if key in self.PROJECT_LAYERS:
        layers_to_filter.append(self.PROJECT_LAYERS[key]["infos"])
```

**After**:
```python
for key in self.PROJECT_LAYERS[current_layer.id()]["filtering"]["layers_to_filter"]:
    if key in self.PROJECT_LAYERS:
        layer_info = self.PROJECT_LAYERS[key]["infos"].copy()
        
        # Validate required keys exist
        required_keys = [
            'layer_name', 'layer_id', 'layer_provider_type',
            'primary_key_name', 'layer_geometry_field', 'layer_schema'
        ]
        
        missing_keys = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
        if missing_keys:
            logger.warning(f"Layer {key} missing required keys: {missing_keys}")
            # Try to fill in missing keys if possible
            layer_obj = [l for l in self.PROJECT.mapLayers().values() if l.id() == key]
            if layer_obj:
                layer = layer_obj[0]
                if 'layer_name' not in layer_info:
                    layer_info['layer_name'] = layer.name()
                if 'layer_id' not in layer_info:
                    layer_info['layer_id'] = layer.id()
                # Log what couldn't be filled
                still_missing = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
                if still_missing:
                    logger.error(f"Cannot filter layer {key}: still missing {still_missing}")
                    continue
        
        layers_to_filter.append(layer_info)
```

---

## Testing Checklist

### Pre-Implementation Tests
- [ ] Document current failure modes
- [ ] Capture error logs
- [ ] Create test project with all three layer types

### Post-Implementation Tests

#### Basic Functionality
- [ ] Expression filtering on source layer works
- [ ] Single feature selection in exploration panel
- [ ] Multiple feature selection in exploration panel
- [ ] Custom expression selection in exploration panel

#### Geometric Filtering - PostgreSQL
- [ ] Intersects predicate
- [ ] Within predicate
- [ ] Contains predicate
- [ ] With buffer value
- [ ] With buffer expression
- [ ] Multiple target layers simultaneously

#### Geometric Filtering - Spatialite
- [ ] Intersects predicate
- [ ] Within predicate
- [ ] Contains predicate
- [ ] With buffer value
- [ ] Fallback to OGR when Spatialite geometry prep fails

#### Geometric Filtering - OGR (Shapefile/GeoPackage)
- [ ] Intersects predicate
- [ ] Within predicate
- [ ] Contains predicate
- [ ] With buffer value

#### Mixed Scenarios
- [ ] PostgreSQL source, Spatialite targets
- [ ] Spatialite source, OGR targets
- [ ] OGR source, PostgreSQL targets
- [ ] All three types mixed

#### Error Handling
- [ ] Missing geometry field handled gracefully
- [ ] Missing primary key handled gracefully
- [ ] Empty predicates list handled
- [ ] Invalid layer_props structure handled
- [ ] User sees meaningful error messages

#### Performance
- [ ] Large datasets (>10k features) filter reasonably fast
- [ ] Spatial indexes are used when available
- [ ] No memory leaks during repeated filtering

---

## Success Criteria

### Must Have
1. ✅ All three backends (PostgreSQL, Spatialite, OGR) support geometric filtering
2. ✅ Source layer filtering by expression works
3. ✅ Target layers filtered by geometric predicates relative to source
4. ✅ Buffer values applied correctly
5. ✅ No crashes or unhandled exceptions
6. ✅ Clear error messages when filtering fails

### Should Have
1. ✅ Fallback mechanisms when preferred method fails
2. ✅ Comprehensive logging for debugging
3. ✅ Performance warnings for large datasets
4. ✅ Undo/redo via filter history

### Nice to Have
1. Progress indicators during filtering
2. Filter preview before applying
3. Statistics on filtered features
4. Export filter expressions

---

## Risk Assessment

### High Risk
- **Thread safety**: QGIS API calls from worker threads can crash
  - *Mitigation*: Use `_safe_set_subset_string` for all subset operations

### Medium Risk
- **Backend compatibility**: Backends may have different SQL dialects
  - *Mitigation*: Use backend-specific implementations via factory pattern

### Low Risk
- **Performance**: Large datasets may be slow
  - *Mitigation*: Use spatial indexes, warn users for large datasets

---

## Rollback Plan

If implementation causes regressions:

1. **Immediate**: Revert commits using git
2. **Document**: Capture specific failures in issue tracker
3. **Isolate**: Test each backend independently
4. **Fallback**: Disable geometric filtering, keep expression filtering working

---

## Timeline

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1: Core Fixes | 2 hours | Ready |
| Phase 2: Resilience | 1 hour | Ready |
| Phase 3: Backend Compatibility | 2 hours | Ready |
| Phase 4: Testing | 2 hours | Ready |
| **Total** | **7 hours** | **Ready to Start** |

---

## Dependencies

### Code Dependencies
- ✅ Backend factory pattern already implemented
- ✅ Thread-safe subset string method exists
- ✅ Logging infrastructure in place

### Testing Dependencies
- Test project with PostgreSQL layers
- Test project with Spatialite layers
- Test project with Shapefiles/GeoPackage
- Various geometry types (Point, Line, Polygon)

---

## Next Steps

1. **Immediate**: Implement Phase 1 (Core Fixes)
2. **Same Session**: Implement Phase 2 (Resilience)
3. **Follow-up**: Implement Phase 3 (Backend Compatibility)
4. **Validation**: Execute Phase 4 (Testing)
5. **Documentation**: Update user-facing documentation

---

## Notes

- This fix addresses the root causes, not just symptoms
- All three backends will work consistently after implementation
- Error handling is comprehensive to prevent silent failures
- Code is more maintainable with clear structure
- Performance considerations are built in from the start

---

**Document Status**: Implementation Ready  
**Last Updated**: 3 December 2025  
**Author**: GitHub Copilot (AI Assistant)
