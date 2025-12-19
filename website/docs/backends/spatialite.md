---
sidebar_position: 3
---

# Spatialite Backend

The Spatialite backend provides **excellent performance** for small to medium datasets without requiring external database servers. It leverages SQLite's built-in spatial capabilities with R-tree indexes for efficient filtering.

:::tip Sweet Spot
Spatialite is optimal for datasets **< 50,000 features** and requires **no additional installation** - it works out of the box with Python.
:::

## Overview

FilterMate's Spatialite backend connects to local SQLite databases with the Spatialite spatial extension. It creates temporary tables with spatial indexes to perform geometric filtering efficiently.

### Key Benefits

- ⚡ **Fast performance** on datasets < 50k features
- 🔧 **No setup required** - SQLite built into Python
- 📦 **Portable** - single file database
- 🗺️ **R-tree spatial indexes** for optimized searches
- 💾 **Local processing** - no network overhead
- 🚀 **Automatic** - works immediately with .sqlite files

## When Spatialite Backend Is Used

FilterMate automatically selects the Spatialite backend when:

1. ✅ Layer source is Spatialite/SQLite with spatial extension
2. ✅ File path points to `.sqlite`, `.db`, or `.spatialite` file
3. ✅ Spatialite extension is available (automatically in Python 3.7+)

:::info Performance Warning
For datasets **> 50,000 features**, FilterMate will display a performance warning suggesting PostgreSQL for better performance.
:::

## Installation

### Prerequisites

- **Python 3.7+** (included with QGIS 3.x)
- **Spatialite extension** (usually pre-installed)

### Verification

Spatialite is typically available by default. Verify in QGIS Python Console:

```python
import sqlite3

conn = sqlite3.connect(':memory:')
conn.enable_load_extension(True)

try:
    conn.load_extension('mod_spatialite')
    print("✓ Spatialite extension available")
except Exception as e:
    # Windows fallback
    try:
        conn.load_extension('mod_spatialite.dll')
        print("✓ Spatialite extension available (Windows)")
    except:
        print(f"✗ Spatialite extension not found: {e}")

conn.close()
```

### Manual Installation (if needed)

#### Linux
```bash
sudo apt-get install libspatialite7
# or
sudo yum install libspatialite
```

#### macOS
```bash
brew install libspatialite
```

#### Windows
Spatialite is included with OSGeo4W QGIS installation. If missing:
1. Download from https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/
2. Extract `mod_spatialite.dll` to Python's `DLLs` folder

## Features

### 1. Temporary Tables

FilterMate creates **temporary tables** to store filtered results:

```sql
-- Example temporary table created by FilterMate
CREATE TEMP TABLE filtermate_filtered_123 AS
SELECT *
FROM my_layer
WHERE ST_Intersects(
    geometry,
    (SELECT geometry FROM filter_layer WHERE id = 1)
);

-- Spatial index automatically created
SELECT CreateSpatialIndex('filtermate_filtered_123', 'geometry');
```

**Benefits:**
- Fast creation and querying
- Automatic cleanup on session end
- No permanent database modifications
- Memory-efficient for < 50k features

### 2. R-tree Spatial Indexes

Spatialite uses **R-tree indexes** for spatial queries:

```sql
-- Check spatial indexes
SELECT * FROM geometry_columns
WHERE f_table_name = 'my_layer';

-- FilterMate creates R-tree indexes automatically
SELECT CreateSpatialIndex('my_layer', 'geometry');

-- Index is used automatically for spatial queries
SELECT * FROM my_layer
WHERE ST_Intersects(geometry, MakePoint(100, 50, 4326));
```

:::tip Performance Impact
R-tree indexes provide 10-100x speedup on spatial queries depending on data distribution.
:::

### 3. Spatial Operations

Spatialite supports ~90% of PostGIS functions:

