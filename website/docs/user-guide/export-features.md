---
sidebar_position: 6
---

# Export Features

Export filtered features to various formats including GeoPackage, Shapefile, GeoJSON, CSV, and more.

## Overview

After filtering features, you can **export** the results to create standalone datasets for:
- **Sharing** with colleagues or clients
- **Analysis** in other software
- **Archiving** snapshots of data
- **Publishing** web maps
- **Reporting** tabular data

### Supported Formats

| Format | Type | Best For | Max Size |
|--------|------|----------|----------|
| **GeoPackage** | Vector | General use, large datasets | Unlimited |
| **Shapefile** | Vector | Legacy compatibility | 2 GB |
| **GeoJSON** | Vector | Web mapping, APIs | \~500 MB |
| **KML/KMZ** | Vector | Google Earth, mobile | \~100 MB |
| **CSV** | Tabular | Spreadsheets, coordinates only | Unlimited |
| **PostGIS** | Database | Large datasets, enterprise | Unlimited |
| **Spatialite** | Database | Medium datasets, portable | \~140 TB |

## Export Workflow

```mermaid
sequenceDiagram
    participant U as User
    participant FM as FilterMate
    participant Q as QGIS
    participant DB as Backend
    participant F as File System
    
    U->>FM: Apply filter
    FM->>Q: Filter layer
    Q->>U: Show filtered count
    
    U->>FM: Click Export
    FM->>U: Show format options
    U->>FM: Select format + settings
    
    FM->>Q: Prepare export
    
    alt Database Backend
        Q->>DB: Query filtered features
        DB->>Q: Return feature stream
    else File Backend
        Q->>Q: Read filtered features
    end
    
    Q->>F: Write to output format
    F->>Q: Confirm write
    Q->>FM: Export complete
    FM->>U: Success message (1,234 features exported)
```

## Format Details

### GeoPackage (.gpkg)

**Recommended format** for most use cases.

**Advantages:**
- ✅ Single file (portable)
- ✅ Unlimited size
- ✅ Multiple layers per file
- ✅ Spatial indexes built-in
- ✅ Open standard (OGC)
- ✅ Fast performance
- ✅ Supports all geometry types

**Limitations:**
- ⚠️ Requires GDAL 2.0+ (standard in modern QGIS)

**When to Use:**
- Default choice for most exports
- Large datasets (&gt;100k features)
- Multi-layer exports
- Long-term archiving

**Export Example:**
```python
output_file = "/path/to/export.gpkg"
layer_name = "filtered_features"
# Single file, multiple layers possible
```

### Shapefile (.shp)

Legacy format for **backward compatibility**.

**Advantages:**
- ✅ Universal compatibility
- ✅ Widely supported
- ✅ Simple structure

**Limitations:**
- ❌ 2 GB file size limit
- ❌ 10-character field name limit
- ❌ Limited data types
- ❌ Multiple files (.shp, .dbf, .shx, .prj)
- ❌ No mixed geometry types
- ⚠️ Encoding issues (non-ASCII characters)

**When to Use:**
- Required by legacy software
- Sharing with ArcGIS Desktop 9.x users
- Simple, small datasets

**Recommendations:**
- Use GeoPackage instead when possible
- Keep feature count &lt; 100k
- Avoid long field names
- Test encoding with non-ASCII characters

**Export Example:**
```python
output_file = "/path/to/export.shp"
# Creates .shp, .dbf, .shx, .prj files
```

### GeoJSON (.geojson)

Text-based format for **web applications**.

**Advantages:**
- ✅ Human-readable
- ✅ Web-friendly
- ✅ JavaScript native
- ✅ API integration
- ✅ Version control friendly

**Limitations:**
- ⚠️ Large file sizes (text format)
- ⚠️ Slower performance than binary formats
- ⚠️ No spatial indexes
- ⚠️ WGS84 (EPSG:4326) recommended

**When to Use:**
- Web mapping (Leaflet, Mapbox)
- REST APIs
- Small to medium datasets (&lt;10k features)
- Git version control

**Export Example:**
```python
output_file = "/path/to/export.geojson"
crs = "EPSG:4326"  # WGS84 recommended for web
```

### KML/KMZ (.kml, .kmz)

Format for **Google Earth** and mobile apps.

**Advantages:**
- ✅ Google Earth compatibility
- ✅ KMZ includes styling and images
- ✅ Mobile app support
- ✅ Human-readable (KML)

**Limitations:**
- ❌ Limited attribute support
- ❌ Styling complexity
- ⚠️ Performance issues with large datasets
- ⚠️ WGS84 only (EPSG:4326)

**When to Use:**
- Google Earth visualization
- Mobile field apps
- Stakeholder presentations
- Public engagement

