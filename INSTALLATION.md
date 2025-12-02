# FilterMate - Installation & Configuration Guide

**Version**: 1.9.0 (Phase 2 Complete)  
**Date**: December 2025

---

## 📦 Installation

### Quick Install (QGIS Plugin Manager)

1. Open QGIS
2. Go to **Plugins** → **Manage and Install Plugins**
3. Search for **"FilterMate"**
4. Click **Install Plugin**
5. ✅ Done! FilterMate is ready to use

### Manual Install

1. Download the latest release from [GitHub Releases](https://github.com/sducournau/filter_mate/releases)
2. Extract to your QGIS plugins directory:
   - **Windows**: `C:\Users\YourName\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - **Mac**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
3. Restart QGIS
4. Enable plugin in **Plugins** → **Manage and Install Plugins**

---

## 🚀 Getting Started

### Minimum Requirements

- **QGIS**: 3.x or later
- **Python**: 3.7+ (included with QGIS)
- **sqlite3**: Included with Python (for local filtering)

### Optional (for best performance)

- **PostgreSQL/PostGIS**: For large datasets (>50k features)
- **psycopg2**: Python PostgreSQL adapter
  ```bash
  pip install psycopg2-binary
  ```

---

## 🎯 Backend Selection

FilterMate **automatically** selects the best backend for your data:

### Automatic Backend Detection

```
Your Data Layer
       ↓
┌──────────────┐
│ PostgreSQL?  │──Yes→ Use PostgreSQL (fastest)
│              │
└──────┬───────┘
       No
       ↓
┌──────────────┐
│ Spatialite?  │──Yes→ Use Spatialite (fast)
│              │
└──────┬───────┘
       No
       ↓
┌──────────────┐
│ Shapefile    │
│ GeoPackage   │──→ Use Local Backend (good)
│ Other OGR    │
└──────────────┘
```

**You don't need to configure anything!** FilterMate handles it automatically.

---

## 📊 Backend Comparison

| Backend | Speed | Setup | Best For |
|---------|-------|-------|----------|
| **PostgreSQL** | ⚡⚡⚡ Fastest | Requires server | Large datasets (>100k features) |
| **Spatialite** | ⚡⚡ Fast | No setup | Medium datasets (10k-100k features) |
| **Local (OGR)** | ⚡ Good | No setup | Small datasets (<10k features) |

### Performance Guide

| Dataset Size | PostgreSQL | Spatialite | Local | Recommendation |
|--------------|------------|------------|-------|----------------|
| < 1,000 features | ~0.5s | ~1s | ~2s | Any backend OK |
| 1k - 10k | ~1s | ~2s | ~5s | Spatialite or PostgreSQL |
| 10k - 50k | ~2s | ~5s | ~15s | **PostgreSQL recommended** |
| 50k - 100k | ~5s | ~15s | ~60s+ | **PostgreSQL strongly recommended** |
| > 100k | ~10s | ~60s+ | Very slow | **PostgreSQL required** |

---

## 🔧 PostgreSQL Setup (Optional)

### Why PostgreSQL?

- ⚡ **10x faster** for large datasets
- 💪 **Handles millions** of features
- 🔄 **Advanced** spatial operations
- 🎯 **Optimized** indexing

### Installation Steps

#### 1. Install PostgreSQL + PostGIS

**Windows**:
- Download from [postgresql.org](https://www.postgresql.org/download/windows/)
- Use StackBuilder to install PostGIS extension

**Linux (Ubuntu/Debian)**:
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib postgis
```

**Mac**:
```bash
brew install postgresql postgis
```

#### 2. Install psycopg2 (Python adapter)

**Option A: Using QGIS Python**
```python
# In QGIS Python Console:
import subprocess
import sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
```

**Option B: System Python**
```bash
pip install psycopg2-binary
```

**Option C: OSGeo4W (Windows)**
```bash
# Run OSGeo4W Shell as Administrator:
python3 -m pip install psycopg2-binary
```

#### 3. Connect QGIS to PostgreSQL

1. In QGIS, go to **Browser Panel**
2. Right-click **PostgreSQL** → **New Connection**
3. Enter your credentials:
   - **Name**: My PostgreSQL
   - **Host**: localhost (or your server)
   - **Port**: 5432
   - **Database**: your_database
   - **Username**: postgres
   - **Password**: your_password
4. Click **Test Connection**
5. ✅ If successful, click **OK**

#### 4. Verify FilterMate Detects PostgreSQL

Open QGIS Python Console:
```python
from filter_mate.modules.appUtils import POSTGRESQL_AVAILABLE
print(f"PostgreSQL available: {POSTGRESQL_AVAILABLE}")
```

Expected output:
- `True` ✅ PostgreSQL detected
- `False` ⚠️ psycopg2 not installed

---

## 💡 Usage Tips

### For Small Projects (< 10k features)

✅ **No setup needed!** Just use FilterMate with Shapefiles or GeoPackages.

**Example**:
1. Load a Shapefile in QGIS
2. Open FilterMate
3. Apply filters
4. Works instantly! 🎉

### For Medium Projects (10k - 50k features)

✅ **Use Spatialite** for better performance (no PostgreSQL needed)

**Example**:
1. Convert your Shapefile to Spatialite:
   - Right-click layer → **Export** → **Save Features As**
   - Format: **Spatialite**
2. Use FilterMate normally
3. ~3x faster than Shapefile ⚡

### For Large Projects (> 50k features)

⚡ **PostgreSQL recommended** for optimal speed

**Example**:
1. Import data to PostgreSQL:
   ```sql
   shp2pgsql -I -s 4326 mydata.shp myschema.mytable | psql -d mydatabase
   ```
2. Connect QGIS to PostgreSQL
3. Load PostgreSQL layer
4. Use FilterMate
5. **10x faster** than Shapefile! 🚀

---

## 🔍 Troubleshooting

### "FilterMate: PostgreSQL support disabled"

**Cause**: psycopg2 not installed

**Solution**:
```python
# In QGIS Python Console:
import subprocess, sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary"])
```

Then restart QGIS.

### "Large dataset (X features) using Spatialite backend"

**Cause**: Dataset > 50k features without PostgreSQL

**Impact**: Filtering will be slower but still works

**Solutions**:
1. ✅ **Continue anyway** (works, just slower)
2. ⚡ **Install PostgreSQL** for better performance
3. 🔻 **Reduce dataset** by pre-filtering

### "Failed to create temporary Spatialite table"

**Cause**: Spatialite extension not loaded

**Solution 1** (Windows):
- Reinstall QGIS with default settings
- Spatialite should be included

**Solution 2** (Linux):
```bash
sudo apt install libsqlite3-mod-spatialite
```

**Solution 3** (Use PostgreSQL):
- Follow PostgreSQL setup above

### Filtering is slow

**Check your backend**:
```python
# In QGIS Python Console while layer is active:
layer = iface.activeLayer()
print(f"Provider: {layer.providerType()}")
print(f"Feature count: {layer.featureCount()}")
```

**Recommendations**:
- < 10k features: Any backend OK
- 10k - 50k: Use Spatialite
- \> 50k: **Use PostgreSQL**

---

## 🆘 Support

### Documentation
- **GitHub Pages**: https://sducournau.github.io/filter_mate
- **QGIS Plugin**: https://plugins.qgis.org/plugins/filter_mate
- **GitHub Issues**: https://github.com/sducournau/filter_mate/issues

### Common Questions

**Q: Do I need PostgreSQL?**  
A: No! FilterMate works without it. PostgreSQL is optional for better performance with large datasets.

**Q: What formats are supported?**  
A: All QGIS vector formats: Shapefile, GeoPackage, Spatialite, PostgreSQL, GeoJSON, etc.

**Q: Can I use FilterMate offline?**  
A: Yes! Spatialite and local backends work completely offline.

**Q: Does FilterMate work on QGIS Server?**  
A: FilterMate is a desktop plugin. For server-side filtering, use standard QGIS Server filters.

**Q: Is my data modified?**  
A: No! FilterMate only filters (hides) features. Your original data is never modified.

---

## 📝 Version History

### Version 1.9.0 (December 2025) - Phase 2 Complete

**New Features**:
- ✅ **Spatialite backend**: No PostgreSQL required!
- ✅ **Automatic backend selection**: Smart detection
- ✅ **Local OGR support**: Shapefile, GeoPackage, etc.
- ✅ **Performance warnings**: Helpful user messages
- ✅ **Improved error handling**: Clear error messages

**Breaking Changes**: None (100% backward compatible)

**Performance**:
- PostgreSQL: Same speed as before (no regression)
- Spatialite: New backend (3-5x faster than QGIS direct)
- OGR: Works for small datasets

### Version 1.8.x (Previous)
- PostgreSQL-only version
- Required psycopg2 installed

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License

FilterMate is released under GNU GPL v3 license.

---

## 🙏 Credits

**Author**: Sébastien Ducournau  
**Contributors**: Community contributors  
**AI Assistant**: Claude (Anthropic) for Phase 2 implementation

**Special Thanks**:
- QGIS community
- PostGIS team
- Spatialite project

---

**Last Updated**: December 2, 2025  
**FilterMate Version**: 1.9.0 (Phase 2)
