# Dynamic Widget Insertion Issues - February 5, 2026

**Date:** February 5, 2026  
**Context:** Custom widgets (layers_to_filter, layers_to_export, multiple_selection) not displaying correctly

---

## PROBLEM SUMMARY

Three custom widgets are created dynamically but have visibility/layout issues:
1. **checkableComboBoxLayer_filtering_layers_to_filter** - Layers to filter combobox
2. **checkableComboBoxLayer_exporting_layers** - Layers to export combobox
3. **checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection** - Multiple feature picker

---

## ROOT CAUSES

### Issue #1: Parent Widget Mismatch

**File:** `filter_mate_dockwidget.py` lines 720-755

**Problem:** Widgets are created with page widgets as parents (FILTERING, EXPORTING, mGroupBox_exploring_multiple_selection) instead of proper layout parents.

```python
# CURRENT (lines 720, 738, 751):
QgsCheckableComboBoxFeaturesListPickerWidget(self.CONFIG_DATA, self.mGroupBox_exploring_multiple_selection)
QgsCheckableComboBoxLayer(self.FILTERING)
QgsCheckableComboBoxLayer(self.EXPORTING)
```

**Why it's wrong:**
- Qt layouts expect widgets to have the same parent as the layout's parent widget
- When a widget with parent A is added to a layout with parent B, Qt doesn't automatically reparent
- This causes widgets to be "floating" outside the layout hierarchy

**Correct approach:**
- Create widgets with `None` parent initially OR
- Create widgets with correct parent (dockWidgetContents) OR  
- Let Qt reparent automatically when added to layout (requires layout to be properly parented first)

---

### Issue #2: Layout Insertion Timing

**File:** `ui/managers/configuration_manager.py` lines 1094-1146

**Problem:** Complex multi-step layout creation process prone to failure:
1. Remove old layout from vl
2. Delete old layout reference
3. Create NEW empty layout
4. Insert empty layout into vl
5. THEN add widgets to layout

**Why it's fragile:**
- If any step fails, subsequent steps operate on invalid state
- `insertLayout()` can fail silently if layout is already parented elsewhere
- Widget reparenting may not happen if layout isn't properly established
- Multiple state checks (`isVisible()`, loop through layouts) add complexity

---

### Issue #3: Early Return Guards Too Aggressive

**File:** `ui/managers/configuration_manager.py` lines 1080-1092

```python
# FIX 2026-02-02 v6: Check if widget is already visible and in correct layout position
if layers_widget.isVisible():
    # Check if it's in the vertical layout (in any sub-layout)
    for i in range(vl.count()):
        # ... complex nested loop ...
        if sub_item and sub_item.widget() is not None and sub_item.widget() == layers_widget:
            logger.info(f"  ✓ Widget already visible and in layout at position [{i}][{j}], skipping")
            return  # <-- EARLY RETURN!
```

**Problem:**
- If widget is visible BUT in wrong position, function returns without fixing it
- Assumes visibility == correctly positioned (not always true)
- Complex nested loop makes debugging difficult

---

## SYMPTOMS

Users report:
- ❌ Widgets not visible after plugin load
- ❌ Widgets visible but at size 0×0 (collapsed)
- ❌ Widgets in wrong position in layout
- ❌ Widgets don't respond to theme changes
- ❌ Widgets don't respond to parent resize

Debug scripts created:
- `force_add_widgets.py`
- `fix_widgets_visibility.py`
- `debug_filtering_widgets.py`
- `debug_widgets_simple.py`
- `force_visibility.py`

**This indicates persistent, difficult-to-reproduce issues!**

---

## COMPARISON: WORKING vs BROKEN PATTERNS

### ❌ CURRENT BROKEN PATTERN (Filtering Widget)

```python
# Step 1: Create widget with FILTERING page as parent
self.checkableComboBoxLayer_filtering_layers_to_filter = QgsCheckableComboBoxLayer(self.FILTERING)

# Step 2: Much later, in ConfigurationManager...
# Remove old layout, create new layout, insert layout, THEN add widget
h_layout = QtWidgets.QHBoxLayout()
vl.insertLayout(1, h_layout)  # Insert empty layout first
h_layout.addWidget(layers_widget, 1)  # Add widget to layout
```

**Problems:**
- Widget parent (FILTERING) ≠ layout parent (determined by vl.insertLayout)
- Multi-step process with many failure points
- Timing issues (widget created in setupUiCustom, layout created in setup_filtering_tab_widgets)

---

### ✅ WORKING PATTERN (Raster Tool Buttons)

```python
# Defined directly in .ui file
<widget class="QWidget" name="widget_raster_keys">
    <layout class="QVBoxLayout" name="verticalLayout_raster_keys_container">
        <item>
            <layout class="QVBoxLayout" name="verticalLayout_raster_keys">
                <item>
                    <widget class="QPushButton" name="pushButton_raster_pixel_picker"/>
                </item>
                <!-- More buttons... -->
            </layout>
        </item>
    </layout>
</widget>
```

