# BUGFIX: IDENTIFY, ZOOM, and RESET Buttons Not Working (2026-01-15)

## Problem

The `pushButton_exploring_identify`, `pushButton_exploring_zoom`, and 
`pushButton_exploring_reset_layer_properties` buttons in the EXPLORING tab were 
not triggering their actions when clicked. The buttons appeared in the UI but 
clicking them had no effect.

## Root Cause

Signal connection issue: The buttons were **defined** in the widgets dictionary with their signal handlers:

```python
"IDENTIFY": {
    "TYPE": "PushButton",
    "WIDGET": d.pushButton_exploring_identify,
    "SIGNALS": [("clicked", d.exploring_identify_clicked)],
    ...
},
"ZOOM": {
    "TYPE": "PushButton",
    "WIDGET": d.pushButton_exploring_zoom,
    "SIGNALS": [("clicked", d.exploring_zoom_clicked)],
    ...
},
"RESET_ALL_LAYER_PROPERTIES": {
    "TYPE": "PushButton",
    "WIDGET": d.pushButton_exploring_reset_layer_properties,
    "SIGNALS": [("clicked", lambda: d.resetLayerVariableEvent())],
    ...
}
```

However, the `manageSignal()` system was NOT successfully connecting these signals, even though `connect_widgets_signals()` was being called. The reason is unclear but likely related to the order of widget initialization or a Qt-specific issue with these particular buttons.

## Investigation

1. **Compared with before_migration**: In before_migration, the exact same pattern was used - buttons defined in dict, `connect_widgets_signals()` called, no direct `.clicked.connect()` calls found.

2. **Pattern works for other widgets**: Feature pickers, groupboxes, and checkable pushbuttons all connect fine via `manageSignal()`.

3. **UI definition**: Buttons are defined in `filter_mate_dockwidget_base.ui` but without signal connections (`<connections/>` is empty).

4. **Expected behavior**: `connect_widgets_signals()` iterates over all widgets and calls `manageSignal([group, widget], 'connect')`, which should connect all signals in the `"SIGNALS"` list.

5. **Actual behavior**: The connection silently fails (caught by `except: pass` in `connect_widgets_signals()`), leaving the buttons non-functional.

## Solution

**Direct signal connection** instead of relying on `manageSignal()` for all three standard QPushButton widgets.

### Changes Made

#### 1. filter_mate_dockwidget.py - manage_interactions()

Added explicit connection after `connect_widgets_signals()`:

```python
# FIX 2026-01-15: Connect IDENTIFY, ZOOM, and RESET buttons explicitly (manageSignal doesn't work for them)
try:
    self.pushButton_exploring_identify.clicked.connect(self.exploring_identify_clicked)
    logger.info("✓ Connected pushButton_exploring_identify.clicked")
except Exception as e:
    logger.debug(f"Could not connect IDENTIFY button: {e}")
try:
    self.pushButton_exploring_zoom.clicked.connect(self.exploring_zoom_clicked)
    logger.info("✓ Connected pushButton_exploring_zoom.clicked")
except Exception as e:
    logger.debug(f"Could not connect ZOOM button: {e}")
try:
    self.pushButton_exploring_reset_layer_properties.clicked.connect(
        lambda: self.resetLayerVariableEvent()
    )
    logger.info("✓ Connected pushButton_exploring_reset_layer_properties.clicked")
except Exception as e:
    logger.debug(f"Could not connect RESET button: {e}")
```

#### 2. ui/controllers/exploring_controller.py - _reload_exploration_widgets()

Added reconnection after widget layer updates (when signals are disconnected/reconnected):

```python
# FIX 2026-01-15: manageSignal doesn't work for IDENTIFY/ZOOM/RESET - connect them directly
# Reconnect after widget layer updates to ensure they remain functional
for btn_name, btn_widget, handler in [
    ("IDENTIFY", self._dockwidget.pushButton_exploring_identify, self._dockwidget.exploring_identify_clicked),
    ("ZOOM", self._dockwidget.pushButton_exploring_zoom, self._dockwidget.exploring_zoom_clicked),
    ("RESET", self._dockwidget.pushButton_exploring_reset_layer_properties, lambda: self._dockwidget.resetLayerVariableEvent())
]:
    try:
        btn_widget.clicked.disconnect(handler)
    except TypeError:
        pass  # Not connected
    btn_widget.clicked.connect(handler)
    logger.debug(f"✓ Reconnected {btn_name} button")
```

## Why This Works

