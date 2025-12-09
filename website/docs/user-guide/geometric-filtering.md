---
sidebar_position: 4
---

# Geometric Filtering

Filter features based on their spatial relationships with other geometries using the **FILTERING** tab's geometric predicates and reference layer selector.

## Overview

Geometric filtering in FilterMate allows you to select features based on their **spatial relationships** with a reference layer. This is configured in the same **FILTERING tab** where you set up attribute filters.

**Key Components in FILTERING Tab**:
- **Spatial Predicates**: Multi-selection of geometric relationships (Intersects, Contains, Within, etc.)
- **Reference Layer**: Choose which layer to compare against
- **Combine Operator**: Use AND/OR when multiple predicates are selected
- **Buffer Integration**: Combine with buffer zones for proximity analysis

<!-- <!-- ![Spatial Predicates Selector](/img/ui-components/ui-filtering-spatial-predicates.png --> -->
*Multi-selection of spatial predicates in FILTERING tab*

<!-- <!-- ![Reference Layer Selector](/img/ui-components/ui-filtering-reference-layer.png --> -->
*Select reference layer for spatial comparison*

<!-- <!-- ![Combine Operator](/img/ui-components/ui-filtering-combine-operator.png --> -->
*Choose AND/OR to combine multiple predicates*

### Common Use Cases

- **Containment**: Find parcels within a municipality
- **Intersection**: Identify roads crossing a floodplain
- **Proximity**: Select buildings near a transit station (with buffer)
- **Adjacency**: Find neighboring polygons

:::tip Location
All geometric filtering is configured in the **FILTERING** tab, alongside attribute filters. Don't confuse this with the **EXPLORING** tab, which is for visualizing and selecting features from the current layer.
:::

## Status Indicators

When geometric filters are configured, FilterMate displays visual indicators:

<!-- <!-- ![Geometric Predicates Indicator](/img/ui-components/ui-filtering-has-predicates-indicator.png --> -->
*"Has Geometric Predicates" indicator (geo_predicates.png)*

<!-- <!-- ![Combine Operator Indicator](/img/ui-components/ui-filtering-has-combine-indicator.png --> -->
*"Has Combine Operator" indicator (add_multi.png) - shown when multiple predicates selected*

These badges provide quick visual feedback of active geometric filters.

## Spatial Predicates

### Intersects

Features that **share any space** with the reference geometry.

```mermaid
graph LR
    A[Reference Geometry] --> B{Intersects?}
    B -->|Yes| C[Feature overlaps,<br/>touches, or contains]
    B -->|No| D[Completely separate]
    
    style C fill:#90EE90
    style D fill:#FFB6C1
```

**Example Use Cases:**
- Roads crossing a district
- Properties touching a river
- Parcels within or overlapping a zone

**Expression:**
```sql
intersects($geometry, geometry(get_feature('zones', 'id', 1)))
```

### Contains

Reference geometry **completely contains** the feature (feature is entirely inside).

```mermaid
graph TB
    A[Reference Polygon] --> B{Feature completely<br/>inside?}
    B -->|Yes| C[✓ Contains]
    B -->|No| D[Extends outside<br/>or separate]
    
    style C fill:#90EE90
    style D fill:#FFB6C1
```

**Example Use Cases:**
- Buildings entirely within a parcel
- Parks completely inside city limits
- Points inside polygons

**Expression:**
```sql
contains(
    geometry(get_feature('parcels', 'id', @selected_parcel_id)),
    $geometry
)
```

### Within

Feature is **completely inside** the reference geometry (inverse of Contains).

```mermaid
graph TB
    A[Feature] --> B{Completely inside<br/>reference?}
    B -->|Yes| C[✓ Within]
    B -->|No| D[Extends outside<br/>or separate]
    
    style C fill:#90EE90
    style D fill:#FFB6C1
```

**Example Use Cases:**
- Find which district a point is in
- Properties entirely within a zone
- Features contained by a boundary

**Expression:**
```sql
within($geometry, geometry(get_feature('districts', 'name', 'Downtown')))
```

### Overlaps

Features that **partially overlap** (some shared area, but neither contains the other).

```mermaid
graph LR
    A[Two Polygons] --> B{Partial overlap?}
    B -->|Yes| C[✓ Overlaps<br/>shared area exists]
    B -->|No| D[Separate, touching,<br/>or one contains other]
    
    style C fill:#90EE90
    style D fill:#FFB6C1
```

**Example Use Cases:**
- Overlapping land use zones
- Conflicting property claims
- Intersecting administrative boundaries

**Expression:**
```sql
overlaps($geometry, geometry(get_feature('zones', 'type', 'commercial')))
```

### Touches

Features that **share a boundary** but don't overlap.

```mermaid
graph LR
    A[Two Geometries] --> B{Share boundary<br/>but no overlap?}
    B -->|Yes| C[✓ Touches<br/>adjacent]
    B -->|No| D[Overlap or<br/>separate]
    
    style C fill:#90EE90
    style D fill:#FFB6C1
```

**Example Use Cases:**
- Adjacent parcels
- Neighboring administrative units
- Connected road segments

**Expression:**
```sql
touches($geometry, geometry(get_feature('parcels', 'id', @parcel_id)))
```

### Disjoint

Features that **don't share any space** (completely separate).

```mermaid
graph LR
    A[Two Geometries] --> B{No shared space?}
    B -->|Yes| C[✓ Disjoint<br/>completely separate]
    B -->|No| D[Intersect, touch,<br/>or overlap]
    
    style C fill:#90EE90
    style D fill:#FFB6C1
```

**Example Use Cases:**
- Features outside a restricted area
- Non-adjacent regions
- Isolated features

**Expression:**
```sql
disjoint($geometry, geometry(get_feature('restricted', 'id', 1)))
```

### Crosses

A line **crosses through** a polygon or another line.

```mermaid
graph LR
    A[Line Geometry] --> B{Crosses through<br/>other geometry?}
    B -->|Yes| C[✓ Crosses<br/>passes through]
    B -->|No| D[Separate, touches<br/>edge, or contained]
    
    style C fill:#90EE90
    style D fill:#FFB6C1
```

**Example Use Cases:**
- Roads crossing district boundaries
- Pipelines passing through zones
- Trails intersecting rivers

**Expression:**
```sql
crosses($geometry, geometry(get_feature('districts', 'name', 'Industrial')))
```

## Geometric Functions

### Distance Calculations

```sql
-- Features within 500 meters
distance($geometry, geometry(get_feature('stations', 'id', 1))) < 500

-- Find nearest features
distance($geometry, @reference_geom) < @max_distance
```

### Area and Length

```sql
-- Large polygons (area in map units)
area($geometry) > 10000

-- Long roads (length in map units)
length($geometry) > 1000

-- Perimeter
perimeter($geometry) > 500
```

### Centroid Operations

```sql
-- Features whose centroid is in a polygon
within(
    centroid($geometry),
    geometry(get_feature('zones', 'type', 'residential'))
)

-- Distance from centroid
distance(
    centroid($geometry),
    make_point(lon, lat)
) < 1000
```

## Combining Filters

### Spatial + Attribute

```sql
-- Residential buildings near transit
zone_type = 'residential'
AND distance($geometry, geometry(get_feature('transit', 'id', 1))) < 500
```

### Multiple Spatial Conditions

```sql
-- Within district but not in restricted zone
within($geometry, geometry(get_feature('districts', 'id', 5)))
AND disjoint($geometry, geometry(get_feature('restricted', 'id', 1)))
```

### Complex Scenarios

```sql
-- Properties near river but outside floodplain
distance($geometry, geometry(get_feature('rivers', 'name', 'Main River'))) < 200
AND NOT within($geometry, geometry(get_feature('floodplain', 'risk', 'high')))
AND property_type = 'residential'
```

## Workflow Example: Geometric Filtering

**Complete workflow for finding buildings near roads with buffer:**

```mermaid
sequenceDiagram
    participant U as User
    participant FM as FilterMate (FILTERING Tab)
    participant Q as QGIS
    participant DB as Backend (PostgreSQL/Spatialite)
    
    U->>FM: 1. Select source layer "buildings"
    FM->>U: Show layer info (15,234 features)
    
    U->>FM: 2. Select spatial predicate "Intersects"
    FM->>U: Enable predicate indicator
    
    U->>FM: 3. Select reference layer "roads"
    FM->>U: Load reference layer
    
    U->>FM: 4. Configure buffer: 200m, Standard type
    FM->>U: Show buffer indicators
    
    U->>FM: 5. Click FILTER button
    FM->>Q: Build spatial query
    Q->>DB: Execute: ST_Intersects(buildings.geom, ST_Buffer(roads.geom, 200))
    DB->>Q: Return matching feature IDs
    Q->>FM: Filtered features (3,847 matched)
    FM->>U: Update feature count + map display
    
    U->>FM: 6. Optionally switch to EXPORTING tab
    FM->>U: Export filtered results
```

### Step-by-Step: Complete Geometric Filter

**Scenario**: Find buildings within 200m of roads

<!-- <!-- ![Step 1 - FILTERING Tab](/img/workflows/workflow-filtering-01.png --> -->
*1. Open FILTERING tab, interface ready*

<!-- <!-- ![Step 2 - Select Source](/img/workflows/workflow-filtering-02.png --> -->
*2. Select "buildings" layer in layer selector*

<!-- <!-- ![Step 3 - Layer Info](/img/workflows/workflow-filtering-03.png --> -->
*3. Verify layer info: Spatialite, 15,234 features, EPSG:4326*

<!-- <!-- ![Step 4 - Spatial Predicate](/img/workflows/workflow-filtering-04.png --> -->
*4. Select "Intersects" in spatial predicates multi-selector*

<!-- <!-- ![Step 5 - Reference Layer](/img/workflows/workflow-filtering-05.png --> -->
*5. Select "roads" as reference layer (distant layer)*

<!-- <!-- ![Step 6 - Buffer Distance](/img/workflows/workflow-filtering-06.png --> -->
*6. Set buffer: Distance=200, Unit=meters*

<!-- <!-- ![Step 7 - Buffer Type](/img/workflows/workflow-filtering-07.png --> -->
*7. Choose buffer type: Standard*

<!-- <!-- ![Step 8 - Indicators](/img/workflows/workflow-filtering-08.png --> -->
*8. View active indicators: geo_predicates, buffer_value, buffer_type*

<!-- <!-- ![Step 9 - Apply](/img/workflows/workflow-filtering-09.png --> -->
*9. Click FILTER button (filter.png icon)*

<!-- <!-- ![Step 10 - Progress](/img/workflows/workflow-filtering-10.png --> -->
*10. Progress bar shows backend processing (PostgreSQL⚡ or Spatialite)*

<!-- <!-- ![Step 11 - Results](/img/workflows/workflow-filtering-11.png --> -->
*11. Map displays filtered features: 3,847 buildings within 200m of roads*

## Combining Multiple Predicates

When you select multiple spatial predicates, use the **Combine Operator** to specify how they should be combined:

<!-- <!-- ![Combine Operator](/img/workflows/workflow-combine-02.png --> -->
*Select AND or OR to combine predicates*

**Example - Parcels that Intersect OR Touch a Protected Zone:**

<!-- <!-- ![Step 1 - Multi-Predicates](/img/workflows/workflow-combine-01.png --> -->
*1. Select both "Intersects" AND "Touches" predicates*

<!-- <!-- ![Step 2 - OR Operator](/img/workflows/workflow-combine-02.png --> -->
*2. Choose "OR" in combine operator dropdown*

<!-- <!-- ![Step 3 - Indicator](/img/workflows/workflow-combine-03.png --> -->
*3. "Has Combine Operator" indicator activates (add_multi.png)*

<!-- <!-- ![Step 4 - Reference](/img/workflows/workflow-combine-04.png --> -->
*4. Select "protected_zones" as reference layer*

<!-- <!-- ![Step 5 - Results](/img/workflows/workflow-combine-05.png --> -->
*5. Apply filter: 1,834 parcels found*

<!-- <!-- ![Step 6 - Map View](/img/workflows/workflow-combine-06.png --> -->
*6. Parcels highlighted on map (intersecting OR touching zone)*

**Combine Operator Logic**:
- **AND**: Feature must satisfy ALL selected predicates
- **OR**: Feature must satisfy AT LEAST ONE predicate

```sql
-- AND example: Must intersect AND touch
ST_Intersects(geom, ref) AND ST_Touches(geom, ref)

-- OR example: Can intersect OR touch
ST_Intersects(geom, ref) OR ST_Touches(geom, ref)
```

## Backend-Specific Behavior

### PostgreSQL (Fastest)

```sql
-- Uses GIST spatial index
ST_Intersects(geometry, reference_geometry)
```

- ✅ Full spatial index support
- ✅ Optimized for large datasets
- ✅ Hardware acceleration

### Spatialite (Fast)

```sql
-- Uses R-tree spatial index
ST_Intersects(geometry, reference_geometry)
```

- ✅ R-tree spatial index
- ✅ Good performance for medium datasets
- ⚠️ Slower than PostgreSQL for complex queries

### OGR (Fallback)

```sql
-- No spatial index
-- Scans all features
```

- ❌ No spatial index
- ⚠️ Performance degrades with size
- ✓ Universal compatibility

:::tip Performance Tip
For large datasets with frequent spatial queries, use **PostgreSQL** with GIST indexes for best performance.
:::

## Practical Examples

### Urban Planning

#### Find Parcels Near Transit
```sql
-- Within 400m walking distance
distance(
    centroid($geometry),
    geometry(get_feature('metro_stations', 'line', 'Red'))
) < 400
AND land_use = 'undeveloped'
```

#### Identify Development Opportunities
```sql
-- Large parcels, not in protected areas
area($geometry) > 5000
AND disjoint($geometry, geometry(get_feature('protected_areas', 'status', 'active')))
AND zone = 'mixed-use'
```

### Environmental Analysis

#### Protected Areas Impact
```sql
-- Projects intersecting protected zones
intersects(
    $geometry,
    geometry(get_feature('protected', 'category', 'wildlife'))
)
AND project_status = 'proposed'
```

#### Watershed Analysis
```sql
-- Properties within watershed
within(
    $geometry,
    geometry(get_feature('watersheds', 'name', 'Main Watershed'))
)
AND distance($geometry, geometry(get_feature('rivers', 'id', 1))) < 100
```

### Emergency Services

#### Coverage Analysis
```sql
-- Areas NOT covered by fire stations (&>;5km)
distance(
    centroid($geometry),
    aggregate('fire_stations', 'collect', $geometry)
) > 5000
```

#### Evacuation Routes
```sql
-- Roads within evacuation zone
intersects(
    $geometry,
    buffer(geometry(get_feature('hazard', 'type', 'flood')), 1000)
)
AND road_type IN ('highway', 'major')
```

## Performance Optimization

### 1. Use Spatial Indexes

Ensure spatial indexes exist:

**PostgreSQL:**
```sql
CREATE INDEX idx_geom ON table_name USING GIST (geometry);
```

**Spatialite:**
```sql
SELECT CreateSpatialIndex('table_name', 'geometry');
```

### 2. Simplify Reference Geometries

```sql
-- Simplify before filtering (faster)
intersects(
    $geometry,
    simplify(geometry(get_feature('complex_polygon', 'id', 1)), 10)
)
```

### 3. Filter Attributes First

```sql
-- ✅ Fast: Filter by attribute first
status = 'active'
AND intersects($geometry, @reference_geom)

-- ❌ Slower: Spatial filter first
intersects($geometry, @reference_geom)
AND status = 'active'
```

### 4. Use Bounding Box Checks

```sql
-- Fast bounding box check before expensive spatial operation
bbox($geometry, @reference_geom)
AND intersects($geometry, @reference_geom)
```

## Troubleshooting

### Invalid Geometries

```sql
-- Check geometry validity
is_valid($geometry)

-- Repair invalid geometries (if needed)
make_valid($geometry)
```

### Empty Results

1. **Check CRS compatibility** - Ensure layers use compatible projections
2. **Verify reference geometry** - Confirm reference feature exists
3. **Test simpler predicates** - Try `intersects` before `contains`
4. **Inspect geometries** - Check for NULL or invalid geometries

### Performance Issues

1. **Verify spatial indexes** - Check indexes exist and are up-to-date
2. **Simplify geometries** - Reduce vertex count if possible
3. **Use appropriate backend** - PostgreSQL for large datasets
4. **Break complex queries** - Split into multiple simpler filters

## Related Topics

- [Buffer Operations](buffer-operations.md) - Configure buffer zones in FILTERING tab for proximity analysis
- [Filtering Basics](filtering-basics.md) - Combine geometric filters with attribute filters
- [Interface Overview](interface-overview.md) - Complete FILTERING tab component guide
- [Export Features](export-features.md) - Export filtered results from EXPORTING tab

:::info FILTERING Tab Components
The FILTERING tab combines three types of filters:
1. **Attribute filters** - Expression builder (see [Filtering Basics](filtering-basics.md))
2. **Geometric filters** - Spatial predicates + reference layer (this page)
3. **Buffer operations** - Distance zones (see [Buffer Operations](buffer-operations.md))

All three can be used together in a single filter operation.
:::

## Next Steps

- **[Buffer Operations](buffer-operations.md)** - Add distance-based proximity zones to geometric filters
- **[Export Features](export-features.md)** - Save filtered results in various formats

**Complete Workflow**: See [First Filter Guide](../getting-started/first-filter.md) for a comprehensive example combining attribute, geometric, and buffer filters.
