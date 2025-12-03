# Known Issues and Bugs

## Current Issues

### 1. Combobox Layer Icons Not Displaying Correctly ⚠️ **HIGH PRIORITY**

**Location**: `modules/appTasks.py:2311` and `filter_mate_dockwidget.py:489, 508, 539`

**Problem**: 
- `layer.geometryType()` returns a QGIS enum object (e.g., `QgsWkbTypes.PointGeometry`)
- The code converts it to string representation which becomes numeric (e.g., `"0"`, `"1"`, `"2"`)
- `icon_per_geometry_type()` expects string format like `'GeometryType.Point'`, `'GeometryType.Line'`, `'GeometryType.Polygon'`
- Result: Icons don't match geometry types in combobox

**Affected Code**:
```python
# appTasks.py line 2311
layer_geometry_type = layer.geometryType()  # Returns QgsWkbTypes.GeometryType enum

# filter_mate_dockwidget.py lines 489, 508, 539
layer_icon = self.icon_per_geometry_type(
    self.PROJECT_LAYERS[key]["infos"]["layer_geometry_type"]
)

# filter_mate_dockwidget.py line 446-458
def icon_per_geometry_type(self, geometry_type):
    if geometry_type == 'GeometryType.Line':
        return QgsLayerItem.iconLine()
    elif geometry_type == 'GeometryType.Point':
        return QgsLayerItem.iconPoint()
    elif geometry_type == 'GeometryType.Polygon':
        return QgsLayerItem.iconPolygon()
    # ...
```

**Solution**:
Replace `layer.geometryType()` with proper string conversion:
```python
# Option 1: Convert enum to expected string format
from qgis.core import QgsWkbTypes

geometry_type = layer.geometryType()
if geometry_type == QgsWkbTypes.PointGeometry:
    layer_geometry_type = 'GeometryType.Point'
elif geometry_type == QgsWkbTypes.LineGeometry:
    layer_geometry_type = 'GeometryType.Line'
elif geometry_type == QgsWkbTypes.PolygonGeometry:
    layer_geometry_type = 'GeometryType.Polygon'
elif geometry_type == QgsWkbTypes.UnknownGeometry:
    layer_geometry_type = 'GeometryType.UnknownGeometry'
else:
    layer_geometry_type = 'GeometryType.UnknownGeometry'

# Option 2: Use QgsWkbTypes.displayString()
layer_geometry_type = f"GeometryType.{QgsWkbTypes.geometryDisplayString(layer.geometryType())}"
```

**Files to Modify**:
1. `modules/appTasks.py` - Line ~2311 (in LayersManagementEngineTask)
2. `filter_mate_dockwidget.py` - Line ~446-458 (icon_per_geometry_type method)

**Testing**:
- Test with Point layers
- Test with Line layers
- Test with Polygon layers
- Test with tables (no geometry)
- Check icons in both "Layers to Filter" and "Layers to Export" comboboxes

---

## Resolved Issues

### 1. ✅ IS_SELECTING Button Auto-Selection (3 Dec 2025)

**Issue**: When activating the IS_SELECTING button in the exploration panel, features from the active groupbox were not automatically selected on the layer.

**Location**: `filter_mate_dockwidget.py:343` (IS_SELECTING button signal) and `~1699` (new function)

**Root Cause**: 
The `ON_TRUE` callback of the IS_SELECTING button was calling `get_current_features()`, which only retrieves features but doesn't select them. Users had to manually trigger another action to see the selection.

**Solution Implemented**:
1. Created new `exploring_select_features()` method that:
   - Retrieves features from the active exploration groupbox (single/multiple/custom)
   - Automatically selects them on the current layer
   
2. Updated IS_SELECTING button signal to call `exploring_select_features()` instead of `get_current_features()`:

```python
"IS_SELECTING": {
    "SIGNALS": [("clicked", lambda state, x='is_selecting', 
                 custom_functions={
                     "ON_TRUE": lambda x: self.exploring_select_features(),  # NEW
                     "ON_FALSE": lambda x: self.exploring_deselect_features()
                 }: self.layer_property_changed(x, state, custom_functions))]
}
```

**Impact**: 
- Activating IS_SELECTING button now immediately selects features from active groupbox
- More intuitive user experience - button state directly reflects selection state
- Consistent behavior across all three exploration modes

**Testing**: 
1. Select features in any exploration mode (single/multiple/custom)
2. Click IS_SELECTING button to activate
3. Verify features are immediately selected on the layer (highlighted in yellow/selection color)
4. Click IS_SELECTING button to deactivate
5. Verify features are deselected

**Files Modified**:
- `filter_mate_dockwidget.py` - Line ~343 (signal) and ~1709 (new method)

### 2. ✅ Exploration Widgets Not Updating Layer Source (3 Dec 2025)

**Issue**: When changing current layer, exploration feature and field widgets (QgsFeaturePickerWidget, QgsFieldExpressionWidget) were not properly updated to display features from the new layer.

**Location**: `filter_mate_dockwidget.py:1420-1435` (`exploring_groupbox_changed` method)

**Root Cause**: 
In the `exploring_groupbox_changed` method, when switching to "single_selection" mode, the code was NOT calling `setLayer()` on the `SINGLE_SELECTION_FEATURES` widget (QgsFeaturePickerWidget). This meant the widget continued displaying features from the previous layer even after the current layer changed.

**Comparison with multiple_selection mode**:
```python
# Multiple selection: CORRECTLY calls setLayer
self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setLayer(self.current_layer, layer_props)

# Single selection: MISSING setLayer call (BUG)
# Only updated the expression widget, not the feature picker
self.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setLayer(self.current_layer)
```

