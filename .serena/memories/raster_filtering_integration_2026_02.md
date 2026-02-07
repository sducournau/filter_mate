# Raster Filtering Integration (v6.0) — February 2026

## Overview
Integrated raster filtering (histogram + range) into the FILTERING section of FilterMate.
Previously, the filtering section was 100% vector-only. Now it supports both layer types
via a QStackedWidget with page 0 (vector) and page 1 (raster).

## Architecture

### QStackedWidget Structure
```
verticalLayout_filtering_values
├── horizontalLayout_filtering_source_layer  ← SHARED (comboBox_filtering_current_layer)
└── stackedWidget_filtering
    ├── page_filtering_vector (index 0)  ← existing widgets moved at runtime
    │   ├── layers_to_filter combobox
    │   ├── combine operator
    │   ├── geometric predicates
    │   └── buffer controls
    └── page_filtering_raster (index 1)  ← created programmatically
        ├── comboBox_band_filtering
        ├── _filtering_raster_histogram (RasterHistogramInteractiveWidget)
        ├── [min] ─── [max] doubleSpinBox_filtering_min/max
        └── comboBox_filtering_predicate (RasterPredicate enum)
```

### Signal Flow
```
comboBox_filtering_current_layer.layerChanged
  → current_layer_changed(layer, manual_change=True)
    → _auto_switch_exploring_page(layer)      [toolBox_exploring: page 0=vector, 1=raster]
      → _auto_switch_filtering_page(layer)    [stackedWidget_filtering: page 0=vector, 1=raster]
        → _sync_filtering_raster_widgets_with_layer(layer) [if raster]
          → _populate_filtering_raster_band_combobox(layer)
          → _populate_filtering_raster_predicate_combobox()
          → QTimer.singleShot(100, _update_filtering_raster_histogram) [deferred]
```

### Raster Filtering Signal Handlers
- `_on_filtering_histogram_range_changed(min, max)` → syncs spinboxes (blockSignals)
- `_on_filtering_histogram_range_finished(min, max)` → creates RasterFilterCriteria
- `_on_filtering_raster_band_changed(index)` → refreshes histogram for new band
- `_on_filtering_raster_predicate_changed(index)` → updates criteria
- `_update_raster_filter_from_filtering_ui()` → builds `_current_raster_criteria`

### Filter Execution Pipeline (Raster)
```
launchTaskEvent('filter') [with raster layer]
  → checks isinstance(self.current_layer, QgsRasterLayer)
  → builds _current_raster_criteria if not set
  → self.launchingTask.emit('filter')
  → TaskOrchestrator picks up criteria from dockwidget
```

## Bug Fixes (Phase 1)

### Race condition in `_enable_toolbox_page_for_switch`
- **Root cause**: Method managed `_programmatic_page_change` flag internally, but caller
  `_auto_switch_exploring_page` also managed it. Inner `finally` reset flag to False
  before caller finished work.
- **Fix**: Removed flag management from inner method. Caller manages flag exclusively.

### Redundant `_auto_switch_exploring_page` calls
- `current_layer_changed()` called `_auto_switch_exploring_page()` both pre-validation
  AND post-validation. Post-validation call was redundant.
- Kept only pre-validation call (ensures UI reflects layer type even if validation fails).

## Key Design Decisions
1. **No .ui file changes** — all done programmatically (runtime widget creation/movement)
2. **Shared source layer row** — `horizontalLayout_filtering_source_layer` stays outside QStackedWidget
3. **Deferred histogram** — 100ms QTimer.singleShot to avoid QGIS freeze during stats computation
4. **Signal safety** — all programmatic setValue() wrapped in blockSignals(True/False)
5. **QSS-managed dimensions** — DimensionsManager is deprecated, all sizes in default.qss

## Files Modified
- `filter_mate_dockwidget.py` — Main changes (setup, auto-switch, sync, signals, launchTaskEvent)
- `resources/styles/default.qss` — QSS for new raster filtering widgets

## Future Roadmap
- Phase 2: RGB segmentation / smart selection (orthophoto) — new stacked page
- Multi-band filtering support
- Classification-based filtering
