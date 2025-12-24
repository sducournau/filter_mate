# ![alt title logo](https://github.com/sducournau/filter_mate/blob/main/icon.png?raw=true) FilterMate

**Version 2.4.7** | December 2025 | **Production-Ready**

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

### v2.4.7 - GeoPackage Geometry Detection & Stability Fix

- 🔧 **FIX**: Improved geometry column detection for GeoPackage/Spatialite layers
- 🛡️ **Multi-method detection**: layer.geometryColumn() → dataProvider → gpkg_metadata
- 🔒 Safe layer variable operations with deferred execution
- 📝 Better diagnostics for spatial filter failures
- ⚡ Support for non-spatial layers in attribute-only mode

### v2.4.6 - Layer Variable Access Violation Crash Fix

- 🔥 **CRITICAL FIX**: Access violation in setLayerVariable race condition resolved
- 🛡️ **Safe Wrappers**: Re-fetches layer from project registry before C++ calls
- 🔒 Validates sip deletion status and layer validity right before access

### v2.4.5 - Processing Parameter Validation Fix

- 🔥 **CRITICAL FIX**: Access violation in checkParameterValues during geometric filtering
- 🛡️ Pre-flight validation tests layer access before calling processing.run()

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
