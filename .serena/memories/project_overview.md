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

## Project Structure
```
filter_mate/
├── filter_mate.py              # Plugin entry point (QGIS integration)
├── filter_mate_app.py          # Main application orchestrator (~1687 lines)
├── filter_mate_dockwidget.py   # UI dockwidget management (~3877 lines)
├── filter_mate_dockwidget_base.py  # Base UI class (auto-generated)
├── filter_mate_dockwidget_base.ui  # Qt Designer UI file
├── config/
│   ├── config.json             # Plugin configuration (dynamic, reactive)
│   └── config.py               # Configuration loader
├── modules/
│   ├── appTasks.py             # Async filtering tasks (QgsTask) (~5678 lines)
│   ├── appUtils.py             # Database connections and utilities
│   ├── backends/               # Multi-backend architecture
│   │   ├── base_backend.py    # Abstract base class
│   │   ├── factory.py         # Backend factory (auto-selection)
│   │   ├── postgresql_backend.py  # PostgreSQL/PostGIS backend
│   │   ├── spatialite_backend.py  # Spatialite backend
│   │   └── ogr_backend.py     # OGR universal fallback
│   ├── tasks/                  # Task modules (NEW in v2.3.0-alpha)
│   │   ├── __init__.py         # Re-exports & backwards compatibility
│   │   ├── task_utils.py       # Common utilities (328 lines)
│   │   ├── geometry_cache.py   # SourceGeometryCache (146 lines)
│   │   ├── layer_management_task.py  # LayersManagementEngineTask (1125 lines)
│   │   └── README.md           # Task module documentation
│   ├── config_helpers.py       # Configuration utilities (v2.2.2)
│   ├── constants.py            # Application constants
│   ├── customExceptions.py     # Custom exception classes
│   ├── feedback_utils.py       # User feedback utilities
│   ├── filter_history.py       # Filter history with undo/redo
│   ├── logging_config.py       # Logging configuration
│   ├── prepared_statements.py  # SQL prepared statements
│   ├── signal_utils.py         # Qt signal management utilities
│   ├── state_manager.py        # Application state management
│   ├── ui_config.py            # Dynamic UI dimensions
│   ├── ui_elements.py          # UI element creation
│   ├── ui_elements_helpers.py  # UI helper functions
│   ├── ui_styles.py            # Theme management
│   ├── ui_widget_utils.py      # Widget utilities
│   ├── widgets.py              # Custom widgets
│   └── qt_json_view/           # JSON tree view widgets
├── resources/
│   └── styles/                 # QSS theme files
├── icons/                      # Plugin icons
├── i18n/                       # Translations
├── tests/                      # Unit tests (26+ tests)
├── docs/                       # Comprehensive documentation
├── website/                    # Docusaurus documentation site
├── .github/
│   ├── copilot-instructions.md # GitHub Copilot guidelines
│   └── workflows/
│       └── test.yml            # CI/CD pipeline
├── .editorconfig               # Editor configuration
└── .serena/                    # Serena MCP configuration
```

## Current Status
- **Version**: 2.2.5 (December 10, 2025)
- **Development Version**: 2.3.0-alpha (Phase 3 refactoring in progress)
- **Status**: Production - Geographic CRS handling with automatic EPSG:3857 conversion
- **All Phases Complete**: PostgreSQL, Spatialite, and OGR backends fully operational
- **Key Innovation**: Automatic metric-based buffer calculations for geographic coordinate systems

## Recent Development (December 10, 2025)

### Code Quality Improvements
**Status**: Phase 1 & 2 & 3a Complete ✅
- **Tests**: 26 unit tests created, CI/CD active
- **Wildcard Imports**: 94% eliminated (31/33 cleaned, 2 legitimate re-exports kept)
- **PEP 8 Compliance**: 95% (was 85%)
- **Code Quality**: 4.5/5 stars (was 2/5)
- **Bare Except**: 100% eliminated (13/13 fixed)
- **Null Comparisons**: 100% fixed (27/27 `!= None` → `is not None`)

