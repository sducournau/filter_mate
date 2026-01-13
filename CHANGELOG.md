# FilterMate - Changelog

All notable changes to FilterMate will be documented in this file.

## [Unreleased]

### Added (v4.0.4 - UX Enhancement)
- **CONDITIONAL WIDGET STATES**: Automatic enable/disable of widgets based on pushbutton toggles (2026-01-13)
  - Widgets in FILTERING and EXPORTING sections now automatically enable/disable when their associated pushbutton is toggled
  - 12 pushbutton→widget mappings implemented (6 FILTERING + 6 EXPORTING)
  - Provides clear visual feedback about active/inactive options
  - Improves user guidance and prevents configuration errors
  - Files: `filter_mate_dockwidget.py` (+ `_setup_conditional_widget_states()`, `_toggle_associated_widgets()`)
  - Documentation: [docs/UX-ENHANCEMENT-CONDITIONAL-WIDGET-STATES.md](docs/UX-ENHANCEMENT-CONDITIONAL-WIDGET-STATES.md)

### Fixed (v4.0.5 - Splitter Layout)
- **SPLITTER TRUNCATION**: Fixed panel truncation when dragging splitter handle (2026-01-13)
  - Splitter now properly enforces minimum heights on both frames
  - `frame_exploring` min: 120px → 140px, `frame_toolset` min: 200px → 250px
  - `SplitterManager._apply_frame_policies()` now applies minimum heights from config
  - `_apply_splitter_frame_policies()` in dockwidget also applies min heights
  - Initial splitter ratio: 50/50 → 35/65 (more space for toolset by default)
  - Dockwidget min height: 400px → 500px to accommodate both frames
  - Impact: Exploring groupboxes and toolset tabs no longer get hidden/truncated

## [4.0.3] - 2026-01-13

### Fixed
- **ICONS**: Fixed missing button icons by migrating to IconManager system
  - ConfigurationManager now uses `IconManager.set_button_icon()` instead of deprecated `get_themed_icon()`
  - Icons now properly store `icon_name` property for theme refresh support
  - Impact: All pushbutton icons now display correctly with theme support

### Improved
- **COMPACT Mode**: Adjusted button dimensions for better visibility and usability
  - Button height: 48px → 42px (more compact but still readable)
  - Action button: 32px → 34px, icon 20px → 22px
  - Tool button: icon 22px → 24px (better icon visibility)
  - Key button: spacing 2px → 3px
- **COMPACT Mode**: Improved layout spacing for better visual comfort
  - Main/section/content spacing: 6px → 8px
  - Margins frame: 8px → 10px (left/top/right), 10px → 12px (bottom)
  - GroupBox padding: 6px → 8px, title 4px → 6px
  - Impact: More breathing room without losing screen space

### Technical Details
- Files changed:
  - `ui/managers/configuration_manager.py` - IconManager integration
  - `ui/config/__init__.py` - COMPACT profile dimensions & spacing

## [4.0.2] - 2026-01-13

### Fixed
- **CLEAN #1 (P1)**: Eliminated duplicate fieldChanged signal connections
  - Removed obsolete references to `setup_expression_widget_direct_connections()`
  - Cleaned up comments in ConfigurationManager
  - All fieldChanged signals now handled ONLY by ExploringController via SignalManager
  - Impact: Prevents triple-connection risk and potential performance issues
  - Files: `ui/managers/configuration_manager.py`, `ui/controllers/exploring_controller.py`

## [4.0.1] - 2026-01-13

### Fixed
- **FIX #3 (P0 - CRITICAL)**: Restored COMPACT as default UI profile
  - Impact: Fixes spacing regressions in GroupBox exploring for laptops and Full HD displays
  - Affected users: ~70% (laptops 13-17", desktop 24" Full HD)
  - Surface gain: +12% usable vertical space (+78px on 1366x768 screens)
  - See: `_bmad-output/UX-ANALYSIS-SPACING-GROUPBOX-20260113.md`

