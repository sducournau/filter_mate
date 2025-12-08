---
sidebar_position: 2
---

# PostgreSQL Backend

The PostgreSQL backend provides **optimal performance** for FilterMate, especially with large datasets. It leverages server-side spatial operations, materialized views, and spatial indexes for ultra-fast filtering.

:::tip Performance Champion
PostgreSQL is recommended for datasets **> 50,000 features** and required for datasets **> 500,000 features**.
:::

## Overview

FilterMate's PostgreSQL backend connects directly to your PostGIS-enabled database to perform geometric filtering operations server-side. This approach dramatically reduces data transfer and processing time compared to client-side filtering.

### Key Benefits

- ⚡ **Sub-second queries** on million+ feature datasets
- 🔧 **Materialized views** for persistent filtered results
- 🗺️ **GIST spatial indexes** for optimized spatial searches
- 🚀 **Server-side processing** reduces network overhead
- 💾 **Memory efficient** - processes data in the database
- ⚙️ **Concurrent operations** - multiple filters don't slow down

## When PostgreSQL Backend Is Used

FilterMate automatically selects the PostgreSQL backend when:

1. ✅ Layer source is PostgreSQL/PostGIS
2. ✅ `psycopg2` Python package is installed
3. ✅ Database connection is available

If `psycopg2` is **not** installed, FilterMate falls back to Spatialite or OGR backends with a performance warning for large datasets.

## Installation

### Prerequisites

- **PostgreSQL 9.5+** with **PostGIS 2.3+** extension
- **QGIS 3.x** with PostgreSQL connection configured
- **Python 3.7+** (included with QGIS)

### Installing psycopg2

Choose the method that works best for your environment:

#### Method 1: pip (Recommended)

```bash
pip install psycopg2-binary
```

#### Method 2: QGIS Python Console

Open QGIS Python Console (Ctrl+Alt+P) and run:

```python
import pip
pip.main(['install', 'psycopg2-binary'])
```

#### Method 3: OSGeo4W Shell (Windows)

```bash
# Open OSGeo4W Shell as Administrator
py3_env
pip install psycopg2-binary
```

#### Method 4: Conda (if using conda environment)

```bash
conda install -c conda-forge psycopg2
```

### Verification

Check if psycopg2 is available:

```python
# In QGIS Python Console
try:
    import psycopg2
    print(f"✓ psycopg2 version: {psycopg2.__version__}")
except ImportError:
    print("✗ psycopg2 not installed")
```

## Features

### 1. Materialized Views

FilterMate creates **materialized views** in PostgreSQL to store filtered results persistently:

```sql
-- Example materialized view created by FilterMate
CREATE MATERIALIZED VIEW filtermate_filtered_view_123 AS
SELECT *
FROM my_layer
WHERE ST_Intersects(
    geometry,
    (SELECT geometry FROM filter_layer WHERE id = 1)
);

-- Spatial index automatically created
CREATE INDEX idx_filtermate_filtered_view_123_geom
ON filtermate_filtered_view_123
USING GIST (geometry);
```

**Benefits:**
- Results cached in database
- Instant refresh on subsequent filters
- Shareable across QGIS sessions
- Automatic cleanup on plugin close

### 2. Server-Side Spatial Operations

All geometric operations execute **in the database**:

- `ST_Intersects()` - Find intersecting features
- `ST_Contains()` - Find containing features  
- `ST_Within()` - Find features within boundaries
- `ST_Buffer()` - Create buffers server-side
- `ST_Distance()` - Calculate distances

**Performance Impact:**

| Operation | Client-Side (Python) | Server-Side (PostGIS) |
|-----------|---------------------|----------------------|
| 10k features | ~5 seconds | ~0.5 seconds (10x faster) |
| 100k features | ~60 seconds | ~2 seconds (30x faster) |
| 1M features | Timeout/crash | ~10 seconds (100x+ faster) |

### 3. GIST Spatial Indexes

FilterMate ensures your geometries have **GIST indexes** for optimal query performance:

```sql
-- Check existing indexes
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'my_layer';

-- FilterMate creates GIST indexes automatically
CREATE INDEX IF NOT EXISTS idx_my_layer_geom
ON my_layer
USING GIST (geometry);
```