**Export Example:**
```python
output_file = "/path/to/export.kmz"  # Compressed
# or
output_file = "/path/to/export.kml"  # Text
```

### CSV (.csv)

**Tabular format** for coordinates and attributes.

**Advantages:**
- ✅ Universal spreadsheet compatibility
- ✅ Small file size
- ✅ Easy to edit
- ✅ Database import friendly

**Limitations:**
- ❌ No geometry (only X,Y coordinates for points)
- ❌ No spatial reference
- ❌ No styling
- ⚠️ Points only (no lines/polygons)

**When to Use:**
- Point coordinates only
- Excel/spreadsheet analysis
- Attribute-only reports
- Database imports

**Export Example:**
```python
output_file = "/path/to/export.csv"
# Includes X, Y columns for point geometry
# GEOMETRY_AS: 'AS_XY' or 'AS_WKT'
```

### PostGIS (PostgreSQL)

Export to **PostgreSQL database** with PostGIS extension.

**Advantages:**
- ✅ Best performance
- ✅ Unlimited size
- ✅ Multi-user access
- ✅ Spatial indexes
- ✅ Advanced querying
- ✅ Enterprise features

**Limitations:**
- ⚠️ Requires PostgreSQL + PostGIS
- ⚠️ Network setup needed
- ⚠️ More complex administration

**When to Use:**
- Enterprise environments
- Large datasets (&gt;1M features)
- Multi-user collaboration
- Continuous updates
- Integration with backend systems

**Export Example:**
```python
connection = "postgresql://user:password@host:5432/database"
schema = "public"
table_name = "filtered_features"
```

### Spatialite (.sqlite)

Lightweight **database file**.

**Advantages:**
- ✅ Single file
- ✅ Spatial indexes
- ✅ SQL queries
- ✅ Good performance
- ✅ No server needed

**Limitations:**
- ⚠️ Slower than PostGIS
- ⚠️ Single-writer limitation
- ⚠️ 140 TB theoretical max

**When to Use:**
- Portable databases
- Medium datasets (10k-1M features)
- Offline work
- Desktop applications

**Export Example:**
```python
output_file = "/path/to/export.sqlite"
table_name = "filtered_features"
```

## Export Options

### Coordinate Reference System (CRS)

Choose the target CRS for your export:

```python
# Keep original CRS
crs = layer.crs()

# Transform to WGS84 (web/GPS)
crs = "EPSG:4326"

# Transform to local projection
crs = "EPSG:32633"  # UTM Zone 33N
```

**Common CRS Choices:**
- **EPSG:4326** (WGS84) - Web maps, GPS, global
- **EPSG:3857** (Web Mercator) - Web tiles
- **EPSG:32xxx** (UTM) - Local projected, metric
- **Original CRS** - Maintain source projection

### Field Selection

Export specific fields or all attributes:

```python
# All fields
export_fields = None

# Selected fields only
export_fields = ['name', 'population', 'area', 'date']

# Exclude fields
exclude_fields = ['internal_id', 'temp_field']
```

### Geometry Type

Control geometry export:

```python
# Keep geometry (default)
geometry = True

# Attribute-only (no geometry)
geometry = False

# Simplify geometry (reduce size)
geometry = "simplified"
simplify_tolerance = 10  # meters
```

### Encoding

Character encoding for text fields:

```python
# UTF-8 (recommended, default)
encoding = "UTF-8"

# Latin-1 (Western Europe)
encoding = "ISO-8859-1"

# Windows-1252 (Windows default)
encoding = "CP1252"
```

## Export Strategies

### Large Dataset Export

For datasets &gt; 100k features:

```mermaid
graph TD
    A[Large Dataset] --> B{Size Check}
    B -->|&lt; 100k| C[Direct Export]
    B -->|100k - 1M| D[GeoPackage]
    B -->|&gt; 1M| E[PostGIS]
    
    D --> F[Enable Spatial Index]
    E --> G[Batch Processing]
    
    F --> H[Export Complete]
    G --> H
    C --> H
    
    style D fill:#90EE90
    style E fill:#87CEEB
```

**Recommendations:**
1. **Use GeoPackage or PostGIS** - Binary formats
2. **Enable spatial indexes** - Faster subsequent access
3. **Batch processing** - Export in chunks if needed
4. **Simplify geometry** - Reduce vertex count if appropriate

### Multi-Format Export

Export the same data to multiple formats:

```python
# Export workflow
filter_applied = True

# Web version (GeoJSON)
export_geojson(crs="EPSG:4326", simplified=True)

# Desktop version (GeoPackage)
export_geopackage(crs=original_crs, full_precision=True)

# Spreadsheet version (CSV)
export_csv(coordinates="XY", attributes_only=False)
```

