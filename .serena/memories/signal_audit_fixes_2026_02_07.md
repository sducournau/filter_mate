# Signal Audit & Fixes - February 7, 2026

**Branch:** fix/widget-visibility-and-styles-2026-02-02
**File:** filter_mate_dockwidget.py
**Status:** All 11 fixes applied + 2 dead code methods cleaned

## Previous Fixes (Feb 5) - Verified OK
All 5 fixes from `raster_signal_fixes_applied_2026_02_05` remain intact.

## New Fixes Applied

### Priority 1 - HIGH (Cascading handlers)
- **S1:** `_on_pixel_values_picked()` (l.2089) — Added blockSignals around 4 spinbox setValue() calls
- **S2:** `_on_raster_reset_range_clicked()` (l.3048) — Added blockSignals around min/max setValue()
- **S3:** `_on_add_pixel_to_selection_clicked()` (l.2189) — Added blockSignals around rect spinbox setValue()

### Priority 2 - MEDIUM (Signal chains)
- **S4:** `_uncheck_raster_tool_buttons()` (l.2777) — Added blockSignals around setChecked(False) in loop
- **S5:** `_on_pixel_picking_finished()` (l.2265) — Removed redundant individual setChecked(False), kept only _uncheck_raster_tool_buttons()
- **S6:** Pixel picker activation (l.2078) — Added blockSignals around setChecked(True)
- **S7:** Rect picker validation (l.2931) — Added blockSignals around setChecked(False)

### Priority 3 - LOW (Non-raster)
- **S8:** `filtering_auto_current_layer_changed()` (l.11421) — Added blockSignals around setChecked(state)
- **S9:** `reset_export_output_path()` / `reset_export_output_pathzip()` — Added blockSignals around setChecked(False)
- **S10:** Export combobox population (l.7012) — Added blockSignals around setCurrentIndex()
- **S11:** Buffer segments optimization (l.5588) — Added blockSignals around setValue(3)

### Dead Code Cleanup
- `_on_raster_range_changed()` — body replaced with pass + deprecation docstring (0 references)
- `_on_raster_predicate_changed()` — body replaced with pass + deprecation docstring (0 references)
- Cleaned up 6-line old comment block (l.1157-1163) → 1-line summary

## Validation
- `python3 -m py_compile` — OK
- Pattern: all fixes use try/finally for blockSignals safety where multiple widgets are involved
