---
sidebar_position: 3
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Environmental Analysis: Protected Zone Impact

Find industrial sites within protected water buffer zones to assess environmental compliance and risks.

## Scenario Overview

**Goal**: Identify industrial facilities that fall within 1km buffer zones around protected water bodies to evaluate environmental impact.

**Real-World Application**:
- Environmental agencies monitoring compliance
- NGOs assessing industrial pollution risks
- Policy makers creating buffer zone regulations
- Urban planners managing industrial zoning

**Estimated Time**: 15 minutes

**Difficulty**: ⭐⭐⭐ Advanced

---

## Prerequisites

### Required Data

1. **Industrial Sites Layer** (points or polygons)
   - Industrial facility locations
   - Must include facility type/classification
   - Minimum 50+ sites for meaningful analysis

2. **Water Bodies Layer** (polygons)
   - Rivers, lakes, wetlands, reservoirs
   - Protected status attribute (optional but useful)
   - Covers your study area

3. **Protected Zones** (optional)
   - Existing environmental protection zones
   - Regulatory buffer boundaries

### Sample Data Sources

**Option 1: OpenStreetMap**
```python
# Use QGIS QuickOSM plugin
# For water bodies:
Key: "natural", Value: "water"
Key: "waterway", Value: "river"

# For industrial sites:
Key: "landuse", Value: "industrial"
Key: "industrial", Value: "*"
```

**Option 2: Government Data**
- Environmental Protection Agency (EPA) databases
- National water quality databases
- Industrial facility registries
- Protected area boundaries (WDPA)

### Backend Recommendation

**Spatialite** - Best choice for this workflow:
- Good performance for regional datasets (typically &lt;100k features)
- Robust buffer operations
- Good geometry repair capabilities
- No server setup required

---

## Step-by-Step Instructions

### Step 1: Load and Inspect Data

1. **Load both layers** into QGIS:
   - `water_bodies.gpkg` or `rivers_lakes.shp`
   - `industrial_sites.gpkg` or `factories.shp`

2. **Check CRS compatibility**:
   ```
   Right-click layer → Properties → Information
   Verify both use same projected CRS (e.g., UTM, State Plane)
   ```

3. **Verify geometry validity**:
   ```
   Vector → Geometry Tools → Check Validity
   Run on both layers
   ```

:::warning CRS Requirements
Buffer operations require a **projected coordinate system** (meters/feet), not geographic (lat/lon). If your data is in EPSG:4326, reproject first:

```
Vector → Data Management Tools → Reproject Layer
Target CRS: Choose appropriate UTM zone or local projection
```
:::

### Step 2: Create 1km Buffer Around Water Bodies

**Option A: Using FilterMate (Recommended)**

1. Open FilterMate panel
2. Select **water_bodies** layer
3. Enter filter expression:
   ```sql
   -- Keep all water bodies, prepare for buffer
   1 = 1
   ```
4. Enable **Geometry Modification** → **Buffer**
5. Set **Buffer Distance**: `1000` (meters)
6. **Buffer Type**: `Positive (expand)`
7. Click **Apply Filter**
8. **Export Result** as `water_buffers_1km.gpkg`

**Option B: Using QGIS Native Tools**

```
Vector → Geoprocessing Tools → Buffer
Distance: 1000 meters
Segments: 16 (smooth curves)
Save as: water_buffers_1km.gpkg
```

### Step 3: Filter Industrial Sites Within Buffer Zones

Now the main FilterMate operation:

1. **Select industrial_sites layer** in FilterMate
2. **Choose Backend**: Spatialite (or PostgreSQL if available)
3. Enter **spatial filter expression**:

<Tabs>
  <TabItem value="spatialite" label="Spatialite / OGR" default>
    ```sql
    -- Industrial sites intersecting 1km water buffers
    intersects(
      $geometry,
      geometry(get_feature('water_buffers_1km', 'fid', fid))
    )
    ```
    
    **Alternative using layer reference**:
    ```sql
    -- More efficient if buffer layer is already loaded
    intersects(
      $geometry,
      aggregate(
        layer:='water_buffers_1km',
        aggregate:='collect',
        expression:=$geometry
      )
    )
    ```
  </TabItem>
  
  <TabItem value="postgresql" label="PostgreSQL (Advanced)">
    ```sql
    -- More efficient PostGIS approach with direct buffer
    ST_DWithin(
      sites.geom,
      water.geom,
      1000  -- 1km buffer applied on-the-fly
    )
    WHERE water.protected_status = true
    ```
    
    **Full materialized view approach**:
    ```sql
    -- Creates optimized temporary table
    CREATE MATERIALIZED VIEW industrial_risk AS
    SELECT 
      s.*,
      w.name AS nearest_water_body,
      ST_Distance(s.geom, w.geom) AS distance_meters
    FROM industrial_sites s
    JOIN water_bodies w ON ST_DWithin(s.geom, w.geom, 1000)
    ORDER BY distance_meters;
    ```
  </TabItem>
</Tabs>

4. Click **Apply Filter**
5. Review results in map canvas (features should be highlighted)

### Step 4: Add Distance Calculations (Optional)

To see **how far** each industrial site is from protected zones:

1. Open **Field Calculator** (F6)
2. Create new field:
   ```
   Field name: distance_to_water
   Field type: Decimal (double)
   
   Expression:
   distance(
     $geometry,
     aggregate(
       'water_buffers_1km',
       'collect',
       $geometry
     )
   )
   ```
3. Features inside buffer will show `0` or small values

### Step 5: Categorize by Risk Level

Create visual categories based on proximity:

1. **Right-click filtered layer** → Properties → Symbology
2. Choose **Categorized**
3. Use expression:
   ```python
   CASE
     WHEN "distance_to_water" = 0 THEN 'High Risk (Inside Buffer)'
     WHEN "distance_to_water" <= 500 THEN 'Medium Risk (0-500m)'
     WHEN "distance_to_water" <= 1000 THEN 'Low Risk (500-1000m)'
     ELSE 'No Risk (Outside Buffer)'
   END
   ```
4. Apply color scheme (red → yellow → green)

### Step 6: Export Results

1. In FilterMate, **Export Filtered Features**:
   ```
   Format: GeoPackage
   Filename: industrial_sites_environmental_risk.gpkg
   Include attributes: ✓ All fields
   CRS: Keep original or choose standard (e.g., WGS84 for sharing)
   ```

2. **Generate report** (optional):
   ```python
   # In Python Console (optional advanced step)
   layer = iface.activeLayer()
   total = layer.featureCount()
   high_risk = sum(1 for f in layer.getFeatures() if f['distance_to_water'] == 0)
   
   print(f"Total industrial sites in buffer: {total}")
   print(f"High risk (directly in water buffer): {high_risk}")
   print(f"Percentage at risk: {(high_risk/total)*100:.1f}%")
   ```

---

## Understanding the Results

### What the Filter Shows

✅ **Selected features**: Industrial sites within 1km of protected water bodies

❌ **Excluded features**: Industrial sites farther than 1km from any water body

### Interpreting the Analysis

**High Risk Sites** (distance = 0):
- Directly within regulated buffer zones
- May violate environmental regulations
- Require immediate compliance review
- Potential for water contamination

**Medium Risk Sites** (0-500m):
- Close to buffer boundaries
- Should be monitored
- May need additional safeguards
- Future buffer expansions could affect them

**Low Risk Sites** (500-1000m):
- Within analytical buffer but outside typical regulation
- Useful for proactive planning
- Lower immediate concern

### Quality Checks

1. **Visual inspection**: Zoom to several results and verify they're actually near water
2. **Attribute check**: Ensure facility types match expectations
3. **Distance validation**: Measure distance in QGIS to confirm buffer accuracy
4. **Geometry issues**: Look for sites on buffer boundary (may indicate geometry problems)

---

## Best Practices

### Performance Optimization

**For Large Datasets (>10,000 industrial sites)**:

1. **Simplify water body geometry** first:
   ```
   Vector → Geometry Tools → Simplify
   Tolerance: 10 meters (maintains accuracy)
   ```

2. **Use spatial index** (automatic in PostgreSQL, manual in Spatialite):
   ```
   Layer → Properties → Create Spatial Index
   ```

3. **Pre-filter water bodies** to protected areas only:
   ```sql
   "protected_status" = 'yes' OR "designation" IS NOT NULL
   ```

**Backend Selection**:
```
Features    | Recommended Backend
--------    | -------------------
< 1,000     | OGR (simplest)
1k - 50k    | Spatialite (good balance)
> 50k       | PostgreSQL (fastest)
```

