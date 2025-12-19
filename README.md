# ![alt title logo](https://github.com/sducournau/filter_mate/blob/main/icon.png?raw=true) FilterMate
**Version 2.3.8** | December 19, 2025

**FilterMate is a production-ready QGIS plugin that provides advanced filtering and export capabilities for vector data - works with ANY data source!**

### 🎉 What's New in v2.3.8 - Automatic Dark Mode Support & Filter Favorites

- 🎨 **Automatic Dark Mode Detection** - Real-time QGIS theme detection and UI synchronization
- 🌓 **Icon Inversion for Dark Mode** - PNG icons automatically adapted for dark themes
- ⭐ **Filter Favorites System** - Save, organize, and reuse complex filter configurations
  - 💾 SQLite persistence across sessions
  - 📊 Usage tracking and statistics
  - 📤 Export/Import via JSON files
  - 🎯 Multi-layer filter support
  - 🏷️ Tags and search capabilities
- 🎯 **New Icon Utilities Module** - Theme-aware icon management with caching
- ✨ **JsonView Theme Sync** - Config editor updates with main theme

### Previous: v2.3.7 - Project Change Stability Enhancement

- 🛡️ **Enhanced Project Change Handling** - Complete rewrite of `_handle_project_change()`
  - Forces cleanup of previous project state before reinitializing
  - Clears `PROJECT_LAYERS`, add_layers queue, and all state flags
  - Resets dockwidget layer references to prevent stale data
  
- 🔄 **New `cleared` Signal Handler** - Proper cleanup on project close/clear
  - Added `_handle_project_cleared()` connected to `QgsProject.instance().cleared`
  - Ensures plugin state is reset when project is closed or new project created
  
- ⌨️ **F5 Shortcut: Force Reload Layers** - Manual recovery when project change fails
  - Press F5 in dockwidget to force complete layer reload
  - Also available via `launchingTask.emit('reload_layers')`
  
- 🐛 **Bug Fixes** - Root cause identified and fixed
  - Fixed project change not reloading layers
  - Fixed signal timing issue (QGIS emits `layersAdded` BEFORE `projectRead` handler completes)
  - Now manually triggers `add_layers` after cleanup instead of waiting for missed signal

### Previous Updates (v2.3.5) - Code Quality & Configuration v2.0

- 🛠️ **Centralized Feedback System** - Unified message bar notifications
  - New `show_info/warning/error/success` functions with graceful fallback
- ⚡ **PostgreSQL Init Optimization** - 5-50× faster layer loading
- ⚙️ **Configuration System v2.0** - Integrated metadata structure with auto-migration
- 🔒 **Forced Backend Respect** - User choice strictly enforced
- 🐛 **Bug Fixes** - Fixed syntax errors in dockwidget module
- 🧹 **Code Quality** - Score improved to 8.9/10

### Previous Updates (v2.3.4) - PostgreSQL 2-Part Table Reference Fix
- 🐛 **CRITICAL: Fixed PostgreSQL spatial filtering** - Tables using `"table"."geom"` format now work correctly
- ✨ **Smart display field selection** - Auto-selects best descriptive field (name, label, etc.)
- 🛠️ **Automatic PostgreSQL ANALYZE** - Optimal query performance with proper statistics

### Previous Updates (v2.3.0) - Global Undo/Redo System
- ⭐ **Intelligent Undo/Redo** - Smart context-aware undo/redo for filters
  - **Source Layer Mode**: Undo/redo applies only to the source layer when no remote layers selected
  - **Global Mode**: Undo/redo restores all layers (source + remote) atomically
  - **Auto-Detection**: Seamlessly switches between modes based on layer selection
  - **Button States**: Automatic enable/disable based on history availability
- 🔄 **Automatic Filter Preservation** - Filters combined using AND by default (no more lost filters!)
- 🏗️ **Architecture Refactor** - Task modules extracted (-99% appTasks.py, +400% maintainability)
- ✅ **Code Quality** - PEP 8 95%, 26 automated tests, CI/CD active
- 🚀 **5× Performance** - Geometry caching for multi-layer operations
- 📉 **Reduced Notifications** - Configurable feedback levels (minimal/normal/verbose)