| Function | Spatialite | Equivalent |
|----------|-----------|------------|
| `ST_Intersects()` | ✅ Full support | Same as PostGIS |
| `ST_Contains()` | ✅ Full support | Same as PostGIS |
| `ST_Within()` | ✅ Full support | Same as PostGIS |
| `ST_Buffer()` | ✅ Full support | Same as PostGIS |
| `ST_Distance()` | ✅ Full support | Same as PostGIS |
| `ST_Area()` | ✅ Full support | Same as PostGIS |
| `ST_Length()` | ✅ Full support | Same as PostGIS |
| `ST_Union()` | ✅ Full support | Same as PostGIS |
| `ST_Difference()` | ✅ Full support | Same as PostGIS |
| `ST_Intersection()` | ✅ Full support | Same as PostGIS |

**Example Query:**

```sql
-- Find all features within 100m of a point
SELECT *
FROM my_layer
WHERE ST_Intersects(
    geometry,
    ST_Buffer(MakePoint(100, 50, 4326), 100)
);
```

### 4. Database Optimization

FilterMate applies several optimizations:

- **VACUUM** - Reclaims unused space
- **ANALYZE** - Updates query statistics
- **Spatial index hints** - Forces R-tree usage
- **Transaction batching** - Groups operations

Example:

```sql
-- After creating temp table
ANALYZE filtermate_filtered_123;

-- Vacuum on cleanup
VACUUM;
```

## Configuration

### Database Location

Spatialite databases are single files:

```
/path/to/data/
  ├── my_data.sqlite       # Main database
  ├── my_data.sqlite-shm   # Shared memory (auto-created)
  └── my_data.sqlite-wal   # Write-ahead log (auto-created)
```

### Cache Settings

Optimize Spatialite for performance:

```sql
-- In QGIS Python Console (per-session)
import sqlite3

conn = sqlite3.connect('/path/to/data.sqlite')

-- Increase cache size (in KB)
conn.execute("PRAGMA cache_size = 100000")  -- 100MB cache

-- Enable memory-mapped I/O
conn.execute("PRAGMA mmap_size = 268435456")  -- 256MB mmap

-- WAL mode for better concurrency
conn.execute("PRAGMA journal_mode = WAL")

conn.close()
```

### Performance Settings

For optimal performance in `config/config.json`:

```json
{
  "SPATIALITE": {
    "cache_size_kb": 100000,
    "enable_mmap": true,
    "journal_mode": "WAL",
    "vacuum_on_cleanup": true
  }
}
```

## Usage

### Basic Filtering

1. **Load Spatialite layer** in QGIS (Layer → Add Layer → Vector)
2. **Open FilterMate** plugin
3. **Configure filter** options
4. **Click "Apply Filter"**

FilterMate automatically:
- Detects Spatialite backend
- Creates temporary table with spatial index
- Adds filtered layer to QGIS
- Displays backend indicator: **[SQLite]**

### Creating Spatialite Database

From existing data:

```python
# In QGIS Python Console
from qgis.core import QgsVectorFileWriter

layer = iface.activeLayer()
options = QgsVectorFileWriter.SaveVectorOptions()
options.driverName = "SQLite"
options.layerName = "my_layer"
options.datasourceOptions = ["SPATIALITE=YES"]

QgsVectorFileWriter.writeAsVectorFormatV3(
    layer,
    "/path/to/output.sqlite",
    QgsCoordinateTransformContext(),
    options
)
```

### Batch Processing

For multiple Spatialite layers:

```python
# FilterMate handles multiple layers efficiently
# Each gets its own temporary table
```

## Performance Tuning

### For Small Datasets (< 10k features)

- **No special configuration needed**
- Use default settings
- Performance comparable to PostgreSQL

### For Medium Datasets (10k - 50k features)

- **Increase cache size:**
  ```sql
  PRAGMA cache_size = 50000;  -- 50MB
  ```

- **Enable WAL mode:**
  ```sql
  PRAGMA journal_mode = WAL;
  ```

