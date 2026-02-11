# C1: filter_task.py God Class Decomposition (Pass 3)

## Date: 2026-02-11
## Status: COMPLETE - Target achieved (2929 lines < 3000)

## Results Summary
- **Starting size**: 3970 lines
- **Final size**: 2929 lines
- **Total reduction**: -1041 lines (-26.2%)
- **4 new handlers**: 1734 lines total

## Commits (chronological)

### 1. MaterializedViewHandler (commit 10b9661d)
- File: `core/tasks/materialized_view_handler.py` (565 lines)
- Methods: create_source_mv_if_needed, ensure_buffer_expression_mv_exists, try_create_filter_chain_mv
- Also centralized thin delegations to CleanupHandler (10 methods)
- Reduction: 3970 -> 3559 (-411 lines, -10.4%)

### 2. ExpressionFacadeHandler (commit 7b50e77d)
- File: `core/tasks/expression_facade_handler.py` (initial 401 lines)
- Methods: sanitize_subset_string, extract_spatial_clauses_for_exists, apply_postgresql_type_casting, process_qgis_expression, combine_with_old_subset, build_feature_id_expression, is_pk_numeric, format_pk_values_for_sql, optimize_duplicate_in_clauses, qualify_field_names_in_expression, build_combined_filter_expression, apply_filter_and_update_subset
- Reduction: 3559 -> 3362 (-197 lines, -5.5%)

### 3. SpatialQueryHandler (commit 5ec1c7b4)
- File: `core/tasks/spatial_query_handler.py` (258 lines)
- Methods: get_source_reference, build_spatial_join_query, apply_combine_operator, build_postgis_filter_expression, execute_ogr_spatial_selection, build_ogr_filter_from_selection
- Reduction: 3362 -> 3286 (-76 lines, -2.3%)

### 4. ExpressionFacadeHandler enrichment + V3BridgeHandler (commit 65f25539)
- ExpressionFacadeHandler enriched to 587 lines (+8 methods): qgis_expression_to_postgis, qgis_expression_to_spatialite, normalize_sql_operator, get_source_combine_operator, get_combine_operator, combine_with_old_filter, has_expensive_spatial_expression, is_complex_filter
- New file: `core/tasks/v3_bridge_handler.py` (324 lines)
- V3BridgeHandler methods: try_v3_attribute_filter, try_v3_spatial_filter, try_v3_multi_step_filter, try_v3_export
- Reduction: 3286 -> 2929 (-357 lines, -10.8%)

## Pattern Used
- Handler class takes `task` (FilterEngineTask) reference in `__init__`
- Accesses task state via `self.task.xxx`
- filter_task.py keeps thin delegation stubs for backward compatibility
- Each handler is autonomous and testable in isolation
- Public interface of FilterEngineTask is preserved

## Handler File Summary
| Handler | Lines | Methods |
|---------|-------|---------|
| materialized_view_handler.py | 565 | 13 |
| expression_facade_handler.py | 587 | 21 |
| v3_bridge_handler.py | 324 | 4 |
| spatial_query_handler.py | 258 | 6 |
| **Total** | **1734** | **44** |

## All Handlers in core/tasks/ (including pre-existing)
1. cleanup_handler.py - MV cleanup and schema management
2. export_handler.py - Export operations
3. geometry_handler.py - Geometry operations
4. initialization_handler.py - Task initialization
5. source_geometry_preparer.py - Source geometry preparation
6. subset_management_handler.py - Subset string management
7. filtering_orchestrator.py - Filtering orchestration
8. finished_handler.py - Task completion handling
9. materialized_view_handler.py - MV lifecycle (NEW Pass 3)
10. expression_facade_handler.py - Expression building (NEW Pass 3)
11. spatial_query_handler.py - Spatial queries (NEW Pass 3)
12. v3_bridge_handler.py - V3 TaskBridge delegation (NEW Pass 3)
