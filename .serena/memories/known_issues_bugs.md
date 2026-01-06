# Known Issues & Bug Fixes - FilterMate

**Last Updated:** January 6, 2026

## Critical Bug Fixes (v2.9.x Series - January 2026)

### v2.9.8 - Dissolve Optimization for WKT Creation (January 6, 2026)

**Status:** ✅ FIXED

**Problem:**
- Multiple overlapping/adjacent source geometries create unnecessarily complex WKT
- `collectGeometry()` preserves all vertices even when geometries overlap
- Large WKT strings slow down SQL execution and can cause RTTOPO errors

**Solution:**
- Use `safe_unary_union()` (dissolve) instead of `safe_collect_geometry()` in `prepare_spatialite_source_geom()`
- Dissolve merges overlapping geometries into a single boundary
- Falls back to `safe_collect_geometry()` if unaryUnion fails (e.g., mixed geometry types)

**Benefits:**
- WKT size reduced by 30-70% (less vertices)
- Eliminates redundant overlapping boundaries
- Produces simpler geometry faster to process in Spatialite
- Prevents RTTOPO/MakeValid errors from complex GeometryCollections

**Files Changed:**
- `modules/tasks/filter_task.py` - `prepare_spatialite_source_geom()` method
- `docs/FIX_GEOMETRYCOLLECTION_RTTOPO_2026-01.md` - Updated documentation

---

### v2.9.7 - GeometryCollection RTTOPO Error Fix (January 6, 2026)

**Status:** ✅ FIXED

**Problem:**
- Filtering with complex GeometryCollection source geometries (~111K chars WKT) fails
- Error: `MakeValid error - RTTOPO reports: Unknown Reason`
- OGR fallback also fails (geometries too complex for GEOS)

**Root Cause:**
- GeometryCollection type problematic for RTTOPO/MakeValid in Spatialite
- Excessive coordinate precision (15+ decimal places)
- Complex multi-part geometries exceed RTTOPO internal limits

**Solution (3 parts):**
1. **Enhanced `_simplify_wkt_if_needed()`:**
   - Convert GeometryCollection → MultiPolygon (extract polygons)
   - Reduce coordinate precision (15 decimals → 2 decimals)
   - Apply makeValid() in QGIS before SQL

2. **SQL-level SimplifyPreserveTopology:**
   - For WKT >50KB, add `SimplifyPreserveTopology()` wrapper
   - Provides backup simplification in SQL engine

3. **OGR Fallback Simplification:**
   - New `_simplify_source_for_ogr_fallback()` method
   - Simplifies source geometry before OGR processing

**Files Changed:**
- `modules/backends/spatialite_backend.py`
- `modules/tasks/filter_task.py`
- `docs/FIX_GEOMETRYCOLLECTION_RTTOPO_2026-01.md`

---


### v2.9.6 - Invalid Source Geometry Handling (January 6, 2026)

**Status:** ✅ FIXED

**Problem:**
- Filtering multiple layers from the same GeoPackage returned 0 results for some layers
- Source geometry (filter polygon) was geometrically invalid (self-intersecting, duplicate points)
- Invalid geometries in spatial predicates cause databases to return 0 results

**Solution:**
- Added `MakeValid()`/`ST_MakeValid()` wrapper to ALL source geometry expressions
- Spatialite: `MakeValid(GeomFromText('{wkt}', {srid}))`
- PostgreSQL: `ST_MakeValid(ST_GeomFromText('{wkt}', {srid}))`
- Applied in both `build_expression()` and `_create_permanent_source_table()`

**Files Changed:**
- `modules/backends/spatialite_backend.py`
- `modules/backends/postgresql_backend.py`
- `docs/FIX_INVALID_GEOMETRY_SPATIALITE_2026-01.md`

---

### v2.9.5 - QGIS Shutdown Crash Fix (January 5, 2026)

**Status:** ✅ FIXED

**Problem:**
- Windows fatal access violation during QGIS shutdown
- `QgsMessageLog` C++ object destroyed before `QApplication`
- `cancel()` method called `QgsMessageLog.logMessage()` during task cancellation

**Root Cause:**
- `QgsMessageLog` destruction order is unpredictable during `QgsApplication::~QgsApplication()`
- Even `is_qgis_alive()` check was insufficient

**Solution:**
- Removed all `QgsMessageLog` calls from `cancel()` method in `LayersManagementEngineTask`
- Now uses Python file-based logger (`logger.info()`) which is safe during shutdown

**Files Changed:**
- `modules/tasks/layer_management_task.py`

---

### v2.9.4 - Spatialite Large Dataset Filter Fix (January 5, 2026)

