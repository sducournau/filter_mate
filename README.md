# ![alt title logo](https://github.com/sducournau/filter_mate/blob/main/icon.png?raw=true) FilterMate

**FilterMate is a Qgis plugin, a daily companion that allows you to easily explore, filter and export vector data**

*FilterMate will change your daily life with QGIS, it allows you to:*
- *a more intuitive search for entities in a layer.*
- *make selections simplier.*
- *be able to review each entity.*
- *filter your vector layers by expressions and by geometric predicates, using a buffer if necessary.*
- *it allows you to configure the differents widgets and save them independently for each layer.*
- *export your layers more intuitively.*
<br>
It adapts to your data, takes advantage of PostGIS when possible, manages differents CRS by reprojecting on the fly.
<br>
The layers keep an history of each subset, making it easy to return to the previous state.
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

# 2. Backend Selection

FilterMate automatically selects the best backend for your data source to provide optimal performance.

## 2.1 PostgreSQL Backend (Optimal Performance)

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

## 2.2 Spatialite Backend (Good Performance)

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

## 2.3 OGR Backend (Universal Compatibility)

**When used:**
- Layer source is Shapefile, GeoPackage, or other OGR formats
- Fallback when PostgreSQL is not available
- **Works with all data sources**

**Features:**
- ✅ QGIS processing framework
- ✅ Memory-based operations
- ✅ Full compatibility with all formats
- ⚠️ Slower on large datasets

## 2.4 Performance Comparison

| Backend      | 10k Features | 100k Features | 1M Features | Concurrent Ops |
|--------------|--------------|---------------|-------------|----------------|
| PostgreSQL   | <1s          | <2s           | ~10s        | Excellent      |
| Spatialite   | <2s          | ~10s          | ~60s        | Good           |
| OGR          | ~5s          | ~30s          | >120s       | Limited        |

*Times are approximate and depend on geometry complexity and system resources*

## 2.5 Checking Your Current Backend

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

## 2.6 Backend Selection Logic

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

## 2.7 Troubleshooting

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

# 3. Advanced Features