### Phase 3a: Task Module Extraction (✅ Complete)
**Date**: December 10, 2025 - 23:00
- **Extracted**: 474 lines of utilities from appTasks.py
- **New Structure**: `modules/tasks/` directory
  - `task_utils.py`: Common utilities (spatialite_connect, retry logic, CRS helpers)
  - `geometry_cache.py`: SourceGeometryCache (5× speedup for multi-layer filtering)
  - `__init__.py`: Backwards-compatible re-exports
  - `README.md`: Complete documentation
- **Benefits**: Better separation, testability, reusability
- **Breaking Changes**: None (backwards compatibility maintained)
- **Commit**: `699f637` - Phase 3a extraction

### Phase 3b: Layer Management Extraction (✅ Complete)
**Date**: December 10, 2025 - 23:30
- **Extracted**: LayersManagementEngineTask (1125 lines) from appTasks.py
- **New File**: `modules/tasks/layer_management_task.py`
- **Contains**: Complete layer lifecycle management, index creation, metadata detection
- **Benefits**: Isolation, testability, clearer responsibilities
- **Breaking Changes**: None (backwards compatibility via __init__.py)
- **Commit**: Not yet pushed

### Latest Commits
- `3d23744` (HEAD) - fixing missing imports
- `2c8b627` - docs: Update implementation status with Phase 3a completion
- `699f637` - refactor: Phase 3a - Extract utilities and cache from appTasks.py
- `4f672ae` - docs: update implementation status and quality audit
- `a4612f2` - fix: replace remaining bare except clauses
- `0d9367e` - style(pep8): replace != None with is not None
- `92a1f82` - fix: replace bare except clauses with specific exceptions
- `317337b` - refactor(imports): remove redundant local imports

## Recent Releases

### v2.2.5 - Automatic Geographic CRS Handling (December 8, 2025)
- **Automatic EPSG:3857 Conversion**: Auto-detects geographic CRS (EPSG:4326) and switches to EPSG:3857 for metric operations
- **Accuracy Improvement**: 50m buffer is always 50 meters regardless of latitude (eliminates 30-50% errors at high latitudes)
- **Zero Configuration**: Works automatically for all geographic layers
- **Performance**: Minimal overhead (~1ms per feature transformation)
- **Bug Fix**: Fixed geographic coordinates zoom & flash flickering issues
- **Implementation**:
  - Zoom operations: Auto-convert to EPSG:3857 for metric buffer
  - Filtering: Spatialite and OGR backends auto-convert for buffer calculations
  - Updated backends: `filter_mate_dockwidget.py`, `modules/appTasks.py`

### v2.2.4 - Bug Fix Release (December 8, 2025)
- **CRITICAL FIX**: Spatialite expression field name quote handling
  - Issue: `"HOMECOUNT" > 100` was incorrectly converted by removing quotes
  - Impact: Filters failed on case-sensitive field names
  - Solution: Preserved field name quotes in `qgis_expression_to_spatialite()`
  - Added comprehensive test suite (`test_spatialite_expression_quotes.py`)
- Enhanced Spatialite backend robustness
- Comprehensive expression conversion testing

### v2.2.3 - Color Harmonization & Accessibility (December 8, 2025)
- **Enhanced Visual Distinction**: +300% frame contrast improvement
- **WCAG 2.1 Compliance**: AA/AAA accessibility standards met
  - Primary text contrast: 17.4:1 (AAA compliance)
  - Secondary text contrast: 8.86:1 (AAA compliance)
  - Disabled text: 4.6:1 (AA compliance)
