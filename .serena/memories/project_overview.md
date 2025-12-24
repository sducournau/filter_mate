# FilterMate Project Overview

## Purpose
FilterMate is a production-ready QGIS plugin that provides advanced filtering and export capabilities for vector data. It allows users to:
- Explore, filter, and export vector layers intuitively
- Filter layers by expressions and geometric predicates with buffer support
- Configure widgets independently for each layer
- Export layers with customizable options
- Work with multiple data sources (PostgreSQL/PostGIS, Spatialite, Shapefiles, GeoPackage, OGR)

## Tech Stack
- **Language**: Python 3.7+
- **Framework**: PyQGIS (QGIS API 3.0+), PyQt5
- **Database Support**: 
  - PostgreSQL/PostGIS (via psycopg2 - optional)
  - Spatialite (built-in SQLite with spatial extension)
  - OGR (Shapefiles, GeoPackage, etc.)
- **Architecture**: Multi-backend with factory pattern and automatic selection

## Current Status
- **Version**: 2.4.10 (December 23, 2025)
- **Status**: Production - Stable with critical Windows access violation fixes
- **All Phases Complete**: PostgreSQL, Spatialite, and OGR backends fully operational
- **Recent Focus (v2.4.x)**: Windows crash fixes, thread safety, layer validation
- **Languages Supported**: 21 languages (including Slovenian, Filipino, Amharic)

## Recent Development (December 23, 2025)

### v2.4.10 - Backend Change Access Violation Fix (✅ Complete)
**Date**: December 23, 2025

**Problem Solved:**
- Windows fatal exception during backend change to Spatialite
- Race condition in `setLayerVariableEvent()` signal emission

**Solutions Implemented:**
1. **Robust Layer Validation** - `is_valid_layer()` check in `_save_single_property()`
2. **Pre-emit Validation** - Layer validation before signal emission
3. **Entry Point Validation** - Full C++ deletion detection

---

### v2.4.9 - Definitive Layer Variable Access Violation Fix (✅ Complete)
**Date**: December 23, 2025

**Problem Solved:**
- Race condition between layer validation and C++ call
- Windows access violations are FATAL (cannot be caught by Python)

**Solutions Implemented:**
1. **QTimer.singleShot(0) Deferral** - Complete event loop separation
2. **Direct setCustomProperty()** - Wrapped C++ calls with try/except
3. **Defense-in-depth**: 4 layers of protection against race conditions

---

### v2.4.5 - Processing Parameter Validation Crash Fix (✅ Complete)
**Date**: December 23, 2025

**Problem Solved:**
- Access violation in `checkParameterValues` during geometric filtering
- Corrupted/invalid layers causing GEOS/PDAL crashes

**Solutions Implemented:**
1. **Pre-flight Layer Validation** - Three-tier validation before `processing.run()`
2. **Deep Provider Access Validation** - Tests all layer properties before C++ access

---

### v2.4.4 - Critical Thread Safety Fix (✅ Complete)
**Date**: December 23, 2025

**Problem Solved:**
- Parallel filtering access violation crash
- QGIS `QgsVectorLayer` objects are NOT thread-safe

**Solutions Implemented:**
1. **Sequential Execution for OGR** - Auto-detection forces sequential for unsafe operations
2. **Thread Tracking** - Logs warnings for concurrent access attempts

---

### v2.4.3 - Export System Fix & Message Bar Improvements (✅ Complete)
**Date**: December 22, 2025

**Fixes:**
- Missing file extensions in exports
- Driver name mapping for all formats
- Correct message bar argument order

---

### v2.4.2 - Exploring ValueRelation & Display Enhancement (✅ Complete)
**Date**: December 22, 2025

**Features:**
- Smart display expression detection for exploring widgets
- ValueRelation support with `represent_value()` display
- Intelligent field selection priority order

---

### v2.4.1 - International Edition Extended (✅ Complete)
**Date**: December 22, 2025

**Features:**
- 3 new languages: Slovenian, Filipino/Tagalog, Amharic
- Total: 21 languages supported
- Fixed hardcoded French strings

