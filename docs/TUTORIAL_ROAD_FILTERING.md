# FilterMate Tutorial: Filtering Roads and Surrounding Features

## Introduction

This tutorial demonstrates how to use **FilterMate**, a powerful QGIS plugin, to filter road networks by importance level and automatically filter surrounding geographic features (buildings, vegetation, water surfaces, railways, etc.) using spatial intersection with a buffer zone.

![FilterMate Interface](../icons/sketchy_logo.png)

## Use Case

You're working with a comprehensive geographic dataset (like IGN TOPO data) and need to:

1. **Filter roads** to show only major routes (importance levels 1, 2, and 3)
2. **Create a 50-meter buffer** around these important roads
3. **Automatically filter** all related layers (buildings, vegetation, water bodies, railways) to show only features within this buffer zone

This is particularly useful for:

- Urban planning projects
- Infrastructure analysis
- Map production focused on major transport corridors
- Environmental impact studies along major routes

---

## Prerequisites

- **QGIS 3.x** installed
- **FilterMate plugin** installed and activated
- Geographic data loaded (vector layers for roads, buildings, vegetation, etc.)

---

## Step-by-Step Tutorial

### Step 1: Load Your Data

Load your vector layers into QGIS. For this tutorial, we'll use typical topographic layers:

| Layer Name               | Description          | Geometry Type |
| ------------------------ | -------------------- | ------------- |
| `troncon_de_route`       | Road segments        | LineString    |
| `batiment`               | Buildings            | Polygon       |
| `zone_de_vegetation`     | Vegetation areas     | Polygon       |
| `surface_hydrographique` | Water surfaces       | Polygon       |
| `troncon_de_voie_ferree` | Railway segments     | LineString    |
| `commune`                | Municipal boundaries | Polygon       |

### Step 2: Open FilterMate

1. Open the FilterMate panel via **View → Panels → FilterMate** or click the FilterMate icon in the toolbar
2. The FilterMate dock widget will appear on the right side of your QGIS window

### Step 3: Configure Custom Selection Filter

In the **SÉLECTION** (Selection) section:

1. Check **"SÉLECTION PERSONNALISÉE"** (Custom Selection)
2. In the expression field, enter the filter for road importance:

```sql
"importance" IN ('1', '2', '3')
```

This expression filters roads where the `importance` attribute equals 1, 2, or 3 (the most important roads in the network).

> **Note**: Adjust the field name (`importance`) and values according to your data schema. Some datasets may use `classe`, `hierarchy`, or similar field names.

### Step 4: Configure Spatial Filtering

In the **FILTRAGE** (Filtering) section:

1. **Primary Layer**: Select `troncon_de_route` (road segments) as your primary filtering layer
2. **Secondary Layer**: Select the layer you want to filter spatially (e.g., `batiment`)
3. **Operator**: Choose `ET` (AND) to combine filters
4. **Spatial Relationship**: Select `Sketchy` from the dropdown menu

### Step 5: Set Buffer Distance

The buffer distance determines how far from the selected roads features will be included:

1. Locate the buffer distance setting (shown as the sketchy icon area)
2. Set the buffer distance to **50** meters
3. This creates a 50-meter zone around all selected road segments

### Step 6: Apply the Filter

1. Click the **Filter** button (funnel icon) at the bottom of the FilterMate panel
2. FilterMate will:
   - Select road segments matching importance 1, 2, or 3
   - Create a 50-meter buffer around these roads
   - Filter the target layer to show only features intersecting this buffer

> ⚠️ **Performance Warning**: Complex spatial queries with large datasets and buffer operations may take several seconds to several minutes to process, depending on:
>
> - The number of features in your layers
> - The buffer distance (larger buffers = more intersections)
> - The number of target layers
> - Your data backend (PostgreSQL is fastest)
>
> **💡 Pro Tip: Save as Favorite!** Once you've configured a complex filter that works well, **save it as a favorite** using the ⭐ button in FilterMate. The next time you need this filter, simply load it from your favorites and the filter will be applied **instantly** — no need to recalculate! This is especially useful for recurring analysis workflows.

### Step 7: Filter Multiple Layers

To filter all surrounding layers, repeat the process for each layer:

| Target Layer             | Spatial Relationship | Buffer |
| ------------------------ | -------------------- | ------ |
| `batiment`               | Sketchy              | 50m    |
| `zone_de_vegetation`     | Sketchy              | 50m    |
| `surface_hydrographique` | Sketchy              | 50m    |
| `troncon_de_voie_ferree` | Sketchy              | 50m    |

> **Pro Tip**: You can add multiple layers to the filtering list in FilterMate to process them simultaneously.