### Incremental Exports

Export changes since last update:

```python
# Filter by date
filter_expression = "last_modified >= '2024-01-01'"

# Export with timestamp
output_file = f"updates_{datetime.now().strftime('%Y%m%d')}.gpkg"
```

## Practical Examples

### Urban Planning Export

```python
# Export filtered parcels for review
filter_expression = """
zone = 'commercial'
AND area > 5000
AND status = 'proposed'
"""

# Multiple formats for different stakeholders
export_geopackage("parcels_review.gpkg")  # GIS team
export_kml("parcels_review.kmz")  # Public presentation
export_csv("parcels_list.csv")  # Planning board
```

### Environmental Monitoring

```python
# Export monitoring sites with recent data
filter_expression = """
site_type = 'water_quality'
AND last_sample >= now() - interval '30 days'
AND parameter_count > 5
"""

# GeoJSON for web dashboard
export_geojson(
    output="monitoring_sites.geojson",
    crs="EPSG:4326",
    fields=['site_id', 'last_sample', 'status']
)
```

### Emergency Response

```python
# Export evacuation zones
filter_expression = """
intersects(
    $geometry,
    buffer(geometry(get_feature('hazard', 'status', 'active')), 2000)
)
AND occupancy > 0
"""

# KML for field teams
export_kml("evacuation_zones.kmz")

# GeoPackage for GIS analysis
export_geopackage("evacuation_analysis.gpkg")
```

## Performance Optimization

### Backend Comparison

| Backend | Export Speed | Recommended |
|---------|--------------|-------------|
| PostgreSQL | ⚡⚡⚡⚡ Fastest | GeoPackage, PostGIS |
| Spatialite | ⚡⚡⚡ Fast | GeoPackage, Spatialite |
| OGR | ⚡⚡ Moderate | GeoPackage |

### Optimization Tips

1. **Simplify Geometry**
   ```python
   # Reduce vertex count
   simplify_tolerance = 10  # meters
   ```

2. **Select Necessary Fields**
   ```python
   # Export only needed attributes
   fields = ['id', 'name', 'status']
   ```

3. **Use Appropriate Format**
   ```python
   # Binary formats faster than text
   GeoPackage > Shapefile > GeoJSON
   ```

4. **Enable Spatial Indexes**
   ```python
   # For GeoPackage/Spatialite
   create_spatial_index = True
   ```

## Troubleshooting

### Export Fails

**Common Issues:**

1. **File Locked**
   - Close applications using the file
   - Check file permissions

2. **Disk Space**
   - Verify available space
   - Use compression (KMZ, GPKG)

3. **Invalid Geometries**
   ```sql
   -- Filter invalid geometries before export
   is_valid($geometry)
   ```

4. **Encoding Issues**
   - Use UTF-8 encoding
   - Test with sample features

### Large File Size

**Solutions:**

1. **Simplify geometry**
   ```python
   simplify_tolerance = 10  # Reduce precision
   ```

2. **Reduce attributes**
   ```python
   fields = ['essential_field_1', 'essential_field_2']
   ```

3. **Use compression**
   ```python
   # KMZ instead of KML
   # GPKG has internal compression
   ```

4. **Split into tiles**
   ```python
   # Export by region or grid
   filter_expression = "region = 'north'"
   ```

### Projection Issues

**Solutions:**

1. **Verify source CRS**
   ```python
   source_crs = layer.crs()
   print(f"Source: {source_crs.authid()}")
   ```

2. **Transform explicitly**
   ```python
   target_crs = "EPSG:4326"
   ```

3. **Check transformation accuracy**
   ```python
   # Use appropriate transformation
   # Especially for historic datums
   ```

## Batch Export

Export multiple filtered layers:

```python
# Define exports
exports = [
    {
        'layer': 'parcels',
        'filter': "zone = 'commercial'",
        'output': 'commercial_parcels.gpkg'
    },
    {
        'layer': 'buildings',
        'filter': "year_built > 2020",
        'output': 'recent_buildings.gpkg'
    }
]

# Process batch
for export_config in exports:
    apply_filter(export_config['layer'], export_config['filter'])
    export_layer(export_config['output'])
```

## Related Topics

- [Filtering Basics](filtering-basics.md) - Create filters
- [Geometric Filtering](geometric-filtering.md) - Spatial filters
- [Buffer Operations](buffer-operations.md) - Proximity analysis
- [Backend Performance](../backends/performance-comparison.md) - Optimize exports

## Next Steps

- **[Filter History](filter-history.md)** - Reuse filter configurations
- **[Advanced Features](advanced-features.md)** - Complex export workflows
- **[Backend Selection](../backends/backend-selection.md)** - Choose optimal backend for exports
