---
sidebar_position: 2
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Urban Planning: Properties Near Transit

Find all residential parcels within walking distance of subway stations for transit-oriented development analysis.

## Scenario Overview

**Goal**: Identify properties within 500 meters of subway stations to assess transit-oriented development opportunities.

**Real-World Application**:
- Urban planning departments evaluating development zones
- Real estate developers finding transit-accessible properties
- Policy makers assessing transit equity and coverage
- Environmental planners reducing car dependency

**Estimated Time**: 10 minutes

**Difficulty**: ⭐⭐ Intermediate

---

## Prerequisites

### Required Data

1. **Parcels Layer** (polygons)
   - Residential property boundaries
   - Must include land use or zoning attributes
   - Recommended: 1,000+ features for realistic analysis

2. **Transit Stations Layer** (points)
   - Subway/metro station locations
   - Includes station names
   - Covers your study area

### Sample Data Sources

**Option 1: OpenStreetMap (Free)**
```bash
# Use QGIS QuickOSM plugin
1. Vector → QuickOSM → Quick Query
2. Key: "railway", Value: "station"
3. Select your city/region
4. Download points
```

**Option 2: Municipal Open Data**
- Check your city's open data portal
- Look for "parcels", "cadastre", or "property" datasets
- Transit data usually under "transportation"

### System Requirements

- **Recommended Backend**: PostgreSQL (for 50k+ parcels)
- **Alternative**: Spatialite (for `<50k` parcels)
- **CRS**: Any (FilterMate handles reprojection automatically)

---

## Step-by-Step Instructions

### Step 1: Load Your Data

1. Open QGIS and create a new project
2. Load the **parcels** layer (drag & drop or Layer → Add Layer)
3. Load the **transit_stations** layer
4. Verify both layers display correctly on the map

:::tip CRS Check
Different CRS? No problem! FilterMate automatically reprojects layers during spatial operations. You'll see a 🔄 indicator when reprojection occurs.
:::

---

### Step 2: Open FilterMate

1. Click the **FilterMate** icon in the toolbar
2. Or: **Vector** → **FilterMate**
3. The panel docks on the right side

**What you should see**:
- Three tabs: FILTERING / EXPLORING / EXPORTING
- Layer selector at the top
- Empty expression builder

---

### Step 3: Configure the Filter

#### 3.1 Select Target Layer

1. In the **Layer Selection** dropdown (top of panel)
2. Check **parcels** layer
3. Notice the backend indicator (PostgreSQL⚡ / Spatialite / OGR)

**Layer Info Display**:
```
Provider: postgresql (PostgreSQL)
Features: 125,347
CRS: EPSG:2154 (Lambert 93)
Primary Key: gid
```

:::info Backend Performance
If you see "OGR" for large parcel datasets, consider migrating to PostgreSQL for 10-50× faster performance. See [Backend Guide](../backends/choosing-backend.md).
:::

---

#### 3.2 Add Attribute Filter (Optional)

Filter to residential parcels only:

1. In the **Expression Builder** section
2. Click the **Fields** dropdown to see available attributes
3. Enter this expression:

```sql
land_use = 'residential'
-- OR if using zoning codes:
zoning LIKE 'R-%'
-- OR multiple residential types:
land_use IN ('residential', 'mixed-use', 'multi-family')
```

4. Wait for the green checkmark (✓) - indicates valid syntax

**Expression Explanation**:
- `land_use = 'residential'` - Exact match on land use field
- `LIKE 'R-%'` - Pattern matching for residential zoning codes (R-1, R-2, etc.)
- `IN (...)` - Multiple allowed values

:::tip No Residential Field?
If your data doesn't have land use, skip this step. The spatial filter will work on all parcels.
:::

---

#### 3.3 Configure Geometric Filter

Now add the spatial component - proximity to transit:

1. **Scroll down** to the **Geometric Filter** section
2. Click to expand if collapsed

**Reference Layer**:
3. Select **transit_stations** from the dropdown
4. The reference layer icon appears: 🚉

