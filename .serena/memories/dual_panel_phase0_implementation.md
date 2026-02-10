# Dual Panel Phase 0 - Implementation Notes (2026-02-10)

## What was implemented

Phase 0 of the dual Vector/Raster mode for the Exploring panel.

### New Files Created
1. **`ui/widgets/dual_mode_toggle.py`** - `DualModeToggle` widget (segment control V/R)
   - `DualMode` enum (VECTOR=0, RASTER=1)
   - `modeChanged` signal (int)
   - Auto-styled with palette-based QSS
   - `setMode()` for programmatic switching

2. **`ui/controllers/raster_exploring_controller.py`** - Skeleton `RasterExploringController`
   - Extends `BaseController`
   - `raster_layer_changed` signal
   - `set_raster_layer()` method
   - Phase 0: no-op setup/teardown

3. **`infrastructure/raster/__init__.py`** - Empty package for future raster infra

### Modified Files
4. **`ui/widgets/__init__.py`** - Added `DualModeToggle`, `DualMode` exports
5. **`ui/controllers/integration.py`** - Registered `RasterExploringController`
6. **`filter_mate_dockwidget.py`** - Two new methods:
   - `_setup_dual_mode_exploring()` called from `setupUiCustom()`
   - `_on_dual_mode_layer_changed()` for auto-detection

### How it works
- `setupUiCustom()` calls `_setup_dual_mode_exploring()` after `_setup_exploring_tab_widgets()`
- Creates a `QStackedWidget` (`_stacked_exploring`) inside `verticalLayout_exploring_tabs_content`
- Page 0 (vector): existing 3 groupboxes moved here
- Page 1 (raster): placeholder label "Raster Exploring"
- `DualModeToggle` inserted at index 0 of `verticalLayout_main_content` (above scrollArea)
- Auto-detection: `iface.layerTreeView().currentLayerChanged` → `_on_dual_mode_layer_changed()`
- Raster layer → switches to RASTER page + updates `RasterExploringController`
- Vector layer → switches to VECTOR page

### Key Design Decisions
- All programmatic (no .ui file changes) - enables gradual rollout
- Toggle uses QPalette colors (adapts to any QGIS theme)
- Controller registered in integration.py following existing patterns
- `_raster_exploring_ctrl` property on dockwidget for convenient access
