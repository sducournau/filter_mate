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
├── filter_mate_app.py          # Main application orchestrator (~1100 lines)
├── filter_mate_dockwidget.py   # UI dockwidget management (~2500 lines)
├── filter_mate_dockwidget_base.py  # Base UI class
├── filter_mate_dockwidget_base.ui  # Qt Designer UI file
├── config/
│   ├── config.json             # Plugin configuration (dynamic, reactive)
│   └── config.py               # Configuration loader
├── modules/
│   ├── appTasks.py             # Async filtering tasks (QgsTask) (~2800 lines)
│   ├── appUtils.py             # Database connections and utilities (~800 lines)
│   ├── backends/               # Multi-backend architecture
│   │   ├── base_backend.py    # Abstract base class
│   │   ├── factory.py         # Backend factory (auto-selection)
│   │   ├── postgresql_backend.py  # PostgreSQL/PostGIS backend
│   │   ├── spatialite_backend.py  # Spatialite backend
│   │   └── ogr_backend.py     # OGR universal fallback
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
├── tests/                      # Unit tests (60+ tests)
├── docs/                       # Comprehensive documentation
├── website/                    # Docusaurus documentation site
├── .github/
│   └── copilot-instructions.md # GitHub Copilot guidelines
└── .serena/                    # Serena MCP configuration
```

## Current Status
- **Version**: 2.2.5 (December 10, 2025)
- **Status**: Production - Geographic CRS handling with automatic EPSG:3857 conversion
- **All Phases Complete**: PostgreSQL, Spatialite, and OGR backends fully operational
- **Key Innovation**: Automatic metric-based buffer calculations for geographic coordinate systems

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

### v2.1.0 - Major Multi-Backend Release
- Complete multi-backend architecture with factory pattern
- Dynamic UI dimensions system (compact/normal modes)
- Enhanced theme support and QGIS synchronization
- Comprehensive error handling and geometry repair (5 strategies)
- SQLite database lock management with retry logic
- Performance optimizations: 3-45× faster on typical operations
- Extensive documentation and testing framework

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
- Source geometry caching for multi-layer operations
- Field name quote preservation for case-sensitive databases

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
- 60+ comprehensive tests including:
  - Backend tests
  - Expression conversion tests
  - Color contrast/WCAG compliance tests
  - Configuration reactivity tests
  - Performance optimization tests

### Build & Release
- Compile UI: `./compile_ui.sh` (Linux/macOS) or `compile_ui.bat` (Windows)
- Create release: `python create_release_zip.py`
- Deploy: See `website/DEPLOYMENT.md`

### Documentation
- Developer guide: `docs/DEVELOPER_ONBOARDING.md`
- Architecture: `docs/architecture.md`
- API docs: `docs/BACKEND_API.md`
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

### Fixed Issues (v2.2.4)
- ✅ Spatialite field name quote preservation
- ✅ Case-sensitive field name handling
- ✅ Expression conversion robustness

## Documentation Structure

### Core Documentation
- `README.md`: User-facing introduction
- `CHANGELOG.md`: Complete version history (1700+ lines)
- `docs/INDEX.md`: Documentation index

### Technical Documentation
- `docs/architecture.md`: System architecture
- `docs/BACKEND_API.md`: Backend API reference
- `docs/IMPLEMENTATION_STATUS.md`: Feature completion status

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
- **Current Plugin Version**: 2.2.4

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
