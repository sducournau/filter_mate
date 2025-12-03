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

### 1. ✅ Combobox Layer Icons Fixed (3 Dec 2025)

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
