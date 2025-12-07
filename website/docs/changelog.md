---
sidebar_position: 100
---

# Changelog

All notable changes to FilterMate are documented here.

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
