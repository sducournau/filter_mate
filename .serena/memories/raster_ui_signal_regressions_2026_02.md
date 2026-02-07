# Raster UI Signal Regressions Analysis - February 2026

**Date:** February 5, 2026  
**Branch:** fix/widget-visibility-and-styles-2026-02-02  
**Analysis Focus:** Signal connections and UI regressions in raster tool panel

---

## Context

The raster tool panel (widget_raster_keys) was introduced in v5.4.0 with 5 interactive tools:
- Pixel Picker (pushButton_raster_pixel_picker)
- Rectangle Range (pushButton_raster_rect_picker)
- Sync Histogram (pushButton_raster_sync_histogram)
- All Bands Info (pushButton_raster_all_bands)
- Reset Range (pushButton_raster_reset_range)

Recent commit (1574828) fixed widget visibility and layout issues, but signal connection problems remain.

---

## CRITICAL ISSUES FOUND

### 1. DUPLICATE SIGNAL CONNECTIONS ⚠️ HIGH RISK

**File:** `filter_mate_dockwidget.py`  
**Lines:** 1078-1083 AND 2354-2360

**Problem:** Same spinbox/combobox signals connected to TWO different handlers:

```python
# Connection Set 1 (Lines 1078-1083)
doubleSpinBox_min.valueChanged → _on_raster_range_changed()
doubleSpinBox_max.valueChanged → _on_raster_range_changed()
comboBox_predicate.currentIndexChanged → _on_raster_predicate_changed()

# Connection Set 2 (Lines 2354-2360)
doubleSpinBox_min.valueChanged → _on_raster_spinbox_range_trigger()
doubleSpinBox_max.valueChanged → _on_raster_spinbox_range_trigger()
comboBox_predicate.currentIndexChanged → _on_raster_combobox_predicate_trigger()
```

**Impact:**
- Each value change fires TWO handlers (2x processing overhead)
- First set has no groupbox check, second set checks if groupbox is active
- Potential for inconsistent behavior and performance degradation
- User changes trigger duplicate histogram updates

**Fix:** Remove first set (lines 1078-1083) OR remove second set (2354-2360). Keep the more specific guarded version (2354-2360).

---

### 2. MISSING blockSignals() DURING STATISTICS REFRESH ⚠️ HIGH RISK

**File:** `filter_mate_dockwidget.py`  
**Lines:** 2991-2997 (in `_refresh_raster_statistics()`)  
**Lines:** 3100-3105 (in `_refresh_raster_statistics_sync()`)

**Problem:** No signal blocking when programmatically updating spinbox values:

```python
# WRONG - Fires valueChanged signals
self.doubleSpinBox_min.setValue(stats.minimumValue)
self.doubleSpinBox_max.setValue(stats.maximumValue)
```

**Should be:**
```python
# CORRECT - Block signals during programmatic update
self.doubleSpinBox_min.blockSignals(True)
self.doubleSpinBox_min.setValue(stats.minimumValue)
self.doubleSpinBox_min.blockSignals(False)
```

**Impact:**
- Initialization triggers handler calls (due to duplicate connections)
- Async task completion (lines 3043-3044) can cause cascading updates
- Performance degradation during layer switching or band changes

**Fix:** Add blockSignals(True/False) wrapper around all setValue() calls in both methods.

---

### 3. SIGNAL LOOP RISK: Groupbox ↔ Button ⚠️ MEDIUM RISK

**File:** `filter_mate_dockwidget.py`  
**Lines:** 2211-2245, 2543-2607

**Problem:** Complex signal chain with incomplete recursion guards:

```
QButtonGroup.buttonToggled (2211)
  → _on_raster_button_group_toggled (2310)
    → _ensure_raster_exclusive_groupbox (2543)
      → gb.setChecked(False) on inactive groupboxes (2586)
        → groupbox.toggled signal (2243)
          → _sync_raster_button_from_groupbox (2500)
            → button.setChecked(False) (2509)
              → LOOP BACK to buttonToggled
```

**Guard Analysis:**
- Main guard `_updating_raster_groupboxes` is set at line 2576
- BUT the "not checked" path (lines 2561-2573) doesn't set the guard flag
- Only uses blockSignals() on groupbox, not the flag

**Impact:**
- Potential infinite loop during groupbox collapse
- Button/groupbox state desync
- Unexpected UI behavior when user rapidly toggles buttons

**Fix:** Add `_updating_raster_groupboxes` flag at start of "not checked" path (after line 2561).

---

### 4. HISTOGRAM RANGE REDUNDANT CALLS ⚠️ MEDIUM RISK

**File:** `filter_mate_dockwidget.py`  
**Lines:** 1381-1382, 1393-1407

**Problem:** Histogram range signals create redundant handler calls:

```python
# Line 1381-1382
self._raster_histogram.rangeChanged.connect(self._on_histogram_range_changed)
self._raster_histogram.rangeSelectionFinished.connect(self._on_histogram_range_finished)

# Line 1407
def _on_histogram_range_finished(self, min_val: float, max_val: float):
    self._on_histogram_range_changed(min_val, max_val)  # <-- Redundant call
```

**Impact:**
- Histogram range updates processed twice
- Duplicate spinbox setValue() calls (though guarded with blockSignals)
- Minor performance overhead

**Fix:** Either remove the redundant call OR merge the two handlers into one.

---

### 5. NO DISCONNECT BEFORE RECONNECT ⚠️ MEDIUM RISK

**File:** `filter_mate_dockwidget.py`  
**Lines:** 2334-2375 (`_connect_raster_combobox_triggers()`)

**Problem:** Signal connections added without disconnect first:

```python
def _connect_raster_combobox_triggers(self):
    # No disconnect here!
    self.comboBox_predicate.currentIndexChanged.connect(...)  # Could accumulate
```

**Impact:**
- If called multiple times (e.g., during re-initialization), signals accumulate
- Each trigger would fire multiple times
- Difficult to debug cascading signal issues

**Fix:** Add explicit disconnect() before connect(), or use a connection tracking pattern.

---

## WIDGET VISIBILITY ISSUES (FIXED in 1574828)

### Already Fixed:
✅ Dynamic widget parent hierarchy (FILTERING/EXPORTING pages as parents)  
✅ Qt resource paths for icons (resources_rc.py)  
✅ Widget geometry updates after layout insertion  
✅ QComboBox boolean evaluation (use `is not None`)  
✅ Minimum height for QgsCheckableComboBoxLayer (26px)  

### Remaining:
❌ Signal connection cleanup not verified post-fix

---

## TESTING RECOMMENDATIONS

### Manual Testing:
1. **Duplicate Spinbox Test:**
   - Open plugin with raster layer
   - Change histogram min/max spinboxes
   - Monitor debug log for TWO handler calls per change
   - Expected: See both `_on_raster_range_changed` AND `_on_raster_spinbox_range_trigger` logs

2. **Signal Loop Test:**
   - Rapidly click between raster tool buttons
   - Watch for UI freezing or unexpected button states
   - Try clicking groupbox checkbox directly vs. button

3. **Statistics Refresh Test:**
   - Switch between raster bands
   - Monitor histogram redraws (should redraw once, not twice)
   - Check console for cascade signal warnings

### Automated Testing:
- Add unit test for signal connection count (should be exactly 1 per signal)
- Add integration test for button/groupbox state sync
- Add performance test for histogram refresh timing

---

## RECOMMENDED FIXES (PRIORITY ORDER)

### Priority 1: HIGH RISK (Do First)
1. **Remove duplicate signal connections** (lines 1078-1083 OR 2354-2360)
2. **Add blockSignals() wrappers** in statistics refresh methods

### Priority 2: MEDIUM RISK (Do Next)
3. **Add guard flag to collapse path** (line 2561)
4. **Clean up histogram range handlers** (merge or remove redundant call)
5. **Add disconnect pattern** to combobox triggers

### Priority 3: PREVENTIVE (Do Later)
6. **Add signal connection tracking** (log all connects/disconnects)
7. **Add automated signal loop detection** in tests
8. **Document signal flow diagram** for raster tool panel

---

## FILE REFERENCES

### Key Methods:
- `_connect_raster_tool_buttons()` (2176-2308) - Main connection setup
- `_ensure_raster_exclusive_groupbox()` (2543-2607) - Exclusivity logic
- `_refresh_raster_statistics()` (2969-3010) - Statistics update
- `_on_raster_button_group_toggled()` (2310-2332) - Button group handler

### Related Files:
- `ui/tools/pixel_picker_tool.py` - RasterPixelPickerTool implementation
- `ui/managers/dockwidget_signal_manager.py` - Signal management utilities
- `filter_mate_dockwidget_base.ui` - UI definition with widget_raster_keys

---

## RELATED COMMITS

- `1574828` (Feb 2, 2026) - fix: widget visibility, layout management and theme styling
- `4ca3c47` - ui: adjust UI spacing and dimensions for better breathing room  
- `bb461bc` - feat: Add raster filter infrastructure and UI components  
- `8547e85` - feat(epic-3): Implement unified filter architecture with raster visibility controls

---

## NOTES

- The duplicate connection issue (Issue #1) is the most impactful and easiest to fix
- Signal loops (#3) are harder to reproduce but can cause UI freezes
- All issues compound each other - fixing one may reduce impact of others
- The recent widget visibility fix (1574828) resolved layout issues but not signal issues
- Consider extracting raster tool panel signal management to separate controller class

---

**Last Updated:** February 5, 2026  
**Status:** Analysis Complete - Fixes Pending  
**Next Action:** Implement Priority 1 fixes and test