**Why it works:**
- All widgets and layouts defined in .ui file
- Qt Designer handles parent relationships correctly
- No dynamic insertion at runtime
- Everything properly initialized before setupUiCustom() is called

---

## RECOMMENDED FIX STRATEGY

### Option A: Define in .ui File (BEST - Most Reliable)

**Move custom widget placeholders to .ui file:**

```xml
<!-- In filter_mate_dockwidget_base.ui -->
<layout class="QHBoxLayout" name="horizontalLayout_filtering_distant_layers">
    <item>
        <!-- Placeholder widget - will be replaced at runtime -->
        <widget class="QComboBox" name="placeholder_filtering_layers_to_filter">
            <property name="objectName">
                <string>placeholder_filtering_layers_to_filter</string>
            </property>
        </widget>
    </item>
    <item>
        <widget class="QCheckBox" name="checkBox_filtering_use_centroids_distant_layers">
            <!-- Already defined -->
        </widget>
    </item>
</layout>
```

**Then in setupUiCustom:**
```python
# Replace placeholder with custom widget
old_widget = self.placeholder_filtering_layers_to_filter
layout = old_widget.parentWidget().layout()
index = layout.indexOf(old_widget)

# Remove placeholder
layout.removeWidget(old_widget)
old_widget.deleteLater()

# Create custom widget with correct parent (from layout)
self.checkableComboBoxLayer_filtering_layers_to_filter = QgsCheckableComboBoxLayer(layout.parentWidget())

# Insert at same position
layout.insertWidget(index, self.checkableComboBoxLayer_filtering_layers_to_filter)
```

**Benefits:**
- ✅ Layout structure defined in .ui (reliable)
- ✅ Parent relationships correct by design
- ✅ Simple replacement pattern (no complex multi-step insertion)
- ✅ Works for Qt Designer preview
- ✅ Easy to maintain

---

### Option B: Fix Current Pattern (QUICK FIX)

**1. Change parent in widget creation:**

```python
# BEFORE (line 738):
self.checkableComboBoxLayer_filtering_layers_to_filter = QgsCheckableComboBoxLayer(self.FILTERING)

# AFTER:
self.checkableComboBoxLayer_filtering_layers_to_filter = QgsCheckableComboBoxLayer(None)  # No parent yet
```

**2. Simplify layout insertion in ConfigurationManager:**

```python
def setup_filtering_tab_widgets(self):
    # ... existing code ...
    
    # Remove complex early return guard (lines 1080-1092)
    
    # Simplified insertion:
    if not hasattr(d, 'horizontalLayout_filtering_distant_layers'):
        # Create layout ONCE
        h_layout = QtWidgets.QHBoxLayout()
        h_layout.setSpacing(4)
        h_layout.setContentsMargins(0, 0, 0, 0)
        d.horizontalLayout_filtering_distant_layers = h_layout
        
        # Insert into vertical layout
        vl.insertLayout(1, h_layout)
    else:
        h_layout = d.horizontalLayout_filtering_distant_layers
    
    # Clear layout if it has widgets (idempotent)
    while h_layout.count():
        item = h_layout.takeAt(0)
    
    # Add widgets (Qt will reparent automatically)
    h_layout.addWidget(layers_widget, 1)
    h_layout.addWidget(centroids_widget, 0)
    
    # Force visibility
    layers_widget.show()
    centroids_widget.show()
    
    # Update parent
    parent = h_layout.parentWidget()
    if parent:
        parent.updateGeometry()
```

**Benefits:**
- ✅ Simpler logic (less code)
- ✅ Idempotent (can be called multiple times safely)
- ✅ No complex early returns
- ✅ Faster to implement

**Drawbacks:**
- ⚠️ Still using dynamic insertion (inherently fragile)
- ⚠️ Doesn't fix root cause (parent mismatch)

---

## TESTING CHECKLIST

After implementing fix:
- [ ] Load plugin with fresh QGIS instance
- [ ] Verify all 3 custom widgets are visible
- [ ] Check widget sizes (not 0×0)
- [ ] Resize dockwidget → widgets should resize
- [ ] Switch QGIS theme → widgets should update colors
- [ ] Check widget parent() matches layout parent
- [ ] No console errors about reparenting
- [ ] Delete debug scripts (force_add_widgets.py, etc.) if fix works

---

## NEXT STEPS

**Immediate (Quick Fix):**
1. Change widget parent to `None` in widget creation
2. Simplify ConfigurationManager insertion logic
3. Test with fresh QGIS instance

**Long-term (Best Fix):**
1. Add placeholder widgets to .ui file
2. Implement replacement pattern in setupUiCustom
3. Remove complex ConfigurationManager insertion code
4. Update UI testing guide

---

**Last Updated:** February 5, 2026  
**Status:** Analysis complete - Fix strategy defined  
**Priority:** HIGH (affects core plugin functionality)
