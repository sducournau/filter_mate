# Paris 10th Dataset - Python Script Documentation

## Overview

This directory contains an automated Python script to generate the **paris_10th.gpkg** sample dataset for FilterMate tutorials.

## Files

- **generate_paris_10th_dataset.py** - Main generation script (450+ lines)
- **requirements.txt** - Python dependencies
- **README.md** - Dataset documentation (main)
- **README_SCRIPT.md** - This file (script usage guide)

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `requests` - HTTP library for Overpass API
- `geopandas` - Geospatial data processing
- `shapely` - Geometry operations
- `pyproj` - Coordinate system transformations

### 2. Run Script

```bash
python generate_paris_10th_dataset.py
```

### 3. Output

- **paris_10th.gpkg** - GeoPackage with 5 layers (~8 MB)
- **generation_report.txt** - Validation report

## Script Features

### 🌍 Data Source

- **Provider**: OpenStreetMap via Overpass API
- **Area**: Paris 10th Arrondissement
- **Bounding Box**: 
  - South: 48.8698°N
  - North: 48.8830°N
  - West: 2.3516°E
  - East: 2.3730°E

### 📊 Generated Layers

| Layer | Type | Expected Count | Attributes |
|-------|------|----------------|------------|
| **buildings** | Polygon | ~3,200 | area_m2, building_type, osm_id |
| **roads** | LineString | ~450 | length_m, road_type, road_name |
| **metro_stations** | Point | 12 | station_name, lines |
| **schools** | Polygon | 28 | school_name, school_type |
| **green_spaces** | Polygon | 15 | area_m2, park_name, leisure_type |

### ✅ Validation Scenarios

The script automatically validates the dataset against tutorial scenarios:

1. **Schools Near Metro** - Count schools within 300m of metro stations
2. **Large Buildings** - Filter buildings > 500m²
3. **Main Roads** - Identify primary/secondary/tertiary roads
4. **Large Parks** - Find green spaces > 5,000m²

## Script Usage

### Basic Usage

```bash
# Generate dataset with default settings
python generate_paris_10th_dataset.py
```

### Expected Output

```
============================================================
🏗️  FilterMate Sample Dataset Generator
============================================================

Target: paris_10th.gpkg
CRS: EPSG:2154 (Lambert 93)
Bounding Box: Paris 10th Arrondissement

📥 Downloading data from OpenStreetMap...
------------------------------------------------------------
🌍 Querying Overpass API for buildings... ✅ 3245 elements
✅ Created buildings: 3199 features
💾 Saved buildings to paris_10th.gpkg

🌍 Querying Overpass API for roads... ✅ 502 elements
✅ Created roads: 456 features
💾 Saved roads to paris_10th.gpkg

🌍 Querying Overpass API for metro_stations... ✅ 12 elements
✅ Created metro_stations: 12 features
💾 Saved metro_stations to paris_10th.gpkg

🌍 Querying Overpass API for schools... ✅ 35 elements
✅ Created schools: 28 features
💾 Saved schools to paris_10th.gpkg

🌍 Querying Overpass API for green_spaces... ✅ 18 elements
✅ Created green_spaces: 15 features
💾 Saved green_spaces to paris_10th.gpkg

🔍 Validating dataset...

============================================================
📊 DATASET VALIDATION REPORT
============================================================

✅ Total Features: 3710

📋 Layers:
  ✅ buildings: 3199 features
     CRS: EPSG:2154
  ✅ roads: 456 features
     CRS: EPSG:2154
  ✅ metro_stations: 12 features
     CRS: EPSG:2154
  ✅ schools: 28 features
     CRS: EPSG:2154
  ✅ green_spaces: 15 features
     CRS: EPSG:2154

🎯 Tutorial Scenarios:

  ✅ Schools Near Metro
     count: 8
     expected: 8-12
     status: ✅

  ✅ Large Buildings
     count: 892
     total: 3199
     percentage: 27.9%
     status: ✅

  ✅ Main Roads
     count: 45
     total: 456
     status: ✅

  ✅ Large Parks
     count: 3
     total: 15
     status: ✅

============================================================

💾 Validation report saved to generation_report.txt

============================================================
✅ GENERATION COMPLETE
============================================================
⏱️  Time elapsed: 45.2 seconds
📦 Output: /path/to/paris_10th.gpkg
💾 File size: 7.84 MB

🎯 Next Steps:
  1. Open QGIS
  2. Drag & drop paris_10th.gpkg into map canvas
  3. Follow tutorials in FilterMate documentation
  4. Try the 4 tutorial scenarios!
============================================================
```