**Status:** ✅ FIXED

**Problem:**
- Filtering layers with ≥20,000 matching features failed silently
- Filter expression used SQL subquery: `"fid" IN (SELECT fid FROM "_fm_fids_xxx")`
- OGR provider doesn't support subqueries in `setSubsetString()` expressions

**Root Cause:**
- v2.8.7 introduced FID table optimization to avoid QGIS freeze
- Subquery only works with direct SQLite connections, not OGR SQL parser

**Solution:**
- Replaced `_build_fid_table_filter()` with `_build_range_based_filter()`
- Range-based uses BETWEEN/IN() clauses: `("fid" BETWEEN 1 AND 500) OR ...`
- DEPRECATED: `_build_fid_table_filter()` method

**Files Changed:**
- `modules/backends/spatialite_backend.py`
- `docs/FIX_SPATIALITE_SUBQUERY_2026-01.md`

---

### v2.9.2 - Centroid Accuracy Fix (January 4, 2026)

**Status:** ✅ FIXED

**Problem:**
- `ST_Centroid()` can return a point OUTSIDE concave polygons (L-shapes, rings)
- This caused incorrect spatial predicate results

**Solution:**
- Now uses `ST_PointOnSurface()` by default for polygon geometries
- Guaranteed to return a point INSIDE the polygon
- Configurable via `CENTROID_MODE` constant

---

## Critical Bug Fixes (v2.8.x Series - January 2026)

### v2.8.1 - Orphaned Materialized View Recovery (January 3, 2026)

**Status:** ✅ FIXED

**Problem:**

- PostgreSQL layers display "relation does not exist" errors after QGIS restart
- Layer subset string references a materialized view that no longer exists
- Example error: `ERROR: relation "public.filtermate_mv_ddccad55" does not exist`

**Root Cause:**

- FilterMate creates materialized views (MVs) for optimized PostgreSQL filtering
- MVs are dropped when QGIS closes or database connection is lost
- Layer's subset string (saved in project file) still references the deleted MV
- On project reopen, QGIS tries to use the stale reference → error

**Solution:**

- Added automatic MV reference detection in subset strings
- `detect_filtermate_mv_reference()` - Identifies FilterMate MV patterns
- `validate_mv_exists()` - Checks if MV exists in database
- `clear_orphaned_mv_subset()` - Clears invalid subset strings
- `validate_and_cleanup_postgres_layers()` - Batch validation on project load
- Integration with `_refresh_ui_after_project_load()` and `_on_layers_added()`
- User notification when orphaned filters are cleared

**Files Changed:**

- `modules/appUtils.py` - New utility functions
- `filter_mate_app.py` - Integration with project/layer load

---

## Critical Bug Fixes (v2.5.x Series - December 2025 / January 2026)

### v2.5.20 - Multi-Backend Extended Canvas Refresh (January 3, 2026)

**Status:** ✅ FIXED

**Problem:**

- Spatialite/OGR layers with complex spatial filters not displaying correctly
- OGR fallback from PostgreSQL/Spatialite showing stale data

**Solution:**

- Extended deferred refresh system to all backends
- Spatialite: Detection of ST\_\*, Intersects(), Contains(), Within(), GeomFromText patterns
- OGR: Detection of large IN clauses (> 50 commas)
- Aggressive refresh with `updateExtents()`, `reload()`, `dataProvider().reloadData()`
- Universal `_final_canvas_refresh()` at 2000ms delay

---

### v2.5.19 - PostgreSQL Complex Filter Display Fix (January 3, 2026)

**Status:** ✅ FIXED

**Problem:**

- Display issues after multi-step filtering with EXISTS/ST_BUFFER expressions
- PostgreSQL provider cache stale after complex spatial queries

**Solution:**

- `_delayed_canvas_refresh()` forces `dataProvider().reloadData()` for PostgreSQL
- Pattern detection for EXISTS, ST_BUFFER, \_\_source markers
- Double-pass refresh (800ms + 2000ms) for reliable display

---

### v2.5.5 - PostgreSQL Negative Buffer Empty Geometry Detection (December 29, 2025)

**Status:** ✅ FIXED

**Problem:**

- PostgreSQL backend incorrectly detected empty geometries from negative buffers
- `NULLIF(geom, 'GEOMETRYCOLLECTION EMPTY')` only detected that exact type
- `POLYGON EMPTY`, `MULTIPOLYGON EMPTY`, etc. were NOT detected

**Root Cause:**

- Negative buffer (erosion) produces different empty geometry types depending on source
- NULLIF pattern was too specific

**Solution:**

