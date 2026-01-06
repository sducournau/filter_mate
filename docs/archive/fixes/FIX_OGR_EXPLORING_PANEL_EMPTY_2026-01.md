# Fix: Exploring Panel Empty After OGR Filter (v2.8.16)

## Issue
After applying an OGR filter successfully, the exploring panel widgets (single selection and multiple selection) displayed empty comboboxes instead of showing the filtered features.

## Root Cause
The QGIS `QgsFeaturePickerWidget` and custom `QgsCheckableComboBoxFeaturesListPickerWidget` cache features internally. When a layer's `subsetString` changes (e.g., after OGR filtering via `setSubsetString()`), these widgets don't automatically detect that the feature list has changed because the layer object reference remains the same.

## Technical Details

### QgsFeaturePickerWidget Behavior
- Maintains an internal model that caches layer features
- Calling `setLayer(layer)` with the same layer reference doesn't force a refresh
- The widget doesn't monitor `subsetString` changes automatically

### QgsCheckableComboBoxFeaturesListPickerWidget Behavior  
- Reuses existing widget instances when `setLayer()` is called with the same layer
- Only reloads features if the display expression changes
- Doesn't detect that features may have changed due to filtering

## Solution

### 1. Force QgsFeaturePickerWidget Refresh
In `_reload_exploration_widgets()`, set the layer to `None` first, then set it back to the actual layer:

```python
# Clear layer reference to force widget to rebuild internal model
self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setLayer(None)
# Now set the layer - this forces complete rebuild
self.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setLayer(layer)
```

This forces the widget to:
1. Clear its internal feature cache
2. Rebuild the combobox model
3. Reload all features from the layer (respecting new subsetString)

### 2. Force Custom Widget Refresh
For the multiple selection widget, explicitly call `setDisplayExpression()` even if the expression hasn't changed:

```python
# First ensure proper initialization
self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setLayer(layer, layer_props)
# Force refresh by calling setDisplayExpression (triggers feature reload)
self.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(multiple_expr)
```

This ensures:
1. The widget recognizes it needs to reload features
2. Launches a `loadFeaturesList` task
3. Updates the displayed feature list

## Files Modified

### filter_mate_dockwidget.py
- Method: `_reload_exploration_widgets()` (lines ~9450-9470)
- Changes:
  - Added `setLayer(None)` before `setLayer(layer)` for single selection widget
  - Added explicit `setDisplayExpression()` call for multiple selection widget
  - Added explanatory comments

## Testing

Test scenarios:
1. ✅ Apply OGR filter → exploring panel shows filtered features
2. ✅ Apply OGR filter multiple times → exploring panel updates correctly each time
3. ✅ Switch between layers after OGR filter → exploring panel switches correctly
4. ✅ Apply OGR filter with 0 results → exploring panel shows empty (correct)

## Related Issues

This fix complements the existing OGR combobox synchronization fix in `filter_mate_app.py` (lines 3974-3997):
- That fix ensures the filtering current layer combobox stays synchronized
- This fix ensures the exploring widgets refresh their feature lists

## Version
- **Introduced**: v2.8.16 (January 2026)
- **Related Fixes**: v2.8.15 (OGR combobox synchronization)

## Keywords
- OGR backend
- Exploring panel
- Widget refresh
- QgsFeaturePickerWidget
- Feature cache
- subsetString
