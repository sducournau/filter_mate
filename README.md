# ![alt title logo](https://github.com/sducournau/filter_mate/blob/main/icon.png?raw=true) FilterMate

**Version 2.5.7** | December 2025 | **Production-Ready**

> Advanced filtering and export capabilities for vector data in QGIS - works with ANY data source!

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

### v2.5.7 - Improved CRS Compatibility (December 2025)

- 🌍 **IMPROVED CRS COMPATIBILITY**: Automatic conversion to EPSG:3857 when metric calculations needed
- 📐 **OPTIMAL UTM ZONES**: Calculates best UTM zone based on data extent for more accurate metric operations
- 🔄 **CRS TRANSFORMER**: New utility class for reliable geometry transformations between CRS
- 🛠️ **NEW MODULE**: `crs_utils.py` with `is_geographic_crs()`, `get_optimal_metric_crs()`, `CRSTransformer`
- 🔧 **METRIC BUFFER**: `safe_buffer_metric()` handles CRS conversion automatically
- 🧪 **TESTS**: New `test_crs_utils.py` for comprehensive CRS validation

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

## 🎬 Preview

https://www.youtube.com/watch?v=2gOEPrdl2Bo

---

## 🏗️ Architecture

FilterMate uses a **factory pattern** for automatic backend selection:

```
modules/backends/
  ├── postgresql_backend.py  # PostgreSQL/PostGIS (optimal)
  ├── spatialite_backend.py  # Spatialite (good)
  ├── ogr_backend.py         # Universal OGR (compatible)
  └── factory.py             # Automatic selection
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
