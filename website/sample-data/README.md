# FilterMate Sample Dataset

**Complete GIS dataset for learning FilterMate**

This package contains real-world geographic data from **Paris 10th Arrondissement** (France) designed for FilterMate tutorials and testing.

---

## 📦 What's Included

### Layers Overview

| Layer | Type | Features | Description | Use Cases |
|-------|------|----------|-------------|-----------|
| **buildings** | Polygon | ~3,200 | Building footprints with heights, types | Attribute filtering, geometric selection |
| **roads** | LineString | ~450 | Road network with classifications | Spatial relationships, buffer analysis |
| **metro_stations** | Point | 12 | Paris Metro stations | Proximity analysis, distance queries |
| **schools** | Point | 28 | Educational facilities (primary/secondary) | Point-in-polygon, within distance |
| **green_spaces** | Polygon | 15 | Parks and public gardens | Contains/Within operations |

**Total dataset size**: ~8 MB (GeoPackage format)  
**Coordinate System**: EPSG:2154 (Lambert 93 - France)  
**Data source**: OpenStreetMap (© OpenStreetMap contributors)  
**License**: ODbL (Open Database License)

---

## 🎯 Quick Start

### Option 1: Direct Download

```bash
# Download from GitHub releases
wget https://github.com/sducournau/filter_mate/releases/download/v2.3.7/sample-data.zip

# Extract
unzip sample-data.zip -d ~/Documents/FilterMate/
```

### Option 2: QGIS Cloud Plugin

1. Install **"FilterMate Sample Data"** plugin from QGIS Plugin Repository
2. Menu: **Plugins → FilterMate Sample Data → Load Paris Dataset**
3. Dataset loads automatically into QGIS

### Option 3: Manual Setup

1. Open QGIS
2. **Layer → Add Layer → Add Vector Layer**
3. Navigate to `sample-data/paris_10th.gpkg`
4. Select all 5 layers or choose specific ones

---

## 📂 File Structure

```
sample-data/
├── README.md                          # This file
├── paris_10th.gpkg                    # Main GeoPackage (all layers)
├── paris_10th.qgz                     # QGIS Project (pre-configured)
├── screenshots/                       # Visual references
│   ├── dataset_overview.png
│   └── layer_styling.png
├── tutorials/                         # Step-by-step guides
│   ├── 01_first_filter.md
│   ├── 02_geometric_filtering.md
│   └── 03_export_workflow.md
└── LICENSE                            # Data license (ODbL)
```

---

## 🗺️ Dataset Details

### 1. Buildings Layer

**Geometry**: Polygon (MultiPolygon)  
**Features**: 3,187 building footprints

**Attributes**:

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `osm_id` | Integer | 123456789 | OpenStreetMap ID |
| `building` | String | "residential" | Building type |
| `height` | Float | 12.5 | Height in meters |
| `levels` | Integer | 4 | Number of floors |
| `addr_street` | String | "Rue de Paradis" | Street address |
| `addr_housenumber` | String | "42" | House number |
| `construction_year` | Integer | 1890 | Year built (if available) |
| `area_m2` | Float | 250.3 | Building area (m²) |

**Sample Queries**:
```sql
-- Tall buildings (>20m)
"height" > 20

-- Residential buildings from 19th century
"building" = 'residential' AND "construction_year" < 1900

-- Large buildings (>500m²)
"area_m2" > 500
```

---

### 2. Roads Layer

**Geometry**: LineString (MultiLineString)  
**Features**: 453 road segments

**Attributes**:

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `osm_id` | Integer | 987654321 | OpenStreetMap ID |
| `name` | String | "Boulevard de Strasbourg" | Road name |
| `highway` | String | "secondary" | Road classification |
| `surface` | String | "asphalt" | Surface type |
| `lanes` | Integer | 2 | Number of lanes |
| `maxspeed` | Integer | 50 | Speed limit (km/h) |
| `oneway` | Boolean | False | One-way street? |
| `length_m` | Float | 145.2 | Length in meters |

**Road Classification** (highway field):
- `primary`: Major roads (Boulevard de Magenta, Rue La Fayette)
- `secondary`: Important streets
- `residential`: Local streets
- `pedestrian`: Pedestrian-only
- `service`: Service roads, parking access

**Sample Queries**:
```sql
-- Major roads only
"highway" IN ('primary', 'secondary')

-- Long streets (>200m)
"length_m" > 200

-- One-way streets
"oneway" = True
```

---

### 3. Metro Stations Layer

**Geometry**: Point  
**Features**: 12 stations

**Attributes**:

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `station_name` | String | "Gare du Nord" | Station name |
| `lines` | String | "4, 5" | Metro line numbers |
| `operator` | String | "RATP" | Operating company |
| `wheelchair` | Boolean | True | Wheelchair accessible? |
| `passenger_count` | Integer | 50000000 | Annual passengers |

