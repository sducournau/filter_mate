# Signal Audit C1: selectionChanged Centralization

**Date:** 2026-02-10
**Issue:** C1 - selectionChanged signal connected in 7 code paths across 3 files, only 2 disconnect points. Caused signal stacking.

## Solution
Created centralized `_connect_selection_signal()` / `_disconnect_selection_signal()` in `filter_mate_dockwidget.py`.

### New Methods (dockwidget lines ~329-388)
- `_connect_selection_signal(layer=None)`: Safe disconnect-then-connect. Uses `safe_disconnect` to prevent stacking.
- `_disconnect_selection_signal()`: Safe disconnect via `safe_disconnect`. Sets flag to `None`.
- `_ensure_layer_signals_connected(layer)`: Now a thin wrapper delegating to `_connect_selection_signal(layer)`.
- `_ensure_selection_changed_connected()`: Now a thin wrapper delegating to `_connect_selection_signal()`.

### Files Modified
1. **filter_mate_dockwidget.py**
   - Added `safe_disconnect` import from `infrastructure.utils`
   - Replaced `_ensure_layer_signals_connected` body with centralized pair + wrapper
   - Replaced `_ensure_selection_changed_connected` body with delegation
   - L2329: `_setup_widgets_and_controllers` end -> calls `_connect_selection_signal()`
   - L5154: `on_layer_selection_changed` self-healing removed -> just syncs flag
   - L5656: `_validate_and_prepare_layer` disconnect -> calls `_disconnect_selection_signal()`
   - L6019: `_fallback_reconnect_layer_signals` -> calls `_connect_selection_signal()`

2. **ui/controllers/exploring_controller.py**
   - L2917: `handle_layer_selection_changed` self-healing removed -> just syncs flag

3. **ui/controllers/layer_sync_controller.py**
   - L1130: `_connect_layer_selection_signal` -> delegates to `dw._connect_selection_signal()`

### Verification
- All 4 files pass `py_compile` (dockwidget, exploring_controller, layer_sync_controller, dockwidget_signal_manager)
- Only one direct `.selectionChanged.connect()` call remains in entire codebase (inside `_connect_selection_signal`)
- Only `safe_disconnect` calls handle disconnection (inside `_connect_selection_signal` and `_disconnect_selection_signal`)
