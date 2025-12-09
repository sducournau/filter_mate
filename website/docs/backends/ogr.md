---
sidebar_position: 4
---

# OGR Backend

The OGR backend provides **universal compatibility** with all vector formats supported by QGIS through the GDAL/OGR library. It serves as a reliable fallback when PostgreSQL or Spatialite backends are unavailable.

:::tip Universal Compatibility
OGR backend works with **all vector formats**: Shapefiles, GeoPackage, GeoJSON, KML, DXF, CSV, and 80+ more formats.
:::

## Overview

FilterMate's OGR backend uses QGIS's processing framework and memory layers to perform geometric filtering. While not as fast as database backends for large datasets, it provides excellent compatibility and requires no additional setup.

### Key Benefits

- ✅ **Universal format support** - works with any OGR-readable format
- 🔧 **No setup required** - built into QGIS
- 📦 **Portable** - works with local and remote files
- 🌐 **Web formats** - GeoJSON, KML, etc.
- 💾 **Memory layers** - temporary in-memory processing
- 🚀 **Automatic** - fallback when other backends unavailable

## When OGR Backend Is Used

FilterMate automatically selects the OGR backend when:

1. ✅ Layer source is **not** PostgreSQL or Spatialite
2. ✅ Layer provider is `ogr` (Shapefile, GeoPackage, etc.)
3. ✅ Fallback when psycopg2 is unavailable for PostgreSQL layers

**Common Formats Using OGR Backend:**
- Shapefile (`.shp`)
- GeoPackage (`.gpkg`)
- GeoJSON (`.geojson`, `.json`)
- KML/KMZ (`.kml`, `.kmz`)
- DXF/DWG (CAD formats)
- CSV with geometry (`.csv`)
- GPS Exchange (`.gpx`)
- And 80+ more formats

## Installation

### Prerequisites

- **QGIS 3.x** (includes GDAL/OGR)
- **No additional packages needed**

### Verification

OGR is always available in QGIS. Check supported formats:

```python
# In QGIS Python Console
from osgeo import ogr

driver_count = ogr.GetDriverCount()
print(f"✓ {driver_count} OGR drivers available")

# List some common drivers
for driver_name in ['ESRI Shapefile', 'GPKG', 'GeoJSON', 'KML']:
    driver = ogr.GetDriverByName(driver_name)
    if driver:
        print(f"  ✓ {driver_name}")
```

## Features

### 1. Memory Layers

FilterMate creates **memory layers** for filtered results:

```python
# Example memory layer created by FilterMate
from qgis.core import QgsVectorLayer

memory_layer = QgsVectorLayer(
    f"Point?crs=epsg:4326&field=id:integer&field=name:string",
    "filtered_layer",
    "memory"
)

# Copy filtered features
for feature in source_layer.getFeatures(expression):
    memory_layer.dataProvider().addFeature(feature)
```

**Benefits:**
- Fast creation
- No disk I/O
- Automatic cleanup
- Works with all formats

**Limitations:**
- Held in RAM - not suitable for very large datasets
- Lost when QGIS closes (unless saved)

### 2. QGIS Processing Framework

OGR backend leverages QGIS processing algorithms:

```python
# FilterMate uses QGIS processing for complex operations
import processing

result = processing.run("native:extractbyexpression", {
    'INPUT': layer,
    'EXPRESSION': 'ST_Intersects($geometry, geometry(@filter_layer))',
    'OUTPUT': 'memory:'
})

filtered_layer = result['OUTPUT']
```

**Available Operations:**
- Extract by expression
- Extract by location
- Buffer
- Intersection
- Union
- Clip
- And 300+ more algorithms

### 3. Format Compatibility Matrix

| Format | Read | Write | Spatial Index | Performance |
|--------|------|-------|---------------|-------------|
| Shapefile | ✅ | ✅ | ⚠️ .qix files | Good |
| GeoPackage | ✅ | ✅ | ✅ R-tree | Excellent |
| GeoJSON | ✅ | ✅ | ❌ | Good |
| KML/KMZ | ✅ | ✅ | ❌ | Good |
| CSV | ✅ | ✅ | ❌ | Fair |
| DXF/DWG | ✅ | ⚠️ Limited | ❌ | Fair |
| GPX | ✅ | ✅ | ❌ | Good |
| GML | ✅ | ✅ | ❌ | Good |
| FlatGeobuf | ✅ | ✅ | ✅ Built-in | Excellent |

