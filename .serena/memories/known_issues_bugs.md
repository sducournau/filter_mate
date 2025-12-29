# Known Issues & Bug Fixes - FilterMate

**Last Updated:** December 23, 2025

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

**Status:** ✅ FULLY IMPLEMENTED

### Implementation Details

Both PostgreSQL and Spatialite backends properly handle negative buffers:

1. **Wrap in MakeValid()** - Ensures valid geometry after erosion
2. **Use ST_IsEmpty()** - Detects all empty geometry types (v2.5.4 fix)
3. **Return NULL** - Prevents false positive spatial matches

| Backend | Validity Function | Empty Check |
|---------|-------------------|-------------|
| PostgreSQL | `ST_MakeValid()` | `ST_IsEmpty(geom)` |
| Spatialite | `MakeValid()` | `ST_IsEmpty(geom) = 1` |

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
