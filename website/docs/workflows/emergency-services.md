---
sidebar_position: 4
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Emergency Services: Coverage Analysis

Identify areas that lack adequate emergency service coverage to optimize facility placement and response planning.

## Scenario Overview

**Goal**: Find residential areas more than 5km from the nearest fire station to identify service coverage gaps.

**Real-World Application**:
- Fire departments optimizing station placement
- Emergency management planning response times
- Urban planners evaluating service equity
- Insurance companies assessing risk zones

**Estimated Time**: 12 minutes

**Difficulty**: ⭐⭐ Intermediate

---

## Prerequisites

### Required Data

1. **Fire Stations Layer** (points)
   - Emergency service facility locations
   - Must include station names/IDs
   - Covers your study area

2. **Population Areas Layer** (polygons)
   - Census blocks, neighborhoods, or postal zones
   - Population count attribute (optional but valuable)
   - Residential land use areas

3. **Optional: Road Network**
   - For drive-time analysis (advanced)
   - Network topology for routing

### Sample Data Sources

**Option 1: OpenStreetMap**
```python
# Use QGIS QuickOSM plugin

# For fire stations:
Key: "amenity", Value: "fire_station"

# For residential areas:
Key: "landuse", Value: "residential"
Key: "place", Value: "neighbourhood"
```

**Option 2: Government Open Data**
- Municipal emergency services databases
- Census boundary files with population
- HIFLD (Homeland Infrastructure Foundation-Level Data)
- Local GIS data portals

### Backend Recommendation

**OGR** - Best for this workflow:
- Universal format compatibility (Shapefiles, GeoJSON, GeoPackage)
- No complex setup required
- Good for datasets &lt;10,000 features
- Works with any QGIS installation

---

## Step-by-Step Instructions

### Step 1: Load and Prepare Data

1. **Load layers** into QGIS:
   - `fire_stations.gpkg` (or .shp, .geojson)
   - `residential_areas.gpkg`

2. **Verify CRS**:
   ```
   Both layers must use same projected coordinate system
   Right-click → Properties → Information → CRS
   
   Recommended: Local UTM zone or state/national grid
   Example: EPSG:32633 (UTM Zone 33N)
   ```

3. **Inspect data**:
   - Count fire stations: Should have at least 3-5 for meaningful analysis
   - Check residential areas: Look for population or household count attributes
   - Verify coverage: Fire stations should be distributed across study area