**Spatial Predicate**:
5. Select **"Intersects"** from predicate dropdown
   - (We'll add buffer distance, so intersects = "touches buffer")

**Buffer Distance**:
6. Enter `500` in the distance field
7. Select **meters** as the unit
8. Leave buffer type as **Round (Planar)** for urban areas

**Your Configuration Should Look Like**:
```
Reference Layer: transit_stations
Spatial Predicate: Intersects
Buffer Distance: 500 meters
Buffer Type: Round (Planar)
```

:::tip Geographic CRS Auto-Conversion
If your layers use geographic coordinates (EPSG:4326), FilterMate automatically converts to EPSG:3857 for accurate metric buffers. You'll see: 🌍 indicator in logs.
:::

---

### Step 4: Apply the Filter

1. Click the **Apply Filter** button (big button at bottom)
2. FilterMate executes the spatial query

**What Happens**:

<Tabs>
  <TabItem value="postgresql" label="PostgreSQL Backend" default>
    ```sql
    -- Creates optimized materialized view
    CREATE MATERIALIZED VIEW temp_filter AS
    SELECT p.*
    FROM parcels p
    WHERE p.land_use = 'residential'
      AND EXISTS (
        SELECT 1 FROM transit_stations s
        WHERE ST_DWithin(
          p.geom::geography,
          s.geom::geography,
          500
        )
      );
    
    CREATE INDEX idx_temp_geom 
      ON temp_filter USING GIST(geom);
    ```
    ⚡ **Performance**: 0.3-2 seconds for 100k+ parcels
  </TabItem>
  
  <TabItem value="spatialite" label="Spatialite Backend">
    ```sql
    -- Creates temporary table with spatial index
    CREATE TEMP TABLE temp_filter AS
    SELECT p.*
    FROM parcels p
    WHERE p.land_use = 'residential'
      AND EXISTS (
        SELECT 1 FROM transit_stations s
        WHERE ST_Distance(p.geom, s.geom) <= 500
      );
    
    SELECT CreateSpatialIndex('temp_filter', 'geom');
    ```
    ⏱️ **Performance**: 5-15 seconds for 50k parcels
  </TabItem>
  
  <TabItem value="ogr" label="OGR Backend">
    Uses QGIS Processing framework with memory layers.
    
    🐌 **Performance**: 30-120 seconds for large datasets
    
    **Recommendation**: Migrate to PostgreSQL for this workflow.
  </TabItem>
</Tabs>

---

### Step 5: Review Results

**Map View**:
- Filtered parcels are highlighted on the map
- Non-matching parcels are hidden (or greyed out)
- Count displayed in FilterMate panel: `Found: 3,247 features`

**Verify Results**:
1. Zoom to a transit station
2. Select one filtered parcel
3. Use **Measure Tool** to verify it's within 500m of station

**Expected Results**:
- Urban cores: High density of filtered parcels
- Suburban areas: Sparse parcels near stations
- Rural areas: Very few or no results

---

### Step 6: Analyze & Export

#### Option A: Quick Statistics

1. Right-click filtered layer
2. **Properties** → **Information**
3. View feature count and extent

#### Option B: Export for Reporting

1. Switch to **EXPORTING** tab in FilterMate
2. Select filtered parcels layer
3. Choose output format:
   - **GeoPackage (.gpkg)** - Best for QGIS
   - **GeoJSON** - For web mapping
   - **Shapefile** - For legacy systems
   - **PostGIS** - Back to database

4. **Optional**: Transform CRS (e.g., WGS84 for web)
5. Click **Export**

**Export Settings Example**:
```
Layer: parcels (filtered)
Format: GeoPackage
Output CRS: EPSG:4326 (WGS84)
Filename: transit_accessible_parcels.gpkg
```

---

## Understanding the Results

### Interpreting Feature Counts

**Example Results**:
```
Total parcels: 125,347
Residential parcels: 87,420 (70%)
Transit-accessible residential: 3,247 (3.7% of residential)
```

**What This Means**:
- Only 3.7% of residential parcels are transit-accessible
- Opportunity for transit-oriented development
- Most residents depend on cars (equity concern)

### Spatial Patterns

**Look for**:
- **Clusters** around major transit hubs → High-density zones
- **Gaps** between stations → Potential infill development
- **Isolated parcels** → Transit deserts requiring service expansion

---

## Best Practices

### Performance Optimization

✅ **Use PostgreSQL** for parcel datasets >50k` features
- 10-50× faster than OGR backend
- Sub-second query times even on 500k+ parcels

✅ **Filter by attribute first** if possible
- `land_use = 'residential'` reduces spatial query scope
- 30-50% performance improvement

✅ **Buffer Distance Units**
- Use **meters** for urban analysis (consistent worldwide)
- Avoid **degrees** for distance-based queries (inaccurate)

### Accuracy Considerations

⚠️ **Buffer Type Selection**:
- **Round (Planar)**: Fast, accurate for small areas (`<10km`)
- **Round (Geodesic)**: More accurate for large regions
- **Square**: Computational optimization (rarely needed)

⚠️ **CRS Choice**:
- Local projected CRS (e.g., State Plane, UTM) - Best accuracy
- Web Mercator (EPSG:3857) - Good for worldwide analysis
- WGS84 (EPSG:4326) - Auto-converted by FilterMate ✓

### Data Quality

🔍 **Check for**:
- **Overlapping parcels** - Can inflate counts
- **Missing geometries** - Use "Check Geometries" tool
- **Outdated transit data** - Verify station operational status

---

## Common Issues & Solutions

### Issue 1: No Results Found

**Symptoms**: Filter returns 0 features, but you expect matches.

**Possible Causes**:
1. ❌ Buffer distance too small (try 1000m)
2. ❌ Wrong attribute value (check `land_use` field values)
3. ❌ Layers don't overlap geographically
4. ❌ CRS mismatch (though FilterMate handles this)

**Debug Steps**:
```sql
-- Test 1: Remove attribute filter
-- Just run spatial query on all parcels

-- Test 2: Increase buffer distance
-- Try 1000 or 2000 meters

-- Test 3: Reverse query
-- Filter stations within parcels (should always return results)
```

---

### Issue 2: Slow Performance (>30` seconds)

