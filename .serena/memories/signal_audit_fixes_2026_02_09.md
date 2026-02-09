# Qt Signal Audit - Fixes Applied (2026-02-09)

## Files Modified

### `ui/managers/raster_exploring_manager.py`
- **C1**: Fixed signal name mismatch in teardown: `rangeFinished` → `rangeSelectionFinished` (L141)
- **C2**: Added `blockSignals(True/False)` around `setValue/setMinimum/setMaximum` in `_refresh_statistics()` (L1027-1036)
- **C3**: Added `blockSignals(True/False)` around `setChecked(False)` in `_uncheck_tool_buttons()` (L1406-1408)
- **H1**: Added `blockSignals` in `_on_pixel_picking_finished()` (L930-932)
- **H2**: Added `blockSignals` in `_activate_pixel_picker_tool()` (L681-683)
- **H3**: Added `blockSignals` in `_on_rect_picker_clicked()` error path (L713-715)
- **H10**: Added `blockSignals` around `QgsCheckableComboBoxBands.setLayer()` in `populate_band_combobox()` (L1196-1198)
- **Dead code removal**: Removed `_on_range_changed()` and `_on_predicate_changed()` (were only called from removed dockwidget stubs)

### `filter_mate_dockwidget.py`
- **H4/H5**: Removed duplicate signal connections for `doubleSpinBox_min/max.valueChanged` and `comboBox_predicate.currentIndexChanged` (L1028-1033) - already connected in `RasterExploringManager._connect_combobox_triggers()`
- **H4/H5**: Removed dead code stubs `_on_raster_range_changed()` and `_on_raster_predicate_changed()`
- **H7/H8**: Added `blockSignals(True/False)` in `_populate_export_combobox_direct()` for `layers_widget` and `datatype_widget`
- **L4**: Added `blockSignals` around `setLayer(None)` calls in `closeEvent` to prevent signals during shutdown

## Issues Verified as Not Bugs
- **C4**: `_on_raster_source_toggled()` already had blockSignals
- **H9**: `reset_export_output_path/pathzip` `setChecked(False)` is intentional (triggers `_toggle_associated_widgets`)
- **M4**: Duplicate groupbox setup in `dockwidget_signal_manager` is dead code (never called in production)
- **M1**: `_toolbox_bridge` signals auto-disconnect when parent QObject is destroyed
- **M3**: `config_model.itemChanged` disconnect/connect always paired correctly

## Remaining MEDIUM/LOW Issues (not fixed - larger refactoring)
- **M-general**: 91 raw `blockSignals(True)` calls across 20 files; `SignalBlocker`/`SignalBlockerGroup` never used in production
- **M-general**: `ConnectionManager` never used in production code
- **M5**: 5 sequential QTimers for combobox restoration (fragile but functional)
- **L2**: `_programmatic_page_change` flag pattern (protected by try/finally, works correctly)