:::info Automatic Index Management
FilterMate checks for spatial indexes and creates them if missing. This one-time operation may take a few seconds on large tables.
:::

### 4. Query Optimization

The PostgreSQL backend applies several optimizations:

- **Bounding box pre-filtering** - Uses `&&` operator before expensive operations
- **Parallel query execution** - Leverages PostgreSQL's parallel workers
- **Prepared statements** - Reuses query plans for repeated filters
- **ANALYZE statistics** - Ensures optimal query planning

Example optimized query:

```sql
-- Bounding box filter first (fast)
WHERE geometry && ST_Buffer(filter_geom, 100)
  -- Then expensive intersection check (only on bbox matches)
  AND ST_Intersects(geometry, ST_Buffer(filter_geom, 100))
```

## Configuration

### Database Connection

FilterMate uses QGIS's existing PostgreSQL connection. Ensure your connection is configured:

1. **Layer → Data Source Manager → PostgreSQL**
2. **New** connection with details:
   - Name: `my_postgis_db`
   - Host: `localhost` (or remote host)
   - Port: `5432`
   - Database: `my_database`
   - Authentication: Basic or stored credentials

### Performance Settings

Optimize PostgreSQL for spatial queries:

```sql
-- In postgresql.conf or per-session

-- Increase work memory for large sorts
SET work_mem = '256MB';

-- Enable parallel query execution
SET max_parallel_workers_per_gather = 4;

-- Optimize for spatial operations
SET random_page_cost = 1.1;  -- For SSD storage
```

### Schema Permissions

FilterMate requires these PostgreSQL permissions:

```sql
-- Minimum required permissions
GRANT CONNECT ON DATABASE my_database TO filter_mate_user;
GRANT USAGE ON SCHEMA public TO filter_mate_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO filter_mate_user;
GRANT CREATE ON SCHEMA public TO filter_mate_user;  -- For temp views
```

## Usage

### Basic Filtering

1. **Load PostgreSQL layer** in QGIS
2. **Open FilterMate** plugin
3. **Configure filter** options
4. **Click "Apply Filter"**

FilterMate automatically:
- Detects PostgreSQL backend
- Creates materialized view
- Adds filtered layer to QGIS
- Displays backend indicator: **[PG]**

### Advanced Options

#### Custom Schema

Specify custom schema for materialized views:

```python
# In config/config.json
{
  "POSTGRESQL": {
    "schema": "filtermate_temp",
    "auto_cleanup": true
  }
}
```

#### Connection Pooling

For multiple simultaneous filters:

```python
# FilterMate handles connection pooling automatically
# Max connections: 5 (configurable)
```

## Performance Tuning

### For Small Datasets (< 10k features)

- **No special configuration needed**
- PostgreSQL performs similarly to Spatialite
- Use default settings

### For Medium Datasets (10k - 100k features)

- **Ensure spatial indexes exist**
- **Increase `work_mem` to 128MB**
- **Enable parallel workers (2-4)**

```sql
ALTER TABLE my_layer SET (parallel_workers = 2);
```

### For Large Datasets (100k - 1M features)

- **Increase `work_mem` to 256MB+**
- **Increase `parallel_workers` to 4-8**
- **Run `VACUUM ANALYZE` regularly**

```sql
VACUUM ANALYZE my_layer;
```

### For Very Large Datasets (> 1M features)

- **Partition tables by spatial extent**
- **Use table inheritance**
- **Consider table clustering by geometry**

```sql
-- Cluster table by spatial index
CLUSTER my_layer USING idx_my_layer_geom;
```

## Troubleshooting

### Issue: "psycopg2 not found"

**Symptom:** FilterMate shows OGR/Spatialite backend for PostgreSQL layers

**Solution:**
1. Install psycopg2 (see Installation section)
2. Restart QGIS
3. Verify installation in Python Console

### Issue: "Permission denied to create view"

**Symptom:** Error when applying filter

