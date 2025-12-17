---
sidebar_position: 1
slug: /
---

# Welcome to FilterMate

**FilterMate** is a production-ready QGIS plugin that provides advanced filtering and export capabilities for vector data - works with ANY data source!

## 🎉 What's New in v2.3.5 - Stability & Backend Improvements

### Bug Fixes
- 🐛 **CRITICAL: Fixed GeometryCollection errors in OGR backend** - Buffer operations now properly convert to MultiPolygon, fixing "Impossible d'ajouter l'objet avec une géométrie de type GeometryCollection" errors
- 🐛 **CRITICAL: Fixed potential crashes in layer operations** - Guard clauses prevent KeyError when layers are removed during filtering, undo/redo, or exploration

### Performance Improvements
- 🚀 **GeoPackage 10× faster** - GeoPackage layers now use Spatialite backend with direct SQL queries instead of slow OGR algorithms

### Technical Improvements
- 🛠️ **Improved exception handling** - Replaced generic exception handlers with specific types for better debugging
- Added logging for all exception handlers to aid troubleshooting

## Previous Updates

### v2.3.4 - PostgreSQL 2-Part Table Reference Fix (December 16, 2025)
- 🐛 **CRITICAL: Fixed PostgreSQL 2-part table references** - Spatial filtering now works correctly with tables using `"table"."geom"` format
- ✨ **Smart display field selection** - New layers auto-select the best descriptive field (name, label, titre, etc.)
- 🛠️ **Automatic PostgreSQL ANALYZE** - Query planner now gets proper statistics before spatial queries

## Why FilterMate?

- **🚀 Fast**: Optimized backends for PostgreSQL, Spatialite, and OGR
- **🎯 Precise**: Advanced spatial predicates and buffer operations
- **💾 Export Ready**: Multiple formats (GeoPackage, Shapefile, GeoJSON, PostGIS)
- **📜 History**: Full undo/redo with filter history tracking
- **🎨 Beautiful**: WCAG-compliant UI with theme support
- **🔧 Flexible**: Works with any vector data source

## Quick Start

1. **Install**: Open QGIS → Plugins → Manage and Install Plugins → Search "FilterMate"
2. **Open**: Click the FilterMate icon in the toolbar
3. **Filter**: Select a layer, write an expression, click Apply
4. **Export**: Choose format and export your filtered data

👉 **[Complete Installation Guide](./installation.md)**

## Key Features

### Advanced Filtering
- Attribute filtering with QGIS expressions
- Geometric filtering (intersects, contains, within, etc.)
- Buffer operations with automatic CRS conversion
- Multi-layer support

### Multiple Backends
- **PostgreSQL**: Best for large datasets (`>50k` features) - 10-50× faster
- **Spatialite**: Good for medium datasets (`<50k` features)
- **OGR**: Universal compatibility (Shapefiles, GeoPackage, etc.)

**FilterMate automatically chooses the best backend** for your data source - no configuration needed! Learn more in the [Backend Selection Guide](./backends/choosing-backend.md).

### Export Capabilities
- Multiple formats: GPKG, SHP, GeoJSON, KML, CSV, PostGIS
- CRS transformation on export
- Style export (QML, SLD, ArcGIS)
- Batch export and ZIP compression

## Prerequisites

Before using FilterMate:

- ✅ **QGIS 3.x** installed (any version)
- ✅ **Vector layer** loaded in your project
- ⚡ **Optional**: Install `psycopg2` for PostgreSQL support (recommended for large datasets)

## Learning Path

New to FilterMate? Follow this path:

1. **[Installation](./installation.md)** - Install the plugin and optional dependencies
2. **[Quick Start](./getting-started/quick-start.md)** - 5-minute tutorial
3. **[Your First Filter](./getting-started/first-filter.md)** - Complete step-by-step example
4. **[Interface Overview](./user-guide/interface-overview.md)** - Understand the UI
5. **[Filtering Basics](./user-guide/filtering-basics.md)** - Master filtering techniques

## Getting Help

- 📖 **Documentation**: Browse the [User Guide](./user-guide/introduction.md)
- 🐛 **Issues**: Report bugs on [GitHub Issues](https://github.com/sducournau/filter_mate/issues)
- 💬 **Discussions**: Join [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions)
- 🎥 **Video**: Watch our [YouTube tutorial](https://www.youtube.com/watch?v=2gOEPrdl2Bo)

## Documentation Sections

- **[Getting Started](./getting-started/index.md)** - Tutorials and quick start guides
- **[User Guide](./user-guide/introduction.md)** - Complete feature documentation
- **[Backends](./backends/overview.md)** - Understanding data source backends
- **[Advanced](./advanced/configuration.md)** - Configuration and performance tuning
- **[Developer Guide](./developer-guide/architecture.md)** - Contributing and development

### v2.2.0 & Earlier
- ✅ **Complete Multi-Backend** - PostgreSQL, Spatialite, and OGR implementations
- ✅ **Dynamic UI** - Adaptive interface that adjusts to screen resolution
- ✅ **Robust Error Handling** - Automatic geometry repair and retry mechanisms
- ✅ **Theme Synchronization** - Matches QGIS interface theme automatically
- ✅ **Performance Optimized** - 2.5× faster with intelligent query ordering

## Key Features

- 🔍 **Intuitive search** for entities in any layer
- 📐 **Geometric filtering** with spatial predicates and buffer support
- 🎨 **Layer-specific widgets** - Configure and save settings per layer
- 📤 **Smart export** with customizable options
- 🌍 **Automatic CRS reprojection** on the fly
- 📝 **Filter history** - Easy undo/redo for all operations
- 🚀 **Performance warnings** - Intelligent recommendations for large datasets
- 🎨 **Adaptive UI** - Dynamic dimensions based on screen resolution
- 🌓 **Theme support** - Automatic synchronization with QGIS theme

## Quick Links

- [Installation Guide](./installation.md)
- [Quick Start Tutorial](./getting-started/quick-start.md)
- [GitHub Repository](https://github.com/sducournau/filter_mate)
- [QGIS Plugin Repository](https://plugins.qgis.org/plugins/filter_mate)

## Video Demo

Watch FilterMate in action:

[![FilterMate Demo](https://img.youtube.com/vi/2gOEPrdl2Bo/0.jpg)](https://www.youtube.com/watch?v=2gOEPrdl2Bo)

## Get Started

Ready to start? Head over to the [Installation Guide](./installation.md) to set up FilterMate in your QGIS environment.