### Previous Updates (v2.2.5) - Geographic CRS Handling
- ✅ **Automatic Geographic CRS Handling** - Auto-converts EPSG:4326 to EPSG:3857 for metric operations
- ✅ **Accurate Buffer Distances** - 50m buffer is always 50 meters regardless of latitude
- ✅ **Geographic Zoom Fix** - Resolved flickering issues with `flashFeatureIds`
- ✅ **Zero Configuration** - Works automatically for all geographic layers
- ✅ **Minimal Performance Impact** - Only ~1ms per feature transformation

### Previous Updates (v2.2.4)
- ✅ **Bug Fix** - Fixed critical Spatialite expression field name quote handling
- ✅ **Enhanced Stability** - Improved error handling for case-sensitive fields
- ✅ **Better Testing** - Comprehensive test suite for expression conversion
- ✅ **Increased Reliability** - Robust Spatialite backend operations

### Previous Updates (v2.2.3)
- ✅ **Color Harmonization** - Enhanced visual distinction with +300% frame contrast
- ✅ **WCAG Accessibility** - AA/AAA compliant text contrast (17.4:1 ratio)
- ✅ **Reduced Eye Strain** - Optimized color palette for long work sessions

### Previous Updates (v2.2.1)
- ✅ **Enhanced Stability** - Improved Qt JSON view crash prevention
- ✅ **Better Error Recovery** - Robust tab widget and theme handling
- ✅ **Complete Multi-Backend** - PostgreSQL, Spatialite, and OGR implementations
- ✅ **Dynamic UI** - Adaptive interface that adjusts to screen resolution
- ✅ **Robust Error Handling** - Automatic geometry repair and retry mechanisms
- ✅ **Theme Synchronization** - Matches QGIS interface theme automatically
- ✅ **Performance Optimized** - 2.5× faster with intelligent query ordering

### Key Features
- 🔍 **Intuitive search** for entities in any layer
- 📐 **Geometric filtering** with spatial predicates and buffer support
- 🎨 **Layer-specific widgets** - Configure and save settings per layer
- 📤 **Smart export** with customizable options
- 🌍 **Automatic CRS reprojection** on the fly
- 📝 **Filter history** - Easy undo/redo for all operations
- ⭐ **Filter Favorites** - Save, organize, and reuse complex filter configurations
  - 💾 SQLite persistence across sessions
  - 📊 Usage tracking and statistics
  - 📤 Export/Import via JSON
  - 🎯 Multi-layer support
- 🚀 **Performance warnings** - Intelligent recommendations for large datasets
- 🎨 **Adaptive UI** - Dynamic dimensions based on screen resolution
- 🌓 **Theme support** - Automatic synchronization with QGIS theme
<br>
<br>
📚 **Documentation** : https://sducournau.github.io/filter_mate
<br>
Github repository : https://github.com/sducournau/filter_mate
<br>
Qgis plugin repository : https://plugins.qgis.org/plugins/filter_mate

******

<br>

# 1. Preview
<br>
https://www.youtube.com/watch?v=2gOEPrdl2Bo

---

# 2. Architecture Overview

FilterMate v1.9+ uses a **factory pattern** for backend selection, automatically choosing the optimal backend for your data source.

## Multi-Backend System

```
modules/backends/
  ├── base_backend.py        # Abstract interface
  ├── postgresql_backend.py  # PostgreSQL/PostGIS backend
  ├── spatialite_backend.py  # Spatialite backend
  ├── ogr_backend.py         # Universal OGR backend
  └── factory.py             # Automatic backend selection
```

**Automatic Selection Logic:**
1. Detects layer provider type (`postgres`, `spatialite`, `ogr`)
2. Checks PostgreSQL availability (psycopg2 installed?)
3. Selects optimal backend with performance warnings when needed

---

# 3. Backend Selection

FilterMate automatically selects the best backend for your data source to provide optimal performance.

## 3.1 PostgreSQL Backend (Optimal Performance)

**When used:**
- Layer source is PostgreSQL/PostGIS
- `psycopg2` Python package is installed
- **Best for datasets >50,000 features**

**Features:**
- ✅ Materialized views for ultra-fast filtering
- ✅ Server-side spatial operations
- ✅ Native spatial indexes (GIST)
- ✅ Sub-second response on million+ feature datasets

