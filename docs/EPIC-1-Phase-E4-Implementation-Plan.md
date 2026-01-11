# EPIC-1 Phase E4: Backend Consolidation - Implementation Plan

**Status:** PLANNED (stub modules created)  
**Date:** January 10, 2026  
**Estimated Effort:** 3-4 hours (2-3 sessions)

## Overview

Phase E4 extracts ~3,500 lines of backend-specific code from `filter_task.py` to dedicated backend modules. This is the largest and most complex phase due to:

- Heavy interdependencies between methods
- Database-specific SQL generation
- Connection management and error handling
- Performance-critical code paths

## Modules Created (Stubs)

✅ **PostgreSQL**: `adapters/backends/postgresql/filter_executor.py`  
✅ **Spatialite**: `adapters/backends/spatialite/filter_executor.py`  
✅ **OGR**: `adapters/backends/ogr/filter_executor.py`

## Methods to Extract

### PostgreSQL Methods (~1,500 lines)

| Method                               | Lines  | Priority | Complexity |
| ------------------------------------ | ------ | -------- | ---------- |
| `prepare_postgresql_source_geom()`   | 122    | HIGH     | Medium     |
| `qgis_expression_to_postgis()`       | 68     | HIGH     | Low        |
| `_build_postgis_predicates()`        | 59     | MEDIUM   | Medium     |
| `_build_postgis_filter_expression()` | 34     | MEDIUM   | Low        |
| `_apply_postgresql_type_casting()`   | 40     | MEDIUM   | Low        |
| `_build_spatial_join_query()`        | ~80    | LOW      | Medium     |
| Others                               | ~1,100 | LOW      | Varies     |

### Spatialite Methods (~1,200 lines)

| Method                             | Lines | Priority | Complexity    |
| ---------------------------------- | ----- | -------- | ------------- |
| `prepare_spatialite_source_geom()` | 629   | HIGH     | **VERY HIGH** |
| `qgis_expression_to_spatialite()`  | 58    | HIGH     | Low           |
| `_build_spatialite_query()`        | ~50   | MEDIUM   | Medium        |
| `_apply_spatialite_subset()`       | ~44   | MEDIUM   | Medium        |
| `_manage_spatialite_subset()`      | ~119  | MEDIUM   | High          |
| `_get_spatialite_datasource()`     | ~28   | LOW      | Low           |
| Others                             | ~270  | LOW      | Varies        |

**CRITICAL**: `prepare_spatialite_source_geom()` is the LARGEST method (629 lines, 139 total methods). Handles:

- Temporary table creation/deletion
- R-tree spatial index management
- Buffer expression evaluation
- Centroid calculations
- Complex error handling and cleanup

### OGR Methods (~800 lines)

| Method                               | Lines | Priority | Complexity |
| ------------------------------------ | ----- | -------- | ---------- |
| `prepare_ogr_source_geom()`          | 382   | HIGH     | High       |
| `_execute_ogr_spatial_selection()`   | 159   | HIGH     | Medium     |
| `_build_ogr_filter_from_selection()` | 57    | MEDIUM   | Low        |
| Others                               | ~200  | LOW      | Varies     |

## Implementation Strategy

### Session 1: Core Methods (HIGH priority)

1. Extract `prepare_postgresql_source_geom()` (122 lines)
2. Extract `qgis_expression_to_postgis()` (68 lines)
3. Extract `qgis_expression_to_spatialite()` (58 lines)
4. Add Strangler Fig delegations
5. Test & commit (~250 lines)

### Session 2: Spatialite Giant (VERY HIGH complexity)

1. **FOCUS**: Extract `prepare_spatialite_source_geom()` (629 lines)
2. This method alone requires careful extraction due to:
   - SQLite connection management
   - Temporary table lifecycle
   - R-tree index operations
   - Error handling and cleanup
3. Test & commit (~630 lines)

### Session 3: OGR & Remaining

1. Extract `prepare_ogr_source_geom()` (382 lines)
2. Extract `_execute_ogr_spatial_selection()` (159 lines)
3. Extract remaining MEDIUM priority methods
4. Test & commit (~600+ lines)

### Session 4: Polish & Integrate

1. Extract remaining LOW priority methods
2. Add all missing delegations
3. Update backend factory if needed
4. Integration testing
5. Final commit

## Dependencies & Challenges

### Method Interdependencies

- Expression converters called by prepare\_\* methods
- prepare*\* methods use instance variables (self.param*\*)
- Connection management shared across methods

### Proposed Solutions

