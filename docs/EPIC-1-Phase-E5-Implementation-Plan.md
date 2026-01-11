# EPIC-1 Phase E5: Code Consolidation & Final Extractions

**Status:** IN PROGRESS  
**Date:** January 11, 2026  
**Estimated Effort:** 3-4 sessions

## Overview

Phase E5 continues the refactoring of `filter_task.py` by:

1. Completing Strangler Fig delegations for methods already extracted
2. Removing legacy code where delegations are working
3. Extracting remaining utility methods to appropriate modules

## Progress Summary

### E5-S1: Legacy Code Removal from prepare_*_source_geom (COMPLETED ✅)

Removed legacy fallback implementations from methods with working Strangler Fig delegations:

| Method                             | Before     | After     | Saved            |
| ---------------------------------- | ---------- | --------- | ---------------- |
| `prepare_postgresql_source_geom()` | ~150 lines | ~30 lines | **~120 lines**   |
| `prepare_ogr_source_geom()`        | ~450 lines | ~45 lines | **~405 lines**   |
| `prepare_spatialite_source_geom()` | ~690 lines | ~55 lines | **~635 lines**   |
| **Total E5-S1**                    |            |           | **~1,160 lines** |

**File size**: 12,894 → 11,769 lines (**-1,125 lines**, ~8.7% reduction)

### E5-S2: Memory Layer Operations (COMPLETED ✅)

Removed legacy fallback code from memory layer methods with v4.0 delegations:

| Method                                 | Before     | After    | Saved           |
| -------------------------------------- | ---------- | -------- | --------------- |
| `_copy_filtered_layer_to_memory()`     | ~109 lines | ~27 lines | **~82 lines**   |
| `_copy_selected_features_to_memory()`  | ~115 lines | ~26 lines | **~89 lines**   |
| `_create_memory_layer_from_features()` | ~109 lines | ~27 lines | **~82 lines**   |
| `_create_buffered_memory_layer()`      | ~86 lines  | ~26 lines | **~60 lines**   |
| **Total E5-S2**                        |            |           | **~313 lines**  |

**File size**: 11,769 → 11,456 lines (**-313 lines**, ~2.7% reduction)

### Combined Progress (E5-S1 + E5-S2)

**Total removed**: 1,438 lines  
**File size**: 12,894 → 11,456 lines (**-11.1% reduction**)

---

## Current State Analysis

### Phase E4 Completed ✅

| Backend    | Functions | Lines     | Status      |
| ---------- | --------- | --------- | ----------- |
| PostgreSQL | 14        | 882       | ✅ Complete |
| Spatialite | 16        | 1,147     | ✅ Complete |
| OGR        | 12        | 888       | ✅ Complete |
| **TOTAL**  | **42**    | **2,917** | Extracted   |

### Strangler Fig Delegations Active

**core/geometry** (buffer_processor.py, geometry_repair.py):

- `create_buffered_memory_layer()` → delegated
- `aggressive_geometry_repair()` → delegated
- `repair_invalid_geometries()` → delegated

**core/export** (layer_exporter.py, style_exporter.py):

- `save_layer_style()` → delegated

## Methods to Extract in E5

### Category 1: Memory Layer Operations (~450 lines)

| Method                                 | Lines | Target Module                    | Priority |
| -------------------------------------- | ----- | -------------------------------- | -------- |
| `_copy_filtered_layer_to_memory()`     | ~110  | core/geometry/layer_utils.py     | HIGH     |
| `_copy_selected_features_to_memory()`  | ~115  | core/geometry/layer_utils.py     | HIGH     |
| `_create_memory_layer_from_features()` | ~110  | core/geometry/layer_utils.py     | HIGH     |
| `_convert_layer_to_centroids()`        | ~80   | core/geometry/layer_utils.py     | MEDIUM   |
| `_fix_invalid_geometries()`            | ~25   | core/geometry/geometry_repair.py | LOW      |

### Category 2: Expression Processing (~350 lines)

| Method                       | Lines | Target Module                       | Priority |
| ---------------------------- | ----- | ----------------------------------- | -------- |
| `_process_qgis_expression()` | ~70   | core/filter/expression_processor.py | HIGH     |
| `_combine_with_old_subset()` | ~250  | core/filter/expression_processor.py | HIGH     |
| `_sanitize_subset_string()`  | ~160  | core/filter/expression_processor.py | MEDIUM   |

### Category 3: Canvas/UI Operations (~300 lines)

