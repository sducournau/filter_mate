# EPIC-1 Option E: filter_task.py Decomposition Plan

**Date:** January 10, 2026  
**Status:** PLANNED (not started)  
**File:** `modules/tasks/filter_task.py`  
**Size:** 12,694 lines, 139 methods  
**Estimated Time:** 10-12 hours (5-6 sessions)

## Current EPIC-1 Progress

| Metric             | Value                                  |
| ------------------ | -------------------------------------- |
| **Progress**       | 54%                                    |
| **Lines Migrated** | 14,880 / 27,518                        |
| **Remaining**      | filter_task.py (12,694) + shims (~450) |

## filter_task.py Analysis

### Responsibilities Identified (6 domains)

| Domain                    | Methods | Est. Lines | Target Location                 |
| ------------------------- | ------- | ---------- | ------------------------------- |
| **1. PostgreSQL Backend** | 16      | ~1,500     | `adapters/backends/postgresql/` |
| **2. Spatialite Backend** | 10      | ~1,200     | `adapters/backends/spatialite/` |
| **3. OGR Backend**        | 11      | ~800       | `adapters/backends/ogr/`        |
| **4. Geometry/Buffer**    | 36      | ~3,500     | `core/geometry/`                |
| **5. Export**             | 12      | ~1,000     | `core/export/`                  |
| **6. Filter/Expression**  | 61      | ~4,500     | `core/filter/`                  |

### Largest Methods (>100 lines)

| Method                                      | Lines | Domain     |
| ------------------------------------------- | ----- | ---------- |
| `prepare_spatialite_source_geom()`          | 629   | Spatialite |
| `_build_backend_expression()`               | 544   | Filter     |
| `prepare_ogr_source_geom()`                 | 382   | OGR        |
| `_prepare_geometries_by_provider()`         | 286   | Geometry   |
| `_simplify_geometry_adaptive()`             | 254   | Geometry   |
| `_combine_with_old_subset()`                | 252   | Expression |
| `_organize_layers_to_filter()`              | 190   | Filter     |
| `_initialize_source_filtering_parameters()` | 185   | Filter     |
| `execute_source_layer_filtering()`          | 177   | Filter     |
| `_initialize_source_subset_and_buffer()`    | 163   | Geometry   |

## Decomposition Strategy (Strangler Fig Pattern)

### Phase E1: Geometry/Buffer Extraction (~3,500 lines)

**Target:** `core/geometry/`

```
core/geometry/
├── __init__.py
├── buffer_processor.py      # _apply_buffer*, _create_buffered*, _buffer_all_features
├── geometry_repair.py       # _repair*, _aggressive_geometry_repair, _fix_invalid*
├── geometry_simplifier.py   # _simplify_geometry_adaptive, _simplify_buffer_result
├── centroid_converter.py    # _convert_layer_to_centroids
├── memory_layer_factory.py  # _copy_*_to_memory, _create_memory_layer*
└── geometry_collection.py   # _convert_geometry_collection_to_multipolygon
```

**Methods to extract:**

- `_apply_qgis_buffer()` (97 lines)
- `_create_buffered_memory_layer()` (70 lines)
- `_buffer_all_features()` (71 lines)
- `_dissolve_and_add_to_layer()` (86 lines)
- `_aggressive_geometry_repair()` (71 lines)
- `_repair_invalid_geometries()` (84 lines)
- `_simplify_buffer_result()` (146 lines)
- `_simplify_geometry_adaptive()` (254 lines)
- `_convert_layer_to_centroids()` (65 lines)
- `_copy_filtered_layer_to_memory()` (95 lines)
- `_copy_selected_features_to_memory()` (103 lines)
- `_create_memory_layer_from_features()` (93 lines)
- `_convert_geometry_collection_to_multipolygon()` (126 lines)
- And ~23 more geometry-related methods

**Time estimate:** 2-3 hours  
**Risk:** Medium (geometry operations are well-isolated)

### Phase E2: Export Extraction (~1,000 lines)

**Target:** `core/export/`

```
core/export/
├── __init__.py
├── layer_exporter.py        # _export_single_layer, _export_to_gpkg, _export_multiple*
├── style_exporter.py        # _save_layer_style*, _convert_symbol_to_arcgis
└── export_validator.py      # _validate_export_parameters
```

**Methods to extract:**

- `_validate_export_parameters()` (83 lines)
- `_get_layer_by_name()` (17 lines)
- `_save_layer_style()` (28 lines)
- `_save_layer_style_lyrx()` (103 lines)
- `_convert_symbol_to_arcgis()` (67 lines)
- `_export_single_layer()` (88 lines)
- `_export_to_gpkg()` (50 lines)
- `_export_multiple_layers_to_directory()` (~100 lines)
- And related export methods

**Time estimate:** 1 hour  
**Risk:** Low (export is isolated, easy to test)

### Phase E3: Expression Builder Extraction (~2,000 lines)