:::tip Best Formats for OGR Backend
For optimal performance: **GeoPackage** or **FlatGeobuf** (both have spatial indexes)
:::

### 4. Spatial Predicate Support

OGR backend supports most spatial predicates through QGIS expressions:

| Predicate | Support | Notes |
|-----------|---------|-------|
| `intersects` | ✅ Full | Via QGIS expression |
| `contains` | ✅ Full | Via QGIS expression |
| `within` | ✅ Full | Via QGIS expression |
| `touches` | ⚠️ Limited | Some formats |
| `crosses` | ⚠️ Limited | Some formats |
| `overlaps` | ⚠️ Limited | Some formats |
| `disjoint` | ✅ Full | Via QGIS expression |
| `buffer` | ✅ Full | QGIS processing |

**Example:**

```python
# QGIS expression for intersects
expression = 'intersects($geometry, geometry(@filter_layer))'

# FilterMate applies to OGR layer
layer.setSubsetString(expression)  # If format supports
# OR
filtered_features = [f for f in layer.getFeatures() if expression.evaluate(f)]
```

## Configuration

### Format-Specific Options

Configure OGR backend behavior in `config/config.json`:

```json
{
  "OGR": {
    "use_memory_layers": true,
    "enable_spatial_index": true,
    "max_features_in_memory": 100000,
    "prefer_geopackage": true
  }
}
```

### Shapefile Spatial Indexes

For Shapefiles, create `.qix` spatial index:

```python
# In QGIS Python Console
layer = iface.activeLayer()
layer.dataProvider().createSpatialIndex()

# Or via processing
processing.run("native:createspatialindex", {
    'INPUT': layer
})
```

This creates `myfile.qix` next to `myfile.shp`.

### GeoPackage Optimization

GeoPackage has built-in R-tree indexes:

```sql
-- Check spatial index (in GeoPackage)
SELECT * FROM sqlite_master
WHERE type = 'table' AND name LIKE 'rtree_%';

-- Rebuild if needed
DROP TABLE IF EXISTS rtree_my_layer_geometry;
-- QGIS will recreate automatically
```

## Usage

### Basic Filtering

1. **Load any vector layer** in QGIS
2. **Open FilterMate** plugin
3. **Configure filter** options
4. **Click "Apply Filter"**

FilterMate automatically:
- Detects OGR backend
- Creates memory layer
- Copies filtered features
- Adds layer to QGIS
- Displays backend indicator: **[OGR]**

### Format Recommendations

**Best Performance:**
- GeoPackage (`.gpkg`) - has spatial indexes
- FlatGeobuf (`.fgb`) - optimized for streaming

**Good Performance:**
- Shapefile (`.shp`) - with `.qix` index
- GeoJSON (`.geojson`) - for smaller datasets

**Acceptable Performance:**
- KML (`.kml`) - for web/Google Earth
- CSV (`.csv`) - for simple point data

**Slower Performance:**
- DXF/DWG - complex CAD formats
- Remote services (WFS) - network latency

### Saving Filtered Results

Memory layers are temporary. To persist:

```python
# In QGIS, right-click filtered layer → Export → Save Features As
# Or via code:
from qgis.core import QgsVectorFileWriter

QgsVectorFileWriter.writeAsVectorFormat(
    memory_layer,
    "/path/to/output.gpkg",
    "UTF-8",
    layer.crs(),
    "GPKG"
)
```

## Performance Tuning

### For Small Datasets (< 10k features)

- **No special configuration needed**
- All formats work well
- Memory layers are fast

### For Medium Datasets (10k - 50k features)

- **Use GeoPackage or Shapefile with .qix index**
- **Enable memory layers** (default)
- **Consider Spatialite backend** instead (5x faster)

```json
{
  "OGR": {
    "use_memory_layers": true,
    "enable_spatial_index": true
  }
}
```

### For Large Datasets (50k - 500k features)

:::warning Performance Recommendation
**Switch to PostgreSQL or Spatialite** for 5-10x better performance. OGR backend is not optimal for large datasets.
:::

