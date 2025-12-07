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
- **Framework**: PyQGIS (QGIS API), PyQt5
- **Database Support**: 
  - PostgreSQL/PostGIS (via psycopg2 - optional)
  - Spatialite (built-in SQLite)
  - OGR (Shapefiles, GeoPackage, etc.)
- **Architecture**: Multi-backend with automatic selection

## Project Structure
```
filter_mate/
├── filter_mate.py              # Plugin entry point (QGIS integration)
├── filter_mate_app.py          # Main application orchestrator (~1038 lines)
├── filter_mate_dockwidget.py   # UI dockwidget (~2446 lines)
├── filter_mate_dockwidget_base.py  # Base UI class
├── filter_mate_dockwidget_base.ui  # Qt Designer UI file
├── modules/
│   ├── appTasks.py             # Async filtering tasks (~2772 lines)
│   ├── appUtils.py             # Database connections and utilities
│   ├── customExceptions.py     # Custom exception classes
│   ├── widgets.py              # Custom widgets (combobox, etc.)
│   └── qt_json_view/           # JSON tree view widgets
├── config/
│   ├── config.json             # Plugin configuration
│   └── config.py               # Configuration loader
├── icons/                      # Plugin icons
├── i18n/                       # Translations
├── .github/
│   └── copilot-instructions.md # GitHub Copilot guidelines
└── .serena/                    # Serena MCP configuration

```

## Current Status
- **Version**: 2.1.0 (December 2025)
- **Production**: Stable multi-backend release, fully tested and documented
- **All Phases Complete**: PostgreSQL, Spatialite, and OGR backends fully operational
- **Performance**: All optimizations implemented (spatial indexes, temp tables, caching, predicate ordering)
- **Recent Improvements** (v2.1.0):
  - ✅ Complete multi-backend architecture with factory pattern
  - ✅ Dynamic UI dimensions system (compact/normal modes)
  - ✅ Enhanced theme support and QGIS synchronization
  - ✅ Comprehensive error handling and geometry repair (5 strategies)
  - ✅ SQLite database lock management with retry logic
  - ✅ All critical bugs fixed (undo/redo, field selection, geometric filtering)
  - ✅ Performance optimizations: 3-45× faster on typical operations
  - ✅ Extensive documentation and testing framework

## Key Features
- Multi-backend support with automatic selection (PostgreSQL/Spatialite/OGR)
- Asynchronous task execution (QgsTask) for non-blocking operations
- Layer property persistence with JSON configuration
- Filter history with full undo/redo support (in-memory management)
- Automatic CRS reprojection on the fly
- Performance warnings and recommendations for large datasets
- Dynamic UI dimensions (adaptive to screen resolution)
- Theme synchronization with QGIS interface
- Robust geometry repair for buffer operations
- SQLite lock retry mechanism (5 attempts with exponential backoff)
- Intelligent predicate ordering for optimal query performance