### Changed
- Adjusted UI profile resolution breakpoint: 1920x1080 → 2560x1440
  - COMPACT: Now used for all screens < 2560x1440 (laptops, Full HD desktops)
  - NORMAL: Reserved for large screens ≥ 2560x1440 (27"+ 2K/4K monitors)
  - Fallback: COMPACT instead of NORMAL (fail-safe for small screens)

### Technical Details
- Files changed:
  - `ui/config/__init__.py:34` - Restored COMPACT default
  - `core/services/app_initializer.py:320,327,331` - Adjusted breakpoint and fallbacks

## [4.0.0-alpha] - 2026-01-12 (God Classes Elimination Complete!)

### 🎉 Major Milestone: All God Classes Objectives Achieved!

**God Classes Reduction (Measured 12 jan 2026):**

| File | Peak | Target | **Actual** | Reduction |
|------|------|--------|------------|-----------|
| filter_task.py | 12,894 | <10,000 | **6,023** | -53.3% ✅ |
| filter_mate_app.py | 5,900 | <2,500 | **1,667** | -71.7% ✅ |
| filter_mate_dockwidget.py | 12,000 | <2,500 | **2,494** | -79.2% ✅ |
| **TOTAL** | 30,794 | <15,000 | **10,184** | **-66.9%** ✅ |

### 🏗️ Architecture v4.0 Established

**Hexagonal Services Layer (10,528 lines):**
- 20 services in `core/services/`
- Clean separation: business logic isolated from UI
- Key services: LayerLifecycleService, TaskManagementService, ExpressionService, etc.

**MVC Controllers Layer (13,143 lines):**
- 12 controllers in `ui/controllers/`
- Complete UI orchestration delegation
- Integration with hexagonal services via DI

**Multi-Backend Architecture:**
- PostgreSQL, Spatialite, OGR backends stable
- Factory pattern for backend selection
- Consistent API across all backends

### 📊 Metrics Summary

- **Test Coverage**: ~75% (400+ tests)
- **Backward Compatibility**: 100% maintained
- **Code Quality**: 9.0/10 score
- **Total Core Code**: ~36,888 lines (well-structured)

### 📚 Documentation Consolidated

- Updated BMAD_DOCUMENTATION_INDEX.md
- Created REFACTORING-STATUS-20260112.md
- Updated migration-v4-roadmap.md with real metrics
- Archived obsolete documents to `_bmad-output/_archive/`

---

## [3.1.0] - 2026-01-09 (Phase 5: Validation & Dépréciation)

### 🏗️ Architecture Migration v3.0 Complete

**MIG-040: Complete E2E Test Suite:**

- Added comprehensive E2E tests in `tests/integration/workflows/test_e2e_complete_workflow.py`
- 6 new test classes covering all major workflows:
  - `TestCompleteFilteringWorkflow`: Full filter lifecycle
  - `TestBackendSwitchingWorkflow`: Backend selection and fallback
  - `TestExportWorkflow`: Export operations
  - `TestFavoritesWorkflow`: Favorites management
  - `TestMultiStepFilterWorkflow`: Progressive filtering
  - `TestEdgeCasesWorkflow`: Edge cases and Unicode handling
- Tests validate history/undo/redo, buffer distance, error recovery

**MIG-041: Performance Benchmarks:**

- Added `tests/performance/test_v3_performance_comparison.py`
- Complete v2.x baseline comparison for all backends
- Performance scenarios:
  - PostgreSQL: 1k-100k features, attribute + spatial filters
  - Spatialite: 1k-100k features
  - OGR: 1k-100k features
- `PerformanceReport` class generates markdown reports
- Regression detection with 5% threshold

**MIG-042: Migration Documentation Updated:**

- Enhanced `docs/migration-v3.md` with:
  - Complete migration checklist
  - Import path mapping table
  - Deprecation notices with v4.0 removal timeline
  - Troubleshooting guide

**MIG-043: Legacy Code Deprecation:**

- `modules/__init__.py` now emits `DeprecationWarning` on import
- Deprecation tracking with `get_deprecated_usage_report()`
- Migration paths documented:
  - `modules.appUtils` → `infrastructure.utils` / `adapters.database_manager`
  - `modules.appTasks` → `adapters.qgis.tasks`
  - `modules.backends` → `adapters.backends`
- Added `tests/test_deprecation_warnings.py` for deprecation tests

### 📊 Test Coverage Improvements

- New tests added: ~150 test cases
- E2E workflow coverage: 100%
- Performance benchmark coverage: 100%
- Deprecation warning coverage: 100%

### ⚠️ Deprecation Notices

The following will be removed in FilterMate v4.0:

| Deprecated Module  | Replacement            | Status        |
| ------------------ | ---------------------- | ------------- |
| `modules.appUtils` | `infrastructure.utils` | ⚠️ Deprecated |
| `modules.appTasks` | `adapters.qgis.tasks`  | ⚠️ Deprecated |
| `modules.backends` | `adapters.backends`    | ⚠️ Deprecated |
| `modules.config_*` | `config.config`        | ⚠️ Deprecated |

---

## [3.0.20] - 2026-01-08

### 🐛 Bug Fixes from Backlog

**HIGH-002: Fixed bare except clauses (v3.0.20):**

- **widgets.py**: Replaced 2 bare `except:` clauses with `except Exception:` in `finished()` method
- **parallel_executor.py**: Replaced 1 bare `except:` clause with `except Exception:` in `execute_filter_parallel()`
- **Impact**: Better exception handling, clearer code intent, and no silent swallowing of system exceptions

**CRIT-002: Fixed SQL Injection Risk (v3.0.20):**

- **progressive_filter.py**: Changed f-string SQL query to parameterized query in `_parse_bbox_from_wkt()`
- **Before**: `cursor.execute(f"SELECT ST_Extent(ST_GeomFromText('{wkt}'))")`
- **After**: `cursor.execute("SELECT ST_Extent(ST_GeomFromText(%s))", (wkt,))`
- **Impact**: Prevents potential SQL injection via malformed WKT input

**HIGH-006: Added large OGR dataset warning (v3.0.20):**

- **ogr_backend.py**: Added user warning for datasets ≥50k features
- **Message**: "Grand jeu de données (X entités) avec OGR. Considérez PostgreSQL ou Spatialite pour de meilleures performances."
- **Impact**: Users are now informed when OGR performance may be suboptimal vs other backends

### 🔧 Code Style Improvements

**MED-001: Converted .format() to f-strings (partial):**

- **customExceptions.py**: Converted exception message formatting to f-string
- **widgets.py**: Converted task cancellation log message to f-string
- **Note**: Remaining .format() calls are in i18n `tr()` contexts (required for translation)

### ✅ Backlog Verification (v3.0.20)

**Verified as already implemented:**

- **HIGH-004**: Buffer code duplication - Fixed in v3.0.12 via `_build_buffer_expression()` in base_backend.py
- **HIGH-005**: CRS transformation duplication - Centralized in `crs_utils.py` (CRSTransformer class)
- **HIGH-009**: Exception handlers vides - Verified OK (graceful degradations with appropriate comments)
- **HIGH-013**: Magic numbers - Already centralized in `constants.py` (PERFORMANCE*THRESHOLD*\*)
- **HIGH-014**: Geometry validation - Centralized in `geometry_safety.py`
- **HIGH-016**: Cache unifié - 6 specialized caches (Query, Geometry, WKT, Spatialite, Exploring, PreparedStatement)
- **HIGH-017**: Error messages - Custom exceptions in `customExceptions.py`
- **MED-005**: TODO/FIXME - Only 1 remaining (ogr_backend.py:701 - legitimate future feature)
- **MED-010**: .gitignore - Properly configured for **pycache**
- **MED-016**: Factory pattern - Complete with auto-selection, forced backends, fallbacks
- **MED-018**: Logging incohérent - All backends use `get_tasks_logger()` consistently
- **MED-020**: Health checks - Implemented in `connection_pool.py` with periodic thread
- **MED-023**: Cache invalidation - TTL + `invalidate_layer()` in QueryExpressionCache
- **MED-024**: Connection pooling - Full implementation in `connection_pool.py`
- **MED-025**: Lazy loading - `LazyResultIterator` in progressive_filter.py
- **MED-026**: Spatial indexes - `spatial_index_manager.py` (QIX, SBN, R-tree)
- **LOW-002**: Print statements debug - Only in docstrings/bootstrap code (legitimate)
- **LOW-005**: Empty `__init__.py` files - All contain proper exports

---

## [3.0.19] - 2026-01-08

### 🐛 Critical Bug Fixes

**CRIT-006: Comprehensive feature_count None Protection (v3.0.19) - COMPLETE FIX:**

- **Fixed persistent issue**: 2nd/3rd filter on PostgreSQL distant layers still crashed with TypeError
- **Issue**: Additional `layer.featureCount()` calls without None protection in multiple files
- **Root Cause**: Several backend files called `featureCount()` and compared without None check
- **Additional Fixes Applied**:
  1. **multi_step_optimizer.py**: `_compute_layer_stats()` now protects `featureCount()` before storing in `LayerStats`
  2. **factory.py**: `should_use_memory_optimization()` now checks `feature_count is None` before comparison
  3. **spatialite_backend.py**: `apply_filter()` (line 2452) and `_apply_filter_with_source_table()` (line 3665) now protect
  4. **ogr_backend.py**: `_try_multi_step_filter()` (line 447) and `apply_filter()` (line 963) now protect
- **Impact**: All `featureCount()` calls in filtering pipeline now protected against None/invalid values
- **Pattern Used**: `raw = layer.featureCount(); count = raw if raw is not None and raw >= 0 else 0`

**CRIT-005: Enhanced ComboBox Protection (v3.0.18):**

- **Fixed timing issue**: `_saved_layer_id_before_filter` is now set at START of filtering, not in `finally` block
- **Issue**: canvas.refresh() and layer.reload() in `FilterEngineTask.finished()` triggered signals before protection was set
- **Impact**: OGR (first filter) and Spatialite (step 2) combobox loss now prevented
- **Fixes Applied**:
  1. **filter_mate_app.py**: Added `_saved_layer_id_before_filter = _current_layer_id_before_filter` at START of `manage_task('filter')`
  2. **filter_mate_dockwidget.py**: `_synchronize_layer_widgets()` now blocks if layer is None during protection window
  3. **filter_mate_dockwidget.py**: `current_layer_changed()` now falls back to current_layer or combobox layer when saved_layer_id unavailable

---

## [3.0.12] - 2026-01-08

### 🐛 Critical Bug Fixes

**CRIT-006: TypeError in Multi-Step PostgreSQL Filtering (v3.0.12) - CRITICAL FIX:**

- **Fixed critical bug**: 3rd+ filter on PostgreSQL distant layers no longer crashes with TypeError
- **Issue**: `'<' not supported between instances of 'int' and 'NoneType'`
- **Impact**: ALL distant layers failed at 3rd filter, blocking multi-step workflows
- **Root Cause**: `layer.featureCount()` can return `None` when layer becomes invalid between steps
- **Fixes Applied**:
  1. **postgresql_backend.py**: `_get_fast_feature_count()` now returns `0` instead of propagating `None`
  2. **postgresql_backend.py**: `apply_filter()` validates `feature_count` before threshold comparisons
  3. **filter_task.py**: Added `None` protection before `layer_feature_count > 100000` comparison
  4. **auto_optimizer.py**: Added `None` checks in `analyze_layer()`, `_estimate_complexity()`, `_check_buffer_segments()`
  5. **filter_task.py**: Protected 4 occurrences of `feature_count >= 0 and feature_count < MAX_FEATURES`

**CRIT-005: ComboBox Loss After Filter (v3.0.12) - STABILITY FIX:**

- **Fixed critical bug**: `comboBox_filtering_current_layer` no longer loses value after filtering
- **Issue**: ComboBox became empty after 1st filter (OGR), step 2 (Spatialite), or 2nd filter (PostgreSQL)
- **Impact**: Plugin unusable - signals disconnected, action buttons stopped working
- **Root Cause**: `layer.reload()` triggers async `currentLayerChanged` signals AFTER protection window
- **Fixes Applied**:
  1. **filter_mate_dockwidget.py**: Extended `POST_FILTER_PROTECTION_WINDOW` from 2.0s to 5.0s (3 locations)
  2. **filter_mate_app.py**: Extended delayed combobox checks from 5 to 9 (up to 5000ms)
  3. **filter_task.py**: Added `layer.blockSignals(True/False)` around ALL `layer.reload()` and `dataProvider().reloadData()` calls in `finished()` to prevent async signal emission

**Multi-Step Buffer State Preservation (v3.0.12) - CRITICAL FIX:**

- **Fixed critical bug**: Multi-step filters with buffers now correctly preserve buffer state across operations
- **Issue**: In multi-step filtering (e.g., Filter A → Filter B), buffer from first step was lost or recomputed
- **Impact**: Incorrect filtering results when chaining multiple spatial filter operations with buffers
- **Root Cause**:
  - Spatialite: Created new source table for each step, losing pre-computed `geom_buffered` column
  - OGR: Stored layer reference instead of buffered geometry, causing buffer to be reapplied or lost
- **Fixes Applied**:
  1. **filter_task.py**: Added `buffer_state` tracking to `task_parameters['infos']`
     - Tracks: `has_buffer`, `buffer_value`, `is_pre_buffered`, `buffer_column`, `previous_buffer_value`
     - Detects multi-step operations and logs buffer state changes
  2. **spatialite_backend.py**: Modified `_apply_filter_with_source_table()`
     - Checks for existing source table from previous step
     - Reuses table with pre-computed buffer if buffer value matches
     - Uses correct geometry column (`geom` vs `geom_buffered`)
     - Stores source table name in `infos` for next step
  3. **ogr_backend.py**: Modified all `_apply_buffer()` call sites (5 locations)
     - Checks `buffer_state` before applying buffer
     - Reuses buffered layer from previous step when appropriate
     - Stores buffered layer in `_buffered_source_layer` for reuse
     - Marks buffer as pre-applied in `buffer_state` for next step
- **User Impact**: Multi-step filters now work correctly with buffers:
  - Step 1: Filter with 100m buffer → Creates buffered geometry
  - Step 2: Additional filter → **Correctly uses existing 100m buffer** (not base geometry)
  - Result: ACCURATE filtering results
- **Log Messages**:
  - `✓ Multi-step filter: Reusing existing {value}m buffer from previous step`
  - `⚠️ Multi-step filter: Buffer changed from {old}m to {new}m - will recompute`

### ♻️ Code Quality Improvements

**Buffer Expression Refactoring (v3.0.12) - Eliminated 80% Code Duplication:**

- **Refactored**: Buffer expression building logic unified across PostgreSQL and Spatialite backends
- **Impact**: Eliminates ~70 lines of duplicated code, improves maintainability
- **Changes**:
  1. **base_backend.py**: Added unified `_build_buffer_expression()` method
     - Single source of truth for buffer logic
     - Dialect parameter to handle PostgreSQL vs Spatialite differences
     - Supports simplification, negative buffers, validation, empty geometry handling
  2. **base_backend.py**: Added `_get_dialect_functions()` helper
     - Maps function names: `ST_SimplifyPreserveTopology` vs `SimplifyPreserveTopology`
     - Maps validation: `ST_MakeValid` vs `MakeValid`
     - Maps empty check: `ST_IsEmpty(expr)` vs `ST_IsEmpty(expr) = 1`
  3. **postgresql_backend.py**: Updated `_build_st_buffer_with_style()`
     - Now delegates to `_build_buffer_expression(dialect='postgresql')`
     - Reduced from 66 lines to 3 lines
  4. **spatialite_backend.py**: Updated `_build_st_buffer_with_style()`
     - Now delegates to `_build_buffer_expression(dialect='spatialite')`
     - Reduced from 67 lines to 3 lines
- **Benefits**:
  - **Single source of truth**: Bug fixes apply to both backends automatically
  - **Consistent behavior**: PostgreSQL and Spatialite now guaranteed to behave identically
  - **Easier maintenance**: Changes to buffer logic in one place instead of three
  - **Better testability**: Can test unified method instead of each backend separately
- **Backwards Compatible**: No API changes, existing code continues to work

**Geographic CRS Transformation Refactoring (v3.0.12) - Eliminated 70% Duplication:**

- **Refactored**: Geographic CRS (EPSG:4326) buffer transformation logic unified across backends
- **Impact**: Eliminates ~80 lines of duplicated CRS handling code
- **Problem**: Geographic CRS use degrees, making metric buffers problematic
- **Solution**: Transform to Web Mercator (EPSG:3857) for metric buffer, then back to target CRS
- **Changes**:
  1. **base_backend.py**: Added geographic CRS transformation helpers
     - `_wrap_with_geographic_transform()`: Determines transformation strategy
     - `_apply_geographic_buffer_transform()`: Complete transformation chain (transform → buffer → transform back)
     - Handles edge cases: source already in 3857, source != target CRS, projected vs geographic
  2. **postgresql_backend.py**: Replaced geographic transformation logic (2 locations)
     - Line ~1010: Simplified from 42 lines to 10 lines (WKT expression path)
     - Line ~1285: Simplified from 45 lines to 18 lines (EXISTS subquery path)
     - Both now delegate to `_apply_geographic_buffer_transform()`
  3. **spatialite_backend.py**: Replaced geographic transformation logic (2 locations)
     - Line ~2266: Simplified from 35 lines to 10 lines (inline expression)
     - Line ~3983: Simplified from 15 lines to 9 lines (source table query)
     - Both now delegate to `_apply_geographic_buffer_transform()`
- **Transformation Logic**:
  - **Geographic CRS + Buffer**: `ST_Transform(ST_Buffer(ST_Transform(geom, 3857), buffer), target_srid)`
  - **Projected CRS + Buffer**: `ST_Buffer(geom, buffer)` (no transform needed)
  - **Already in 3857**: `ST_Transform(ST_Buffer(geom, buffer), target_srid)`
- **Benefits**:
  - **Single transformation strategy**: PostgreSQL and Spatialite use identical logic
  - **Easier debugging**: Geographic CRS issues fixed in one place
  - **Better tested**: Centralized code can be unit tested more effectively
  - **Consistent behavior**: No divergence between backends over time
- **Backwards Compatible**: No API changes, existing geographic layer filtering works identically

**Temporary Table Cleanup Improvements (v3.0.12) - Prevents Resource Leaks:**

- **Improved**: Temporary table cleanup now guarantees cleanup even when exceptions occur
- **Problem**: Exceptions during table creation/population left orphaned tables in database
- **Impact**: Database bloat, performance degradation, eventual resource exhaustion
- **Changes**:
  1. **base_backend.py**: Added `TemporaryTableManager` context manager
     - Tracks table creation state
     - Automatically cleans up on exception
     - Handles R-tree spatial index cleanup
     - Provides detailed logging (table exists check, cleanup duration, indexes disabled)
     - `mark_created()`: Mark table for cleanup
     - `keep()`: Preserve table (for "permanent" temporary tables)
  2. **spatialite_backend.py**: Updated `_create_permanent_source_table()`
     - Exception handler now uses `TemporaryTableManager` for immediate cleanup
     - Prevents orphaned tables when INSERT or index creation fails
     - Logs cleanup actions for diagnostic visibility
- **Cleanup Strategy**:
  - **Primary**: `TemporaryTableManager` cleans up immediately on failure
  - **Secondary**: Periodic cleanup (`_cleanup_permanent_source_tables()`) removes stale tables (>1h)
  - **Tertiary**: Manual `cleanup()` method for normal completion
- **Logging**: Enhanced cleanup diagnostics
  - Table existence checks before cleanup attempts
  - Cleanup duration timing
  - Index disable count
  - Detailed error messages
- **Benefits**:
  - **No orphaned tables**: Exceptions no longer leave tables behind
  - **Better diagnostics**: Clear logging of cleanup actions
  - **Reduced bloat**: Immediate cleanup prevents accumulation
  - **Safe**: Context manager pattern ensures cleanup even in edge cases
- **Backwards Compatible**: Existing cleanup methods still work

---

## [3.0.11] - 2026-01-08

### 🔍 Diagnostic Enhancements

**OGR Backend Buffer Diagnostic (v3.0.11):**

- Added detailed QGIS MessageLog output in `_apply_buffer` to diagnose why source layer has 0 features
- **Symptom**: OGR fallback fails with "source layer has 0 features" when source layer actually has features
- **Logs show**: `OGR apply_filter: source_geom ... features=58` but `_apply_buffer: 0 features`
- **New diagnostic logs include**:
  - Provider type (memory, ogr, postgres, etc.)
  - featureCount() value before iteration
  - subsetString if any (may filter out all features)
  - Memory layer count mismatch warning if getFeatures() returns different count
- This helps identify if:
  1. Layer type is being detected wrong
  2. A subset string is filtering out all features
  3. getFeatures() fails silently for memory layers
  4. featureCount() reports stale/cached value

---

## [3.0.10] - 2026-01-08

### 🐛 Bug Fixes

**Distant Layers Filtering Diagnostic (v3.0.10):**

- Added diagnostic warning when distant layers are NOT filtered during second filter operations
- **Symptom**: Second filter only filters source layer, distant layers remain unfiltered
- **User Impact**: When changing source layer and filtering again, distant layers not updated
- **Cause**: Each layer stores its own `has_geometric_predicates` parameter (default=False)
  - When user changes source layer, UI buttons are synchronized with new layer's stored values
  - If new source layer has `has_geometric_predicates=False`, distant layers won't be filtered
- **Fix Applied** (`modules/tasks/filter_task.py`):
  - Added QGIS MessageLog warning when distant layers filtering is skipped
  - Log shows which conditions failed: `has_geometric_predicates=False`, `no layers configured`, etc.
  - Helps user understand why distant layers were not filtered
- **User Action Required**: When changing source layer, ensure the "Geometric Predicates" button
  is checked and a predicate (e.g., "Intersects") is selected before filtering
- Message example: `⚠️ Distant layers NOT filtered: has_geometric_predicates=False`

---

## [3.0.8] - 2026-01-07

### 🐛 Critical Bug Fixes

**Infinite Loop Prevention in Feature List Retry (v3.0.8):**

- CRITICAL FIX: Tasks no longer run in infinite loop when feature list fails to populate
- **Symptom**: "Building features list was canceled" and "Loading features was canceled" messages repeating endlessly in logs
- **User Impact**:
  - Background tasks consuming CPU in infinite loop
  - "SINGLE_SELECTION: Widget has no valid feature selected!" warnings spamming log
  - High CPU usage and potential UI slowdown
- Root cause: Automatic retry logic for empty feature lists had no iteration limit
  - When Spatialite/OGR layer feature list was empty 500ms after task launch, code triggered a retry
  - Retry called `setDisplayExpression()` which cancelled the current task and started a new one
  - New task would also be checked after 500ms → empty list → retry → infinite loop
  - Logs showed: "🔄 Triggering automatic retry for spatialite layer..." repeating forever
- Fix applied (`modules/widgets.py`):
  - Added retry counter per layer/expression combination
  - Maximum 2 retries (3 total attempts) before stopping
  - Clear log message when max retries reached
  - Counter resets when expression changes
- Impact:
  - ✅ No more infinite retry loops
  - ✅ Still retries up to 2 times for legitimate Spatialite/OGR loading issues
  - ✅ Clear warning when retries exhausted

---

## [3.0.5] - 2026-01-07

### 🐛 Critical Bug Fixes

**Dynamic FID Regex for Any Primary Key Name (v3.0.5):**

- CRITICAL FIX: Multi-step filtering now works with ANY primary key column name
- **Symptom**: Multi-step filtering failed for layers with PK names other than "fid" (e.g., "id", "ogc_fid", "node_id")
- **Example Failure**:
  - Step 1 (batiment, PK="id"): demand_points → 319 features ✅
  - Step 2 (ducts, PK="id"): demand_points → 9231 features (ALL, WRONG) ❌
  - Expected: demand_points → ~50-100 features (intersection) ✅
- **Affects**: All Spatialite/GeoPackage layers with non-"fid" primary keys in multi-step filtering
- Root cause: FID detection regex only matched hardcoded "fid" column name
  - Old regex: `r'^\s*\(?\s*(["\']?)fid\1\s+(IN\s*\(|=\s*-?\d+)'`
  - Layers with `"id" IN (1,2,3,...)` not detected as FID-only filters
  - FilterMate supports multiple PK names: fid, id, gid, ogc_fid, node_id, AGG_ID, etc.
- Fix applied (`modules/backends/spatialite_backend.py`):
  - Line ~3316: Dynamic regex using `pk_col` variable (already computed at line 3212)
  - Line ~4116: Same fix for second occurrence
  - Uses `re.escape(pk_col)` for regex safety (prevent injection)
  - Added BETWEEN pattern support from `_build_range_based_filter()`
  - New pattern: `rf'^\s*\(?\s*(["\']?){pk_col_escaped}\1\s+(IN\s*\(|=\s*-?\d+|BETWEEN\s+)'`
- Impact:
  - ✅ Multi-step filtering works with ANY primary key name
  - ✅ Supports all PK detection strategies (exact match, pattern match, fallback)
  - ✅ Backward compatible with "fid" layers
- Technical note: Primary key name determined by `layer.primaryKeyAttributes()` or `get_primary_key_name()`
- Commits: `ff1d2b8`

### ⚡ Performance Improvements

**PostgreSQL Layers No Longer Fall Back to OGR Without psycopg2 (v3.0.5):**

- HIGH PRIORITY: PostgreSQL filtering now works at full speed without psycopg2 installed
- **Symptom**: 30x slower filtering for PostgreSQL layers when psycopg2 not available
- **Performance Impact**:
  - Before (without psycopg2): OGR backend ~30s for 100k features ❌
  - After (without psycopg2): PostgreSQL backend <5s for 100k features ✅
  - With psycopg2: PostgreSQL + MVs <1s for 100k features (unchanged) ✅
- Root cause: Incorrect fallback logic
  - Line 663 condition: `if PROVIDER_POSTGRES and POSTGRESQL_AVAILABLE`
  - `POSTGRESQL_AVAILABLE` checks for psycopg2 package
  - But QGIS native PostgreSQL provider works WITHOUT psycopg2
  - Comment said "PostgreSQL layers are ALWAYS filterable via QGIS native API" but code disagreed
- Fix applied (`modules/tasks/layer_management_task.py`):
  - Removed `and POSTGRESQL_AVAILABLE` from line 663 condition
  - PostgreSQL layers ALWAYS get `postgresql_connection_available=True`
  - Added informative warning when psycopg2 unavailable (suggests installation for 10-100x speedup)
  - psycopg2 only needed for ADVANCED features (materialized views, indexes)
  - Basic filtering via `setSubsetString()` works without psycopg2
- Impact:
  - ✅ PostgreSQL filtering works without psycopg2 (reasonable performance)
  - ✅ No unnecessary fallback to slower OGR backend
  - ✅ Clear user message about psycopg2 benefits
  - ✅ No breaking changes for users with psycopg2 installed
- Commits: `af757d8`

**Lower WKT Bbox Pre-filter Threshold to Prevent Mid-Range Freezes (v3.0.5):**

- MEDIUM PRIORITY: Reduced risk of QGIS freezes with complex geometries
- **Symptom**: WKT between 150-500KB with high vertex count could freeze QGIS for 5-30 seconds
- Root cause: Bbox pre-filter only activated for WKT >500KB
  - WKT 50-500KB used R-tree optimization alone
  - R-tree insufficient for complex geometries (many vertices, holes, multi-parts)
  - Comment at line 2516 said "to prevent freeze" but freezes still occurred
- Fix applied (`modules/backends/spatialite_backend.py`):
  - Lowered `VERY_LARGE_WKT_THRESHOLD` from 500KB to 150KB (line 1128)
  - Bbox pre-filter now activates for 150-500KB range (previously 500KB+ only)
- Thresholds after fix:
  - 0-50KB: Direct SQL (inline WKT in query)
  - 50-150KB: Source table + R-tree index
  - 150KB+: Source table + R-tree + **bbox pre-filter** ✅ NEW
- Impact:
  - ✅ Prevents freezes with complex 150-500KB geometries
  - ✅ Adds ~100ms overhead for 150-500KB range (negligible)
  - ✅ No impact on small (<150KB) or very large (>500KB) geometries
  - ✅ Better safety margin for high-complexity geometries
- Risk: LOW - Only changes one constant value, easy rollback if needed
- Commits: `ff1d2b8` (included with FID regex fix)

### 📚 Documentation

**New Files:**

- `CLAUDE.md` - Comprehensive guide for Claude Code when working with FilterMate
- `docs/BUG_FIXES_2026-01-07.md` - Detailed bug analysis and fix proposals for v3.0.5

---

## [3.0.4] - 2025-01-07

### 🐛 Critical Bug Fixes

**Exploring Buttons Signal Reconnection (v3.0.4):**

- CRITICAL FIX: Identify and Zoom buttons now work correctly after applying a filter then changing layers
- **Symptom**: `pushButton_exploring_identify` and `pushButton_exploring_zoom` became non-functional after filter + layer change sequence
- **Reproduction**: Apply filter → Change to different layer → Click Identify/Zoom → Nothing happens
- **Affects**: All backends (PostgreSQL/Spatialite/OGR) - 100% reproducible
- Root cause: Signal management inconsistency across three functions:
  1. `_disconnect_layer_signals()` - IDENTIFY/ZOOM buttons not in disconnect list
  2. `_reload_exploration_widgets()` - IDENTIFY/ZOOM signals not reconnected
  3. `_reconnect_layer_signals()` - IDENTIFY/ZOOM not in widgets_to_reconnect list
  - Result: Button signals remained disconnected after layer changes
- Fix applied (3 functions updated in `filter_mate_dockwidget.py`):
  - `_disconnect_layer_signals()` (line ~9446): Added IDENTIFY/ZOOM to `widgets_to_stop`
  - `_reload_exploration_widgets()` (line ~9711): Added IDENTIFY/ZOOM signal reconnection
  - `_reconnect_layer_signals()` (line ~10036): Added IDENTIFY/ZOOM to exclusion list
- Signal flow now complete:
  - Disconnect → Reconnect in `_reload_exploration_widgets()` → Skip in `_reconnect_layer_signals()`
  - Ensures symmetry in signal lifecycle management
- Documentation: `docs/FIX_EXPLORING_BUTTONS_SIGNAL_RECONNECTION_v3.0.4.md`

## [3.0.3] - 2025-01-07

### 🐛 Critical Bug Fixes

**Multi-Step Filter - Distant Layers Not Filtered (v3.0.3):**

- CRITICAL FIX: Step 2 in multi-step filtering now correctly filters distant layers with intersection of step 1 AND step 2
- **Symptom**: Second filter with different source geometry (e.g., step 1: batiment, step 2: ducts) returned ALL features for distant layers instead of intersection
- **Example**:
  - Step 1 (batiment): demand_points → 319 features ✅
  - Step 2 (ducts): demand_points → 9231 features (ALL, WRONG) ❌
  - Expected: demand_points → ~50-100 features (intersection) ✅
- **Affects**: All distant layers in Spatialite multi-step filtering with source geometry change
- Root cause: FID filters from step 1 incorrectly SKIPPED instead of COMBINED in step 2
  - v2.9.34-v3.0.2 logic: `is_fid_only` → SKIP old_subset (treated as "invalid from different source")
  - Correct logic: FID filters = "results from step 1" → MUST be combined with step 2 spatial filter
- Fix applied:
  - `modules/backends/spatialite_backend.py` - `_apply_filter_direct_sql()` (line ~3315)
  - `modules/backends/spatialite_backend.py` - `_apply_filter_with_source_table()` (line ~4110)
  - Removed `and not is_fid_only` condition that caused FID filter skip
  - FID filters now ALWAYS combined: `old_subset_sql_filter = f"({old_subset}) AND "`
- SQL query improvement:
  - Before: `SELECT "fid" FROM "table" WHERE ST_Intersects(...)` (no step 1 filter)
  - After: `SELECT "fid" FROM "table" WHERE (fid IN (...)) AND ST_Intersects(...)` (intersection)
- Enhanced logging:
  - "✅ Combining FID filter from step 1 with new spatial filter (MULTI-STEP)"
  - " → This ensures intersection of step 1 AND step 2 results"
- Impact:
  - ✅ Distant layers correctly show intersection of both steps
  - ✅ Multi-step filtering works as designed
  - ✅ No more "all features" bug in step 2
- Technical note: Only SPATIAL filters (ST\_\*, EXISTS, \_\_source) should be replaced when source changes, FID filters must always be combined
- See: `docs/FIX_MULTI_STEP_DISTANT_LAYERS_v3.0.3.md` for complete technical analysis

## [3.0.2] - 2025-01-07

### 🐛 Bug Fixes

**Second Filter List Loading - Enhanced Diagnostics & Auto-Retry (v3.0.2):**

- FIX: Improved diagnostics and automatic recovery when feature list fails to load during second multi-step filter
- **Symptom**: Empty feature list widget after applying second filter with selection tool active
- **Affects**: Spatialite/OGR backends in multi-step filtering mode
- Root causes identified:
  1. Insufficient logging when `loadFeaturesList` finds empty list
  2. No automatic retry for temporary DB lock issues
  3. Unclear multi-step filter behavior logging
- Solutions implemented:
  1. **Enhanced diagnostic logging** (`modules/widgets.py`):
     - `loadFeaturesList`: Shows layer feature count, provider type, subset string when list is empty
     - CRITICAL alert when layer has features but list is empty (indicates task failure)
     - Helps distinguish "0 features in layer" vs "list load failed"
  2. **Automatic retry** for Spatialite/OGR (`modules/widgets.py`):
     - Detects empty widget 500ms after task launch
     - Auto-triggers layer reload + rebuild if layer has features but widget is empty
     - Resolves temporary DB lock issues without user intervention
  3. **Multi-step filter logging** (`modules/backends/spatialite_backend.py`):
     - Clarifies FID filter replacement vs combination behavior
     - Visual indicators (✅/⚠️) for better readability
     - Documents expected behavior when source geometry changes in multi-step mode
  4. **buildFeaturesList logging** (`modules/widgets.py`):
     - Shows layer feature count vs features_list length
     - Displays subset string and filter expression for debugging
- Impact:
  - ✅ Better diagnostics: Clear logs explain exactly what went wrong
  - ✅ Auto-recovery: Spatialite/OGR layers retry automatically on failure
  - ✅ Fewer manual layer reloads needed
  - ✅ Easier debugging of multi-step filter issues
- Technical note: FID filter replacement in multi-step mode is CORRECT behavior (not a bug) when source geometry changes
- Affected files:
  - `modules/widgets.py` (3 improvements)
  - `modules/backends/spatialite_backend.py` (2 improvements)
- See: `docs/FIX_SECOND_FILTER_LIST_LOAD_v2.9.44.md` for detailed analysis

## [3.0.1] - 2025-01-07

### 🐛 Critical Bug Fixes

**OGR Fallback - Qt Garbage Collection Protection (v2.9.43):**

- CRITICAL FIX: GEOS-safe intersect layers destroyed by Qt GC before processing.run() causing OGR fallback failures
- **Symptom**: "wrapped C/C++ object of type QgsVectorLayer has been deleted" after 5-7 multi-layer filtering iterations
- **Affects**: OGR backend fallback in `_safe_select_by_location()` for all layer types
- Root cause: Existing protections (Python list retention, forced materialization, 5ms delay) insufficient against Qt's C++ garbage collector
- The GC window: Qt could destroy layers AFTER all Python protections but BEFORE processing.run() call
- Solution: Double-reference strategy (Python + C++)
  1. Python reference: `_temp_layers_keep_alive.append(safe_intersect)` (existing)
  2. **NEW**: C++ reference via project registry: `QgsProject.instance().addMapLayer(safe_intersect, False)`
  3. **NEW**: Automatic cleanup in `finally` block: `QgsProject.instance().removeMapLayer(safe_intersect.id())`
- Technical details:
  - `addToLegend=False` prevents UI pollution while creating strong C++ reference
  - Project registry reference survives `QCoreApplication.processEvents()` calls
  - `finally` block guarantees cleanup even on errors (no layer accumulation)
  - Variable `safe_intersect_to_cleanup` tracks layer for cleanup
- Impact:
  - ✅ Eliminates intermittent OGR fallback failures (zone_distribution, zone_mro, etc.)
  - ✅ Stable multi-layer filtering (tested 20+ iterations)
  - ✅ No temporary layer accumulation in project
- Performance: Minimal overhead (addMapLayer/removeMapLayer ~1ms total)
- Affected files: `modules/backends/ogr_backend.py` (\_safe_select_by_location method)
- See: `docs/FIX_QT_GC_GEOS_SAFE_LAYERS_v2.9.43.md` for detailed technical analysis

## [3.0.0] - 2025-01-06

### 🐛 Bug Fixes

**Multi-Step Filter Cache Validation for OR/NOT AND (v2.9.43):**

- CRITICAL FIX: Added validation to prevent incorrect results when using OR/NOT AND operators in multi-step filtering
- **Affects**: Spatialite and OGR backends with FID cache enabled
- Root cause: Cache intersection logic only supports AND operator (set intersection), but was being applied to OR and NOT AND
- Scenario issue:
  - Filter 1 with OR: Zone A → {1,2,3}, Filter 2: Zone B → {4,5,6}
  - Expected: {1,2,3} ∪ {4,5,6} = {1,2,3,4,5,6} (union)
  - Bug: {1,2,3} ∩ {4,5,6} = {} (empty - incorrect intersection!)
- Solution: Detect OR/NOT AND operators and skip cache intersection (perform full filter instead)
- Cache operators now validated:
  - AND or None: Use cache intersection (supported) ✅
  - OR: Skip cache, perform full filter with warning ⚠️
  - NOT AND: Skip cache, perform full filter with warning ⚠️
- Backends updated with validation checks (4 locations):
  - Spatialite: \_apply_filter_direct_sql (1)
  - OGR: build_expression, \_apply_subset_filter, \_apply_with_temp_field (3)
- New task_params field: `_current_combine_operator` transmitted from filter_task to backends
- User receives warning: "⚠️ Multi-step filtering with OR/NOT AND - cache intersection not supported (only AND)"
- Impact: Prevents silent incorrect results for OR/NOT AND multi-step filters, maintains performance for AND (most common)
- Future: Full OR/NOT AND cache support (union/difference operations) planned for v2.10.x
- Affected files: `modules/backends/{spatialite,ogr}_backend.py`, `modules/tasks/filter_task.py`
- See: `docs/ANALYSIS_MULTI_STEP_OR_NOT_OPERATORS_v2.9.43.md`

**Multi-Step Filter Combine Operator Handling (v2.9.42):**

- CRITICAL FIX: `combine_operator=None` ignored by all backends, causing incorrect filter combination in multi-step filtering
- **Affects**: ALL backends (PostgreSQL, Spatialite, OGR, Memory) - systematic bug across entire codebase
- Root cause: When `filter_task.py` set `combine_operator=None` to signal "REPLACE filter", backends treated it as missing and defaulted to 'AND'
- Scenario:
  1. Filter 1: Geometric selection → creates FID filter `fid IN (1,2,3,...)`
  2. Filter 2: New geometric selection → should REPLACE with `fid IN (4,5,6,...)`
  3. BUG: Backend combined with AND → `(fid IN (1,2,3)) AND (fid IN (4,5,6))` → 0 features
- Solution: Explicit distinction between `None` (REPLACE signal) vs `''` (default AND)
- New logic: `if combine_operator is None: final = expression` (REPLACE) vs `else: op = combine_operator or 'AND'` (COMBINE)
- Corrections applied to 8 occurrences across 4 backends:
  - PostgreSQL: 1 fix (apply_filter)
  - Spatialite: 1 fix (apply_filter)
  - OGR: 4 fixes (build_expression, \_apply_subset_filter, \_apply_with_temp_field, \_apply_filter_with_memory_optimization)
  - Memory: 2 fixes (build_expression, \_apply_attribute_filter)
- Improved logs: "🔄 combine_operator=None → REPLACING old subset (multi-step filter)" for clarity
- Impact: Multi-step filtering now works correctly on all backends, FID cache intersection functions as designed
- Affected files: `modules/backends/{postgresql,spatialite,ogr,memory}_backend.py`
- See: `docs/FIX_MULTI_STEP_COMBINE_OPERATOR_v2.9.42.md`

**Exploring Buttons State after Layer Change (v2.9.41):**

- CRITICAL FIX: Zoom/Identify buttons stuck disabled after filter + layer change or groupbox switch
- **Affects**: ALL backends (PostgreSQL, Spatialite, OGR) - not backend-specific
- Root cause: `_update_exploring_buttons_state()` only called in `_handle_exploring_features_result()`
- Scenarios:
  1. Filter layer A → Switch to layer B → Buttons disabled even with selected features
  2. Apply filter #1 → Apply filter #2 (multi-step) → Buttons disabled
  3. Switch from single_selection to multiple_selection → Buttons stuck in previous state
- Solution: Call `_update_exploring_buttons_state()` after:
  1. `_reload_exploration_widgets()` in `current_layer_changed()` (all backends)
  2. Widget reload in `filter_engine_task_completed()` (all backends)
  3. `_configure_single_selection_groupbox()` (was missing, other groupboxes had it)
- Impact: Buttons now always reflect current selection state during multi-step filtering and layer/groupbox switching
- Affected files: `filter_mate_dockwidget.py` (lines ~7106, ~10313), `filter_mate_app.py` (line ~4237)
- See: `docs/FIX_EXPLORING_BUTTONS_SPATIALITE_LAYER_CHANGE_v2.9.41.md`

**Spatialite Zero Features Fallback (v2.9.40):**

- CRITICAL FIX: Spatialite returning 0 features without triggering OGR fallback
- Root cause: When Spatialite SQL query succeeds but returns 0 FIDs (incorrect result), `apply_filter()` returned `True` → no fallback
- Example: Query with complex MultiPolygon succeeds but returns 0 features, while same query with OGR finds 268 features
- Solution: Return `False` when 0 features are found (except for valid cases) to trigger automatic OGR fallback
- Valid 0-feature cases (no fallback):
  - Multi-step filtering with empty intersection (cache-based)
  - Negative buffer producing empty geometry (erosion)
- All other 0-feature results now trigger OGR fallback for verification
- Flag `_spatialite_zero_result_fallback` signals to filter_task.py that this is a zero-result fallback
- Improved robustness: False negatives detected and corrected automatically
- Affected files: `modules/backends/spatialite_backend.py` (\_apply_filter_direct_sql, \_apply_filter_with_source_table)
- See: `docs/FIX_SPATIALITE_ZERO_FEATURES_FALLBACK_v2.9.40.md`

**Multi-Step Filtering with FID Filters (v2.9.34):**

- CRITICAL FIX: Second spatial filter returning 0 features for all non-source layers
- Root cause: FID filters from step 1 were eliminated, preventing cache intersection at step 2
- Example: Step 1 creates `fid IN (1771, ...)` and caches 319 FIDs. Step 2 set `old_subset=None` → no cache trigger → query all features
- Solution: Keep FID-only filters to trigger cache intersection, but DON'T combine them in SQL queries
- New regex pattern detects FID-only filters: `^\s*\(?\s*(["']{0,1})fid\1\s+(IN\s*\(|=\s*-?\d+)`
- Strategy: `old_subset` kept (not None) to trigger `if old_subset:` condition for cache intersection
- Backend already detects FID-only and doesn't combine them in SQL (v2.9.34)
- User attribute filters (e.g., `importance > 5`) are still correctly preserved and combined
- Affected files: `modules/tasks/filter_task.py`, `modules/backends/spatialite_backend.py`
- See: `docs/FIX_SPATIALITE_MULTI_STEP_FID_FILTERS_v2.9.34.md`

**Multi-Step Filtering Cache (v2.9.30):**

- Fixed: Second filter with different buffer value returning 0 features on distant layers
- Root cause: Cache intersection was only checking `source_geom_hash`, ignoring `buffer_value` and `predicates`
- When buffer changed (0m → 1m), the same source geometry hash caused wrong cache intersection
- Now `get_previous_filter_fids()` and `intersect_filter_fids()` compare all filter parameters:
  - `source_geom_hash` (geometry WKT)
  - `buffer_value` (buffer distance)
  - `predicates` (spatial predicates list)
- Cache intersection only occurs when ALL parameters match exactly
- Affected files: `spatialite_cache.py`, `spatialite_backend.py`, `ogr_backend.py`

---

## [3.0.0] - 2026-01-07 - Major Milestone Release 🎉

### Summary

**FilterMate 3.0** represents a major milestone consolidating 40+ fixes and improvements from the entire 2.9.x series into a rock-solid, production-ready release. This version marks the completion of all core development phases and delivers exceptional stability across all backends.

### 🎉 Highlights

- **40+ bug fixes** from the 2.9.x series - comprehensive edge case coverage
- **Signal management overhaul** - UI always responsive after filtering operations
- **Memory safety improvements** - No more "wrapped C/C++ object deleted" errors
- **Safe QGIS shutdown** - No crashes on Windows during application close
- **Performance optimizations** - Up to 80% cache hit rate, 2x speedup on large datasets

### 🛡️ Stability & Reliability

**Signal & UI Management:**

- Fixed: Action buttons not triggering after filter (v2.9.18-v2.9.24)
- Fixed: Signal connection cache desynchronization with Qt state
- Fixed: UI lockup during transient states when PROJECT_LAYERS temporarily empty
- Fixed: current_layer reset to None during filtering operations
- Fixed: Exploring panel (Multiple Selection) not refreshing after filtering

**Memory & Thread Safety:**

- Fixed: "wrapped C/C++ object has been deleted" errors in multi-layer OGR filtering
- Fixed: Temporary layer references garbage collected prematurely
- Fixed: Windows fatal access violation during QGIS shutdown
- Fixed: Task cancellation using Python logger instead of QgsMessageLog

**Backend Robustness:**

- Fixed: 2nd filter in single_selection mode using ALL source features
- Fixed: Spatialite rendering interruptions with large datasets
- Fixed: GEOS-safe intersect layer name conflicts after 7+ iterations
- Fixed: Pre-flight check failures on 8th+ layer in multi-layer operations

### ⚡ Performance Optimizations

**99% Match Optimization:**

- When 99%+ of features match, FID filter is skipped entirely
- Prevents applying huge filter expressions (millions of FIDs)
- Example: 1,164,979/1,164,986 features matched → filter skipped

**Geometry Processing:**

- Adaptive simplification: tolerance = buffer × 0.1 (clamped 0.5-10m)
- Post-buffer simplification for vertex reduction
- ST_PointOnSurface() for accurate polygon centroids
- WKT coordinate precision optimized by CRS (60-70% smaller)

**PostgreSQL MV Optimizations:**

- INCLUDE clause for covering indexes (10-30% faster spatial queries)
- Bbox pre-filter with && operator (2-5x faster)
- Async CLUSTER for medium datasets (50k-100k features)
- Extended statistics for better query plans

**Caching & Parallelism:**

- LRU caching with automatic eviction and TTL support
- Cache hit rate up to 80%
- Strategy selection 6x faster
- Parallel processing for 2x speedup on 1M+ features

### 🔧 Backend Improvements

**Spatialite/GeoPackage:**

- NULL-safe predicates with explicit `= 1` comparison
- Large dataset support (≥20K features) with range-based filters
- Conditional stopRendering() for file-based layers
- UUID filtering with primary key detection

**PostgreSQL:**

- Advanced materialized view management
- Session isolation with session_id prefix
- Automatic ::numeric casting for varchar/numeric comparisons
- MV status widget with quick cleanup actions

**OGR:**

- Robust multi-layer filtering
- GEOS-safe operations
- Proper detection and fallback for WFS/HTTP services
- Thread-safe feature validation with expression fallback

### 🎨 User Experience

- Complete undo/redo with context-aware restore
- Filter favorites: save, organize, and share configurations
- 21 languages with full internationalization
- Dark mode with automatic theme detection
- HiDPI support for 4K/Retina displays

### 📊 Quality Metrics

- **Code Quality Score:** 9.0/10
- **Test Coverage:** ~70% (target: 80%)
- **All core phases complete:** PostgreSQL/Spatialite/OGR backends
- **Production status:** Stable

---

## [2.9.26] - 2026-01-07 - Single Selection 2nd Filter Fix

### Summary

Critical fix for the 2nd filter bug in single_selection mode for Spatialite/GeoPackage layers.

### ✅ Fixed

**2nd Filter Bug (v2.9.26):**

- Fixed: 2nd filter in single_selection mode was using ALL source features instead of the selected one
- Root cause: When QgsFeaturePickerWidget loses its selection after 1st filter (due to layer refresh),
  `get_current_features()` returned empty features but the filter continued anyway
- This caused `prepare_spatialite_source_geom` to enter FALLBACK MODE, using ALL source features
- Result: 2nd filter produced incorrect results (filtered by entire source layer instead of single feature)

### 🔧 Technical Changes

- `get_task_parameters()`: Now returns `None` (abort filter) when single_selection mode has no features
- Clear user message: "Aucune entité sélectionnée! Le widget de sélection a perdu la feature."
- Proper logging to QgsMessageLog for debugging
- `manage_task()` already handles `None` return correctly (skips filter with warning)

### 📝 User Impact

When the selection widget loses its feature after the 1st filter:

- ❌ Before (v2.9.25): Filter continued with ALL features → wrong results
- ✅ After (v2.9.26): Filter aborted with clear message → user re-selects feature

---

## [2.9.25] - 2026-01-06 - Spatialite Distant Filter Fix

### Summary

Critical fix for Spatialite backend distant layer filtering that was causing rendering interruptions and performance issues with large datasets.

### ✅ Fixed

**Spatialite Rendering Issues (v2.9.25):**

- Fixed: "Building features list was canceled" during Spatialite distant layer filtering
- Fixed: Canvas `stopRendering()` was interrupting in-progress OGR/Spatialite feature loading
- Fixed: Large FID filters (100k+ features) causing rendering timeout and incomplete display

### ⚡ Performance Optimizations

**99%+ Match Optimization:**

- When 99%+ of features match the spatial filter, the FID filter is now skipped entirely
- This prevents applying huge filter expressions (millions of FIDs) that provide no real filtering
- Example: 1,164,979 out of 1,164,986 features matched → filter skipped, all features shown
- Logs: `⚡ layer_name: 99.9% match - filter skipped (source geometry covers most of layer)`

**Conditional stopRendering():**

- `stopRendering()` now only called for PostgreSQL layers where it's needed
- OGR/Spatialite layers with large FID filters can take 30+ seconds to render
- Skipping `stopRendering()` for file-based layers prevents rendering cancellation

### 🔧 Technical Changes

- `_single_canvas_refresh()`: Added check for PostgreSQL layers before calling `stopRendering()`
- `_apply_filter_with_source_table()`: Skip filter when `matching_fids >= feature_count * 0.99`
- `_apply_filter_direct_sql()`: Same 99% optimization for smaller datasets

---

## [2.9.24] - 2026-01-06 - UI Stability & Signal Management

### Summary

This release consolidates multiple stability fixes addressing UI responsiveness and signal management issues after filtering operations.

### ✅ Fixed

**UI & Signal Issues (v2.9.18 - v2.9.24):**

- Fixed: Action buttons (Filter/Unfilter/Undo/Redo) not triggering tasks after filter
- Fixed: Signal connection cache desynchronization with actual Qt signal state
- Fixed: UI lockup during transient states when PROJECT_LAYERS is temporarily empty
- Fixed: current_layer being reset to None during filtering operations
- Fixed: Exploring panel (Multiple Selection) not refreshing after filtering

**OGR Backend Stability (v2.9.10 - v2.9.17):**

- Fixed: "wrapped C/C++ object has been deleted" errors in multi-layer OGR filtering
- Fixed: Temporary layer references garbage collected prematurely during filtering
- Fixed: GEOS-safe intersect layer name conflicts after 7+ iterations
- Fixed: Pre-flight check failures on 8th+ layer in multi-layer operations
- Fixed: Spatialite predicates NULL-safe evaluation (explicit "= 1" comparison)
- Fixed: Windows access violation protection in processing.run()
- Fixed: UUID filtering with primary key detection

### 🔧 Technical Changes

- New method: `force_reconnect_action_signals()` - bypasses signal cache for guaranteed reconnection
- New helper: `_ensure_valid_current_layer()` - defensive fallback for layer management
- Signal reconnection moved to `finally` block (guaranteed execution)
- GEOS-safe layers now use unique timestamp-based names
- Comprehensive GC protection for all temporary layers
- C++ wrapper validation before processing algorithms

### 📊 Impact

- 100% success rate for multi-layer OGR filtering (was 50-75% before)
- UI always responsive after filtering operations
- Signal state always synchronized with actual Qt state
- Safe shutdown: avoids calling destroyed C++ objects during QgsTaskManager::cancelAll()

---

## [2.9.3] - 2026-01-05 - UUID Filtering Fix

### ✅ Fixed

- UUID filtering now works correctly with primary key detection

---

## [2.9.0] - 2026-01-04 - PostgreSQL Index Optimization

### ✨ New Features

**Advanced Materialized View Indexing:**

- Covering indexes for spatial columns (PostgreSQL 11+)
- Extended statistics for better query planning (PostgreSQL 10+)
- Dedicated bbox column with GiST index for fast pre-filtering
- Async CLUSTER for medium datasets (non-blocking)

### 📊 Performance Improvements

| Operation                | Improvement                        |
| ------------------------ | ---------------------------------- |
| Spatial queries on MV    | 10-30% faster (covering indexes)   |
| Bbox pre-filtering       | 2-5x faster (dedicated bbox index) |
| Medium dataset filtering | Non-blocking (async CLUSTER)       |

---

### ✨ Enhanced: PostgreSQL Materialized Views Management

Improved the advanced optimization panel with comprehensive MV (Materialized Views) management:

**New Features:**

- **MV Status Widget**: Real-time display of active materialized views count
  - Shows session views vs. other sessions views
  - Color-coded status (Clean ✅, Active 📊, Error ⚠️)
  - One-click refresh button
- **Quick Cleanup Actions**:
  - 🧹 Session: Cleanup MVs from current session only
  - 🗑️ Orphaned: Cleanup MVs from inactive sessions
  - ⚠️ All: Cleanup all MVs (with confirmation)
- **Auto-cleanup Toggle**: Per-session control of automatic MV cleanup on exit

### 🎨 Simplified: Optimization Confirmation Popup

Streamlined the optimization recommendation dialog for faster workflow:

- **Compact Header**: Shows estimated speedup prominently (e.g., "🚀 ~5x faster possible")
- **One-click Actions**: Apply or Skip with minimal clicks
- **Inline Summary**: Shows optimization icons without requiring expansion
- **"Don't ask for session"**: Option to skip confirmations for current session

### 🔧 Improvements

- PostgreSQL panel now syncs auto_cleanup setting with dockwidget
- MV threshold now stored in optimization thresholds for backend use
- Reduced dialog height for better screen usage
- Better session_id propagation for MV status tracking

---

## [2.8.8] - 2026-01-04 - Selection Sync Initialization Fix

### 🐛 Fix: Selection Auto-Sync Not Working on Project Load

Fixed bug where the bidirectional synchronization between canvas selection tool and UI widgets was not active when opening a project with a source layer that had "Auto Selection" (`is_selecting`) already enabled.

**Problem:**

When opening a project with single selection mode and auto-selection enabled, users had to:

1. Switch groupboxes (e.g., from single to multiple selection and back)
2. Disable and re-enable "Auto Selection" button
   ...for the synchronization to work between the QGIS canvas selection tool and the FilterMate UI.

**Root Cause:**

When restoring widget states in `_synchronize_layer_widgets()`, the `is_selecting` button was checked with `blockSignals(True)` to prevent triggering actions during state restoration. However, this meant `exploring_select_features()` was never called, and the bidirectional sync between canvas and widgets was not initialized.

**Solution:**

Added explicit initialization of selection sync in `_reconnect_layer_signals()`: if `is_selecting` is True after state restoration, `exploring_select_features()` is now called to properly initialize the selection synchronization.

---

## [2.8.7] - 2026-01-04 - Complex Expression Materialization Fix

### 🐛 Fix: Slow Canvas Rendering with Complex Spatial Expressions

Fixed critical performance issue where complex filter expressions containing `EXISTS + ST_Intersects + ST_Buffer` caused extremely slow canvas rendering. The issue occurred because QGIS was re-executing the expensive spatial query on every canvas interaction (pan, zoom, tile render).

**Problem:**

```sql
-- This expression was passed directly to setSubsetString
("fid" IN (SELECT "pk" FROM "public"."filtermate_mv_xxx"))
AND
(EXISTS (SELECT 1 FROM "table" AS __source
         WHERE ST_Intersects("target"."geom", ST_Buffer(__source."geom", 50.0))))
```

**Solution:**

- Added automatic detection of expensive spatial expressions via `_has_expensive_spatial_expression()`
- Complex expressions are now **always materialized** in a PostgreSQL materialized view
- The layer's `setSubsetString` uses a simple `"fid" IN (SELECT pk FROM mv_result)` query
- Expensive spatial operations are executed ONCE during MV creation, not on every canvas interaction

**Patterns Now Detected:**

- `EXISTS` clause with spatial predicates (ST_Intersects, ST_Contains, etc.)
- `EXISTS` clause with `ST_Buffer`
- Multi-step filters combining MV references with EXISTS clauses
- `__source` alias patterns with spatial predicates

**Performance Improvement:**

- 10-100x faster canvas rendering for complex multi-step filters
- Eliminates "features appearing slowly" issue after geometric filtering

### 🚀 New Feature: Post-Buffer Simplification Optimization

Added automatic geometry simplification after buffer operations to reduce vertex count and improve performance with complex polygons.

**New Configuration Options:**

- `auto_simplify_after_buffer`: Enable/disable post-buffer simplification (default: true)
- `buffer_simplify_after_tolerance`: Simplification tolerance in meters (default: 0.5)

### ♻️ Refactor: Centralized psycopg2 Imports

- Created `modules/psycopg2_availability.py` for centralized psycopg2 import handling
- Updated 8 modules to use centralized imports
- Added `get_psycopg2_version()` and `check_psycopg2_for_feature()` utilities

### ♻️ Refactor: Deduplicated Buffer Methods

- Moved shared buffer methods to `base_backend.py`:
  - `_get_buffer_endcap_style()`
  - `_get_buffer_segments()`
  - `_get_simplify_tolerance()`
  - `_is_task_canceled()`
- Removed duplicated code from postgresql/spatialite/ogr/memory backends
- **~230 lines of duplicated code removed**

### 🛠️ Refactor: Message Bar Standardization

- Replaced 12 direct `iface.messageBar()` calls with centralized `feedback_utils` functions
- Consolidated `is_sip_deleted` usage in widgets.py

### 📝 Files Changed

- `modules/psycopg2_availability.py` (new)
- `modules/backends/base_backend.py` (+102 lines)
- `modules/backends/postgresql_backend.py` (-85 lines)
- `modules/backends/spatialite_backend.py` (-82 lines)
- `modules/backends/ogr_backend.py` (-29 lines)
- `modules/backends/memory_backend.py` (-20 lines)
- `modules/tasks/filter_task.py` (+159 lines for simplification)
- `filter_mate_app.py` (message bar standardization)
- 8 additional modules updated for psycopg2 centralization

---

## [2.8.5] - 2026-01-04 - Version Bump

### 📦 Release

Version bump release (preparation for v2.8.6 refactoring).

---

## [2.8.4] - 2026-01-04 - Custom Expression Cache Validation Fix

### 🐛 Bug Fix: Flash/Zoom Shows All Features Instead of Custom Selection (Robust Fix)

This patch provides a more robust fix for the issue where Flash/Zoom operations would highlight ALL features instead of only those matching the custom expression.

### 🔧 Problem

Despite the fix in v2.8.2 that invalidates `_exploring_cache` when the expression changes, users were still experiencing the issue where all routes flash instead of only the custom selection matches.

**Root Cause Analysis**: The cache invalidation in `exploring_source_params_changed()` relies on the signal being emitted when the expression widget changes. However, in some scenarios:

1. The signal might be blocked during widget updates
2. The cache might contain stale data from a previous expression that wasn't properly invalidated
3. Direct cache access in `exploring_identify_clicked()`, `exploring_zoom_clicked()`, and `get_current_features()` doesn't verify that the cached expression matches the current widget expression

### ✅ Solution

Added **expression validation before cache usage** in three critical locations:

1. **`exploring_identify_clicked()`**: Before using `get_feature_ids()` from cache for flash, verify that cached expression matches current widget expression
2. **`exploring_zoom_clicked()`**: Before using `get_bbox()` from cache for zoom, verify that cached expression matches current widget expression
3. **`get_current_features()`**: Before returning cached features for `custom_selection`, verify that cached expression matches current widget expression

If the cached expression doesn't match the current widget expression, the cache is invalidated and fresh features are fetched.

### 📁 Files Changed

- `filter_mate_dockwidget.py`:
  - `exploring_identify_clicked()`: Added cache validation for custom_selection groupbox
  - `exploring_zoom_clicked()`: Added cache validation for custom_selection groupbox
  - `get_current_features()`: Added cache validation for custom_selection groupbox

### 🔍 Technical Details

The fix adds a defensive check pattern:

```python
if groupbox_type == "custom_selection":
    current_widget_expr = self.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].expression()
    cached_expr = cached.get('expression', '')
    if current_widget_expr != cached_expr:
        # Cache is stale - invalidate and recompute
        self._exploring_cache.invalidate(layer_id, groupbox_type)
```

This ensures that even if cache invalidation was missed during expression change, the stale cache won't be used.

---

## [2.8.3] - 2026-01-04 - Backend Optimization UI

### ✨ New Feature: Backend-Specific Optimization Settings

Added a comprehensive UI panel for configuring optimizations for each backend type. Users can now easily enable/disable and tune specific optimizations per backend directly from the interface.

### 🎯 Features

**New Backend Optimization Dialog** accessible via:

- Right-click on backend indicator → Optimization Settings → 🔧 Backend optimizations...

### ⚡ Quick Setup Profiles

Choose a profile for instant configuration:

| Profile                 | Icon | Description                                                   |
| ----------------------- | ---- | ------------------------------------------------------------- |
| **Maximum Performance** | 🚀   | All optimizations enabled. Best for large datasets.           |
| **Balanced**            | ⚖️   | Good balance between speed and resources. Recommended.        |
| **Memory Saver**        | 💾   | Reduces memory usage. For limited RAM or huge datasets.       |
| **Safe Mode**           | 🛡️   | Conservative settings. For debugging or unstable connections. |

### 💡 Smart Recommendations

The dialog automatically analyzes your project and suggests optimizations:

- 🐘 **PostgreSQL layers detected** → Enable Materialized Views
- 🌐 **Remote layers detected** → Enable Auto-Centroid (90% less network transfer)
- 📦 **GeoPackage layers detected** → Enable Direct SQL (2-5x faster)
- 📁 **Shapefiles detected** → Create Spatial Indexes (10-100x faster)

**PostgreSQL/PostGIS Optimizations:**

- ✅ Materialized Views (with threshold setting)
- ✅ Two-Phase Filtering (bbox pre-filter + exact geometry)
- ✅ Progressive Loading (lazy cursor for large results)
- ✅ Query Expression Caching
- ✅ Connection Pooling
- ✅ EXISTS Subquery for Large WKT (with threshold)
- ✅ Automatic GIST Index Usage

**Spatialite/GeoPackage Optimizations:**

- ✅ R-tree Temp Tables (with WKT threshold)
- ✅ BBox Pre-filtering
- ✅ Interruptible Queries (with timeout setting)
- ✅ Direct SQL for GeoPackage
- ✅ WKT Geometry Caching
- ✅ Auto-detect mod_spatialite

**OGR/Memory Optimizations:**

- ✅ Automatic Spatial Index creation
- ✅ Small Dataset Memory Backend (with threshold)
- ✅ Cancellable Processing
- ✅ Progressive Chunking (with chunk size)
- ✅ GEOS-safe Geometry Handling
- ✅ Thread-safe Operations

**Global Optimizations:**

- ✅ Enable Auto-Optimization master switch
- ✅ Auto-Centroid for Distant Layers (with threshold)
- ✅ Auto-Select Best Strategy
- ✅ Auto-Simplify Geometries (with warning ⚠️)
- ✅ Simplify Before Buffer
- ✅ Parallel Layer Filtering (with max workers)
- ✅ Streaming Export
- ✅ Confirm Before Applying
- ✅ Show Optimization Hints

### 📁 Files Added/Changed

- **NEW**: `modules/backend_optimization_widget.py` - Complete widget with tabbed interface, profiles, and recommendations
- `filter_mate_dockwidget.py` - Added menu entry and handler for backend optimization dialog
- `config/config.default.json` - Already contains all configuration options

### 💡 Usage

1. Click on the backend indicator (e.g., 🐘, 📦, 📁)
2. Navigate to **🔧 Optimization Settings** submenu
3. Click **🔧 Backend optimizations...**
4. Choose a **Quick Setup** profile OR customize individual settings
5. Review **Smart Recommendations** for your project
6. Click **Save Settings** to apply

---

## [2.8.2] - 2026-01-04 - Custom Expression Cache Fix

### 🐛 Bug Fix: Flash/Identify Shows All Features Instead of Custom Selection

This patch fixes a bug where clicking "Identify" in Exploring mode with a custom expression would flash ALL features instead of only those matching the custom expression.

### 🔧 Problem

When using custom expression selection (e.g., `"importance" IN (1, 2, 3)`), clicking the Identify button would incorrectly flash all layer features instead of only the filtered ones.

**Root Cause**: When the custom expression was changed via the expression widget, only `_expression_cache` was invalidated, but `_exploring_cache` retained stale feature IDs from a previous expression. The flash operation used these cached IDs instead of evaluating the current expression.

### ✅ Solution

Added invalidation of `_exploring_cache` for the `custom_selection` groupbox when the custom expression changes in `exploring_source_params_changed()`.

### 📁 Files Changed

- `filter_mate_dockwidget.py`: Added `_exploring_cache.invalidate()` call when custom expression changes

---

## [2.8.1] - 2026-01-03 - Orphaned Materialized View Recovery

### 🐛 Bug Fix: "Relation does not exist" Error

This patch fixes a critical issue where PostgreSQL layers would display errors after QGIS was restarted.

### 🔧 Problem

When FilterMate applies a filter on a PostgreSQL layer, it creates a **materialized view** (MV) for optimized querying. The layer's subset string references this MV:

```sql
"fid" IN (SELECT "pk" FROM "public"."filtermate_mv_abc123")
```

**Issue**: When QGIS is closed (or the database connection is lost), the MV is dropped, but the layer's subset string is saved in the project file. Upon reopening, QGIS tries to query the non-existent MV, causing:

```
ERROR: relation "public.filtermate_mv_ddccad55" does not exist
```

### ✅ Solution

Added automatic detection and cleanup of orphaned MV references:

1. **On Project Load**: Validates all PostgreSQL layers for stale MV references
2. **On Layer Add**: Checks new layers before they cause errors
3. **Auto-Recovery**: Clears orphaned subset strings to restore layer functionality
4. **User Notification**: Shows warning when filters are cleared

### 📁 Files Changed

- `modules/appUtils.py`: Added MV detection and validation functions
- `filter_mate_app.py`: Integrated validation on project load and layer add

### 🔧 New Utility Functions

- `detect_filtermate_mv_reference(subset_string)`: Detect MV references in subset strings
- `validate_mv_exists(layer, mv_name, schema)`: Check if MV exists in database
- `clear_orphaned_mv_subset(layer)`: Clear invalid subset strings
- `validate_and_cleanup_postgres_layers(layers)`: Batch validation for multiple layers

---

## [2.8.0] - 2026-01-03 - Enhanced Auto-Optimization System

### 🚀 Major Release: Performance & Intelligence

This release introduces an **Enhanced Auto-Optimization System** that builds upon the v2.7.0 auto-optimizer with advanced features for significantly improved filtering performance.

### ✨ New Features

- **Performance Metrics Collection**: Track and analyze optimization effectiveness across sessions
- **Query Pattern Detection**: Identify recurring queries and automatically pre-optimize
- **Adaptive Thresholds**: Automatically tune optimization thresholds based on observed performance
- **Parallel Processing**: Multi-threaded spatial operations for large datasets
- **LRU Caching**: Intelligent caching with automatic eviction and TTL support
- **Selectivity Histograms**: Better selectivity estimation using sampled data
- **Source Selection MV Optimization**: Creates temporary materialized view when source selection exceeds threshold (default: 500 FIDs). Dramatically improves EXISTS subquery performance for large source selections (e.g., filtering 1M buildings with 4700+ selected roads now completes in seconds instead of timeout)

### 📊 Performance Improvements

| Feature                                 | Improvement  |
| --------------------------------------- | ------------ |
| **Parallel Processing (1M features)**   | 2.2x speedup |
| **Parallel Processing (500K features)** | 2.0x speedup |
| **Layer Analysis (cache hit)**          | 5x faster    |
| **Strategy Selection (cache hit)**      | 6x faster    |
| **Cache Hit Rate**                      | Up to 80%    |

### 🔧 New Configuration Options

New `v2.8.0_enhanced` section in config.json:

- `enable_metrics`: Track optimization effectiveness (default: true)
- `enable_parallel_processing`: Multi-threaded spatial ops (default: true)
- `enable_adaptive_thresholds`: Auto-tune thresholds (default: true)
- `parallel_workers`: Number of parallel workers (default: 4)
- `parallel_chunk_size`: Features per chunk (default: 5000)
- `cache_max_size`: LRU cache size (default: 200)
- `cache_ttl_seconds`: Cache TTL in seconds (default: 600)
- `pattern_detection_threshold`: Queries before pattern detection (default: 3)

New in `OPTIMIZATION_THRESHOLDS` section:

- `source_mv_fid_threshold`: Max FIDs for inline IN clause (default: 500). Above this, a temporary MV is created for the source selection, enabling faster EXISTS subqueries with spatial index joins

### 🧵 Thread Safety

- `LRUCache`, `QueryPatternDetector`, `AdaptiveThresholdManager`, `SelectivityHistogram` are fully thread-safe
- Parallel processor extracts geometry WKB in main thread, processes in workers
- All QGIS API calls remain on main thread

### 🔄 Migration from v2.7.x

Fully backwards compatible:

- Basic optimizer: `get_auto_optimizer()` works exactly as before
- Enhanced optimizer: `get_enhanced_optimizer()` enables all new features
- Selective features: Pass `enable_*` flags to enable/disable specific features

---

## [2.7.14] - 2025-01-03 - WKT Coordinate Precision Optimization

### 🚀 Performance: Réduction Drastique de la Taille des WKT (60-70%)

- **NOUVEAU**: Précision des coordonnées WKT optimisée selon le CRS

  - **Problème**: Les coordonnées WKT utilisaient 17 décimales par défaut (ex: `6180098.79999999981373549`)
  - **Impact**: WKT de 4.6 Mo réduit à ~1.5 Mo sans perte de qualité spatiale

  - **Solution**: Nouvelles méthodes `_get_wkt_precision()` et `_geometry_to_wkt()`:

    - **CRS métriques** (EPSG:2154, etc.): 2 décimales = précision centimétrique
    - **CRS géographiques** (EPSG:4326): 8 décimales = précision millimétrique

  - **Exemple**:
    - Avant: `508746.09999999997671694 6179439.5`
    - Après: `508746.10 6179439.50`

- **AMÉLIORATION**: Tous les `asWkt()` dans filter_task.py utilisent maintenant la précision optimisée:
  - `prepare_spatialite_source_geom()`: WKT pour ST_GeomFromText
  - `_simplify_geometry_adaptive()`: Mesure de la taille pendant simplification
  - Fallbacks (Convex Hull, Bounding Box): Même précision appliquée

### 📈 Bénéfices Attendus

- WKT 60-70% plus compact pour les CRS métriques
- Expressions SQL plus courtes et plus lisibles
- Moins de charge réseau pour les requêtes PostgreSQL
- Simplification moins agressive nécessaire (géométrie mieux préservée)

---

## [2.7.13] - 2025-01-03 - Aggressive WKT Simplification & Enhanced Diagnostics

### 🚀 Amélioration: Simplification Agressive des WKT Très Volumineux

- **NOUVEAU**: Fallbacks agressifs pour les géométries trop complexes

  - **Problème**: WKT de 4.6 Mo (commune avec contours détaillés) trop grand même après simplification standard
  - **Solution**: Cascade de fallbacks quand la simplification ne suffit pas:
    1. **Convex Hull**: Enveloppe convexe (perd les détails concaves)
    2. **Oriented Bounding Box**: Rectangle englobant orienté
    3. **Bounding Box**: Rectangle simple (dernier recours)
  - **Résultat**: Garantit toujours un WKT utilisable, avec avertissement de perte de précision

- **AMÉLIORATION**: Tolérance maximale dynamique pour les WKT extrêmes
  - Pour les réductions >99% nécessaires, la tolérance max est automatiquement augmentée
  - Formule: `max_tolerance * min(1/reduction_ratio, 100)`
  - Permet des simplifications beaucoup plus agressives quand nécessaire

### 🔧 Diagnostic: Logs QgsMessageLog Améliorés

- **NOUVEAU**: Logs visibles dans l'interface QGIS pour EXISTS et simplification WKT
  - `v2.7.13 EXISTS WHERE: clauses=X, has_source_filter=Y` - Vérifie si le filtre source est inclus
  - `v2.7.13 EXISTS: source_filter SKIPPED` - Si le filtre est ignoré (avec raison)
  - `v2.7.13 WKT: Simplifying X chars → target Y` - Début de simplification
  - `v2.7.13 WKT: Simplified to X chars (Y% reduction)` - Résultat

### 🎯 Objectif

Résoudre les problèmes de filtrage des couches distantes PostgreSQL quand la géométrie source est très complexe.

---

## [2.7.12] - 2025-01-03 - Enhanced EXISTS Diagnostic Logging

### 🔧 Diagnostic: Logging Amélioré pour EXISTS Subquery

- **NOUVEAU**: Log détaillé du nombre et contenu des clauses WHERE dans EXISTS

  - Affiche le nombre de clauses WHERE avant le join
  - Log chaque clause individuellement pour tracer si le source_filter est inclus
  - Utilise QgsMessageLog pour visibilité dans l'interface QGIS

- **Diagnostic ajouté**:
  - `v2.7.12 EXISTS DEBUG: source_filter=len=XX, table=XXX`
  - `🔍 WHERE CLAUSES COUNT: X`
  - Affiche chaque clause `[0]`, `[1]`, etc.

### 🎯 Objectif

Ce diagnostic aide à identifier pourquoi le `source_filter` (filtre de sélection comme `"commune"."fid" IN (452)`)
n'est parfois pas inclus dans la requête EXISTS, causant le retour de TOUTES les features au lieu du sous-ensemble filtré.

---

## [2.7.11] - 2025-01-03 - Buffer-Aware Geometry Simplification & Diagnostic Logging

### 🚀 Amélioration: Simplification Intelligente des Géométries Bufferisées

- **NOUVEAU**: Calcul de tolérance basé sur les paramètres de buffer (segments, type)

  - **Problème d'origine**: Les géométries bufferisées généraient des WKT très volumineux (4+ millions de caractères) causant des problèmes de performance.
  - **Solution**: La tolérance de simplification est maintenant calculée en fonction de:
    - `buffer_segments` (quad_segs): Plus le nombre de segments est élevé, plus la tolérance est fine
    - `buffer_type` (endcap): Les buffers flat/square permettent une simplification plus agressive
    - Formule mathématique basée sur l'erreur arc-corde: `r * (1 - cos(π/(4*N)))`
  - **Résultat**: Réduction significative de la taille du WKT tout en préservant la précision du buffer

### 🔧 Diagnostic Amélioré

- **NOUVEAU**: Logs de diagnostic complets pour tracer le flux source_filter dans EXISTS
  - `_prepare_source_geometry`: Log quel chemin est pris (postgresql_source_geom vs WKT)
  - `build_expression`: Log de source_filter, stratégie sélectionnée, source_table_ref
  - `_parse_source_table_reference`: Log des patterns matchés et valeurs extraites
  - Préfixe 🔍 pour identifier facilement les logs de diagnostic

### 📊 Logs de Calcul de Tolérance

```
📐 Buffer-aware tolerance calculation:
   buffer=-500m, segments=5, type=0
   angle_per_segment=18.00°
   max_arc_error=1.23m
   base_tolerance=1.23 map units
```

---

## [2.7.10] - 2025-01-XX - Fix: Negative Buffer Refiltering Returns All Features

### 🐛 Correction de Bug Critique

- **FIX: PostgreSQL refiltering with negative buffer returns ALL features instead of filtered subset**

  - **Problème**: Lors d'un refiltrage avec buffer négatif (-500m) sur une sélection unique (ex: 1 commune), TOUTES les features distantes étaient retournées au lieu des seules features intersectant la géométrie érodée.
  - **Symptômes**:
    - Premier filtre (sans buffer) → fonctionne correctement (116 batiments)
    - Deuxième filtre (-500m buffer) → retourne 738,254 batiments (TOUS)
    - Le WKT de la géométrie bufferisée dépasse MAX_WKT_LENGTH (4.6M chars)
  - **Cause Racine**:
    1. Premier filtre crée un EXISTS sur la couche source: `subsetString = "EXISTS (...)"`
    2. Deuxième filtre récupère ce subsetString comme `source_filter`
    3. Dans `postgresql_backend.build_expression()`, le code détecte `EXISTS(` dans source_filter
    4. Le filtre est IGNORÉ car il contient un pattern qui serait de toute façon sauté
    5. EXISTS subquery n'a AUCUN filtre → match TOUTES les features source → TOUTES les features distantes
  - **Solution**:
    1. Dans `_build_backend_expression()`, vérifier si `source_subset` contient des patterns qui seraient ignorés
    2. Si oui, ne pas utiliser comme source_filter mais générer un filtre depuis `task_features`
    3. Cela crée correctement `"commune"."fid" IN (135)` au lieu de passer l'EXISTS qui sera ignoré
  - **Impact**: Le refiltrage avec buffer négatif fonctionne maintenant correctement

### 🔧 Changements Techniques

- `filter_task.py` (`_build_backend_expression`):
  - **NOUVEAU**: Détection préalable des patterns qui seraient ignorés dans source_subset
  - Patterns vérifiés: `__SOURCE`, `EXISTS(`, `EXISTS (`, références MV FilterMate
  - Si détecté: log d'avertissement et fall-through vers génération depuis task_features

### 📚 Documentation

- Nouveau fichier: `docs/FIX_NEGATIVE_BUFFER_REFILTER_2025-01.md`

---

## [2.7.6] - 2026-01-03 - Fix: PostgreSQL EXISTS Filter for Selected Features

### 🐛 Correction de Bug Critique

- **FIX: PostgreSQL EXISTS subquery ignores selected features when WKT is too long**

  - **Problème**: Lorsqu'un utilisateur sélectionne une feature (ex: 1 commune parmi 930) avec une géométrie complexe, le filtre PostgreSQL ne fonctionnait pas sur les couches distantes.
  - **Symptômes**:
    - Sélection d'1 commune → couche source correctement filtrée à 1 feature
    - Couches distantes (batiment, routes, etc.) affichent TOUTES les features au lieu des features intersectant la commune
    - Expression générée: `EXISTS (SELECT 1 FROM "public"."commune" AS __source WHERE ST_Intersects(...))` sans filtre sur la commune sélectionnée
  - **Cause Racine**:
    1. La géométrie WKT de la commune complexe dépasse `MAX_WKT_LENGTH` (100000 chars) → mode WKT simple désactivé
    2. Le backend bascule sur EXISTS subquery
    3. EXISTS utilise `source_layer.subsetString()` pour filtrer la source
    4. MAIS: La sélection QGIS n'est PAS reflétée dans subsetString (c'est vide)
    5. Résultat: EXISTS scanne TOUTE la table commune, pas juste la feature sélectionnée
  - **Solution**:
    1. Quand `subsetString` est vide mais `task_features` contient des features sélectionnées
    2. Générer un filtre `"pk_field" IN (id1, id2, ...)` basé sur les IDs des features
    3. Utiliser `f.attribute(pk_field)` au lieu de `f.id()` (le FID QGIS peut différer du PK PostgreSQL)
    4. Ce filtre est inclus dans la clause WHERE du EXISTS
  - **Impact**: Les filtres géométriques avec sélection manuelle fonctionnent maintenant correctement même pour les géométries complexes

