---
sidebar_position: 1
slug: /
---

# Welcome to FilterMate

**FilterMate** is a production-ready QGIS plugin that provides advanced filtering and export capabilities for vector data - works with ANY data source!

## 🎉 What's New in v2.4.8 - PostgreSQL Thread Safety & Session Isolation

### 🛡️ Thread Safety Improvements

- **Defer setSubsetString() to Main Thread** - PostgreSQL subset string updates now use queue callback for thread safety
- **Session Isolation** - Multi-client materialized view naming with session_id prefix prevents conflicts
- **Connection Validation** - Proper validation of ACTIVE_POSTGRESQL connection objects before use

### 🔧 Key Fixes

- **Type Casting** - Fix varchar/numeric comparison errors with automatic ::numeric casting
- **Full SELECT Statement** - Build complete SQL for PostgreSQL materialized views (was causing syntax errors)
- **Filter Sanitization** - Remove non-boolean display expressions from subset strings

### 🔧 New Features

- **PostgreSQL Maintenance Menu** - New UI for session view cleanup and schema management

## Previous Updates

### v2.4.7 - GeoPackage Geometry Detection & Stability Fix (December 24, 2025)

- 🔧 Improved geometry column detection for GeoPackage/Spatialite layers
- 🛡️ Multi-method detection: layer.geometryColumn() → dataProvider → gpkg_metadata
- 🔒 Safe layer variable operations with deferred execution

### v2.4.6 - Layer Variable Access Violation Crash Fix (December 23, 2025)

- 🔥 **CRITICAL FIX**: Access violation in setLayerVariable race condition resolved
- 🛡️ Safe wrapper functions re-fetch layer from project registry immediately before operation

### v2.4.5 - Processing Parameter Validation Fix (December 23, 2025)

- 🔥 **CRITICAL FIX**: Access violation in checkParameterValues during geometric filtering
- 🛡️ Pre-flight validation tests layer access before calling processing.run()

### v2.4.3 - Export System Fix (December 22, 2025)

- 🐛 Fixed streaming export error with missing datatype argument
- 💬 Improved message bar notifications with correct argument order
- 🔧 Better partial export handling with detailed failure messages

### v2.4.2 - ValueRelation & Display Enhancement (December 22, 2025)

- ✨ **Smart Display Detection** - Auto-detects ValueRelation fields and shows human-readable values
- 🔗 **Layer Display Expression** - Uses the layer's configured display expression from Layer Properties
- 🎯 **Better Exploring UX** - See meaningful labels instead of cryptic IDs

### v2.4.1 - International Edition Extended (December 22, 2025)

- 🌍 **21 Languages Supported** - Added Slovenian, Filipino/Tagalog, Amharic
- 🔤 Fixed hardcoded French strings - all UI now properly translatable
- ✨ 19 new translatable configuration messages

### v2.4.0 - International Edition (December 22, 2025)

- 🌍 **11 New Languages** - Polish, Chinese, Russian, Indonesian, Vietnamese, Turkish, Hindi, Finnish, Danish, Swedish, Norwegian
- 🔤 Enhanced language selection in Configuration panel
- All 140+ UI strings fully translated

### v2.3.9 - Critical Stability Fix (December 22, 2025)

- 🔥 **Fixed GEOS Crash** - Resolved fatal crash during OGR backend filtering
- 🛡️ **New Safety Modules** - `geometry_safety.py` and `object_safety.py`
- 🐛 **Fixed Access Violation** - Resolved crash on plugin reload/QGIS close

### v2.3.8 - Automatic Dark Mode Support & Filter Favorites (December 19, 2025)

- 🎨 **Automatic Dark Mode Detection** - Real-time QGIS theme detection
- 🌓 **Icon Inversion for Dark Mode** - PNG icons visible in dark themes
- ⭐ **Filter Favorites System** - Save, organize, and reuse filter configurations
  - SQLite persistence, usage tracking, export/import via JSON
- 📦 **New Modules** - `icon_utils.py` and `filter_favorites.py`

### v2.3.7 - Project Change Stability Enhancement (December 19, 2025)