If must use OGR:
- **Use GeoPackage** (best format for large data)
- **Disable memory layers** (reduce RAM usage):
  ```json
  {
    "OGR": {
      "use_memory_layers": false,
      "write_to_disk": true,
      "temp_directory": "/fast/ssd/path"
    }
  }
  ```
- **Create spatial indexes**
- **Filter in stages** if very slow

### For Very Large Datasets (> 500k features)

❌ **OGR backend not recommended**

**Alternatives:**
1. **Migrate to PostgreSQL** - 10-100x faster
2. **Use Spatialite** - 5-10x faster
3. **Tile/partition data** - split into manageable chunks

## Limitations

### Compared to Database Backends

| Feature | OGR | Spatialite | PostgreSQL |
|---------|-----|-----------|-----------|
| Max practical size | ~50k features | ~500k features | 10M+ features |
| Spatial indexes | ⚠️ Format-dependent | ✅ R-tree | ✅ GIST |
| Memory usage | ⚠️ High | ✅ Low | ✅ Very low |
| Server-side ops | ❌ No | ❌ No | ✅ Yes |
| Concurrent access | ⚠️ Limited | ⚠️ Limited | ✅ Excellent |
| Query optimization | ❌ Basic | ✅ Good | ✅ Excellent |

### Format-Specific Limitations

**Shapefile:**
- 2GB file size limit
- 254 character field name limit
- No mixed geometry types
- Date/time limited precision

**GeoJSON:**
- No spatial index support
- Can be very large (verbose format)
- Slower parsing on large files

**KML:**
- Limited attribute support
- No true spatial operations
- Better for visualization than analysis

**CSV:**
- Geometry stored as WKT (slow parsing)
- No spatial index
- Not recommended for large datasets

## Troubleshooting

### Issue: "Layer has no spatial index"

**Symptom:** Slow queries despite small dataset

**Solution:**

For **Shapefile**, create .qix index:
```python
layer.dataProvider().createSpatialIndex()
```

For **GeoPackage**, rebuild R-tree:
```python
# Open in DB Manager and run:
# DROP TABLE rtree_layer_name_geometry;
# Then reload layer
```

### Issue: "Out of memory"

**Symptom:** QGIS crashes on large dataset

**Solution:**

1. **Disable memory layers:**
   ```json
   {
     "OGR": {
       "use_memory_layers": false
     }
   }
   ```

2. **Switch to GeoPackage format** (more efficient)

3. **Use PostgreSQL or Spatialite backend** instead

### Issue: "Filtering very slow"

**Symptom:** Takes minutes for small dataset

**Solution:**

1. **Check for spatial index:**
   ```python
   # Shapefile - check for .qix file
   # GeoPackage - check for rtree table
   ```

2. **Simplify geometry** if complex:
   ```python
   processing.run("native:simplifygeometries", {
       'INPUT': layer,
       'METHOD': 0,  # Distance
       'TOLERANCE': 1,  # meters
       'OUTPUT': 'memory:'
   })
   ```

3. **Use simpler predicates** - `intersects` faster than `touches`

### Issue: "Format not supported"

**Symptom:** Cannot open file

**Solution:**

1. **Check GDAL/OGR version:**
   ```python
   from osgeo import gdal
   print(gdal.VersionInfo())
   ```

2. **List available drivers:**
   ```python
   from osgeo import ogr
   for i in range(ogr.GetDriverCount()):
       print(ogr.GetDriver(i).GetName())
   ```

3. **Convert to supported format:**
   ```bash
   ogr2ogr -f GPKG output.gpkg input.xyz
   ```

## Format Conversion

### To GeoPackage (Recommended)

```bash
# Command line (ogr2ogr)
ogr2ogr -f GPKG output.gpkg input.shp

# Python
import processing
processing.run("native:package", {
    'LAYERS': [layer],
    'OUTPUT': '/path/to/output.gpkg'
})
```

### To Shapefile

```bash
ogr2ogr -f "ESRI Shapefile" output.shp input.gpkg
```

### To GeoJSON

```bash
ogr2ogr -f GeoJSON output.geojson input.shp
```

## Performance Benchmarks

Real-world performance on typical hardware (Core i7, 16GB RAM, SSD):

