# FilterMate Project Overview

## Purpose
FilterMate is a QGIS plugin that provides advanced filtering and export capabilities for vector data. It allows users to:
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
├── filter_mate_app.py          # Main application orchestrator
├── filter_mate_dockwidget.py   # UI dockwidget management
├── filter_mate_dockwidget_base.py  # Base UI class
├── filter_mate_dockwidget_base.ui  # Qt Designer UI file
├── config/
│   ├── config.json             # Plugin configuration (dynamic)
│   └── config.py               # Configuration loader
├── modules/
│   ├── appTasks.py             # Async filtering tasks (QgsTask)
│   ├── appUtils.py             # Database connections and utilities
│   ├── backends/               # Multi-backend architecture
│   │   ├── base_backend.py    # Abstract base class
│   │   ├── factory.py         # Backend factory (auto-selection)
│   │   ├── postgresql_backend.py  # PostgreSQL/PostGIS backend
│   │   ├── spatialite_backend.py  # Spatialite backend
│   │   └── ogr_backend.py     # OGR universal fallback
│   ├── config_helpers.py       # Configuration utilities
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
├── tests/                      # Unit tests (50+ tests)
├── docs/                       # Documentation
├── website/                    # Docusaurus documentation site
├── .github/
│   └── copilot-instructions.md # GitHub Copilot guidelines
└── .serena/                    # Serena MCP configuration

```

## Current Status
- **Version**: 2.2.2 (December 2025)
- **Status**: Production - Stable multi-backend release
- **All Phases Complete**: PostgreSQL, Spatialite, and OGR backends fully operational

## Recent Improvements (v2.2.x)

### v2.2.2 - Configuration Reactivity
- ✅ Real-time configuration updates without restart
- ✅ Dynamic UI profile switching (compact/normal/auto)
- ✅ Live icon updates and instant feedback
- ✅ ChoicesType integration for dropdowns
- ✅ Auto-save configuration changes
- ✅ Type safety and validation

### v2.2.0-2.2.1 - Maintenance & Documentation
- ✅ Code cleanup and refactoring
- ✅ Improved build and deployment scripts
- ✅ Enhanced documentation structure
- ✅ Bug fixes and stability improvements

### v2.1.0 - Major Release
- ✅ Complete multi-backend architecture with factory pattern
- ✅ Dynamic UI dimensions system (compact/normal modes)
- ✅ Enhanced theme support and QGIS synchronization
- ✅ Comprehensive error handling and geometry repair (5 strategies)
- ✅ SQLite database lock management with retry logic
- ✅ All critical bugs fixed (undo/redo, field selection, geometric filtering)
- ✅ Performance optimizations: 3-45× faster on typical operations
- ✅ Extensive documentation and testing framework

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
- Comprehensive error messages and user feedback

### Technical Features
- Robust geometry repair for buffer operations
- SQLite lock retry mechanism (5 attempts with exponential backoff)
- Intelligent predicate ordering for optimal query performance
- Spatial index automation
- Source geometry caching for multi-layer operations

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

### Build & Release
- Compile UI: `./compile_ui.sh`
- Create release: `python create_release_zip.py`
- Deploy: See `website/DEPLOYMENT.md`

### Documentation
- Developer guide: `docs/DEVELOPER_ONBOARDING.md`
- Architecture: `docs/architecture.md`
- API docs: `docs/BACKEND_API.md`
- Website: https://sducournau.github.io/filter_mate

## Configuration System

### Dynamic Configuration (v2.2.2)
- Real-time updates via JSON tree view
- ChoicesType for validated dropdowns
- Auto-save on changes
- Backward compatible

### Key Configuration Fields
- `UI_PROFILE`: Display mode (auto/compact/normal)
- `ACTIVE_THEME`: Theme selection (auto/default/dark/light)
- `THEME_SOURCE`: Theme source (config/qgis/system)
- `STYLES_TO_EXPORT`: Export format (QML/SLD/None)
- `DATATYPE_TO_EXPORT`: Data format (GPKG/SHP/GEOJSON/KML/DXF/CSV)

## Known Limitations

### Current Constraints
- PostgreSQL requires psycopg2 (optional dependency)
- Very large exports (>1M features) may require disk space
- Some QGIS expressions may not translate to all backends

### Planned Enhancements
- Result caching for repeated queries
- Parallel execution for multi-layer filtering
- Custom backend plugin support
- Enhanced export progress reporting

## Documentation Structure

### Core Documentation
- `README.md`: User-facing introduction
- `CHANGELOG.md`: Complete version history
- `docs/INDEX.md`: Documentation index

### Technical Documentation
- `docs/architecture.md`: System architecture
- `docs/BACKEND_API.md`: Backend API reference
- `docs/IMPLEMENTATION_STATUS.md`: Feature completion status

### Configuration Documentation
- `docs/CONFIG_JSON_REACTIVITY.md`: Reactivity system
- `docs/CONFIG_JSON_IMPROVEMENTS.md`: Configuration improvements
- `docs/CONFIG_OK_CANCEL_BEHAVIOR.md`: Dialog behavior

### UI Documentation
- `docs/UI_SYSTEM_OVERVIEW.md`: UI architecture
- `docs/UI_DYNAMIC_CONFIG.md`: Dynamic dimensions
- `docs/UI_STYLE_HARMONIZATION.md`: Theme system
- `docs/THEMES.md`: Theme details

### Developer Documentation
- `docs/DEVELOPER_ONBOARDING.md`: Getting started guide
- `.github/copilot-instructions.md`: Coding guidelines
- `tests/README.md`: Testing guide

## Repository Information
- **Repository**: https://github.com/sducournau/filter_mate
- **Issues**: https://github.com/sducournau/filter_mate/issues
- **License**: See LICENSE file
- **Author**: imagodata (simon.ducournau+filter_mate@gmail.com)
