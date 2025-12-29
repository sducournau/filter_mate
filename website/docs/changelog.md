---
sidebar_position: 100
---

# Changelog

All notable changes to FilterMate are documented here.

## [2.5.5] - December 29, 2025 - Critical PostgreSQL Negative Buffer Fix

### 🐛 Critical Bug Fix

- **CRITICAL: PostgreSQL backend now correctly detects ALL empty geometry types from negative buffers**
  - **Symptom**: Negative buffer (erosion) on PostgreSQL could filter features incorrectly
  - **Cause**: `NULLIF(geom, 'GEOMETRYCOLLECTION EMPTY')` only detected that exact type
  - **Impact**: POLYGON EMPTY, MULTIPOLYGON EMPTY, LINESTRING EMPTY were not detected
  - **Solution**: Uses `CASE WHEN ST_IsEmpty(...) THEN NULL ELSE ... END`
  - **Benefit**: All empty geometry types now correctly converted to NULL

### 🎨 UI Improvements

- **HiDPI UI Profile** - New profile for 4K/Retina displays with auto-detection
  - Auto-detects `devicePixelRatio >= 1.5` or physical resolution >= 3840px
  - Scaled dimensions for buttons, icons, and spacing
- **Compact Sidebar Buttons** - Smaller, centered buttons with reduced spacing
- **Equal Splitter Ratio** - 50/50 distribution between exploring and toolset frames
- **Harmonized Button Layouts** - Consistent spacing across exploring/filtering/exporting tabs

### 🔧 Thread Safety

- **Warning Messages** - Stored during worker thread execution, displayed in main thread
  - Prevents crashes from calling `iface.messageBar()` in worker threads

---

## [2.5.4] - December 29, 2025 - Critical OGR Backend Memory Layer Fix

### 🐛 Critical Bug Fix

- **CRITICAL: OGR backend now correctly counts features in memory layers**
  - **Symptom**: All OGR filters failed with "backend returned FAILURE"
  - **Cause**: `featureCount()` returns 0 immediately after memory layer creation
  - **Solution**: Intelligent retry mechanism with `updateExtents()` before counting

---

## [2.3.7] - December 18, 2025 - Project Change Stability Enhancement

### 🛡️ Stability Improvements

- **Enhanced Project Change Handling** - Complete rewrite of project change detection

  - Forces cleanup of previous project state before reinitializing
  - Clears layer cache, task queue, and all state flags
  - Resets dockwidget layer references to prevent stale data

- **New `cleared` Signal Handler** - Proper cleanup on project close/clear

  - Ensures plugin state is reset when project is closed or new project created
  - Disables UI widgets while waiting for new layers

- **Updated Timing Constants** - Improved delays for better stability with PostgreSQL

### ✨ New Features

- **Force Reload Layers (F5 Shortcut)** - Manual layer reload when project change fails
  - Press F5 in dockwidget to force complete layer reload
  - Shows status indicator during reload ("⟳")
  - Useful recovery option when automatic project change detection fails

### 🐛 Bug Fixes

- **Fixed Project Change Not Reloading Layers** - More aggressive cleanup prevents stale state
- **Fixed Dockwidget Not Updating After Project Switch** - Full reset of layer references
- **Fixed Signal Timing Issue** - QGIS emits `layersAdded` signal BEFORE `projectRead` handler completes

---

## [2.3.6] - December 18, 2025 - Project & Layer Loading Stability

### 🛡️ Stability Improvements

- **Centralized Timing Constants** - All timing values now in `STABILITY_CONSTANTS` dict

  - `MAX_ADD_LAYERS_QUEUE`: 50 (prevents memory overflow)
  - `FLAG_TIMEOUT_MS`: 30000 (30-second timeout for stale flags)

- **Timestamp-Tracked Flags** - Automatic stale flag detection and reset

  - Prevents plugin from getting stuck in "loading" state
  - Auto-resets flags after 30 seconds

