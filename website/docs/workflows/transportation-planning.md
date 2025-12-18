---
sidebar_position: 6
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Transportation Planning: Road Data Export

Extract and export road segments within municipal boundaries with specific attributes for transportation planning analysis.

## Scenario Overview

**Goal**: Export all major roads (highway, primary, secondary) within city limits with proper CRS transformation for CAD/engineering software.

**Real-World Application**:
- Transportation departments preparing data for contractors
- Engineering firms analyzing road networks
- GIS analysts creating data subsets for modeling
- Urban planners evaluating infrastructure coverage

**Estimated Time**: 10 minutes

**Difficulty**: ⭐ Beginner

---

## Prerequisites

### Required Data

1. **Roads Network Layer** (lines)
   - Road segments/centerlines
   - Required attributes:
     - `road_type` or `highway` classification
     - `name` (street name)
   - Optional: `surface`, `lanes`, `speed_limit`, `condition`

2. **Municipality Boundary** (polygon)
   - City, county, or district boundary
   - Single feature preferred (use Dissolve if multiple)
   - Must match or overlap road network extent

### Sample Data Sources

**Roads Data**:
```python
# OpenStreetMap via QuickOSM
Key: "highway", Value: "*"

# Road types to include:
- motorway
- trunk  
- primary
- secondary
- tertiary
```

**Boundaries**:
- Municipal GIS portals (official boundaries)
- Census TIGER/Line files (USA)
- OpenStreetMap administrative boundaries
- National mapping agencies (UK Ordnance Survey, etc.)

### Backend Recommendation

**Any Backend** - This workflow focuses on export features:
- **OGR**: Universal compatibility, works with all formats
- **Spatialite**: If you need temporary processing
- **PostgreSQL**: If exporting very large networks (>100k segments)

All backends export identically - choose based on your setup.

---

## Step-by-Step Instructions

### Step 1: Load and Verify Data

1. **Load layers** into QGIS:
   - `roads_network.gpkg` (or OSM .shp, .geojson)
   - `city_boundary.gpkg`

2. **Check CRS**:
   ```
   Both layers should ideally be in same CRS
   Right-click → Properties → Information → CRS
   
   Note: Not critical for this workflow (FilterMate handles reprojection)
   ```

3. **Inspect attributes**:
   ```
   Open roads attribute table (F6)
   Find road classification field: "highway", "road_type", "fclass", etc.
   Note field name for next step
   ```

4. **Verify boundary**:
   ```
   Select city_boundary layer
   Should show single feature covering your area of interest
   If multiple polygons: Vector → Geoprocessing → Dissolve
   ```

:::tip OSM Road Classifications
OpenStreetMap `highway` values:
- `motorway`: Freeway/interstate
- `trunk`: Major roads between cities
- `primary`: Main roads within cities
- `secondary`: Connecting roads  
- `tertiary`: Local important roads
- `residential`: Neighborhood streets
:::

### Step 2: Filter Roads by Type and Location

**Using FilterMate**:

1. Open FilterMate panel
2. Select **roads_network** layer
3. Choose **any backend** (OGR is fine)
4. Enter filter expression:

<Tabs>
  <TabItem value="osm" label="OpenStreetMap Data" default>
    ```sql
    -- Major roads only (exclude residential, service roads)
    "highway" IN ('motorway', 'trunk', 'primary', 'secondary')
    
    -- Within city boundary
    AND intersects(
      $geometry,
      aggregate(
        layer:='city_boundary',
        aggregate:='collect',
        expression:=$geometry
      )
    )
    ```
  </TabItem>
  
  <TabItem value="generic" label="Generic Road Data">
    ```sql
    -- Adjust field name to match your data
    "road_type" IN ('highway', 'arterial', 'collector')
    
    -- Within municipality
    AND within(
      $geometry,
      aggregate('city_boundary', 'collect', $geometry)
    )
    ```
  </TabItem>
  
  <TabItem value="advanced" label="Advanced Filtering">
    ```sql
    -- Major roads + additional criteria
    "highway" IN ('motorway', 'trunk', 'primary', 'secondary')
    AND intersects($geometry, aggregate('city_boundary', 'collect', $geometry))
    
    -- Optional: Add condition filters
    AND ("surface" = 'paved' OR "surface" IS NULL)  -- Exclude unpaved
    AND "lanes" >= 2  -- Multi-lane only
    AND "access" != 'private'  -- Public roads only
    ```
  </TabItem>
</Tabs>