**Cause**: Large dataset with OGR backend.

**Solutions**:
1. ✅ Install PostgreSQL + PostGIS
2. ✅ Load data into PostgreSQL database
3. ✅ Use PostgreSQL layer in QGIS
4. ✅ Re-run filter (expect 10-50× speedup)

**Quick PostgreSQL Setup**:
```bash
# Install psycopg2 for QGIS Python
pip install psycopg2-binary

# Or in OSGeo4W Shell (Windows):
py3_env
pip install psycopg2-binary
```

---

### Issue 3: Results Look Wrong

**Symptoms**: Parcels far from stations are included.

**Possible Causes**:
1. ❌ Buffer distance in wrong units (degrees instead of meters)
2. ❌ "Contains" predicate instead of "Intersects"
3. ❌ Reference layer is wrong (roads instead of stations)

**Verification**:
1. Use QGIS **Measure Tool**
2. Measure distance from filtered parcel to nearest station
3. Should be ≤ 500 meters

---

## Next Steps

### Related Workflows

- **[Emergency Services Coverage](emergency-services.md)** - Similar distance analysis
- **[Environmental Protection Zones](environmental-protection.md)** - Multi-criteria filtering
- **[Real Estate Analysis](real-estate-analysis.md)** - Combined attribute filtering

### Advanced Techniques

**Graduated Buffers**:
Run multiple filters with different distances (250m, 500m, 1000m) to create walkability zones.

**Combine with Demographics**:
Join census data to estimate transit-accessible population.

**Time-Based Analysis**:
Use historical data to track transit-oriented development over time.

---

## Summary

**You've Learned**:
- ✅ Combined attribute and geometric filtering
- ✅ Buffer operations with distance parameters
- ✅ Spatial predicate selection (Intersects)
- ✅ Backend performance optimization
- ✅ Result export and CRS transformation

**Key Takeaways**:
- FilterMate handles CRS reprojection automatically
- PostgreSQL backend provides best performance for large datasets
- 500m is typical "walking distance" for urban planning
- Always verify results with manual measurement sampling

**Time Saved**:
- Manual selection: ~2 hours
- Processing Toolbox (multi-step): ~20 minutes
- FilterMate workflow: ~10 minutes ⚡

---

Need help? Check the [Troubleshooting Guide](../advanced/troubleshooting.md) or ask on [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions).