---

### v2.4.0 - Major Refactoring Release
**Date**: December 20-21, 2025

Consolidated all v2.3.x stability improvements into production release.

---

### Configuration System v2.0 (✅ Complete)
**Date**: December 17, 2025

**New Components:**
- **Integrated Metadata Structure**: Metadata embedded directly in parameters (no fragmented `_*_META` sections)
- **ConfigMetadataHandler**: `modules/config_metadata_handler.py` - Intelligent extraction and tooltips
- **Migration System**: `modules/config_migration.py` - Automatic v1.0 → v2.0 migration with backup/rollback
- **Auto-Reset**: Obsolete/corrupted configs automatically detected and reset with backup
- **Forced Backend Respect**: User backend choice strictly enforced (no fallback)

**Features:**
- Auto-detect configuration version (v1.0, v2.0, unknown)
- Automatic backup before migration
- Pattern uniforme: `{value, choices, description, ...}`
- 47 usage cases documented and validated
- Real-time validation with WCAG-compliant error messages

**Documentation (30+ files):**
- `docs/CONFIG_DEVELOPER_GUIDE_2025-12-17.md` - Quick reference for developers
- `docs/CONFIG_INTEGRATION_ANALYSIS_2025-12-17.md` - Complete integration analysis
- `docs/CONFIG_USAGE_CASES_2025-12-17.md` - 47 usage patterns documented
- `docs/INTEGRATION_SUMMARY_2025-12-17.md` - Executive summary
- `docs/fixes/FIX_FORCED_BACKEND_RESPECT_2025-12-17.md` - Backend respect fix

**Testing:**
- `tests/test_auto_config_reset.py` - Migration and reset tests
- `tests/test_config_improved_structure.py` - Structure validation
- `tests/test_forced_backend_respect.py` - Backend respect tests

### Performance & Stability Audit (✅ Complete)
**Date**: December 17, 2025

**Actions Performed:**
- Complete codebase audit for performance, stability, TODOs, duplicates
- Generated comprehensive report: `docs/AUDIT_PERFORMANCE_STABILITY_2025-12-17.md`
- Implemented 2 critical TODOs:
  1. Configuration saving in config editor (P0)
  2. Validation error user feedback (P1)

**Findings:**
- **Overall Score**: 8.5/10 → 9.0/10 (after fixes)
- **Performance**: 9/10 (optimizations 3-45× already in place)
- **Stability**: 9/10 (40+ try/finally blocks, improved error handling)
- **Test Coverage**: ~70% (target: 80%)
- **Critical TODOs**: 0/2 remaining (all implemented)
- **Non-Critical TODOs**: 2/4 (tracked for backlog)

**Documentation:**
- `docs/AUDIT_PERFORMANCE_STABILITY_2025-12-17.md` - Complete audit
- `docs/AUDIT_IMPLEMENTATION_2025-12-17.md` - TODOs implementation details
- Updated `.serena/memories/code_quality_improvements_2025.md`

### PostgreSQL Loading Optimizations (December 16-17, 2025)
**Date**: December 16-17, 2025

**Optimizations Implemented:**
1. **Fast Feature Count**: Uses `pg_stat_user_tables` (500× faster than COUNT(*))
2. **UNLOGGED MVs**: 30-50% faster materialized view creation
3. **Smart Caching**: Eliminates double feature counting

**Performance Impact:**
- **Overall**: ~30% reduction in loading time
- **Feature counting**: 2.5s → 5ms (500× faster)
- **MV creation**: 30s → 18s (40% faster)
- **1M features**: 46s → 32s total loading time

**Documentation:**
- `docs/POSTGRESQL_LOADING_OPTIMIZATION.md` - Complete technical guide
- `docs/POSTGRESQL_LOADING_OPTIMIZATION_SUMMARY.md` - Executive summary

## Key Features

