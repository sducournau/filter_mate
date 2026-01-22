# ![FilterMate](https://github.com/sducournau/filter_mate/blob/main/icon.png?raw=true) FilterMate

**Version 4.4.0** | QGIS Plugin | **Production-Ready** 🎉

> 🚀 Explore, filter & export vector data with lightning-fast performance on ANY data source.

[![Documentation](https://img.shields.io/badge/docs-website-blue)](https://sducournau.github.io/filter_mate)
[![QGIS Plugin](https://img.shields.io/badge/QGIS-Plugin-green)](https://plugins.qgis.org/plugins/filter_mate)
[![GitHub](https://img.shields.io/badge/GitHub-repo-black)](https://github.com/sducournau/filter_mate)
[![Issues](https://img.shields.io/badge/issues-report-red)](https://github.com/sducournau/filter_mate/issues)

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔍 **Smart Search** | Intuitive entity search across all layer types |
| 📐 **Geometric Filtering** | Spatial predicates with buffer support |
| ⭐ **Filter Favorites** | Save and reuse filter configurations |
| 📝 **Undo/Redo** | Complete filter history |
| 🌍 **21 Languages** | Full internationalization |
| 🎨 **Dark Mode** | Automatic theme detection |
| 🚀 **Multi-Backend** | PostgreSQL, Spatialite, OGR |

---

## 📦 Installation

### From QGIS Plugin Repository (Recommended)

1. QGIS → `Plugins` → `Manage and Install Plugins`
2. Search "FilterMate" → `Install Plugin`

### Manual Installation

Download from [GitHub Releases](https://github.com/sducournau/filter_mate/releases) and extract to:

| OS | Path |
|---|---|
| **Windows** | `%APPDATA%\QGIS\QGIS3\profiles\default\python\plugins\` |
| **Linux** | `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/` |
| **macOS** | `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/` |

### Optional: PostgreSQL Support

```bash
pip install psycopg2-binary
```

---

## 🎬 Video Tutorials

| Tutorial | Link |
|----------|------|
| 📺 Complete Overview | [Watch](https://www.youtube.com/watch?v=2gOEPrdl2Bo) |
| 🔍 Dataset Exploration | [Watch](https://youtu.be/YwEalDjgEdY) |
| 🛣️ Road Network Filtering | [Watch](https://youtu.be/svElL8cDpWE) |
| 📦 GeoPackage Export | [Watch](https://youtu.be/gPLi2OudKcI) |
| 📐 Negative Buffer | [Watch](https://youtu.be/9rZb-9A-tko) |

---

## ⚡ Backend Performance

| Backend | 10k | 100k | 1M Features |
|---------|:---:|:----:|:-----------:|
| 🟢 PostgreSQL | <1s | <2s | ~10s |
| 🔵 Spatialite | <2s | ~10s | ~60s |
| 🟠 OGR | ~5s | ~30s | >120s |

**Tip**: Install `psycopg2-binary` for optimal performance with large datasets.

---

## 📋 Requirements

- **QGIS**: 3.0+
- **Python**: 3.7+ (included with QGIS)
- **Optional**: psycopg2 for PostgreSQL backend

---

## 📚 Documentation

- **Users**: [Documentation Website](https://sducournau.github.io/filter_mate)
- **Developers**: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)

---

## 🤝 Contributing

See [Contributing Guidelines](.github/copilot-instructions.md)

---

## 📄 License

GNU General Public License v3.0 - See [LICENSE](LICENSE)

---

**Developed by**: imagodata | **Contact**: simon.ducournau+filter_mate@gmail.com