- **Create spatial indexes manually** if missing:
  ```sql
  SELECT CreateSpatialIndex('my_layer', 'geometry');
  ```

### For Large Datasets (50k - 500k features)

:::warning Performance Consideration
Consider using **PostgreSQL backend** for better performance. Spatialite can handle these sizes but will be slower.
:::

If using Spatialite:

- **Maximize cache:**
  ```sql
  PRAGMA cache_size = 200000;  -- 200MB
  ```

- **Enable memory-mapped I/O:**
  ```sql
  PRAGMA mmap_size = 536870912;  -- 512MB
  ```

- **Run VACUUM ANALYZE:**
  ```sql
  VACUUM;
  ANALYZE;
  ```

## Limitations

### Compared to PostgreSQL

| Feature | Spatialite | PostgreSQL |
|---------|-----------|-----------|
| Max practical size | ~500k features | 10M+ features |
| Concurrent access | Limited | Excellent |
| Server-side ops | ❌ No | ✅ Yes |
| Parallel queries | ❌ No | ✅ Yes |
| Network access | ❌ No (file-based) | ✅ Yes |
| Transaction isolation | Basic | Advanced |
| Query optimization | Good | Excellent |

### Known Limitations

1. **Single-user** - File locking prevents true concurrent access
2. **No parallel processing** - Queries run single-threaded
3. **Memory constraints** - Large operations may consume lots of RAM
4. **No remote access** - Must have local file access

:::tip When to Switch
If you regularly work with **> 50k features**, consider migrating to PostgreSQL for 5-10x performance improvement.
:::

## Troubleshooting

### Issue: "Spatialite extension not found"

**Symptom:** Error when opening Spatialite database

**Solution:**

1. **Check Python environment:**
   ```python
   import sqlite3
   print(sqlite3.sqlite_version)  # Should be 3.7+
   ```

2. **Try alternative extension names:**
   ```python
   conn.load_extension('mod_spatialite')      # Linux/macOS
   conn.load_extension('mod_spatialite.dll')  # Windows
   conn.load_extension('libspatialite')       # Alternative
   ```

3. **Install Spatialite** (see Installation section)

### Issue: "Slow queries despite spatial index"

**Symptom:** Filtering takes longer than expected

**Solution:**

1. **Verify spatial index exists:**
   ```sql
   SELECT * FROM geometry_columns WHERE f_table_name = 'my_layer';
   ```

2. **Check R-tree index:**
   ```sql
   SELECT * FROM sqlite_master
   WHERE type = 'table' AND name LIKE 'idx_%_geometry';
   ```

3. **Rebuild spatial index:**
   ```sql
   SELECT DisableSpatialIndex('my_layer', 'geometry');
   SELECT CreateSpatialIndex('my_layer', 'geometry');
   ```

4. **Run ANALYZE:**
   ```sql
   ANALYZE my_layer;
   ```

### Issue: "Database is locked"

**Symptom:** Cannot write to database

**Solution:**

- Close other QGIS instances using the same file
- Check for orphaned lock files (`.sqlite-shm`, `.sqlite-wal`)
- Switch to WAL mode for better concurrency:
  ```sql
  PRAGMA journal_mode = WAL;
  ```

### Issue: "Out of memory"

**Symptom:** Query fails on large dataset

**Solution:**

- **Reduce cache size** (paradoxically helps sometimes):
  ```sql
  PRAGMA cache_size = 10000;  -- 10MB
  ```

- **Switch to PostgreSQL** for datasets > 100k features

- **Filter in stages** - break up large operations

## Performance Benchmarks

Real-world performance on typical hardware (Core i7, 16GB RAM, SSD):

| Dataset Size | Features | Spatialite | PostgreSQL | Ratio |
|-------------|----------|-----------|-----------|-------|
| Small | 5,000 | 0.4s | 0.3s | 1.3x slower |
| Medium | 50,000 | 8.5s | 1.2s | 7x slower |
| Large | 500,000 | 65s | 8.4s | 8x slower |
| Very Large | 5,000,000 | Timeout | 45s | Not viable |