1. **Context Objects**: Create `FilterContext` dataclass to pass parameters
2. **Strangler Fig**: Keep legacy methods, delegate to new modules
3. **Connection Factory**: Centralize database connection management
4. **Gradual Migration**: Extract and test incrementally

## Testing Strategy

### Per-Session Testing

- Compile all new modules
- Run existing unit tests
- Manual testing with each provider:
  - PostgreSQL: Test with PostGIS layer
  - Spatialite: Test with GeoPackage
  - OGR: Test with Shapefile

### Integration Testing

- Multi-layer filtering (different providers)
- Buffer + centroid combinations
- Complex spatial predicates
- Error scenarios

## Risks & Mitigation

| Risk                         | Impact | Mitigation                                       |
| ---------------------------- | ------ | ------------------------------------------------ |
| Breaking existing filters    | HIGH   | Strangler Fig pattern, comprehensive testing     |
| Spatialite temp table issues | MEDIUM | Careful transaction management, cleanup on error |
| Performance regression       | MEDIUM | Benchmark before/after, profile critical paths   |
| Missing dependencies         | LOW    | Extract in dependency order, stub if needed      |

## Progress Summary (Updated: January 11, 2026 - E4-S4)

**Phase E4 Status**: IN PROGRESS - All three backends have utility functions extracted

### Completed Extractions

✅ **Session 1 (E4-S1)**: Core expression converters (~250 lines)

- `qgis_expression_to_postgis()` → postgresql/filter_executor.py (68 lines)
- `qgis_expression_to_spatialite()` → spatialite/filter_executor.py (58 lines)
- `prepare_postgresql_source_geom()` → postgresql/filter_executor.py (122 lines)
- Commit: MIG-210

✅ **Session 2 (E4-S2)**: Predicate builders (~123 lines)

- `build_postgis_predicates()` → postgresql/filter_executor.py (59 lines)
- `build_spatialite_query()` → spatialite/filter_executor.py (64 lines)
- Commit: MIG-211

✅ **Session 3 (E4-S3)**: PostgreSQL utility functions (~530 lines)

- `apply_postgresql_type_casting()` → type casting for varchar→numeric (40 lines)
- `build_spatial_join_query()` → INNER JOIN subquery builder (56 lines)
- `apply_combine_operator()` → UNION/INTERSECT/EXCEPT wrapping (20 lines)
- `cleanup_session_materialized_views()` → Session MV cleanup (45 lines)
- `execute_postgresql_commands()` → Auto-reconnection executor (27 lines)
- `ensure_source_table_stats()` → ANALYZE for missing stats (40 lines)
- `normalize_column_names_for_postgresql()` → Case normalization (49 lines)
- `qualify_field_names_in_expression()` → Table prefix qualifier (90 lines)
- `format_pk_values_for_sql()` → PK formatting for IN clause (45 lines)
- `_is_pk_numeric()` → PK type detection (25 lines)
- Commit: fe55ff8

✅ **Session 4 (E4-S4)**: Spatialite + OGR utility functions (~564 lines)

**Spatialite (8 functions, 510 lines total):**

- `apply_spatialite_subset()` → Apply subset with history update (70 lines)
- `manage_spatialite_subset()` → Handle temp tables for filtering (80 lines)
- `get_last_subset_info()` → Get last subset from history table (35 lines)
- `cleanup_session_temp_tables()` → Clean session temp tables (50 lines)
- `normalize_column_names_for_spatialite()` → Column quoting (25 lines)

**OGR (6 functions, 286 lines total):**

- `build_ogr_filter_from_selection()` → Build filter from selection (80 lines)
- `format_ogr_pk_values()` → Format PK values for IN clause (25 lines)
- `normalize_column_names_for_ogr()` → Column case normalization (40 lines)
- `build_ogr_simple_filter()` → Simple PK IN filter builder (20 lines)
- `apply_ogr_subset()` → Thread-safe subset application (25 lines)
- `combine_ogr_filters()` → Combine filters with AND/OR/NOT (25 lines)
- Commit: 17ba303

**Total Extracted**: ~1,467 lines / ~3,500 target (41.9%)

### Backend Summary

| Backend    | Functions | Lines     | Status            |
| ---------- | --------- | --------- | ----------------- |
| PostgreSQL | 14        | 883       | ✅ Core complete  |
| Spatialite | 8         | 510       | ✅ Core complete  |
| OGR        | 6         | 286       | ✅ Core complete  |
| **TOTAL**  | **28**    | **1,679** | **48% of target** |