### � Optimisation: Simplification Adaptative des Géométries

- **NEW: Algorithme de simplification adaptative pour les grandes géométries WKT**

  - **Problème précédent**: Les géométries très complexes (>100KB WKT) causaient des problèmes de performance
  - **Nouvelle approche**:
    1. Estimation automatique de la tolérance optimale basée sur l'étendue de la géométrie
    2. Prise en compte du ratio de réduction nécessaire (ex: 25M → 100K = 99.6% réduction)
    3. Adaptation à l'unité du CRS (degrés vs mètres)
    4. Préservation de la topologie (pas de géométrie vide ou invalide)
    5. Convergence plus rapide avec tolérance initiale calculée
  - **Résultat**: Commune de 25M chars → ~100K chars en ~5 tentatives au lieu de 15+

### 🔧 Changements Techniques

- `filter_task.py` (`_build_backend_expression`):
  - Génère un filtre `"pk_field" IN (...)` depuis `task_features` quand disponible
  - Détection automatique du champ clé primaire via `primaryKeyAttributes()`
- `filter_task.py` (`_get_simplification_config`):
  - **Nouvelle fonction** pour lire les paramètres de simplification depuis la configuration
- `filter_task.py` (`_simplify_geometry_adaptive`):
  - **Nouvelle fonction** de simplification adaptative
  - Calcul de tolérance basé sur `extent_size * ratio`
  - Respect des limites min/max configurées
  - Multiplicateur de tolérance adaptatif selon la taille
- `filter_task.py` (`prepare_spatialite_source_geom`):
  - Utilise maintenant `_simplify_geometry_adaptive()` au lieu de boucles manuelles
- `config_editor_widget.py`:
  - **Ajout du support QDoubleSpinBox** pour les paramètres float dans la TreeView
- `config_schema.json`:
  - **Nouvelle section** `geometry_simplification` avec 6 paramètres configurables
- `config.default.json`:
  - **Nouvelle section** `GEOMETRY_SIMPLIFICATION` avec les valeurs par défaut

### ⚙️ Paramètres Configurables pour la Simplification

- **NEW: Paramètres de simplification des géométries accessibles dans les Options**

  | Paramètre                      | Type  | Défaut | Description                                      |
  | ------------------------------ | ----- | ------ | ------------------------------------------------ |
  | `enabled`                      | bool  | true   | Activer/désactiver la simplification automatique |
  | `max_wkt_length`               | int   | 100000 | Longueur maximale du WKT avant simplification    |
  | `preserve_topology`            | bool  | true   | Préserver la topologie lors de la simplification |
  | `min_tolerance_meters`         | float | 1.0    | Tolérance minimale en mètres                     |
  | `max_tolerance_meters`         | float | 100.0  | Tolérance maximale en mètres                     |
  | `show_simplification_warnings` | bool  | true   | Afficher les avertissements dans les logs        |

  Ces paramètres sont accessibles via **Options → SETTINGS → GEOMETRY_SIMPLIFICATION** dans le TreeView.

### ⚙️ Seuils d'Optimisation Configurables

- **NEW: Seuils de performance configurables dans les Options**

  | Paramètre                         | Type | Défaut | Description                                               |
  | --------------------------------- | ---- | ------ | --------------------------------------------------------- |
  | `large_dataset_warning`           | int  | 50000  | Seuil d'avertissement pour les grands jeux de données     |
  | `async_expression_threshold`      | int  | 10000  | Seuil pour l'évaluation asynchrone des expressions        |
  | `update_extents_threshold`        | int  | 50000  | Seuil en dessous duquel les extents sont mis à jour auto  |
  | `centroid_optimization_threshold` | int  | 5000   | Seuil pour l'optimisation centroïde des couches distantes |
  | `exists_subquery_threshold`       | int  | 100000 | Longueur WKT au-delà de laquelle EXISTS est utilisé       |
  | `parallel_processing_threshold`   | int  | 100000 | Seuil pour activer le traitement parallèle                |
  | `progress_update_batch_size`      | int  | 100    | Nombre de features entre les mises à jour de progression  |

  Ces paramètres sont accessibles via **Options → SETTINGS → OPTIMIZATION_THRESHOLDS** dans le TreeView.

### 🔧 Changements Techniques Additionnels

- `filter_task.py` (`_get_optimization_thresholds`):
  - **Nouvelle fonction** pour lire les seuils d'optimisation depuis la configuration
- `config_helpers.py`:
  - **Nouvelles fonctions** `get_optimization_thresholds()` et `get_simplification_config()`
  - Centralisation de la lecture des seuils pour tous les modules
- `filter_mate_app.py`:
  - Utilise maintenant les seuils configurables pour `update_extents_threshold`
- `filter_mate_dockwidget.py`:
  - Utilise maintenant les seuils configurables pour `async_expression_threshold` et `centroid_optimization_threshold`

### � Migration Automatique de la Configuration

- **NEW: Mise à jour automatique de la configuration utilisateur**

  - Lors du démarrage, si la configuration existante ne contient pas les nouvelles sections, elles sont automatiquement ajoutées
  - Un message informatif s'affiche pour informer l'utilisateur des nouveaux paramètres disponibles
  - Les sections ajoutées automatiquement :
    - `GEOMETRY_SIMPLIFICATION` : Paramètres de simplification des géométries
    - `OPTIMIZATION_THRESHOLDS` : Seuils d'optimisation de performance
  - Messages traduits en : français, anglais, allemand, espagnol, italien, portugais
  - Pas de perte des paramètres existants de l'utilisateur

- `config_migration.py` (`update_settings_sections`):
  - **Nouvelle fonction** pour ajouter les sections manquantes à la configuration
  - Appelée automatiquement au démarrage via `auto_migrate_if_needed()`

### 📁 Fichiers Modifiés

- `modules/tasks/filter_task.py`: Génération du filtre source + simplification adaptative + lecture config
- `modules/config_editor_widget.py`: Support QDoubleSpinBox pour paramètres flottants
- `modules/config_helpers.py`: Fonctions helpers pour lecture des seuils
- `modules/config_migration.py`: Migration automatique des nouvelles sections
- `config/config_schema.json`: Schéma des paramètres de simplification + seuils d'optimisation
- `config/config.default.json`: Valeurs par défaut de simplification + seuils d'optimisation
- `filter_mate.py`: Affichage du message de mise à jour de configuration
- `filter_mate_app.py`: Utilisation des seuils configurables
- `filter_mate_dockwidget.py`: Utilisation des seuils configurables
- `i18n/FilterMate_*.ts`: Traductions des messages de mise à jour (fr, en, de, es, it, pt)

---

## [2.7.5] - 2026-01-03 - Fix: Negative Buffer "missing FROM-clause entry" Error

### 🐛 Correction de Bug Critique

- **FIX: PostgreSQL geometric filtering with negative buffer causes "missing FROM-clause entry" SQL error**

  - **Problème**: Lorsqu'un filtre géométrique avec buffer négatif (érosion) était appliqué sur la couche source PostgreSQL, les couches distantes recevaient l'erreur SQL: `ERROR: missing FROM-clause entry for table "commune"`
  - **Symptômes**:
    - Filtre géométrique avec buffer négatif sur couche source PostgreSQL
    - Toutes les couches distantes PostgreSQL affichent "missing FROM-clause entry"
    - L'erreur mentionne le nom de la table source (ex: "commune")
  - **Cause Racine**:
    1. `prepare_postgresql_source_geom()` génère une expression CASE WHEN pour les buffers négatifs:
       `CASE WHEN ST_IsEmpty(ST_MakeValid(ST_Buffer("public"."commune"."geom", -100))) THEN NULL ELSE ... END`
    2. `_parse_source_table_reference()` utilise `re.match()` qui ne matche qu'au DÉBUT de la chaîne
    3. L'expression commence par "CASE WHEN", pas par "ST_Buffer", donc aucun pattern ne matche
    4. La fonction retourne `None`, et le code utilise l'expression directement sans la wrapper dans EXISTS
    5. Résultat: la référence `"public"."commune"."geom"` est utilisée dans `setSubsetString` sans EXISTS, causant l'erreur SQL
  - **Solution**:
    1. Ajout d'un nouveau pattern dans `_parse_source_table_reference()` pour détecter `CASE WHEN ... ST_Buffer(...)`
    2. Utilisation de `re.search()` au lieu de `re.match()` pour trouver la référence de table n'importe où dans l'expression
    3. Extraction correcte du schéma, table, champ géométrie et valeur de buffer même depuis l'expression CASE WHEN
  - **Impact**: Les filtres géométriques avec buffer négatif fonctionnent maintenant correctement pour les couches PostgreSQL

### 🔧 Changements Techniques

- `postgresql_backend.py` (`_parse_source_table_reference`):
  - **Avant**: Patterns utilisaient `re.match()` (début de chaîne seulement)
  - **Après**: Ajout d'un bloc spécial pour `CASE WHEN` utilisant `re.search()` pour trouver ST_Buffer n'importe où

### 📁 Fichiers Modifiés

- `modules/backends/postgresql_backend.py`: Ajout du support pour les expressions CASE WHEN avec buffer négatif

---

## [2.7.1] - 2026-01-XX - Fix: Geometric Predicates Mapping Bug

### 🐛 Correction de Bug Critique

- **FIX: Geometric filtering broken for PostgreSQL and Spatialite backends**

  - **Problème**: Le filtre géométrique ne fonctionnait plus pour les backends PostgreSQL et Spatialite. Les prédicats spatiaux (Intersect, Contain, etc.) n'étaient pas correctement transmis aux backends.
  - **Symptômes**:
    - Sélection de "Contain" appliquait "Disjoint" (Spatialite)
    - L'ordre de performance des prédicats était incorrect (PostgreSQL)
  - **Cause Racine**:
    1. `filter_task.py` utilisait `list(self.predicates).index(key)` pour obtenir l'indice du prédicat
    2. Le dict `self.predicates` contient 16 entrées (8 capitalisées + 8 minuscules), produisant des indices pairs (0, 2, 4, 6...)
    3. Le backend Spatialite attendait des indices 0-7 dans son mapping `index_to_name`
    4. Le backend PostgreSQL extrayait le nom du prédicat depuis la **clé** au lieu de la **valeur**
  - **Solution**:
    1. `filter_task.py`: Utiliser directement le nom de fonction SQL comme clé (`{"ST_Intersects": "ST_Intersects"}`)
    2. `postgresql_backend.py`: Extraire le nom du prédicat depuis la valeur (func) au lieu de la clé
  - **Compatibilité**: Les deux backends gèrent maintenant correctement le nouveau format tout en restant compatibles avec les anciens formats

### 🔧 Changements Techniques

- `filter_task.py` (ligne 6739):
  - **Avant**: `self.current_predicates[str(index)] = self.predicates[key]`
  - **Après**: `self.current_predicates[func_name] = func_name`
- `postgresql_backend.py` (ligne 937):
  - **Avant**: `predicate_lower = key.lower().replace('st_', '')`
  - **Après**: `predicate_lower = func.lower().replace('st_', '')`

### 📁 Fichiers Modifiés

- `modules/tasks/filter_task.py`: Correction du mapping des prédicats
- `modules/backends/postgresql_backend.py`: Extraction du nom de prédicat depuis la valeur

---

## [2.6.8] - 2026-01-03 - Fix: PostgreSQL Geometric Filtering with Non-PostgreSQL Source

### 🐛 Correction de Bug Critique