- Replaced `NULLIF(...)` with `CASE WHEN ST_IsEmpty(...) THEN NULL ELSE ... END`
- `ST_IsEmpty()` detects ALL empty geometry types (PostGIS standard)
- Applied in 3 functions: `_build_st_buffer_with_style()`, `_build_simple_wkt_expression()`, `build_expression()`

---

### v2.5.4 - OGR Backend Memory Layer Feature Count (December 29, 2025)

**Status:** ✅ FIXED

**Problem:**

- OGR backend reported 0 features in memory layers
- `featureCount()` returns 0 immediately after memory layer creation

**Solution:**

- Automatic memory layer detection via `providerType() == 'memory'`
- Force `updateExtents()` before counting
- Count by iteration for memory layers (more reliable)

---

### v2.5.3 - Negative Buffer Erosion Handling (December 29, 2025)

**Status:** ✅ FIXED

**Improvements:**

- Separate tracking for completely eroded features
- Clear user message when all features eroded
- Detailed logging for erosion vs invalid distinction

---

### v2.5.2 - Negative Buffer for All Backends (December 29, 2025)

**Status:** ✅ FIXED

**Problem:**

- Negative buffer only worked for PostgreSQL direct connections
- OGR backend ignored `buffer_value` parameter

**Solution:**

- OGR `build_expression()` now passes `buffer_value` to `apply_filter()`
- Buffer applied via correct method for each backend

---

## Critical Bug Fixes (v2.4.x Series - December 2025)

### v2.4.11 - Materialized View Cleanup Timing Fix (December 24, 2025)

**Status:** ✅ FIXED

**Problem:**

- PostgreSQL filters were removed immediately after being applied
- Layer-by-layer filtering worked but filters disappeared right after
- Subset string referenced materialized views that no longer existed

**Root Cause:**

- `_cleanup_postgresql_materialized_views()` was called in `finished()` unconditionally
- This deleted ALL materialized views (prefix `filtermate_mv_*`) after filtering completed
- The layer subset strings (e.g., `"id" IN (SELECT "id" FROM schema.filtermate_mv_xxx)`) became invalid
- Result: 0 features shown (view no longer exists)

**Solution:**

- Only call MV cleanup for `reset`, `unfilter`, and `export` actions
- Filtering action (`filter`) now preserves materialized views for persistent filters
- MVs are cleaned up when user explicitly removes filters or exports data

---

### Overview

The v2.4.x series focused heavily on fixing Windows access violation crashes that were occurring during:

- Layer variable operations (setLayerVariable)
- Backend changes (especially to Spatialite)
- Geometric filtering with corrupted/invalid layers
- Parallel execution of OGR operations

All crashes are now resolved with multi-layer defense-in-depth protection.

---

## v2.4.10 - Backend Change Access Violation Fix (December 23, 2025)

**Status:** ✅ FIXED

**Problem:**

- Windows fatal exception during backend change to Spatialite
- `setLayerVariableEvent()` signal emission during widget synchronization

**Root Cause:**

- Despite `blockSignals(True)`, Qt `fieldChanged` signal cascades through event queue
- Layer becomes invalid during signal cascade → CRASH

**Solution:**

1. Robust Layer Validation in `_save_single_property()` with `is_valid_layer()`
2. Pre-emit Validation in `setLayerVariableEvent()` before signal emission
3. Entry Point Validation in `save_variables_from_layer()`

---

## v2.4.9 - Definitive Layer Variable Access Violation Fix (December 23, 2025)

**Status:** ✅ FIXED

**Problem:**

- Race condition between layer validation and C++ call
- Windows access violations are FATAL (cannot be caught by Python try/except)

**Solution - Two-Pronged Fix:**

1. **QTimer.singleShot(0) Deferral** - Schedules callback for next complete event loop iteration
2. **Direct setCustomProperty()** - Wraps C++ calls in try/except that CAN catch RuntimeError

**Defense-in-depth (4 layers):**

1. Task level: QTimer.singleShot(0) defers operations
2. Callback level: is_qgis_alive() check before and during loop
3. Function level: Fresh layer lookup + sip deletion check
4. Operation level: Try/except around direct setCustomProperty() call

---

## v2.4.7 - Layer Variable Race Condition Fix (December 23, 2025)

**Status:** ✅ FIXED

**Problem:**

- Race condition persisted between sip.isdeleted() validation and C++ call

**Solution:**

1. `QApplication.processEvents()` flush before critical C++ operations
2. Post-flush re-validation of layer status
3. Windows-specific stricter validation

---

## v2.4.5 - Processing Parameter Validation Crash Fix (December 23, 2025)

