# Raster Critical Bugs Fixed - February 7, 2026

**Branch:** fix/widget-visibility-and-styles-2026-02-02
**Status:** ✅ All 10 bugs fixed

## Summary

Fixed all 10 critical/high/medium raster bugs identified in the audit.
1384 lines of dead code removed, 7 files modified, 3 files deleted.

## Fixes Applied

### Phase 1 — Quick Wins
| Bug | Fix | File |
|-----|-----|------|
| #1 Missing `supported_layer_type` | Added property returning `LayerType.RASTER` | `core/strategies/raster_filter_strategy.py` |
| #8 Duplicate `RasterPredicate` | Removed duplicate from service, import from `filter_criteria` | `core/services/raster_filter_service.py` |
| #5+10 Dead code (1384 lines) | Deleted 3 files, cleaned `__init__.py` exports | 5 files |

### Phase 2 — Functional Fixes
| Bug | Fix | File |
|-----|-----|------|
| #4 MASK_INSIDE no-op | Implemented `_create_inverted_mask()` using `QgsGeometry.difference()` | `core/services/raster_filter_service.py` |
| #7 `_update_raster_filter_from_ui()` stub | Creates `RasterFilterCriteria`, updates histogram, stores criteria | `filter_mate_dockwidget.py` |

### Phase 3 — Data Integrity
| Bug | Fix | File |
|-----|-----|------|
| #3 Source layer mutation | `_create_memory_layer()` uses VRT, `_create_file_based_layer()` uses `gdal.Translate` | `core/tasks/raster_range_filter_task.py` |
| #2 Thread safety | Store URI/metadata in `__init__`, recreate layers from URI in `run()` | Both task files |

### Phase 4 — Architecture
| Bug | Fix | File |
|-----|-----|------|
| #9 Strategy→Service wiring | Added `_apply_mask_filter()` delegating to `service.apply_vector_to_raster()` for mask ops | `core/strategies/raster_filter_strategy.py` |
| #6 COG export | Replaced double `gdal:translate` with `gdal.Translate(format='COG')` + version check | `core/export/raster_exporter.py` |

## Files Changed
- `core/strategies/raster_filter_strategy.py` — +property, +mask delegation method
- `core/services/raster_filter_service.py` — dedup enum, +inverted mask, fix _mask_raster
- `core/tasks/raster_range_filter_task.py` — thread safety + VRT/copy approach
- `core/tasks/raster_mask_task.py` — thread safety (URI-based)
- `core/export/raster_exporter.py` — real COG driver
- `filter_mate_dockwidget.py` — stub → real implementation
- `ui/tools/__init__.py` — cleaned exports
- `ui/widgets/__init__.py` — cleaned exports

## Files Deleted
- `ui/widgets/raster_histogram.py` (506 lines)
- `ui/tools/raster_canvas_tools.py` (537 lines)
- `ui/widgets/raster_tools_keys.py` (341 lines)

## Remaining from Audit (26 bugs)
- 10 high priority bugs (not yet addressed)
- 10 medium priority bugs
- 6 low priority bugs
- See `raster_audit_2026_02_07` memory for full list
