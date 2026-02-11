# C1: FilterEngineTask Decomposition - Phase 3 (2026-02-11)

## Branch
`refactor/quick-wins-2026-02-10`

## Pass 1: Initial Extraction (3 handlers)
Extracted 3 handler classes from `FilterEngineTask` (core/tasks/filter_task.py):

### 1. CleanupHandler (core/tasks/cleanup_handler.py) -- 421 lines
Extracted PostgreSQL MV cleanup and schema management:
- `cleanup_postgresql_materialized_views()` (89 lines saved)
- `cleanup_session_materialized_views()` (14 lines saved)
- `cleanup_orphaned_materialized_views()` (7 lines saved)
- `ensure_temp_schema_exists()` (20 lines saved)
- `get_session_prefixed_name()` (7 lines saved)
- `execute_postgresql_commands()` (22 lines saved)
- `ensure_source_table_stats()` (16 lines saved)
- `create_simple_materialized_view_sql()` (3 lines saved)
- `parse_where_clauses()` (3 lines saved)
- `create_custom_buffer_view_sql()` (90 lines saved)

### 2. ExportHandler (core/tasks/export_handler.py) -- 513 lines
Extracted all export operations:
- `execute_exporting()` (223 lines saved)
- `_export_with_streaming()` (123 lines saved)
- `validate_export_parameters()` (34 lines saved)
- `calculate_total_features()` (17 lines saved)
- `get_layer_by_name()` (7 lines saved)
- `save_layer_style()` / `save_layer_style_lyrx()` (11 lines saved)
- Private helper: `_export_gpkg()`, `_export_with_streaming()`

### 3. GeometryHandler (core/tasks/geometry_handler.py) -- 712 lines
Extracted geometry preparation, buffer ops, and memory layer management:
- `simplify_geometry_adaptive()` (36 lines saved)
- `apply_buffer_with_fallback()` (49 lines saved)
- `simplify_buffer_result()` (12 lines saved)
- `copy_filtered_layer_to_memory()` (10 lines saved)
- `copy_selected_features_to_memory()` (10 lines saved)
- `create_memory_layer_from_features()` (12 lines saved)
- `convert_layer_to_centroids()` (11 lines saved)
- `reproject_layer()` (21 lines saved)
- Plus 15+ utility methods (WKT, buffer, repair, spatial index)

### Pass 1 Metrics
- **Before**: filter_task.py = 5890 lines
- **After**: filter_task.py = 5162 lines (-728 lines, -12.4%)
- **New files**: 3 handler files totaling 1646 lines
- **Tests**: 235/235 passing (zero regressions)

## Pass 2: Continued Extraction (3 more handlers)

### 4. InitializationHandler (core/tasks/initialization_handler.py) -- 431 lines
Extracted all task initialization/parameter setup:
- `initialize_source_layer()` (63 lines saved)
- `configure_metric_crs()` (57 lines saved)
- `initialize_source_filtering_parameters()` (56 lines saved)
- `initialize_source_subset_and_buffer()` (38 lines saved)
- `initialize_current_predicates()` (106 lines saved)

### 5. SourceGeometryPreparer (core/tasks/source_geometry_preparer.py) -- 368 lines
Extracted all source geometry preparation for 3 backends:
- `prepare_postgresql_source_geom()` (50 lines saved)
- `prepare_spatialite_source_geom()` (53 lines saved)
- `prepare_ogr_source_geom()` (28 lines saved)
- `prepare_geometries_by_provider()` (40 lines saved)

### 6. SubsetManagementHandler (core/tasks/subset_management_handler.py) -- 943 lines
Extracted subset string management orchestrator:
- `manage_layer_subset_strings()` main orchestrator (55 lines saved)
- `filter_action_postgresql()`, `reset_action_postgresql()`, `reset_action_spatialite()`, `reset_action_ogr()`
- `unfilter_action()`, `_unfilter_action_ogr()`, `_unfilter_action_spatialite()`
- `determine_backend()`, `get_last_subset_info()`, `insert_subset_history()`
- `get_spatialite_datasource()`, `build_spatialite_query()`, etc.
- NOTE: Original sub-methods STILL in filter_task.py as callbacks for pg_execute_filter

### Pass 2 Metrics
- **Before Pass 2**: filter_task.py = 5162 lines
- **After Pass 2**: filter_task.py = 4800 lines (-362 lines, -7.0%)
- **Tests**: 235/235 passing (zero regressions)
- **py_compile**: All files compile cleanly

## Cumulative Metrics
- **Original**: filter_task.py = 5890 lines
- **Current**: filter_task.py = 4800 lines (-1090 lines, -18.5%)
- **Total handler files**: 6 files totaling 3388 lines
- **Architecture preserved**: No public API changes, all callers see identical signatures

## Architecture
- Handlers are instantiated in `FilterEngineTask.__init__()`:
  - `self._cleanup_handler = CleanupHandler()`
  - `self._export_handler = ExportHandler()`
  - `self._geometry_handler = GeometryHandler()`
  - `self._init_handler = InitializationHandler()`
  - `self._source_geom_preparer = SourceGeometryPreparer()`
  - `self._subset_handler = SubsetManagementHandler()`
- Original methods become thin delegation wrappers (1-5 lines each)
- No public API changes -- all callers see identical signatures
- Thread safety preserved -- handlers receive data via parameters
- `__init__.py` updated to export all 6 handler classes

## Remaining in FilterEngineTask (~4800 lines)
Still contains (not yet extracted):
- `execute_filtering()` (~250 lines) -- core orchestration logic
- `execute_unfiltering()` (~50 lines) -- simple but depends on self state
- `execute_reseting()` (~40 lines) -- simple but depends on self state
- `finished()` (~216 lines) -- runs in main thread, needs iface access
- `run()` (~160 lines) -- main entry point
- `execute_source_layer_filtering()` (~40 lines)
- `_filter_all_layers_*` (~250 lines) -- parallel/sequential orchestration
- All callback wrappers passed to handlers (~350 lines total)
- E13 lazy initialization methods (~200 lines)
- Expression/filtering helper methods (~250 lines)
- Various MV creation/chain methods (~500 lines)
- Backend expression building (~200 lines)
- Geometric filtering execution (~200 lines)

## Next Steps
To continue reduction toward <2500 lines:
1. **FilteringOrchestrator** (~400 lines): execute_filtering, _filter_all_layers_*
2. **FinishedHandler** (~216 lines): finished() method
3. **Dead callback cleanup**: Remove callback wrappers that are now redundant
   (careful: many are still used by pg_execute_filter and other adapters)
