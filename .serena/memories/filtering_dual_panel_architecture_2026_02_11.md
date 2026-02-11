# Filtering Dual Panel Architecture Design (2026-02-11)

## Decision
QStackedWidget inside the FILTERING page of toolBox_tabTools, mirroring the existing `_setup_dual_mode_exploring()` pattern.

## Current State (branch: refactor/quick-wins-2026-02-10)
- Exploring panel: HAS dual mode (Phase 0+1+2)
- Filtering panel: 100% vector, NO dual mode
- Exporting panel: 100% vector, NO dual mode (out of scope)

## Architecture: Single QStackedWidget in FILTERING page

```
horizontalLayout_filtering_main (existing)
 +-- _stacked_filtering (QStackedWidget NEW)
     +-- Page 0 (VECTOR): existing HBox(keys + values) moved here
     +-- Page 1 (RASTER): new HBox(raster_keys + raster_values)
```

## Filtering Widget Classification

### COMMON (both modes):
- pushButton_checkable_filtering_auto_current_layer

### VECTOR ONLY (all existing except auto_current_layer):
- 5 toggle buttons (layers_to_filter, combine_operator, geometric_predicates, buffer_value, buffer_type)
- All right-column widgets (combos, spinboxes, etc.)

### RASTER NEW widgets:
- Left column: 3 buttons (band, range, vector_target)
- Right column: raster layer combo, band combo, operator, min/max spinboxes, vector target combo, method combo, apply button, result label, progress bar

## Key Design Decisions
1. **Separate combo for raster** (not reusing comboBox_filtering_current_layer) to avoid signal conflicts
2. **Separate FILTERING_RASTER group** in ConfigManager widgets dict
3. **Reuse existing DualModeToggle** - one toggle controls N stacked widgets
4. **Extend _on_dual_mode_layer_changed** for filtering switch
5. **100% reuse** of Phase 1 domain/task/infra (raster_filter_criteria, raster_sampling_task, sampling.py)

## New Files
- ui/controllers/raster_filtering_controller.py (~300-500 lines)

## Modified Files
- filter_mate_dockwidget.py: add _setup_dual_mode_filtering(), extend _on_dual_mode_layer_changed
- ui/controllers/integration.py: register RasterFilteringController
- ui/controllers/registry.py: add entry
- ui/managers/configuration_manager.py: add FILTERING_RASTER widgets group

## Effort: 6-9 days total
- Phase A: QStackedWidget creation + widget construction (2-3d)
- Phase B: RasterFilteringController (2-3d)
- Phase C: Wiring + ConfigManager (1d)
- Phase D: Manual testing + signal debugging (1-2d)

## Risks
- comboBox_filtering_current_layer referenced ~30 places -> keep untouched in vector page
- ConfigManager FILTERING signals are all vector-centric -> separate FILTERING_RASTER group
- Toggle controls 2+ stacked widgets -> one signal, multiple connections