5. Click **Apply Filter**
6. Review count: "Showing X of Y features"
7. Visually inspect: Only major roads within boundary should be highlighted

**Expected Result**: Road segments filtered to major types within city limits

### Step 3: Review and Refine Selection

**Check coverage**:

1. Zoom to full extent of city_boundary
2. Verify filtered roads cover entire municipality
3. Look for gaps or missing segments

**Adjust if needed**:

```sql
-- If too many roads included, be more strict:
"highway" IN ('motorway', 'trunk', 'primary')  -- Exclude secondary

-- If missing important roads, expand:
"highway" IN ('motorway', 'trunk', 'primary', 'secondary', 'tertiary')

-- If using custom classification:
"functional_class" IN (1, 2, 3)  -- Numeric codes
```

**Edge cases** - Roads partially outside boundary:

<Tabs>
  <TabItem value="include" label="Include Partial Segments" default>
    ```sql
    -- Use intersects (includes partially overlapping)
    intersects($geometry, aggregate('city_boundary', 'collect', $geometry))
    ```
  </TabItem>
  
  <TabItem value="exclude" label="Only Completely Inside">
    ```sql
    -- Use within (only fully contained roads)
    within($geometry, aggregate('city_boundary', 'collect', $geometry))
    ```
  </TabItem>
  
  <TabItem value="clip" label="Clip to Boundary (Manual)">
    After filtering, use QGIS Clip tool:
    ```
    Vector → Geoprocessing → Clip
    Input: filtered roads
    Overlay: city_boundary
    Result: Roads trimmed exactly to boundary
    ```
  </TabItem>
</Tabs>

### Step 4: Select Attributes to Export

**Identify useful fields**:

1. Open **Attribute Table** of filtered layer
2. Note relevant columns:
   ```
   Essential:
   - road_id, osm_id (identifier)
   - name (street name)
   - highway / road_type (classification)
   
   Useful:
   - surface (paved, unpaved, etc.)
   - lanes (number of lanes)
   - maxspeed (speed limit)
   - length_m (calculated or existing)
   ```

3. Optional: **Remove unnecessary columns** before export:
   ```
   Layer → Properties → Fields
   Toggle editing mode (pencil icon)
   Delete unwanted fields (osm metadata, etc.)
   Save edits
   ```

### Step 5: Add Calculated Fields (Optional)

**Add road length** in your preferred units:

1. Open **Field Calculator** (Ctrl+I)
2. Create new field:
   ```
   Field name: length_m
   Type: Decimal (double)
   Precision: 2
   
   Expression:
   $length
   ```

**Add length in different units**:
   ```
   Field name: length_ft
   Expression: $length * 3.28084  -- meters to feet
   
   Field name: length_km
   Expression: $length / 1000  -- meters to kilometers
   ```

**Add functional classification** (if converting OSM data):
   ```
   Field name: functional_class
   Type: Integer
   
   Expression:
   CASE
     WHEN "highway" IN ('motorway', 'trunk') THEN 1
     WHEN "highway" = 'primary' THEN 2
     WHEN "highway" = 'secondary' THEN 3
     WHEN "highway" = 'tertiary' THEN 4
     ELSE 5
   END
   ```

### Step 6: Choose Target CRS for Export

**Common CRS choices**:

<Tabs>
  <TabItem value="wgs84" label="WGS84 (Universal)" default>
    ```
    EPSG:4326 - WGS84 Geographic
    
    Use for:
    - Web mapping (Leaflet, Google Maps)
    - GPS applications
    - Maximum interoperability
    
    ⚠️ Not suitable for CAD (uses degrees, not meters)
    ```
  </TabItem>
  
  <TabItem value="utm" label="UTM (Engineering)">
    ```
    EPSG:326XX - UTM Zones
    Examples:
    - EPSG:32633 - UTM Zone 33N (Central Europe)
    - EPSG:32617 - UTM Zone 17N (Eastern USA)
    
    Use for:
    - CAD software (AutoCAD, MicroStation)
    - Engineering drawings
    - Accurate distance measurements
    
    ✓ Meters-based, preserves accuracy
    ```
  </TabItem>
  
  <TabItem value="state" label="State Plane (USA)">
    ```
    State Plane Coordinate Systems
    Examples:
    - EPSG:2249 - Massachusetts State Plane (meters)
    - EPSG:2278 - Texas State Plane Central (feet)
    
    Use for:
    - Local government projects (USA)
    - Compliance with state standards
    - Integration with official datasets
    ```
  </TabItem>
  
  <TabItem value="local" label="Local Grid">
    ```
    National/Regional Systems
    Examples:
    - EPSG:27700 - British National Grid (UK)
    - EPSG:2154 - Lambert 93 (France)
    - EPSG:3857 - Web Mercator (web maps)
    
    Use for:
    - National mapping agency compatibility
    - Regional standards compliance
    ```
  </TabItem>