### PostgreSQL filter_executor.py Status

**Functions implemented: 14**
| Function | Lines | Status |
|----------|-------|--------|
| `prepare_postgresql_source_geom()` | 122 | ✅ Complete |
| `qgis_expression_to_postgis()` | 68 | ✅ Complete |
| `build_postgis_predicates()` | 59 | ✅ Complete |
| `apply_postgresql_type_casting()` | 40 | ✅ Complete |
| `build_spatial_join_query()` | 56 | ✅ Complete |
| `apply_combine_operator()` | 20 | ✅ Complete |
| `cleanup_session_materialized_views()` | 45 | ✅ Complete |
| `execute_postgresql_commands()` | 27 | ✅ Complete |
| `ensure_source_table_stats()` | 40 | ✅ Complete |
| `normalize_column_names_for_postgresql()` | 49 | ✅ Complete |
| `qualify_field_names_in_expression()` | 90 | ✅ Complete |
| `format_pk_values_for_sql()` | 45 | ✅ Complete |
| `_is_pk_numeric()` | 25 | ✅ Complete |
| `add_numeric_cast()` | helper | ✅ Complete |

### Deferred for Refactoring

The following methods require significant refactoring before extraction:

#### ⚠️ prepare_spatialite_source_geom() (629 lines)

**Reason**: Extreme complexity - thread-safety, caching, dissolve optimization
**Dependencies**:

- `_get_optimization_thresholds()` (33 lines)
- `_geometry_to_wkt()` (73 lines)
- `_simplify_geometry_adaptive()` (122 lines)
- `safe_unary_union()`, `safe_collect_geometry()` (geometry utilities)
- Advanced WKT simplification logic
- GeometryCache integration
  **Recommendation**: Refactor into smaller, testable components first

#### ⚠️ prepare_ogr_source_geom() (382 lines)

**Reason**: Many helper method dependencies
**Dependencies**:

- `_copy_filtered_layer_to_memory()`
- `_create_memory_layer_from_features()`
- `_reproject_layer()`
- `_convert_layer_to_centroids()`
- `_repair_invalid_geometries()`
  **Recommendation**: Extract helper methods to shared utilities first

#### ⚠️ \_execute_ogr_spatial_selection() (159 lines)

**Dependencies**: QGIS processing algorithms, selection handling
**Recommendation**: Extract after prepare_ogr_source_geom()

## Success Criteria

- [ ] All backend modules compile without errors
- [ ] All existing tests pass
- [ ] Manual testing successful for all 3 backends
- [ ] filter_task.py reduced by ~3,500 lines
- [ ] No performance regression
- [ ] Code coverage maintained or improved

## Timeline

- **Session 1-2**: Core methods + Spatialite giant (4-6 hours)
- **Session 3**: OGR extraction (2-3 hours)
- **Session 4**: Polish & integration (2-3 hours)
- **Total**: 8-12 hours over 4 sessions

## Next Steps

1. ✅ Create stub modules (DONE - MIG-209)
2. ✅ Session 1: Extract HIGH priority methods (DONE - MIG-210)
3. ✅ Session 2: Extract predicate builders (DONE - MIG-211)
4. ✅ Session 3: Extract PostgreSQL utility functions (DONE - fe55ff8)
5. ✅ Session 4: Extract Spatialite + OGR utility functions (DONE - 17ba303)
6. ⏳ Session 5: Extract `prepare_spatialite_source_geom()` (629 lines) - DEFERRED
7. ⏳ Session 6: Extract `prepare_ogr_source_geom()` (382 lines) - DEFERRED
8. ⏳ Session 7: Add Strangler Fig delegations to filter_task.py

### Deferred Methods (Need Significant Refactoring)

The following methods are deferred because they have heavy dependencies on instance
variables (`self.*`) and QGIS processing context:

| Method                             | Lines | Dependencies                                    | Recommendation                   |
| ---------------------------------- | ----- | ----------------------------------------------- | -------------------------------- |
| `prepare_spatialite_source_geom()` | 629   | GeometryCache, safe_unary_union, thread context | Refactor into smaller components |
| `prepare_ogr_source_geom()`        | 382   | Memory layers, reproject, QGIS processing       | Extract helpers first            |
| `execute_ogr_spatial_selection()`  | 159   | Processing context, selection handling          | Extract after prepare_ogr        |

---

**Note**: This phase requires more sessions than E1-E3 due to complexity. Each session should focus on a specific subset to maintain quality and testability.