---

## Understanding the Filter Expression

### Road Importance Levels

In many topographic datasets, road importance is classified as:

| Level | Description      | Examples                            |
| ----- | ---------------- | ----------------------------------- |
| 1     | Primary highways | Motorways, national routes          |
| 2     | Secondary roads  | Regional roads, main urban arteries |
| 3     | Tertiary roads   | Local main roads, collector streets |
| 4     | Minor roads      | Residential streets                 |
| 5     | Paths/Tracks     | Rural tracks, footpaths             |

### Expression Variants

Depending on your data structure, you might use:

```sql
-- Numeric field
"importance" <= 3

-- Text field
"importance" IN ('1', '2', '3')

-- Alternative field names
"classe" IN ('Autoroute', 'Nationale', 'Departementale')

-- Combined conditions
"importance" <= 3 AND "etat" = 'En service'
```

---

## Advanced Configuration

### Using AND/OR Operators

FilterMate supports combining multiple conditions:

- **ET (AND)**: Both conditions must be true
- **OU (OR)**: Either condition must be true

Example: Filter roads of importance 1-3 that are also paved:

```sql
"importance" IN ('1', '2', '3') AND "revetement" = 'Bitume'
```

### Variable Buffer Distances

For different analysis needs, adjust the buffer:

| Use Case                 | Recommended Buffer |
| ------------------------ | ------------------ |
| Noise impact study       | 100-200m           |
| Visual corridor analysis | 50-100m            |
| Direct adjacency         | 10-25m             |
| Regional overview        | 200-500m           |

### Sketchy Options

The "Sketchy" spatial relationship in FilterMate offers several modes:

1. **Sketchy** - Simplified intersection using buffered geometry
2. **Within** - Features completely inside the buffer
3. **Contains** - Buffer completely contains the feature
4. **Touches** - Features touching the buffer boundary

---

## Performance Tips

### For Large Datasets

1. **Use PostgreSQL/PostGIS** for optimal performance with large datasets
2. **Enable spatial indexes** on your layers
3. **Consider chunked processing** for millions of features

### Backend Selection

FilterMate automatically selects the best backend:

| Data Source        | Backend Used | Performance |
| ------------------ | ------------ | ----------- |
| PostgreSQL/PostGIS | PostgreSQL   | ⭐⭐⭐⭐⭐  |
| GeoPackage/Sketchy | Sketchy      | ⭐⭐⭐⭐    |
| Shapefile          | OGR          | ⭐⭐⭐      |
| Memory Layer       | QGIS         | ⭐⭐        |

---

## Export Results

After filtering, you can export the results:

1. Expand the **EXPORT** section in FilterMate
2. Choose your export format:
   - GeoPackage (recommended)
   - Sketchy
   - Shapefile
   - GeoJSON
3. Select destination folder
4. Click Export

---

## Complete Workflow Example

Here's a complete workflow for filtering a city's major road corridor:

```
1. Load layers: roads, buildings, vegetation, water, railways
2. Open FilterMate panel
3. Set selection: "importance" IN ('1', '2', '3')
4. Configure filtering:
   - Source: troncon_de_route
   - Targets: batiment, zone_de_vegetation, surface_hydrographique
   - Relationship: Sketchy
   - Buffer: 50m
5. Apply filter
6. Review results
7. Export to GeoPackage
```

---

## Troubleshooting

### Common Issues

| Problem              | Solution                                     |
| -------------------- | -------------------------------------------- |
| No features filtered | Check field names match your data            |
| Slow performance     | Use PostgreSQL backend or reduce buffer size |
| Missing layers       | Ensure layers are visible and loaded         |
| Buffer too large     | Reduce buffer distance for precision         |

### Checking Filter Status

The FilterMate panel shows:

- 🟢 Green indicator: Filter active
- 🔴 Red indicator: No filter applied
- Feature count after filtering

---

## Conclusion

FilterMate provides a powerful, intuitive way to:

- Filter vector data using attribute expressions
- Apply spatial filters with customizable buffer distances
- Chain filters across multiple related layers
- Export filtered results for further analysis

This workflow is essential for:

- Urban planning and development
- Transportation corridor analysis
- Environmental impact assessments
- Cartographic production

---

## Additional Resources

- [FilterMate GitHub Repository](https://github.com/sducournau/filter_mate)
- [QGIS Documentation](https://docs.qgis.org/)
- [Expression Builder Guide](https://docs.qgis.org/latest/en/docs/user_manual/expressions/index.html)

---

_FilterMate v2.5.x - A QGIS Plugin for Advanced Vector Filtering_
_Documentation updated: January 2026_
