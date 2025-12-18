---
sidebar_position: 1
slug: /
---

# Welcome to FilterMate

**FilterMate** is a production-ready QGIS plugin that provides advanced filtering and export capabilities for vector data - works with ANY data source!

## 🎉 What's New in v2.3.7 - Project Change Stability Enhancement

### Enhanced Project Change Handling
- 🛡️ **Complete Rewrite of `_handle_project_change()`** - Forces cleanup of previous project state
- 🗑️ **Full State Reset** - Clears `PROJECT_LAYERS`, add_layers queue, and all state flags
- 🔗 **Dockwidget Sync** - Resets layer references to prevent stale data access

### New `cleared` Signal Handler
- 📢 **`_handle_project_cleared()` Method** - Proper cleanup on project close/clear
- 🔌 **Connected to `QgsProject.instance().cleared`** - Handles new project and project close events
- 🛡️ **State Reset** - Ensures plugin state is properly reset when project changes

### F5 Shortcut: Force Reload Layers
- ⌨️ **Press F5** in dockwidget to force complete layer reload
- 🔄 **Manual Recovery** when automatic project change detection fails
- 📊 **Status Indicator** shows reload in progress ("⟳")

### Bug Fixes
- 🐛 **Fixed Project Change Not Reloading Layers** - Root cause identified and fixed
- 🐛 **Fixed Signal Timing Issue** - QGIS emits `layersAdded` BEFORE `projectRead` handler completes
- 🔧 **Now manually triggers `add_layers`** after cleanup instead of waiting for missed signal

## Previous Updates

### v2.3.6 - Project & Layer Loading Stability (December 18, 2025)
- 🛡️ **Centralized Timing Constants** - `STABILITY_CONSTANTS` dict
- ⏱️ **Timestamp-Tracked Flags** - Auto-reset after 30 seconds
- ✅ **Layer Validation** - `_is_layer_valid()` checks C++ object validity
- 🔄 **Signal Debouncing** - Graceful handling of rapid signals

### v2.3.5 - Code Quality & Configuration v2.0 (December 17, 2025)
- 🛠️ **Centralized Feedback System** - Unified message bar notifications (`show_info/warning/error/success`)
- ⚡ **PostgreSQL Init Optimization** - 5-50× faster layer loading with connection caching
- ⚙️ **Configuration v2.0** - Integrated metadata structure with auto-migration
- 🔒 **Forced Backend Respect** - User choice strictly enforced (no fallback to OGR)
- 🐛 **Bug Fixes** - Fixed syntax errors and bare except clauses
- 🧹 **Code Quality** - Score improved to 8.9/10

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

---

## ⚡ Try FilterMate in 3 Minutes

New to FilterMate? Start with a quick task to see it in action immediately:

<div class="quick-tasks-grid">

### 🔍 Task 1: Filter by Attribute
**Time**: 2 minutes | **Difficulty**: ⭐  
**Goal**: Show only large cities

Filter expression: `"population" > 100000`

[▶️ Start Tutorial](./getting-started/3-minute-tutorial.md)

---

### 📐 Task 2: Geometric Filter  
**Time**: 3 minutes | **Difficulty**: ⭐  
**Goal**: Find buildings near roads

Use spatial predicates with 200m buffer

[▶️ Start Tutorial](./getting-started/first-filter.md)

---

### 💾 Task 3: Export Filtered Data
**Time**: 2 minutes | **Difficulty**: ⭐  
**Goal**: Save filtered features to GeoPackage

Choose format and CRS, click Export

[▶️ Start Tutorial](./user-guide/export-features.md)

</div>

:::tip Sample Data Available
Don't have data to test? Download our [sample dataset](https://github.com/sducournau/filter_mate/releases) (Paris 10th - 5 MB) with pre-configured QGIS project.
:::

---

## 💡 Popular Use Cases

Explore what you can achieve with FilterMate:

### 🏙️ Urban Planning
**Find properties within walking distance of transit stations**

Combine buffer operations with attribute filtering for transit-oriented development analysis.

[View Workflow →](./workflows/urban-planning-transit.md)

---

### 🏠 Real Estate Analysis
**Filter homes by price, size, and school proximity**

Multi-criteria filtering for investment opportunities and market analysis.

[View Workflow →](./workflows/real-estate-analysis.md)

---

### 🌳 Environmental Protection
**Identify industrial sites in protected zones**

Geometric filtering to assess regulatory compliance and environmental impact.

[View Workflow →](./workflows/environmental-protection.md)

---

### 🚒 Emergency Services
**Analyze service coverage areas**

Distance calculations to identify underserved areas.

[View Workflow →](./workflows/emergency-services.md)

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