**Solution:**
```sql
-- Grant CREATE permission
GRANT CREATE ON SCHEMA public TO your_user;

-- Or use a dedicated schema
CREATE SCHEMA filtermate_temp;
GRANT ALL ON SCHEMA filtermate_temp TO your_user;
```

### Issue: "Slow queries despite PostgreSQL"

**Symptom:** Queries take longer than expected

**Solution:**
1. **Check for spatial indexes:**
   ```sql
   SELECT * FROM pg_indexes WHERE tablename = 'your_table';
   ```

2. **Run ANALYZE:**
   ```sql
   ANALYZE your_table;
   ```

3. **Check query plan:**
   ```sql
   EXPLAIN ANALYZE
   SELECT * FROM your_table
   WHERE ST_Intersects(geometry, ST_GeomFromText('POLYGON(...)'));
   ```

4. **Look for "Seq Scan"** - if present, index not being used

### Issue: "Connection timeout"

**Symptom:** FilterMate hangs when applying filter

**Solution:**
- Increase PostgreSQL `statement_timeout`
- Check network connectivity
- Verify database server is responsive

```sql
-- Increase timeout to 5 minutes
SET statement_timeout = '300s';
```

## Performance Benchmarks

Real-world performance on typical hardware (Core i7, 16GB RAM, SSD):

| Dataset Size | Features | PostgreSQL | Spatialite | Speedup |
|-------------|----------|-----------|-----------|---------|
| Small | 5,000 | 0.3s | 0.4s | 1.3x |
| Medium | 50,000 | 1.2s | 8.5s | 7x |
| Large | 500,000 | 8.4s | 65s | 8x |
| Very Large | 5,000,000 | 45s | Timeout | 10x+ |

**Spatial Operations:**

| Operation | 100k Features | 1M Features |
|-----------|--------------|-------------|
| Intersects | 1.5s | 9.2s |
| Contains | 1.8s | 11.5s |
| Buffer (10m) + Intersects | 2.3s | 15.1s |
| Complex expression | 3.1s | 18.7s |

## Best Practices

### ✅ Do

- **Use PostgreSQL for datasets > 50k features**
- **Ensure spatial indexes exist before filtering**
- **Run VACUUM ANALYZE after bulk data updates**
- **Use connection pooling for multiple filters**
- **Monitor query performance with EXPLAIN**

### ❌ Don't

- **Don't mix spatial reference systems** - reproject beforehand
- **Don't create too many materialized views** - FilterMate auto-cleans up
- **Don't disable spatial indexes** - huge performance penalty
- **Don't run complex expressions without testing** - use EXPLAIN first

## See Also

- [Backends Overview](./overview.md) - Multi-backend architecture
- [Backend Selection](./backend-selection.md) - Automatic selection logic
- [Performance Comparison](./performance-comparison.md) - Detailed benchmarks
- [Spatialite Backend](./spatialite.md) - Alternative for smaller datasets
- [Troubleshooting](../advanced/troubleshooting.md) - Common issues

## Technical Details

### Connection Management

FilterMate uses `psycopg2` for database connections:

```python
import psycopg2
from qgis.core import QgsDataSourceUri

# Extract connection from QGIS layer
uri = QgsDataSourceUri(layer.source())
conn = psycopg2.connect(
    host=uri.host(),
    port=uri.port(),
    database=uri.database(),
    user=uri.username(),
    password=uri.password()
)
```

### Materialized View Lifecycle

1. **Creation** - When filter applied
2. **Usage** - QGIS loads as virtual layer
3. **Refresh** - On filter parameter change
4. **Cleanup** - On plugin close or manual cleanup

### Supported PostGIS Functions

FilterMate translates QGIS expressions to PostGIS functions:

| QGIS Expression | PostGIS Function |
|----------------|------------------|
| `intersects()` | `ST_Intersects()` |
| `contains()` | `ST_Contains()` |
| `within()` | `ST_Within()` |
| `buffer()` | `ST_Buffer()` |
| `distance()` | `ST_Distance()` |
| `area()` | `ST_Area()` |
| `length()` | `ST_Length()` |

---

**Last Updated:** December 8, 2025  
**Plugin Version:** 2.2.3  
**PostgreSQL Support:** 9.5+ with PostGIS 2.3+
