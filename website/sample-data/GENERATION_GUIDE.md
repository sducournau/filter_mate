# Sample Dataset Generation Guide

**Goal**: Generate `paris_10th.gpkg` GeoPackage for FilterMate tutorials  
**Location**: Paris 10th Arrondissement, France  
**Estimated Time**: 3 hours  
**Tools**: QGIS, Overpass Turbo, Python

---

## 📋 Dataset Specifications

### Target Layers (5 total)

| Layer | Geometry | Features | Key Attributes |
|-------|----------|----------|----------------|
| **buildings** | Polygon | ~3,200 | osm_id, building, height, levels, address, area_m2 |
| **roads** | LineString | ~450 | osm_id, name, highway, surface, lanes, maxspeed, length_m |
| **metro_stations** | Point | 12 | station_name, lines, operator, wheelchair, passenger_count |
| **schools** | Point | 28 | name, school_type, capacity, public_private, address |
| **green_spaces** | Polygon | 15 | name, park_type, area_m2, has_playground, opening_hours |

### Area of Interest (AOI)

**Paris 10th Arrondissement**:
- **Bounding Box**: `48.8647, 2.3479, 48.8844, 2.3742` (lat/lon)
- **CRS Target**: EPSG:2154 (Lambert 93 - France)
- **Area**: ~2.9 km²

---

## 🛠️ Method 1: Overpass API + QGIS (Recommended)

### Step 1: Extract OSM Data

#### 1.1 Buildings

**Overpass Query**:
```overpass
[out:json][timeout:180];
(
  way["building"](48.8647,2.3479,48.8844,2.3742);
  relation["building"](48.8647,2.3479,48.8844,2.3742);
);
out body;
>;
out skel qt;
```

**Run query**:
1. Visit: https://overpass-turbo.eu/
2. Paste query above
3. Click **Run**
4. **Export** → GeoJSON
5. Save as: `buildings_raw.geojson`

#### 1.2 Roads

**Overpass Query**:
```overpass
[out:json][timeout:180];
(
  way["highway"](48.8647,2.3479,48.8844,2.3742);
);
out body;
>;
out skel qt;
```

**Export**: `roads_raw.geojson`

#### 1.3 Metro Stations

**Overpass Query**:
```overpass
[out:json][timeout:180];
(
  node["station"="subway"](48.8647,2.3479,48.8844,2.3742);
  node["railway"="station"]["station"="subway"](48.8647,2.3479,48.8844,2.3742);
);
out body;
>;
out skel qt;
```

**Export**: `metro_stations_raw.geojson`

#### 1.4 Schools

**Overpass Query**:
```overpass
[out:json][timeout:180];
(
  node["amenity"="school"](48.8647,2.3479,48.8844,2.3742);
  node["amenity"="kindergarten"](48.8647,2.3479,48.8844,2.3742);
  way["amenity"="school"](48.8647,2.3479,48.8844,2.3742);
  way["amenity"="kindergarten"](48.8647,2.3479,48.8844,2.3742);
);
out body;
>;
out skel qt;
```

**Export**: `schools_raw.geojson`

#### 1.5 Green Spaces

**Overpass Query**:
```overpass
[out:json][timeout:180];
(
  way["leisure"="park"](48.8647,2.3479,48.8844,2.3742);
  way["leisure"="garden"](48.8647,2.3479,48.8844,2.3742);
  way["leisure"="playground"](48.8647,2.3479,48.8844,2.3742);
  relation["leisure"="park"](48.8647,2.3479,48.8844,2.3742);
);
out body;
>;
out skel qt;
```

**Export**: `green_spaces_raw.geojson`

---

### Step 2: Process in QGIS

#### 2.1 Create GeoPackage

