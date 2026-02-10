# Signal & ComboBox Fixes - 2026-02-10

## Problem
Layers not appearing in filtering and exporting comboboxes due to signal issues.

## Root Causes & Fixes Applied

### BUG 1 (CRITICAL): `_filtering_in_progress` stuck True permanently
- **Files**: `adapters/filter_result_handler.py`, `filter_mate_app.py`, `filter_mate_dockwidget.py`
- **Cause**: `unblock_and_reconnect_combobox()` timer callback (1.5s) had exception handler that didn't reset flag
- **Fix**: 
  1. Added safety reset in `except` block of `unblock_and_reconnect_combobox()`
  2. Added `_filtering_in_progress_timestamp` tracking in dockwidget
  3. Added `_filtering_in_progress` stale flag detection in `_check_and_reset_stale_flags()`
  4. Set timestamp in `_set_filter_protection_flags()`

### BUG 2 (CRITICAL): `_handle_project_cleared` fires layerChanged(None) without blockSignals
- **File**: `filter_mate.py`
- **Cause**: `setLayer(None)` and `clear()` called without blocking signals, causing cascading `current_layer_changed(None)`
- **Fix**: Wrapped in `blockSignals(True/False)` with error-safe unblock. Also resets `_filtering_in_progress`.

### BUG 3 (MAJOR): Dual signal cache desynchronization
- **File**: `ui/managers/dockwidget_signal_manager.py`
- **Cause**: `DockwidgetSignalManager.manage_signal()` only updated its own cache, not `dockwidget._signal_connection_states`
- **Fix**: Added `self.dockwidget._signal_connection_states[state_key] = state` sync in `manage_signal()`

### BUG 4 (MAJOR): Silent exception swallowing in connect/disconnect_widgets_signals
- **File**: `ui/managers/dockwidget_signal_manager.py`
- **Cause**: Blanket `except Exception: pass` hid critical connection failures
- **Fix**: Changed to `except TypeError: pass` (expected) + `except Exception: logger.warning(...)` (unexpected)

### BUG 5 (MEDIUM): Raster layers completely ignored in `_on_layers_added`
- **Files**: `filter_mate_app.py`, `core/tasks/layer_management_task.py`
- **Cause**: `_on_layers_added` early-returned for non-vector batches; `add_project_layer` rejected non-QgsVectorLayer
- **Fix**: 
  1. `_on_layers_added` now includes valid QgsRasterLayer alongside vectors
  2. `add_project_layer` now creates minimal metadata for raster layers
  3. Controllers already handled rasters in populate methods

## Files Modified (6 total)
1. `adapters/filter_result_handler.py` - BUG 1: safety reset in except
2. `filter_mate_app.py` - BUG 1: timestamp + stale flag check; BUG 5: raster passthrough
3. `filter_mate_dockwidget.py` - BUG 1: `_filtering_in_progress_timestamp` init
4. `filter_mate.py` - BUG 2: blockSignals in _handle_project_cleared
5. `ui/managers/dockwidget_signal_manager.py` - BUG 3: cache sync; BUG 4: logging
6. `core/tasks/layer_management_task.py` - BUG 5: raster layer support