### Core Functionality
- Multi-backend support with automatic selection (PostgreSQL/Spatialite/OGR)
- Asynchronous task execution (QgsTask) for non-blocking operations
- Layer property persistence with JSON configuration
- Filter history with full undo/redo support (global state management)
- Automatic CRS reprojection on the fly
- Performance warnings and recommendations for large datasets
- Configuration migration with automatic backup/rollback

### User Experience
- Dynamic UI dimensions (adaptive to screen resolution)
- Theme synchronization with QGIS interface
- Real-time configuration updates (no restart required)
- Auto-generated configuration UI from metadata
- ChoicesType dropdowns for validated settings
- WCAG 2.1 AA/AAA accessibility compliance
- Comprehensive error messages with user feedback

### Technical Features
- Robust geometry repair for buffer operations
- SQLite lock retry mechanism (5 attempts with exponential backoff)
- Intelligent predicate ordering for optimal query performance
- Spatial index automation
- Source geometry caching for multi-layer operations (5× speedup)
- Field name quote preservation for case-sensitive databases
- Automatic geographic CRS to metric conversion
- PostgreSQL statistics-based fast counting
- UNLOGGED materialized views for temporary data

## Configuration System v2.0

### Features
- **Integrated Metadata**: Metadata embedded directly in parameters (no fragmented sections)
- **Auto-detection**: Version detection (v1.0, v2.0, unknown) with automatic migration
- **Auto-reset**: Obsolete/corrupted configs automatically reset with backup
- **Forced Backend Respect**: User backend choice strictly enforced
- **Validation**: Complete value validation with clear error messages
- **User-friendly**: Labels, descriptions, tooltips for all parameters

### Components
- `config/config.default.json`: Config with integrated metadata structure
- `modules/config_metadata_handler.py`: Intelligent extraction and tooltips
- `modules/config_helpers.py`: Helper functions (get_config_value, set_config_value)
- `modules/config_migration.py`: Version migration system with backup
- `modules/config_editor_widget.py`: Auto-generated UI

### Config Value Pattern
```json
{
  "PARAMETER": {
    "value": "default",
    "choices": ["option1", "option2"],
    "description": "User-friendly description"
  }
}
```

### Access Patterns
```python
# Reading (handles both v1.0 and v2.0)
value = get_config_value(config, "APP", "DOCKWIDGET", "PARAMETER")

# Writing (preserves metadata)
set_config_value(config, new_value, "APP", "DOCKWIDGET", "PARAMETER")
```

## Architecture Patterns

### Factory Pattern
- Automatic backend selection based on layer provider
- Consistent interface across all backends
- Easy to extend with new backends

### Task Pattern
- All heavy operations run as QgsTask
- Non-blocking UI
- Progress reporting and cancellation support

### Signal/Slot Pattern
- Clean separation between UI and logic
- Signal utilities for safe blocking/unblocking
- Automatic resource cleanup

### Metadata Pattern
- Configuration metadata drives UI generation
- Single source of truth for all config parameters
- Automatic validation and documentation

## Performance Characteristics

### PostgreSQL Backend
- **Best for:** > 50,000 features
- **Performance:** Sub-second queries on millions of features (30% faster with v2.3.5)
- **Implementation:** UNLOGGED materialized views with GIST indexes, fast statistics-based counting

### Spatialite Backend
- **Best for:** 10,000 - 50,000 features
- **Performance:** 1-10s for 100k features
- **Implementation:** Temporary tables with R-tree indexes

### OGR Backend
- **Best for:** < 10,000 features
- **Performance:** Universal compatibility
- **Implementation:** QGIS processing framework

## Documentation Structure

### Core Documentation
- `README.md`: User-facing introduction
- `CHANGELOG.md`: Complete version history
- `docs/INDEX.md`: Documentation index

### Configuration Documentation (NEW)
- `docs/CONFIG_SYSTEM.md`: Complete configuration system guide
- `docs/CONFIG_MIGRATION.md`: Migration guide with examples
- `docs/CONFIG_OVERVIEW.md`: System overview
- `docs/CONFIG_INTEGRATION_EXAMPLES.py`: Integration code examples
- `docs/QUICK_INTEGRATION.md`: 5-minute integration guide
- `config/README_CONFIG.md`: Quick start guide