**Status:** ✅ FIXED

**Problem:**

- Access violation in `checkParameterValues` during geometric filtering
- QGIS Processing accesses layer data at C++ level during parameter validation

**Solution - Three-tier Validation:**

1. `_validate_input_layer()` - Deep provider access validation
2. `_validate_intersect_layer()` - Same + geometry checks
3. `_preflight_layer_check()` - Final check before processing.run()

---

## v2.4.4 - Critical Thread Safety Fix (December 23, 2025)

**Status:** ✅ FIXED

**Problem:**

- Parallel filtering access violation crash
- QGIS `QgsVectorLayer` objects are NOT thread-safe

**Solution:**

1. Auto-detection of OGR layers → forces sequential execution
2. Geometric filtering safety detection → sequential mode
3. Thread tracking with concurrent access warnings

---

## v2.4.3 - Export System Fix (December 22, 2025)

**Status:** ✅ FIXED

**Fixes:**

- Missing file extensions in exports (.shp, .gpkg, etc.)
- Driver name mapping for all formats
- Streaming export datatype argument
- Message bar argument order

---

## v2.3.9 - Access Violation Crash on Plugin Reload (December 19, 2025)

**Status:** ✅ FIXED

**Problem:**

- QGIS crashed during plugin reload or shutdown
- Lambdas in QTimer.singleShot captured self reference

**Solution:**

1. Weak References for all QTimer callbacks
2. Safety checks in callbacks (try/except RuntimeError)
3. Safe message display utility

---

## Modules for Safety Operations

### modules/object_safety.py

New module (v2.4.x) providing safe wrappers for C++ operations:

- `is_qgis_alive()` - Check if QGIS application is running
- `is_sip_deleted()` - Check if SIP object was deleted
- `is_valid_qobject()` - Validate QObject
- `is_valid_layer()` - Full layer validation (C++ object + project)
- `is_layer_in_project()` - Check layer still in project
- `safe_layer_access()` - Context manager for safe layer access
- `safe_disconnect()` - Safe signal disconnection
- `safe_emit()` - Safe signal emission
- `safe_set_layer_variable()` - Safe layer variable setting
- `safe_set_layer_variables()` - Safe multiple variables
- `safe_block_signals()` - Safe signal blocking
- `make_safe_callback()` / `make_safe_lambda()` - Safe callback creation
- `SafeLayerContext` / `SafeSignalContext` - Context managers

---

## Negative Buffer (Erosion) Handling - v2.5.5

**Status:** ✅ FULLY IMPLEMENTED (All backends)

### Implementation Details

All backends properly handle negative buffers:

1. **Wrap in MakeValid()** - Ensures valid geometry after erosion
2. **Use ST_IsEmpty()** - Detects ALL empty geometry types (v2.5.5 fix)
3. **Return NULL** - Prevents false positive spatial matches

| Backend    | Validity Function | Empty Check            | Buffer Application         |
| ---------- | ----------------- | ---------------------- | -------------------------- |
| PostgreSQL | `ST_MakeValid()`  | `ST_IsEmpty(geom)`     | SQL ST_Buffer()            |
| Spatialite | `MakeValid()`     | `ST_IsEmpty(geom) = 1` | SQL ST_Buffer()            |
| OGR        | QGIS native       | Feature iteration      | native:buffer (Processing) |

**Key Fix (v2.5.5):** PostgreSQL now uses `ST_IsEmpty()` instead of `NULLIF` to detect:

- `POLYGON EMPTY`
- `MULTIPOLYGON EMPTY`
- `LINESTRING EMPTY`
- `GEOMETRYCOLLECTION EMPTY`
- All other empty geometry types

See: `.serena/memories/negative_buffer_wkt_handling.md` for full documentation.

---

## Known Remaining Issues

### Low Priority

1. **TODO: User-configurable settings** (filter_mate.py:97) - Future feature
2. **TODO: Dock location choice** (filter_mate_app.py:355) - Now implemented via config

### Performance Considerations

- Large OGR datasets (> 50k features) may be slow without PostgreSQL
- Parallel execution disabled for OGR backends (thread safety)

---

## Testing Recommendations

For any new crash fixes, test:

1. Rapid plugin reload (10x)
2. Close QGIS during layer loading
3. Reload plugin during active filtering
4. Quick project switching
5. Backend change to Spatialite/OGR
6. Geometric filtering with invalid layers
7. Export with large datasets

---

## Documentation

Crash fix documentation in `docs/fixes/`:

- `FIX_ACCESS_VIOLATION_CRASH_2025-12-19.md`
- Various other fix documentation files
