---
sidebar_position: 1
---

# Glossary

Essential GIS and FilterMate terminology explained in plain language.

## A

### Attribute
A property or characteristic of a geographic feature stored as data in a table.

**Example**: A building feature might have attributes like `height: 25`, `type: 'residential'`, `year_built: 2015`.

**In FilterMate**: Used in expression-based filtering to select features matching specific criteria.

---

### Attribute Filter
A filter that selects features based on their attribute values rather than spatial relationships.

**Example**:
```sql
population > 100000
city = 'Paris'
year >= 2020
```

**See**: [Filtering Basics](../user-guide/filtering-basics)

---

## B

### Backend
The database engine or processing system FilterMate uses to execute spatial operations.

**Analogy**: Like choosing between a bicycle (OGR), motorcycle (Spatialite), or sports car (PostgreSQL) for your journey.

**Types**:
- **PostgreSQL**: Fastest, best for `>50k` features
- **Spatialite**: Good balance, `<50k` features
- **OGR**: Universal compatibility, slowest

**See**: [Backend Overview](../backends/overview)

---

### Buffer
A zone of specified distance around a geometry, like a "force field" extending outward.

**Visual**:
```
Point buffer:     O → ⭕ (circle)
Line buffer:      ─ → ▭ (capsule)
Polygon buffer:   □ → ▢ (expanded polygon)
```

**Example**: "200m buffer around a road" = all land within 200 meters of the road centerline.