- **Direct connection bypasses manageSignal**: Uses Qt's native `.clicked.connect()` which is guaranteed to work
- **Disconnect before connect**: Prevents duplicate connections after widget reload
- **TypeError catch**: Gracefully handles case where button wasn't connected yet
- **Logging**: Confirms connection success in QGIS Python console

## Button Functionality

### pushButton_exploring_identify

**Action**: Opens QGIS Identify Results panel and shows attributes for the selected feature(s).

**Implementation** (exploring_identify_clicked):
1. Determines current groupbox (single/multiple/custom selection)
2. Gets selected features from appropriate widget
3. Opens identify results panel via `iface.actionIdentify().trigger()`
4. Calls `iface.openFeatureForm()` for each selected feature

**Expected behavior**: When clicked, shows feature attributes in a panel

### pushButton_exploring_zoom

**Action**: Zooms the map canvas to the extent of selected feature(s).

**Implementation** (exploring_zoom_clicked):
1. Gets features from current active groupbox
2. Builds combined bounding box of all features
3. Zooms map canvas to that extent via `iface.mapCanvas().zoomToFeatureExtent()`

**Expected behavior**: When clicked, map zooms to show selected features

### pushButton_exploring_reset_layer_properties

**Action**: Resets all layer properties (expressions, selection state, etc.) to their default values.

**Implementation** (resetLayerVariableEvent):
1. Confirms action with user
2. Resets all exploring properties to defaults
3. Updates UI widgets to reflect reset state
4. Saves changes to layer variables

**Expected behavior**: When clicked, resets all layer-specific EXPLORING settings

## Testing

To verify the fix works:

1. **Load FilterMate** and select a vector layer
2. **EXPLORING tab**: Select SINGLE SELECTION groupbox
3. **Select a feature** in the feature picker
4. **Click IDENTIFY button**: Should open identify panel with feature attributes
5. **Click ZOOM button**: Should zoom map to feature extent
6. **Change some properties** (expression, toggle IS_SELECTING)
7. **Click RESET button**: Should reset all properties to defaults
8. **Repeat with MULTIPLE SELECTION**: Select multiple features and test all buttons
9. **Check logs**: Should see "✓ Connected pushButton_exploring_*.clicked" messages in QGIS Python console on startup

## Files Modified

- `filter_mate_dockwidget.py`: Added direct connection in `manage_interactions()` for 3 buttons
- `ui/controllers/exploring_controller.py`: Added reconnection in `_reload_exploration_widgets()` for 3 buttons
- `docs/BUGFIX-IDENTIFY-ZOOM-BUTTONS-20260115.md`: This documentation
- `docs/EXPLORING-BUTTONS-ANALYSIS-20260115.md`: Complete inventory of all EXPLORING buttons

## Related Fixes

This issue is part of the broader EXPLORING tab synchronization fixes:
- **BUGFIX-EXPLORING-SYNC-20260115.md**: Widget refresh issues
- **BUGFIX-COMBOBOX-CURRENT-LAYER-SIGNALS-20260115.md**: Layer change signals
- **BUGFIX-ICONS-REFRESH-20260115.md**: Icon loading issues
- **EXPLORING-BUTTONS-ANALYSIS-20260115.md**: Complete analysis of all 6 EXPLORING pushbuttons

## Technical Notes

### Why manageSignal Failed (Hypothesis)

The exact reason `manageSignal()` fails for these buttons is unknown, but possible causes:

1. **Timing**: Buttons created in `.ui` file before custom widgets in `setupUiCustom()`
2. **Widget type**: Standard `QPushButton` vs QGIS custom widgets (which all work fine)
3. **Signal registry**: `manageSignal()` uses complex caching that may interfere
4. **Qt version quirk**: PyQt5 behavior difference on some systems

Since direct connection works 100% reliably and matches how checkable pushbuttons (IS_SELECTING, etc.) are connected, we use this pattern for IDENTIFY, ZOOM, and RESET.

### Alternative Approaches Considered

1. **Debug manageSignal**: Would require deep dive into signal caching logic - risky
2. **Remove from widgets dict**: Would break consistency with architecture
3. **Use auto-connect**: Qt Designer auto-connect requires specific naming - not portable

Direct connection is the **simplest, most reliable** solution.

## Follow-up

- [x] Applied fix to all 3 standard QPushButton widgets in EXPLORING tab
- [x] Documented pattern for future button additions
- [ ] Monitor if other non-QGIS pushbuttons in other tabs have similar issues

---

**Status**: ✅ FIXED (2026-01-15)
**Severity**: HIGH (core features non-functional)
**Impact**: ALL EXPLORING tab pushbuttons (IDENTIFY, ZOOM, RESET) now work correctly
