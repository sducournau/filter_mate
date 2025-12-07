---
sidebar_position: 2
---

# Quick Start

Get started with FilterMate in 5 minutes! This guide covers the essential workflow.

## Step 1: Open FilterMate

1. In QGIS, load a vector layer (any format: Shapefile, GeoPackage, PostGIS, etc.)
2. Click the **FilterMate** icon in the toolbar, or go to **Plugins** → **FilterMate**
3. The FilterMate dockable panel will appear

:::tip First Time?
FilterMate will automatically detect your layer type and select the optimal backend (PostgreSQL, Spatialite, or OGR).
:::

## Step 2: Select Your Layer

1. From the **Layer Selection** dropdown at the top of the panel
2. Choose the layer you want to filter
3. FilterMate will load layer-specific settings and display relevant fields

## Step 3: Create a Filter

### Option A: Attribute Filter

For filtering by attributes (e.g., population > 10,000):

1. Go to the **Attribute Filter** tab
2. Enter a QGIS expression like:
   ```
   "population" > 10000
   ```
3. Click **Apply Filter**

### Option B: Geometric Filter

For spatial filtering (e.g., buildings within 100m of a road):

1. Go to the **Geometric Filter** tab
2. Select a **reference layer** (e.g., roads)
3. Choose a **spatial predicate** (e.g., "within distance")
4. Set a **buffer distance** (e.g., 100 meters)
5. Click **Apply Filter**

:::info Backend Selection
FilterMate automatically uses the best backend for your data:
- **PostgreSQL**: For PostGIS layers (fastest, requires psycopg2)
- **Spatialite**: For Spatialite databases
- **OGR**: For Shapefiles, GeoPackage, etc.
:::

## Step 4: Review Results

After applying the filter:

- Filtered features are **highlighted** in the map
- The **feature count** updates in the panel
- Use the **History** tab to undo/redo filters

## Step 5: Export (Optional)

To export filtered features:

1. Go to the **Export** tab
2. Choose **export format** (GeoPackage, Shapefile, PostGIS, etc.)
3. Configure **CRS** and other options
4. Click **Export**

## Common Workflows

### Filter by Multiple Criteria

Combine attribute and geometric filters:

```python
# Attribute filter
"population" > 10000 AND "type" = 'residential'

# Then apply geometric filter
# within 500m of city center
```

### Undo/Redo Filters

1. Go to **History** tab
2. Click **Undo** to revert the last filter
3. Click **Redo** to reapply

### Save Filter Settings

FilterMate automatically saves settings per layer:
- Filter expressions
- Buffer distances
- Export preferences

## Performance Tips

### For Large Datasets (>50,000 features)

:::tip Use PostgreSQL
Install psycopg2 and use PostGIS layers for **10-50× faster filtering**:
```bash
pip install psycopg2-binary
```
:::

### For Medium Datasets (10,000-50,000 features)

- Spatialite backend works well
- No additional installation needed

### For Small Datasets (Less than 10,000 features)

- Any backend will work fine
- OGR backend is sufficient

## Next Steps

- **[First Filter Tutorial](./first-filter.md)** - Detailed step-by-step example
- **[Filtering Basics](../user-guide/filtering-basics.md)** - Learn about expressions and predicates
- **[Geometric Filtering](../user-guide/geometric-filtering.md)** - Advanced spatial operations
- **[Backend Comparison](../backends/performance-comparison.md)** - Understand backend performance

## Troubleshooting

### Filter not applying?

Check:
- ✅ Expression syntax is correct (use QGIS expression builder)
- ✅ Field names are quoted correctly: `"field_name"`
- ✅ Layer has features matching the criteria

### Performance slow?

- For large datasets, consider [installing PostgreSQL backend](../installation.md#optional-postgresql-backend-recommended-for-large-datasets)
- Check [Performance Tuning](../advanced/performance-tuning.md) guide

### Backend not detected?

FilterMate will show which backend is being used. If PostgreSQL is not available:
1. Check if psycopg2 is installed: `import psycopg2`
2. Verify layer source is PostgreSQL/PostGIS
3. See [Installation Troubleshooting](../installation.md#troubleshooting)
