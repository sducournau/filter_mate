# Merge Analysis: v9.0 Integration into main (v6.0 architecture)
## Date: 2026-02-09

## Decision
- **Chosen approach**: Full v9.0 unified filtering (replace v5.4 L1-L5 dedicated widgets)
- **Branch**: new branch from `origin/main`
- **Source**: `fix/widget-visibility-and-styles-2026-02-02` (16 commits, 2 fév→8 fév)

## Key Architecture Difference
- main has `RasterExploringManager` (extracted from dockwidget in P3.1)
- fix branch works directly on dockwidget (pre-extraction)
- v9.0 unified filtering reuses exploring widgets (band, histogram, predicate, spinboxes)
- This means v9.0 code must interact with `RasterExploringManager` instead of direct widget access

## Items to Integrate (24 items)

### Backend (I1-I10) - port directly
- I1: Thread safety tasks (URI instead of QObject) - raster_range_filter_task.py, raster_mask_task.py
- I2: 7 predicates complete - raster_filter_strategy.py
- I3: Mask inversion _create_inverted_mask() - raster_filter_service.py
- I4: Geometry cloning before transform - raster_filter_service.py
- I5: Non-destructive filter (VRT/GeoTIFF) - raster_range_filter_task.py
- I6: COG export GDAL direct - raster_exporter.py
- I7: QGIS 3.30 compat - pixel_picker_tool.py, tasks, strategy
- I8: TransparentSingleValuePixel 3 args - raster_range_filter_task.py
- I9: Progress signals (int, str) - raster_exporter.py
- I10: PK detection simplified - raster_filter_service.py

### UI/UX (I11-I17) - adapt to v6.0 arch
- I11: _adapt_filtering_widgets_for_layer_type() - dockwidget
- I12: Single-select predicate for raster - dockwidget
- I13: Result feedback label - dockwidget, QSS
- I14: Auto-detection mode (transparency vs vector-by-raster) - dockwidget
- I15: QButtonGroup for raster tool buttons - raster_exploring_manager.py
- I16: 11 signal guards (blockSignals) - dockwidget
- I17: Raster transparency filter complete - dockwidget

### Styling (I18-I24) - port with minor adaptation
- I18: ToolBoxIconAlignStyle (QProxyStyle) - new file
- I19: Widget heights unified 26px - QSS
- I20: Remove non-functional CSS - QSS
- I21: Zero margin/padding widget keys - QSS, dimensions_manager
- I22: Icon sizes increased - button_styler
- I23: Theme apply unpolish/polish/update - theme_manager
- I24: Config fallback paths - base_styler, theme_manager

### Do NOT integrate
- X1: Debug scripts
- X2: resources_rc.py (regenerate)
- X3: Files deleted on main (orchestrator, etc.)
- X4: v9.0 code as-is (must adapt to v6.0)

## Critical Adaptation Point
v9.0's `_setup_unified_filtering_widgets()` adds only 2 widgets (sampling + result label)
and relies on exploring widgets for everything else. On main, exploring widgets are managed
by `RasterExploringManager`. The manager accesses widgets via `self.dockwidget.widget_name`,
so the dockwidget can still access them directly — no blocking issue.

## Implementation Plan
Full plan saved to: `_bmad-output/PLAN-V9-INTEGRATION-INTO-MAIN.md`

### 6 Phases:
1. Backend raster (I1-I10): thread safety, predicates, compat — direct port
2. Styling/QSS (I18-I24): heights 26px, ToolBoxIconAlignStyle, zero margins
3. **Replace v5.4 → v9.0** (I11-I14, I17): remove 200-line dedicated section, add unified filtering
4. QButtonGroup enhancements (I15) in RasterExploringManager
5. Signal guards (I16): 11 blockSignals additions
6. Cleanup & validation

### Key Decisions:
- v9.0 dispatch goes directly in `launchTaskEvent` (NOT via FilteringController)
- Bug fix: store `_last_raster_filter_mode` to fix unfilter mode mismatch
- RasterExploringManager already has QButtonGroup — just enhance

### Files Most Impacted:
- `filter_mate_dockwidget.py`: Phase 3 core (remove v5.4, add v9.0)
- `raster_range_filter_task.py`: Phase 1 (thread safety)
- `raster_filter_strategy.py`: Phase 1 (7 predicates)
- `default.qss`: Phase 2 (harmonization)
- `raster_filter_service.py`: Phase 1 (mask inversion, PK)