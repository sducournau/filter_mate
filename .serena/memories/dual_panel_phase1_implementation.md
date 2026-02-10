# Dual Panel Phase 1 - Implementation Notes (2026-02-10)

## What was implemented

Phase 1 of the dual Vector/Raster mode: Layer Info + Value Sampling.

### New Files Created

1. **`core/domain/raster_filter_criteria.py`** - Pure Python domain objects (ZERO QGIS imports)
   - `SamplingMethod` enum: CENTROID, POINT_ON_SURFACE, MEAN_UNDER_POLYGON
   - `ComparisonOperator` enum: =, !=, >, >=, <, <=, BETWEEN (with `.evaluate()` method)
   - `RasterSamplingCriteria` frozen dataclass: thread-safe sampling parameters
   - `RasterSamplingResult` dataclass: feature_values mapping, matching_ids, stats
   - `SamplingStats` frozen dataclass: min/max/mean/std/median (with `.from_values()` factory)

2. **`infrastructure/raster/sampling.py`** - Low-level raster sampling functions
   - `sample_raster_at_point()`: atomic single-point sampling
   - `sample_raster_for_features()`: batch sampling with CRS reprojection, cancellation
   - `get_raster_info()`: extract raster metadata (format, bands, COG detection, etc.)
   - Thread-safe: recreates layers from URI, never accepts layer objects
   - Uses `pointOnSurface()` by default (not centroid) for concave polygon safety

3. **`core/tasks/raster_sampling_task.py`** - QgsTask for background sampling
   - `RasterSamplingSignals(QObject)`: completed(result, task_id), error(msg, task_id), progress_updated(processed, total)
   - `RasterSamplingTask(QgsTask)`: stores URIs in __init__, recreates in run()
   - Applies ComparisonOperator filter and computes SamplingStats
   - Cancellation support via QgsFeedback

### Modified Files

4. **`core/domain/__init__.py`** - Added exports: SamplingMethod, ComparisonOperator, RasterSamplingCriteria, RasterSamplingResult, SamplingStats
5. **`core/tasks/__init__.py`** - Added exports: RasterSamplingSignals, RasterSamplingTask
6. **`infrastructure/raster/__init__.py`** - Added exports: sample_raster_at_point, sample_raster_for_features, get_raster_info

7. **`filter_mate_dockwidget.py`** — Replaced placeholder page_raster with real groupboxes:
   - **GroupBox 1: Layer Info** (QFormLayout): name, format, size+pixel, bands+dtype+nodata, CRS, extent
   - **GroupBox 2: Value Sampling** (QFormLayout, collapsible):
     - QgsMapLayerComboBox for raster (raster-only filter)
     - QComboBox for band selection
     - QgsMapLayerComboBox for vector (vector-only filter)
     - QComboBox for method (Point on Surface / Centroid)
     - Operator combo (=, !=, >, >=, <, <=, BETWEEN) + threshold spinbox + BETWEEN max spinbox
     - "Sample" and "Apply Filter" buttons
     - Result label + progress bar
   - Added `_on_raster_operator_changed()` to show/hide BETWEEN widgets

8. **`ui/controllers/raster_exploring_controller.py`** — Fully fleshed out from skeleton:
   - `setup()`: connects sample/apply buttons, raster combo layerChanged
   - `set_raster_layer()`: updates layer info, band combo, syncs raster combo
   - `_on_sample_clicked()`: validates inputs, builds URIs, launches RasterSamplingTask
   - `_on_sampling_complete()`: shows result summary, enables Apply Filter
   - `_on_apply_filter_clicked()`: selectByIds() on vector layer, refreshes canvas
   - Static helpers: _detect_cog, _data_type_string, _map_unit_string

### Architecture Patterns Followed
- Domain purity: `raster_filter_criteria.py` has ZERO QGIS imports
- Thread safety: task stores URIs, recreates layers in run()
- Signal safety: blockSignals(True/False) around programmatic combo changes
- CRS: vector geometries reprojected to raster CRS before sampling
- Cancellation: QgsFeedback integration in sampling loop
- Error handling: no bare excepts, specific exception types
- i18n: self.tr() for all user-visible strings
- Non-invasive: all widgets checked with hasattr/getattr before access

### Validation
- All files pass `ast.parse()` (Python syntax check)
- Domain objects pass 15+ unit tests (enums, evaluation, validation, stats)
- Zero QGIS imports in domain layer confirmed
