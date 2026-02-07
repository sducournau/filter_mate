# Raster Subsystem Audit - February 7, 2026

## Key Findings

**36 bugs total:** 10 critical, 10 high, 10 medium, 6 low
**Effective test coverage:** ~10-15%

### Critical:
1. `RasterFilterStrategy` missing `supported_layer_type` → cannot instantiate
2. Thread safety violations in `RasterMaskTask` + `RasterRangeFilterTask` (store layer refs across threads)
3. `RasterRangeFilterTask` mutates source layer (no copy, no backup)
4. `MASK_INSIDE` is a no-op (TODO in code)
5. `raster_histogram.py` is deprecated + broken (500 lines dead code)
6. COG export doesn't produce actual COG

### Dead Code (878+ lines):
- `RasterCanvasToolsController` - never imported
- `RasterToolButtonManager` - never imported
- `RasterToolsKeysWidget` - never imported
- `RasterHistogramWidget` (raster_histogram.py) - deprecated, broken

### Architecture Issues:
- `_update_raster_filter_from_ui()` is a STUB (placeholder comment)
- Duplicate `RasterPredicate` enum in two locations
- Strategy never delegates to service (despite docstring claim)
- Absolute imports in 3 files (will break in standard QGIS loading)

### Tests:
- 7+ tests will FAIL (field name mismatches)
- 11 tests are tautological (test mocks, not real code)
- 0% coverage on all primary public APIs