**Solution Implemented**:
Added missing `setLayer()` and `setDisplayExpression()` calls for the `SINGLE_SELECTION_FEATURES` widget in `exploring_groupbox_changed`:

```python
# CRITICAL FIX: Update SINGLE_SELECTION_FEATURES widget to use current layer
# This ensures the QgsFeaturePickerWidget displays features from the correct layer
layer_props = self.PROJECT_LAYERS[self.current_layer.id()]
self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setLayer(self.current_layer)
self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(layer_props["exploring"]["single_selection_expression"])
```

**Impact**: 
- Fixed exploration widgets now correctly update when switching between layers
- QgsFeaturePickerWidget displays features from current layer, not previous layer
- Consistent behavior between single_selection and multiple_selection modes
- Field expression widgets properly linked to current layer source

**Testing**: 
1. Load multiple vector layers in QGIS project
2. Select first layer and open exploration panel
3. Switch to second layer via current layer dropdown or layer tree
4. Verify single selection feature picker shows features from NEW layer
5. Verify multiple selection feature list shows features from NEW layer
6. Verify field expression widgets show fields from NEW layer
7. Test all three exploration modes (single, multiple, custom selection)

**Files Modified**:
- `filter_mate_dockwidget.py` - Line ~1420-1437 (exploring_groupbox_changed method)

### 2. ✅ Layers Not Initialized at Plugin Startup (3 Dec 2025)

**Issue**: When opening a project with existing layers, PROJECT_LAYERS was not properly initialized in the dockwidget, and widgets remained disabled
**Location**: 
- `filter_mate_dockwidget.py:2638` (`get_project_layers_from_app`)
- `filter_mate_dockwidget.py:1312` (`manage_interactions`)

**Root Causes**: 
1. **Race condition in layer data sync**: `FilterMateApp.run()` creates dockwidget and immediately launches `manage_task('add_layers', init_layers)`. The async `LayersManagementEngineTask` completes and calls `get_project_layers_from_app()`. If task completes before `widgets_initialized = True`, the method returned early without updating `PROJECT_LAYERS`.

2. **Premature widget activation**: `manage_interactions()` was calling `set_widgets_enabled_state(has_loaded_layers)` based only on whether vector layers existed in the project, NOT whether `PROJECT_LAYERS` was populated. This caused widgets to be enabled before data was ready, leading to KeyError exceptions and widgets being disabled again.

**Solution Implemented**:

**Part 1** - Always update PROJECT_LAYERS even if widgets not initialized:
```python
def get_project_layers_from_app(self, project_layers, project=None):
    # Always update PROJECT and PROJECT_LAYERS, even if widgets not initialized yet
    if project != None:    
        self.PROJECT = project
    
    self.PROJECT_LAYERS = project_layers
    
    # Update has_loaded_layers flag based on PROJECT_LAYERS
    if len(list(self.PROJECT_LAYERS)) > 0:
        self.has_loaded_layers = True
    else:
        self.has_loaded_layers = False
    
    # Only update UI if widgets are initialized
    if self.widgets_initialized is True:
        # ... rest of UI update logic
```

**Part 2** - Only enable widgets if PROJECT_LAYERS is populated:
```python
def manage_interactions(self):
    # Only enable widgets if PROJECT_LAYERS is already populated
    # Otherwise, wait for get_project_layers_from_app() to enable them when data is ready
    if self.has_loaded_layers is True and len(self.PROJECT_LAYERS) > 0:
        self.set_widgets_enabled_state(True)
        self.connect_widgets_signals()
    else:
        self.set_widgets_enabled_state(False)
```

**Impact**: 
- Fixed race condition where layer initialization task could complete before widgets fully initialized
- Fixed widgets remaining disabled when PROJECT_LAYERS was empty at initialization time
- Widgets now properly activate once data is loaded, regardless of timing

**Testing**: 
- Verify plugin startup with existing layers in project
- Check comboboxes are populated
- Verify widgets are enabled after startup completes

### 2. ✅ Combobox Layer Icons Fixed (3 Dec 2025)

**Issue**: Geometry type enum was being converted to numeric string instead of expected format
**Location**: `modules/appTasks.py:2311` and utility functions
**Solution Implemented**:
- Created `geometry_type_to_string()` utility function in `appUtils.py`
- Converts `QgsWkbTypes` enums to proper string format ('GeometryType.Point', etc.)
- Updated `add_project_layer()` to use utility function
**Testing**: Verify icons display correctly for Point, Line, Polygon, and Table layers

### 2. ✅ Layer Sorting Performance Optimized (3 Dec 2025)

**Issue**: Layers were being re-sorted on every iteration when adding multiple layers
**Location**: `modules/appTasks.py:2236` (now ~2237)
**Solution Implemented**:
- Moved sorting operation outside the loop in `manage_project_layers()`
- Now sorts only once after all layers are processed
- Significant performance improvement when adding many layers (10+)
**Impact**: ~N times faster when adding N layers

### 3. ✅ Provider Type Detection Refactored (3 Dec 2025)

**Issue**: Provider type detection logic was duplicated in multiple places
**Location**: `modules/appTasks.py` (multiple locations)
**Solution Implemented**:
- Created `detect_layer_provider_type()` utility function in `appUtils.py`
- Handles OGR vs Spatialite distinction via capability check
- Updated `add_project_layer()` to use utility function
- Reduced code duplication by ~30 lines
**Benefits**: More maintainable, consistent behavior, easier to extend

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

---

## Issue Template for New Bugs

```markdown
### [Issue Title]
**Location**: `filename.py:line_number`
**Priority**: LOW/MEDIUM/HIGH/CRITICAL
**Problem**: Clear description
**Affected Code**: Code snippet
**Solution**: Proposed fix
**Files to Modify**: List of files
**Testing**: Test cases
```