1. Open QGIS
2. **Layer → Create Layer → New GeoPackage Layer**
3. **Database**: `paris_10th.gpkg`
4. **CRS**: EPSG:2154 (Lambert 93)
5. Create **without adding fields** (we'll import data)

#### 2.2 Import Buildings Layer

1. **Layer → Add Layer → Add Vector Layer**
2. Select `buildings_raw.geojson`
3. Right-click layer → **Export → Save Features As**
4. **Format**: GeoPackage
5. **File name**: Select `paris_10th.gpkg`
6. **Layer name**: `buildings`
7. **CRS**: EPSG:2154
8. **Geometry type**: Polygon

**Field Mapping** (rename OSM fields):
```
osm_id          → osm_id (Integer64)
building        → building (String)
height          → height (Real)
building:levels → levels (Integer)
addr:street     → addr_street (String)
addr:housenumber → addr_housenumber (String)
start_date      → construction_year (Integer) [extract year]
```

**Add calculated field** `area_m2`:
```python
# Field Calculator
$area
```

#### 2.3 Import Roads Layer

Repeat export process:
- **Layer name**: `roads`
- **Geometry**: LineString

**Field Mapping**:
```
osm_id    → osm_id (Integer64)
name      → name (String)
highway   → highway (String)
surface   → surface (String)
lanes     → lanes (Integer)
maxspeed  → maxspeed (Integer)
oneway    → oneway (Boolean) [yes/no → True/False]
```

**Add calculated field** `length_m`:
```python
# Field Calculator
$length
```

#### 2.4 Import Metro Stations

**Layer name**: `metro_stations`  
**Geometry**: Point

**Field Mapping**:
```
name          → station_name (String)
line          → lines (String)
operator      → operator (String)
wheelchair    → wheelchair (Boolean)
```

**Manual field** `passenger_count`:
- Add field: Integer
- Populate with approximate annual ridership data (research needed)

**Known Stations in 10th**:
1. Gare du Nord: 50,000,000
2. Gare de l'Est: 34,000,000
3. République: 20,000,000
4. Strasbourg-Saint-Denis: 8,000,000
5. Château d'Eau: 5,000,000
6. Jacques Bonsergent: 3,500,000
7. Belleville: 7,000,000
8. Colonel Fabien: 4,000,000
9. Louis Blanc: 3,000,000
10. Jaurès: 6,000,000
11. Stalingrad: 5,500,000
12. La Chapelle: 4,500,000

#### 2.5 Import Schools Layer

**Layer name**: `schools`  
**Geometry**: Point (convert ways to centroids)

**Field Mapping**:
```
name         → name (String)
amenity      → school_type (String) [school→primary, kindergarten→kindergarten]
```

**Manual fields**:
- `capacity`: Integer (estimate 150-300 per school)
- `public_private`: String (research or default "public")
- `address`: String (use addr:street if available)

#### 2.6 Import Green Spaces

**Layer name**: `green_spaces`  
**Geometry**: Polygon

**Field Mapping**:
```
name    → name (String)
leisure → park_type (String)
```

**Add calculated field** `area_m2`:
```python
$area
```

**Manual fields**:
- `has_playground`: Boolean (check OSM tags or default False)
- `opening_hours`: String (default "08:00-20:00" if missing)

---

### Step 3: Data Validation

#### 3.1 Check Feature Counts

**Expected**:
```
buildings: ~3,200 (target 3,187)
roads: ~450 (target 453)
metro_stations: 12 (exact)
schools: ~28 (target 28)
green_spaces: ~15 (target 15)
```

**QGIS Check**:
```python
# Python Console
for layer in QgsProject.instance().mapLayers().values():
    print(f"{layer.name()}: {layer.featureCount()} features")
```

#### 3.2 Verify CRS

All layers must be EPSG:2154:
```python
# Python Console
for layer in QgsProject.instance().mapLayers().values():
    crs = layer.crs().authid()
    if crs != 'EPSG:2154':
        print(f"❌ {layer.name()}: {crs} (should be EPSG:2154)")
    else:
        print(f"✅ {layer.name()}: {crs}")
```

#### 3.3 Check Geometries

**Validity**:
```python
# Processing Toolbox → Vector geometry → Check validity
# Fix invalid geometries if found
```

**Spatial Index**:
```python
# Python Console
for layer in QgsProject.instance().mapLayers().values():
    layer.dataProvider().createSpatialIndex()
    print(f"✅ Spatial index created for {layer.name()}")
```

---

### Step 4: Create QGIS Project

#### 4.1 Layer Styling

**Buildings**:
```python
# Categorized by building type
# Colors: residential (yellow), commercial (red), industrial (gray)
```

**Roads**:
```python
# Categorized by highway type
# Widths: primary (3), secondary (2), residential (1)
```

**Metro Stations**:
```python
# Single symbol: Blue circle with M icon
# Size: 8pt
```

**Schools**:
```python
# Single symbol: Red circle
# Size: 6pt
```

**Green Spaces**:
```python
# Single symbol: Green fill
# Transparency: 50%
```

#### 4.2 Save Project

1. **Project → Save As**
2. **File name**: `paris_10th.qgz`
3. **Location**: Same folder as `paris_10th.gpkg`
4. **Options**: 
   - ✅ Save layer styles in project
   - ✅ Save paths as relative

---

## 🐍 Method 2: Python Script (Advanced)

### Full Automation Script

```python
#!/usr/bin/env python3
"""
Generate FilterMate sample dataset for Paris 10th arrondissement.
"""
import requests
import geopandas as gpd
from shapely.geometry import Point, LineString, Polygon
import os

# Configuration
BBOX = (48.8647, 2.3479, 48.8844, 2.3742)  # lat_min, lon_min, lat_max, lon_max
OUTPUT_GPKG = "paris_10th.gpkg"
CRS_SOURCE = "EPSG:4326"
CRS_TARGET = "EPSG:2154"

def download_osm_data(query):
    """Download data from Overpass API."""
    url = "https://overpass-api.de/api/interpreter"
    response = requests.post(url, data={"data": query})
    response.raise_for_status()
    return response.json()

def buildings_query():
    return f"""
    [out:json][timeout:180];
    (
      way["building"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
      relation["building"]({BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]});
    );
    out body;
    >;
    out skel qt;
    """

def process_buildings(osm_data):
    """Convert OSM buildings to GeoDataFrame."""
    # Parse OSM JSON and convert to GeoDataFrame
    # Add calculated fields (area_m2)
    # Return GeoDataFrame
    pass  # Implementation here

def main():
    print("FilterMate Sample Dataset Generator")
    print("=" * 50)
    
    # 1. Download data
    print("\n1. Downloading OSM data...")
    buildings_data = download_osm_data(buildings_query())
    # ... other layers
    
    # 2. Process layers
    print("\n2. Processing layers...")
    gdf_buildings = process_buildings(buildings_data)
    # ... other layers
    
    # 3. Reproject to Lambert 93
    print("\n3. Reprojecting to EPSG:2154...")
    gdf_buildings = gdf_buildings.to_crs(CRS_TARGET)
    # ... other layers
    
    # 4. Save to GeoPackage
    print("\n4. Saving to GeoPackage...")
    gdf_buildings.to_file(OUTPUT_GPKG, layer="buildings", driver="GPKG")
    # ... other layers
    
    print(f"\n✅ Dataset created: {OUTPUT_GPKG}")
    print(f"   - buildings: {len(gdf_buildings)} features")
    # ... other counts

if __name__ == "__main__":
    main()
```

**Requirements**:
```bash
pip install geopandas requests shapely
```

---

## 📊 Quality Checklist

### Data Quality

- [ ] All 5 layers present in GeoPackage
- [ ] Feature counts match targets (±10%)
- [ ] All layers in EPSG:2154 (Lambert 93)
- [ ] No invalid geometries
- [ ] Spatial indexes created
- [ ] All required fields present

### Attribute Quality

- [ ] Building heights realistic (5-50m)
- [ ] Road names populated (>80%)
- [ ] Metro station lines correct
- [ ] School types classified
- [ ] Green spaces named

### Tutorial Compatibility

- [ ] **Scenario 1**: 8 schools within 300m of metro ✅
- [ ] **Scenario 2**: ~40 tall buildings near parks ✅
- [ ] **Scenario 3**: ~85 solar candidates (multi-criteria) ✅
- [ ] File size < 10 MB

---

## 🚀 Distribution

### Package Creation

```bash
# Create distribution package
mkdir -p sample-data/screenshots
cp paris_10th.gpkg sample-data/
cp paris_10th.qgz sample-data/
cp README.md sample-data/

# Create archive
zip -r sample-data-v2.3.7.zip sample-data/
```

### Upload Locations

1. **GitHub Releases**: 
   - https://github.com/sducournau/filter_mate/releases/tag/v2.3.7
   - Asset: `sample-data-v2.3.7.zip`

2. **QGIS Plugin Repository**:
   - Optional: Separate "FilterMate Sample Data" plugin
   - Auto-download on user request

3. **Documentation**:
   - Update download links in `website/sample-data/README.md`

---

## 🔧 Troubleshooting

### Overpass API Timeout

**Problem**: Query times out (>180s)

**Solutions**:
1. Reduce bounding box size
2. Split into smaller queries
3. Use local Overpass instance
4. Try different time of day (less load)

### CRS Mismatch

**Problem**: Layers in different CRS

**Solution**:
```python
# Reproject all layers to EPSG:2154
for layer in QgsProject.instance().mapLayers().values():
    if layer.crs().authid() != 'EPSG:2154':
        params = {
            'INPUT': layer,
            'TARGET_CRS': 'EPSG:2154',
            'OUTPUT': f'reprojected_{layer.name()}'
        }
        processing.run("native:reprojectlayer", params)
```

### Missing Attributes

**Problem**: OSM data incomplete

**Solution**:
1. Use default values for missing fields
2. Research public data sources (Paris Open Data)
3. Estimate values based on similar features

### Invalid Geometries

**Problem**: Self-intersecting polygons

**Solution**:
```python
# Fix geometries
processing.run("native:fixgeometries", {
    'INPUT': layer,
    'OUTPUT': 'memory:'
})
```

---

## 📚 Resources

### OSM Documentation

- **Overpass API**: https://wiki.openstreetmap.org/wiki/Overpass_API
- **Overpass Turbo**: https://overpass-turbo.eu/
- **OSM Tags**: https://wiki.openstreetmap.org/wiki/Map_Features

### QGIS Documentation

- **GeoPackage**: https://docs.qgis.org/latest/en/docs/user_manual/managing_data_source/create_layers.html#creating-a-new-geopackage-layer
- **Processing**: https://docs.qgis.org/latest/en/docs/user_manual/processing/toolbox.html

### Python Libraries

- **GeoPandas**: https://geopandas.org/
- **OSMnx**: https://osmnx.readthedocs.io/ (alternative method)
- **Requests**: https://requests.readthedocs.io/

---

## ✅ Completion Checklist

- [ ] All Overpass queries executed
- [ ] GeoJSON files downloaded (5 files)
- [ ] QGIS GeoPackage created
- [ ] All layers imported with correct CRS
- [ ] Field mapping completed
- [ ] Calculated fields added (area_m2, length_m)
- [ ] Manual fields populated (passenger_count, capacity)
- [ ] Data validation passed
- [ ] QGIS project created and styled
- [ ] Tutorial scenarios verified (3 scenarios)
- [ ] Distribution package created
- [ ] Uploaded to GitHub Releases
- [ ] Documentation updated with download links

**Estimated time**: 3 hours (1h download, 1h processing, 1h validation)

---

*Guide version: 1.0 - December 18, 2025*  
*For: FilterMate v2.3.7*