## Troubleshooting

### Error: Missing Package

```
❌ Missing required package: No module named 'geopandas'

Install required packages:
  pip install requests geopandas shapely pyproj
```

**Solution**: Install dependencies with `pip install -r requirements.txt`

### Error: Overpass API Timeout

```
⏱️  Timeout (attempt 1/3)
⏱️  Timeout (attempt 2/3)
```

**Causes**:
- Overpass API server overload
- Slow internet connection
- Large area query

**Solutions**:
1. Wait 5 minutes and retry
2. Check internet connection
3. Use alternative Overpass instance (edit `OVERPASS_URL` in script)

### Error: No Features Found

```
⚠️  No features found for schools
⚠️  Skipped schools (no features)
```

**Causes**:
- OSM data missing in area
- Incorrect bounding box
- Wrong OSM tags

**Solutions**:
1. Check OSM data availability: https://www.openstreetmap.org/#map=15/48.8764/2.3623
2. Verify bounding box coordinates
3. Adjust Overpass queries in script

### Warning: File Exists

```
⚠️  paris_10th.gpkg already exists. Overwrite? [y/N]:
```

**Solution**: Type `y` to overwrite, or `N` to cancel and backup existing file

## Script Customization

### Change Bounding Box

Edit the `BBOX` dictionary in the script:

```python
BBOX = {
    "south": 48.8698,  # Your south latitude
    "west": 2.3516,    # Your west longitude
    "north": 48.8830,  # Your north latitude
    "east": 2.3730     # Your east longitude
}
```

### Change CRS

Edit the `TARGET_CRS` variable:

```python
TARGET_CRS = "EPSG:2154"  # Lambert 93 (France)
# or
TARGET_CRS = "EPSG:3857"  # Web Mercator
# or
TARGET_CRS = "EPSG:4326"  # WGS84
```

### Add Custom Attributes

Modify the layer creation section:

```python
if layer_name == "buildings":
    gdf['area_m2'] = gdf.geometry.area
    gdf['building_type'] = gdf.get('building', 'yes')
    gdf['custom_field'] = gdf.get('osm_tag', 'default_value')  # ADD THIS
```

### Adjust Timeout

Edit the Overpass query timeout:

```python
queries = {
    "buildings": f"""
[out:json][timeout:120];  # Change from 60 to 120 seconds
...
"""
}
```

## Performance

### Expected Runtime

| Operation | Time | Notes |
|-----------|------|-------|
| Buildings download | ~10s | Largest dataset |
| Roads download | ~5s | Medium dataset |
| Metro stations | ~2s | Small dataset |
| Schools download | ~3s | Small dataset |
| Green spaces | ~3s | Small dataset |
| Processing | ~5s | Reprojection + attributes |
| Validation | ~2s | Scenario checks |
| **TOTAL** | **~45s** | With 2s delays between queries |

### Optimization Tips

1. **Remove delays** for faster execution (but respect Overpass API rate limits):
   ```python
   # time.sleep(2)  # Comment out this line
   ```

2. **Parallel queries** (advanced, requires threading):
   ```python
   from concurrent.futures import ThreadPoolExecutor
   
   with ThreadPoolExecutor(max_workers=3) as executor:
       # Submit queries
   ```

3. **Cache results** to avoid re-downloading:
   ```python
   cache_file = f"{layer_name}_cache.json"
   if Path(cache_file).exists():
       with open(cache_file) as f:
           osm_data = json.load(f)
   ```

## Technical Details

### Coordinate Systems