| Dataset Size | Features | OGR (Shapefile) | OGR (GeoPackage) | Spatialite | PostgreSQL |
|-------------|----------|----------------|-----------------|-----------|-----------|
| Small | 5,000 | 0.8s | 0.6s | 0.4s | 0.3s |
| Medium | 50,000 | 25s | 15s | 8.5s | 1.2s |
| Large | 500,000 | Timeout | 180s | 65s | 8.4s |

**Format Comparison (50k features):**

| Format | Load Time | Filter Time | Total | Spatial Index |
|--------|-----------|------------|-------|---------------|
| GeoPackage | 2.3s | 12.7s | 15.0s | ✅ Yes |
| Shapefile + .qix | 3.1s | 21.9s | 25.0s | ✅ Yes |
| Shapefile (no index) | 3.1s | 87.2s | 90.3s | ❌ No |
| GeoJSON | 4.8s | 45.3s | 50.1s | ❌ No |
| KML | 6.2s | 52.7s | 58.9s | ❌ No |

## Best Practices

### ✅ Do

- **Use GeoPackage for best OGR performance**
- **Create spatial indexes** (.qix for Shapefile)
- **Keep datasets < 50k features** for OGR backend
- **Use for universal format compatibility**
- **Test format conversion** if performance is poor

### ❌ Don't

- **Don't use OGR for > 100k features** - too slow
- **Don't forget spatial indexes** - huge performance impact
- **Don't use CSV/GeoJSON for large data** - no spatial index
- **Don't rely on Shapefile for production** - consider GeoPackage
- **Don't use memory layers for huge datasets** - will crash

## Migrating to Better Backends

### When to Switch to Spatialite

**Indicators:**
- Dataset > 10k features
- Need better query performance
- Want persistent results

**Migration:**
```python
# Export to Spatialite
from qgis.core import QgsVectorFileWriter

options = QgsVectorFileWriter.SaveVectorOptions()
options.driverName = "SQLite"
options.datasourceOptions = ["SPATIALITE=YES"]

QgsVectorFileWriter.writeAsVectorFormatV3(
    layer,
    "/path/to/output.sqlite",
    QgsCoordinateTransformContext(),
    options
)
```

### When to Switch to PostgreSQL

**Indicators:**
- Dataset > 50k features
- Need concurrent access
- Want server-side operations
- Need best performance

**Migration:**
```bash
# Using ogr2ogr
ogr2ogr -f PostgreSQL \
  PG:"host=localhost dbname=mydb user=myuser" \
  input.gpkg \
  -lco GEOMETRY_NAME=geometry \
  -lco SPATIAL_INDEX=GIST
```

## See Also

- [Backends Overview](./overview.md) - Multi-backend architecture
- [Backend Selection](./choosing-backend.md) - Automatic selection logic
- [PostgreSQL Backend](./postgresql.md) - For best performance
- [Spatialite Backend](./spatialite.md) - For medium datasets
- [Performance Comparison](./performance-benchmarks.md) - Detailed benchmarks

## Technical Details

### Memory Layer Creation

```python
# FilterMate creates memory layers like this
from qgis.core import QgsVectorLayer, QgsFeature

# Create memory layer with same structure
uri = f"{geom_type}?crs={crs_string}"
for field in source_layer.fields():
    uri += f"&field={field.name()}:{field.typeName()}"

memory_layer = QgsVectorLayer(uri, "filtered", "memory")

# Copy filtered features
features = []
for feature in source_layer.getFeatures(expression):
    features.append(QgsFeature(feature))

memory_layer.dataProvider().addFeatures(features)
```

### Supported OGR Drivers

Common drivers in QGIS 3.x:

- `ESRI Shapefile` - .shp files
- `GPKG` - GeoPackage
- `GeoJSON` - .geojson, .json
- `KML` - .kml, .kmz
- `CSV` - .csv with geometry
- `GPX` - GPS Exchange
- `DXF` - AutoCAD DXF
- `GML` - Geography Markup Language
- `Memory` - In-memory layers
- `FlatGeobuf` - .fgb (streaming format)

Check all available:
```python
from osgeo import ogr
for i in range(ogr.GetDriverCount()):
    driver = ogr.GetDriver(i)
    print(f"{driver.GetName()}: {driver.GetMetadata().get('DMD_LONGNAME', '')}")
```

---

**Last Updated:** December 8, 2025  
**Plugin Version:** 2.2.3  
**OGR/GDAL Support:** Version included with QGIS 3.x
