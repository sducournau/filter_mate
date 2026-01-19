# ![alt title logo](https://github.com/sducournau/filter_mate/blob/main/icon.png?raw=true) FilterMate

**Version 4.2.6** | January 2026 | **Production-Ready** 🎉

> 🚀 The ultimate spatial filtering plugin! Explore, filter & export vector data with lightning-fast performance on ANY data source.

## 🔗 Quick Links

| 📚 [Documentation](https://sducournau.github.io/filter_mate) | 💻 [GitHub](https://github.com/sducournau/filter_mate) | 🔌 [QGIS Plugin](https://plugins.qgis.org/plugins/filter_mate) | 🐛 [Report Issue](https://github.com/sducournau/filter_mate/issues) |
| :----------------------------------------------------------: | :----------------------------------------------------: | :------------------------------------------------------------: | :-----------------------------------------------------------------: |

---

## ✨ Key Features

| Feature                    | Description                                        |
| -------------------------- | -------------------------------------------------- |
| 🔍 **Smart Search**        | Intuitive entity search across all layer types     |
| 📐 **Geometric Filtering** | Spatial predicates with buffer support             |
| ⭐ **Filter Favorites**    | Save, organize and reuse filter configurations     |
| 📝 **Undo/Redo**           | Complete filter history with context-aware restore |
| 🌍 **21 Languages**        | Full internationalization support                  |
| 🎨 **Dark Mode**           | Automatic theme detection and synchronization      |
| 🚀 **Multi-Backend**       | PostgreSQL, Spatialite, OGR - optimal performance  |

---

## 📋 Recent Changes

### 🔧 v4.2.6 - Code Quality & UI Polish (January 2026)

**Major code cleanup** with debug print removal, new searchable config view, and QSS fixes.

- **New:** SearchableJsonView with integrated search bar for configuration
- **Fixed:** QSS stylesheet scoping - no longer affects other QGIS panels
- **Fixed:** UI alignment in filtering section (32x32 button consistency)
- **Cleanup:** Removed 150+ debug print statements across 68 files
- **Quality:** Config model signal handling improvements
- See [CHANGELOG.md](CHANGELOG.md) for complete details

### 🐛 v4.2.5 - Multiple Feature Picker Fix (January 2026)

**Definitive fix** for checkbox auto-uncheck in Multiple Selection Feature Picker.

- **Fixed:** Checkboxes no longer automatically uncheck after clicking
- **Fixed:** Auto-switch groupbox based on canvas selection count
- **Quality:** QGIS selection synchronization improvements

### 🚀 v4.1.0 - Performance & Quality Release (January 2026)

**Major performance improvements** with 2-8× faster filtering and 85% test coverage.

- **Performance:** 4 new optimizers (Auto Backend, Multi-Step, Cache, Async)
- **Quality:** 106 automated tests (+1,567% vs v4.0), 85% coverage
- **Stability:** 3 critical bug fixes (PostgreSQL EXISTS, Spatialite actions, Exploring reload)
- **Documentation:** 1,000+ lines of professional documentation

### 🎉 v3.0.0 - Major Milestone Release (January 2026)

**FilterMate 3.0 represents a major milestone** consolidating 40+ fixes and improvements from the 2.9.x series into a rock-solid, production-ready release.

#### 🛡️ Stability & Reliability

- **40+ bug fixes** addressing edge cases across all backends
- **Signal management overhaul** - UI always responsive after filtering
- **Memory safety** - No more "wrapped C/C++ object deleted" errors
- **Safe QGIS shutdown** - No crashes on Windows during close

#### ⚡ Performance Optimizations

- **99% match optimization** - Skip redundant filters automatically
- **Adaptive geometry simplification** - 2-10x faster buffer operations
- **Smart caching** - Up to 80% cache hit rate on repeated queries
- **Parallel processing** - 2x speedup on datasets with 1M+ features

#### 🔧 Backend Improvements

- **Spatialite/GeoPackage** - NULL-safe predicates, large dataset support
- **PostgreSQL** - Advanced MV optimizations, INCLUDE clause indexes
- **OGR** - Robust multi-layer filtering, GEOS-safe operations

#### 🎨 User Experience

- **Complete undo/redo** - Full filter history with context-aware restore
- **Filter favorites** - Save, organize and share configurations
- **21 languages** - Full internationalization support
- **Dark mode** - Automatic theme synchronization

### v2.9.1 - PostgreSQL MV Performance Optimizations (January 2026)

- 🚀 **PERF: INCLUDE clause** - Covering indexes for 10-30% faster spatial queries (PostgreSQL 11+)
- 📦 **PERF: Bbox pre-filter** - Ultra-fast && operator checks (2-5x faster)
- ⚡ **PERF: Async CLUSTER** - Non-blocking for medium datasets (50k-100k features)
- 📊 **PERF: Extended statistics** - Better query plans (PostgreSQL 10+)

### v2.8.9 - Enhanced MV Management & Simplified UI (January 2026)

- ✨ **NEW: MV Status Widget** - Real-time materialized views count
- 🧹 **NEW: Quick cleanup actions** - Session/Orphaned/All MVs cleanup
- 🎨 **IMPROVED: Optimization popup** - Simplified confirmation dialog

### v2.8.7 - Complex Expression Materialization Fix (January 2026)

- 🐛 **FIX: Slow canvas rendering** - Complex spatial expressions (EXISTS + ST_Buffer) now always materialized
- 🚀 **PERF: 10-100x faster** - Canvas rendering with complex multi-step filters

### v2.8.6 - Code Quality & Post-Buffer Optimization (January 2026)

- 🚀 **NEW: Post-buffer simplification** - Automatic vertex reduction after buffer operations
- ♻️ **REFACTOR: Centralized psycopg2** - New `psycopg2_availability.py` module for clean imports
- ♻️ **REFACTOR: Deduplicated buffer methods** - ~230 lines removed, moved to `base_backend.py`
- 🛠️ **REFACTOR: Standardized message bars** - Centralized via `feedback_utils`
- ⚙️ **NEW CONFIG: `auto_simplify_after_buffer`** - Enable/disable post-buffer simplification
- ⚙️ **NEW CONFIG: `buffer_simplify_after_tolerance`** - Tolerance in meters (default: 0.5)

### v2.8.0 - Enhanced Auto-Optimization System (January 2026)

- 🚀 **NEW: Performance Metrics Collection** - Track and analyze optimization effectiveness
- 🚀 **NEW: Query Pattern Detection** - Identify recurring queries and pre-optimize
- 🚀 **NEW: Adaptive Thresholds** - Automatically tune optimization thresholds based on observed performance
- 🚀 **NEW: Parallel Processing** - Multi-threaded spatial operations for large datasets (2x speedup on 1M features)
- 🚀 **NEW: LRU Caching** - Intelligent caching with automatic eviction and TTL support
- 🚀 **NEW: Selectivity Histograms** - Better selectivity estimation using sampled data
- 📊 **STATS: Cache hit rate up to 80%, strategy selection 6x faster**

### v2.7.14 - WKT Coordinate Precision Optimization (January 2026)

- 🐛 **FIX: PostgreSQL refiltering with negative buffer returns ALL features**
- 🔧 **WKT coordinate precision optimized by CRS (60-70% smaller WKT for metric CRS)**
- 🚀 **Aggressive WKT simplification with Convex Hull/Bounding Box fallbacks**

### v2.6.6 - Fix: Spatialite Filtering Freeze (January 2026)

- 🐛 **FIX: QGIS freeze when filtering with Spatialite/GeoPackage backend**
- 🐛 **FIX: Removed reloadData() calls for OGR/Spatialite layers (causes freeze)**
- 🚀 **PERF: Only PostgreSQL uses reloadData() for MV-based complex filters**

### v2.5.x Series - Stability Improvements (December 2025 - January 2026)

- 🔄 **Bidirectional Sync**: QGIS selection ↔ widgets perfectly synchronized
- 🐛 **PostgreSQL ST_IsEmpty**: Correctly detects ALL empty geometry types from negative buffers
- 🎨 **HiDPI Profile**: New UI profile for 4K/Retina displays with auto-detection
- 🛡️ **Thread Safety**: Robust layer variable access with anti-loop protection

### v2.5.6 - Auto Focus with Native QGIS Selection Tool (December 2025)

- 🎯 **AUTO FOCUS WITH SELECTING**: FilterMate widgets now perfectly sync with QGIS native selection tool
- 🔄 **Bidirectional Sync**: Select features with native QGIS tools → see them in FilterMate widgets automatically
- ✨ **Complete Multiple Selection**: Full synchronization (check AND uncheck) instead of additive-only behavior

### v2.5.5 - Critical Fix: PostgreSQL Negative Buffer Detection (December 2025)

- 🐛 **CRITICAL FIX**: PostgreSQL backend now correctly detects ALL empty geometry types from negative buffers
- 🔧 **ST_IsEmpty**: Uses ST_IsEmpty() instead of NULLIF to detect POLYGON EMPTY, MULTIPOLYGON EMPTY, etc.
- 🎨 **HiDPI Profile**: New UI profile for 4K/Retina displays with auto-detection
- 🖼️ **UI Improvements**: Compact sidebar buttons, harmonized spacing across all tabs
- ✅ **Thread Safety**: Warning messages properly stored for main thread display

### v2.5.4 - Critical Fix: OGR Backend Memory Layers (December 2025)

- 🐛 **CRITICAL FIX**: OGR backend now correctly counts features in memory layers
- 🔧 **Intelligent Counting**: Handles memory layer refresh delays with retry mechanism
- 🔍 **Enhanced Diagnostics**: Better logging for memory layer feature validation

### v2.5.0 - Major Stability Release (December 2025)

- 🎉 **Major Milestone**: Consolidates all 2.4.x stability fixes into stable release
- 🛡️ **GeoPackage Fix**: Correct GeomFromGPB() function for GPB geometry conversion
- 🔒 **Thread Safety**: Defer setSubsetString() to main thread via queue callback
- 🗄️ **Session Isolation**: Multi-client materialized view naming with session_id prefix
- 🔧 **Type Casting**: Automatic ::numeric casting for varchar/numeric comparisons
- 🔍 **Remote Layers**: Proper detection and fallback to OGR for WFS/HTTP services
- 🐛 **Source Geometry**: Thread-safe feature validation with expression fallback

### v2.4.x Series - Stability Fixes (December 2025)

- 🔧 GeoPackage geometry detection improvements
- 🛡️ Layer variable access violation crash fixes
- ✅ Connection validation for PostgreSQL objects
- 🧹 PostgreSQL maintenance menu for session cleanup

> 📖 See [CHANGELOG.md](CHANGELOG.md) for complete version history.

---

## 🎬 Video Tutorials

### 📺 Overview

<div align="center">

[![FilterMate Overview](https://img.youtube.com/vi/2gOEPrdl2Bo/maxresdefault.jpg)](https://www.youtube.com/watch?v=2gOEPrdl2Bo)

**▶️ Click to watch: Complete FilterMate Overview**

</div>

---

### 🔍 Explore your dataset intuitively & filter layers from multiple selection

<div align="center">

[![Dataset Exploration](https://img.youtube.com/vi/YwEalDjgEdY/maxresdefault.jpg)](https://youtu.be/YwEalDjgEdY)

**▶️ Click to watch: Intuitive Dataset Exploration**

</div>

---

### 🛣️ Deeply explore road data and filter connected areas

<div align="center">

[![Road Data Filtering](https://img.youtube.com/vi/svElL8cDpWE/maxresdefault.jpg)](https://youtu.be/svElL8cDpWE)

**▶️ Click to watch: Road Network Filtering**

</div>

---

### 📦 Export to GeoPackage with styles (negative buffer example on Toulouse)

<div align="center">

[![GeoPackage Export](https://img.youtube.com/vi/gPLi2OudKcI/maxresdefault.jpg)](https://youtu.be/gPLi2OudKcI)

**▶️ Click to watch: GeoPackage Export with Styles**

</div>

---

### 📐 Negative buffer (-500m) with multiple attribute selection on BD Topo IGN

<div align="center">

[![Negative Buffer](https://img.youtube.com/vi/9rZb-9A-tko/maxresdefault.jpg)](https://youtu.be/9rZb-9A-tko)

**▶️ Click to watch: Advanced Negative Buffer Tutorial**

</div>

---

## 🏗️ Architecture

FilterMate v4.0+ uses a **hexagonal architecture** (ports & adapters) for maintainability, testability, and clean separation of concerns.

### 🎯 Hexagonal Architecture Benefits

| Benefit | Description |
|---------|-------------|
| **🔌 Pluggable Backends** | Easy to add new data sources (PostgreSQL, Spatialite, OGR, Memory) |
| **✅ Testable** | Pure business logic in `core/` with 85% test coverage |
| **🔧 Maintainable** | Clear separation: UI → Services → Adapters → Infrastructure |
| **🚀 Scalable** | Add features without breaking existing code |
| **📦 Portable** | Core logic is QGIS-independent, can be reused elsewhere |

### 📂 Directory Structure

```
filter_mate/
├── core/                    # 🧠 Business Logic (Pure Python)
│   ├── domain/              # Value Objects & Entities
│   │   ├── favorites_manager.py      # Favorites persistence & management
│   │   ├── filter_expression.py     # Filter expression domain model
│   │   └── layer_info.py            # Layer metadata value object
│   ├── ports/               # 🔌 Interfaces (Abstract Base Classes)
│   │   └── backend_port.py          # Backend interface contract
│   ├── services/            # 🎯 Business Logic Services
│   │   ├── filter_service.py        # Core filtering orchestration
│   │   ├── history_service.py       # Undo/Redo management
│   │   ├── favorites_service.py     # Favorites business logic
│   │   ├── layer_organizer.py       # Layer organization by provider
│   │   └── task_orchestrator.py     # Async task coordination
│   ├── tasks/               # ⚡ Background Tasks (QgsTask)
│   │   ├── filter_task.py           # Main filtering task (6,022 lines → refactored)
│   │   └── layer_management_task.py # Layer CRUD operations
│   ├── filter/              # 🔍 Filter Domain Logic
│   │   ├── expression_builder.py   # Expression construction
│   │   ├── filter_orchestrator.py  # Multi-backend orchestration
│   │   └── result_processor.py     # Result aggregation
│   └── geometry/            # 📐 Geometry Utilities
│       └── crs_utils.py             # CRS transformations
│
├── adapters/                # 🔗 External World Integration
│   ├── backends/            # 💾 Filter Backends (Data Sources)
│   │   ├── factory.py               # Smart backend selection (v4.1.1 hybrid detection)
│   │   ├── postgresql/              # PostgreSQL backend (psycopg2)
│   │   │   ├── backend.py           # PostgreSQL executor
│   │   │   ├── materialized_view.py # MV optimization (>10k features)
│   │   │   └── optimizer.py         # Query optimization
│   │   ├── spatialite/              # Spatialite backend
│   │   │   ├── backend.py           # Spatialite executor
│   │   │   ├── filter_actions.py    # Reset/Unfilter/Cleanup (v4.1.0)
│   │   │   └── rtree.py             # R-tree spatial indexing
│   │   ├── ogr/                     # OGR universal fallback
│   │   │   └── backend.py           # OGR executor
│   │   └── memory/                  # In-memory operations
│   │       └── backend.py           # Memory backend
│   ├── qgis/                # 🗺️ QGIS-specific adapters
│   │   └── tasks/                   # QgsTask wrappers
│   ├── repositories/        # 💽 Data Access Layer
│   │   └── layer_repository.py      # Layer CRUD operations
│   ├── app_bridge.py        # 🌉 App ↔ Hexagonal services bridge
│   ├── task_builder.py      # 🏗️ Task parameter construction
│   ├── undo_redo_handler.py # ⏮️ Undo/Redo adapter
│   └── database_manager.py  # 🗄️ SQLite database management
│
├── ui/                      # 🎨 User Interface Layer (MVC)
│   ├── controllers/         # 🎮 UI Controllers
│   │   ├── favorites_controller.py  # Favorites UI logic
│   │   ├── exploring_controller.py  # Exploring panel logic
│   │   └── filtering_controller.py  # Filtering panel logic
│   ├── widgets/             # 🧩 Custom Widgets
│   │   └── custom_widgets.py        # QgsCheckableComboBox extensions
│   └── dialogs/             # 💬 Dialog Windows
│
└── infrastructure/          # ⚙️ Cross-cutting Concerns
    ├── cache/               # 💾 Caching Infrastructure
    │   └── exploring_cache.py       # Feature list caching (100-500× speedup)
    ├── config/              # 📋 Configuration Management
    │   ├── config.py                # Config system v2.0
    │   └── config_metadata.py       # Metadata handling
    ├── logging/             # 📊 Logging Infrastructure
    │   └── logger.py                # Centralized logging
    └── utils/               # 🛠️ Utilities
        └── layer_utils.py           # Layer validation, safety checks
```

### 🔄 Architecture Evolution

FilterMate has undergone a major refactoring from **God Classes** to **Hexagonal Architecture**:

| Version | Architecture | Lines of Code | Test Coverage | Notes |
|---------|--------------|---------------|---------------|-------|
| **v2.x** | Monolithic | ~15,000 LOC | <10% | Legacy: All logic in `filter_mate_app.py` |
| **v3.0** | Mixed | ~18,000 LOC | ~30% | Transition: Started extracting services |
| **v4.0-alpha** | Hexagonal | ~22,000 LOC | 75% | Migration: Modules shims, core extraction |
| **v4.1.0** | Hexagonal | ~24,000 LOC | 85% | Production: Full hexagonal, 106 tests |

**Key Milestones:**
- **EPIC-1 (v4.0)**: `modules/` → `core/`, `adapters/`, `infrastructure/`
- **Phase E9-E11**: God classes eliminated (-67% reduction in app/dockwidget)
- **Phase E12**: `filter_task.py` migrated to `core/tasks/`
- **Phase E13 (v5.0 planned)**: Complete removal of `modules/` shims

### 🧪 Testing Philosophy

The hexagonal architecture enables comprehensive testing:

```python
# Example: Testing filter service WITHOUT QGIS
from core.services.filter_service import FilterService
from core.domain.filter_expression import FilterExpression

# Pure Python test - no QGIS dependencies
def test_filter_expression_building():
    service = FilterService()
    expr = FilterExpression(layer_id="test", expression='"population" > 1000')
    result = service.build_filter(expr)
    assert result.is_valid()
```

**Test Organization:**
- `tests/`: Unit tests for core services (85% coverage)
- `tests/backends/`: Backend-specific tests (PostgreSQL, Spatialite, OGR)
- `tests/integration/`: End-to-end QGIS integration tests

### 📖 Architecture Documentation

For detailed architecture information, see:

- **Architecture Overview**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Developer Onboarding**: [docs/DEVELOPER_ONBOARDING.md](docs/DEVELOPER_ONBOARDING.md)
- **Coding Standards**: [.github/copilot-instructions.md](.github/copilot-instructions.md)
- **Refactoring Status**: [_bmad-output/REFACTORING-STATUS-20260112.md](_bmad-output/REFACTORING-STATUS-20260112.md)

### Backend Features Matrix

Comprehensive feature support across backends:

| Feature | PostgreSQL | Spatialite | OGR | Notes |
|---------|:----------:|:----------:|:---:|-------|
| **Geometric Filtering** | ✅ | ✅ | ✅ | All backends support all geometric predicates |
| **Buffer Operations** | ✅ | ✅ | ✅ | Positive, negative, and zero buffers |
| **Multi-layer Filtering** | ✅ | ✅ | ✅ | Filter multiple layers simultaneously |
| **Reset Action** | ✅ | ✅ **(v4.1)** | ✅ | Clear filter and refresh layer |
| **Unfilter Action** | ✅ | ✅ **(v4.1)** | ✅ | Restore previous subset string |
| **Session Cleanup** | ✅ | ✅ **(v4.1)** | ✅ | Automatic cleanup of temp tables/views |
| **Materialized Views** | ✅ | ❌ | ❌ | PostgreSQL only (>10k features) |
| **R-tree Indexes** | ✅ | ✅ | ❌ | PostgreSQL (GIST), Spatialite (R-tree) |
| **Temp Tables** | ❌ | ✅ | ✅ | Spatialite/OGR use temp tables |
| **Two-phase Filtering** | ✅ | ❌ | ❌ | PostgreSQL optimization for >50k |
| **Parallel Queries** | ✅ | ❌ | ❌ | PostgreSQL parallel workers |
| **Progressive Chunking** | ❌ | ❌ | ✅ | OGR fallback for large datasets |

**Legend:**
- ✅ Full support
- ❌ Not supported
- ⚠️ Partial support
- **(v4.1)** New in v4.1.0-beta.1

**Key Updates in v4.1.0-beta.1:**
- **Spatialite Reset/Unfilter**: Restored actions for Spatialite backend (regression fix)
- **Session Cleanup**: All backends now support automatic cleanup of temporary resources
- **PostgreSQL EXISTS**: Fixed source filter application in EXISTS subqueries

```

### Backend Performance

| Backend    | 10k Features | 100k Features | 1M Features |
| ---------- | :----------: | :-----------: | :---------: |
| PostgreSQL |     <1s      |      <2s      |    ~10s     |
| Spatialite |     <2s      |     ~10s      |    ~60s     |
| OGR        |     ~5s      |     ~30s      |    >120s    |

### 🔄 Backend Management

FilterMate provides tools to manage and monitor backends:

#### Backend Indicator

The **backend indicator** is displayed in the plugin interface showing the current backend status:

|     Indicator      | Meaning                                         |
| :----------------: | ----------------------------------------------- |
| 🟢 **PostgreSQL**  | PostgreSQL backend active (optimal performance) |
| 🔵 **Spatialite**  | Spatialite backend active (good performance)    |
|     🟠 **OGR**     | OGR fallback active (universal compatibility)   |
| 🔴 **Unavailable** | No backend available for this layer             |

#### Reload Backend

To **reload the backend** after configuration changes:

1. **Via Menu**: `FilterMate` → `Backend` → `Reload Backend`
2. **Via Button**: Click the **🔄 refresh icon** next to the backend indicator
3. **Automatic**: Backend auto-reloads when:
   - Switching active layer
   - Installing/uninstalling psycopg2
   - Changing data source connection

#### PostgreSQL Maintenance

For PostgreSQL users, a dedicated maintenance menu is available:

| Action                  | Description                                              |
| ----------------------- | -------------------------------------------------------- |
| **Clean Session Views** | Remove temporary materialized views from current session |
| **Clean All Views**     | Remove all FilterMate materialized views from schema     |
| **View Schema Info**    | Display current PostgreSQL schema statistics             |

Access via: `FilterMate` → `PostgreSQL` → `Maintenance`

#### Troubleshooting Backend Issues

| Issue                                        | Solution                                                 |
| -------------------------------------------- | -------------------------------------------------------- |
| PostgreSQL not detected                      | Install `psycopg2-binary`: `pip install psycopg2-binary` |
| Slow performance on large data               | Switch to PostgreSQL data source                         |
| Backend indicator shows "OGR" for GeoPackage | Normal - GeoPackage uses Spatialite internally via OGR   |
| Connection errors                            | Check database credentials and network connectivity      |

---

## 📦 Installation

### From QGIS Plugin Repository

1. QGIS → `Plugins` → `Manage and Install Plugins`
2. Search "FilterMate" → `Install Plugin`

### Manual Installation

1. Download from [GitHub Releases](https://github.com/sducournau/filter_mate/releases)
2. Extract to QGIS plugins directory:
   - **Windows**: `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`

### Optional: PostgreSQL Support

```bash
pip install psycopg2-binary
```

---

## 📋 Requirements

- **QGIS**: 3.0+
- **Python**: 3.7+ (included with QGIS)
- **Optional**: psycopg2 for PostgreSQL backend

---

## 📚 Documentation

| Audience         | Resource                                                          |
| ---------------- | ----------------------------------------------------------------- |
| **Users**        | [Website Documentation](https://sducournau.github.io/filter_mate) |
| **Developers**   | [Developer Onboarding](docs/DEVELOPER_ONBOARDING.md)              |
| **Contributors** | [Coding Guidelines](.github/copilot-instructions.md)              |

---

## 🤝 Contributing

1. Read [Developer Onboarding](docs/DEVELOPER_ONBOARDING.md)
2. Review [Architecture](docs/architecture.md)
3. Follow [Coding Standards](.github/copilot-instructions.md)

---

## 📄 License

GNU General Public License v3.0 - See [LICENSE](LICENSE)

---

**Developed by**: imagodata  
**Contact**: simon.ducournau+filter_mate@gmail.com
