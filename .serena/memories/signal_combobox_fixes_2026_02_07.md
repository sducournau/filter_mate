# comboBox_filtering_current_layer Signal & layers_to_filter Fixes (2026-02-07)

## Problem
1. Changing `comboBox_filtering_current_layer` didn't trigger exploring/filtering page switch
2. `layers_to_filter` multicombobox was not populated

## Root Cause
**Primary:** `blockSignals(True)` stuck on `comboBox_filtering_current_layer` after a filter task
terminated (failed/cancelled). The `FilterEngineTask` had NO `taskTerminated` handler, so:
- `blockSignals(True)` stayed permanently set → `layerChanged` signal silenced
- `_filtering_in_progress = True` stayed set
- `CURRENT_LAYER.layerChanged` signal stayed disconnected

**Secondary:** No validation of `layerChanged` signal connection state (only pushbuttons were checked)

**Tertiary:** `layers_to_filter` not populated on raster→vector switch (only populated in
`_synchronize_layer_widgets` which only runs for vector layers when full `current_layer_changed` completes)

## Fixes Applied

### 1. `_validate_and_force_reconnect_current_layer_signal()` — dockwidget.py
- Added to `_validate_signal_connections()` (called at end of `manage_interactions`)
- Checks `comboBox.signalsBlocked()` and resets if True
- Checks actual Qt signal state (bypasses cache) and force reconnects if disconnected

### 2. `launchTaskEvent` blockSignals safety — dockwidget.py
- At the top of `launchTaskEvent`, resets `blockSignals(False)` if stuck

### 3. `_handle_filter_task_terminated()` — filter_mate_app.py
- NEW handler connected to `FilterEngineTask.taskTerminated` signal
- Resets `_filtering_in_progress`, unblocks comboBox signals, reconnects `layerChanged`

### 4. `_check_and_reset_stale_flags` enhanced — filter_mate_app.py
- Added check for comboBox blockSignals stuck True without active filtering

### 5. `_auto_switch_filtering_page` layers_to_filter population — dockwidget.py
- When switching to vector page, if `layers_to_filter` widget is empty, populates it immediately

## Files Modified
- `filter_mate_dockwidget.py`
- `filter_mate_app.py`
