# Raster Exploring/Filtering Sync Fixes — February 7, 2026

## Context
Analysis revealed 6 bugs in the raster exploring ↔ filtering synchronization.
All exploring actions (pixel picker, rect picker, reset range, sync histogram, spinbox changes)
only updated EXPLORING widgets, never FILTERING widgets. Additionally, undo/unfilter/reset
were completely broken for raster layers.

## Changes Made (v6.1)

### New Methods
- `_sync_range_to_filtering_widgets(min_val, max_val)` — Utility method that syncs
  filtering spinboxes + filtering histogram with given range (blockSignals-safe)
- `_on_apply_rect_range_clicked()` — Handler for previously dead pushButton_apply_rect_range.
  Applies rect min/max to histogram spinboxes, exploring histogram, filtering widgets, and criteria
- `_handle_raster_unfilter_reset(task_name)` — Handles 'unfilter' and 'reset' for raster layers.
  Uses style manager or `setDefaultContrastEnhancement()` fallback.

### Modified Methods
- `_on_pixel_values_picked()` — Added `_sync_range_to_filtering_widgets()` + `_update_raster_filter_from_filtering_ui()`
- `_on_add_pixel_to_selection_clicked()` — Now updates ALL spinboxes (min/max + rect_min/max), 
  syncs to filtering, updates criteria
- `_on_raster_reset_range_clicked()` — Added filtering sync + criteria update
- `_on_raster_sync_histogram_action()` — Added filtering sync + criteria update
- `_on_raster_spinbox_range_trigger()` — Added filtering sync + criteria update
- `launchTaskEvent()` — Added raster unfilter/reset bypass (before PROJECT_LAYERS validation)

### Signal Connection
- `pushButton_apply_rect_range.clicked` → `_on_apply_rect_range_clicked` (was disconnected!)

## Bugs Fixed
| Bug | Fix |
|-----|-----|
| P0: pushButton_apply_rect_range dead button | Connected to new handler |
| P1: Picker results not in filtering widgets | All handlers now call _sync_range_to_filtering_widgets |
| P2: Raster undo/unfilter/reset broken | New bypass in launchTaskEvent + _handle_raster_unfilter_reset |
| P3: Reset/Sync only update exploring | Added filtering sync to both handlers |
| P4: Spinbox range trigger not synced | _on_raster_spinbox_range_trigger now syncs filtering |

## Additional Fixes (same session)

### Absolute Imports Fixed (3 files)
- `core/services/raster_filter_service.py:35` — `from infrastructure.logging` → `from ...infrastructure.logging`
- `ui/widgets/raster_histogram_interactive.py:22` — same fix
- `ui/tools/pixel_picker_tool.py:28` — same fix

### API Mismatch Fixed
- `core/strategies/raster_filter_strategy.py:_export_with_exporter()` — Removed invalid
  `config.value_range` assignment (field doesn't exist in RasterExportConfig) and
  fixed `config.clip_layer` → passed `mask_layer` directly in constructor.

## Remaining Issues (not addressed)
- Multi-band asymmetry: Exploring uses QgsCheckableComboBoxBands, Filtering uses plain QComboBox
- No undo/redo stack for raster (only unfilter/reset, no step-back)
- `_on_all_bands_picked` handler not verified