### Performance Documentation (NEW)
- `docs/POSTGRESQL_LOADING_OPTIMIZATION.md`: Detailed optimization guide
- `docs/POSTGRESQL_LOADING_OPTIMIZATION_SUMMARY.md`: Executive summary
- `docs/AUDIT_PERFORMANCE_STABILITY_2025-12-17.md`: Complete audit report
- `docs/AUDIT_IMPLEMENTATION_2025-12-17.md`: TODOs implementation

### Technical Documentation
- `docs/architecture.md`: System architecture
- `docs/BACKEND_API.md`: Backend API reference
- `docs/IMPLEMENTATION_STATUS_2025-12-10.md`: Feature completion status
- `docs/CODEBASE_QUALITY_AUDIT_2025-12-10.md`: Quality audit

### Developer Documentation
- `docs/DEVELOPER_ONBOARDING.md`: Getting started guide
- `.github/copilot-instructions.md`: Coding guidelines
- `tests/README.md`: Testing guide
- `modules/tasks/README.md`: Task module documentation

## Testing

### Test Categories
- Configuration system tests (migration, metadata, helpers)
- Backend tests (PostgreSQL, Spatialite, OGR)
- Expression conversion tests
- Color contrast/WCAG compliance tests
- Performance optimization tests
- Layer handling tests
- **Total**: 30+ comprehensive tests

### Running Tests
```bash
# All tests
pytest tests/ -v

# Configuration tests
pytest tests/test_config*.py -v

# Coverage
pytest --cov=modules --cov-report=html
```

## Code Quality Metrics (December 17, 2025)

| Metric | Score | Status |
|--------|-------|--------|
| Overall Quality | 9.0/10 | ✅ Excellent |
| PEP 8 Compliance | 95% | ✅ |
| Wildcard Imports | 6% (2/33) | ✅ |
| Bare except clauses | 0% | ✅ |
| Test Coverage | ~70% | 🎯 Target 80% |
| Critical TODOs | 0/2 | ✅ |
| Performance | 9/10 | ✅ |
| Stability | 9/10 | ✅ |
| Error Handling | 9/10 | ✅ |
| Documentation | 90% | ✅ |

## Repository Information
- **Repository**: https://github.com/sducournau/filter_mate
- **Issues**: https://github.com/sducournau/filter_mate/issues
- **Website**: https://sducournau.github.io/filter_mate
- **License**: See LICENSE file
- **Author**: imagodata (simon.ducournau+filter_mate@gmail.com)
- **QGIS Min Version**: 3.0
- **Current Plugin Version**: 2.4.10

## BMAD Documentation

FilterMate uses BMAD methodology with documents in `.bmad-core/`:

| Document | Content |
|----------|---------|
| `project.bmad.md` | Project vision and goals |
| `prd.md` | 40+ requirements (functional & non-functional) |
| `architecture.md` | Technical architecture with diagrams |
| `epics.md` | 6 epics, 23 user stories |
| `roadmap.md` | 8 completed phases, future plans |
| `quality.md` | Code standards, testing guidelines |
| `personas.md` | 5 user personas |
| `tech-stack.md` | Complete technology stack |

See `.serena/memories/bmad_integration.md` for Serena-BMAD mapping.

## Serena Integration

### Windows MCP Configuration
FilterMate is configured for automatic Serena MCP server activation:
- **Location**: `%APPDATA%/Code/User/globalStorage/github.copilot.chat.mcp/config.json`
- **Command**: `uvx serena`
- **Project Path**: Set via `SERENA_PROJECT` environment variable
- **Auto-start**: Activates when Copilot Chat opens in VS Code

### Coding Workflow
- Use `get_symbols_overview()` before reading large files
- Leverage symbolic tools for token-efficient code exploration
- Read `.github/copilot-instructions.md` for coding guidelines
- Check `POSTGRESQL_AVAILABLE` before PostgreSQL operations
- Use Serena's symbolic search for efficient code navigation