| Method                      | Lines | Target Module                   | Priority |
| --------------------------- | ----- | ------------------------------- | -------- |
| `_single_canvas_refresh()`  | ~140  | adapters/qgis/canvas_manager.py | MEDIUM   |
| `_delayed_canvas_refresh()` | ~110  | adapters/qgis/canvas_manager.py | MEDIUM   |
| `_final_canvas_refresh()`   | ~45   | adapters/qgis/canvas_manager.py | MEDIUM   |

### Category 4: Export Utilities (~400 lines) - Partial

| Method                        | Lines | Target Module                 | Priority |
| ----------------------------- | ----- | ----------------------------- | -------- |
| `_save_layer_style_lyrx()`    | ~100  | core/export/style_exporter.py | LOW      |
| `_convert_symbol_to_arcgis()` | ~65   | core/export/style_exporter.py | LOW      |
| `_create_zip_archive()`       | ~70   | core/export/archive_utils.py  | LOW      |
| `_export_with_streaming()`    | ~125  | core/export/layer_exporter.py | MEDIUM   |

### Category 5: Geometry Utilities (~300 lines)

| Method                                | Lines | Target Module                        | Priority |
| ------------------------------------- | ----- | ------------------------------------ | -------- |
| `_simplify_source_for_ogr_fallback()` | ~130  | core/geometry/geometry_simplifier.py | MEDIUM   |
| `_verify_and_create_spatial_index()`  | ~50   | core/geometry/layer_utils.py         | HIGH     |
| `_reproject_layer()`                  | ~40   | core/geometry/layer_utils.py         | MEDIUM   |

## Implementation Strategy

### Session E5-S1: Memory Layer Utilities

**Goal:** Create `core/geometry/layer_utils.py` (~400 lines)

1. Create `layer_utils.py` module
2. Extract memory layer operations:
   - `copy_filtered_layer_to_memory()`
   - `copy_selected_features_to_memory()`
   - `create_memory_layer_from_features()`
   - `verify_and_create_spatial_index()`
3. Add Strangler Fig delegations
4. Test with existing workflows

### Session E5-S2: Expression Processing

**Goal:** Create `core/filter/expression_processor.py` (~350 lines)

1. Create `expression_processor.py` module
2. Extract expression handling:
   - `process_qgis_expression()`
   - `combine_with_old_subset()`
   - `sanitize_subset_string()`
3. Add Strangler Fig delegations
4. Test attribute filtering

### Session E5-S3: Canvas Manager

**Goal:** Create `adapters/qgis/canvas_manager.py` (~300 lines)

1. Create `canvas_manager.py` module
2. Extract canvas operations:
   - `single_canvas_refresh()`
   - `delayed_canvas_refresh()`
   - `final_canvas_refresh()`
3. Add Strangler Fig delegations
4. Test multi-layer filtering refresh

### Session E5-S4: Cleanup & Polish

**Goal:** Remove legacy code, finalize documentation

1. Review all Strangler Fig delegations
2. Remove legacy fallback code where safe
3. Update module documentation
4. Run full test suite
5. Update metrics

## Expected Outcomes

### Before Phase E5

- filter_task.py: **12,894 lines**
- Total methods: ~100+

### After Phase E5

- filter_task.py: **~10,500 lines** (-2,400 lines)
- New modules: 4 files (~1,500 lines)
- Legacy code removed: ~900 lines

## Dependencies

### New Module Structure

```
core/
├── geometry/
│   ├── __init__.py
│   ├── buffer_processor.py    (existing, 509 lines)
│   ├── geometry_converter.py  (existing, 199 lines)
│   ├── geometry_repair.py     (existing, 255 lines)
│   ├── geometry_simplifier.py (NEW, ~150 lines)
│   └── layer_utils.py         (NEW, ~400 lines)
├── filter/
│   ├── __init__.py           (existing)
│   └── expression_processor.py (NEW, ~350 lines)
└── export/
    ├── __init__.py           (existing)
    ├── layer_exporter.py     (existing, 423 lines)
    ├── style_exporter.py     (existing, 328 lines)
    └── archive_utils.py      (NEW, ~100 lines)

adapters/
└── qgis/
    └── canvas_manager.py     (NEW, ~300 lines)
```

## Success Criteria

- [ ] All new modules compile without errors
- [ ] filter_task.py reduced by ~2,400 lines
- [ ] All existing tests pass
- [ ] No performance regression
- [ ] Strangler Fig delegations working
- [ ] Legacy fallbacks tested

## Session Progress

### Session E5-S1: Memory Layer Utilities (Pending)

**Status:** NOT STARTED

---

## Notes

- Phase E5 focuses on utility methods that are provider-agnostic
- Phase E4 extracted backend-specific code; E5 targets shared utilities
- Maintain Strangler Fig pattern for safe migration
- Priority given to methods with clear boundaries and minimal dependencies