### Accuracy Considerations

1. **Buffer distance units**: Always verify units match your CRS:
   ```
   Meters: UTM, State Plane, Web Mercator
   Feet: Some State Plane zones
   Degrees: NEVER use for buffers (reproject first!)
   ```

2. **Geometry repair**: Water bodies often have invalid geometries:
   ```
   Vector → Geometry Tools → Fix Geometries
   Run before buffer operation
   ```

3. **Topology**: Overlapping water bodies may create unexpected buffer shapes:
   ```
   Vector → Geoprocessing → Dissolve (union all water bodies)
   Then create single unified buffer
   ```

### Regulatory Compliance

- **Document methodology**: Save FilterMate expression history
- **Version control**: Keep original data + filtered results + metadata
- **Validation**: Cross-reference with official regulatory databases
- **Updates**: Re-run analysis when industrial registry is updated

---

## Common Issues

### Issue 1: "No features selected"

**Cause**: CRS mismatch or buffer distance too small

**Solution**:
```
1. Check both layers are in same projected CRS
2. Verify buffer distance: 1000 in meters, not degrees
3. Try larger buffer (e.g., 2000m) for testing
4. Check water bodies actually exist in your study area
```

### Issue 2: "Geometry errors" during buffer

**Cause**: Invalid water body geometries

**Solution**:
```
Vector → Geometry Tools → Fix Geometries
Then re-create buffers
```

### Issue 3: Performance very slow (>2 minutes)

**Cause**: Large datasets without optimization

**Solutions**:
```
1. Create spatial indexes on both layers
2. Simplify water body geometry (10m tolerance)
3. Switch to PostgreSQL backend
4. Pre-filter to smaller area of interest
```

### Issue 4: Buffer creates strange shapes

**Cause**: Geographic CRS (lat/lon) instead of projected

**Solution**:
```
Reproject BOTH layers to appropriate UTM zone:
Vector → Data Management → Reproject Layer
Find correct zone: https://epsg.io/
```

---

## Next Steps

### Related Workflows

- **[Emergency Services Coverage](./emergency-services.md)**: Similar buffer analysis techniques
- **[Urban Planning Transit](./urban-planning-transit.md)**: Multi-layer spatial filtering
- **[Real Estate Analysis](./real-estate-analysis.md)**: Combining spatial + attribute filters

### Advanced Techniques

**1. Multi-Ring Buffers** (graduated risk zones):
```
Create 3 separate buffers: 500m, 1000m, 1500m
Categorize facilities by which buffer they fall into
```

**2. Proximity to Nearest Water** (not just any water):
```sql
-- Find distance to closest water body only
array_min(
  array_foreach(
    overlay_nearest('water_bodies', $geometry),
    distance(@element, $geometry)
  )
)
```

**3. Temporal Analysis** (if you have facility age data):
```sql
-- Old facilities in sensitive areas (highest risk)
"year_built" < 1990 
AND distance_to_water < 500
```

**4. Cumulative Impact** (multiple facilities near same water body):
```sql
-- Count facilities affecting each water body
WITH risk_counts AS (
  SELECT water_id, COUNT(*) as num_facilities
  FROM filtered_sites
  GROUP BY water_id
)
-- Show water bodies with >5 nearby facilities
```

### Further Learning

- 📖 [Spatial Predicates Reference](../reference/cheat-sheets/spatial-predicates.md)
- 📖 [Buffer Operations Guide](../user-guide/buffer-operations.md)
- 📖 [Performance Tuning](../advanced/performance-tuning.md)
- 📖 [Troubleshooting](../advanced/troubleshooting.md)

---

## Summary

✅ **You've learned**:
- Creating buffer zones around water bodies
- Spatial intersection filtering with industrial sites
- Distance calculation and risk categorization
- Geometry validation and repair
- Backend-specific optimization techniques

✅ **Key takeaways**:
- Always use projected CRS for buffer operations
- Fix geometry errors before spatial analysis
- Choose backend based on dataset size
- Document methodology for regulatory compliance
- Visual validation is essential

🎯 **Real-world impact**: This workflow helps environmental agencies identify compliance risks, supports evidence-based policy making, and protects water quality by highlighting facilities requiring monitoring or remediation.