**Target:** `core/filter/`

```
core/filter/
├── __init__.py
├── expression_builder.py    # _build_*_expression, _combine_*
├── expression_sanitizer.py  # _sanitize_subset_string, _optimize_*
├── pk_formatter.py          # _format_pk_values*, _is_pk_numeric, _build_feature_id*
└── expression_combiner.py   # _combine_with_old_subset, _apply_combine_operator
```

**Methods to extract:**

- `_sanitize_subset_string()` (160 lines)
- `_combine_with_old_subset()` (252 lines)
- `_build_feature_id_expression()` (94 lines)
- `_is_pk_numeric()` (30 lines)
- `_format_pk_values_for_sql()` (37 lines)
- `_optimize_duplicate_in_clauses()` (100 lines)
- `_build_combined_filter_expression()` (77 lines)
- `_apply_combine_operator()` (21 lines)
- And ~10 more expression methods

**Time estimate:** 2 hours  
**Risk:** Medium (expression logic is complex)

### Phase E4: Backend Consolidation (~3,500 lines)

**Target:** `adapters/backends/*/filter_executor.py`

```
adapters/backends/
├── postgresql/
│   ├── filter_executor.py   # prepare_postgresql_source_geom, _build_postgis*, qgis_expression_to_postgis
│   └── (existing files)
├── spatialite/
│   ├── filter_executor.py   # prepare_spatialite_source_geom, _build_spatialite*, qgis_expression_to_spatialite
│   └── (existing files)
├── ogr/
│   ├── filter_executor.py   # prepare_ogr_source_geom, _execute_ogr_spatial_selection
│   └── (existing files)
└── factory.py (update)
```

**PostgreSQL methods:**

- `prepare_postgresql_source_geom()` (119 lines)
- `qgis_expression_to_postgis()` (68 lines)
- `_build_postgis_predicates()` (59 lines)
- `_build_postgis_filter_expression()` (34 lines)
- `_apply_postgresql_type_casting()` (40 lines)
- And ~11 more PostgreSQL methods

**Spatialite methods:**

- `prepare_spatialite_source_geom()` (629 lines) ← LARGEST METHOD
- `qgis_expression_to_spatialite()` (58 lines)
- And ~8 more Spatialite methods

**OGR methods:**

- `prepare_ogr_source_geom()` (382 lines)
- `_execute_ogr_spatial_selection()` (159 lines)
- `_build_ogr_filter_from_selection()` (57 lines)
- And ~8 more OGR methods

**Time estimate:** 3-4 hours  
**Risk:** High (backend logic is critical path)

### Phase E5: FilterEngineTask Slim (~2,500 lines remaining)

**Target:** Keep in `modules/tasks/filter_task.py` (orchestration only)

**Remaining responsibilities:**

- `__init__()` - Task initialization
- `run()` - Main entry point
- `execute_filtering()` - Orchestration
- `execute_unfiltering()` - Reset filters
- `execute_reseting()` - Full reset
- Signal emissions and progress callbacks
- Layer organization and validation
- Delegation to extracted modules

**Approach:**

1. Replace method implementations with calls to extracted modules
2. Keep QgsTask inheritance and signals
3. Maintain backward compatibility for external callers

**Time estimate:** 2 hours  
**Risk:** High (integration testing required)

## Recommended Execution Order

1. **E2 (Export)** - Lowest risk, quick win, validates approach
2. **E1 (Geometry)** - Large but well-isolated
3. **E3 (Expression)** - Medium complexity
4. **E4 (Backends)** - High risk, requires careful testing
5. **E5 (Slim)** - Final integration

## Dependencies

### External Dependencies (keep as-is)

- `modules.appUtils` - Utility functions
- `modules.object_safety` - Thread safety
- `modules.type_utils` - Type conversion
- `config.config` - Configuration

### Internal Dependencies (already migrated)

- `infrastructure.cache` - QueryExpressionCache, SourceGeometryCache
- `infrastructure.streaming` - StreamingExporter
- `infrastructure.parallel` - ParallelFilterExecutor
- `core.optimization` - CombinedQueryOptimizer
- `core.strategies` - Progressive/MultiStep filters
- `core.tasks` - ExpressionEvaluationTask, LayersManagementEngineTask

## Testing Strategy

For each phase:

1. Extract methods to new module
2. Create shim methods in filter_task.py that delegate
3. Run existing tests to validate behavior
4. Add unit tests for extracted module
5. Commit with detailed message

## Success Criteria

- [ ] filter_task.py reduced to <3,000 lines (orchestration only)
- [ ] All extracted modules have unit tests
- [ ] No regression in existing functionality
- [ ] EPIC-1 progress reaches 100%
- [ ] Clean architecture boundaries established

## Notes

- Use Strangler Fig pattern: extract gradually, keep shims
- Each phase should be a separate commit
- Test after each extraction
- Consider feature flags for gradual rollout