- **Layer Validation** - Better C++ object validation

  - Prevents crashes from accessing deleted layer objects

- **Signal Debouncing** - Rapid signal handling
  - Queue size limit with automatic trimming (FIFO)
  - Graceful handling of rapid project/layer changes

### 🐛 Bug Fixes

- **Fixed Stuck Flags** - Flags now auto-reset after 30-second timeout
- **Fixed Queue Overflow** - add_layers queue capped at 50 items
- **Fixed Error Recovery** - Flags properly reset on exception

---

## [2.3.5] - December 17, 2025 - Code Quality & Configuration v2.0

### 🛠️ Centralized Feedback System

- **Unified Message Bar Notifications** - Consistent user feedback across all modules
  - New `show_info()`, `show_warning()`, `show_error()`, `show_success()` functions
  - Graceful fallback when iface is unavailable

### ⚡ PostgreSQL Init Optimization

- **5-50× Faster Layer Loading** - Smarter initialization for PostgreSQL layers
  - Check index existence before creating
  - Connection caching per datasource
  - Skip CLUSTER at init (deferred to filter time)
  - Conditional ANALYZE only if table has no statistics

### ⚙️ Configuration System v2.0

- **Integrated Metadata Structure** - Metadata embedded directly in parameters
- **Automatic Configuration Migration** - v1.0 → v2.0 migration system
- **Forced Backend Respect** - User choice strictly enforced (no fallback to OGR)

### 🐛 Bug Fixes

- **Fixed Syntax Errors** - Corrected unmatched parentheses
- **Fixed Bare Except Clauses** - Specific exception handling

### 🧹 Code Quality

- **Score Improvement**: 8.5 → 8.9/10

---

## [2.3.4] - December 16, 2025 - PostgreSQL 2-Part Table Reference Fix

### 🐛 Bug Fixes

- **CRITICAL: Fixed PostgreSQL 2-part table references** - Spatial filtering now works correctly with tables using `"table"."geom"` format
- **Fixed GeometryCollection buffer results** - Now properly extracts polygons and converts to MultiPolygon
- **Fixed PostgreSQL virtual_id error** - Informative error for layers without primary key

### ✨ New Features

- **Smart display field selection** - New layers auto-select the best descriptive field (name, label, titre, etc.)
- **Automatic ANALYZE on source tables** - PostgreSQL query planner now has proper statistics

### ⚡ Performance Improvements

- **~30% Faster PostgreSQL Layer Loading**
  - Fast feature count using `pg_stat_user_tables` (500× faster than COUNT(\*))
  - UNLOGGED materialized views (30-50% faster creation)

---

## [2.3.3] - December 15, 2025 - Project Loading Auto-Activation Fix

### 🐛 Bug Fixes

- **CRITICAL: Fixed plugin auto-activation on project load** - Plugin now correctly activates when loading a QGIS project containing vector layers

---

## [2.3.2] - December 15, 2025 - Interactive Backend Selector

### ✨ New Features

- **Interactive Backend Selector** - Backend indicator is now clickable to manually force a specific backend

  - Click on backend badge to open context menu with available backends
  - Forced backends marked with ⚡ lightning bolt symbol
  - Per-layer backend preferences

- **🎯 Auto-select Optimal Backends** - Automatically optimize all layers
  - Analyzes each layer's characteristics (provider type, feature count)
  - Intelligently selects the best backend for each layer

### 🎨 UI Improvements

- **Enhanced Backend Indicator**
  - Added hover effect with cursor change to pointer
  - Visual feedback for forced backend with ⚡ symbol

---

## [2.3.1] - December 14, 2025 - Stability & Backend Improvements

### 🐛 Bug Fixes

- **CRITICAL: Fixed GeometryCollection error in OGR backend buffer operations**
  - Added automatic conversion from GeometryCollection to MultiPolygon