**Buffer Types**:
- **Round (Planar)**: Fast, accurate for small areas
- **Round (Geodesic)**: Accurate for large areas (accounts for Earth's curvature)
- **Square**: Computational optimization (rarely used)

**See**: [Buffer Operations](../user-guide/buffer-operations)

---

### Buffer Distance
The radius or width of a buffer zone, measured in specified units.

**Common Values**:
- **Walkability**: 400-800 meters (5-10 minute walk)
- **Bikeability**: 1-2 kilometers
- **Service Areas**: 5-10 kilometers
- **Environmental Zones**: 50-500 meters

**Units**: meters, kilometers, feet, miles, degrees (avoid for distance)

---

## C

### Coordinate Reference System (CRS)
A mathematical framework that defines how coordinates relate to locations on Earth's surface.

**Common CRS Types**:
- **Geographic** (EPSG:4326): Latitude/Longitude in degrees
- **Projected** (EPSG:3857): X/Y in meters (flat map)
- **Local** (various): Optimized for specific regions

**FilterMate Behavior**: Automatically reprojects layers when needed (you'll see 🔄 indicator).

**See**: [CRS Handling](../user-guide/geometric-filtering#crs-reprojection)

---

## E

### EPSG Code
A standardized numerical identifier for Coordinate Reference Systems.

**Common Codes**:
- **EPSG:4326** - WGS84 (GPS coordinates, worldwide)
- **EPSG:3857** - Web Mercator (Google Maps, web mapping)
- **EPSG:2154** - Lambert 93 (France)
- **EPSG:32633** - UTM Zone 33N (Central Europe)

**Usage**: Specify CRS when exporting or reprojecting layers.

**Find Your CRS**: [epsg.io](https://epsg.io/) search engine

---

### Expression
A formula or query written in QGIS expression language to filter or calculate values.

**Types**:
- **Boolean**: Returns true/false (for filtering)
- **Numeric**: Returns numbers (for calculations)
- **String**: Returns text (for labeling)

**Example**:
```sql
-- Boolean expression for filtering
population > 50000 AND status = 'active'

-- Numeric expression
area / 10000  -- Convert m² to hectares

-- String expression
upper(name) || ' (' || country || ')'
```

**See**: [Expression Cheat Sheet](./cheat-sheets/expressions)

---

## F

### Feature
A single geographic entity (point, line, or polygon) with associated attributes.

**Examples**:
- **Point Feature**: A building location, tree, fire hydrant
- **Line Feature**: A road segment, river, pipeline
- **Polygon Feature**: A parcel boundary, lake, administrative zone

**In QGIS**: Rows in the attribute table represent features.

---

### Filter
A query or condition that selects a subset of features from a layer.

**Types in FilterMate**:
1. **Attribute Filter**: Based on data values
2. **Geometric Filter**: Based on spatial relationships
3. **Combined Filter**: Both attribute AND geometric

**Result**: Temporary view showing only matching features (original data unchanged).

---

## G

### Geodesic
Calculations that account for Earth's curvature (spherical/ellipsoidal).

**Use When**:
- Large geographic areas (countries, continents)
- High-accuracy distance measurements
- Working across multiple UTM zones

**Contrast**: Planar (flat Earth approximation, faster but less accurate at large scales)

**In FilterMate**: Available as "Round (Geodesic)" buffer type.

---

### Geometric Filter
A filter based on spatial relationships between features in different layers.

**Example**: "Find all buildings within 100m of a river"
- **Target**: Buildings layer
- **Reference**: Rivers layer
- **Predicate**: Within Distance
- **Buffer**: 100 meters

**See**: [Geometric Filtering](../user-guide/geometric-filtering)

---

### Geometry
The shape and location of a geographic feature (point, line, polygon, etc.).

**Types**:
- **Point**: Single coordinate (0D)
- **LineString**: Connected points (1D)
- **Polygon**: Closed shape with area (2D)
- **MultiPoint/MultiLineString/MultiPolygon**: Collections

**Common Issues**:
- **Invalid geometry**: Self-intersecting, holes outside boundary
- **NULL geometry**: Missing spatial data
- **Empty geometry**: Valid but contains no coordinates

**Repair**: QGIS Processing → Fix Geometries

---

### GeoPackage (GPKG)
An open, standards-based file format for storing geospatial data.

**Advantages**:
- Single-file (vs Shapefile's multiple files)
- No attribute name length limits
- Supports multiple layers
- Better performance than Shapefile

**Recommended Format**: Best for QGIS workflows and data sharing.

**File Extension**: `.gpkg`

---

### GIST Index
A spatial index type used in PostgreSQL/PostGIS for fast spatial queries.

**Purpose**: Dramatically speeds up spatial operations (10-100× faster).

**FilterMate**: Automatically creates GIST indexes on filtered views.

**Manual Creation**:
```sql
CREATE INDEX idx_geom ON my_table USING GIST(geom);
```

---

## H

### History Manager
FilterMate's built-in undo/redo system for filter operations.

**Features**:
- Tracks up to 100 filter operations
- Undo/redo buttons in toolbar
- Session-based (not saved with project)
- Alternative: Save important filters as Favorites

**See**: [Filter History](../user-guide/filter-history)

---

## L

### Layer
A collection of geographic features of the same type (all points, all polygons, etc.).

**Examples**:
- Roads layer (lines)
- Buildings layer (polygons)
- Trees layer (points)

**In QGIS**: Appears in Layers Panel, can be styled and queried independently.

---

## M

### Materialized View
A database query result stored as a physical table for fast access.

**FilterMate Use**: PostgreSQL backend creates materialized views for filtered data.

**Benefits**:
- Sub-second query times on large datasets
- Spatial indexes automatically created
- Refreshable when data changes

**Performance**: 10-50× faster than on-the-fly queries.

---

## O

### OGR
Open source library for reading/writing vector geospatial data formats.

**FilterMate Backend**: Used for Shapefiles, GeoPackage (when not Spatialite), and other file formats.

**Performance**: Slowest backend but most compatible.

**When Used**:
- Shapefile layers
- GeoPackage layers (non-Spatialite)
- File geodatabases
- GeoJSON files

**See**: [OGR Backend](../backends/ogr)

---

## P

### Planar
Calculations assuming a flat Earth surface (2D Cartesian plane).

**Use When**:
- Small geographic areas (`<100 km²`)
- Local coordinate systems (UTM, State Plane)
- Speed is priority over precision

**Accuracy**: ±0.1% error for areas ``<10km`` across, ±1% for ``<100km``.

**In FilterMate**: Default buffer type "Round (Planar)".

---

### PostGIS
PostgreSQL extension adding spatial database capabilities.

**Features**:
- Advanced spatial functions
- Spatial indexing (GIST)
- Coordinate transformations
- Topology operations

**FilterMate**: Best backend for large datasets (`>50k` features).

**See**: [PostgreSQL Backend](../backends/postgresql)

---

### Predicate
See [Spatial Predicate](#spatial-predicate)

---

### Primary Key
A unique identifier field for each feature in a database table.

**Examples**: `id`, `gid`, `fid`, `objectid`

**Importance**: Required for PostgreSQL layers in QGIS to enable editing.

**FilterMate**: Displays primary key in layer info panel.

---

### psycopg2
Python library for connecting to PostgreSQL databases.

**FilterMate Requirement**: Must be installed for PostgreSQL backend support.

**Installation**: See [Common Mistakes - PostgreSQL Unavailable](../user-guide/common-mistakes#2-backend-postgresql-indisponible)

---

## R

### Reference Layer
In geometric filtering, the layer containing features you're filtering **against** (not the layer being filtered).

**Example**:
```
Goal: Find buildings near roads
Target Layer: Buildings (being filtered)
Reference Layer: Roads (spatial reference)
```

**In FilterMate**: Selected in "Reference Layer" dropdown in Geometric Filter section.

---

## S

### Shapefile
Legacy vector data format widely used in GIS (despite limitations).

**Limitations**:
- Multiple files required (.shp, .shx, .dbf, .prj, etc.)
- 10-character attribute name limit
- 2GB file size limit
- Limited data types

**Modern Alternative**: GeoPackage (GPKG)

**FilterMate**: Supported via OGR backend (slower than PostgreSQL/Spatialite).

---

### Spatial Index
A database structure that speeds up spatial queries by organizing features by location.

**Types**:
- **GIST** (PostgreSQL/PostGIS)
- **R-Tree** (Spatialite)
- **Quadtree** (some file formats)

**Performance Impact**: 10-100× faster spatial queries.

**FilterMate**: Automatically created by PostgreSQL and Spatialite backends.

---

### Spatial Predicate
A test for a specific geometric relationship between two features.

**Common Predicates**:

| Predicate | Meaning | Example Use |
|-----------|---------|-------------|
| **Intersects** | Touch or overlap | Buildings on parcels |
| **Contains** | A completely wraps B | Points in polygons |
| **Within** | A completely inside B | Parcels in city boundary |
| **Crosses** | Lines intersect | Roads crossing railways |
| **Touches** | Share boundary but don't overlap | Adjacent parcels |
| **Disjoint** | Don't touch or overlap | Isolated features |
| **Overlaps** | Partial overlap (same dimension) | Overlapping zones |

**Visual Guide**: See [Spatial Predicates Reference](./cheat-sheets/spatial-predicates)

---

### Spatialite
SQLite extension adding spatial database capabilities.

**Characteristics**:
- File-based (single .sqlite file)
- Good performance for medium datasets (``<50k`` features)
- No server setup required
- Spatial indexing via R-Tree

**FilterMate**: Middle-ground backend between PostgreSQL and OGR.

**See**: [Spatialite Backend](../backends/spatialite)

---

### Subset String
QGIS mechanism for filtering layer features using SQL-like expressions.

**FilterMate**: Applies filters by setting subset strings on layers.

**Example**:
```sql
-- Subset string applied to layer
"population" > 100000 AND "status" = 'active'
```

**View Current Subset**: Layer Properties → Source → Provider Feature Filter

---

## T

### Target Layer
The layer being filtered (features will be selected from this layer).

**Example**:
```
Goal: Find buildings near roads
Target Layer: Buildings ← This layer gets filtered
Reference Layer: Roads
```

**In FilterMate**: Selected in main "Layer Selection" dropdown.

---

## U

### UTM (Universal Transverse Mercator)
A projected coordinate system dividing Earth into 60 zones, each 6° wide.

**Properties**:
- Units: meters
- Good accuracy within each zone
- Minimizes distortion for local areas

**Example CRS**:
- EPSG:32633 - UTM Zone 33N (Central Europe)
- EPSG:32736 - UTM Zone 36S (East Africa)

**Use**: Ideal for local/regional analysis requiring metric measurements.

---

## V

### Vector Layer
Geographic data represented as points, lines, or polygons (vs raster images).

**Components**:
- **Geometry**: Shape and location
- **Attributes**: Data table with properties
- **Style**: Visual appearance on map

**FilterMate**: Works exclusively with vector layers (not rasters).

---

## W

### WGS84
World Geodetic System 1984 - the standard geographic coordinate system.

**EPSG Code**: 4326

**Properties**:
- Units: degrees (latitude/longitude)
- Global coverage
- Used by GPS

**Range**:
- Latitude: -90&deg; to +90&deg; (South to North)
- Longitude: -180&deg; to +180&deg; (West to East)

**FilterMate Behavior**: Automatically converts to EPSG:3857 for metric buffer operations.

---

## Symbols & Icons

### 🔄 Reprojection Indicator
Appears in logs when FilterMate automatically transforms layer CRS.

**Example**: `🔄 Reprojecting from EPSG:4326 to EPSG:3857`

---

### 🌍 Geographic CRS Indicator
Shown when FilterMate detects geographic coordinates and converts for metric operations.

**Example**: `🌍 Geographic CRS detected, using EPSG:3857 for buffer`

---

### ⚡ PostgreSQL Performance Icon
Indicates PostgreSQL backend is active (fastest option).

---

### ⏱️ Spatialite Performance Icon
Indicates Spatialite backend (good performance).

---

### ⚠️ Performance Warning Icon
Shown when using OGR backend on large datasets.

---

### ✓ Valid Expression
Green checkmark indicating expression syntax is correct.

---

### ✗ Invalid Expression
Red X indicating expression has syntax errors.

---

## Need More Detail?

- **User Guide**: [Complete feature documentation](../user-guide/introduction)
- **Cheat Sheets**: [Quick reference cards](./cheat-sheets/expressions)
- **Backends**: [Understanding data sources](../backends/overview)
- **Workflows**: [Real-world examples](../workflows/)

---

## Contribute to Glossary

Missing a term? [Suggest additions on GitHub](https://github.com/sducournau/filter_mate/issues)