**Spatial Operations (50k features):**

| Operation | Time | vs PostgreSQL |
|-----------|------|---------------|
| Intersects | 8.2s | 6x slower |
| Contains | 9.1s | 5x slower |
| Buffer (10m) + Intersects | 12.5s | 5x slower |
| Complex expression | 18.3s | 6x slower |

## Best Practices

### ✅ Do

- **Use Spatialite for < 50k features** - excellent performance
- **Create spatial indexes** - huge performance boost
- **Use WAL journal mode** - better concurrency
- **Run VACUUM periodically** - maintains performance
- **Backup before bulk operations** - easy with single file

### ❌ Don't

- **Don't use for > 500k features** - too slow
- **Don't forget spatial indexes** - 10-100x performance penalty
- **Don't open same file in multiple processes** - database locking
- **Don't disable R-tree indexes** - spatial queries will be slow

## Migrating to PostgreSQL

If your Spatialite database grows too large:

### Option 1: QGIS DB Manager

1. **Open DB Manager** (Database → DB Manager)
2. **Select Spatialite database**
3. **Right-click layer → Export to PostgreSQL**
4. **Configure connection and import**

### Option 2: Command Line (ogr2ogr)

```bash
ogr2ogr -f PostgreSQL \
  PG:"host=localhost dbname=mydb user=myuser password=mypass" \
  my_data.sqlite \
  -lco GEOMETRY_NAME=geometry \
  -lco SPATIAL_INDEX=GIST
```

### Option 3: Python Script

```python
from qgis.core import QgsVectorLayer, QgsDataSourceUri

# Load Spatialite layer
sqlite_layer = QgsVectorLayer(
    "/path/to/data.sqlite|layername=my_layer",
    "sqlite_layer",
    "ogr"
)

# Export to PostgreSQL
uri = QgsDataSourceUri()
uri.setConnection("localhost", "5432", "mydb", "user", "pass")
uri.setDataSource("public", "my_layer", "geometry")

# Use QGIS processing or DB Manager export
```

## See Also

- [Backends Overview](./overview) - Multi-backend architecture
- [Backend Selection](./choosing-backend) - Automatic selection logic
- [PostgreSQL Backend](./postgresql) - For larger datasets
- [Performance Comparison](./performance-benchmarks) - Detailed benchmarks
- [Troubleshooting](../advanced/troubleshooting) - Common issues

## Technical Details

### Database Structure

FilterMate creates temporary tables with this structure:

```sql
-- Temporary filtered table
CREATE TEMP TABLE filtermate_filtered_123 (
    fid INTEGER PRIMARY KEY,
    geometry BLOB,
    -- Original attribute columns
    ...
);

-- Register geometry column
SELECT RecoverGeometryColumn(
    'filtermate_filtered_123',
    'geometry',
    4326,  -- SRID
    'POLYGON',
    'XY'
);

-- Create spatial index
SELECT CreateSpatialIndex('filtermate_filtered_123', 'geometry');
```

### Supported Functions

QGIS expressions translated to Spatialite SQL:

| QGIS Expression | Spatialite Function |
|----------------|---------------------|
| `intersects()` | `ST_Intersects()` |
| `contains()` | `ST_Contains()` |
| `within()` | `ST_Within()` |
| `buffer()` | `ST_Buffer()` |
| `distance()` | `ST_Distance()` |
| `area()` | `ST_Area()` |
| `length()` | `ST_Length()` |

### Cleanup

FilterMate automatically cleans up temporary tables:

```sql
-- On plugin close or filter clear
DROP TABLE IF EXISTS filtermate_filtered_123;

-- Reclaim space
VACUUM;
```

---

**Last Updated:** December 8, 2025  
**Plugin Version:** 2.2.3  
**Spatialite Support:** SQLite 3.7+ with Spatialite 4.3+