- 🛡️ **Enhanced Project Change Handling** - Complete rewrite of project change logic
- 🔄 **New `cleared` Signal Handler** - Proper cleanup on project close
- ⌨️ **F5 Shortcut** - Force reload layers when project change fails
- 🐛 **Bug Fixes** - Fixed project change not reloading layers and signal timing issues

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

👉 **[Complete Installation Guide](/docs/installation)**

---

## ⚡ Try FilterMate in 3 Minutes

New to FilterMate? Start with a quick task to see it in action immediately:

<div class="quick-tasks-grid">

### 🔍 Task 1: Filter by Attribute

**Time**: 2 minutes | **Difficulty**: ⭐  
**Goal**: Show only large cities

Filter expression: `"population" > 100000`

[▶️ Start Tutorial](/docs/getting-started/minute-tutorial)

---

### 📐 Task 2: Geometric Filter

**Time**: 3 minutes | **Difficulty**: ⭐  
**Goal**: Find buildings near roads

Use spatial predicates with 200m buffer

[▶️ Start Tutorial](/docs/getting-started/first-filter)

---

### 💾 Task 3: Export Filtered Data

**Time**: 2 minutes | **Difficulty**: ⭐  
**Goal**: Save filtered features to GeoPackage

Choose format and CRS, click Export

[▶️ Start Tutorial](/docs/user-guide/export-features)

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

[View Workflow →](/docs/workflows/urban-planning-transit)

---

### 🏠 Real Estate Analysis

**Filter homes by price, size, and school proximity**

Multi-criteria filtering for investment opportunities and market analysis.

[View Workflow →](/docs/workflows/real-estate-analysis)

---

### 🌳 Environmental Protection

**Identify industrial sites in protected zones**

Geometric filtering to assess regulatory compliance and environmental impact.

[View Workflow →](/docs/workflows/environmental-protection)

---

### 🚒 Emergency Services

**Analyze service coverage areas**

Distance calculations to identify underserved areas.

[View Workflow →](/docs/workflows/emergency-services)

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

**FilterMate automatically chooses the best backend** for your data source - no configuration needed! Learn more in the [Backend Selection Guide](/docs/backends/choosing-backend).

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

1. **[Installation](/docs/installation)** - Install the plugin and optional dependencies
2. **[Quick Start](/docs/getting-started/quick-start)** - 5-minute tutorial
3. **[Your First Filter](/docs/getting-started/first-filter)** - Complete step-by-step example
4. **[Interface Overview](/docs/user-guide/interface-overview)** - Understand the UI
5. **[Filtering Basics](/docs/user-guide/filtering-basics)** - Master filtering techniques

## Getting Help

- 📖 **Documentation**: Browse the [User Guide](/docs/user-guide/introduction)
- 🐛 **Issues**: Report bugs on [GitHub Issues](https://github.com/sducournau/filter_mate/issues)
- 💬 **Discussions**: Join [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions)
- 🎥 **Video**: Watch our [YouTube tutorial](https://www.youtube.com/watch?v=2gOEPrdl2Bo)

## Documentation Sections

- **[Getting Started](/docs/getting-started/)** - Tutorials and quick start guides
- **[User Guide](/docs/user-guide/introduction)** - Complete feature documentation
- **[Backends](/docs/backends/overview)** - Understanding data source backends
- **[Advanced](/docs/advanced/configuration)** - Configuration and performance tuning
- **[Developer Guide](/docs/developer-guide/architecture)** - Contributing and development

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

- [Installation Guide](/docs/installation)
- [Quick Start Tutorial](/docs/getting-started/quick-start)
- [GitHub Repository](https://github.com/sducournau/filter_mate)
- [QGIS Plugin Repository](https://plugins.qgis.org/plugins/filter_mate)

## Video Demo

Watch FilterMate in action:

[![FilterMate Demo](https://img.youtube.com/vi/2gOEPrdl2Bo/0.jpg)](https://www.youtube.com/watch?v=2gOEPrdl2Bo)

## Get Started

Ready to start? Head over to the [Installation Guide](/docs/installation) to set up FilterMate in your QGIS environment.