- **CRITICAL: Fixed potential KeyError crashes in PROJECT_LAYERS access**
  - Added guard clauses to verify layer existence before dictionary access
- **Fixed GeoPackage geometric filtering** - GeoPackage layers now use fast Spatialite backend (10× performance improvement)

### 🛠️ Improvements

- **Improved exception handling throughout codebase** - Replaced generic exception handlers with specific types

---

## [2.3.0] - December 13, 2025 - Global Undo/Redo & Automatic Filter Preservation

### 🚀 Major Features

#### Global Undo/Redo Functionality

Intelligent undo/redo system with context-aware behavior:

- **Source Layer Only Mode**: Undo/redo applies only to the source layer when no remote layers are selected
- **Global Mode**: When remote layers are selected and filtered, undo/redo restores the complete state of all layers simultaneously
- **Smart Button States**: Undo/redo buttons automatically enable/disable based on history availability
- **Multi-Layer State Capture**: New `GlobalFilterState` class captures source + remote layers state atomically
- **Automatic Context Detection**: Seamlessly switches between source-only and global modes

#### Automatic Filter Preservation ⭐ NEW

Critical feature preventing filter loss during layer switching and multi-step filtering workflows:

- **Problem Solved**: Previously, applying a new filter would replace existing filters
- **Solution**: Filters are now automatically combined using logical operators (AND by default)
- **Available Operators**: AND (default), OR, AND NOT
- **Use Case Example**:
  1. Filter by polygon geometry → 150 features
  2. Switch to another layer
  3. Apply attribute filter `population > 10000`
  4. Result: 23 features (intersection of both filters preserved!)

#### Reduced Notification Fatigue ⭐ NEW

Configurable feedback system with verbosity control:

- **Three Levels**: Minimal (-92% messages), Normal (default, -42%), Verbose
- **Configurable via**: `config.json` → `APP.DOCKWIDGET.FEEDBACK_LEVEL`

### ✨ Enhancements

- **Auto-Activation**: Plugin now auto-activates when vector layers are added to empty project
- **Debug Cleanup**: All debug print statements converted to proper logging

### 🐛 Bug Fixes

- **QSplitter Freeze**: Fixed freeze when ACTION_BAR_POSITION set to 'left' or 'right'
- **Project Load Race Condition**: Fixed freeze when loading projects with layers
- **Global Undo Remote Layers**: Fixed undo not restoring all remote layers

### 🛠️ Code Quality

- Comprehensive codebase audit with overall score **4.2/5**
- All `!= None` and `== True/False` comparisons fixed to PEP 8 style

---

## [2.2.5] - December 8, 2025 - Automatic Geographic CRS Handling

### 🚀 Major Improvements

- **Automatic EPSG:3857 Conversion**: FilterMate now automatically detects geographic coordinate systems (EPSG:4326, etc.) and switches to EPSG:3857 for metric-based operations
  - **Why**: Ensures accurate buffer distances in meters instead of imprecise degrees
  - **Benefit**: 50m buffer is always 50 meters, regardless of latitude!
  - **User impact**: Zero configuration - works automatically

### 🐛 Bug Fixes

- **Geographic Coordinates Zoom & Flash**: Fixed critical issues with EPSG:4326
  - Feature geometry was modified in-place during transformation
  - Buffer distances in degrees varied with latitude
  - Solution: Use geometry copy, auto-switch to EPSG:3857 for buffers

---

## [2.2.4] - December 8, 2025 - Spatialite Expression Fix

### 🐛 Bug Fixes

- **CRITICAL: Spatialite Expression Quotes**: Fixed bug where double quotes around field names were removed
  - Issue: `"HOMECOUNT" > 100` was incorrectly converted to `HOMECOUNT > 100`
  - Impact: Filters failed on Spatialite layers with case-sensitive field names
  - Solution: Preserved field name quotes in expression conversion

### 🧪 Testing

