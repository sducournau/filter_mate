---
sidebar_position: 100
---

# Changelog

All notable changes to FilterMate are documented here.

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