:::tip Finding Your UTM Zone
Use [epsg.io](https://epsg.io/) and click on map to find appropriate UTM zone for your region.
:::

### Step 2: Create 5km Service Areas Around Fire Stations

**Using FilterMate**:

1. Open FilterMate, select **fire_stations** layer
2. Enter expression:
   ```sql
   -- Keep all fire stations
   1 = 1
   ```
3. Enable **Buffer** operation:
   - Distance: `5000` meters
   - Type: Positive (expand)
   - Segments: 16 (for smooth circles)
4. **Apply Filter**
5. **Export** as `fire_coverage_5km.gpkg`

**Result**: Circular 5km buffers around each fire station (service coverage zones)

### Step 3: Identify Under-Served Residential Areas (Inverse Query)

This is the key step - finding areas **NOT** within 5km of any fire station:

<Tabs>
  <TabItem value="ogr" label="OGR / Spatialite" default>
    **Method 1: Using FilterMate (Recommended)**
    
    1. Select **residential_areas** layer
    2. Choose **OGR** backend
    3. Enter expression:
    ```sql
    -- Residential areas NOT intersecting fire coverage
    NOT intersects(
      $geometry,
      aggregate(
        layer:='fire_coverage_5km',
        aggregate:='collect',
        expression:=$geometry
      )
    )
    ```
    
    **Method 2: Using disjoint() predicate**
    ```sql
    -- Areas completely outside all coverage zones
    disjoint(
      $geometry,
      aggregate('fire_coverage_5km', 'collect', $geometry)
    )
    ```
  </TabItem>
  
  <TabItem value="postgresql" label="PostgreSQL (Advanced)">
    ```sql
    -- Residential areas with NO nearby fire stations
    NOT EXISTS (
      SELECT 1
      FROM fire_stations fs
      WHERE ST_DWithin(
        residential_areas.geom,
        fs.geom,
        5000  -- 5km threshold
      )
    )
    ```
    
    **Or using spatial join**:
    ```sql
    SELECT r.*
    FROM residential_areas r
    LEFT JOIN fire_stations fs
      ON ST_DWithin(r.geom, fs.geom, 5000)
    WHERE fs.station_id IS NULL  -- No matching station found
    ```
  </TabItem>
</Tabs>

4. Click **Apply Filter**
5. Review map - red/highlighted areas show coverage gaps

### Step 4: Calculate Exact Distance to Nearest Station

Add a field showing how far each under-served area is from nearest fire station:

1. Open **Attribute Table** (F6) of filtered layer
2. **Open Field Calculator**
3. Create new field:
   ```
   Field name: distance_to_nearest_station
   Type: Decimal (double)
   Precision: 2
   
   Expression:
   array_min(
     array_foreach(
       overlay_nearest('fire_stations', $geometry, limit:=5),
       distance(geometry(@element), $geometry)
     )
   ) / 1000  -- Convert meters to kilometers
   ```

**Result**: Each residential area now shows distance to closest fire station

### Step 5: Prioritize by Population at Risk

If your residential layer has population data:

1. **Calculate total population** in under-served areas:
   ```sql
   -- In expression filter or field calculator
   "population" > 0
   ```

2. **Sort by priority**:
   ```
   Attribute Table → Click column header "population"
   → Sort descending
   ```

3. **Create priority categories**:
   ```sql
   CASE
     WHEN "distance_to_nearest_station" > 10 THEN 'Critical (>10km)'
     WHEN "distance_to_nearest_station" > 7 THEN 'High Priority (7-10km)'
     WHEN "distance_to_nearest_station" > 5 THEN 'Medium Priority (5-7km)'
     ELSE 'Acceptable (<5km)'
   END
   ```

### Step 6: Visualize Coverage Gaps

**Symbology Setup**:

1. Right-click **residential_areas** → Symbology
2. Choose **Graduated**
3. Value: `distance_to_nearest_station`
4. Method: Natural Breaks (Jenks)
5. Classes: 5
6. Color ramp: Red (far) → Yellow → Green (close)
7. Apply

**Add Labels** (optional):
```
Label with: concat("name", ' - ', round("distance_to_nearest_station", 1), ' km')
Size: Based on "population" (larger = more people affected)
```

### Step 7: Export Results and Generate Report

1. **Export under-served areas**:
   ```
   FilterMate → Export Filtered Features
   Format: GeoPackage
   Filename: residential_areas_underserved.gpkg
   CRS: WGS84 (for sharing) or keep project CRS
   ```

2. **Generate summary statistics**:
   ```
   Vector → Analysis Tools → Basic Statistics
   Input: residential_areas_underserved
   Field: population
   ```

3. **Create summary report** (Python Console - optional):
   ```python
   layer = iface.activeLayer()
   features = list(layer.getFeatures())
   
   total_areas = len(features)
   total_population = sum(f['population'] for f in features if f['population'])
   avg_distance = sum(f['distance_to_nearest_station'] for f in features) / total_areas
   max_distance = max(f['distance_to_nearest_station'] for f in features)
   
   print(f"=== Emergency Services Coverage Gap Analysis ===")
   print(f"Under-served residential areas: {total_areas}")
   print(f"Population affected: {total_population:,}")
   print(f"Average distance to nearest station: {avg_distance:.1f} km")
   print(f"Maximum distance: {max_distance:.1f} km")
   ```

---

## Understanding the Results

### What the Filter Shows

✅ **Selected areas**: Residential zones >5km from ANY fire station

❌ **Excluded areas**: Residential zones within 5km service radius

### Interpreting Coverage Gaps

**Critical Gaps (>10km)**:
- Response time likely exceeds national standards (e.g., NFPA 1710: 8 minutes)
- High priority for new station placement
- Consider temporary or volunteer stations
- May need mutual aid agreements with neighboring jurisdictions

**High Priority (7-10km)**:
- Response time borderline acceptable
- Should be addressed in next planning cycle
- Consider mobile/seasonal stations
- Evaluate road network quality (may be longer drive time)

**Medium Priority (5-7km)**:
- Technically under-served by strict standards
- Low urgency if population density is low
- Monitor for future growth
- May be acceptable for rural areas

### Validation Checks

1. **Visual spot check**: Use QGIS Measure tool to verify distances
2. **Edge cases**: Areas just outside 5km may round differently
3. **Population accuracy**: Verify sum matches known census totals
4. **Geometry validity**: Check for slivers or invalid polygons

---

## Best Practices

### Coverage Standards

**NFPA 1710 (USA) Recommendations**:
- Urban areas: 1.5 mile (2.4 km) travel distance
- Rural areas: Up to 5 miles (8 km) acceptable
- Response time goal: 8 minutes from call to arrival

**Adjust threshold** based on your region:
```
Urban areas:    2-3 km
Suburban areas: 5 km (as in this tutorial)
Rural areas:    8-10 km
```

### Performance Optimization

**For large datasets**:

1. **Simplify residential area geometry**:
   ```
   Vector → Geometry → Simplify
   Tolerance: 50 meters (maintains coverage accuracy)
   ```

2. **Pre-filter to populated areas only**:
   ```sql
   "population" > 0 OR "landuse" = 'residential'
   ```

3. **Use spatial index** (OGR creates automatically for GeoPackage)

4. **Backend selection guide**:
   ```
   < 1,000 areas:    OGR (sufficient)
   1k - 50k:         Spatialite
   > 50k:            PostgreSQL
   ```

### Real-World Adjustments

**Consider road network reality**:
- Straight-line 5km may be 8km by road
- Mountains/rivers may block direct access
- Use network analysis for drive-time instead (advanced)

**Network Analysis Alternative** (QGIS built-in):
```
Processing → Network Analysis → Service Area (from layer)
Input: fire_stations
Travel cost: 5000 meters OR 10 minutes
Creates drive-time polygons instead of circles
```

### Data Quality Considerations

1. **Fire station accuracy**:
   - Verify stations are operational (not decommissioned)
   - Check if volunteer stations should have smaller radius
   - Consider specialized stations (airport, industrial)

2. **Residential area quality**:
   - Remove parks, industrial zones misclassified as residential
   - Update with recent census data
   - Account for new developments

3. **CRS importance**:
   - Distance calculations require projected CRS
   - Geographic (lat/lon) will give incorrect results
   - Always reproject if needed before analysis

---

## Common Issues

### Issue 1: All residential areas selected (or none selected)

**Cause**: CRS mismatch or buffer not created properly

**Solution**:
```
1. Check fire_coverage_5km layer exists and has features
2. Verify both layers in same CRS
3. Re-create buffers with correct distance unit (meters)
4. Check buffer layer name matches expression exactly
```

### Issue 2: Distance calculation returns NULL or errors

**Cause**: overlay_nearest() not finding fire stations layer

**Solution**:
```
1. Ensure fire_stations layer is loaded in project
2. Check layer name matches exactly (case-sensitive)
3. Alternative: Use aggregate() with minimum distance:

distance(
  $geometry,
  aggregate('fire_stations', 'collect', $geometry)
)
```

### Issue 3: Results show unexpected patterns

**Cause**: Data quality issues or projection problems

**Troubleshooting**:
```
1. Zoom to specific result and measure distance manually
2. Check for overlapping residential polygons
3. Verify fire_stations actually cover the area
4. Look for invalid geometries:
   Vector → Geometry Tools → Check Validity
```

### Issue 4: Performance very slow

**Cause**: Large geometries or complex residential areas

**Solutions**:
```
1. Simplify residential geometry (50-100m tolerance)
2. Create spatial index on both layers
3. Process by administrative districts separately
4. Use PostgreSQL backend for >10k features
```

---

## Next Steps

### Related Workflows

- **[Urban Planning Transit](./urban-planning-transit)**: Similar buffer analysis pattern
- **[Environmental Protection](./environmental-protection)**: Inverse spatial queries
- **[Real Estate Analysis](./real-estate-analysis)**: Multi-criteria filtering

### Advanced Techniques

**1. Multi-Station Coverage** (areas served by ≥2 stations):
```sql
-- Count overlapping coverage zones
array_length(
  overlay_intersects('fire_coverage_5km', $geometry)
) >= 2
```

**2. Priority Scoring** (distance + population):
```sql
-- Higher score = higher priority for new station
("distance_to_nearest_station" - 5) * "population" / 1000
```

**3. Optimal New Station Location**:
```
1. Export under-served areas with population
2. Find centroid weighted by population:
   Processing → Vector Geometry → Centroids
3. Manual analysis: Place new station at highest-priority centroid
```

**4. Response Time Modeling** (advanced):
```python
# Requires road network and routing
# Uses QGIS Network Analysis tools
# Models actual drive time vs. straight-line distance
# Accounts for road speed limits and turn restrictions
```

**5. Temporal Analysis** (future growth):
```sql
-- If you have population projection data
("population_2030" - "population_2024") / "population_2024" > 0.2
-- Areas expecting >20% growth
```

### Further Learning

- 📖 [Spatial Predicates Reference](../reference/cheat-sheets/spatial-predicates)
- 📖 [Buffer Operations](../user-guide/buffer-operations)
- 📖 [Network Analysis in QGIS](https://docs.qgis.org/latest/en/docs/user_manual/processing_algs/qgis/networkanalysis.html)
- 📖 [Performance Tuning](../advanced/performance-tuning)

---

## Summary

✅ **You've learned**:
- Creating service area buffers around facilities
- Inverse spatial filtering (NOT intersects)
- Distance calculations to nearest feature
- Population-weighted priority analysis
- Exporting results for planning reports

✅ **Key techniques**:
- `NOT intersects()` for coverage gap analysis
- `overlay_nearest()` for distance calculations
- `aggregate()` with spatial predicates
- Priority scoring with attribute + spatial data

🎯 **Real-world impact**: This workflow helps emergency management agencies identify service gaps, optimize resource allocation, improve response times, and ensure equitable emergency service coverage across communities.

💡 **Pro tip**: Run this analysis annually with updated census data to track coverage changes as populations shift and adjust station placement accordingly.