- Added comprehensive test suite for Spatialite expression conversion
- Validated field name quote preservation

---

## [2.2.3] - December 8, 2025 - Color Harmonization & Accessibility

### 🎨 UI Improvements

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

- ✅ Reduced eye strain with optimized color contrasts
- ✅ Clear visual hierarchy throughout the interface
- ✅ Better distinction for users with mild visual impairments
- ✅ Long work session comfort improved

### 🧪 Testing & Documentation

- **New Test Suite**: `test_color_contrast.py` validates WCAG compliance
- **Visual Preview**: `generate_color_preview.py` creates interactive HTML comparison
- **Documentation**: Complete color harmonization guide

## [2.2.2] - December 8, 2025 - Configuration Reactivity

### ✨ New Features

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

### 🎨 Initial Color Harmonization Work

- Enhanced contrast between UI elements in normal mode
- WCAG AAA compliance (17.4:1 for primary text)
- Better frame/widget distinction

## [2.2.1] - December 7, 2025 - Maintenance Release

### 🔧 Maintenance

- ✅ Release Management: Improved release tagging and deployment procedures
- ✅ Build Scripts: Enhanced build automation and version management
- ✅ Documentation: Updated release documentation and procedures
- ✅ Code Cleanup: Minor code formatting and organization improvements

## [2.2.0] - December 2025

### Added

- ✅ Enhanced Qt JSON view crash prevention
- ✅ Improved tab widget error recovery
- ✅ Robust theme handling and synchronization
- ✅ Complete multi-backend architecture documentation

### Improved

- ⚡ 2.5× faster performance with intelligent query ordering
- 🎨 Dynamic UI adaptation based on screen resolution
- 🔧 Better error recovery for SQLite locks
- 📝 Enhanced logging and debugging capabilities

### Fixed

- 🐛 Qt JSON view crash on theme switching
- 🐛 Tab widget initialization issues
- 🐛 Geometry repair edge cases
- 🐛 CRS reprojection warnings

## [2.1.0] - November 2025

### Added

- 🎨 Adaptive UI with dynamic dimensions
- 🌓 Automatic theme synchronization with QGIS
- 📝 Filter history with undo/redo
- 🚀 Performance warnings for large datasets

### Improved

- ⚡ Multi-backend support (PostgreSQL, Spatialite, OGR)
- 📊 Enhanced performance monitoring
- 🔍 Better spatial predicate handling

## [1.9.0] - October 2025

### Added

- 🏗️ Factory pattern for backend selection
- 📈 Automatic performance optimizations
- 🔧 SQLite lock retry mechanisms

### Performance

- ⚡ 44.6× faster Spatialite filtering (R-tree indexes)
- ⚡ 19.5× faster OGR operations (spatial indexes)
- ⚡ 2.3× faster with predicate ordering

## [1.8.0] - September 2025

### Added

- 🎨 Layer-specific widget configuration
- 💾 Persistent settings per layer
- 🔄 Automatic CRS reprojection

## Earlier Versions

For complete version history, see the [GitHub Releases](https://github.com/sducournau/filter_mate/releases) page.

---

## Version Numbering

FilterMate follows [Semantic Versioning](https://semver.org/):

- **Major.Minor.Patch** (e.g., 2.1.0)
- **Major**: Breaking changes
- **Minor**: New features (backward compatible)
- **Patch**: Bug fixes

## Upgrade Guide

### From 1.x to 2.x

Version 2.0 introduced the multi-backend architecture. To upgrade:

1. Update via QGIS Plugin Manager
2. (Optional) Install psycopg2 for PostgreSQL support
3. Existing settings will be migrated automatically

### From 2.0 to 2.1+

No breaking changes. Update directly via Plugin Manager.

## Reporting Issues

Found a bug or have a feature request?

- [GitHub Issues](https://github.com/sducournau/filter_mate/issues)
- [Discussion Forum](https://github.com/sducournau/filter_mate/discussions)