**Installation:**
```bash
# Method 1: pip (recommended)
pip install psycopg2-binary

# Method 2: QGIS Python console
import pip
pip.main(['install', 'psycopg2-binary'])

# Method 3: OSGeo4W Shell (Windows)
py3_env
pip install psycopg2-binary
```

## 3.2 Spatialite Backend (Good Performance)

**When used:**
- Layer source is Spatialite
- Automatically available (SQLite built-in to Python)
- **Good for datasets <50,000 features**

**Features:**
- ✅ Temporary tables for filtering
- ✅ R-tree spatial indexes
- ✅ Local database operations
- ✅ No additional installation required

**Note:** FilterMate will display an info message when filtering large Spatialite datasets, suggesting PostgreSQL for better performance.

## 3.3 OGR Backend (Universal Compatibility)

**When used:**
- Layer source is Shapefile, GeoPackage, or other OGR formats
- Fallback when PostgreSQL is not available
- **Works with all data sources**

**Features:**
- ✅ QGIS processing framework
- ✅ Memory-based operations
- ✅ Full compatibility with all formats
- ⚠️ Slower on large datasets

## 3.4 Performance Comparison

| Backend      | 10k Features | 100k Features | 1M Features | Concurrent Ops |
|--------------|--------------|---------------|-------------|----------------|
| PostgreSQL   | <1s          | <2s           | ~10s        | Excellent      |
| Spatialite   | <2s          | ~10s          | ~60s        | Good           |
| OGR          | ~5s          | ~30s          | >120s       | Limited        |

*Times are approximate and depend on geometry complexity and system resources*

## 3.5 Performance Optimizations (v1.9+)

FilterMate includes several automatic optimizations:

### Spatialite Backend
- **Temporary tables with R-tree indexes**: 44.6× faster filtering
- **Predicate ordering**: 2.3× faster with optimal predicate evaluation
- **Automatic spatial index detection**: Uses existing indexes when available

### OGR Backend
- **Automatic spatial index creation**: 19.5× faster on large datasets
- **Large dataset optimization**: 3× improvement for >50k features
- **Memory-efficient processing**: Reduces memory footprint

### All Backends
- **Geometry caching**: 5× faster for multi-layer operations
- **Retry mechanisms**: Handles SQLite locks automatically
- **Geometry repair**: Multi-strategy approach for invalid geometries

## 3.6 Checking Your Current Backend

### Via QGIS Python Console:
```python
from modules.appUtils import POSTGRESQL_AVAILABLE, logger
print(f"PostgreSQL available: {POSTGRESQL_AVAILABLE}")
logger.info("Backend check completed")
```

### Via FilterMate Messages:
FilterMate will display info messages indicating which backend is being used:
- "Using Spatialite backend" → Spatialite mode
- No message → PostgreSQL or OGR (check layer type)

## 3.7 Backend Selection Logic

FilterMate automatically selects the backend based on:

1. **Layer Provider Type**: Detected via `layer.providerType()`
   - `postgres` → PostgreSQL backend (if psycopg2 available)
   - `spatialite` → Spatialite backend
   - `ogr` → OGR backend

2. **psycopg2 Availability**: 
   - Available → PostgreSQL enabled for PostGIS layers
   - Not available → Spatialite/OGR fallback

3. **Feature Count Warnings**:
   - >50,000 features on Spatialite → Info message suggests PostgreSQL

## 3.8 Troubleshooting

### PostgreSQL Not Being Used?

**Check if psycopg2 is installed:**
```python
try:
    import psycopg2
    print("✅ psycopg2 installed")
except ImportError:
    print("❌ psycopg2 not installed - install it for PostgreSQL support")
```

**Common issues:**
- Layer is not from PostgreSQL source → Use PostGIS layers
- psycopg2 not in QGIS Python environment → Reinstall in correct environment
- Connection credentials not saved → Check layer data source settings

### Performance Issues?

**For large datasets:**
1. Use PostgreSQL backend (install psycopg2)
2. Ensure spatial indexes exist on your tables
3. Use server-side filtering when possible