**Stations Included**:
1. Gare du Nord (Lines 4, 5)
2. Gare de l'Est (Lines 4, 5, 7)
3. Château d'Eau (Line 4)
4. Strasbourg - Saint-Denis (Lines 4, 8, 9)
5. République (Lines 3, 5, 8, 9, 11)
6. Jacques Bonsergent (Line 5)
7. Belleville (Lines 2, 11)
8. Colonel Fabien (Line 2)
9. Louis Blanc (Line 7, 7bis)
10. Jaurès (Lines 2, 5, 7bis)
11. Stalingrad (Lines 2, 5, 7)
12. La Chapelle (Line 2)

**Sample Queries**:
```sql
-- Major hubs (multiple lines)
array_length(string_to_array("lines", ','), 1) >= 3

-- Accessible stations
"wheelchair" = True

-- High-traffic stations (>20M passengers/year)
"passenger_count" > 20000000
```

---

### 4. Schools Layer

**Geometry**: Point  
**Features**: 28 educational facilities

**Attributes**:

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `name` | String | "École Élémentaire Mozart" | School name |
| `school_type` | String | "primary" | School level |
| `capacity` | Integer | 250 | Student capacity |
| `public_private` | String | "public" | Public or private |
| `address` | String | "10 Rue de la Grange..." | Full address |

**School Types**:
- `primary`: Elementary schools (ages 6-11)
- `secondary`: Middle/high schools (ages 11-18)
- `kindergarten`: Preschools (ages 3-6)

**Sample Queries**:
```sql
-- Public primary schools
"school_type" = 'primary' AND "public_private" = 'public'

-- Large schools (>300 students)
"capacity" > 300

-- Secondary education facilities
"school_type" = 'secondary'
```

---

### 5. Green Spaces Layer

**Geometry**: Polygon (MultiPolygon)  
**Features**: 15 parks and gardens

**Attributes**:

| Field | Type | Example | Description |
|-------|------|---------|-------------|
| `name` | String | "Jardin Villemin" | Park name |
| `park_type` | String | "public_park" | Type of green space |
| `area_m2` | Float | 7200.5 | Area in square meters |
| `has_playground` | Boolean | True | Children's playground? |
| `opening_hours` | String | "06:00-20:00" | Access hours |

**Park Types**:
- `public_park`: Public parks
- `garden`: Public gardens
- `square`: Small urban squares
- `playground`: Dedicated play areas

**Sample Queries**:
```sql
-- Large parks (>5000m²)
"area_m2" > 5000

-- Parks with playgrounds
"has_playground" = True

-- Open early morning
"opening_hours" LIKE '06:%'
```

---

## 📚 Tutorial Scenarios

### Scenario 1: Proximity Analysis (5 min)

**Goal**: Find schools within 300m of metro stations

1. **FILTERING** tab
2. **Reference layer**: metro_stations
3. **Predicate**: Intersects
4. **Buffer**: 300 meters
5. **Result**: Schools with easy transit access

**Expected output**: 8 schools

---

### Scenario 2: Attribute + Geometry (10 min)

**Goal**: Find tall buildings (>15m) in green space buffer zones

1. **FILTERING** tab (geometric)
   - Reference: green_spaces
   - Buffer: 100 meters
2. **ATTRIBUTE** tab: `"height" > 15`
3. **Result**: Tall buildings near parks

**Expected output**: ~40 buildings

**Use case**: Assess shading impact on parks

---

### Scenario 3: Multi-Criteria Selection (15 min)

**Goal**: Identify residential buildings suitable for rooftop solar panels

**Criteria**:
- Height: 10-20m (multi-story but not too tall)
- Building type: residential
- Area: >200m² (roof space)
- Not within 50m of metro (vibration concerns)

**FilterMate Setup**:
1. **ATTRIBUTE** tab:
   ```sql
   "building" = 'residential' 
   AND "height" BETWEEN 10 AND 20 
   AND "area_m2" > 200
   ```
2. **FILTERING** tab:
   - Reference: metro_stations
   - Predicate: Disjoint (or NOT Intersects)
   - Buffer: 50 meters

**Expected output**: ~85 buildings

---

### Scenario 4: Export Workflow (10 min)

**Goal**: Export selected buildings to GeoPackage for external analysis

1. Complete Scenario 3 (multi-criteria selection)
2. Click **EXPORT** tab
3. Configure:
   - Format: GeoPackage
   - Filename: `solar_candidates.gpkg`
   - Options: Include all attributes
4. Export
5. Verify: ~85 features exported

---

## 🎓 Learning Path

### Beginner Path (1-2 hours)

1. ✅ [3-Minute Tutorial](../docs/getting-started/3-minute-tutorial.md)  
   Start here if completely new to FilterMate

2. ✅ [First Attribute Filter](../docs/getting-started/first-filter.md)  
   Learn basic attribute filtering

3. ✅ [Geometric Filtering Basics](../docs/user-guide/geometric-filtering.md)  
   Introduction to spatial operations

4. ✅ **Sample Data Scenario 1** (this README)  
   Proximity analysis hands-on

---

### Intermediate Path (2-4 hours)

5. ✅ [Buffer Operations](../docs/user-guide/buffer-operations.md)  
   Master distance-based queries