- **Theme Refinements**:
  - `default` theme: Darker frames (#EFEFEF), clearer borders (#D0D0D0)
  - `light` theme: Better widget contrast (#F8F8F8), visible borders (#CCCCCC)
- **Accent Colors**: Deeper blue (#1565C0) for better contrast
- **Testing**: New color contrast test suite, WCAG validation
- **Documentation**: Complete color harmonization guide

### v2.2.2 - Configuration Reactivity (December 8, 2025)
- **Real-time Configuration**: Updates without restart
- **Dynamic UI Profile Switching**: Compact/normal/auto modes
- **ChoicesType Integration**: Dropdown selectors for config fields
- **Live Updates**: Icons, themes, dimensions apply immediately
- **Auto-save**: Configuration changes saved automatically
- **Type Safety**: Validation for configuration values

## Key Features

### Core Functionality
- Multi-backend support with automatic selection (PostgreSQL/Spatialite/OGR)
- Asynchronous task execution (QgsTask) for non-blocking operations
- Layer property persistence with JSON configuration
- Filter history with full undo/redo support (in-memory management)
- Automatic CRS reprojection on the fly
- Performance warnings and recommendations for large datasets

### User Experience
- Dynamic UI dimensions (adaptive to screen resolution)
- Theme synchronization with QGIS interface
- Real-time configuration updates (no restart required)
- ChoicesType dropdowns for key settings
- WCAG 2.1 AA/AAA accessibility compliance
- Comprehensive error messages and user feedback

### Technical Features
- Robust geometry repair for buffer operations
- SQLite lock retry mechanism (5 attempts with exponential backoff)
- Intelligent predicate ordering for optimal query performance
- Spatial index automation
- Source geometry caching for multi-layer operations (5× speedup)
- Field name quote preservation for case-sensitive databases
- Automatic geographic CRS to metric conversion

## Performance Characteristics

### PostgreSQL Backend
- **Best for:** > 50,000 features
- **Performance:** Sub-second queries on millions of features
- **Implementation:** Materialized views with GIST indexes

### Spatialite Backend
- **Best for:** 10,000 - 50,000 features
- **Performance:** 1-10s for 100k features
- **Implementation:** Temporary tables with R-tree indexes

### OGR Backend
- **Best for:** < 10,000 features
- **Performance:** Universal compatibility
- **Implementation:** QGIS processing framework

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

## Development Workflow

### Testing
- Unit tests: `pytest tests/ -v`
- Coverage: `pytest tests/ --cov=modules`
- Performance benchmarks: `python tests/benchmark_simple.py`
- 26+ comprehensive tests including:
  - Backend tests
  - Expression conversion tests
  - Color contrast/WCAG compliance tests
  - Configuration reactivity tests
  - Performance optimization tests

### CI/CD
- **GitHub Actions**: `.github/workflows/test.yml`
- **Automated checks**: Tests, flake8, black, wildcard detection
- **Coverage**: Codecov integration
- **Triggers**: Push, pull requests

### Build & Release
- Compile UI: `./compile_ui.sh` (Linux/macOS) or `compile_ui.bat` (Windows)
- Create release: `python create_release_zip.py`
- Deploy: See `website/DEPLOYMENT.md`

### Documentation
- Developer guide: `docs/DEVELOPER_ONBOARDING.md`
- Architecture: `docs/architecture.md`
- API docs: `docs/BACKEND_API.md`
- Quality audit: `docs/CODEBASE_QUALITY_AUDIT_2025-12-10.md`
- Implementation status: `docs/IMPLEMENTATION_STATUS_2025-12-10.md`
- Color harmonization: `docs/COLOR_HARMONIZATION.md`
- Website: https://sducournau.github.io/filter_mate

## Configuration System (v2.2.2+)

### Dynamic Configuration
- Real-time updates via JSON tree view
- ChoicesType for validated dropdowns
- Auto-save on changes
- Backward compatible
- No restart required for most changes

### Key Configuration Fields
- `UI_PROFILE`: Display mode (auto/compact/normal)
- `ACTIVE_THEME`: Theme selection (auto/default/dark/light)
- `THEME_SOURCE`: Theme source (config/qgis/system)
- `STYLES_TO_EXPORT`: Export format (QML/SLD/None)
- `DATATYPE_TO_EXPORT`: Data format (GPKG/SHP/GEOJSON/KML/DXF/CSV)

### Configuration Helpers
**File:** `modules/config_helpers.py`
**Functions:**
- `get_config_value(key, default)`: Read with ChoicesType extraction
- `set_config_value(key, value)`: Write with validation
- `get_config_choices(key)`: Get available options
- `validate_config_value(key, value)`: Validate before setting
- Convenience functions: `get_ui_profile()`, `get_active_theme()`, etc.

## Known Limitations

### Current Constraints
- PostgreSQL requires psycopg2 (optional dependency)
- Very large exports (>1M features) may require disk space
- Some QGIS expressions may not translate to all backends
- Field names with special characters may need quoting

### Fixed Issues (v2.2.4-2.2.5)
- ✅ Spatialite field name quote preservation
- ✅ Case-sensitive field name handling
- ✅ Expression conversion robustness
- ✅ Geographic coordinates zoom & flash flickering
- ✅ Automatic metric CRS conversion

## Documentation Structure

### Core Documentation
- `README.md`: User-facing introduction
- `CHANGELOG.md`: Complete version history (1796+ lines)
- `docs/INDEX.md`: Documentation index

### Technical Documentation
- `docs/architecture.md`: System architecture
- `docs/BACKEND_API.md`: Backend API reference
- `docs/IMPLEMENTATION_STATUS_2025-12-10.md`: Feature completion status (696 lines)
- `docs/CODEBASE_QUALITY_AUDIT_2025-12-10.md`: Quality audit (1689 lines)

### Configuration Documentation
- `docs/CONFIG_JSON_REACTIVITY.md`: Reactivity system
- `docs/CONFIG_JSON_IMPROVEMENTS.md`: Configuration improvements

### UI Documentation
- `docs/UI_SYSTEM_OVERVIEW.md`: UI architecture
- `docs/UI_DYNAMIC_CONFIG.md`: Dynamic dimensions
- `docs/COLOR_HARMONIZATION.md`: Color system & WCAG compliance
- `docs/THEMES.md`: Theme details

### Developer Documentation
- `docs/DEVELOPER_ONBOARDING.md`: Getting started guide
- `.github/copilot-instructions.md`: Coding guidelines
- `tests/README.md`: Testing guide
- `modules/tasks/README.md`: Task module documentation

## Accessibility (v2.2.3+)

### WCAG 2.1 Compliance
- **Primary Text**: 17.4:1 contrast ratio (AAA)
- **Secondary Text**: 8.86:1 contrast ratio (AAA)
- **Disabled Text**: 4.6:1 contrast ratio (AA)
- **Frame Separation**: +300% contrast improvement
- **Border Visibility**: +40% darker borders
- **Reduced eye strain** for long work sessions

### Testing
- Automated WCAG validation: `tests/test_color_contrast.py`
- Visual preview generation: `tests/generate_color_preview.py`
- Interactive HTML comparison: `docs/color_harmonization_preview.html`

## Repository Information
- **Repository**: https://github.com/sducournau/filter_mate
- **Issues**: https://github.com/sducournau/filter_mate/issues
- **License**: See LICENSE file
- **Author**: imagodata (simon.ducournau+filter_mate@gmail.com)
- **QGIS Min Version**: 3.0
- **Current Plugin Version**: 2.2.5
- **Development Version**: 2.3.0-alpha

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
- Serena MCP server auto-starts when Chat opens (Windows: configured via MCP with SERENA_PROJECT)

## Next Steps (Phase 3 Refactoring)

### In Progress
- ✅ Phase 3a: Extract utilities from appTasks.py (Complete)
- ✅ Phase 3b: Extract LayersManagementEngineTask (Complete)
- 🔄 Phase 3c: Extract remaining tasks from appTasks.py (Next)

### Planned
- Phase 4: Decompose filter_mate_dockwidget.py into logical UI components
- Phase 5: Additional testing and documentation
- Phase 6: Performance optimization and final polish
