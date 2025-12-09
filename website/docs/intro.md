---
sidebar_position: 1
slug: /
---

# Welcome to FilterMate

**FilterMate** is a production-ready QGIS plugin that provides advanced filtering and export capabilities for vector data - works with ANY data source!

## 🎉 What's New in v2.2.5 - Automatic Geographic CRS Handling

### Major Improvements
- ✅ **Automatic EPSG:3857 Conversion** - Geographic CRS (EPSG:4326, etc.) auto-converted for metric operations
  - Feature: Detects geographic coordinate systems automatically
  - Impact: 50m buffer is always 50 meters, regardless of latitude (no more 30-50% errors!)
  - Implementation: Auto-converts to EPSG:3857 (Web Mercator) for buffer calculations
  - Performance: Minimal overhead (~1ms per feature transformation)
- ✅ **Geographic Zoom & Flash Fix** - Resolved flickering with `flashFeatureIds`
  - Fixed: Feature geometry no longer modified in-place during transformation
  - Solution: Uses `QgsGeometry()` copy constructor to prevent original geometry modification
- ✅ **Consistent Metric Operations** - All backends updated (Spatialite, OGR, Zoom)
  - Zero configuration required
  - Clear logging with 🌍 indicator when CRS switching occurs
- ✅ **Comprehensive Testing** - Added test suite in `tests/test_geographic_coordinates_zoom.py`

## Previous Updates

### v2.2.4 - Color Harmonization & Accessibility (December 8, 2025)
- ✅ **Color Harmonization** - Enhanced visual distinction with +300% frame contrast
- ✅ **WCAG 2.1 Compliance** - AA/AAA accessibility standards for all text
  - Primary text: 17.4:1 contrast ratio (AAA)
  - Secondary text: 8.86:1 contrast ratio (AAA)
  - Disabled text: 4.6:1 contrast ratio (AA)
- ✅ **Reduced Eye Strain** - Optimized color palette for long work sessions
- ✅ **Better Readability** - Clear visual hierarchy throughout interface
- ✅ **Theme Refinements** - Darker frames (#EFEFEF), clearer borders (#D0D0D0)
- ✅ **Automated Testing** - WCAG compliance validation suite

### v2.2.2 - Configuration Reactivity (December 8, 2025)
- ✅ **Real-time Config Updates** - JSON tree view changes apply instantly without restart
- ✅ **Dynamic UI Switching** - Switch compact/normal/auto modes on the fly
- ✅ **Live Icon Updates** - Configuration changes reflected immediately
- ✅ **ChoicesType Integration** - Dropdown selectors for validated config fields
- ✅ **Type Safety** - Invalid values prevented at UI level
- ✅ **Auto-save** - All configuration changes saved automatically

### v2.2.1 - Maintenance (December 7, 2025)
- ✅ **Enhanced Stability** - Improved Qt JSON view crash prevention
- ✅ **Better Error Recovery** - Robust tab widget and theme handling
- ✅ **Build Improvements** - Enhanced automation and version management

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
