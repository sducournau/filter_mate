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

## Progress Summary (Updated: January 10, 2026 - E4-S2)

**Phase E4 Status**: IN PROGRESS - Partial extraction completed

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

**Total Extracted**: ~373 lines / ~3,500 target (10.6%)

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

1. ✅ Create stub modules (DONE - this commit)
2. ⏳ Session 1: Extract HIGH priority methods
3. ⏳ Session 2: Extract `prepare_spatialite_source_geom()`
4. ⏳ Session 3: Extract OGR methods
5. ⏳ Session 4: Complete extraction and integration

---

**Note**: This phase requires more sessions than E1-E3 due to complexity. Each session should focus on a specific subset to maintain quality and testability.