6. ✅ [Complex Filters](../docs/user-guide/complex-filters.md)  
   Combine multiple criteria

7. ✅ **Sample Data Scenario 2** (this README)  
   Mixed attribute + geometric filters

8. ✅ [Export Guide](../docs/user-guide/export-options.md)  
   Save and share results

---

### Advanced Path (4+ hours)

9. ✅ [Performance Tuning](../docs/advanced/performance-tuning.md)  
   Optimize large datasets

10. ✅ [Backend Selection](../docs/backends/choosing-backend.md)  
    Choose PostgreSQL vs Spatialite

11. ✅ **Sample Data Scenario 3** (this README)  
    Multi-criteria real-world problem

12. ✅ [Custom Workflows](../docs/workflows/)  
    Urban planning, real estate, environmental

---

## 🔧 Troubleshooting

### Issue: "CRS mismatch" warning

**Cause**: QGIS project CRS ≠ layer CRS

**Solution**:
```
1. Right-click project → Properties → CRS
2. Set to EPSG:2154 (Lambert 93)
3. Reload layers
```

---

### Issue: "No features selected" (but should be)

**Cause**: Buffer distance in wrong units

**Solution**:
- EPSG:2154 uses **meters**
- For 300m buffer, enter: `300` (not `0.003`)
- Check **Status bar** bottom-right for CRS units

---

### Issue: Slow geometric filtering (>30 seconds)

**Cause**: Missing spatial indexes

**Solution**:
```bash
# In QGIS Python console:
from qgis.core import QgsVectorLayer
layer = iface.activeLayer()
layer.dataProvider().createSpatialIndex()
```

Or use FilterMate's auto-index feature (enabled by default).

---

### Issue: Sample data download fails

**Fallback mirror**:
- **GitHub**: https://github.com/sducournau/filter_mate/releases
- **Google Drive**: [Link to be added]
- **Dropbox**: [Link to be added]

---

## 📖 Additional Resources

### Documentation

- 📘 [FilterMate Documentation](https://filtermate.readthedocs.io)
- 📗 [Spatial Predicates Cheat Sheet](../docs/reference/cheat-sheets/spatial-predicates.md)
- 📙 [Expression Reference](../docs/reference/expression-reference.md)

### External Resources

- 🗺️ [OpenStreetMap Wiki](https://wiki.openstreetmap.org)
- 🎓 [QGIS Training Manual](https://docs.qgis.org/latest/en/docs/training_manual/)
- 📊 [PostGIS Documentation](https://postgis.net/documentation/)

---

## 🤝 Contributing

### Improve Sample Data

Have suggestions for additional layers or attributes?

1. Open an issue: [GitHub Issues](https://github.com/sducournau/filter_mate/issues)
2. Tag with: `sample-data`, `enhancement`
3. Describe proposed addition

### Report Data Issues

Found incorrect attributes or geometry errors?

1. Note the layer and `osm_id`
2. Describe the issue
3. Submit via [GitHub Issues](https://github.com/sducournau/filter_mate/issues)

### Add Tutorial Scenarios

Created a useful workflow with this data?

1. Write up your scenario
2. Submit pull request: `tutorials/` folder
3. Follow template: `tutorials/00_template.md`

---

## 📜 License & Attribution

**Data License**: [Open Database License (ODbL)](https://opendatacommons.org/licenses/odbl/)

**Data Source**: © OpenStreetMap contributors  
**Download Date**: October 2024  
**Processing**: FilterMate Development Team

**Attribution Requirements**:
- When publishing results: "Data © OpenStreetMap contributors, ODbL"
- When modifying: Keep this license, acknowledge changes
- When redistributing: Share under same ODbL license

**Learn more**: https://www.openstreetmap.org/copyright

---

## 🔗 Quick Links

| Resource | Link |
|----------|------|
| **Download Dataset** | [GitHub Releases](https://github.com/sducournau/filter_mate/releases/tag/v2.3.7) |
| **Report Issue** | [GitHub Issues](https://github.com/sducournau/filter_mate/issues) |
| **Discussions** | [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions) |
| **Documentation** | [FilterMate Docs](https://filtermate.readthedocs.io) |
| **Plugin Repository** | [QGIS Plugins](https://plugins.qgis.org) |

---

## ✨ What's Next?

After mastering these scenarios:

1. **Explore Real Workflows**:
   - [Urban Planning](../docs/workflows/urban-planning-transit.md)
   - [Real Estate Analysis](../docs/workflows/real-estate-analysis.md)
   - [Environmental Protection](../docs/workflows/environmental-protection.md)

2. **Try Advanced Features**:
   - [Undo/Redo System](../docs/user-guide/undo-redo.md)
   - [Filter History](../docs/user-guide/filter-history.md)
   - [Export Configurations](../docs/user-guide/export-options.md)

3. **Use Your Own Data**:
   - Apply FilterMate to your projects
   - Experiment with different backends
   - Optimize for performance

---

**Questions?** Join our community: [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions)

---

*Last updated: December 18, 2025 for FilterMate v2.3.7*