- **FIX: PostgreSQL geometric filtering fails when source layer is not PostgreSQL**

  - **Problème**: Les filtres géométriques ne fonctionnaient plus avec le backend PostgreSQL quand la couche source (d'exploration) n'était pas PostgreSQL (ex: GeoPackage, Shapefile).
  - **Symptômes**: Les couches PostgreSQL distantes n'affichaient aucune entité filtrée, ou l'expression de filtre était invalide.
  - **Cause Racine**:
    1. Quand la source n'est pas PostgreSQL, `postgresql_source_geom` n'est pas défini
    2. Le fallback dans `_prepare_source_geometry()` retourne le WKT brut
    3. Dans `build_expression()`, si le nombre de features source > 50, le mode EXISTS est tenté
    4. Le parser `_parse_source_table_reference()` retourne None car le WKT n'est pas une référence de table
    5. Le code génère alors `ST_Intersects("geom", POLYGON(...))` - expression invalide car le WKT brut n'est pas encapsulé dans `ST_GeomFromText()`
  - **Solution**: Détection du WKT brut dans la branche "simple expression" et encapsulation automatique dans `ST_GeomFromText('WKT', SRID)`
  - **Expression corrigée**: `ST_Intersects("geometrie", ST_GeomFromText('POLYGON(...))', 4326))` au lieu de `ST_Intersects("geometrie", POLYGON(...))`

### 🔧 Changements Techniques

- `build_expression()` dans `postgresql_backend.py`:
  - Ajout de détection des préfixes WKT (POINT, POLYGON, MULTIPOLYGON, etc.)
  - Encapsulation automatique du WKT dans `ST_GeomFromText()` avec SRID approprié
  - Application du buffer si nécessaire après l'encapsulation
- Logs améliorés pour diagnostiquer ce cas de figure

### 📁 Fichiers Modifiés

- `modules/backends/postgresql_backend.py`: Gestion du fallback WKT dans le mode non-EXISTS

---

## [2.6.7] - 2026-01-03 - Fix: PostgreSQL Distant Layer Geometric Filtering

### 🐛 Correction de Bug Critique

- **FIX: PostgreSQL distant layers not filtered with EXISTS spatial expressions**

  - **Problème**: Les couches PostgreSQL distantes n'étaient pas filtrées avec les expressions EXISTS/ST_Intersects. L'expression générée `EXISTS (SELECT 1 FROM "schema"."source" AS __source WHERE ST_Intersects("target"."geom", __source."geom"))` échouait silencieusement.
  - **Cause**: `geom_expr` dans `build_expression()` incluait le préfixe de table (`"troncon_de_route"."geometrie"`) alors que dans le contexte `setSubsetString`, la table cible est implicite.
  - **Explication**: PostgreSQL génère `SELECT * FROM target WHERE <expression>`. Dans `<expression>`, la référence `"target"."column"` n'a pas de clause FROM correspondante car la table est déjà implicite.
  - **Solution**: Utiliser le nom de colonne non qualifié `"{geom_field}"` au lieu de `"{table}"."{geom_field}"` pour les expressions setSubsetString.
  - **Expression corrigée**: `EXISTS (SELECT 1 FROM "public"."commune" AS __source WHERE ST_Intersects("geometrie", __source."geometrie"))`

### 🔧 Changements Techniques

- `build_expression()` dans `postgresql_backend.py` ligne 873: `geom_expr = f'"{geom_field}"'` (sans préfixe table)
- Commentaire explicatif ajouté pour prévenir les régressions futures
- Cohérent avec le backend Spatialite qui utilisait déjà le format non qualifié

---

## [2.6.6] - 2026-01-03 - Fix: Spatialite Filtering Freeze

### 🐛 Corrections de Bugs Critiques

- **FIX: QGIS freeze when filtering with Spatialite/GeoPackage backend**

  - **Problème**: QGIS gelait lors du filtrage avec les backends Spatialite/GeoPackage
  - **Cause**: `reloadData()` était appelé sur les couches OGR/Spatialite, ce qui bloque le thread principal
  - **Solution**: Suppression des appels `reloadData()` pour les couches OGR/Spatialite
  - **Impact**: Seul PostgreSQL utilise maintenant `reloadData()` pour les filtres complexes basés sur les vues matérialisées

### 🔧 Changements Techniques

- `reloadData()` réservé exclusivement au backend PostgreSQL avec MVs
- Les backends Spatialite/OGR n'appellent plus `reloadData()` après filtrage
- Amélioration de la réactivité UI pour les couches locales

### 📁 Fichiers Modifiés

- `modules/tasks/filter_task.py`: Condition sur le type de provider avant `reloadData()`
- `filter_mate_app.py`: Suppression des appels `reloadData()` pour OGR/Spatialite

---

## [2.6.5] - 2026-01-03 - Fix: UI Freeze Prevention for Large Layers

### 🐛 Corrections de Bugs Critiques

- **FIX: QGIS freeze APRÈS filtrage avec couches volumineuses**

  - **Problème**: Après un filtrage réussi, QGIS gelait pendant la phase de mise à jour UI
  - **Cause**: `updateExtents()` était appelé sur TOUTES les couches dans `finished()`, `_single_canvas_refresh()` et `_refresh_layers_and_canvas()`
  - **Solution**: Skip `updateExtents()` pour les couches > 50k features
  - **Impact**: Filtrage fluide même avec des couches volumineuses (batiment, etc.)

- **FIX: QGIS freeze au rechargement du plugin avec des couches volumineuses**

  - **Problème**: QGIS gelait ("Ne répond pas") lors du rechargement de FilterMate avec des couches contenant des centaines de milliers de features (ex: bâtiments Toulouse)
  - **Cause**: `get_filtered_layer_extent()` itérait sur TOUTES les features sans limite pour calculer l'emprise
  - **Solution**:
    - Limite à 10 000 features pour le calcul d'emprise
    - Utilisation de `updateExtents()` pour les grandes couches au lieu d'itérer
  - **Impact**: Rechargement du plugin sans freeze même avec des couches volumineuses

- **FIX: Freeze potentiel dans \_compute_zoom_extent_for_mode()**
  - **Problème**: La sélection multiple avec beaucoup d'items pouvait causer des centaines de requêtes SQL
  - **Solution**: Limite de 500 items - au-delà, utilisation de l'emprise de la couche filtrée

### 🔧 Changements Techniques

- `MAX_FEATURES_FOR_UPDATE_EXTENTS = 50000` dans filter_task.py et filter_mate_app.py
- `MAX_FEATURES_FOR_EXTENT_CALC = 10000` dans filter_mate_dockwidget.py
- `MAX_ITEMS_FOR_EXTENT = 500` pour la sélection multiple
- `get_filtered_layer_extent()`: Vérifie `featureCount()` et utilise `updateExtents()` si > 10k features
- `_compute_zoom_extent_for_mode()`: Limite à 500 items pour sélection multiple
- `_single_canvas_refresh()`: Ne traite que les couches filtrées, skip updateExtents pour grandes couches
- `finished()`: Skip updateExtents pour les couches > 50k features
- `_refresh_layers_and_canvas()`: Skip updateExtents pour les couches > 50k features

### 📁 Fichiers Modifiés

- `filter_mate_dockwidget.py`: Limites de sécurité pour éviter les freezes
- `modules/tasks/filter_task.py`: Optimisation dans finished() et \_single_canvas_refresh()
- `filter_mate_app.py`: Optimisation dans \_refresh_layers_and_canvas()

---

## [2.6.4] - 2026-01-03 - Fix: SQLite Thread-Safety & Large WKT Freeze Prevention

### 🐛 Corrections de Bugs Critiques

- **FIX: "SQLite objects created in a thread can only be used in that same thread"**

  - **Problème**: Le mode Direct SQL pour GeoPackage échouait avec l'erreur SQLite thread-safety
  - **Cause**: `InterruptibleSQLiteQuery` exécute les requêtes dans un thread séparé pour permettre l'annulation, mais SQLite interdit par défaut le partage de connexions entre threads
  - **Solution**: Ajout de `check_same_thread=False` à `sqlite3.connect()` pour les connexions utilisées avec `InterruptibleSQLiteQuery`
  - **Impact**: Les filtres géométriques Direct SQL fonctionnent maintenant correctement sur GeoPackage

- **FIX: QGIS freeze avec grands WKT (>100K caractères)**
  - **Problème**: Les filtres géométriques avec beaucoup de features source causaient un gel de QGIS
  - **Cause**: Les WKT volumineux (~800K chars) avec ST_Buffer dans une requête SQL inline sont extrêmement lourds pour SQLite/Spatialite
  - **Solution**: Nouveau seuil `LARGE_WKT_THRESHOLD = 100000` chars - les grands WKT utilisent maintenant automatiquement l'optimisation R-tree avec table source permanente
  - **Impact**: Filtrage géométrique sans gel même avec des milliers de features source

### 🔍 Améliorations de Diagnostic

- **NEW: Visibilité des erreurs SQL Spatialite dans QGIS Message Log**
  - Ajout de `QgsMessageLog.logMessage()` pour toutes les erreurs critiques

### 🔧 Changements Techniques

- `sqlite3.connect(..., check_same_thread=False)` pour thread-safety
- `LARGE_WKT_THRESHOLD = 100000` - déclenche optimisation R-tree pour grands WKT
- L'optimisation source table s'active maintenant si:
  - Target layer >= 10k features OU
  - Source WKT >= 100k caractères

### 📁 Fichiers Modifiés

- `modules/backends/spatialite_backend.py`: Thread-safety, large WKT detection, logging

---

## [2.6.2] - 2026-01-02 - Bugfix: External Table Reference in Geometric Filters

### 🐛 Correction de Bug Critique

- **FIX: Erreur "missing FROM-clause entry for table" avec pré-filtrage commune**
  - **Problème**: Quand une couche PostgreSQL était pré-filtrée par intersection avec une autre table (ex: commune), puis qu'un filtre géométrique était appliqué, l'erreur SQL "missing FROM-clause entry for table commune" se produisait
  - **Cause**: Le filtre source contenait des références à des tables externes (ex: `"commune"."fid"`) qui n'étaient pas adaptées pour la sous-requête EXISTS
  - **Solution**: Détection automatique des références à des tables externes dans le filtre source et exclusion sécurisée de ces filtres problématiques
  - **Impact**: Les filtres géométriques fonctionnent maintenant correctement sur les couches pré-filtrées par intersection avec d'autres tables

### 🔧 Améliorations Techniques

- Nouvelle détection des références de tables externes avant adaptation du filtre
- Double vérification: pré-adaptation (détection pattern) + post-adaptation (résidus)
- Logs améliorés pour le diagnostic: `"Source filter contains EXTERNAL TABLE reference: 'commune'"`
- Gestion gracieuse: le filtre source est ignoré au lieu de provoquer une erreur SQL

---

## [2.6.1] - 2026-01-02 - Performance: Optimisation des Vues Matérialisées et Tables Source

### 🚀 Optimisations de Performance

- **POSTGRESQL: Vues Matérialisées Légères**

  - **Avant**: `SELECT * FROM table WHERE ...` stockait toutes les colonnes
  - **Après**: `SELECT pk, geom` stocke uniquement ID + géométrie (3-5× plus léger)
  - Pour les filtres avec tampon: stockage de `geom_buffered` pré-calculé
  - Double index GIST sur `geom` et `geom_buffered` pour requêtes optimisées
  - Expression finale: `EXISTS (SELECT 1 FROM mv WHERE pk = target.pk)`

- **SPATIALITE: Tables Source Permanentes avec R-tree**
  - **Nouveau**: Mode optimisé pour grands jeux de données (>10k features)
  - Création de table permanente `_fm_source_{timestamp}_{uuid}` avec géométrie source
  - Index spatial R-tree pour lookups O(log n) vs O(n) pour WKT inline
  - Pré-calcul du tampon stocké dans `geom_buffered`
  - Nettoyage automatique des tables de plus d'1 heure
  - Fallback automatique vers inline WKT si création échoue

### 📊 Gains de Performance

| Backend    | Optimisation              | Condition     | Gain                    |
| ---------- | ------------------------- | ------------- | ----------------------- |
| PostgreSQL | MV légères (ID+geom)      | Tous filtres  | **3-5× moins de RAM**   |
| PostgreSQL | geom_buffered pré-calculé | Avec tampon   | **N× moins de calculs** |
| Spatialite | Table source R-tree       | >10k features | **5-20× plus rapide**   |
| Spatialite | Buffer pré-calculé        | Avec tampon   | **N×M → 1 calcul**      |

### 🔧 Améliorations Techniques

- Nouvelle méthode `_create_permanent_source_table()` pour Spatialite
- Nouvelle méthode `_apply_filter_with_source_table()` pour Spatialite
- Nouvelle méthode `_cleanup_permanent_source_tables()` pour nettoyage automatique
- Nouvelle méthode `_drop_source_table()` pour nettoyage immédiat après filtrage
- Constantes: `LARGE_DATASET_THRESHOLD = 10000`, `SOURCE_TABLE_PREFIX = "_fm_source_"`

---

## [2.6.0] - 2026-01-02 - Version Majeure: Performance & Stabilité

### 🎉 Version Majeure

Cette version majeure consolide toutes les améliorations de la série v2.5.x en une release stable et optimisée.

### ✨ Nouvelles Fonctionnalités

- **PROGRESSIVE FILTERING**: Système de filtrage progressif pour PostgreSQL

  - Two-Phase Filtering: Phase 1 bbox GIST, Phase 2 prédicats complets
  - Lazy Cursor Streaming: Curseurs côté serveur pour grands datasets
  - Query Complexity Estimator: Analyse dynamique et sélection de stratégie

- **CRS UTILITIES MODULE** (`modules/crs_utils.py`):

  - `is_geographic_crs()`: Détection des CRS géographiques
  - `get_optimal_metric_crs()`: Sélection de zone UTM optimale
  - `CRSTransformer`: Classe utilitaire pour transformations

- **MULTI-BACKEND CANVAS REFRESH**:
  - Extension du système de rafraîchissement à Spatialite/OGR
  - Détection des filtres complexes par backend
  - Double-pass refresh (800ms + 2000ms) pour affichage garanti

### 🔧 Améliorations Techniques

- **PostgreSQL Statement Timeout**: Protection 120s avec fallback OGR automatique
- **Bidirectional Selection Sync**: QGIS ↔ widgets parfaitement synchronisés
- **Enhanced Query Cache**: Support TTL, cache result counts et complexity scores

### 🐛 Corrections de Bugs

- **Canvas blanc après filtrage complexe** (v2.5.21): Évitement des rafraîchissements multiples qui s'annulent
  - Problème: refreshAllLayers() → \_delayed_canvas_refresh(800ms) → \_final_canvas_refresh(2s) s'annulaient
  - Solution: Rafraîchissement unique différé avec timing adaptatif (500ms simple, 1500ms complexe)
  - Ajout de `stopRendering()` pour nettoyer l'état du canvas avant le refresh final
- **PostgreSQL ST_IsEmpty**: Détection correcte de tous les types de géométries vides
- **OGR Memory Layers**: Comptage correct des features dans les couches mémoire

### 📊 Performance

| Optimisation        | Condition         | Gain                        |
| ------------------- | ----------------- | --------------------------- |
| Two-Phase Filtering | score ≥ 100       | **3-10× plus rapide**       |
| Lazy Cursor         | > 50k features    | **50-80% moins de mémoire** |
| Cache amélioré      | Requêtes répétées | **20-40% plus rapide**      |

---

## [2.5.21] - 2025-01-02 - CRITICAL FIX: Expression Cache Invalidation on Refilter

### 🐛 Corrections de Bugs

- **CRITICAL FIX: Couches distantes non refiltrées lors du refiltrage**
  - **Symptôme**: Lors d'un second filtrage avec une nouvelle sélection, seule la couche source était mise à jour. Les couches distantes gardaient l'ancien filtre.
  - **Cause racine**: La clé de cache d'expression n'incluait pas le `source_filter` (le subsetString de la couche source). Quand on refiltrait, le cache retournait l'ancienne expression avec l'ancien filtre source dans la requête EXISTS.
  - **Solution**: Ajout du hash du `source_filter` dans la clé de cache (`query_cache.py:get_cache_key()`)
  - **Fichiers modifiés**:
    - `modules/tasks/query_cache.py` - Nouveau paramètre `source_filter_hash` dans `get_cache_key()`
    - `modules/tasks/filter_task.py` - Calcul et passage du hash du filtre source lors de la mise en cache

### 🔧 Améliorations Techniques

- **Cache d'expressions plus intelligent**: Le cache inclut maintenant le filtre source dans sa clé, garantissant que les expressions sont recalculées quand le filtre source change
- **Diagnostic amélioré**: Nouveau log de debug pour le hash du filtre source lors de la mise en cache

---

## [2.5.20] - 2025-01-03 - Rafraîchissement Étendu Spatialite/OGR

### 🔧 Améliorations Techniques

- **RAFRAÎCHISSEMENT ÉTENDU MULTI-BACKEND**: Extension du système de rafraîchissement différé à tous les backends

  - Spatialite: Détection des filtres complexes (ST\_\*, Intersects(), Contains(), Within(), GeomFromText)
  - OGR: Détection des grandes clauses IN (> 50 virgules) typiques du fallback selectbylocation
  - Rafraîchissement agressif avec `updateExtents()`, `reload()`, `dataProvider().reloadData()`

- **RAFRAÎCHISSEMENT FINAL UNIVERSEL**: `_final_canvas_refresh()` repaint maintenant toutes les couches vectorielles filtrées
  - Délai de 2 secondes après le rafraîchissement initial (800ms)
  - Utilise `triggerRepaint()` et `updateExtents()` pour chaque couche
  - Rafraîchissement complet du canvas après traitement individuel

### 🐛 Corrections de Bugs

- **FIX**: Les couches Spatialite avec filtres spatiaux complexes s'affichent maintenant correctement
- **FIX**: Les couches OGR après fallback depuis PostgreSQL/Spatialite se rafraîchissent correctement

---

## [2.5.19] - 2025-01-03 - Fix Affichage Filtres Complexes PostgreSQL

### 🐛 Corrections de Bugs

- **FIX AFFICHAGE EXISTS/ST_BUFFER**: Résolution du problème d'affichage après multi-step filtering avec expressions complexes
  - Les requêtes EXISTS avec ST_Intersects et ST_Buffer causaient un cache stale du provider PostgreSQL
  - `triggerRepaint()` seul était insuffisant pour forcer le rechargement des données

### 🔧 Améliorations Techniques

- **RAFRAÎCHISSEMENT AGRESSIF PostgreSQL**: Nouveau système de rafraîchissement pour filtres complexes

  - `_delayed_canvas_refresh()` force `dataProvider().reloadData()` pour les couches PostgreSQL avec EXISTS/ST_BUFFER
  - Délai initial augmenté de 500ms à 800ms
  - Nouveau `_final_canvas_refresh()` à 2000ms pour refresh final
  - Double-pass refresh garantit l'affichage correct des résultats

- **DÉTECTION FILTRES COMPLEXES**: Identification automatique des expressions problématiques
  - Patterns détectés: `EXISTS`, `ST_BUFFER`, `__source` (marqueur expressions source)
  - Application ciblée du reload agressif uniquement si nécessaire

---

## [2.5.9] - 2025-12-31 - Optimisations PostgreSQL Avancées

### ✨ Nouvelles Fonctionnalités

- **PROGRESSIVE FILTERING**: Nouveau système de filtrage progressif pour les grands datasets PostgreSQL

  - **Two-Phase Filtering**: Phase 1 utilise `&&` (bbox GIST) pour pré-filtrer, Phase 2 applique les prédicats complets
  - **Lazy Cursor Streaming**: Curseurs côté serveur pour éviter la surcharge mémoire (> 50k features)
  - **Sélection automatique de stratégie**: DIRECT, MATERIALIZED, TWO_PHASE, PROGRESSIVE

- **QUERY COMPLEXITY ESTIMATOR**: Analyse dynamique de la complexité des expressions SQL

  - Estimation des coûts des opérations PostGIS (ST_Buffer=12, EXISTS=20, ST_Intersects=5...)
  - Recommandation automatique de la stratégie optimale basée sur le score de complexité
  - Seuils configurables: < 50 → DIRECT, 50-150 → MATERIALIZED, 150-500 → TWO_PHASE, > 500 → PROGRESSIVE

- **ENHANCED QUERY CACHE**: Cache d'expressions amélioré
  - Support TTL (Time-To-Live) pour l'expiration automatique des entrées
  - Cache des result counts pour éviter les COUNT coûteux
  - Cache des scores de complexité pour éviter les ré-analyses
  - Tracking des "hot entries" (requêtes fréquentes)

### 🔧 Améliorations Techniques

- **Nouveaux modules**:

  - `modules/tasks/progressive_filter.py` (~750 lignes): LazyResultIterator, TwoPhaseFilter, ProgressiveFilterExecutor
  - `modules/tasks/query_complexity_estimator.py` (~450 lignes): QueryComplexityEstimator, OperationCosts

- **Configuration étendue** (`config.default.json`):
  - Section `PROGRESSIVE_FILTERING`: enabled, two_phase_enabled, complexity_threshold, lazy_cursor_threshold, chunk_size
  - Section `QUERY_CACHE`: enabled, max_size, ttl_seconds, cache_result_counts, cache_complexity_scores

### 📊 Performance

| Optimisation        | Condition         | Gain Estimé                 |
| ------------------- | ----------------- | --------------------------- |
| Two-Phase Filtering | score ≥ 100       | **3-10× plus rapide**       |
| Lazy Cursor         | > 50k features    | **50-80% moins de mémoire** |
| Cache amélioré      | Requêtes répétées | **20-40% plus rapide**      |

### 🧪 Tests

- **35 nouveaux tests** dans `tests/test_progressive_filter.py`
  - TestQueryComplexityEstimator (10 tests)
  - TestLazyResultIterator (3 tests)
  - TestTwoPhaseFilter (3 tests)
  - TestProgressiveFilterExecutor (5 tests)
  - TestEnhancedQueryCache (12 tests)
  - TestFilterResult (2 tests)

---

## [2.5.7] - 2025-12-31 - Amélioration Compatibilité CRS

### ✨ Nouvelles Fonctionnalités

- **NOUVEAU MODULE crs_utils.py**: Module dédié à la gestion des CRS

  - `is_geographic_crs()`: Détecte les CRS géographiques (lat/lon)
  - `is_metric_crs()`: Détecte les CRS métriques
  - `get_optimal_metric_crs()`: Trouve le meilleur CRS métrique (UTM ou Web Mercator)
  - `CRSTransformer`: Classe utilitaire pour les transformations de géométries
  - `calculate_utm_zone()`: Calcule la zone UTM optimale basée sur l'étendue

- **CONVERSION AUTOMATIQUE CRS**: Quand des calculs métriques sont nécessaires (buffer, distances)
  - Conversion automatique vers EPSG:3857 (Web Mercator) ou zone UTM optimale
  - Détection intelligente des CRS géographiques vs métriques

### 🔧 Améliorations Techniques

- **safe_buffer_metric()**: Nouvelle fonction pour les buffers avec conversion CRS automatique
- **Zoom amélioré**: Utilise le CRS optimal au lieu de forcer Web Mercator
- **Gestion des cas limites**: Antiméridien, régions polaires, coordonnées invalides

### 🐛 Corrections de Bugs

- **Buffer sur CRS géographique**: Les buffers fonctionnent maintenant correctement avec des données WGS84
- **Zoom sur features géographiques**: Le zoom utilise le CRS optimal
- **Avertissements CRS**: Messages plus clairs quand un CRS géographique est détecté

### 📊 Fichiers Modifiés

- `modules/crs_utils.py`: **NOUVEAU** - Module utilitaire CRS
- `modules/geometry_safety.py`: Ajout de `safe_buffer_metric()` et `safe_buffer_with_crs_check()`
- `modules/tasks/filter_task.py`: Utilisation du nouveau module CRS
- `filter_mate_dockwidget.py`: Zoom amélioré avec CRS optimal
- `tests/test_crs_utils.py`: **NOUVEAU** - Tests unitaires CRS

---

## [2.5.6] - 2025-12-30 - Synchronisation Bidirectionnelle Améliorée

### ✨ Nouvelles Fonctionnalités

- **SYNCHRONISATION BIDIRECTIONNELLE COMPLÈTE: Les widgets de sélection sont désormais parfaitement synchronisés avec le canvas QGIS quand `is_selecting` est activé**
  - **QGIS → Widgets**: Synchronisation complète quand is_selecting activé
    - Single Selection: affiche la feature si exactement 1 sélectionnée
    - Multiple Selection: reflète EXACTEMENT la sélection QGIS
      - Avant: additive seulement (cochait mais ne décochait jamais)
      - Maintenant: complète (coche ET décoche selon sélection QGIS)
  - **Widgets → QGIS**: Inchangé (déjà fonctionnel)
  - **Protection anti-boucles infinies**: Nouveau flag `_syncing_from_qgis`
    - Empêche récursions lors de synchronisation bidirectionnelle
    - Garantit stabilité même avec sélections rapides multiples

### 🔧 Améliorations UX

- **Synchronisation bidirectionnelle**: Canvas et widgets parfaitement cohérents quand is_selecting activé
- **Workflow simplifié**: Sélectionner dans canvas → voir dans widget → filtrer/exporter
- **Logging amélioré**: Messages clairs pour identifier synchronisation
- **Performance optimisée**: Vérifications pour éviter mises à jour inutiles

### 📝 Changements de Comportement

- **Mode Multiple Selection**: Passage de synchronisation ADDITIVE à COMPLÈTE
  - Avant: ajoutait les features (cochait) mais ne les supprimait jamais
  - Maintenant: reflète EXACTEMENT la sélection QGIS (coche ET décoche)
- **Bouton is_selecting**: Rôle clarifié
  - Active la synchronisation bidirectionnelle complète
  - Widgets ↔ QGIS : synchronisation dans les deux sens

### 🐛 Corrections de Bugs

- **Protection contre boucles infinies**: Flag `_syncing_from_qgis` empêche récursions
- **Gestion d'état robuste**: Vérifications systématiques widgets_initialized et couches valides
- **Updates intelligentes**: Évite mises à jour inutiles via comparaison feature.id()

### 📊 Fichiers Modifiés

- `filter_mate_dockwidget.py`:
  - Ajout flag `_syncing_from_qgis` dans `__init__`
  - Modification `on_layer_selection_changed()` - vérification is_selecting
  - Amélioration `_sync_widgets_from_qgis_selection()` - documentation
  - Update `_sync_single_selection_from_qgis()` - vérifications optimisées
  - Refonte `_sync_multiple_selection_from_qgis()` - sync complète
  - Protection `exploring_features_changed()` - anti-boucles

### 📚 Documentation

- Ajout `docs/RELEASE_NOTES_v2.5.6.md` - Documentation complète de la fonctionnalité
- Schéma d'architecture de synchronisation
- Tests recommandés et cas d'usage
- Guide de migration depuis v2.5.5

---

## [2.5.5] - 2025-12-29 - CRITICAL FIX: PostgreSQL Negative Buffer Empty Geometry Detection

### 🐛 Bug Fixes

- **CRITICAL FIX: PostgreSQL backend incorrectly detected empty geometries from negative buffers**
  - **Symptôme**: Buffer négatif (érosion) sur PostgreSQL pouvait filtrer incorrectement les features
  - **Cause**: `NULLIF(geom, 'GEOMETRYCOLLECTION EMPTY'::geometry)` ne détectait que ce type exact
    - Ne détectait PAS `POLYGON EMPTY`, `MULTIPOLYGON EMPTY`, `LINESTRING EMPTY`, etc.
    - Buffer négatif produit différents types de géométries vides selon la géométrie source
    - Résultat : géométries vides non-NULL passaient dans les prédicats spatiaux → résultats incorrects
  - **Solution**:
    - Remplacement de `NULLIF(...)` par `CASE WHEN ST_IsEmpty(...) THEN NULL ELSE ... END`
    - `ST_IsEmpty()` détecte TOUS les types de géométries vides (PostGIS standard)
    - Application dans 3 fonctions : `_build_st_buffer_with_style()`, `_build_simple_wkt_expression()`, `build_expression()` (chemin EXISTS)
    - Garantit que toute géométrie vide devient NULL → ne matche aucun prédicat spatial

### 📊 Impact

- **Fichier modifié**: `modules/backends/postgresql_backend.py`
- **Fonctions affectées**:
  - `_build_st_buffer_with_style()` (ligne ~180-195)
  - `_build_simple_wkt_expression()` (ligne ~630-650)
  - `build_expression()` - chemin EXISTS (ligne ~870-895)
- **Compatibilité**: PostGIS 2.0+ (ST_IsEmpty disponible)
- **Régression**: Aucune - les résultats sont maintenant CORRECTS

### 🔧 Détails techniques

**Avant:**

```sql
-- ❌ Ne détecte que GEOMETRYCOLLECTION EMPTY
NULLIF(ST_MakeValid(ST_Buffer(geom, -50)), 'GEOMETRYCOLLECTION EMPTY'::geometry)
-- Problème : POLYGON EMPTY, MULTIPOLYGON EMPTY → non-NULL → match incorrects
```

**Après:**

```sql
-- ✅ Détecte TOUS les types de géométries vides
CASE WHEN ST_IsEmpty(ST_MakeValid(ST_Buffer(geom, -50)))
     THEN NULL
     ELSE ST_MakeValid(ST_Buffer(geom, -50))
END
-- Solution : Toute géométrie vide → NULL → aucun match
```

---

## [2.5.4] - 2025-12-29 - CRITICAL FIX: OGR Backend Memory Layer Feature Count

### 🐛 Bug Fixes

- **CRITICAL FIX: OGR backend falsely reported 0 features in memory layers**
  - **Symptôme**: Tous les filtres OGR échouaient systématiquement avec "backend returned FAILURE"
  - **Logs observés**: "Source layer has no features" même quand les logs montraient 1 feature
  - **Cause**: `featureCount()` retourne 0 immédiatement après création de memory layer
    - Pour les memory layers, le count n'est pas actualisé instantanément
    - Le backend OGR vérifiait `source_layer.featureCount() == 0` avant l'actualisation
  - **Solution**:
    - Détection automatique des memory layers via `providerType() == 'memory'`
    - Force `updateExtents()` avant comptage
    - Comptage intelligent par itération pour memory layers (plus fiable)
    - Fallback sur `featureCount()` pour autres providers
    - Log de diagnostic si mismatch entre `featureCount()` et comptage réel

### 📊 Diagnostics améliorés

- **Logs de validation memory layer**:
  - Affiche provider type (memory, postgres, ogr, etc.)
  - Compare `featureCount()` vs comptage par itération
  - Avertissement si mismatch détecté
  - Détails complets pour debugging

### 🔧 Impact technique

- **Fichier modifié**: `modules/backends/ogr_backend.py` (lignes 473-499)
- **Fonction affectée**: `_apply_buffer()`
- **Compatibilité**: Toutes versions QGIS 3.x
- **Régression**: Aucune - amélioration pure

---

## [2.5.3] - 2025-12-29 - Amélioration Gestion Buffers Négatifs

### 🐛 Bug Fixes

- **FIXED: Problème de filtrage avec buffer négatif sur couches polygones**
  - **Symptôme**: Buffer négatif (érosion) pouvait échouer silencieusement quand il érodait complètement les géométries
  - **Cause**: Pas de distinction entre "échec d'opération" et "érosion complète" (géométrie vide légitime)
  - **Solution**:
    - Tracking séparé des features complètement érodées dans `_buffer_all_features()`
    - Message utilisateur clair via barre de message QGIS quand toutes les features sont érodées
    - Logs détaillés pour diagnostiquer le problème (erosion vs invalid)
    - Documentation améliorée dans `safe_buffer()` pour expliquer le comportement

### 📊 Améliorations

- **Logs enrichis pour buffers négatifs**:

  - Détection automatique des buffers négatifs
  - Compte des features érodées vs invalides
  - Avertissement si toutes les features disparaissent
  - Suggestion d'action: "Réduisez la distance du buffer"

- **Messages utilisateur**:
  - `iface.messageBar().pushWarning()` avec message explicite
  - Format: "Le buffer négatif de -Xm a complètement érodé toutes les géométries"
  - Guidance claire pour résoudre le problème

### 🧪 Tests

- Nouveau fichier: `tests/test_negative_buffer.py`
- Tests pour érosion complète, partielle, et buffers positifs
- Documentation complète: `docs/FIX_NEGATIVE_BUFFER_2025-12.md`

### 📝 Fichiers Modifiés

- `modules/geometry_safety.py`: Amélioration `safe_buffer()` avec logs négatifs
- `modules/tasks/filter_task.py`: Amélioration `_buffer_all_features()` avec tracking érosion
- `tests/test_negative_buffer.py`: Tests unitaires (nouveau)
- `docs/FIX_NEGATIVE_BUFFER_2025-12.md`: Documentation technique (nouveau)

---

## [2.5.2] - 2025-12-29 - CRITICAL FIX: Negative Buffer for All Backends

### 🐛 Critical Bug Fixes

- **FIXED: Negative buffer not working for OGR, Spatialite, and fallback backends**
  - **Root Cause**: OGR backend was ignoring `buffer_value` parameter in `build_expression()`
  - **Root Cause**: `prepare_ogr_source_geom()` was skipping buffer application when `spatialite_source_geom` existed
  - **Impact**: Negative buffers (erosion) were only working for PostgreSQL direct connections
  - **Solution**:
    - OGR `build_expression()` now correctly passes `buffer_value` to `apply_filter()`
    - OGR `apply_filter()` applies buffer via `_apply_buffer()` with full negative value support
    - Removed incorrect buffer skip logic in `prepare_ogr_source_geom()`
    - Buffer is now applied in the correct place for each backend:
      - PostgreSQL: ST_Buffer() in SQL (backend)
      - Spatialite: ST_Buffer() in SQL (backend)
      - OGR: native:buffer in apply_filter (Processing)

### 📊 Testing

- Added comprehensive logging for buffer value tracing through backend pipeline
- Logs show buffer values at each step: filter_task → backend.build_expression → apply_filter

### 🔍 Debugging Improvements

- Enhanced logging in `build_expression()` (all backends) to trace buffer parameters
- Added logging in `_build_simple_wkt_expression()` to confirm buffer application
- Added logging in `_apply_filter_standard()` to confirm buffer passed to `_apply_buffer()`

---

## [2.5.1] - 2025-12-29 - Negative Buffer Support

### ✨ New Features

- **Negative Buffer (Erosion)**: Support for negative buffer values across all three backends
  - PostgreSQL: Native ST_Buffer() with negative distance
  - Spatialite: Native ST_Buffer() with negative distance
  - OGR: QGIS Processing native:buffer with negative distance
  - Shrinks polygons inward instead of expanding outward
  - Visual feedback: Orange/yellow styling when negative buffer is active

### 🎨 UI Improvements

- Buffer spinbox now accepts values from -1,000,000 to +1,000,000 meters
- Updated tooltips explaining positive (expand) vs negative (shrink) buffers
- Dynamic styling on buffer spinbox when negative value entered
- Clear visual indication of erosion mode

### 📝 Documentation

- Updated docstrings for buffer-related methods
- Added notes about negative buffer limitations (polygon geometries only)

---

## [2.5.0] - 2025-12-29 - Major Stability Release

### 🎉 Major Milestone

This release consolidates all stability fixes from the 2.4.x series into a stable, production-ready version.

### ✨ Highlights

| Category              | Improvement                                                  |
| --------------------- | ------------------------------------------------------------ |
| **GeoPackage**        | Correct GeomFromGPB() function for GPB geometry conversion   |
| **Thread Safety**     | Defer setSubsetString() to main thread via queue callback    |
| **Session Isolation** | Multi-client materialized view naming with session_id prefix |
| **Type Casting**      | Automatic ::numeric casting for varchar/numeric comparisons  |
| **Remote Layers**     | Proper detection and fallback to OGR for WFS/HTTP services   |
| **Source Geometry**   | Thread-safe feature validation with expression fallback      |

### 🛡️ Stability Improvements

- **GeoPackage GeomFromGPB()**: Use correct SpatiaLite function (without ST\_ prefix)
- **GPB Geometry Conversion**: Proper GeoPackage Binary format handling
- **Spatialite Thread-Safety**: task_parameters priority for source geometry
- **Remote Layer Detection**: Prevents Spatialite from opening HTTP/WFS sources
- **PostgreSQL Thread Safety**: Queue-based subset string updates
- **Session View Naming**: Unique session_id prefix prevents multi-client conflicts

### 🔧 Bug Fixes

- Fixed SQL syntax errors with GeoPackage layers (ST_GeomFromGPB → GeomFromGPB)
- Fixed spatial predicates returning ALL features for GeoPackage
- Fixed source geometry selection in background threads
- Fixed remote layer detection (WFS, HTTP services)
- Fixed type casting for varchar/numeric field comparisons
- Fixed filter sanitization for non-boolean display expressions

### 📁 Files Modified

- `modules/backends/spatialite_backend.py`: GeomFromGPB(), remote detection
- `modules/backends/postgresql_backend.py`: Session isolation, connection validation
- `modules/tasks/filter_task.py`: Thread-safe geometry, type casting
- `filter_mate_app.py`: Thread-safe subset handling

---

## [2.4.13] - 2025-12-29 - GeoPackage GeomFromGPB() Function Fix

### 🐛 Critical Bug Fix

#### Wrong Function Name: ST_GeomFromGPB() Does Not Exist

- **Root Cause**: Used `ST_GeomFromGPB()` but the correct SpatiaLite function is `GeomFromGPB()` (without ST\_ prefix)
- **Symptom**: All GeoPackage layers returned FAILURE because SQL query contained undefined function
- **Evidence**: Logs showed `execute_geometric_filtering ✗ structures → backend returned FAILURE`
- **Solution**: Use `GeomFromGPB("geom")` instead of `ST_GeomFromGPB("geom")`

### 🔧 Technical Details

**Before (broken - v2.4.12):**

```sql
ST_Intersects(ST_GeomFromGPB("geom"), GeomFromText('MultiPolygon...', 31370))
```

**After (fixed - v2.4.13):**

```sql
ST_Intersects(GeomFromGPB("geom"), GeomFromText('MultiPolygon...', 31370))
```

### 📚 SpatiaLite Documentation Reference

From SpatiaLite 5.0 SQL Reference:

- `GeomFromGPB(geom GPKG Blob Geometry) : BLOB encoded geometry`
- Converts a GeoPackage format geometry blob into a SpatiaLite geometry blob
- Alternative: `CastAutomagic()` can auto-detect GPB or standard WKB

### 📁 Files Modified

- `modules/backends/spatialite_backend.py`: Changed `ST_GeomFromGPB()` to `GeomFromGPB()` in `build_expression()`

---

## [2.4.12] - 2025-12-29 - GeoPackage GPB Geometry Conversion Fix

### 🐛 Critical Bug Fix

#### GeoPackage Spatial Predicates Returning ALL Features

- **Root Cause**: GeoPackage stores geometries in GPB (GeoPackage Binary) format, NOT standard WKB
- **Symptom**: `ST_Intersects("geom", GeomFromText(...))` returned TRUE for ALL features
- **Evidence**: Logs showed `→ Direct SQL found 9307 matching FIDs` (entire layer) instead of ~50
- **Solution**: Use `ST_GeomFromGPB("geom")` to convert GPB to Spatialite geometry before spatial predicates

### 🔧 Technical Details

**Before (broken):**

```sql
ST_Intersects("geom", GeomFromText('MultiPolygon...', 31370))
```

**After (fixed):**

```sql
ST_Intersects(ST_GeomFromGPB("geom"), GeomFromText('MultiPolygon...', 31370))
```

### 📁 Files Modified

- `modules/backends/spatialite_backend.py`: Added GeoPackage detection and ST_GeomFromGPB() conversion in `build_expression()`

---

## [2.4.11] - 2025-12-29 - Spatialite Thread-Safety Fix for Source Geometry

### 🐛 Critical Bug Fix

#### Spatialite prepare_spatialite_source_geom() NOT Using task_parameters Priority

- **Root Cause**: `prepare_spatialite_source_geom()` was checking `has_subset` first, but in background threads, `subsetString()` returns empty even when layer is filtered. Meanwhile, `prepare_ogr_source_geom()` was correctly using `task_parameters["task"]["features"]` as PRIORITY.
- **Symptom**: OGR logs show correct 1 feature, but Spatialite backend receives geometry from ALL source features
- **Analysis**:
  1. v2.4.10 fixed `prepare_ogr_source_geom()` to use task_features FIRST
  2. But `prepare_spatialite_source_geom()` still used old logic: has_subset → getFeatures()
  3. In background threads, getFeatures() returns ALL features if subset isn't visible
- **Solution (v2.4.11)**:
  1. `prepare_spatialite_source_geom()` now uses same logic as OGR version
  2. task_parameters["task"]["features"] is checked FIRST (priority mode)
  3. Feature validation with try/except for thread-safety
  4. Consistent logging format with OGR version

### 🔧 Improvements

- **Priority Order**: Both OGR and Spatialite now use: task_features > has_subset > has_selection > field_mode > fallback
- **Better Diagnostics**: `has_task_features` logged with count for easier debugging
- **Simplified else block**: Removed redundant code in else branch

### 📁 Files Modified

- `modules/tasks/filter_task.py`:
  - Refactored `prepare_spatialite_source_geom()` to use task_features priority mode (~line 2352)
  - Added feature validation with try/except like OGR version
  - Simplified fallback mode

---

## [2.4.10] - 2025-12-29 - Source Geometry Thread Safety Fix

### 🐛 Critical Bug Fix

#### Geometric Filter Selecting ALL Features Instead of Intersecting Subset

- **Root Cause**: When filtering remote/distant layers with a filtered source layer (e.g., zone_distribution with 1 feature), the spatial predicate was returning ALL features instead of only intersecting ones
- **Symptom**: Filter generates `'fid' IN (1, 2, 3, ..., 9307)` selecting all features instead of expected subset
- **Analysis**:
  1. `task_features` passed from main thread to background task could become invalid (thread-safety)
  2. `setSubsetString()` from background thread may not take effect immediately
  3. Without valid task_features or visible subset, code falls into "DIRECT MODE" using ALL source features
- **Solution (v2.4.22)**:
  1. More robust validation of task features with exception handling for thread-safety issues
  2. Expression fallback mode: if no subset detected but `self.expression` exists, use it to filter features
  3. Applied fix to both `prepare_ogr_source_geom()` and `prepare_spatialite_source_geom()`

### 🔧 Improvements

- **Better Diagnostics**: Added detailed logging for feature validation failures
- **Expression Fallback**: New "EXPRESSION FALLBACK MODE" uses stored expression when subset detection fails
- **Thread Safety Warnings**: Explicit logging when features become invalid due to thread issues

### 📁 Files Modified

- `modules/tasks/filter_task.py`:
  - Enhanced feature validation in `prepare_ogr_source_geom()` (~line 3693)
  - Added expression fallback in `prepare_ogr_source_geom()` (~line 3814)
  - Added expression fallback in `prepare_spatialite_source_geom()` (~line 2392)

---

## [2.4.9] - 2025-12-29 - Remote Layer Detection Fix

### 🐛 Critical Bug Fix

#### Remote/Distant Layers Incorrectly Handled by Spatialite Backend

- **Root Cause**: Spatialite backend was attempting to open remote layers (WFS, HTTP services) as local SQLite files
- **Symptom**: "unable to open database file" errors during filtering, `-1 features visible` result
- **Solution**: Added detection for remote sources BEFORE attempting Spatialite operations:
  1. Check for remote URL prefixes (http://, https://, ftp://, wfs:, wms:, /vsicurl/)
  2. Check for service markers in source string (url=, service=, typename=)
  3. Verify file existence before SQLite connection attempts
- **Result**: Remote layers now properly fall back to OGR backend (QGIS processing)

### 🔧 Improvements

- **Cache Version Bump**: Force cache invalidation to ensure new detection logic is applied
- **Better Logging**: Added diagnostic logging for remote source detection

### 📁 Files Modified

- `modules/backends/spatialite_backend.py`: Remote layer detection in `supports_layer()` and `_apply_filter_direct_sql()`

---

## [2.4.8] - 2025-12-29 - PostgreSQL Thread Safety & Session Isolation

### 🛡️ Thread Safety Improvements

- **Defer setSubsetString() to Main Thread**: PostgreSQL subset string updates now use queue callback to ensure thread safety
- **Session Isolation**: Multi-client materialized view naming with session_id prefix prevents conflicts
- **Connection Validation**: Proper validation of ACTIVE_POSTGRESQL connection objects before use

### 🔧 Bug Fixes

#### PostgreSQL Type Casting

- **Root Cause**: varchar/numeric comparison errors when filtering numeric fields stored as text
- **Solution**: Automatic ::numeric casting for comparison operations
- **Files**: `filter_task.py`, `postgresql_backend.py`

#### Full SELECT Statement for Materialized Views

- **Root Cause**: `manage_layer_subset_strings` expected complete SQL SELECT but received only WHERE clause
- **Symptom**: Syntax errors like `CREATE MATERIALIZED VIEW ... AS WITH DATA;`
- **Solution**: Build full SELECT statement from layer properties (schema, table, primary_key, geom_field)
- **File**: `modules/tasks/filter_task.py`

### 🧹 Filter Sanitization

- **Remove Non-Boolean Display Expressions**: Filter sanitization removes display expressions without comparison operators
- **Corrupted Filter Cleanup**: Clear filters with `__source` alias or unbalanced parentheses
- **Expression Validation**: Reject display expressions that would cause SQL errors

### 🔧 New Features

- **PostgreSQL Maintenance Menu**: New UI for session view cleanup and schema management
- **Schema Detection**: Re-validate layer_schema from layer source for PostgreSQL connections

### 📁 Files Modified

- `filter_mate_app.py`: Thread-safe subset string handling, PostgreSQL maintenance menu
- `filter_mate_dockwidget.py`: PostgreSQL maintenance UI integration
- `modules/tasks/filter_task.py`: Full SELECT statement builder, type casting
- `modules/backends/postgresql_backend.py`: Session isolation, connection validation
- `modules/backends/spatialite_backend.py`: Enhanced thread safety
- `modules/appUtils.py`: Connection validation utilities
- `tests/test_postgresql_buffer.py`: New test suite for PostgreSQL buffer handling

---

## [2.4.7] - 2025-12-24 - GeoPackage Geometry Detection & Stability Fix

### 🔧 Bug Fixes

#### Improved Geometry Column Detection for GeoPackage/Spatialite

- **Root Cause**: Geometry column detection was failing for some GeoPackage layers, causing spatial filters to fail
- **Solution**: Multi-method detection approach:
  1. `layer.geometryColumn()` - Most reliable, used first
  2. `dataProvider().geometryColumn()` - Fallback
  3. `gpkg_geometry_columns` table query - Last resort for .gpkg files
- **Files**: `spatialite_backend.py`, `layer_management_task.py`

#### Safe Layer Variable Operations (v2.4.14)

- **Issue**: Access violations during layer change when `setLayerVariable()` called concurrently
- **Fix**: Use `safe_set_layer_variable()` wrapper that:
  - Re-fetches layer from project registry immediately before operation
  - Checks sip deletion status multiple times
  - Defers operation if layer change is in progress (`_updating_current_layer` flag)
- **File**: `filter_mate_app.py`

### 🛡️ Stability Improvements

- **Spatialite Cache**: Only cache POSITIVE support test results by file

  - Prevents false negatives when one layer in a file fails but others work
  - Each layer still tested individually if file cache is empty

- **Non-Spatial Layers**: Layers without geometry now supported in attribute-only mode
  - Detected via `layer.geometryType() == NullGeometry`
  - Returns `True` for Spatialite support (attribute filtering works)

### 📝 Better Diagnostics

- Enhanced failure diagnostics for spatial filter issues:
  - Tests geometry column access separately from spatial functions
  - Tests `GeomFromText()` availability
  - Tests `ST_Intersects()` function
  - Provides actionable error messages for troubleshooting

### 📁 Files Modified

- `filter_mate_app.py`: Safe layer variable wrapper, deferred operation during layer change
- `modules/backends/spatialite_backend.py`: Multi-method geometry detection, improved caching
- `modules/tasks/layer_management_task.py`: GeoPackage metadata query for geometry column

---

## [2.4.11] - 2025-12-24 - Multi-Thread & Qt Event Loop Access Violation Fixes

### 🔥 Critical Bug Fixes

#### Bug Fix 1: Multi-Thread Feature Iteration Race Condition

- **Root Cause**: Multiple background threads (`PopulateListEngineTask`) iterating over layer features while main thread calls `setLayerVariable()` during UI state restoration
- **Symptom**: "Windows fatal exception: access violation" at `layer_features_source.getFeatures()` (line 493 in widgets.py)
- **Trigger**: Layer change causes UI groupbox collapse/expand which triggers deferred layer variable saves

#### Bug Fix 2: Qt Event Loop Deferred Operation Crash (NEW)

- **Root Cause**: `setCollapsed()` triggers Qt event processing (`sendPostedEvents`) which executes deferred `save_variables_from_layer` operations during `_restore_groupbox_ui_state`
- **Symptom**: "Windows fatal exception: access violation" at `QgsExpressionContextUtils.setLayerVariable()` during layer change
- **Trigger**: Single-thread crash where `QTimer.singleShot(0, ...)` deferred operation runs inside Qt event processing
- **Stack Trace Path**:
  1. `current_layer_changed` → `_reconnect_layer_signals` → `_restore_groupbox_ui_state`
  2. `setCollapsed(False)` → Qt `sendPostedEvents` → deferred `save_variables_from_layer`
  3. `_save_single_property` → `setLayerVariable` → **CRASH**

### 🛡️ Multi-Thread Protection (v2.4.11)

#### 1. Task Cancellation Checks During Feature Iteration ([widgets.py](modules/widgets.py))

Added `isCanceled()` checks in all feature iteration loops in `buildFeaturesList()` and `loadFeaturesList()`:

```python
for index, feature in enumerate(layer_features_source.getFeatures(filter_expression_request)):
    # CRASH FIX (v2.3.20): Check for task cancellation to prevent access violation
    if self.isCanceled():
        logger.debug(f"buildFeaturesList: Task cancelled during iteration for layer '{self.layer.name()}'")
        return
    # ... process feature
```

#### 2. Layer-Specific Task Cancellation Before Variable Updates ([filter_mate_app.py](filter_mate_app.py))

New method `_cancel_layer_tasks(layer_id)` cancels running feature iteration tasks for a specific layer before modifying its variables.

#### 3. Skip QGIS Variable Updates During Layer Change

Added check for `_updating_current_layer` flag to skip `setLayerVariable()` calls during layer change (database save still proceeds):

```python
# CRASH FIX (v2.4.11): Check if dockwidget is in the middle of a layer change
skip_qgis_variable = False
if hasattr(self, 'dockwidget') and self.dockwidget is not None:
    if getattr(self.dockwidget, '_updating_current_layer', False):
        logger.debug(f"_save_single_property: layer change in progress, deferring QGIS variable")
        skip_qgis_variable = True
```

### 📝 Files Modified

- `modules/widgets.py`: Added `isCanceled()` checks in 10+ feature iteration loops
- `filter_mate_app.py`: Added `_cancel_layer_tasks()` method, layer change detection, and skip logic

---

## [2.4.10] - 2025-12-23 - Backend Change Access Violation Fix

### 🔥 Critical Bug Fix

#### Windows Fatal Exception: Access Violation during Backend Change to Spatialite

- **Root Cause**: `setLayerVariableEvent()` signal emission during widget synchronization when layer's C++ object becomes invalid
- **Symptom**: "Windows fatal exception: access violation" at `QgsExpressionContextUtils.setLayerVariable()` when forcing backend change to Spatialite
- **Stack Trace Path**:
  1. `_synchronize_layer_widgets` calls `setExpression()` on QgsFieldExpressionWidget
  2. Despite `blockSignals(True)`, `fieldChanged` signal cascades through Qt event queue
  3. `on_single_field_changed` → `layer_property_changed` → `setLayerVariableEvent`
  4. Layer becomes invalid during signal cascade → **CRASH**

### 🛡️ Multi-Layer Protection (v2.4.10)

#### 1. Robust Layer Validation in `_save_single_property()` ([filter_mate_app.py](filter_mate_app.py#L2890))

Replaced basic null check with comprehensive `is_valid_layer()` validation:

```python
# OLD - Insufficient check
if layer is None or not hasattr(layer, 'id') or not layer.id():
    return

# NEW - Full C++ object validation
if not is_valid_layer(layer):
    logger.debug(f"_save_single_property: layer is invalid or deleted, skipping")
    return
```

Also wrapped `setLayerVariable()` in try/except to catch `RuntimeError/OSError/SystemError`.

#### 2. Pre-emit Validation in `setLayerVariableEvent()` ([filter_mate_dockwidget.py](filter_mate_dockwidget.py#L8376))

Added `is_valid_layer()` check before emitting signal:

```python
# CRASH FIX: Validate before signal emission
if not is_valid_layer(layer):
    logger.debug("setLayerVariableEvent: layer is invalid, skipping emit")
    return
self.settingLayerVariable.emit(layer, properties)
```

#### 3. Entry Point Validation in `save_variables_from_layer()` ([filter_mate_app.py](filter_mate_app.py#L2940))

Replaced `isinstance()` check with `is_valid_layer()` for full C++ deletion detection.

### 📝 Files Modified

- `filter_mate_app.py`: Enhanced `_save_single_property()` and `save_variables_from_layer()`
- `filter_mate_dockwidget.py`: Added `is_valid_layer` import and validation in `setLayerVariableEvent()`

---

## [2.4.9] - 2025-12-23 - Definitive Layer Variable Access Violation Fix

### 🔥 Critical Bug Fix

#### Windows Fatal Exception: Access Violation in setLayerVariable

- **Root Cause**: Race condition between layer validation and C++ call persisted despite processEvents() flush
- **Symptom**: "Windows fatal exception: access violation" at `QgsExpressionContextUtils::setLayerVariable` during task completion
- **Key Insight**: On Windows, C++ access violations are **FATAL** and cannot be caught by Python's try/except

### 🛡️ Two-Pronged Fix Strategy (v2.4.9)

#### 1. QTimer.singleShot(0) Deferral ([layer_management_task.py](modules/tasks/layer_management_task.py))

Replaced immediate layer variable operations with QTimer.singleShot(0) scheduling:

- **Why it works**: `QTimer.singleShot(0)` schedules the callback for the next complete event loop iteration
- **Effect**: All pending layer deletion events are fully processed before we touch any layers
- **Contrast with processEvents()**: `processEvents()` only processes currently pending events, but new deletion events can arrive immediately after

```python
# OLD (v2.4.8) - Still had race condition
app.processEvents()  # Flush events
# Layer could still be deleted HERE before next line
safe_set_layer_variable(layer_id, key, value)  # CRASH

# NEW (v2.4.9) - Complete event loop separation
def apply_deferred():
    # Runs in completely new event loop iteration
    safe_set_layer_variable(layer_id, key, value)
QTimer.singleShot(0, apply_deferred)  # Schedule for later
```

#### 2. Direct setCustomProperty() Call ([object_safety.py](modules/object_safety.py))

Replaced `QgsExpressionContextUtils.setLayerVariable()` with direct `setCustomProperty()` calls:

- **Why it helps**: Wraps the actual C++ call in try/except that CAN catch RuntimeError
- **Layer variable format**: QGIS stores layer variables as `variableValues/<name>` custom properties
- **Additional benefit**: More granular error handling per-variable

### 📝 Technical Details

The fix provides defense-in-depth:

1. **Layer 1** (task level): `QTimer.singleShot(0)` defers operations to next event loop
2. **Layer 2** (callback level): `is_qgis_alive()` check before and during loop
3. **Layer 3** (function level): Fresh layer lookup + sip deletion check
4. **Layer 4** (operation level): Try/except around direct `setCustomProperty()` call

### 🔧 Files Modified

- [modules/tasks/layer_management_task.py](modules/tasks/layer_management_task.py) - QTimer.singleShot(0) deferral pattern
- [modules/object_safety.py](modules/object_safety.py) - Direct setCustomProperty() with try/except

---

## [2.4.7] - 2025-12-23 - Layer Variable Race Condition Fix

### 🔥 Critical Bug Fix

#### Persistent Access Violation in setLayerVariable ([object_safety.py](modules/object_safety.py#L451))

- **Root Cause**: Despite existing safety checks, a race condition persisted between `sip.isdeleted()` validation and the actual `QgsExpressionContextUtils.setLayerVariable()` C++ call
- **Symptom**: "Windows fatal exception: access violation" at `QgsExpressionContextUtils::setLayerVariable` during task completion
- **Stack trace**: Final sip check passes → layer deleted in another thread → C++ call dereferences deleted object → access violation

### 🛡️ Enhanced Race Condition Protection (v2.4.7)

Added `QApplication.processEvents()` flush before critical C++ operations:

1. **Event Queue Flushing**

   - Calls `QApplication.processEvents()` immediately before layer variable operations
   - Allows any pending layer deletion events to complete before accessing the layer
   - Significantly reduces the race condition window

2. **Post-Flush Re-validation**

   - After processing events, re-checks `sip.isdeleted()` status
   - Re-fetches layer from project registry to ensure it's still valid
   - Only proceeds if layer passes all checks after event flush

3. **Windows-Specific Protection**
   - Uses `platform.system()` to detect Windows where access violations are fatal
   - Applies stricter validation on Windows since these crashes cannot be caught

### 📝 Technical Details

The fix adds a two-phase approach:

1. **In `finished()` method**: Process events BEFORE iterating through deferred layer variables
2. **In safe wrapper functions**: Process events BEFORE each individual C++ call

This multi-layer approach ensures that even if a layer is deleted between the start of the loop and the individual operation, the crash will be prevented.

### 🔧 Files Modified

- [modules/object_safety.py](modules/object_safety.py) - Added event flush and re-validation in `safe_set_layer_variable()` and `safe_set_layer_variables()`
- [modules/tasks/layer_management_task.py](modules/tasks/layer_management_task.py) - Added event flush before layer variable loop

---

## [2.4.6] - 2025-12-23 - Layer Variable Access Violation Crash Fix

### 🔥 Critical Bug Fix

#### Access Violation in setLayerVariable ([layer_management_task.py](modules/tasks/layer_management_task.py#L1618))

- **Root Cause**: Race condition between layer validation and `QgsExpressionContextUtils.setLayerVariable()` C++ call in task `finished()` method
- **Symptom**: "Windows fatal exception: access violation" at `QgsExpressionContextUtils::setLayerVariable` during task completion
- **Stack trace**: Task finishes → applies deferred layer variables → layer deleted between validation and C++ call → access violation

### 🛡️ Safe Layer Variable Wrappers (v2.3.12)

Added new safe wrapper functions in [object_safety.py](modules/object_safety.py):

1. **`safe_set_layer_variable(layer_id, variable_key, value)`**

   - Re-fetches layer fresh from project registry immediately before operation
   - Validates sip deletion status and layer validity right before C++ call
   - Minimizes race condition window between validation and access
   - Returns `False` gracefully instead of crashing

2. **`safe_set_layer_variables(layer_id, variables)`**
   - Same pattern for setting/clearing multiple variables
   - Used when clearing all layer variables with empty dict

### 📝 Technical Details

The crash sequence was:

1. `LayersManagementEngineTask.run()` queues deferred layer variable operations
2. Task completes, `finished()` runs in main thread
3. Multiple validation checks pass (layer exists, sip not deleted, layer valid)
4. Between final validation and `setLayerVariable()` call, layer gets deleted
5. C++ function dereferences invalid pointer → access violation

The fix:

- Moves validation into dedicated safe wrapper functions
- Re-fetches layer from project registry at the last moment
- Performs sip deletion check immediately before C++ operation
- Wraps everything in try-except to catch any RuntimeError

### 🔧 Files Modified

- [modules/object_safety.py](modules/object_safety.py) - Added `safe_set_layer_variable()` and `safe_set_layer_variables()` functions
- [modules/tasks/layer_management_task.py](modules/tasks/layer_management_task.py) - Use safe wrappers instead of direct calls

---

## [2.4.5] - 2025-12-23 - Processing Parameter Validation Crash Fix

### 🔥 Critical Bug Fix

#### Access Violation in checkParameterValues ([ogr_backend.py](modules/backends/ogr_backend.py))

- **Root Cause**: QGIS Processing `checkParameterValues()` accesses layer data at C++ level during parameter validation, which can crash on corrupted/invalid layers before the algorithm even runs
- **Symptom**: "Windows fatal exception: access violation" at `QgsProcessingAlgorithm::checkParameterValues` during geometric filtering
- **Stack trace**: `processing.run("native:selectbylocation")` → `checkParameterValues()` → crash in GEOS/PDAL

### 🛡️ Pre-flight Layer Validation (v2.3.9.3)

Added three-tier validation to catch crashes before calling `processing.run()`:

1. **`_validate_input_layer()`**: Deep provider access validation

   - Tests `layer.id()`, `layer.crs()`, `layer.wkbType()`, `layer.geometryType()`
   - Validates data provider exists and responds
   - Tests `provider.wkbType()`, `provider.featureCount()`, `provider.extent()`

2. **`_validate_intersect_layer()`**: Same deep validation plus geometry checks

   - All validations from input layer
   - Feature iteration test with try-except
   - Geometry validity sampling

3. **`_preflight_layer_check()`**: Final check before `processing.run()`
   - Tests exact operations that `checkParameterValues` performs
   - Validates `layer.source()`, `provider.dataSourceUri()`, `provider.capabilities()`
   - Tests extent access and feature iterator creation
   - Catches `RuntimeError`, `OSError`, `AttributeError` before C++ crash

### 📝 Technical Details

The crash sequence was:

1. `processing.run("native:selectbylocation", ...)` called
2. QGIS Processing calls `alg.checkParameterValues(parameters, context)`
3. `checkParameterValues` accesses layer properties at C++ level
4. Invalid layer state causes GEOS/PDAL memory access violation
5. Python cannot catch C++ level crashes

The fix ensures all C++ level accesses are tested in Python first, where exceptions can be caught and handled gracefully.

### 🔧 Files Modified

- `modules/backends/ogr_backend.py` - Added pre-flight validation

---

## [2.4.4] - 2025-12-23 - Critical Thread Safety Fix

### 🔥 Critical Bug Fix

#### Parallel Filtering Access Violation Crash

- **Root Cause**: Multiple worker threads simultaneously accessed QGIS layer objects (`QgsVectorLayer`) which are NOT thread-safe
- **Symptom**: "Windows fatal exception: access violation" when filtering multiple OGR layers
- **Fix**: OGR layers and geometric filtering now always use sequential execution

### 🛡️ Thread Safety Improvements

#### ParallelFilterExecutor Enhanced ([parallel_executor.py](modules/tasks/parallel_executor.py))

- **Auto-detection**: Automatically detects OGR layers and forces sequential execution
- **Geometric filtering safety**: Detects `filter_type: geometric` and uses sequential mode
- **Parallel only for database backends**: PostgreSQL/Spatialite can still run in parallel (database connections are per-thread)
- **Improved logging**: Clear messages about why sequential/parallel mode is chosen

#### OGR Backend Thread Detection ([ogr_backend.py](modules/backends/ogr_backend.py))

- **Thread tracking**: Added `_ogr_operations_lock` and `_last_operation_thread` tracking
- **Concurrent access warning**: Logs warning if `apply_filter()` called from different threads
- **Defense in depth**: Provides safety even if parallel execution is somehow triggered

### 📝 Technical Details

QGIS `QgsVectorLayer` objects use non-reentrant C++ code and Qt signals that crash when accessed concurrently:

- `layer.selectedFeatures()` - Iterates internal data structures
- `layer.startEditing()` / `layer.commitChanges()` - Modifies layer state
- `layer.getFeatures()` - Creates iterators over internal data
- `dataProvider.addFeatures()` - Writes to underlying data source

### 🔧 Files Modified

- `modules/tasks/parallel_executor.py` - Core thread safety fix
- `modules/tasks/filter_task.py` - Pass filtering params for detection
- `modules/backends/ogr_backend.py` - Thread detection and warnings

---

## [2.4.3] - 2025-12-22 - Export System Fix & Message Bar Improvements

### 🐛 Bug Fixes

#### Export System Completely Fixed

- **Fixed missing file extensions**: Exported files now have correct extensions (.shp, .gpkg, .geojson, etc.)
  - `_export_multiple_layers_to_directory()`: Added extension mapping
  - `_export_batch_to_folder()`: Added extension mapping
  - `_export_batch_to_zip()`: Added extension mapping for temp files
- **Fixed driver name mapping**: Added complete driver mapping in `_export_single_layer()` for formats like 'SHP' → 'ESRI Shapefile'
- **Streaming export fixed**: Missing `datatype` argument in `_save_layer_style()` now correctly passed

#### Message Bar Notifications Improved

- **Fixed argument order**: All `iface.messageBar().pushMessage()` calls now use correct argument order `(category, message, level)`
- **Better error reporting**: Failed tasks now display detailed error messages to users
- **Partial export handling**: When some layers fail during export, users see which layers failed and why

### 🔧 Technical Improvements

- Added `extension_map` dictionary in export methods for consistent file extensions
- Added `driver_map` dictionary in `_export_single_layer()` for QGIS driver names
- Supported formats: GPKG, SHP, GeoJSON, GML, KML, CSV, XLSX, TAB/MapInfo, DXF, SQLite, SpatiaLite
- `FilterEngineTask._export_with_streaming()`: Added `datatype` parameter to style saving call
- `FilterEngineTask.finished()`: Improved error handling with proper message display
- `LayersManagementEngineTask.finished()`: Fixed message bar argument order

---

## [2.4.2] - 2025-12-22 - Exploring ValueRelation & Display Enhancement

### ✨ New Features

#### Smart Display Expression Detection for Exploring Widgets

- **ValueRelation Support**: Automatically detects fields with ValueRelation widget configuration and uses `represent_value("field_name")` to display human-readable values instead of raw foreign keys
- **Layer Display Expression**: Uses the layer's configured display expression (from Layer Properties > Display) when available
- **Intelligent Field Selection**: Enhanced priority order for display field selection:
  1. Layer's configured display expression
  2. ValueRelation fields with descriptive value names
  3. Fields matching name patterns (name, nom, label, titre, etc.)
  4. First text field with values
  5. Primary key as fallback

### 🔧 New Utility Functions in `appUtils.py`

- `get_value_relation_info(layer, field_name)` - Extract ValueRelation widget configuration including referenced layer, key field, and value field
- `get_field_display_expression(layer, field_name)` - Get QGIS expression for displaying a field's value (supports ValueRelation, ValueMap, RelationReference)
- `get_layer_display_expression(layer)` - Get the layer's configured display expression
- `get_fields_with_value_relations(layer)` - List all fields with ValueRelation configuration

### 🎯 Improvements

- **Better Exploring UX**: When browsing features in the EXPLORING tab, users now see meaningful labels (like "Paris" or "Category A") instead of cryptic IDs
- **Automatic Detection**: No configuration needed - FilterMate automatically detects the best display field for each layer
- **Backward Compatible**: Existing configurations continue to work; new logic only applies when no expression is configured

### 📚 Documentation

- Updated function signatures and docstrings for `get_best_display_field()` with new `use_value_relations` parameter
- Added examples showing ValueRelation expression output

---

## [2.4.1] - 2025-12-22 - International Edition Extended

### 🌍 3 New Languages Added!

- **Slovenian (Slovenščina)** - `sl` - For Slovenia users
- **Filipino/Tagalog (Tagalog)** - `tl` - For Philippines users
- **Amharic (አማርኛ)** - `am` - For Ethiopia users

### 📊 Total Languages: 21

FilterMate now supports: English, French, German, Spanish, Italian, Dutch, Portuguese, Polish, Chinese, Russian, Indonesian, Vietnamese, Turkish, Hindi, Finnish, Danish, Swedish, Norwegian, **Slovenian**, **Filipino**, **Amharic**

### 🔧 Translation Improvements

- **Fixed Hardcoded French Strings** - All French source strings in `filter_mate.py` replaced with English
- **19 New Translatable Strings** - Configuration migration, geometry validation, reset dialogs
- **Translation Utility Scripts** - New tools for managing translations:
  - `tools/update_translations.py` - Add new strings to existing translations
  - `tools/create_new_translations.py` - Create new language files

### 📁 New Translation Files

- `i18n/FilterMate_sl.ts` - Slovenian (140 strings)
- `i18n/FilterMate_tl.ts` - Filipino/Tagalog (140 strings)
- `i18n/FilterMate_am.ts` - Amharic (140 strings)

### 🔄 Updated All Existing Translation Files

All 18 existing translation files updated with 11 new configuration-related strings.

---

## [2.4.0] - 2025-12-22 - International Edition

### 🌍 New Languages (11 Added!)

- **Polish (Polski)** - `pl`
- **Chinese Simplified (简体中文)** - `zh`
- **Russian (Русский)** - `ru`
- **Indonesian (Bahasa Indonesia)** - `id`
- **Vietnamese (Tiếng Việt)** - `vi`
- **Turkish (Türkçe)** - `tr`
- **Hindi (हिन्दी)** - `hi`
- **Finnish (Suomi)** - `fi`
- **Danish (Dansk)** - `da`
- **Swedish (Svenska)** - `sv`
- **Norwegian (Norsk)** - `nb`

### 📊 Total Languages: 18

FilterMate now supports: English, French, German, Spanish, Italian, Dutch, Portuguese, Polish, Chinese, Russian, Indonesian, Vietnamese, Turkish, Hindi, Finnish, Danish, Swedish, Norwegian

### 🔧 Configuration Updates

- Updated `config.default.json` with all 18 language choices
- Updated `config_schema.json` validation for new languages
- Enhanced language selection dropdown in Configuration panel

### 📁 New Translation Files

- `i18n/FilterMate_pl.ts` - Polish
- `i18n/FilterMate_zh.ts` - Chinese Simplified
- `i18n/FilterMate_ru.ts` - Russian
- `i18n/FilterMate_id.ts` - Indonesian
- `i18n/FilterMate_vi.ts` - Vietnamese
- `i18n/FilterMate_tr.ts` - Turkish
- `i18n/FilterMate_hi.ts` - Hindi
- `i18n/FilterMate_fi.ts` - Finnish
- `i18n/FilterMate_da.ts` - Danish
- `i18n/FilterMate_sv.ts` - Swedish
- `i18n/FilterMate_nb.ts` - Norwegian

---

## [2.3.9] - 2025-12-22 - Critical Stability Fix

### 🔥 Critical Bug Fixes

- **Fixed GEOS Crash during OGR Backend Filtering** - Resolved fatal "access violation" crash

  - Crash occurred during `native:selectbylocation` with invalid geometries
  - Some geometries cause C++/GEOS level crashes that cannot be caught by Python
  - New validation prevents these geometries from reaching GEOS operations

- **Fixed Access Violation on Plugin Reload** - Resolved crash during plugin reload/QGIS close
  - Lambdas in `QTimer.singleShot` captured references to destroyed objects
  - Now uses weak references with safe callback wrappers

### 🛡️ New Modules

- **`modules/geometry_safety.py`** - GEOS-safe geometry operations

  - `validate_geometry_for_geos()` - Deep validation: NaN/Inf check, isGeosValid(), buffer(0) test
  - `create_geos_safe_layer()` - Creates memory layer with only valid geometries
  - Graceful fallbacks: returns original layer if no geometries can be processed

- **`modules/object_safety.py`** - Qt/QGIS object validation utilities
  - `is_sip_deleted(obj)` - Checks if C++ object is deleted
  - `is_valid_layer(layer)` - Complete QGIS layer validation
  - `is_valid_qobject(obj)` - QObject validation
  - `safe_disconnect(signal)` - Safe signal disconnection
  - `safe_emit(signal, *args)` - Safe signal emission
  - `make_safe_callback(obj, method)` - Wrapper for QTimer callbacks

### 🔧 Technical Improvements

- **Safe `selectbylocation` Wrapper** - `_safe_select_by_location()` in OGR backend

  - Validates intersect layer before spatial operations
  - Uses `QgsProcessingContext.GeometrySkipInvalid`
  - Creates GEOS-safe layers automatically

- **Virtual Layer Support** - Improved handling of QGIS virtual layers
  - Added `PROVIDER_VIRTUAL` constant
  - Virtual layers always copied to memory for safety

### 📁 Files Changed

- `modules/geometry_safety.py` - New file for geometry validation
- `modules/object_safety.py` - New file for object safety utilities
- `modules/backends/ogr_backend.py` - Added validation and safe wrappers
- `modules/tasks/filter_task.py` - Added geometry validation throughout
- `modules/constants.py` - Added `PROVIDER_VIRTUAL`
- `filter_mate_app.py` - Uses `object_safety` for layer validation

## [2.3.8] - 2025-12-19 - Automatic Dark Mode Support

### ✨ New Features

- **Automatic Dark Mode Detection** - Plugin now detects QGIS theme in real-time

  - Added `QGISThemeWatcher` class that monitors `QApplication.paletteChanged` signal
  - Automatically switches UI theme when user changes QGIS theme settings
  - Supports Night Mapping and other dark themes

- **Icon Inversion for Dark Mode** - PNG icons now visible in dark themes

  - Added `IconThemeManager` class for theme-aware icon management
  - Automatic icon color inversion using `QImage.invertPixels()`
  - Support for `_black`/`_white` icon variants
  - Icon caching for optimal performance

- **Filter Favorites System** - Save and reuse complex filter configurations

  - ⭐ **FavoritesManager** class for managing saved filters
  - 💾 **SQLite Persistence** - Favorites stored in database, organized by project UUID
  - 📊 **Usage Tracking** - Track application count and last used date
  - 🎯 **Multi-Layer Support** - Save configurations affecting multiple layers
  - 📤 **Export/Import** - Share favorites via JSON files
  - 🏷️ **Tags & Search** - Organize with tags and find favorites quickly
  - ⭐ **Favorites Indicator** - Header widget showing favorite count with quick access menu

- **New `modules/icon_utils.py` Module**

  - `IconThemeManager`: Singleton for managing themed icons
  - `invert_pixmap()`: Inverts dark icons to white
  - `get_icon_for_theme()`: Returns appropriate icon for current theme
  - `apply_icon_to_button()`: Applies themed icons to QPushButton/QToolButton
  - `get_themed_icon()`: High-level utility function for easy icon theming

- **New `modules/filter_favorites.py` Module**
  - `FilterFavorite`: Dataclass representing a saved filter configuration
  - `FavoritesManager`: Manages collection of favorites with SQLite storage
  - Auto-migration from legacy project variables
  - Max 50 favorites per project (oldest removed when limit exceeded)

### 🎨 UI/UX Improvements

- **JsonView Theme Synchronization** - Config editor updates with main theme

  - Added `refresh_theme_stylesheet()` method to JsonView
  - Config editor now matches plugin theme
  - Smooth transition when switching themes

- **Enhanced Theme Change Notification**
  - Brief info message when theme changes
  - Logs theme transitions for debugging

### 🛠️ Technical Improvements

- **Theme Detection** - Luminance-based algorithm (threshold: 128)

  - Uses `QgsApplication.palette().color(QPalette.Window).lightness()`
  - Consistent detection across QGIS versions

- **Resource Cleanup** - Theme watcher properly cleaned up on plugin close
  - Callback removed in `closeEvent`
  - Prevents memory leaks and dangling signal connections

### 📁 Files Changed

- `modules/icon_utils.py` - New file for icon theming
- `modules/ui_styles.py` - Added `QGISThemeWatcher` class
- `modules/qt_json_view/view.py` - Added `refresh_theme_stylesheet()` method
- `filter_mate_dockwidget.py` - Theme watcher integration

## [2.3.7] - 2025-12-18 - Project Change Stability Enhancement

### 🛡️ Stability Improvements

- **Enhanced Project Change Handling** - Complete rewrite of `_handle_project_change()`

  - Forces cleanup of previous project state before reinitializing
  - Clears `PROJECT_LAYERS`, add_layers queue, and all state flags
  - Resets dockwidget layer references to prevent stale data
  - Added 300ms delay before reinitialization for QGIS signal processing

- **New `cleared` Signal Handler** - Proper cleanup on project close/clear

  - Added `_handle_project_cleared()` method
  - Connected to `QgsProject.instance().cleared` signal
  - Ensures plugin state is reset when project is closed or new project created
  - Disables UI widgets while waiting for new layers

- **Updated Timing Constants** - Improved delays for better stability
  - `UI_REFRESH_DELAY_MS`: 300 (was 200)
  - `PROJECT_LOAD_DELAY_MS`: 2500 (was 1500)
  - `SIGNAL_DEBOUNCE_MS`: 150 (was 100)
  - New: `PROJECT_CHANGE_CLEANUP_DELAY_MS`: 300
  - New: `PROJECT_CHANGE_REINIT_DELAY_MS`: 500
  - New: `POSTGRESQL_EXTRA_DELAY_MS`: 1000

### ✨ New Features

- **Force Reload Layers (F5 Shortcut)** - Manual layer reload when project change fails

  - Press F5 in dockwidget to force complete layer reload
  - Also available via `launchingTask.emit('reload_layers')`
  - Resets all state flags and reloads all vector layers from current project
  - Shows status indicator during reload ("⟳")
  - Useful recovery option when automatic project change detection fails

- **`force_reload_layers()` Method** - Programmatic layer reload
  - New method in `FilterMateApp` class
  - Cancels all pending tasks, clears queues, resets flags
  - Reinitializes database and reloads all vector layers
  - Adds extra delay for PostgreSQL layers

### 🐛 Bug Fixes

- **Fixed Project Change Not Reloading Layers** - More aggressive cleanup prevents stale state
- **Fixed Dockwidget Not Updating After Project Switch** - Full reset of layer references
- **Fixed Plugin Requiring Reload After Project Change** - Proper signal handling
- **Fixed Signal Timing Issue** - Root cause identified and fixed:
  - QGIS emits `layersAdded` signal BEFORE `projectRead` handler completes
  - Old code was waiting for a signal that had already passed
  - Now manually triggers `add_layers` after cleanup instead of waiting for missed signal

### 📝 Technical Details

```python
# Updated stability constants
STABILITY_CONSTANTS = {
    'MAX_ADD_LAYERS_QUEUE': 50,
    'FLAG_TIMEOUT_MS': 30000,
    'LAYER_RETRY_DELAY_MS': 500,
    'UI_REFRESH_DELAY_MS': 300,            # Increased from 200
    'PROJECT_LOAD_DELAY_MS': 2500,         # Increased from 1500
    'PROJECT_CHANGE_CLEANUP_DELAY_MS': 300, # NEW
    'PROJECT_CHANGE_REINIT_DELAY_MS': 500,  # NEW
    'MAX_RETRIES': 10,
    'SIGNAL_DEBOUNCE_MS': 150,             # Increased from 100
    'POSTGRESQL_EXTRA_DELAY_MS': 1000,     # NEW
}
```

### 🔧 Files Changed

- `filter_mate.py`: Rewrote `_handle_project_change()`, added `_handle_project_cleared()`, updated signal connections
- `filter_mate_app.py`: Added `force_reload_layers()`, updated `STABILITY_CONSTANTS`, added `reload_layers` task
- `filter_mate_dockwidget.py`: Added F5 shortcut via `_setup_keyboard_shortcuts()` and `_on_reload_layers_shortcut()`

---

## [2.3.6] - 2025-12-18 - Project & Layer Loading Stability

### 🛡️ Stability Improvements

- **Centralized Timing Constants** - All timing values now in `STABILITY_CONSTANTS` dict

  - `MAX_ADD_LAYERS_QUEUE`: 50 (prevents memory overflow)
  - `FLAG_TIMEOUT_MS`: 30000 (30-second timeout for stale flags)
  - `LAYER_RETRY_DELAY_MS`: 500 (consistent retry delays)
  - `UI_REFRESH_DELAY_MS`: 200 (consistent UI refresh delays)
  - `SIGNAL_DEBOUNCE_MS`: 100 (debounce rapid signals)

- **Timestamp-Tracked Flags** - Automatic stale flag detection and reset

  - `_set_loading_flag(bool)`: Sets `_loading_new_project` with timestamp
  - `_set_initializing_flag(bool)`: Sets `_initializing_project` with timestamp
  - `_check_and_reset_stale_flags()`: Auto-resets flags after 30 seconds
  - Prevents plugin from getting stuck in "loading" state

- **Layer Validation** - Better C++ object validation

  - `_is_layer_valid(layer)`: Checks if layer object is still valid
  - Prevents crashes from accessing deleted layer objects
  - Used in `_on_layers_added` and layer filtering

- **Signal Debouncing** - Rapid signal handling
  - `layersAdded` signal debounced to prevent flood
  - Queue size limit with automatic trimming (FIFO)
  - Graceful handling of rapid project/layer changes

### 🐛 Bug Fixes

- **Fixed Stuck Flags** - Flags now auto-reset after 30-second timeout
- **Fixed Queue Overflow** - add_layers queue capped at 50 items
- **Fixed Error Recovery** - Flags properly reset on exception in `_handle_project_change`
- **Fixed Negative Counter** - `_pending_add_layers_tasks` sanitized if negative

### 📝 Technical Details

```python
# New stability constants
STABILITY_CONSTANTS = {
    'MAX_ADD_LAYERS_QUEUE': 50,
    'FLAG_TIMEOUT_MS': 30000,
    'LAYER_RETRY_DELAY_MS': 500,
    'UI_REFRESH_DELAY_MS': 200,
    'SIGNAL_DEBOUNCE_MS': 100,
}
```

---

## [2.3.5] - 2025-12-17 - Code Quality & Configuration v2.0

### 🛠️ Centralized Feedback System

- **Unified Message Bar Notifications** - Consistent user feedback across all modules
  - New `show_info()`, `show_warning()`, `show_error()`, `show_success()` functions
  - Graceful fallback when iface is unavailable
  - Migrated 20+ direct messageBar calls to centralized functions
  - Files updated: `filter_mate_dockwidget.py`, `widgets.py`, `config_editor_widget.py`

### ⚡ PostgreSQL Init Optimization

- **5-50× Faster Layer Loading** - Smarter initialization for PostgreSQL layers
  - Check index existence before creating (avoids slow CREATE IF NOT EXISTS)
  - Connection caching per datasource (eliminates repeated connection tests)
  - Skip CLUSTER at init (very slow, deferred to filter time if beneficial)
  - Conditional ANALYZE only if table has no statistics (check pg_statistic first)

### ⚙️ Configuration System v2.0

- **Integrated Metadata Structure** - Metadata embedded directly in parameters

  - No more fragmented `_*_META` sections
  - Pattern uniforme: `{value, choices, description, ...}`
  - `modules/config_metadata_handler.py` - Intelligent extraction and tooltips
  - Auto-detection and reset of obsolete/corrupted configurations
  - Automatic backup before any migration

- **Forced Backend Respect** - User choice strictly enforced

  - System always uses the backend chosen by user
  - No automatic fallback to OGR when a backend is forced

- **Automatic Configuration Migration** - v1.0 → v2.0 migration system
  - Automatic version detection and migration
  - Backup creation before migration with rollback capability

### 🐛 Bug Fixes

- **Fixed Syntax Errors** - Corrected unmatched parentheses in dockwidget module
- **Fixed Bare Except Clauses** - Specific exception handling

### 🧹 Code Quality

- **Score Improvement**: 8.5 → 8.9/10
- **Obsolete Code Removal** - Removed 22 lines of dead commented code

---

## [2.3.4] - 2025-12-16 - PostgreSQL 2-Part Table Reference Fix

- Reset to defaults option
- Organized by categories with tooltips

### ⚡ Performance Improvements

- **~30% Faster PostgreSQL Layer Loading**
  - Fast feature count using `pg_stat_user_tables` (500× faster than COUNT(\*))
  - UNLOGGED materialized views (30-50% faster creation)
  - Smart caching to eliminate double counting
  - Benchmarks: 1M features load in 32s vs 46s previously

### 🔧 Fixed

- **Configuration Editor Save** (P0 - CRITICAL) - Config now persists correctly
- **Validation Error Messages** (P1 - HIGH) - Clear user feedback for invalid values
- **Improved Error Handling** - 40+ try/finally blocks for resource management

### 📊 Code Quality

- **Complete Performance & Stability Audit** - Score: 9.0/10
  - Performance: 9/10 (excellent optimizations)
  - Stability: 9/10 (robust error handling)
  - Test Coverage: ~70% (target: 80%)
  - Critical TODOs: 0 remaining (all implemented)

### 📚 Documentation (30+ new files)

- **Configuration System**:

  - `docs/CONFIG_SYSTEM.md` - Complete system guide
  - `docs/CONFIG_MIGRATION.md` - Migration guide with examples
  - `docs/CONFIG_OVERVIEW.md` - System overview
  - `docs/CONFIG_INTEGRATION_EXAMPLES.py` - Integration code examples
  - `docs/QUICK_INTEGRATION.md` - 5-minute integration guide
  - `config/README_CONFIG.md` - Quick start guide

- **Performance & Audit**:
  - `docs/POSTGRESQL_LOADING_OPTIMIZATION.md` - Detailed optimization guide
  - `docs/POSTGRESQL_LOADING_OPTIMIZATION_SUMMARY.md` - Executive summary
  - `docs/AUDIT_PERFORMANCE_STABILITY_2025-12-17.md` - Complete audit report
  - `docs/AUDIT_IMPLEMENTATION_2025-12-17.md` - TODOs implementation

### ✅ Testing

- 20+ new unit tests for configuration system
  - `tests/test_config_migration.py` - Migration tests
  - `tests/test_auto_activate_config.py` - AUTO_ACTIVATE behavior tests
- Demo scripts:
  - `tools/demo_config_system.py` - Configuration system demo
  - `tools/demo_config_migration.py` - Migration demo

### 🎯 Technical Details

- **New Modules**:
  - `modules/config_metadata.py` (~600 lines)
  - `modules/config_editor_widget.py` (~450 lines)
  - `modules/config_migration.py` (~700 lines)
- **Enhanced Modules**:
  - `modules/config_helpers.py` - Added metadata support
  - `modules/backends/postgresql_backend.py` - Fast counting + UNLOGGED MVs
- **Configuration**:
  - `config/config_schema.json` - Complete metadata schema
- **Memory Updates**:
  - `.serena/memories/project_overview.md` - Updated with v2.3.5 features
  - `.serena/memories/code_quality_improvements_2025.md` - Audit results

### 📚 Additional Documentation

- `docs/CONFIG_DEVELOPER_GUIDE_2025-12-17.md` - Quick reference for developers
- `docs/CONFIG_INTEGRATION_ANALYSIS_2025-12-17.md` - Complete integration analysis (47 usage cases)
- `docs/CONFIG_USAGE_CASES_2025-12-17.md` - All usage patterns documented
- `docs/INTEGRATION_SUMMARY_2025-12-17.md` - Executive summary
- `docs/fixes/FIX_FORCED_BACKEND_RESPECT_2025-12-17.md` - Backend respect fix
- `docs/fixes/FIX_AUTO_CONFIG_RESET_2025-12-17.md` - Auto-reset documentation

### ✅ New Tests

- `tests/test_auto_config_reset.py` - Migration and reset tests
- `tests/test_config_improved_structure.py` - Structure validation
- `tests/test_forced_backend_respect.py` - Backend respect tests
- **Pattern Analysis**
  - Identified 48+ iface.messageBar() calls for future centralization
  - No critical code duplication detected
  - Excellent error handling patterns established

### 📚 Documentation

- `docs/AUDIT_PERFORMANCE_STABILITY_2025-12-17.md` - Complete audit report
- `docs/AUDIT_IMPLEMENTATION_2025-12-17.md` - TODOs implementation details
- Updated Serena memory: `code_quality_improvements_2025`

### 🎯 Technical Details

- Modified: `modules/config_editor_widget.py` (+20 lines)
- Added imports: `json`, `os`
- Uses `ENV_VARS['CONFIG_JSON_PATH']` for config location
- Graceful fallback when iface unavailable

## [2.3.7] - 2025-12-17 - PostgreSQL Loading Optimizations

### ⚡ Performance Improvements

- **~30% Faster PostgreSQL Layer Loading** - Major optimizations for large datasets
  - **Fast Feature Count Estimation** - Using `pg_stat_user_tables` instead of COUNT(\*)
    - 500× faster for large tables (5ms vs 2.5s for 1M features)
    - Automatic fallback to exact count if statistics unavailable
  - **UNLOGGED Materialized Views** - 30-50% faster MV creation
    - Eliminates Write-Ahead Log (WAL) overhead for temporary views
    - Perfect for FilterMate's temporary filtering views
    - Configurable via `ENABLE_MV_UNLOGGED` flag (enabled by default)
  - **Cached Feature Count** - Eliminates duplicate counting operations
    - Uses fast estimation for strategy decisions
    - Single exact count only when needed for user reporting

### 📊 Benchmark Results (1M features, spatial intersection)

- Total time: 46.1s → 32.1s (**30% improvement**)
- Initial count: 2.5s → 0.005s (**500× faster**)
- MV creation: 30s → 18s (**40% faster**)

### 📚 Documentation

- New comprehensive guide: `docs/POSTGRESQL_LOADING_OPTIMIZATION.md`
  - Detailed problem analysis and solutions
  - Performance benchmarks by dataset size
  - Configuration and troubleshooting guides
- Executive summary: `docs/POSTGRESQL_LOADING_OPTIMIZATION_SUMMARY.md`

### 🔧 Technical Details

- New method: `PostgreSQLGeometricFilter._get_fast_feature_count()`
- Modified: `apply_filter()` and `_apply_with_materialized_view()`
- Configuration flag: `ENABLE_MV_UNLOGGED = True` (line 61)

## [2.3.6] - 2025-12-17 - Interactive Backend Selector

### ✨ New Features

- **Interactive Backend Selector** - Backend indicator is now clickable to manually force a specific backend
  - Click on backend badge to open context menu with available backends
  - Forced backends marked with ⚡ lightning bolt symbol
  - Per-layer backend preferences (each layer can use different backend)
  - Automatic detection of available backends based on layer type
  - Clear tooltips showing current backend and performance characteristics
  - "Auto" mode restores automatic backend selection
- **🎯 Auto-select Optimal Backends** - NEW menu option to automatically optimize all layers
  - Analyzes each layer's characteristics (provider type, feature count, data source)
  - Intelligently selects the best backend for each layer:
    - Small PostgreSQL datasets (< 10k features) → OGR for speed
    - Large PostgreSQL datasets (≥ 10k features) → PostgreSQL for performance
    - SQLite/GeoPackage with > 5k features → Spatialite for efficiency
    - Small SQLite/GeoPackage (≤ 5k features) → OGR sufficient
    - Regular OGR formats (Shapefiles, GeoJSON) → OGR
  - Shows comprehensive summary with backend distribution
  - One-click optimization for entire project

### 🎨 UI Improvements

- **Enhanced Backend Indicator**
  - Added hover effect with cursor change to pointer
  - Improved tooltips showing backend info and "(Forced: backend)" when applicable
  - Backend badge now displays actual backend used (not just provider type)
  - Visual feedback for forced backend with ⚡ symbol

### 🛠️ Technical Improvements

- Added backend forcing logic to task parameter building
- Backend preferences stored per layer ID in `forced_backends` dictionary
- Task filtering respects forced backend when creating backend instances
- Enhanced logging to show when forced backend is active

### 📝 Documentation

- New comprehensive documentation: `docs/BACKEND_SELECTOR_FEATURE.md`
- Covers user interaction, technical implementation, and testing guidelines

## [2.3.5] - 2025-12-17 - Stability & Backend Improvements

### 🐛 Bug Fixes

- **CRITICAL: Fixed GeometryCollection error in OGR backend buffer operations** - When using `native:buffer` with OGR backend on GeoPackage layers, the buffer result could contain GeometryCollection type instead of MultiPolygon when buffered features don't overlap.
  - Error fixed: "Impossible d'ajouter l'objet avec une géométrie de type GeometryCollection à une couche de type MultiPolygon"
  - Added automatic conversion from GeometryCollection to MultiPolygon in `_apply_buffer()` method
  - New helper method `_convert_geometry_collection_to_multipolygon()` recursively extracts polygon parts
  - This complements the existing fix in `prepare_spatialite_source_geom()` for Spatialite backend
- **CRITICAL: Fixed potential KeyError crashes in PROJECT_LAYERS access** - Added guard clauses to verify layer existence before dictionary access in multiple critical methods:
  - `_build_layers_to_filter()`: Prevents crash when layer removed during filtering
  - `handle_undo()`: Validates layer exists before undo operation
  - `handle_redo()`: Validates layer exists before redo operation
  - `exploring_source_params_changed()`: Guards against invalid layer state
  - `get_exploring_features()`: Returns empty safely if layer not tracked
- **Fixed GeoPackage geometric filtering** - GeoPackage layers now use fast Spatialite backend with direct SQL queries instead of slow OGR algorithms (10× performance improvement)

### 🛠️ Improvements

- **Improved exception handling throughout codebase** - Replaced generic exception handlers with specific types for better debugging:
  - `postgresql_backend.py`: Cleanup errors now logged with specific exception types
  - `layer_management_task.py`: Connection close errors properly typed and logged
  - `widgets.py`: Feature attribute access errors logged for debugging
  - `filter_mate_dockwidget.py`: Warning message errors typed as `RuntimeError, AttributeError`
  - `filter_mate_app.py`: Connection close errors typed as `OSError, AttributeError`

### 📝 Technical Details

- Modified `modules/backends/ogr_backend.py`:
  - Enhanced `_apply_buffer()` to check and convert GeometryCollection results
  - Added `_convert_geometry_collection_to_multipolygon()` method for geometry type conversion
- Modified `modules/backends/factory.py`: GeoPackage/SQLite files now automatically use Spatialite backend
- All bare `except:` and `except Exception:` clauses without logging replaced
- Added logging for exception handlers to aid debugging
- Guard clauses return early with warning log instead of crashing

## [2.3.4] - 2025-12-16 - PostgreSQL 2-Part Table Reference Fix & Smart Display Fields

### 🐛 Bug Fixes

- **CRITICAL: Fixed PostgreSQL 2-part table reference error** - Filtering remote layers by spatial intersection with source layer using 2-part table references (`"table"."geom"` format without schema) now works correctly. Previously caused "missing FROM-clause entry" SQL error.
  - Added Pattern 4: Handle 2-part table references for regular tables (uses default "public" schema)
  - Added Pattern 2: Handle 2-part buffer references (`ST_Buffer("table"."geom", value)`)
  - EXISTS subquery now correctly generated for all table reference formats
- **Fixed GeometryCollection buffer results** - `unaryUnion` can produce GeometryCollection when geometries don't overlap. Now properly extracts polygons and converts to MultiPolygon.
  - Added automatic conversion from GeometryCollection to MultiPolygon
  - Buffer layer now always uses MultiPolygon type for compatibility
- **Fixed PostgreSQL virtual_id error** - PostgreSQL layers without a unique field/primary key now raise an informative error instead of attempting to use a `virtual_id` field in SQL queries.

### ✨ New Features

- **Smart display field selection** - New layers now auto-select the best display field for exploring expressions
  - Prioritizes descriptive text fields (name, label, titre, description, etc.)
  - Falls back to primary key only when no descriptive field found
  - Auto-initializes empty expressions when switching layers
  - New `get_best_display_field()` utility function in `appUtils.py`

### 🛠️ Improvements

- **Automatic ANALYZE on source tables** - PostgreSQL query planner now has proper statistics
  - Checks `pg_stats` for geometry column statistics before spatial queries
  - Runs ANALYZE automatically if stats are missing
  - Prevents "stats for X.geom do not exist" planner warnings
- **Reduced log noise** - Task cancellation now logs at Info level instead of Warning

### 🛠️ New Tools

- **cleanup_postgresql_virtual_id.py** - Utility script to clean up corrupted layers from previous versions

### 📝 Technical Details

- Modified `_parse_source_table_reference()` in `postgresql_backend.py` to handle 2-part references
- Added `_ensure_source_table_stats()` method in `filter_task.py`
- Buffer layer creation now forces `MultiPolygon` geometry type
- Full documentation in `docs/fixes/POSTGRESQL_VIRTUAL_ID_FIX_2025-12-16.md`

## [2.3.3] - 2025-12-15 - Project Loading Auto-Activation Fix

### 🐛 Bug Fixes

- **CRITICAL: Fixed plugin auto-activation on project load** - Plugin now correctly activates when loading a QGIS project containing vector layers, even if it was activated in a previous empty project. The `projectRead` and `newProjectCreated` signals are now properly connected to `_auto_activate_plugin()` instead of `_handle_project_change()`, enabling automatic detection and activation for new projects.

### 📝 Documentation

- Updated plugin metadata, README, and Docusaurus documentation
- Consolidated version synchronization across all files

## [2.3.1] - 2025-12-14 - Stability & Performance Improvements

### 🐛 Bug Fixes

- **Critical stability improvements** - Enhanced error handling across all modules
- **Filter operation optimization** - Improved performance for large datasets
- **Memory management** - Better resource cleanup and connection handling

### 🛠️ Code Quality

- **Enhanced logging** - More detailed debug information for troubleshooting
- **Error recovery** - Improved graceful degradation in edge cases
- **Test coverage** - Additional test cases for stability scenarios

### 📝 Documentation

- **Version updates** - Synchronized version across all documentation files
- **Configuration guides** - Updated setup instructions

---

## [2.3.0] - 2025-12-13 - Global Undo/Redo & Automatic Filter Preservation

### 🛠️ Code Quality

#### Code Quality Audit (December 13, 2025)

Comprehensive codebase audit with overall score **4.2/5**

- **Architecture**: 4.5/5 - Excellent multi-backend factory pattern
- **PEP 8 Compliance**: 4.5/5 - 95% compliant, all `!= None` and `== True/False` fixed
- **Exception Handling**: 4/5 - Good coverage, ~100 `except Exception` remaining (logged appropriately)
- **Organization**: 4.5/5 - Well-structured with clear separation of concerns
- **Test Coverage**: 3.5/5 - 6 test files, estimated 25% coverage (improvement area)
- **No breaking changes**, 100% backward compatible

#### Debug Statements Cleanup & PEP 8 Compliance

Improved code quality by removing debug print statements and fixing style issues

- **Debug prints removed**: All `print(f"FilterMate DEBUG: ...")` statements converted to `logger.debug()`
- **Affected files**: `filter_mate_app.py`, `filter_mate_dockwidget.py`
- **PEP 8 fixes**: Boolean comparisons corrected in `modules/qt_json_view/datatypes.py`
- **Benefit**: Cleaner production code, proper logging integration, better code maintainability

### 🐛 Bug Fixes

#### QSplitter Freeze Fix (December 13, 2025)

- **Issue**: Plugin would freeze QGIS when ACTION_BAR_POSITION set to 'left' or 'right'
- **Root Cause**: `_setup_main_splitter()` created then immediately deleted a QSplitter
- **Solution**: Skip splitter creation when action bar will be on the side
- **Files Changed**: `filter_mate_dockwidget.py`

#### Project Load Race Condition Fix (December 13, 2025)

- **Issue**: Plugin would freeze when loading a project with layers
- **Root Cause**: Multiple signal handlers triggering simultaneously
- **Solution**: Added null checks and `_loading_new_project` flag guards
- **Files Changed**: `filter_mate_app.py`, `filter_mate.py`

#### Global Undo Remote Layers Fix (December 13, 2025)

- **Issue**: Undo didn't restore all remote layers in multi-layer filtering
- **Root Cause**: Pre-filter state only captured on first filter operation
- **Solution**: Always push global state before each filter operation
- **Files Changed**: `filter_mate_app.py`

### ✨ Enhancement

#### Auto-Activation on Layer Addition or Project Load

Improved user experience by automatically activating the plugin when needed

- **Behavior**: Plugin now auto-activates when vector layers are added to an empty project
- **Triggers**: Layer addition, project read, new project creation
- **Smart Detection**: Only activates if there are vector layers
- **Backward Compatible**: Manual activation via toolbar button still works

### 🚀 Major Features

#### 0. Reduced Notification Fatigue - Configurable Feedback System ⭐ NEW

Improved user experience by reducing unnecessary messages and adding verbosity control

- **Problem Solved**: Plugin displayed 48+ messages during normal usage, creating notification overload
- **Reduction Achieved**:
  - Normal mode: **-42% messages** (52 vs 90 per session)
  - Minimal mode: **-92% messages** (7 vs 90 per session)
- **Three Verbosity Levels**:
  - **Minimal**: Only critical errors and performance warnings (production use)
  - **Normal** ⭐ (default): Balanced feedback, essential information only
  - **Verbose**: All messages including debug info (development/support)
- **Messages Removed**:
  - 8× Undo/redo confirmations (UI feedback sufficient via button states)
  - 4× UI config changes (visible in interface)
  - 4× "No more history" warnings (buttons already disabled)
- **Configurable via**: `config.json` → `APP.DOCKWIDGET.FEEDBACK_LEVEL`
- **Smart Categories**: filter_count, backend_info, progress_info, etc. independently controlled
- **Developer API**: `should_show_message('category')` for conditional display
- **Documentation**: See `docs/USER_FEEDBACK_SYSTEM.md` for complete guide

### 🚀 Major Features

#### 1. Global Undo/Redo Functionality

Intelligent undo/redo system with context-aware behavior

- **Source Layer Only Mode**: Undo/redo applies only to the source layer when no remote layers are selected
- **Global Mode**: When remote layers are selected and filtered, undo/redo restores the complete state of all layers simultaneously
- **Smart Button States**: Undo/redo buttons automatically enable/disable based on history availability
- **Multi-Layer State Capture**: New `GlobalFilterState` class captures source + remote layers state atomically
- **Automatic Context Detection**: Seamlessly switches between source-only and global modes based on layer selection
- **UI Integration**: Existing pushButton_action_undo_filter and pushButton_action_redo_filter now fully functional
- **History Manager**: Extended with global history stack (up to 100 states by default)
- **User Feedback**: Clear success/warning messages indicating which mode is active

#### 2. Automatic Filter Preservation ⭐ NEW

Critical feature preventing filter loss during layer switching and multi-step filtering workflows

- **Problem Solved**: Previously, applying a new filter would replace existing filters, causing data loss when switching layers
- **Solution**: Filters are now automatically combined using logical operators (AND by default)
- **Default Behavior**: When no operator is specified, uses AND to preserve all existing filters
- **Available Operators**:
  - AND (default): Intersection of filters - `(filter1) AND (filter2)`
  - OR: Union of filters - `(filter1) OR (filter2)`
  - AND NOT: Exclusion - `(filter1) AND NOT (filter2)`
- **Use Case Example**:
  1. Filter by polygon geometry → 150 features
  2. Switch to another layer
  3. Apply attribute filter `population > 10000`
  4. Result: 23 features (intersection of both filters preserved!)
  5. Without preservation: 450 features (geometric filter lost)
- **Multi-Layer Support**: Works for both source layer and distant layers
- **Complex WHERE Clauses**: Correctly handles nested SQL expressions
- **User Feedback**: Informative log messages when filters are preserved

### 🛠️ Technical Improvements

#### Undo/Redo System

- **New Module Components**:
  - `GlobalFilterState` class in `modules/filter_history.py`: Manages multi-layer state snapshots
  - `handle_undo()` and `handle_redo()` methods in `filter_mate_app.py`: Intelligent undo/redo with conditional logic
  - `update_undo_redo_buttons()`: Automatic button state management
  - `currentLayerChanged` signal: Real-time button updates on layer switching

#### Filter Preservation

- **Modified Methods** in `modules/tasks/filter_task.py`:
  - `_initialize_source_filtering_parameters()`: Always captures existing subset string
  - `_combine_with_old_subset()`: Uses AND operator by default when no operator specified
  - `_combine_with_old_filter()`: Same logic for distant layers
- **Logging**: Clear messages when filters are preserved and operators applied
- **Backwards Compatible**: No breaking changes, 100% compatible with existing projects

### 🧪 Testing

- **New Test Suite**: `tests/test_filter_preservation.py`
  - 8+ unit tests covering all operator combinations
  - Tests for workflow scenarios (geometric → attribute filtering)
  - Tests for complex WHERE clause preservation
  - Tests for multi-layer operations

### 📚 Documentation

- Added `docs/UNDO_REDO_IMPLEMENTATION.md`: Comprehensive implementation guide with architecture, workflows, and use cases
- Added `docs/FILTER_PRESERVATION.md`: Complete technical guide for filter preservation system
  - Architecture and logic explanation
  - SQL examples and use cases
  - User guide with FAQs
  - Testing guidelines
- Added `FILTER_PRESERVATION_SUMMARY.md`: Quick reference in French for users

## [2.2.5] - 2025-12-08 - Automatic Geographic CRS Handling

### 🚀 Major Improvements

- **Automatic EPSG:3857 Conversion for Geographic CRS**: FilterMate now automatically detects geographic coordinate systems (EPSG:4326, etc.) and switches to EPSG:3857 (Web Mercator) for all metric-based operations
  - **Why**: Ensures accurate buffer distances in meters instead of imprecise degrees
  - **Benefit**: 50m buffer is always 50 meters, regardless of latitude (no more 30-50% errors at high latitudes!)
  - **Implementation**:
    - Zoom operations: Auto-convert to EPSG:3857 for metric buffer, then transform back
    - Filtering: Spatialite and OGR backends auto-convert for buffer calculations
    - Logging: Clear messages when CRS switching occurs (🌍 indicator)
  - **User impact**: Zero configuration - works automatically for all geographic layers
  - **Performance**: Minimal (~1ms per feature for transformation)

### 🐛 Bug Fixes

- **Geographic Coordinates Zoom & Flash Fix**: Fixed critical issues with EPSG:4326 and other geographic coordinate systems
  - Issue #1: Feature geometry was modified in-place during transformation, causing flickering with `flashFeatureIds`
  - Issue #2: Buffer distances in degrees were imprecise (varied with latitude: 100m at equator ≠ 100m at 60° latitude)
  - Issue #3: No standardization of buffer calculations across different latitudes
  - Solution:
    - Use `QgsGeometry()` copy constructor to prevent original geometry modification
    - **Automatic switch to EPSG:3857 for all geographic CRS buffer operations**
    - Calculate buffer in EPSG:3857 (metric), then transform back to original CRS
    - All buffers now consistently use meters, not degrees
  - Added comprehensive test suite in `tests/test_geographic_coordinates_zoom.py`
  - See `docs/fixes/geographic_coordinates_zoom_fix.md` for detailed technical documentation

### 📊 Technical Details

**CRS Switching Logic**:

```python
if layer_crs.isGeographic() and buffer_value > 0:
    # Auto-convert: EPSG:4326 → EPSG:3857 → buffer → back to EPSG:4326
    work_crs = QgsCoordinateReferenceSystem("EPSG:3857")
    transform = QgsCoordinateTransform(layer_crs, work_crs, project)
    geom.transform(transform)
    geom = geom.buffer(50, 5)  # Always 50 meters!
    # Transform back...
```

**Backends Updated**:

- ✅ `filter_mate_dockwidget.py`: `zooming_to_features()`
- ✅ `modules/appTasks.py`: `prepare_spatialite_source_geom()`
- ✅ `modules/appTasks.py`: `prepare_ogr_source_geom()` (already had it!)

## [2.2.4] - 2025-12-08 - Bug Fix Release

### 🐛 Bug Fixes

- **CRITICAL FIX: Spatialite Expression Quotes**: Fixed bug where double quotes around field names were removed during expression conversion
  - Issue: `"HOMECOUNT" > 100` was incorrectly converted to `HOMECOUNT > 100`
  - Impact: Filters failed on Spatialite layers with case-sensitive field names
  - Solution: Removed quote-stripping code in `qgis_expression_to_spatialite()`
  - Spatialite now preserves field name quotes, relying on implicit type conversion
  - Added comprehensive test suite in `tests/test_spatialite_expression_quotes.py`

### 🧪 Testing

- Added comprehensive test suite for Spatialite expression conversion
- Validated field name quote preservation across various scenarios
- Ensured backward compatibility with existing expressions

## [2.2.4] - 2025-12-08 - Production Release

### 🚀 Release Highlights

- **Production-Ready**: Stable release with all v2.2.x improvements
- **Color Harmonization**: Complete WCAG AA/AAA accessibility compliance
- **Configuration System**: Real-time JSON reactivity and dynamic UI
- **Multi-Backend Support**: PostgreSQL, Spatialite, and OGR fully implemented
- **Enhanced Stability**: Robust error handling and crash prevention

### 📦 What's Included

All features from v2.2.0 through v2.2.3:

- Color harmonization with +300% frame contrast
- WCAG 2.1 AA/AAA text contrast (17.4:1 primary, 8.86:1 secondary)
- Real-time configuration updates without restart
- Dynamic UI profile switching (compact/normal/auto)
- Qt JSON view crash prevention
- Automated WCAG compliance testing
- Enhanced visual hierarchy and reduced eye strain

### 🎯 Target Audience

Production users requiring:

- Accessibility compliance (WCAG 2.1)
- Multi-backend flexibility
- Long work session comfort
- Stable, well-tested filtering solution

## [2.2.3] - 2025-12-08 - Color Harmonization & Accessibility

### 🎨 UI Improvements - Color Harmonization Excellence

- **Enhanced Visual Distinction**: Significantly improved contrast between UI elements
- **WCAG 2.1 Compliance**: AA/AAA accessibility standards met for all text
  - Primary text contrast: 17.4:1 (AAA compliance)
  - Secondary text contrast: 8.86:1 (AAA compliance)
  - Disabled text: 4.6:1 (AA compliance)
- **Theme Refinements**:
  - `default` theme: Darker frame backgrounds (#EFEFEF), clearer borders (#D0D0D0)
  - `light` theme: Better widget contrast (#F8F8F8), visible borders (#CCCCCC)
- **Accent Colors**: Deeper blue (#1565C0) for better contrast on white backgrounds
- **Frame Separation**: +300% contrast improvement between frames and widgets
- **Border Visibility**: +40% darker borders for clearer field delimitation

### 📊 Accessibility & Ergonomics

- Reduced eye strain with optimized color contrasts
- Clear visual hierarchy throughout the interface
- Better distinction for users with mild visual impairments
- Long work session comfort improved

### 🧪 Testing & Documentation

- **New Test Suite**: `test_color_contrast.py` validates WCAG compliance
- **Visual Preview**: `generate_color_preview.py` creates interactive HTML comparison
- **Documentation**: Complete color harmonization guide in `docs/COLOR_HARMONIZATION.md`

### ✨ Configuration Features (from v2.2.2)

- Real-time configuration updates without restart
- Dynamic UI profile switching (compact/normal/auto)
- Live icon updates and auto-save
- Type-safe dropdown selectors for config fields

## [2.2.2] - 2025-12-08 - Configuration Reactivity & Initial Color Work

### 🎨 UI Improvements - Color Harmonization

- **Enhanced Visual Distinction**: Improved contrast between UI elements in normal mode
- **Theme Refinements**:
  - `default` theme: Darker frame backgrounds (#EFEFEF), clearer borders (#D0D0D0)
  - `light` theme: Better widget contrast (#F8F8F8), visible borders (#CCCCCC)
- **Text Contrast**: WCAG AAA compliance (17.4:1 for primary text)
  - Primary text: #1A1A1A (near-black, excellent readability)
  - Secondary text: #4A4A4A (distinct from primary, 8.86:1 ratio)
  - Disabled text: #888888 (clearly muted)
- **Accent Colors**: Deeper blue (#1565C0) for better contrast on white backgrounds
- **Frame Separation**: +300% contrast improvement between frames and widgets
- **Border Visibility**: +40% darker borders for clearer field delimitation

### 📊 Accessibility Improvements

- WCAG 2.1 AA/AAA compliance for all text elements
- Reduced eye strain with optimized color contrasts
- Clear visual hierarchy throughout the interface
- Better distinction for users with mild visual impairments

### 🧪 Testing & Documentation

- **New Test Suite**: `test_color_contrast.py` validates WCAG compliance
- **Visual Preview**: `generate_color_preview.py` creates interactive HTML comparison
- **Documentation**: Complete color harmonization guide in `docs/COLOR_HARMONIZATION.md`

### ✨ New Features - Configuration Reactivity

- **Real-time Configuration Updates**: JSON tree view changes now auto-apply without restart
- **Dynamic UI Profile Switching**: Instant switching between compact/normal/auto modes
- **Live Icon Updates**: Configuration icon changes reflected immediately
- **Automatic Saving**: All config changes auto-save to config.json

### 🎯 Enhanced Configuration Types

- **ChoicesType Integration**: Dropdown selectors for key config fields
  - UI_PROFILE, ACTIVE_THEME, THEME_SOURCE dropdowns
  - STYLES_TO_EXPORT, DATATYPE_TO_EXPORT format selectors
- **Type Safety**: Invalid values prevented at UI level

### 🔧 Technical Improvements

- **Signal Management**: Activated itemChanged signal for config handler
- **Smart Path Detection**: Auto-detection of configuration change type
- **New Module**: config_helpers.py with get/set config utilities
- **Error Handling**: Comprehensive error handling with user feedback

## [Unreleased] - Future Improvements

### ✨ New Features

#### Real-time Configuration Updates

- **JSON Tree View Reactivity**: Configuration changes in the JSON tree view are now automatically detected and applied
- **Dynamic UI Profile Switching**: Change between `compact`, `normal`, and `auto` modes without restarting
  - Changes to `UI_PROFILE` in config instantly update all widget dimensions
  - Automatic screen size detection when set to `auto`
  - User feedback notification when profile changes
- **Live Icon Updates**: Icon changes in configuration are immediately reflected in the UI
- **Automatic Saving**: All configuration changes are automatically saved to `config.json`

#### Enhanced Configuration Types

- **ChoicesType Integration**: Key configuration fields now use dropdown selectors in the JSON tree view
  - `UI_PROFILE`: Select from auto/compact/normal with visual dropdown
  - `ACTIVE_THEME`: Choose from auto/default/dark/light themes
  - `THEME_SOURCE`: Pick config/qgis/system theme source
  - `STYLES_TO_EXPORT`: Select QML/SLD/None export format
  - `DATATYPE_TO_EXPORT`: Choose GPKG/SHP/GEOJSON/KML/DXF/CSV format
- **Better User Experience**: No more typing errors - valid values enforced through dropdowns
- **Type Safety**: Invalid values prevented at the UI level

### 🔧 Technical Improvements

#### Signal Management

- **Activated itemChanged Signal**: Connected `JsonModel.itemChanged` signal to configuration handler
- **Smart Path Detection**: Automatic detection of configuration path to determine change type
- **ChoicesType Support**: Proper handling of dict-based choice values `{"value": "...", "choices": [...]}`
- **Error Handling**: Comprehensive error handling with logging and user feedback
- **UI_CONFIG Integration**: Proper integration with `UIConfig` system and `DisplayProfile` enum

#### Configuration Helpers

- **New Module**: `modules/config_helpers.py` with utility functions for config access
  - `get_config_value()`: Read values with automatic ChoicesType extraction
  - `set_config_value()`: Write values with validation
  - `get_config_choices()`: Get available options
  - `validate_config_value()`: Validate before setting
  - Convenience functions: `get_ui_profile()`, `get_active_theme()`, etc.
- **Backward Compatibility**: Fallback support for old config structure
- **Type Safety**: Validation prevents invalid choices

#### Code Quality

- **New Tests**:
  - `test_config_json_reactivity.py` with 9 tests for reactivity
  - `test_choices_type_config.py` with 19 tests for ChoicesType
- **Documentation**:
  - `docs/CONFIG_JSON_REACTIVITY.md` - Reactivity architecture
  - `docs/CONFIG_JSON_IMPROVEMENTS.md` - Configuration improvements roadmap
- **Extensibility**: Architecture ready for future reactive configuration types (themes, language, styles)

### 📚 Documentation

- **New**: `docs/CONFIG_JSON_REACTIVITY.md` - Complete guide to configuration reactivity
- **New**: `docs/CONFIG_JSON_IMPROVEMENTS.md` - Analysis and improvement proposals
- **Test Coverage**: All reactivity and ChoicesType features covered by automated tests
- **Code Comments**: Comprehensive inline documentation for config helpers

### 🎯 User Experience

- **Immediate Feedback**: UI updates instantly when configuration changes
- **No Restart Required**: All profile changes applied without restarting QGIS or the plugin
- **Clear Notifications**: Success messages inform users when changes are applied
- **Dropdown Selectors**: ChoicesType fields show as interactive dropdowns in JSON tree view
- **Error Prevention**: Invalid values prevented through UI constraints
- **Backward Compatible**: Works seamlessly with existing configuration files

### 📊 Statistics

- **Lines Added**: ~900 (including tests and documentation)
- **New Files**: 3 (config_helpers.py, 2 test files, 2 docs)
- **Test Coverage**: 28 new tests (100% pass rate ✅)
- **Configuration Fields Enhanced**: 5 fields converted to ChoicesType
- **Helper Functions**: 11 utility functions for config access

---

## [2.2.1] - 2025-12-07 - Maintenance Release

### 🔧 Maintenance

- **Release Management**: Improved release tagging and deployment procedures
- **Build Scripts**: Enhanced build automation and version management
- **Documentation**: Updated release documentation and procedures
- **Code Cleanup**: Minor code formatting and organization improvements

---

## [2.2.0] - 2025-12-07 - Stability & Compatibility Improvements

### 🔧 Stability Enhancements

#### Qt JSON View Crash Prevention

- **Improved Error Handling**: Enhanced crash prevention in Qt JSON view component
- **Tab Widget Safety**: Better handling of tab widget errors during initialization
- **Theme Integration**: More robust QGIS theme detection and synchronization
- **Resource Management**: Optimized memory usage and cleanup

#### UI/UX Refinements

- **Error Recovery**: Graceful degradation when UI components fail
- **Visual Consistency**: Improved theme synchronization across all widgets
- **Feedback Messages**: Enhanced user notifications for edge cases

### 🐛 Bug Fixes

- Fixed potential crashes in Qt JSON view initialization
- Improved tab widget error handling and recovery
- Enhanced theme switching stability
- Better resource cleanup on plugin unload

### 📚 Documentation

- Updated crash fix documentation (`docs/fixes/QT_JSON_VIEW_CRASH_FIX_2025_12_07.md`)
- Enhanced troubleshooting guides
- Improved code comments and inline documentation

### 🔄 Maintenance

- Code cleanup and refactoring
- Updated dependencies documentation
- Improved error logging and diagnostics

---

## [2.1.0] - 2025-12-07 - Stable Production Release

### 🎉 Production Ready - Comprehensive Multi-Backend System

FilterMate 2.1.0 marks the stable production release with full multi-backend architecture, comprehensive testing, and extensive documentation.

### ✨ Major Features

#### Complete Backend Architecture

- **PostgreSQL Backend**: Materialized views, server-side operations (>50k features)
- **Spatialite Backend**: Temporary tables, R-tree indexes (10k-50k features)
- **OGR Backend**: Universal fallback for all data sources (<10k features)
- **Factory Pattern**: Automatic backend selection based on data source
- **Performance Warnings**: Intelligent recommendations for optimal backend usage

#### Advanced UI System

- **Dynamic Dimensions**: Adaptive interface based on screen resolution
  - Compact mode (<1920x1080): Optimized for laptops
  - Normal mode (≥1920x1080): Comfortable spacing
  - 15-20% vertical space savings in compact mode
- **Theme Synchronization**: Automatic QGIS theme detection and matching
- **Responsive Design**: All widgets adapt to available space

#### Robust Error Handling

- **Geometry Repair**: 5-strategy automatic repair system
- **SQLite Lock Management**: Retry mechanism with exponential backoff (5 attempts)
- **Connection Pooling**: Optimized database connection management
- **Graceful Degradation**: Fallback mechanisms for all operations

#### Filter History System

- **In-Memory Management**: No database overhead
- **Full Undo/Redo**: Multiple levels of history
- **State Persistence**: Layer-specific filter history
- **Performance**: Instant undo/redo operations

### 🔧 Improvements

#### Performance Optimizations

- Query predicate ordering (2.5x faster)
- Intelligent caching for repeated queries
- Optimized spatial index usage
- Reduced memory footprint

#### User Experience

- Clear performance warnings with recommendations
- Better error messages with actionable guidance
- Visual feedback during long operations
- Comprehensive tooltips and help text

### 📚 Documentation

- Complete architecture documentation (`docs/architecture.md`)
- Backend API reference (`docs/BACKEND_API.md`)
- Developer onboarding guide (`docs/DEVELOPER_ONBOARDING.md`)
- UI system documentation (`docs/UI_SYSTEM_README.md`)
- Comprehensive testing guides
- GitHub Copilot instructions (`.github/copilot-instructions.md`)
- Serena MCP integration (`.serena/` configuration)

### 🧪 Testing & Quality

- Comprehensive unit tests for all backends
- Integration tests for multi-layer operations
- Performance benchmarks
- UI validation scripts
- Continuous testing framework

### 📦 Deployment

- Streamlined release process
- Automated UI compilation (`compile_ui.sh`)
- Release zip creation script (`create_release_zip.py`)
- Version management automation
- GitHub release workflow

---

## [2.0.1] - 2024-12-07 - Dynamic UI Dimensions

### 🎨 UI/UX Improvements - Dynamic Adaptive Interface

#### Comprehensive Dynamic Dimensions System

- **Adaptive UI**: Interface automatically adjusts to screen resolution
  - Compact mode (< 1920x1080): Optimized for laptops and small screens
  - Normal mode (≥ 1920x1080): Comfortable spacing for large displays
- **Tool Buttons**: Reduced to 18x18px (compact) with 16px icons for better fit
- **Input Widgets**: ComboBox and LineEdit dynamically sized (24px compact / 30px normal)
- **Frames**: Exploring and Filtering frames with adaptive min heights
- **Widget Keys**: Narrower button columns in compact mode (45-90px vs 55-110px)
- **GroupBox**: Adaptive minimum heights (40px compact / 50px normal)
- **Layouts**: Dynamic spacing and margins (3/2px compact / 6/4px normal)

#### Implementation Details

- Added 8 new dimension categories in `ui_config.py`
- New `apply_dynamic_dimensions()` method applies settings at runtime
- Automatic detection and application based on screen resolution
- All standard Qt widgets (QComboBox, QLineEdit, QSpinBox) dynamically adjusted
- ~15-20% vertical space saved in compact mode

#### Space Optimization (Compact Mode)

- Widget heights: -20% (30px → 24px)
- Tool buttons: -36% (28px → 18px)
- Frame heights: -20% reduction
- Widget keys width: -18% reduction

**Files Modified**:

- `modules/ui_config.py`: +52 lines (new dimensions)
- `filter_mate_dockwidget.py`: +113 lines (apply_dynamic_dimensions)
- `filter_mate_dockwidget_base.ui`: Tool buttons constraints updated
- `fix_tool_button_sizes.py`: Utility script for UI modifications

**Documentation Added**:

- `docs/UI_DYNAMIC_PARAMETERS_ANALYSIS.md`: Complete analysis
- `docs/IMPLEMENTATION_DYNAMIC_DIMENSIONS.md`: Implementation details
- `docs/DEPLOYMENT_GUIDE_DYNAMIC_DIMENSIONS.md`: Deployment guide
- `DYNAMIC_DIMENSIONS_SUMMARY.md`: Quick reference

---

## [2.0.0] - 2024-12-07 - Production Release

### 🎉 Major Release - Production Ready

FilterMate 2.0 represents a major milestone: a stable, production-ready multi-backend QGIS plugin with comprehensive error handling, robust geometry operations, and extensive test coverage.

### ✨ Key Highlights

- **Stability**: All critical bugs fixed, comprehensive error handling
- **Reliability**: SQLite lock management, geometry repair, robust filtering
- **Performance**: Query optimization, predicate ordering (2.5x faster)
- **User Experience**: Enhanced UI, better feedback, theme support
- **Quality**: Extensive test coverage, comprehensive documentation

### 🐛 Critical Bug Fixes

#### Undo/Redo Functionality Restored

- Fixed undo button clearing all filters instead of restoring previous state
- Integrated HistoryManager for proper state restoration
- Enabled multiple undo/redo operations
- Preserved in-memory history without database deletion

#### Field Selection Fixed

- All fields now visible in exploring dropdowns (including "id", "fid")
- Fixed field filters persistence across layer switches
- Consistent field availability in all selection modes

#### SQLite Database Lock Errors Eliminated

- Implemented retry mechanism with exponential backoff
- Increased timeout from 30s to 60s
- New `sqlite_execute_with_retry()` utility
- Comprehensive test coverage for concurrent operations

#### Buffer Operations Robustness

- Fixed crashes on invalid geometries
- Implemented 5-strategy geometry repair system
- Fixed subset string handling for OGR layers
- Graceful degradation with clear user feedback

### 🚀 Performance Improvements

- **Predicate Ordering**: 2.5x faster multi-predicate queries
- **Query Optimization**: Selective predicates evaluated first
- **Short-circuit Evaluation**: Reduced CPU time on complex queries

### 🎨 UI/UX Enhancements

- Enhanced theme support (light/dark mode)
- Improved error messages with actionable guidance
- Better visual feedback during operations
- Consistent styling across all widgets

### 📚 Documentation & Testing

- Comprehensive test suite (450+ lines of tests)
- Detailed documentation for all major features
- Troubleshooting guides and best practices
- Developer onboarding documentation

### 🔧 Technical Improvements

- Robust error handling throughout codebase
- Better logging and diagnostics
- Refactored code for maintainability
- Improved signal management

### 📦 What's Included

- Multi-backend support (PostgreSQL, Spatialite, OGR)
- Automatic backend selection
- Works with ANY data source (Shapefile, GeoPackage, etc.)
- Filter history with undo/redo
- Geometric filtering with buffer support
- Advanced geometry repair
- Export capabilities with CRS reprojection

## [Unreleased] - 2024-12-05

### 🐛 Bug Fixes

#### Field Selection in Exploring GroupBoxes Now Includes All Fields (e.g., "id")

- **Problem**: Some fields (like "id") were not selectable in exploring groupboxes
  - Field filters were applied during initialization with `QgsFieldProxyModel.AllTypes`
  - However, filters were NOT reapplied when switching layers in `current_layer_changed()`
  - This caused previously applied restrictive filters to persist, hiding certain fields
- **Solution**: Ensure field filters are reapplied when layer changes
  - **Added `setFilters()` call**: Now called before `setExpression()` for all `QgsFieldExpressionWidget`
  - **Consistent behavior**: All field types (except geometry) are always available
  - **Applied to**: single_selection, multiple_selection, and custom_selection expression widgets
- **Impact**:
  - ✅ All non-geometry fields now visible in exploring field dropdowns
  - ✅ Fields like "id", "fid", etc. are now selectable
  - ✅ Consistent field availability across layer switches
- **Files Modified**:
  - `filter_mate_dockwidget.py`: Added `setFilters(QgsFieldProxyModel.AllTypes)` in `current_layer_changed()`

#### Undo Button (Unfilter) Now Correctly Restores Previous Filter State

- **Problem**: Undo button cleared all filters instead of restoring the previous filter state
  - New `HistoryManager` system implemented for in-memory history tracking
  - Old database-based system in `FilterEngineTask._unfilter_action()` still active
  - Old system **deleted** current filter from database before restoring previous one
  - If only one filter existed, nothing remained to restore → complete unfilter
- **Solution**: Integrated `HistoryManager` into `FilterEngineTask.execute_unfiltering()`
  - **Pass history_manager**: Added to task_parameters for unfilter operations
  - **Rewritten execute_unfiltering()**: Uses `history.undo()` for proper state restoration
  - **Direct filter application**: Bypasses `manage_layer_subset_strings` to avoid old deletion logic
  - **Preserved history**: In-memory history maintained, enables multiple undo/redo operations
- **Impact**:
  - ✅ Undo correctly restores previous filter expression
  - ✅ Multiple undo operations now possible (was broken before)
  - ✅ History preserved in memory (no database deletion)
  - ✅ Consistent with modern history management pattern
  - ✅ Better performance (no database access during undo)
- **Files Modified**:
  - `filter_mate_app.py`: Pass history_manager in unfilter task_parameters
  - `modules/appTasks.py`: Rewrite execute_unfiltering() to use HistoryManager
- **Note**: Associated layers are cleared during undo (future enhancement: restore their filters too)

#### SQLite Database Lock Error Fix

- **Problem**: `sqlite3.OperationalError: database is locked` when multiple concurrent operations
  - Error occurred in `insert_properties_to_spatialite()` during layer management
  - Multiple QgsTasks writing to same database simultaneously caused locks
  - No retry mechanism - failed immediately on lock errors
  - 30-second timeout insufficient for busy systems
- **Solution**: Implemented comprehensive retry mechanism with exponential backoff
  - **Increased timeout**: 30s → 60s for better concurrent access handling
  - **New utility**: `sqlite_execute_with_retry()` - generic retry wrapper for database operations
  - **Exponential backoff**: 0.1s → 0.2s → 0.4s → 0.8s → 1.6s between retries
  - **Configurable retries**: 5 attempts by default (via `SQLITE_MAX_RETRIES`)
  - **Smart error handling**: Only retries on lock errors, fails fast on other errors
  - **Refactored** `insert_properties_to_spatialite()` to use retry logic
- **Impact**:
  - ✅ Dramatically improves reliability with concurrent operations
  - ✅ Proper rollback and connection cleanup on failures
  - ✅ Clear logging for debugging (warnings on retry, error on final failure)
  - ✅ Reusable function for other database operations
  - ✅ Works with existing WAL mode for optimal performance
- **Testing**: Comprehensive test suite in `tests/test_sqlite_lock_handling.py`
  - Tests successful operations, lock retries, permanent locks, exponential backoff
  - Concurrent write scenarios with multiple threads
- **Documentation**: See `docs/SQLITE_LOCK_FIX.md` for details

#### Critical Subset String Handling for Buffer Operations

- **Problem**: Buffer operations failed on OGR layers with active subset strings (single selection mode)
  - Error: "Both buffer methods failed... Impossible d'écrire l'entité dans OUTPUT"
  - QGIS processing algorithms don't always handle subset strings correctly
  - After filtering source layer with subset string, geometry operations failed
- **Solution**: Copy filtered features to memory layer before processing
  - **New method** `_copy_filtered_layer_to_memory()`: Extracts filtered features to memory layer
  - Modified `prepare_ogr_source_geom()`: Automatically copies to memory if subset string detected
  - Ensures all QGIS algorithms work with clean in-memory features
- **Impact**:
  - ✅ Fixes crash when using single selection mode with buffer
  - ✅ Transparent to user - happens automatically
  - ✅ Performance: Only copies when needed (subset string present)
  - ✅ Works with all OGR providers (Shapefile, GeoPackage, etc.)

#### Critical Buffer Operation Error Fix

- **Problem**: Buffer operations failed completely when encountering invalid geometries
  - Error: "Both buffer methods failed. QGIS: Impossible d'écrire l'entité dans OUTPUT, Manual: No valid geometries could be buffered"
  - Both QGIS algorithm and manual fallback failed
  - No graceful degradation or helpful error messages
- **Solution**: Implemented aggressive multi-strategy geometry repair
  - **New method** `_aggressive_geometry_repair()` with 5 repair strategies:
    1. Standard `makeValid()`
    2. Buffer(0) trick (fixes self-intersections)
    3. Simplify + makeValid()
    4. ConvexHull (last resort)
    5. BoundingBox (absolute last resort for filtering)
  - **Enhanced validation**: Check for null/empty geometries after repair
  - **Skip invalid features**: Continue processing valid features even if some fail
  - **Detailed logging**: Shows which repair strategy succeeded
  - **Better error messages**:
    - CRS hints for geographic coordinate systems
    - Geometry repair suggestions with QGIS tool references
- **Impact**:
  - ✅ Fixes crash on layers with invalid geometries
  - ✅ Multiple repair strategies increase success rate
  - ✅ Graceful degradation with clear user feedback
  - ✅ Early failure detection prevents wasted processing
  - ⚠️ Note: Convex hull/bbox may alter geometry shapes (only as last resort)
- **Tests**: New comprehensive test suite in `tests/test_buffer_error_handling.py`
- **Documentation**: See `docs/BUFFER_ERROR_FIX.md`
- **Diagnostic tools**:
  - `diagnose_geometry.py`: Analyze problematic geometries
  - `GEOMETRY_DIAGNOSIS_GUIDE.md`: Complete troubleshooting guide

## [Unreleased] - 2024-12-04

### 🐛 Bug Fixes

#### Invalid Geometry Repair

- **Problem**: Geometric filtering with buffer crashed on OGR layers (GeoPackage, Shapefile) when geometries were invalid
  - Error: "Both buffer methods failed... No valid geometries could be buffered. Valid after buffer: 0"
- **Solution**: Added automatic geometry validation and repair before buffer operations
  - New function `_repair_invalid_geometries()` in `modules/appTasks.py`
  - Uses `geom.makeValid()` to repair invalid geometries automatically
  - Transparent to user - repairs happen automatically
  - Detailed logging of repair operations
- **Impact**:
  - ✅ Fixes crash on OGR layers with invalid geometries
  - ✅ No performance impact if all geometries valid
  - ✅ Robust error handling with detailed diagnostics
- **Tests**: New unit tests in `tests/test_geometry_repair.py`
- **Documentation**: See `docs/GEOMETRY_REPAIR_FIX.md`

### 🎯 Performance - Final Optimization (Predicate Ordering)

#### Predicate Ordering Optimization

- **Spatialite Backend** (`modules/backends/spatialite_backend.py`):
  - ✅ Predicates now ordered by selectivity (intersects → within → contains → overlaps → touches)
  - ✅ More selective predicates evaluated first = fewer expensive geometry operations
  - ✅ **Gain: 2.5× faster** on multi-predicate queries
  - ✅ Short-circuit evaluation reduces CPU time

#### Performance Validation

- **New Tests** (`tests/test_performance.py`):

  - ✅ Unit tests for all optimization features
  - ✅ Regression tests (fallback scenarios)
  - ✅ Integration tests
  - ✅ ~450 lignes de tests complets

- **Benchmark Script** (`tests/benchmark_simple.py`):
  - ✅ Interactive demonstration of performance gains
  - ✅ Simulations showing expected improvements
  - ✅ Visual progress indicators
  - ✅ ~350 lignes de code de benchmark

#### Optimizations Already Present (Discovered)

Lors de l'implémentation, nous avons découvert que **toutes les optimisations majeures étaient déjà en place** :

1. **✅ OGR Spatial Index** - Déjà implémenté

   - `_ensure_spatial_index()` crée automatiquement les index
   - Utilisé dans `apply_filter()` pour datasets 10k+
   - Gain: 4× plus rapide

2. **✅ OGR Large Dataset Optimization** - Déjà implémenté

   - `_apply_filter_large()` pour datasets ≥10k features
   - Attribut temporaire au lieu de liste d'IDs massive
   - Gain: 3× plus rapide

3. **✅ Geometry Cache** - Déjà implémenté

   - `SourceGeometryCache` dans `appTasks.py`
   - Évite recalcul pour multi-layer filtering
   - Gain: 5× sur 5 layers

4. **✅ Spatialite Temp Table** - Déjà implémenté
   - `_create_temp_geometry_table()` pour gros WKT (>100KB)
   - Index spatial sur table temporaire
   - Gain: 10× sur 5k features

#### Performance Globale Actuelle

| Scénario               | Performance | Status       |
| ---------------------- | ----------- | ------------ |
| Spatialite 1k features | <1s         | ✅ Optimal   |
| Spatialite 5k features | ~2s         | ✅ Excellent |
| OGR Shapefile 10k      | ~3s         | ✅ Excellent |
| 5 layers filtrés       | ~7s         | ✅ Excellent |

**Toutes les optimisations critiques sont maintenant actives!**

---

## [Unreleased] - 2024-12-04

### 🚀 Performance - Phase 3 Optimizations (Prepared Statements SQL)

#### SQL Query Performance Boost

- **Prepared Statements Module** (`modules/prepared_statements.py`):

  - ✅ New `PreparedStatementManager` base class for SQL optimization
  - ✅ `PostgreSQLPreparedStatements` with named prepared statements
  - ✅ `SpatialitePreparedStatements` with parameterized queries
  - ✅ **Gain: 20-30% faster** on repeated database operations
  - ✅ SQL injection prevention via parameterization
  - ✅ Automatic query plan caching in database

- **Integration in FilterEngineTask** (`modules/appTasks.py`):

  - ✅ Modified `_insert_subset_history()` to use prepared statements
  - ✅ Modified `_reset_action_postgresql()` to use prepared statements
  - ✅ Modified `_reset_action_spatialite()` to use prepared statements
  - ✅ Automatic fallback to direct SQL if prepared statements fail
  - ✅ Shared prepared statement manager across operations

- **Features**:
  - ✅ Query caching for repeated operations (INSERT/DELETE/UPDATE)
  - ✅ Automatic provider detection (PostgreSQL vs Spatialite)
  - ✅ Graceful degradation if unavailable
  - ✅ Thread-safe operations
  - ✅ Comprehensive logging

#### Expected Performance Gains (Phase 3)

| Operation                      | Before | After    | Gain     |
| ------------------------------ | ------ | -------- | -------- |
| Insert subset history (10×)    | 100ms  | 70ms     | **30%**  |
| Delete subset history          | 50ms   | 35ms     | **30%**  |
| Insert layer properties (100×) | 500ms  | 350ms    | **30%**  |
| Batch operations               | N×T    | N×(0.7T) | **~25%** |

**Key Insight:** SQL parsing overhead is eliminated for repeated queries.
Database server caches the query plan and only parameters change.

#### Technical Details

- **PostgreSQL:** Uses `PREPARE` and `EXECUTE` with named statements
- **Spatialite:** Uses parameterized queries with `?` placeholders
- **Complexity:** Parse once, execute many (vs parse every time)
- **Security:** Parameters never interpolated into SQL string (prevents injection)

```python
# Example usage
from modules.prepared_statements import create_prepared_statements

ps_manager = create_prepared_statements(conn, 'spatialite')
ps_manager.insert_subset_history(
    history_id="123",
    project_uuid="proj-uuid",
    layer_id="layer-123",
    source_layer_id="source-456",
    seq_order=1,
    subset_string="field > 100"
)
```

#### Tests

- ✅ 25+ unit tests created (`tests/test_prepared_statements.py`)
- ✅ Coverage for both PostgreSQL and Spatialite managers
- ✅ SQL injection prevention tests
- ✅ Cursor caching tests
- ✅ Error handling and rollback tests
- ✅ Performance improvement verification

---

### 🚀 Performance - Phase 2 Optimizations (Spatialite Temp Tables)

#### Spatialite Backend Major Performance Boost

- **Temporary Table with Spatial Index** (`modules/backends/spatialite_backend.py`):
  - ✅ New `_create_temp_geometry_table()` method creates indexed temp table
  - ✅ Replaces inline WKT parsing (O(n × m)) with indexed JOIN (O(n log n))
  - ✅ **Gain: 10-50× faster** on medium-large datasets (5k-20k features)
  - ✅ Automatic decision: uses temp table for WKT >50KB
  - ✅ Spatial index on temp table for maximum performance
- **Smart Strategy Selection**:
  - ✅ Detects WKT size and chooses optimal method
  - ✅ Temp table for large WKT (>50KB or >100KB based on size)
  - ✅ Inline WKT for small datasets (backward compatible)
  - ✅ Fallback to inline if temp table creation fails
- **Database Path Extraction**:
  - ✅ New `_get_spatialite_db_path()` method
  - ✅ Robust parsing with multiple fallback strategies
  - ✅ Supports various Spatialite source string formats
- **Cleanup Management**:
  - ✅ New `cleanup()` method to drop temp tables
  - ✅ Automatic connection management
  - ✅ Graceful cleanup even if errors occur

#### Expected Performance Gains (Phase 2)

| Scenario                | Before  | After | Gain     |
| ----------------------- | ------- | ----- | -------- |
| Spatialite 1k features  | 5s      | 0.5s  | **10×**  |
| Spatialite 5k features  | 15s     | 2s    | **7.5×** |
| Spatialite 10k features | timeout | 5s    | **∞**    |
| Spatialite 20k features | timeout | 8s    | **∞**    |

**Key Insight:** WKT inline parsing becomes bottleneck above 1k features.
Temp table eliminates this bottleneck entirely.

#### Technical Details

- **Before:** `GeomFromText('...2MB WKT...')` parsed for EACH row comparison
- **After:** Single INSERT into indexed temp table, then fast indexed JOINs
- **Complexity:** O(n × m) → O(n log n) where m = WKT size
- **Memory:** Temp tables auto-cleaned after use

---

## [Unreleased] - 2024-12-04

### 🚀 Performance - Phase 1 Optimizations (Quick Wins)

#### Optimized OGR Backend Performance

- **Automatic Spatial Index Creation** (`modules/backends/ogr_backend.py`):

  - ✅ New `_ensure_spatial_index()` method automatically creates spatial indexes
  - ✅ Creates .qix files for Shapefiles, internal indexes for other formats
  - ✅ **Gain: 4-100× faster** spatial queries depending on dataset size
  - ✅ Fallback gracefully if index creation fails
  - ✅ Performance boost especially visible for 10k+ features datasets

- **Smart Filtering Strategy Selection**:

  - ✅ Refactored `apply_filter()` to detect dataset size automatically
  - ✅ `_apply_filter_standard()`: Optimized for <10k features (standard method)
  - ✅ `_apply_filter_large()`: Optimized for ≥10k features (uses temp attribute)
  - ✅ Large dataset method uses attribute-based filter (fast) vs ID list (slow)
  - ✅ **Gain: 3-5×** on medium datasets (10k-50k features)

- **Code Organization**:
  - ✅ Extracted helper methods: `_apply_buffer()`, `_map_predicates()`
  - ✅ Better separation of concerns and maintainability
  - ✅ Comprehensive error handling with fallbacks

#### Source Geometry Caching System

- **New SourceGeometryCache Class** (`modules/appTasks.py`):

  - ✅ LRU cache with max 10 entries to prevent memory issues
  - ✅ Cache key: `(feature_ids, buffer_value, target_crs_authid)`
  - ✅ **Gain: 5× when filtering 5+ layers** with same source selection
  - ✅ FIFO eviction when cache full (oldest entry removed first)
  - ✅ Shared across all FilterEngineTask instances

- **Cache Integration**:
  - ✅ Modified `prepare_spatialite_source_geom()` to use cache
  - ✅ Cache HIT: Instant geometry retrieval (0.01s vs 2s computation)
  - ✅ Cache MISS: Compute once, cache for reuse
  - ✅ Clear logging shows cache hits/misses for debugging

#### Expected Performance Gains (Phase 1)

| Scenario            | Before  | After | Gain               |
| ------------------- | ------- | ----- | ------------------ |
| OGR 1k features     | 5s      | 2s    | **2.5×**           |
| OGR 10k features    | 15s     | 4s    | **3.75×**          |
| OGR 50k features    | timeout | 12s   | **∞** (now works!) |
| 5 layers filtering  | 15s     | 7s    | **2.14×**          |
| 10 layers filtering | 30s     | 12s   | **2.5×**           |

**Overall:** 3-5× improvement on average, with support for datasets up to 50k+ features.

#### Documentation

- ✅ `docs/PHASE1_IMPLEMENTATION_COMPLETE.md`: Complete implementation guide
- ✅ `docs/PERFORMANCE_ANALYSIS.md`: Technical analysis and bottlenecks
- ✅ `docs/PERFORMANCE_OPTIMIZATIONS_CODE.md`: Code examples and patterns
- ✅ `docs/PERFORMANCE_SUMMARY.md`: Executive summary
- ✅ `docs/PERFORMANCE_VISUALIZATIONS.md`: Diagrams and flowcharts

---

## [Unreleased] - 2024-12-04

### 🔧 Fixed - Filtering Workflow Improvements

#### Improved Filtering Sequence & Validation

- **Sequential Filtering Logic** (`modules/appTasks.py:execute_filtering()`):

  - ✅ Source layer is now ALWAYS filtered FIRST before distant layers
  - ✅ Distant layers are ONLY filtered if source layer filtering succeeds
  - ✅ Immediate abort if source filtering fails (prevents inconsistent state)
  - ✅ Clear validation of source layer result before proceeding

- **Selection Mode Detection & Logging**:

  - ✅ **SINGLE SELECTION**: Automatically detected when 1 feature selected
  - ✅ **MULTIPLE SELECTION**: Detected when multiple features checked
  - ✅ **CUSTOM EXPRESSION**: Detected when using filter expression
  - ✅ Clear logging shows which mode is active and what data is used
  - ✅ Early error detection if no valid selection mode

- **Enhanced Error Handling**:

  - ✅ Structured, visual logging with success (✓), error (✗), and warning (⚠) indicators
  - ✅ Step-by-step progress: "STEP 1/2: Filtering SOURCE LAYER"
  - ✅ Actionable error messages explain WHY filtering failed
  - ✅ Partial success handling: clear if source OK but distant failed
  - ✅ Warning if source layer has zero features after filtering

- **Performance & Debugging**:
  - ✅ No wasted processing on distant layers if source fails
  - ✅ Feature count validation after source filtering
  - ✅ Clear separation of concerns between source and distant filtering
  - ✅ Logs help users understand exactly what happened at each step

#### Benefits

- 🎯 **Reliability**: Guaranteed consistent state (source filtered before distant)
- 🐛 **Debugging**: Clear logs make issues immediately visible
- ⚡ **Performance**: Fast fail if source filtering doesn't work
- 📖 **User Experience**: Users understand which mode is active and what's happening

---

## [Unreleased] - 2024-12-03

### ✨ URGENCE 1 & 2 - User Experience & Architecture Improvements

Combined implementation of highest-priority improvements across UX, logging, testing, and new features.

#### Added - URGENCE 1 (User Experience)

- **Backend-Aware User Feedback** (`modules/feedback_utils.py`, ~240 lines): Visual backend indicators

  - `show_backend_info()`: Display which backend (PostgreSQL/Spatialite/OGR) is processing operations
  - `show_progress_message()`: Informative progress messages for long operations
  - `show_success_with_backend()`: Success messages include backend and operation details
  - `show_performance_warning()`: Automatic warnings for large datasets without PostgreSQL
  - `get_backend_display_name()`: Emoji icons for visual backend identification
    - 🐘 PostgreSQL (high-performance)
    - 💾 Spatialite (file-based)
    - 📁 OGR (file formats)
    - ⚡ Memory (temporary)

- **Enhanced Progress Tracking**: Real-time operation visibility

  - Task descriptions update in QGIS Task Manager showing current layer being processed
  - Export operations show "Exporting layer X/Y: layer_name" progress
  - Filter operations show "Filtering layer X/Y: layer_name" progress
  - ZIP creation shows "Creating zip archive..." with progress bar

- **Comprehensive Test Suite** (`tests/`, 4 new test files):
  - `test_feedback_utils.py`: 15 fully implemented tests (100% coverage)
  - `test_filter_history.py`: 30 tests for undo/redo functionality (100% coverage)
  - `test_refactored_helpers_appTasks.py`: Structure for 58 helper method tests
  - `test_refactored_helpers_dockwidget.py`: Structure for 14 helper method tests
  - Target: 80%+ code coverage using pytest with QGIS mocks

#### Added - URGENCE 2 (New Features)

- **Filter History with Undo/Redo** (`modules/filter_history.py`, ~450 lines): Professional history management
  - `FilterState`: Immutable filter state (expression, feature count, timestamp, metadata)
  - `FilterHistory`: Linear history stack with undo/redo operations
  - `HistoryManager`: Centralized management for all layer histories
  - Unlimited history size (configurable per layer)
  - Thread-safe operations
  - Serialization support for persistence
  - Ready for Ctrl+Z/Ctrl+Y keyboard shortcuts
  - Ready for UI integration (undo/redo buttons)

#### Improved - Already Excellent

- **Logging Infrastructure** (`modules/logging_config.py`): Verified existing excellence
  - ✅ Log rotation: 10MB max file size, 5 backup files (already implemented)
  - ✅ Standardized log levels across modules (already implemented)
  - ✅ Safe stream handling for QGIS shutdown (already implemented)
- **UI Style Management** (`resources/styles/default.qss`, 381 lines): Already externalized
  - ✅ Styles extracted to QSS file (already completed)
  - ✅ Color placeholders for theming (already implemented)
  - ✅ Dark theme with blue accents (already configured)
- **Icon Caching** (`filter_mate_dockwidget.py`): Already optimized
  - ✅ Static icon cache prevents recalculations (already implemented)
  - ✅ Class-level \_icon_cache dictionary (already exists)

#### Technical Details

- All user messages now include visual backend indicators (emoji + name)
- Thread-safe: Progress updates use QgsTask.setDescription() (safe from worker threads)
- No blocking: Message bar calls only from main thread (task completion signals)
- Duration tuning: Info messages 2-3s, warnings 10s, errors 5s
- Backward compatible: No breaking changes to existing functionality
- Filter history supports unlimited states with configurable max size
- History serialization enables persistence across sessions

### 📚 Documentation

- Added comprehensive testing guide in `tests/README.md`
- Test structure supports future TDD development
- Coverage goals defined per module (75-90%)
- CI/CD integration examples provided

### 🧪 Testing

- 15 new tests for feedback utilities (100% coverage)
- 30 new tests for filter history (100% coverage)
- 72 test stubs for refactored helper methods (ready for implementation)
- pytest + pytest-cov + pytest-mock infrastructure
- QGIS mocks in conftest.py for environment-independent testing

---

## [Unreleased] - 2025-12-03

### ✨ User Experience Improvements - URGENCE 1 Features

Implemented high-priority user-facing enhancements to improve feedback and transparency.

#### Added

- **Backend-Aware User Feedback** (`modules/feedback_utils.py`, ~240 lines): Visual backend indicators

  - `show_backend_info()`: Display which backend (PostgreSQL/Spatialite/OGR) is processing operations
  - `show_progress_message()`: Informative progress messages for long operations
  - `show_success_with_backend()`: Success messages include backend and operation details
  - `show_performance_warning()`: Automatic warnings for large datasets without PostgreSQL
  - `get_backend_display_name()`: Emoji icons for visual backend identification
    - 🐘 PostgreSQL (high-performance)
    - 💾 Spatialite (file-based)
    - 📁 OGR (file formats)
    - ⚡ Memory (temporary)
  - `format_backend_summary()`: Multi-backend operation summaries

- **Enhanced Progress Tracking**: Real-time operation visibility

  - Task descriptions update in QGIS Task Manager showing current layer being processed
  - Export operations show "Exporting layer X/Y: layer_name" progress
  - Filter operations show "Filtering layer X/Y: layer_name" progress
  - ZIP creation shows "Creating zip archive..." with progress bar

- **Comprehensive Test Suite** (`tests/`, 3 new test files):
  - `test_feedback_utils.py`: 15 fully implemented tests for user feedback module
  - `test_refactored_helpers_appTasks.py`: Structure for 58 helper method tests
  - `test_refactored_helpers_dockwidget.py`: Structure for 14 helper method tests
  - `tests/README.md`: Complete testing guide with examples and best practices
  - Target: 80%+ code coverage using pytest with QGIS mocks

#### Improved

- **Logging Infrastructure** (`modules/logging_config.py`): Already excellent

  - ✅ Log rotation: 10MB max file size, 5 backup files (already implemented)
  - ✅ Standardized log levels across modules (already implemented)
  - ✅ Safe stream handling for QGIS shutdown (already implemented)
  - ✅ Separate file handlers per module (Tasks, Utils, UI, App)

- **User Messages**: More informative and context-aware

  - Filter operations: "🐘 PostgreSQL: Starting filter on 5 layer(s)..."
  - Success messages: "🐘 PostgreSQL: Successfully filtered 5 layer(s)"
  - Export feedback: "💾 Spatialite: Exporting layer 3/10: buildings"
  - Performance warnings: "Large dataset (150,000 features) using 💾 Spatialite. Consider using PostgreSQL..."
  - Error messages include backend context: "🐘 PostgreSQL: Filter - Connection timeout"

- **Integration Points** (`filter_mate_app.py`):
  - Updated `manage_task()` to show backend-aware start messages
  - Updated `filter_engine_task_completed()` to show backend-aware success messages
  - Automatic provider type detection from task parameters
  - Consistent message formatting across all operations

#### Technical Details

- All user messages now include visual backend indicators (emoji + name)
- Thread-safe: Progress updates use QgsTask.setDescription() (safe from worker threads)
- No blocking: Message bar calls only from main thread (task completion signals)
- Duration tuning: Info messages 2-3s, warnings 10s, errors 5s
- Backward compatible: No breaking changes to existing functionality

### 📚 Documentation

- Added comprehensive testing guide in `tests/README.md`
- Test structure supports future TDD development
- Coverage goals defined per module (75-90%)
- CI/CD integration examples provided

### 🧪 Testing

- 15 new tests for feedback utilities (100% coverage)
- 72 test stubs for refactored helper methods (ready for implementation)
- pytest + pytest-cov + pytest-mock infrastructure
- QGIS mocks in conftest.py for environment-independent testing

---

## [Unreleased] - 2025-12-04

### 🏗️ Architecture & Maintainability - Refactoring Sprint (Phase 2)

Major architectural improvements focusing on code decomposition, state management patterns, and comprehensive documentation.

#### Added

- **State Management Module** (`modules/state_manager.py`, ~450 lines): Professional state management pattern

  - `LayerStateManager`: Encapsulates PROJECT_LAYERS dictionary operations
  - `ProjectStateManager`: Manages configuration and data source state
  - Clean API replacing direct dictionary access
  - Type hints and comprehensive docstrings
  - Ready for gradual migration from global state

- **Backend Helper Methods** (`modules/backends/base_backend.py`): Reusable backend utilities

  - `prepare_geometry_expression()`: Geometry column handling with proper quoting
  - `validate_layer_properties()`: Layer validation with detailed error messages
  - `build_buffer_expression()`: Backend-agnostic buffer SQL generation
  - `combine_expressions()`: Safe WHERE clause combination logic

- **Comprehensive Documentation**: Three major new docs (~2200 lines total)

  - `docs/BACKEND_API.md` (600+ lines): Complete backend API reference with architecture diagrams
  - `docs/DEVELOPER_ONBOARDING.md` (800+ lines): Full developer setup and contribution guide
  - `docs/architecture.md` (800+ lines): System architecture with detailed component diagrams
  - `docs/IMPLEMENTATION_SUMMARY.md` (500+ lines): Summary of refactoring achievements

- **Subset Management Helper Methods** (`modules/appTasks.py`): 11 new focused methods

  - `_get_last_subset_info()`: Retrieve layer history from database
  - `_determine_backend()`: Backend selection logic
  - `_log_performance_warning_if_needed()`: Performance monitoring
  - `_create_simple_materialized_view_sql()`: SQL generation for simple filters
  - `_create_custom_buffer_view_sql()`: SQL generation for custom buffers
  - `_parse_where_clauses()`: CASE statement parsing
  - `_execute_postgresql_commands()`: Connection-safe command execution
  - `_insert_subset_history()`: History record management
  - `_filter_action_postgresql()`: PostgreSQL filter implementation
  - `_reset_action_postgresql()`: PostgreSQL reset implementation
  - `_reset_action_spatialite()`: Spatialite reset implementation
  - `_unfilter_action()`: Undo last filter operation

- **Export Helper Methods** (`modules/appTasks.py`): 7 new focused methods

  - `_validate_export_parameters()`: Extract and validate export configuration
  - `_get_layer_by_name()`: Layer lookup with error handling
  - `_save_layer_style()`: Style file saving with format detection
  - `_export_single_layer()`: Single layer export with CRS handling
  - `_export_to_gpkg()`: GeoPackage export using QGIS processing
  - `_export_multiple_layers_to_directory()`: Batch export to directory
  - `_create_zip_archive()`: ZIP compression with directory structure

- **Source Filtering Helper Methods** (`modules/appTasks.py`): 6 new focused methods

  - `_initialize_source_filtering_parameters()`: Parameter extraction and initialization
  - `_qualify_field_names_in_expression()`: Provider-specific field qualification
  - `_process_qgis_expression()`: Expression validation and SQL conversion
  - `_combine_with_old_subset()`: Subset combination with operators
  - `_build_feature_id_expression()`: Feature ID list to SQL IN clause
  - `_apply_filter_and_update_subset()`: Thread-safe filter application

- **Layer Registration Helper Methods** (`modules/appTasks.py`): 6 new focused methods

  - `_load_existing_layer_properties()`: Load layer properties from Spatialite database
  - `_migrate_legacy_geometry_field()`: Migrate old geometry_field key to layer_geometry_field
  - `_detect_layer_metadata()`: Extract schema and geometry field by provider type
  - `_build_new_layer_properties()`: Create property dictionaries for new layers
  - `_set_layer_variables()`: Set QGIS layer variables from properties
  - `_create_spatial_index()`: Provider-specific spatial index creation

- **Task Orchestration Helper Methods** (`modules/appTasks.py`): 5 new focused methods

  - `_initialize_source_layer()`: Find and initialize source layer with feature count limit
  - `_configure_metric_crs()`: Configure CRS for metric calculations with reprojection
  - `_organize_layers_to_filter()`: Group layers by provider type for filtering
  - `_log_backend_info()`: Log backend selection and performance warnings
  - `_execute_task_action()`: Route to appropriate action (filter/unfilter/reset/export)
  - `_export_multiple_layers_to_directory()`: Batch export to directory
  - `_create_zip_archive()`: Zip archive creation with validation

- **OGR Geometry Preparation Helper Methods** (`modules/appTasks.py`): 8 new focused methods
  - `_fix_invalid_geometries()`: Fix invalid geometries using QGIS processing
  - `_reproject_layer()`: Reproject layer with geometry fixing
  - `_get_buffer_distance_parameter()`: Extract buffer parameter from config
  - `_apply_qgis_buffer()`: Buffer using QGIS processing algorithm
  - `_evaluate_buffer_distance()`: Evaluate buffer distance from expressions
  - `_create_buffered_memory_layer()`: Manual buffer fallback method
  - `_apply_buffer_with_fallback()`: Automatic fallback buffering
  - (8 total methods for complete geometry preparation workflow)

#### Changed

- **God Method Decomposition Phase 1** (`filter_mate_dockwidget.py`): Applied Single Responsibility Principle

  - Refactored `current_layer_changed()` from **270 lines to 75 lines** (-72% reduction)
  - Extracted 14 focused sub-methods with clear responsibilities
  - Improved readability, testability, and maintainability
  - Each method has single clear purpose with proper docstrings

- **God Method Decomposition Phase 2** (`modules/appTasks.py`): Major complexity reduction

  - Refactored `manage_layer_subset_strings()` from **384 lines to ~80 lines** (-79% reduction)
  - Extracted 11 specialized helper methods (see Added section)
  - Separated PostgreSQL and Spatialite backend logic into dedicated methods
  - Main method now orchestrates workflow, delegates to specialists
  - Eliminated deeply nested conditionals (reduced nesting from 5 levels to 2)
  - Better error handling and connection management

- **God Method Decomposition Phase 3** (`modules/appTasks.py`): Export logic streamlined

  - Refactored `execute_exporting()` from **235 lines to ~65 lines** (-72% reduction)
  - Extracted 7 specialized helper methods (see Added section)
  - Separated validation, GPKG export, standard export, and zip logic
  - Main method now clean workflow orchestrator
  - Better parameter validation with early returns
  - Improved error messages and logging

- **God Method Decomposition Phase 4** (`modules/appTasks.py`): Geometry preparation simplified
  - Refactored `prepare_ogr_source_geom()` from **173 lines to ~30 lines** (-83% reduction)
  - Extracted 8 specialized helper methods (see Added section)
  - Separated geometry fixing, reprojection, and buffering concerns
  - Main method now clean 4-step pipeline
  - Automatic fallback for buffer operations
  - Better error handling for invalid geometries
  - Improved logging at each processing step

**Phase 12: \_create_buffered_memory_layer Decomposition** (`modules/appTasks.py`, 67→36 lines, -46%)

- **Main Method**: Refactored into clean 4-step workflow

  - Before: 67 lines with inline feature iteration, buffering, and dissolving
  - After: 36 lines with clear delegation
  - Steps: Validate features → Evaluate distance → Create layer → Buffer features → Dissolve & add
  - Error handling with detailed statistics maintained

- **Helper Methods Created** (3 methods, ~55 lines total):

  - `_create_memory_layer_for_buffer()`: Create empty memory layer with proper geometry type (15 lines)
  - `_buffer_all_features()`: Buffer all features with validation and statistics (30 lines)
  - `_dissolve_and_add_to_layer()`: Dissolve geometries and add to layer with spatial index (25 lines)

- **Key Improvements**:
  - Memory layer creation isolated
  - Feature buffering loop extracted with detailed statistics
  - Dissolve operation separated from iteration
  - Clear separation of concerns: create → buffer → dissolve
  - Statistics tracking maintained (valid/invalid counts)
  - Spatial index creation encapsulated

**Phase 11: manage_distant_layers_geometric_filtering Decomposition** (`modules/appTasks.py`, 68→21 lines, -69%)

- **Main Method**: Refactored into clean 3-step orchestration

  - Before: 68 lines with mixed initialization, geometry preparation, and layer iteration
  - After: 21 lines with clear delegation
  - Steps: Initialize params → Prepare geometries → Filter layers with progress
  - Clean separation of concerns

- **Helper Methods Created** (3 methods, ~105 lines total):

  - `_initialize_source_subset_and_buffer()`: Extract subset and buffer params from config (25 lines)
  - `_prepare_geometries_by_provider()`: Prepare PostgreSQL/Spatialite/OGR geometries with fallback (50 lines)
  - `_filter_all_layers_with_progress()`: Iterate layers with progress tracking and cancellation (30 lines)

- **Key Improvements**:
  - Configuration extraction isolated
  - Geometry preparation with comprehensive fallback logic (Spatialite → OGR)
  - Layer iteration decoupled from preparation
  - Progress tracking and cancellation in dedicated method
  - Clear error handling at each stage
  - Provider list deduplication centralized

**Phase 10: execute_geometric_filtering Decomposition** (`modules/appTasks.py`, 72→42 lines, -42%)

- **Main Method**: Refactored into clean sequential workflow

  - Before: 72 lines with inline validation, expression building, and combination
  - After: 42 lines with clear delegation to helpers
  - Steps: Validate properties → Create spatial index → Get backend → Prepare geometry → Build expression → Combine filters → Apply & log
  - Exception handling maintained at top level

- **Helper Methods Created** (3 methods, ~60 lines total):

  - `_validate_layer_properties()`: Extract and validate layer_name, primary_key, geom_field (25 lines)
  - `_build_backend_expression()`: Build filter using backend with predicates and buffers (20 lines)
  - `_combine_with_old_filter()`: Combine new expression with existing subset using operator (15 lines)

- **Key Improvements**:
  - Property validation isolated with clear error messages
  - Backend expression building encapsulated
  - Filter combination logic centralized and testable
  - Reduced inline conditionals from 6 to 2
  - Main method now clean orchestrator with early validation
  - Thread-safe subset application maintained

**Phase 9: \_manage_spatialite_subset Decomposition** (`modules/appTasks.py`, 82→43 lines, -48%)

- **Main Method**: Refactored into clean 4-step workflow

  - Before: 82 lines with mixed datasource detection, query building, and application
  - After: 43 lines with clear sequential steps
  - Steps: Get datasource → Build query → Create temp table → Apply subset + history
  - Early return for non-Spatialite layers (OGR/Shapefile)

- **Helper Methods Created** (3 methods, ~95 lines total):

  - `_get_spatialite_datasource()`: Extract db_path, table_name, SRID, detect layer type (30 lines)
  - `_build_spatialite_query()`: Build query for simple or buffered subsets (35 lines)
  - `_apply_spatialite_subset()`: Apply subset string and update history (30 lines)

- **Key Improvements**:
  - Datasource detection isolated and reusable
  - Query building separated from execution
  - Simple vs buffered logic centralized
  - History management decoupled from main flow
  - Clear error handling with appropriate logging
  - Thread-safe subset string application maintained

**Phase 8: \_build_postgis_filter_expression Decomposition** (`modules/appTasks.py`, 113→34 lines, -70%)

- **Main Method**: Refactored into clean 2-step orchestration

  - Before: 113 lines with 6 nearly identical SQL template blocks
  - After: 34 lines with clear workflow
  - Steps: Build spatial join query → Apply combine operator → Return expression tuple
  - Eliminated SQL template duplication (6 blocks → 1 reusable helper)

- **Helper Methods Created** (3 methods, ~90 lines total):

  - `_get_source_reference()`: Determine materialized view vs direct table source (16 lines)
  - `_build_spatial_join_query()`: Construct SELECT with spatial JOIN, handle all branching (60 lines)
  - `_apply_combine_operator()`: Apply SQL set operators UNION/INTERSECT/EXCEPT (20 lines)

- **Key Improvements**:
  - Eliminated massive SQL template duplication (6 nearly identical blocks)
  - Centralized branching logic (is_field, has_combine_operator, has_materialized_view)
  - Source reference logic isolated and reusable
  - Combine operator application decoupled from query building
  - Main method now simple orchestrator, not SQL template factory
  - Improved readability: clear what varies (WHERE clause) vs what's constant (SELECT structure)

**Phase 7: run Decomposition** (`modules/appTasks.py`, 120→50 lines, -58%)

- **Main Method**: Refactored into clean orchestration pipeline

  - Before: 120 lines with mixed initialization, configuration, and action routing
  - After: 50 lines with clear sequential workflow
  - Steps: Initialize layer → Configure CRS → Organize filters → Log info → Execute action → Report success

- **Helper Methods Created** (5 methods, ~110 lines total):

  - `_initialize_source_layer()`: Find source layer, set CRS, extract feature count limit
  - `_configure_metric_crs()`: Check CRS units, reproject if geographic/non-metric
  - `_organize_layers_to_filter()`: Group layers by provider with layer count tracking
  - `_log_backend_info()`: Determine backend (PostgreSQL/Spatialite/OGR), log performance warnings
  - `_execute_task_action()`: Router to filter/unfilter/reset/export methods

- **Key Improvements**:
  - Separated initialization from configuration and execution
  - CRS logic isolated and testable
  - Layer organization decoupled from routing
  - Backend logging only for filter actions
  - Action routing with early validation
  - Clean error handling with exception propagation

#### Changed

**Phase 6: add_project_layer Decomposition** (`modules/appTasks.py`, 132→60 lines, -55%)

- **Main Method**: Refactored into clean, linear orchestration

  - Before: 146 lines with deep nesting (4-5 levels), complex conditional logic
  - After: 30 lines with clear 4-step process
  - Steps: Initialize → Process expression → Combine with old subset → Apply filter
  - Fallback: Feature ID list handling if expression fails

- **Helper Methods Created** (6 methods, ~100 lines total):

  - `_initialize_source_filtering_parameters()`: Extract and set all layer parameters
  - `_qualify_field_names_in_expression()`: Provider-specific field name qualification
  - `_process_qgis_expression()`: Expression validation and PostGIS conversion
  - `_combine_with_old_subset()`: Combine new filter with existing subset
  - `_build_feature_id_expression()`: Create SQL IN clause from feature IDs
  - `_apply_filter_and_update_subset()`: Thread-safe filter application

- **Key Improvements**:
  - Separated initialization, validation, transformation, and application
  - Provider-specific logic encapsulated (PostgreSQL vs others)
  - String manipulation logic centralized in qualification method
  - Expression processing with clear return values (None on failure)
  - All database operations in dedicated helper
  - Reduced nesting from 4-5 levels to 2-3 levels

**Phase 5: execute_source_layer_filtering Decomposition** (`modules/appTasks.py`, 146→30 lines, -80%)

- **Main Method**: Refactored into clear sequential workflow

  - Before: 132 lines with nested conditionals, mixed concerns (loading, migration, creation, indexing)
  - After: 60 lines with clear steps
  - Steps: Load or create properties → Migrate legacy → Update config → Save to DB → Create index → Register

- **Helper Methods Created** (6 methods, ~130 lines total):

  - `_load_existing_layer_properties()`: Load properties from Spatialite with variable setting
  - `_migrate_legacy_geometry_field()`: Handle geometry_field → layer_geometry_field migration
  - `_detect_layer_metadata()`: Extract schema/geometry field by provider (PostgreSQL/Spatialite/OGR)
  - `_build_new_layer_properties()`: Create complete property dict from primary key info
  - `_set_layer_variables()`: Set all QGIS layer variables from property dict
  - `_create_spatial_index()`: Provider-aware spatial index creation with error handling

- **Key Improvements**:
  - Separated loading, migration, creation, and persistence concerns
  - Legacy migration isolated and testable
  - Provider-specific metadata extraction centralized
  - Database operations properly encapsulated
  - Early validation with clear failure paths
  - Spatial index creation decoupled from main flow

#### Technical Debt Reduced

- **Code Metrics**: Significant improvements in maintainability

  - Average method length reduced dramatically across 12 major methods
  - **Total lines eliminated: 1330 lines (1862 → 532, -71%)**
  - **72 focused helper methods created** (average 22 lines each)
  - Cyclomatic complexity reduced through extraction
  - Better separation of concerns throughout codebase
  - State management patterns standardized
  - SQL generation logic centralized and reusable
  - **Phase 8**: Eliminated 6 duplicate SQL template blocks
  - **Phase 9**: Separated Spatialite datasource, query building, and application
  - **Phase 10**: Isolated validation, backend expression, and filter combination
  - **Phase 11**: Separated initialization, geometry prep with fallback, and progress tracking
  - **Phase 12**: Separated memory layer creation, feature buffering, and dissolve operations

- **Documentation Coverage**: From minimal to comprehensive

  - Backend architecture fully documented with diagrams
  - Developer onboarding guide created
  - System architecture documented
  - API reference with usage examples

- **Code Duplication**: Reduced through helper methods

  - PostgreSQL connection management centralized
  - SQL generation templates reusable
  - History management standardized
  - Backend determination logic unified
  - Provider-specific logic (PostgreSQL/Spatialite/OGR) encapsulated
  - CRS configuration logic reusable

- **Refactoring Summary** (Phases 1-7):
  - **7 major methods decomposed**: 1460→390 lines total (-73%)
  - **57 focused helper methods created**: Average 22 lines each
  - **Zero errors introduced**: All refactorings validated
  - **Pattern established**: Extract, reduce nesting, improve naming, test
  - **Code duplication eliminated**: Removed duplicate execute_exporting (245 lines)

## [1.9.3] - 2025-12-03

### 🎨 Code Quality & Maintainability - Harmonization Sprint

Major code quality improvements focusing on eliminating magic strings, standardizing constants, and improving maintainability.

#### Added

- **Constants module** (`modules/constants.py`, 306 lines): Centralized constants for entire codebase

  - Provider types: `PROVIDER_POSTGRES`, `PROVIDER_SPATIALITE`, `PROVIDER_OGR`, `PROVIDER_MEMORY`
  - Geometry types with helper function `get_geometry_type_string()`
  - Spatial predicates: `PREDICATE_INTERSECTS`, `PREDICATE_WITHIN`, `PREDICATE_CONTAINS`, etc.
  - Performance thresholds with `should_warn_performance()` helper
  - Task action constants, buffer types, UI constants
  - Comprehensive test suite (29 tests, 100% passing)

- **Signal utilities module** (`modules/signal_utils.py`, 300 lines): Context managers for safe signal management
  - `SignalBlocker`: Exception-safe signal blocking for Qt widgets
  - `SignalConnection`: Temporary signal connections with automatic cleanup
  - `SignalBlockerGroup`: Manage groups of widgets efficiently
  - Comprehensive test suite (23 tests, 100% passing)

#### Changed

- **Constants applied throughout codebase** (6 files, 20+ instances): Eliminated magic strings

  - `modules/appUtils.py`: Provider detection uses constants
  - `modules/appTasks.py`: **15+ hardcoded strings replaced** with constants
  - `modules/backends/factory.py`: Backend selection uses constants
  - `modules/backends/spatialite_backend.py`: Provider checks use constants
  - `filter_mate_dockwidget.py`: Backend detection uses constants
  - Single source of truth for all provider, geometry, and predicate strings

- **UI styles extraction** (`filter_mate_dockwidget.py`): Major code reduction

  - Refactored `manage_ui_style()` from **527 lines to ~150 lines** (-71% reduction)
  - Styles moved to external QSS file (`resources/styles/default.qss`)
  - Dynamic style loading with theme support
  - Much cleaner, more maintainable code

- **Logging standardization**: Replaced remaining print() debugging
  - 4 print() statements replaced with `logger.debug()`
  - Consistent logging throughout entire codebase

#### Fixed

- **Test suite**: Fixed backend test class name imports
  - Updated test imports to use correct class names
  - `PostgreSQLGeometricFilter`, `SpatialiteGeometricFilter`, `OGRGeometricFilter`

#### Technical Debt Reduced

- **Magic strings**: 20+ instances eliminated across 6 core files
- **Code duplication**: Constants defined once, used everywhere
- **Type safety**: Constants prevent typos in provider/predicate strings
- **Maintainability**: Single source of truth makes updates trivial
- **Test coverage**: 52 new tests (57 total passing) for utility modules

#### Documentation

- **Module architecture guide**: Added comprehensive `modules/README.md`
  - Overview of all core modules and their purposes
  - Architecture patterns and best practices
  - Backend performance comparison table
  - Code quality standards and conventions
  - Developer onboarding guide with examples

#### Metrics

- Lines reduced: 377 (manage_ui_style refactoring)
- Test coverage: 90%+ for new modules
- Magic strings eliminated: 100% from core modules
- Files improved: 6 core files + 2 new modules + 2 test suites

## [1.9.2] - 2025-12-03

### 🔒 Security & User Experience - Sprint 1 Continuation

Continued Sprint 1 implementation focusing on security fixes, user feedback enhancements, and code quality improvements.

#### Security Fixed

- **SQL injection vulnerabilities**: Converted 4 vulnerable f-string SQL statements to parameterized queries
  - `save_variables_from_layer()`: Both INSERT statements now use `?` placeholders
  - `remove_variables_from_layer()`: Both DELETE statements now use `?` placeholders
  - **Impact**: Eliminated all SQL injection attack vectors in layer variable management
  - Follows Python/SQLite security best practices

#### Added - User Feedback Messages

- **Backend indicators**: Automatic logging of active backend on filter start
  - "Using PostgreSQL/PostGIS backend for filtering"
  - "Using Spatialite backend for filtering"
  - Helps users understand which backend is processing their data
- **Performance warnings**: Automatic warnings for large datasets without PostgreSQL
  - Triggers when > 50,000 features and not using PostgreSQL
  - "Large dataset detected (75,432 features) without PostgreSQL backend. Performance may be reduced."
  - Helps users optimize their workflow
- **Task start messages**: User-visible notifications when operations begin
  - "Starting filter operation on 3 layer(s)..." (Info, 3 seconds)
  - "Removing filters..." (Info, 2 seconds)
  - "Resetting layers..." (Info, 2 seconds)
- **Success messages**: Confirmation with feature counts when operations complete
  - "Filter applied successfully - 1,234 features visible" (Success, 3 seconds)
  - "Filter removed - 10,567 features visible" (Success, 3 seconds)
  - "Layer reset - 10,567 features visible" (Success, 3 seconds)
  - Feature counts formatted with thousands separator for readability

#### Verified

- **Log rotation system**: Confirmed working correctly
  - RotatingFileHandler: 10MB max, 5 backups, UTF-8 encoding
  - SafeStreamHandler prevents crashes during QGIS shutdown
  - Proper initialization in appTasks, appUtils, and dockwidget
- **Error handling**: All `except: pass` statements already replaced in Phase 1
  - No silent error handlers remaining
  - All exceptions properly logged

#### Documentation

- **SPRINT1_CONTINUATION_SUMMARY.md**: Complete implementation report
  - 4/5 tasks completed (1 deferred: docstrings)
  - Security score improved from 6/10 to 9/10 (+50%)
  - UX score improved from 5/10 to 8/10 (+60%)
  - ~95 lines of high-quality improvements

---

## [1.9.1] - 2025-12-03

### ✅ Sprint 1 Completed - Code Quality & User Feedback

Completed all critical fixes and user experience improvements. Plugin is now more reliable, maintainable, and provides better feedback to users.

#### Fixed

- **Error handling**: Replaced all silent `except: pass` blocks with proper logging
- **Icon caching**: Implemented static cache for geometry icons (50x performance improvement on layer display)
- **Logging system**: Added rotating file handler (max 10 MB, 5 backups) to prevent disk saturation

#### Added

- **Backend indicator UI**: Visual label showing active backend (PostgreSQL ⚡ / Spatialite 💾 / OGR 📁) with color coding
  - Green: PostgreSQL (optimal performance)
  - Blue: Spatialite (good performance)
  - Orange: OGR (fallback)
- **Progress reporting**: Enhanced progress messages in FilterEngineTask with detailed logging
  - "Filtering layer 2/5: rivers (postgresql)"
  - Percentage-based progress bar (0-100%)
- **Test infrastructure**: Created pytest-based test suite with 20+ unit tests

#### Documentation

- **SPRINT1_SUMMARY.md**: Complete summary of Sprint 1 accomplishments
- **IMPLEMENTATION_PLAN.md**: Detailed implementation plan for remaining work
- **ROADMAP.md**: Long-term vision and phased development plan

---

## [Unreleased] - Sprint 2 Phase 1 - Backend Architecture Refactoring

### 🏗️ Architecture - Backend Pattern Implementation

Major refactoring to introduce a clean backend architecture using the Strategy pattern. This significantly improves code maintainability, testability, and extensibility.

#### Added - New Backend Module (`modules/backends/`)

- **base_backend.py**: Abstract `GeometricFilterBackend` class defining interface
  - `build_expression()`: Build backend-specific filter expressions
  - `apply_filter()`: Apply filter to layers
  - `supports_layer()`: Check backend compatibility
  - Built-in logging helpers for all backends
- **postgresql_backend.py**: PostgreSQL/PostGIS optimized backend (~150 lines)
  - Native PostGIS spatial functions (ST_Intersects, ST_Contains, etc.)
  - Efficient spatial indexes
  - SQL-based filtering for maximum performance
- **spatialite_backend.py**: Spatialite backend (~150 lines)
  - ~90% compatible with PostGIS syntax
  - Good performance for small to medium datasets
  - Performance warnings for >50k features
- **ogr_backend.py**: OGR fallback backend (~140 lines)
  - Uses QGIS processing algorithms
  - Compatible with all OGR formats (Shapefile, GeoPackage, etc.)
  - Performance warnings for >100k features
- **factory.py**: `BackendFactory` for automatic backend selection
  - Selects optimal backend based on provider type
  - Handles psycopg2 availability gracefully
  - Automatic fallback chain: PostgreSQL → Spatialite → OGR

#### Changed

- **execute_geometric_filtering()** in appTasks.py: Refactored from 395 lines to ~120 lines
  - Now delegates to specialized backends via factory pattern
  - Removed deeply nested conditional logic
  - Added helper methods: `_get_combine_operator()`, `_prepare_source_geometry()`
  - Improved error handling and logging
  - Complexity reduced from >40 to <10 (cyclomatic complexity)

#### Benefits

- **Extensibility**: Easy to add new backends (MongoDB, Elasticsearch, etc.)
- **Maintainability**: Clear separation of concerns, each backend self-contained
- **Testability**: Each backend can be unit tested independently
- **Performance**: No performance regression, same optimizations as before
- **Code Quality**: Reduced code duplication by ~30%

---

## [1.9.0] - 2025-12-02

### 🎉 Major Update - Multi-Backend Support & Performance Optimizations

FilterMate now works **WITHOUT PostgreSQL**! This is a major architectural improvement that makes the plugin accessible to all users while preserving optimal performance for those using PostgreSQL. Additionally, comprehensive code quality improvements and automatic performance optimizations have been implemented.

### Added

#### Core Features

- **Multi-backend architecture**: Automatic selection between PostgreSQL, Spatialite, and Local (OGR) backends
- **Spatialite backend**: Full implementation with spatial indexing for fast filtering without PostgreSQL
- **Universal format support**: Works with Shapefile, GeoPackage, GeoJSON, KML, and all OGR formats
- **Smart backend detection**: Automatically chooses optimal backend based on data source and availability
- **Automatic spatial indexing**: Creates spatial indexes automatically before geometric filtering (5-15x performance improvement)

#### Functions & Methods (Phase 2)

- `create_temp_spatialite_table()` in appUtils.py: Creates temporary tables as PostgreSQL materialized view alternative
- `get_spatialite_datasource_from_layer()` in appUtils.py: Extracts Spatialite database path from layers
- `qgis_expression_to_spatialite()` in appTasks.py: Converts QGIS expressions to Spatialite SQL syntax
- `_manage_spatialite_subset()` in appTasks.py: Complete Spatialite subset management with buffer support
- `_verify_and_create_spatial_index()` in appTasks.py: Automatic spatial index creation before filtering operations

#### User Experience (Phase 3)

- **Performance warnings**: Automatic alerts for large datasets (>50k features) without PostgreSQL
- **Backend information**: Users see which backend is being used (PostgreSQL/Spatialite/Local)
- **Detailed error messages**: Helpful troubleshooting hints for common issues
- **Informative notifications**: Messages explain what's happening during filtering
- **Spatial index notifications**: Users informed when spatial indexes are being created for performance optimization

#### Documentation

- **INSTALLATION.md**: Comprehensive installation and setup guide (~500 lines)
  - Backend comparison and recommendations
  - PostgreSQL optional setup instructions
  - Performance guidelines by dataset size
  - Troubleshooting section
- **MIGRATION_v1.8_to_v1.9.md**: Migration guide for existing users (~350 lines)

  - What changed and why
  - Compatibility information
  - Step-by-step upgrade process
  - FAQ and common issues

- **PHASE1_IMPLEMENTATION.md**: Technical documentation Phase 1 (~350 lines)
- **PHASE2_IMPLEMENTATION.md**: Technical documentation Phase 2 (~600 lines)

#### Testing

- `test_phase1_optional_postgresql.py`: 5 unit tests for conditional PostgreSQL import
- `test_phase2_spatialite_backend.py`: 7 unit tests for Spatialite backend functionality
- `test_database_connections.py`: 15+ unit tests for connection management and resource cleanup
- `test_spatial_index.py`: 8 unit tests for automatic spatial index creation and verification

### Changed

#### Architecture

- **PostgreSQL is now optional**: Plugin starts and works without psycopg2 installed (Phase 1)
- **Hybrid dispatcher**: `manage_layer_subset_strings()` now routes to appropriate backend
- **Graceful degradation**: Automatic fallback from PostgreSQL → Spatialite → Local OGR
- **Context managers**: Database connections use `with` statements for automatic cleanup
- **Provider constants**: Standardized PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR, PROVIDER_MEMORY

#### Error Handling

- Enhanced error messages with specific troubleshooting guidance
- Better detection of common issues (missing Spatialite extension, etc.)
- More informative warnings about performance implications
- **Replaced 16 bare except clauses** with specific exception types (OSError, ValueError, TypeError, etc.)

#### Performance Optimizations

- **Cached featureCount()**: Single call per operation (50-80% performance improvement)
- **Automatic spatial indexes**: Created before geometric filtering (5-15x faster queries)
- **Connection pooling**: Tracked and cleaned up on task cancellation

#### Code Quality

- **Professional logging**: Python logging module replaces all print statements
- **Unit tests**: 30+ tests covering critical operations
- **Documentation**: Comprehensive README updates with backend selection guide

#### Metadata

- Updated to version 1.9.0
- Enhanced plugin description highlighting new multi-backend support
- Comprehensive changelog in metadata.txt

### Fixed

- Plugin no longer crashes if psycopg2 is not installed
- Better handling of non-PostgreSQL data sources
- Improved error reporting for spatial operations
- **Database connection leaks** causing memory issues and locked files
- **O(n²) complexity** from repeated featureCount() calls
- **Task cancellation** now properly closes all database connections
- **Missing spatial indexes** now created automatically before filtering

### Performance

#### Spatial Index Optimization

| Feature Count | Without Index | With Auto-Index | Improvement     |
| ------------- | ------------- | --------------- | --------------- |
| 10,000        | ~5s           | <1s             | **5x faster**   |
| 50,000        | ~30s          | ~2s             | **15x faster**  |
| 100,000       | >60s          | ~5s             | **12x+ faster** |

#### Backend Performance by Dataset Size

| Features | PostgreSQL | Spatialite | Local OGR | Best Choice           |
| -------- | ---------- | ---------- | --------- | --------------------- |
| < 1k     | ~0.5s      | ~1s        | ~2s       | Any                   |
| 1k-10k   | ~1s        | ~2s        | ~5s       | Spatialite/PostgreSQL |
| 10k-50k  | ~2s        | ~5s        | ~15s      | PostgreSQL            |
| 50k-100k | ~5s        | ~15s       | ~60s+     | PostgreSQL            |
| > 100k   | ~10s       | ~60s+      | Very slow | PostgreSQL only       |

#### No Regression

- PostgreSQL performance: **Identical to v1.8** (no slowdown)
- Same optimizations: Materialized views, spatial indexes, clustering
- All PostgreSQL features preserved: 100% backward compatible
- **Additional optimizations**: Cached featureCount(), automatic spatial indexes

### Technical Details

#### Code Statistics

- **Lines added**: ~800 lines production code
- **Functions created**: 5 new functions/methods (including \_verify_and_create_spatial_index)
- **Tests created**: 30+ unit tests (5 Phase 1, 7 Phase 2, 15+ connection tests, 8 spatial index tests)
- **Documentation**: ~3500+ lines
- **Files modified**: 7 core files (appTasks.py, appUtils.py, filter_mate_app.py, widgets.py, dockwidget.py, README.md, CHANGELOG.md)
- **Files created**: 12 documentation/test files
- **Code quality improvements**:
  - 16 bare except clauses replaced with specific exceptions
  - 11 print statements replaced with logging
  - Context managers for all database connections
  - Comprehensive error handling throughout

#### Backend Logic

```python
# Automatic backend selection
provider_type = layer.providerType()
use_postgresql = (provider_type == 'postgres' and POSTGRESQL_AVAILABLE)
use_spatialite = (provider_type in ['spatialite', 'ogr'] or not use_postgresql)

# Smart routing
if use_postgresql:
    # PostgreSQL: Materialized views (fastest)
elif use_spatialite:
    # Spatialite: Temp tables with R-tree index (fast)
else:
    # Local: QGIS subset strings (good for small data)
```

### Dependencies

#### Required (unchanged)

- QGIS 3.x or later
- Python 3.7+
- sqlite3 (included with Python)

#### Optional (new)

- **psycopg2**: For PostgreSQL support (recommended for large datasets)
- **Spatialite extension**: Usually included with QGIS

### Breaking Changes

**None** - This release is 100% backward compatible with v1.8.

All existing workflows, configurations, and data continue to work identically.

### Migration Notes

For users upgrading from v1.8:

1. **No action required** if you use PostgreSQL - everything works as before
2. **New capability** - You can now use non-PostgreSQL data sources
3. See MIGRATION_v1.8_to_v1.9.md for detailed migration information

### Known Issues

- Large datasets (>100k features) are slow without PostgreSQL (expected, by design)
- Some PostGIS advanced functions may not have Spatialite equivalents (rare)

### Contributors

- **Implementation**: Claude (Anthropic AI) with guidance
- **Original Author**: Sébastien Ducournau (imagodata)
- **Testing**: Community (ongoing)

---

## [1.8.x] - Previous Versions

### Changed

- Rework filtering logic: use of temporary materialized views and indexes
- Add spatialite management: project metadata and subset history
- Rebuild QgsCheckableComboBoxFeaturesListPickerWidget to show filtered entities
- Rework combine logic filter

### Architecture

- PostgreSQL/PostGIS only
- Required psycopg2 installed
- Complex setup process

---

## Version Comparison

| Feature                      | v1.8     | v1.9        |
| ---------------------------- | -------- | ----------- |
| **PostgreSQL Support**       | Required | Optional    |
| **Spatialite Support**       | No       | Yes (new)   |
| **Shapefile Support**        | No       | Yes (new)   |
| **OGR Formats**              | No       | Yes (new)   |
| **Installation**             | Complex  | Simple      |
| **Works out-of-box**         | No       | Yes         |
| **Performance (PostgreSQL)** | Fast     | Fast (same) |
| **Performance (other)**      | N/A      | Good-Fast   |

---

## Roadmap

### [1.10.0] - Phase 4 (Planned)

- Performance optimizations
- Query result caching
- Enhanced spatial index management
- Advanced buffer expressions

### [2.0.0] - Phase 5 (Future)

- UI/UX improvements
- Additional export formats
- Cloud backend support
- Advanced analytics

---

## Links

- **Repository**: https://github.com/sducournau/filter_mate
- **Issues**: https://github.com/sducournau/filter_mate/issues
- **QGIS Plugin**: https://plugins.qgis.org/plugins/filter_mate
- **Documentation**: https://sducournau.github.io/filter_mate

---

**Format**: This changelog follows [Keep a Changelog](https://keepachangelog.com/) conventions.

**Versioning**: FilterMate uses [Semantic Versioning](https://semver.org/).