- **Input**: EPSG:4326 (WGS84) - OSM default
- **Output**: EPSG:2154 (Lambert 93) - French official projection
- **Reason**: Accurate metric calculations (area, distance, buffers)

### Geometry Processing

1. **Points**: Direct conversion from OSM nodes
2. **LineStrings**: Concatenated node sequences
3. **Polygons**: Closed ways with ≥4 nodes
4. **Relations**: Expanded to member geometries

### Attribute Mapping

| OSM Tag | GeoPackage Attribute | Type | Example |
|---------|---------------------|------|---------|
| building | building_type | String | "residential" |
| highway | road_type | String | "secondary" |
| name | *_name | String | "École Élémentaire" |
| amenity | school_type | String | "school" |
| leisure | leisure_type | String | "park" |

### Validation Logic

```python
# Scenario 1: Buffer + spatial join
schools_buffered = metro.buffer(300).unary_union
schools_near = schools[schools.intersects(schools_buffered)]

# Scenario 2: Attribute filter
large_buildings = buildings[buildings['area_m2'] > 500]

# Scenario 3: Multi-value filter
main_roads = roads[roads['road_type'].isin(['primary', 'secondary'])]
```

## Integration with QGIS

### Load Dataset in QGIS Python Console

```python
from qgis.core import QgsVectorLayer, QgsProject

# Load all layers
layers = ["buildings", "roads", "metro_stations", "schools", "green_spaces"]
for layer_name in layers:
    uri = f"/path/to/paris_10th.gpkg|layername={layer_name}"
    layer = QgsVectorLayer(uri, layer_name, "ogr")
    if layer.isValid():
        QgsProject.instance().addMapLayer(layer)
```

### Use with FilterMate Plugin

```python
# Get active layer
layer = iface.activeLayer()

# Apply filter (FilterMate expression)
layer.setSubsetString('"area_m2" > 500')

# Export filtered features
from modules.appTasks import FilterTask

task = FilterTask(
    description="Export large buildings",
    layer=layer,
    output_path="/path/to/output.gpkg"
)
QgsApplication.taskManager().addTask(task)
```

## FAQ

### Q: Can I use this for other cities?

**A:** Yes! Just change the bounding box coordinates and verify OSM data availability.

### Q: Why Lambert 93 (EPSG:2154)?

**A:** It's the official French projection system, providing accurate metric measurements for Paris.

### Q: How often should I regenerate the dataset?

**A:** OSM data changes daily. Regenerate every 3-6 months for tutorial stability.

### Q: Can I use this script in production?

**A:** The script is designed for sample data generation. For production, use dedicated ETL tools like osmium or osm2pgsql.

### Q: What if Overpass API is down?

**A:** 
1. Check status: https://overpass-api.de/api/status
2. Use alternative instances: https://wiki.openstreetmap.org/wiki/Overpass_API#Public_Overpass_API_instances
3. Download OSM extract and use local osmium

### Q: Can I add more layers?

**A:** Yes! Add new entries to the `layers` dictionary and create corresponding Overpass queries.

Example:
```python
layers = {
    # ... existing layers
    "restaurants": "point"
}

# Add query
queries = {
    # ... existing queries
    "restaurants": f"""
[out:json][timeout:60];
node["amenity"="restaurant"]({bbox_str});
out body;
"""
}
```

## License

This script is part of FilterMate documentation and is licensed under GPL v3.

## Resources

- **Overpass API**: https://overpass-api.de/
- **Overpass Turbo** (test queries): https://overpass-turbo.eu/
- **OSM Tags**: https://wiki.openstreetmap.org/wiki/Map_features
- **GeoPandas Docs**: https://geopandas.org/
- **QGIS Python API**: https://qgis.org/pyqgis/

## Support

For issues with the script:
1. Check GENERATION_GUIDE.md for manual alternatives
2. Open issue on GitHub: https://github.com/sducournau/filter_mate/issues
3. Join QGIS community: https://qgis.org/community/

---

**Generated**: December 2025  
**FilterMate Version**: v2.3.7  
**Script Version**: 1.0.0
