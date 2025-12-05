# ![alt title logo](https://github.com/sducournau/filter_mate/blob/main/icon.png?raw=true) FilterMate

**Version 1.9.1** | December 2025

**FilterMate is a QGIS plugin that provides advanced filtering and export capabilities for vector data - now works with ANY data source!**

### 🎉 What's New in v1.9
- ✅ **Works WITHOUT PostgreSQL** - No database server required!
- ✅ **Multi-backend architecture** - Automatic backend selection (PostgreSQL/Spatialite/OGR)
- ✅ **Universal compatibility** - Shapefile, GeoPackage, Spatialite, PostgreSQL
- ✅ **Performance optimizations** - 2-45× faster with intelligent caching and indexing
- ✅ **Robust error handling** - Automatic geometry repair and retry mechanisms
- ✅ **Filter history** - Full undo/redo support with in-memory management

### Key Features
- 🔍 **Intuitive search** for entities in any layer
- 📐 **Geometric filtering** with spatial predicates and buffer support
- 🎨 **Layer-specific widgets** - Configure and save settings per layer
- 📤 **Smart export** with customizable options
- 🌍 **Automatic CRS reprojection** on the fly
- 📝 **Filter history** - Easy undo/redo for all operations
- 🚀 **Performance warnings** - Intelligent recommendations for large datasets
<br>
<br>
Github page : https://sducournau.github.io/filter_mate
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

# 4. Advanced Features