**Check spatial indexes:**
```sql
-- PostgreSQL
SELECT * FROM pg_indexes WHERE tablename = 'your_table';

-- Spatialite
SELECT * FROM sqlite_master WHERE type = 'index' AND name LIKE '%idx%';
```

### FilterMate Taking Too Long?

**Recommendations by dataset size:**
- <10k features: Any backend works fine
- 10k-50k features: Spatialite or PostgreSQL recommended
- 50k-500k features: PostgreSQL strongly recommended
- >500k features: PostgreSQL required for good performance

---

# 4. Installation & Support

## 4.1 Installation

### From QGIS Plugin Repository
1. Open QGIS
2. Go to `Plugins` → `Manage and Install Plugins`
3. Search for "FilterMate"
4. Click `Install Plugin`

### Manual Installation
1. Download latest release from [GitHub](https://github.com/sducournau/filter_mate/releases)
2. Extract ZIP to QGIS plugins directory:
   - **Windows**: `C:\Users\<username>\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
3. Restart QGIS
4. Enable plugin in `Plugins` → `Manage and Install Plugins`

### Optional: Install PostgreSQL Support
```bash
# Method 1: pip (recommended)
pip install psycopg2-binary

# Method 2: QGIS Python console
import pip
pip.main(['install', 'psycopg2-binary'])

# Method 3: OSGeo4W Shell (Windows)
py3_env
pip install psycopg2-binary
```

## 4.2 System Requirements

- **QGIS**: Version 3.0 or higher
- **Python**: 3.7+ (included with QGIS)
- **Optional**: PostgreSQL/PostGIS server for optimal performance
- **Optional**: psycopg2 Python package for PostgreSQL support

## 4.3 Support & Documentation

- **GitHub**: [https://github.com/sducournau/filter_mate](https://github.com/sducournau/filter_mate)
- **Website**: [https://sducournau.github.io/filter_mate](https://sducournau.github.io/filter_mate)
- **Issues**: [Report bugs](https://github.com/sducournau/filter_mate/issues)
- **Documentation Index**: [docs/INDEX.md](docs/INDEX.md) - Complete documentation guide

### 📚 Documentation Structure

**For Users:**
- Installation and setup guides (this README)
- Feature overview and usage examples

**For Developers:**
- [Developer Onboarding](docs/DEVELOPER_ONBOARDING.md) - Start here!
- [Architecture](docs/architecture.md) - System design and components
- [Backend API](docs/BACKEND_API.md) - Backend interface reference
- [Implementation Status](docs/IMPLEMENTATION_STATUS.md) - Current features and performance

**For Contributors:**
- [GitHub Copilot Guidelines](.github/copilot-instructions.md) - Coding standards
- [UI Testing Guide](docs/UI_TESTING_GUIDE.md) - Testing procedures
- [Theme System](docs/THEMES.md) - Theme development

**Archived Documentation:**
- [Archived Docs](docs/archived/) - Historical fixes, improvements, and planning

## 4.4 Contributing

Contributions welcome! See [DEVELOPER_ONBOARDING.md](docs/DEVELOPER_ONBOARDING.md) for development setup.

**Quick Start for Developers:**
1. Read [docs/INDEX.md](docs/INDEX.md) for documentation overview
2. Follow [docs/DEVELOPER_ONBOARDING.md](docs/DEVELOPER_ONBOARDING.md) for setup
3. Review [.github/copilot-instructions.md](.github/copilot-instructions.md) for coding standards
4. Check [docs/architecture.md](docs/architecture.md) to understand the system

## 4.5 License

FilterMate is released under the GNU General Public License v3.0. See [LICENSE](LICENSE) file for details.

---

# 5. Version History

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

**Current Version:** 2.1.0 (December 2025)
- Production-ready release
- Complete multi-backend architecture
- Dynamic UI system with adaptive dimensions
- Enhanced theme support and synchronization
- Comprehensive testing and documentation

**Previous Versions:**
- 2.0.0: Production release with multi-backend
- 1.9.x: Beta releases with Spatialite support
- 1.0.x: Initial PostgreSQL-only releases

---

**Developed by**: imagodata  
**Contact**: simon.ducournau+filter_mate@gmail.com  
**Repository**: https://github.com/sducournau/filter_mate  
**Plugin Page**: https://plugins.qgis.org/plugins/filter_mate