</Tabs>

**Find your CRS**:
- Search [epsg.io](https://epsg.io/) by location
- Check project requirements/specifications
- Ask receiving organization for preferred CRS

### Step 7: Export Filtered Roads

**Using FilterMate Export** (Recommended):

1. In FilterMate panel, click **Export Filtered Features**
2. Configure export settings:

   ```
   Format: Choose based on recipient's needs
   
   For GIS:
   ├── GeoPackage (.gpkg) - Best for QGIS/modern GIS
   ├── Shapefile (.shp) - Universal GIS format
   └── GeoJSON (.geojson) - Web mapping, lightweight
   
   For CAD:
   ├── DXF (.dxf) - AutoCAD, most compatible
   └── DWG (.dwg) - AutoCAD (requires plugin)
   
   For Databases:
   ├── PostGIS - Direct database export
   └── Spatialite - Embedded database
   
   For Other:
   ├── CSV with WKT geometry - Text-based
   ├── KML - Google Earth
   └── GPX - GPS devices
   ```

3. **Set CRS** (Coordinate Reference System):
   ```
   Click CRS selector
   Search for target CRS (e.g., "UTM 33N" or "EPSG:32633")
   Select and confirm
   
   ℹ️ FilterMate will reproject automatically
   ```

4. **Configure options**:
   ```
   ✓ Export selected features only (already filtered)
   ✓ Skip attribute fields: [choose unnecessary fields]
   ✓ Add geometry column (for CSV exports)
   ✓ Force multi-linestring type (if required)
   ```

5. **Name and save**:
   ```
   Filename: city_major_roads_utm33n_2024.gpkg
   
   Naming convention tip:
   [location]_[content]_[crs]_[date].[ext]
   ```

6. Click **Export** → Wait for confirmation

### Step 8: Validate Export

**Quality checks**:

1. **Load exported file** back into QGIS:
   ```
   Layer → Add Layer → Add Vector Layer
   Browse to exported file
   ```

2. **Verify CRS**:
   ```
   Right-click layer → Properties → Information
   Check CRS matches your target (e.g., EPSG:32633)
   ```

3. **Check feature count**:
   ```
   Should match filtered count from Step 2
   Open attribute table (F6) to verify
   ```

4. **Inspect attributes**:
   ```
   All selected fields present and populated
   No NULL values in critical fields
   Text encoding correct (no garbled characters)
   ```

5. **Visual comparison**:
   ```
   Overlay exported layer with original
   Verify geometries match exactly
   Check no segments were lost or duplicated
   ```

**Test with recipient's software** (if possible):
- Open in AutoCAD/MicroStation (for DXF exports)
- Load in ArcGIS/MapInfo (for Shapefile)
- Import to database (for SQL exports)

---

## Understanding the Results

### What You've Exported

✅ **Included**:
- Major roads (motorway, trunk, primary, secondary) only
- Roads intersecting/within city boundary
- Selected attributes relevant for analysis
- Geometry reprojected to target CRS

❌ **Excluded**:
- Minor roads (residential, service, paths)
- Roads outside municipality
- OSM metadata and technical fields
- Original CRS (if reprojected)

### File Size Expectations

**Typical sizes** for medium city (500km² area):

```
Format      | ~10k segments | Notes
------------|---------------|----------------------------
GeoPackage  | 2-5 MB        | Smallest, fastest
Shapefile   | 3-8 MB        | Multiple files (.shp/.dbf/.shx)
GeoJSON     | 5-15 MB       | Text-based, larger but readable
DXF         | 4-10 MB       | CAD format
CSV+WKT     | 10-30 MB      | Text geometry, very large
```

**If file unexpectedly large**:
- Check for hidden attributes (OSM metadata)
- Simplify line geometry (Simplify tool, 1-5m tolerance)
- Verify filter actually applied (check feature count)

### Common Export Issues

**Issue 1: "CRS transformation failed"**

**Solution**:
```
1. Verify source layer has valid CRS set
2. Choose different target CRS (try WGS84 first)
3. Reproject layer manually first:
   Vector → Data Management → Reproject Layer
4. Then export without CRS change
```

**Issue 2: "Some features were not exported"**

**Solution**:
```
1. Check for invalid geometries:
   Vector → Geometry Tools → Check Validity
2. Fix invalid geometries:
   Vector → Geometry Tools → Fix Geometries
3. Re-apply filter and export fixed layer
```

**Issue 3: Shapefile truncates field names**

**Limitation**: Shapefile format limits field names to 10 characters

**Solution**:
```
Option A: Use GeoPackage instead (no limits)
Option B: Rename fields before export:
   - "maxspeed_mph" → "max_speed"
   - "functional_classification" → "func_class"
```

---

## Best Practices

### Data Preparation

**Before export checklist**:

```
□ Filter applied and verified
□ Attribute table reviewed
□ Unnecessary fields removed
□ Calculated fields added (length, etc.)
□ Geometries validated
□ CRS determined
□ Export format confirmed with recipient
```

### Naming Conventions

**File naming best practices**:

```
Good:
✓ boston_major_roads_utm19n_20240312.gpkg
✓ denver_highways_stateplane_ft_v2.shp
✓ london_transport_network_bng_2024.geojson

Bad:
✗ roads.shp (too generic)
✗ export_final_FINAL_v3.gpkg (unclear versioning)
✗ データ.gpkg (non-ASCII characters)
```

**Folder structure**:
```
project_name/
├── 01_source_data/
│   ├── roads_raw_osm.gpkg
│   └── boundary_official.shp
├── 02_processed/
│   └── roads_filtered.gpkg
└── 03_deliverables/
    ├── roads_utm33n.gpkg
    ├── roads_utm33n.dxf
    └── metadata.txt
```

### Metadata Documentation

**Always include metadata file**:

```
metadata.txt or README.txt contents:

=== Road Network Export ===
Date: 2024-03-12
Analyst: Jane Smith
Project: City Transportation Master Plan

Source Data:
- Roads: OpenStreetMap (downloaded 2024-03-01)
- Boundary: City GIS Portal (official 2024 boundary)

Processing:
- Filter: Major roads only (motorway, trunk, primary, secondary)
- Area: Within city limits
- Tool: QGIS FilterMate plugin v2.8.0

Export Specifications:
- Format: GeoPackage
- CRS: EPSG:32633 (UTM Zone 33N)
- Feature Count: 8,432 segments
- Total Length: 1,247.3 km

Attributes:
- osm_id: OpenStreetMap identifier
- name: Street name
- highway: Road classification
- surface: Pavement type
- lanes: Number of lanes
- length_m: Segment length in meters

Quality Notes:
- Geometries validated and repaired
- Roads partially outside boundary included (intersects)
- Speed limits: 15% missing data (default to city standard)

Contact: jane.smith@city.gov
```

### Performance Tips

**For large networks** (>50k segments):

1. **Create spatial index** first:
   ```
   Layer Properties → Create Spatial Index
   Speeds up spatial filtering
   ```

2. **Export in chunks** if hitting memory limits:
   ```
   Filter by district/zone, export separately, merge later
   Processing → Vector General → Merge Vector Layers
   ```

3. **Use PostgreSQL backend** for fastest export:
   ```
   Direct database to file export (bypass QGIS memory)
   ```

4. **Simplify geometry** if millimeter precision not needed:
   ```
   Vector → Geometry → Simplify
   Tolerance: 1-5 meters (invisible change, major size reduction)
   ```

---

## Common Issues

### Issue 1: Roads along boundary partially cut off

**Cause**: Using `within()` instead of `intersects()`

**Solution**:
```sql
-- Change from:
within($geometry, aggregate('city_boundary', 'collect', $geometry))

-- To:
intersects($geometry, aggregate('city_boundary', 'collect', $geometry))

-- Or clip geometrically after export:
Vector → Geoprocessing → Clip
```

### Issue 2: Export fails with "write error"

**Cause**: File permissions, path issues, or disk space

**Solutions**:
```
1. Check disk space (need 2-3x final file size)
2. Export to different location (e.g., Desktop instead of network drive)
3. Close file if open in another program
4. Use shorter file path (<100 characters)
5. Remove special characters from filename
```

### Issue 3: CAD software won't open DXF

**Cause**: QGIS DXF export may not match CAD version expectations

**Solutions**:
```
Option A: Try different DXF export settings
   Project → Import/Export → Export Project to DXF
   - DXF format version: AutoCAD 2010
   - Symbology mode: Feature symbology

Option B: Use intermediate format
   Export to Shapefile → Open in AutoCAD (has built-in SHP support)

Option C: Use specialized plugin
   Install "Another DXF Exporter" plugin
   Better CAD compatibility than native export
```

### Issue 4: Attribute encoding issues (special characters)

**Cause**: Shapefile encoding limitations

**Solutions**:
```
For GeoPackage: (Recommended, no encoding issues)
   Format: GeoPackage
   Encoding: UTF-8 (automatic)

For Shapefile:
   Format: ESRI Shapefile
   Encoding: UTF-8 or ISO-8859-1
   Layer Options → ENCODING=UTF-8
```

---

## Next Steps

### Related Workflows

- **[Real Estate Analysis](./real-estate-analysis.md)**: Attribute filtering techniques
- **[Emergency Services](./emergency-services.md)**: Buffer-based selection
- **[Urban Planning Transit](./urban-planning-transit.md)**: Multi-layer spatial filtering

### Advanced Techniques

**1. Network Topology Export**:
```
Export roads with connectivity maintained for routing analysis
Processing → Vector Analysis → Network Analysis → Service Areas
```

**2. Multi-CRS Batch Export**:
```python
# Python console - export to multiple CRS simultaneously
target_crs_list = [32633, 32634, 4326]  # EPSG codes
layer = iface.activeLayer()

for epsg in target_crs_list:
    output_file = f'roads_epsg{epsg}.gpkg'
    # Use QgsVectorFileWriter for programmatic export
```

**3. Scheduled Export Automation**:
```python
# Create QGIS processing model
# Schedule with cron (Linux) or Task Scheduler (Windows)
# Auto-export updated road data weekly
```

**4. Attribute Aggregation** (summarize by road type):
```sql
-- Before export, create summary statistics
GROUP BY "highway"
COUNT(*), SUM($length), AVG("lanes")
```

**5. Multi-Format Batch Export**:
```
Export same filtered data to multiple formats simultaneously
Processing → QGIS Model Designer → Batch export node
Outputs: .gpkg, .shp, .geojson, .dxf
```

### Further Learning

- 📖 [Export Features Guide](../user-guide/export-features.md)
- 📖 [Buffer Operations](../user-guide/buffer-operations.md)
- 📖 [Performance Tuning](../advanced/performance-tuning.md)
- 📖 [QGIS Processing Documentation](https://docs.qgis.org/latest/en/docs/user_manual/processing/index.html)

---

## Summary

✅ **You've learned**:
- Filtering roads by classification and boundary
- Selecting and preparing attributes for export
- Choosing appropriate target CRS
- Exporting to multiple formats (GeoPackage, Shapefile, DXF, etc.)
- Validating export quality
- Creating metadata documentation

✅ **Key techniques**:
- Spatial predicates: `intersects()` vs `within()`
- CRS transformation during export
- Format selection based on use case
- Field calculator for derived attributes
- Batch processing for large datasets

🎯 **Real-world impact**: This workflow streamlines data preparation for transportation projects, ensures data interoperability between GIS and CAD systems, and maintains data quality through the analysis pipeline.

💡 **Pro tip**: Create a **QGIS Processing Model** for this workflow to automate filtering + export in one click. Save the model and reuse for different cities or time periods.

---

## Appendix: Export Format Quick Reference

| Format | Extension | Use Case | Max File Size | CRS Support | Attribute Limits |
|--------|-----------|----------|---------------|-------------|------------------|
| **GeoPackage** | .gpkg | Modern GIS, QGIS | 140 TB | ✓ Any | None |
| **Shapefile** | .shp | Legacy GIS, universal | 2-4 GB | ✓ Any | 10-char field names, 254 chars text |
| **GeoJSON** | .geojson | Web mapping, APIs | Unlimited (but slow if >100 MB) | ✓ Any (WGS84 recommended) | None |
| **DXF** | .dxf | CAD (AutoCAD) | Unlimited | ✓ Limited | Limited attribute support |
| **CSV+WKT** | .csv | Spreadsheets, databases | Unlimited (text) | Manual | None |
| **KML** | .kml | Google Earth | Slow if >10 MB | WGS84 only | Limited styling |
| **PostGIS** | SQL | Database | Unlimited | ✓ Any | None |

**Recommendation**: Use **GeoPackage** unless you have specific compatibility requirements. It's the modern standard with no artificial limitations.
