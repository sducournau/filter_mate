# Dual Panel Vector/Raster Design Summary (Atlas, 2026-02-10)

## Decision: QStackedWidget + Auto-Detection + Toggle Fallback
- QStackedWidget inside frame_exploring (and inside each QToolBox page for Filtering/Exporting)
- Auto-detect layer type via `iface.layerTreeView().currentLayerChanged`
- Segment-control toggle (QPushButton pair in QButtonGroup) in frame_header as fallback
- One toggle controls ALL panels synchronously

## Raster Exploring: 6 GroupBoxes
1. **Layer Info** (P0, 0.5d) - Metadata display
2. **Value Sampling** (P1-bis, 3-5d) - Sample raster at vector features, filter by value
3. **Histogram** (P2, 1-2w) - Interactive histogram with range slider, debounced highlight
4. **Zonal Stats** (P1, 2-3w) - THE differentiator, filter vectors by raster stats under polygons
5. **Object Detection** (P3, 1w-1m) - Template matching (L1), SAM (L2), YOLO (L3)
6. **Band Viewer** (P2-bis, 1w) - Band table, preset compositions, spectral indices

## New Files (~25 files)
- core/domain/raster_filter_criteria.py, raster_stats_result.py
- core/services/raster_filter_service.py, raster_sampling_service.py, raster_stats_service.py
- core/tasks/raster_sampling_task.py, raster_stats_task.py, raster_export_task.py
- infrastructure/raster/{sampling,zonal_stats,histogram,masking,export,band_utils}.py
- infrastructure/raster/detection/{template_matching,sam_integration,model_loader}.py
- ui/controllers/raster_{exploring,filtering,exporting}_controller.py
- ui/widgets/{raster_histogram_widget,band_composition_widget,dual_mode_toggle}.py
- ui/tools/raster_pixel_picker_tool.py
- config/raster_config.py

## Existing File Changes (minimal, wiring only)
- filter_mate_dockwidget_base.ui: Add QStackedWidget + toggle
- filter_mate_dockwidget.py: Init stacked, auto-detect, toggle handler
- ui/controllers/integration.py: Register 3 raster controllers
- ui/controllers/registry.py: Add entries
- filter_mate_app.py: Register raster services
- adapters/app_bridge.py: Expose raster services
- config/config.json: Add RASTER section

## Phasing
- Phase 0 (1w): Dual mode foundation (toggle + stacked + skeleton controller)
- Phase 1 (1w): Layer Info + Value Sampling (the quick win)
- Phase 2 (2w): Histogram + Band Viewer
- Phase 3 (2-3w): Zonal Stats (THE differentiator)
- Phase 4 (2w): Export Raster + Filtering dual
- Phase 5 (1-2w): Object Detection L1 (template matching)

## Key Technical Constraints
- Thread safety: Store URI in __init__, recreate layers in run()
- CRS: Always reproject vector to raster CRS before sampling
- pointOnSurface() not centroid() for concave polygons
- QgsZonalStatistics writes in-place -> use temp memory layer
- Graceful degradation for optional deps (cv2, torch, segment-anything)

## Full document: DUAL_PANEL_DESIGN_ATLAS.md (root of project)
