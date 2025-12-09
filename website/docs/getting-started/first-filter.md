---
sidebar_position: 3
---

# Your First Filter

This tutorial walks you through creating your first filter with FilterMate, from start to finish.

## Scenario

**Goal**: Find all buildings within 200 meters of a main road.

**Data Required**:
- A **buildings** layer (polygons)
- A **roads** layer (lines)

## Step-by-Step Tutorial

### 1. Load Your Data

First, load both layers into QGIS:

1. Open QGIS
2. Load the **buildings** layer (the layer we'll filter)
3. Load the **roads** layer (the reference layer)

:::info Sample Data
If you don't have sample data, you can use OpenStreetMap data:
- Download from [Geofabrik](https://download.geofabrik.de/)
- Or use QGIS **QuickOSM** plugin to fetch data
:::

### 2. Open FilterMate

1. Click the **FilterMate** icon in the toolbar
2. Or go to **Plugins** → **FilterMate**
3. The dockable panel appears on the right side

<!-- ![First Filter Setup](/img/first-filter-1.png -->
*FilterMate panel ready for your first geometric filter*

### 3. Select the Target Layer

1. In the **Layer Selection** dropdown at the top
2. Select **buildings** (the layer we want to filter)

FilterMate will analyze the layer and display:
- Backend being used (PostgreSQL, Spatialite, or OGR)
- Feature count
- Available fields

### 4. Set Up Geometric Filter

Now we'll create a spatial filter to find buildings near roads:

1. **Go to the Geometric Filter tab**
   - Click the **Geometric Filter** tab in the panel

2. **Select Reference Layer**
   - Choose **roads** from the reference layer dropdown

3. **Choose Spatial Predicate**
   - Select **"within distance"** or **"intersects"** (if using buffer)

4. **Set Buffer Distance**
   - Enter **200** in the buffer distance field
   - Units: **meters** (or your layer's CRS units)

:::tip CRS Reprojection
FilterMate automatically reprojects layers if they have different CRS. No manual reprojection needed!
:::

### 5. Apply the Filter

1. Click **Apply Filter** button
2. FilterMate will:
   - Create a temporary filtered view
   - Highlight matching features on the map
   - Update the feature count in the panel

**What happens behind the scenes:**

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

<Tabs>
  <TabItem value="postgresql" label="PostgreSQL Backend" default>
    ```sql
    -- Creates a materialized view with spatial index
    CREATE MATERIALIZED VIEW temp_filter AS
    SELECT b.*
    FROM buildings b
    JOIN roads r ON ST_DWithin(b.geom, r.geom, 200);
    
    CREATE INDEX idx_temp_geom ON temp_filter USING GIST(geom);
    ```
    ⚡ **Ultra-fast** (sub-second on 100k+ features)
  </TabItem>
  <TabItem value="spatialite" label="Spatialite Backend">
    ```sql
    -- Creates temporary table with R-tree index
    CREATE TEMP TABLE filtered_buildings AS
    SELECT b.*
    FROM buildings b
    JOIN roads r ON ST_Distance(b.geom, r.geom) <= 200;
    
    -- Uses R-tree spatial index
    SELECT CreateSpatialIndex('filtered_buildings', 'geom');
    ```
    ✅ **Fast** (~2-10s on 50k features)
  </TabItem>
  <TabItem value="ogr" label="OGR Backend">
    ```python
    # Uses QGIS processing framework
    processing.run("native:buffer", {
        'INPUT': roads,
        'DISTANCE': 200,
        'OUTPUT': 'memory:'
    })
    
    processing.run("native:selectbylocation", {
        'INPUT': buildings,
        'INTERSECT': buffered_roads,
        'METHOD': 0
    })
    ```
    ⚠️ **Slower** (~10-30s on 50k features)
  </TabItem>
</Tabs>

### 6. Review Results

After filtering:

- **Map Canvas**: Filtered buildings are highlighted
- **Panel**: Shows count of filtered features
- **Attribute Table**: Open to see filtered features

:::tip Zoom to Results
Right-click the layer → **Zoom to Layer** to see all filtered features
:::

### 7. Refine the Filter (Optional)

Want to add attribute criteria? Combine with an attribute filter:

1. Go to **Attribute Filter** tab
2. Add an expression like:
   ```
   "building_type" = 'residential'
   ```
3. Click **Apply Filter**

Now you have buildings that are:
- ✅ Within 200m of roads
- ✅ AND are residential buildings

### 8. Export Results (Optional)

To save the filtered buildings:

1. Go to **Export** tab
2. Choose output format:
   - **GeoPackage** (recommended for modern workflows)
   - **Shapefile** (for compatibility)
   - **PostGIS** (to save to database)
3. Configure options:
   - Output CRS (default: same as source)
   - Output location
4. Click **Export**

## What You Learned

✅ How to open FilterMate and select a layer  
✅ How to create a geometric filter with buffer  
✅ Understanding backend selection (automatic)  
✅ How to combine attribute and geometric filters  
✅ How to export filtered results  

## Next Steps

Now that you've created your first filter, explore more:

- **[Filtering Basics](../user-guide/filtering-basics.md)** - Learn QGIS expressions
- **[Geometric Filtering](../user-guide/geometric-filtering.md)** - Advanced spatial predicates
- **[Buffer Operations](../user-guide/buffer-operations.md)** - Different buffer types
- **[Export Features](../user-guide/export-features.md)** - Advanced export options

## Common Issues

### No features returned?

Check:
- ✅ Buffer distance is appropriate for your CRS (meters vs. degrees)
- ✅ Layers have overlapping extents
- ✅ Reference layer has features

### Filter is slow?

For large datasets:
- Install PostgreSQL backend for 10-50× speedup
- See [Performance Tuning](../advanced/performance-tuning.md)

### Wrong CRS?

FilterMate reprojects automatically, but you can check:
1. Layer properties → CRS tab
2. Ensure both layers have valid CRS defined
3. FilterMate handles the rest!
