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
- **Version**: 1.9.0 (December 2025)
- **Phase 1**: Complete (PostgreSQL optional)
- **Phase 2**: In progress (Spatialite backend)
- **Known Issues**: 
  - Combobox layer icons not displaying correctly
  - Geometry type representation inconsistency

## Key Features
- Multi-backend support with automatic selection
- Asynchronous task execution (QgsTask)
- Layer property persistence
- Filter history with undo/redo
- CRS reprojection on the fly
- Performance warnings for large datasets
