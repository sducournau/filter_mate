---
sidebar_position: 2
---

# Spatial Predicates Visual Reference

Complete visual guide to spatial relationship functions in FilterMate with examples and diagrams.

## What Are Spatial Predicates?

**Spatial predicates** are functions that test the **geometric relationship** between features. They answer questions like:
- Does this parcel **touch** the road?
- Is this building **within** the flood zone?
- Does this pipeline **cross** the river?
- Are these properties **near** the school?

Unlike attribute filters (`price > 100000`), spatial predicates work with **geometry**.

---

## Quick Reference Table

| Predicate | Question | Example Use Case | Performance |
|-----------|----------|------------------|-------------|
| **intersects** | Do they overlap/touch at all? | Find parcels touching roads | ⚡⚡⚡ Fast |
| **within** | Is A completely inside B? | Buildings in flood zone | ⚡⚡ Medium |
| **contains** | Does A completely enclose B? | Parcels containing buildings | ⚡⚡ Medium |
| **touches** | Do edges meet (but not overlap)? | Adjacent land parcels | ⚡⚡⚡ Fast |
| **crosses** | Does A pass through B? | Roads crossing rivers | ⚡⚡ Medium |
| **overlaps** | Do they share area (but not identical)? | Overlapping land claims | ⚡ Slow |
| **disjoint** | Are they completely separate? | Properties NOT near hazards | ⚡ Slow |
| **distance** | How far apart? | Within 500m of station | ⚡⚡ Medium |
| **ST_DWithin** | Within X distance? (PostGIS) | Buildings within 1km buffer | ⚡⚡⚡ Fast |

---

## Visual Guide by Predicate

### 1. intersects()

**Tests**: Do geometries overlap or touch in **any way**?

**Returns TRUE if**:
- Features share any point
- Features overlap partially or completely
- Features touch at boundary
- One feature is inside another

**Diagram**:
```
     A          B
  ┌─────┐   ┌─────┐
  │  ✓  │   │  ✓  │     intersects(A,B) = TRUE
  │   ┌─┼───┼─┐   │
  └───┼─┘   └─┼───┘
      └───────┘

     A          B
  ┌─────┐   ┌─────┐
  │     │   │     │     intersects(A,B) = FALSE  
  └─────┘   └─────┘
```

**Example Use Cases**:

```sql
-- Buildings intersecting flood zones
intersects(
  $geometry,
  aggregate('flood_zones', 'collect', $geometry)
)

-- Parcels touching or crossing road network
intersects(
  $geometry,
  aggregate('roads', 'collect', $geometry)
)

-- Properties overlapping new development area
intersects(
  $geometry,
  geometry(get_feature('development_plan', 'id', 1))
)
```

**When to use**: 
- ✅ Most versatile spatial test
- ✅ Fast with spatial indexes
- ✅ Catches all types of spatial relationships
- ❌ Doesn't distinguish touch vs overlap vs contain

**Performance**: ⚡⚡⚡ Excellent (fastest spatial predicate)

---

### 2. within()

**Tests**: Is geometry A **completely inside** geometry B?

**Returns TRUE if**:
- All points of A are inside B
- A can touch B's boundary
- A cannot extend outside B

**Diagram**:
```
     B (large polygon)
  ┌─────────────────┐
  │    A (small)    │
  │   ┌───────┐     │   within(A,B) = TRUE
  │   │   ✓   │     │
  │   └───────┘     │
  └─────────────────┘

     B               A
  ┌─────┐       ┌───────┐
  │     │       │   ✗   │   within(A,B) = FALSE
  │  ┌──┼───────┼──┐    │   (A extends outside B)
  └──┼──┘       └──┼────┘
     └─────────────┘
```

**Example Use Cases**:

```sql
-- Buildings completely inside city limits
within(
  $geometry,
  aggregate('city_boundary', 'collect', $geometry)
)

-- Points within protected area (not just touching edge)
within(
  $geometry,
  geometry(get_feature('protected_zones', 'zone_id', 'PROT-001'))
)

-- Properties entirely inside tax district
within(
  $geometry,
  aggregate('tax_districts', 'collect', $geometry)
)
```

**When to use**:
- ✅ Need complete containment (not partial)
- ✅ Compliance checking (fully inside boundary)
- ✅ Point-in-polygon tests
- ❌ Will miss features that cross boundaries

**Performance**: ⚡⚡ Good (benefits from spatial index)

**Common mistake**: Using `within()` when you want `intersects()`
- Buildings partially in zone: Use `intersects()`
- Buildings fully in zone: Use `within()`

---

### 3. contains()

**Tests**: Does geometry A **completely enclose** geometry B?

**Returns TRUE if**:
- All points of B are inside A
- Opposite of `within()`
- `contains(A,B)` = `within(B,A)`

**Diagram**:
```
     A (large parcel)
  ┌─────────────────┐
  │  B (building)   │
  │   ┌───────┐     │   contains(A,B) = TRUE
  │   │   ✓   │     │   (A encloses B)
  │   └───────┘     │
  └─────────────────┘

     A               B
  ┌─────┐       ┌───────┐
  │  ✗  │       │       │   contains(A,B) = FALSE
  │  ┌──┼───────┼──┐    │   (B extends outside A)
  └──┼──┘       └──┼────┘
     └─────────────┘
```

**Example Use Cases**:

```sql
-- Parcels that contain buildings (find developed lots)
contains(
  $geometry,
  aggregate('buildings', 'collect', $geometry)
)

-- Districts containing all their facilities
-- (Check administrative coverage completeness)
contains(
  $geometry,
  aggregate('service_points', 'collect', $geometry, filter:="district_id" = @district_id)
)

-- Polygons fully enclosing points of interest
array_length(
  overlay_contains('points_of_interest', $geometry)
) > 0
```

**When to use**:
- ✅ Finding "parent" geometries (parcels with buildings)
- ✅ Checking coverage completeness
- ✅ Quality control (ensure points in correct polygons)
- ❌ Rare in FilterMate (usually filter the contained layer instead)

**Performance**: ⚡⚡ Good

**Pro tip**: Usually easier to filter the smaller layer with `within()` than the larger layer with `contains()`

---

### 4. touches()

**Tests**: Do geometries **share a boundary but NOT overlap**?

**Returns TRUE if**:
- Edges or vertices touch
- Interiors do NOT overlap
- For polygons: share an edge
- For lines: share an endpoint

**Diagram**:
```
  Adjacent Polygons (share edge):
  
     A       │      B
  ┌─────┐    │   ┌─────┐
  │     │    │   │     │   touches(A,B) = TRUE
  │  ✓  │←───────→│  ✓  │   (share boundary)
  └─────┘    │   └─────┘

  Overlapping Polygons:
  
     A          B
  ┌─────┐   ┌─────┐
  │  ✗  │   │  ✗  │     touches(A,B) = FALSE
  │   ┌─┼───┼─┐   │     (overlapping, not just touching)
  └───┼─┘   └─┼───┘
      └───────┘
```

**Example Use Cases**:

```sql
-- Find adjacent parcels (share property line)
touches(
  $geometry,
  aggregate('parcels', 'collect', $geometry)
)

-- Administrative boundaries that adjoin (no gaps/overlaps)
touches(
  $geometry,
  geometry(get_feature('counties', 'county_id', 'NEXT_COUNTY'))
)

-- Road segments that connect (topology check)
touches(
  $geometry,
  aggregate('road_network', 'collect', $geometry, filter:="road_id" != @road_id)
)
```

**When to use**:
- ✅ Finding neighbors/adjacent features
- ✅ Topology validation (check for gaps/overlaps)
- ✅ Network connectivity analysis
- ❌ Not useful for point layers

**Performance**: ⚡⚡⚡ Excellent

**Common use**: Finding adjacent land parcels for ownership analysis or zoning studies

---

### 5. crosses()

**Tests**: Does geometry A **pass through** geometry B?

**Returns TRUE if**:
- Geometries intersect
- Have some (not all) interior points in common
- Typically: line crossing polygon, or line crossing line

**Diagram**:
```
  Line crossing polygon:
  
      ┌─────────┐
      │    B    │
  ────┼─────────┼────  A (line)
      │    ✓    │      crosses(A,B) = TRUE
      └─────────┘

  Line contained in polygon:
  
      ┌─────────┐
      │  ─────  │  A (line)
      │    ✗    │      crosses(A,B) = FALSE
      └─────────┘      (within, not crossing)
```

**Example Use Cases**:

```sql
-- Roads crossing rivers (bridge locations)
crosses(
  $geometry,
  aggregate('rivers', 'collect', $geometry)
)

-- Pipelines crossing property boundaries (easements)
crosses(
  $geometry,
  aggregate('parcels', 'collect', $geometry)
)

-- Power lines crossing protected zones
crosses(
  $geometry,
  aggregate('conservation_areas', 'collect', $geometry)
)
```

**When to use**:
- ✅ Linear features (roads, pipes, power lines)
- ✅ Finding intersections (bridges, crossings)
- ✅ Identifying boundary violations
- ❌ Not meaningful for point layers

**Performance**: ⚡⚡ Medium

**Common use**: Infrastructure analysis - finding where linear utilities cross boundaries or natural features

---

### 6. overlaps()

**Tests**: Do geometries **share area but not identical**?

**Returns TRUE if**:
- Geometries intersect
- Have same dimension (polygon-polygon or line-line)
- Intersection is also same dimension
- Neither is completely inside the other

**Diagram**:
```
  Overlapping polygons:
  
     A          B
  ┌─────┐   ┌─────┐
  │     │   │     │
  │   ┌─┼───┼─┐   │   overlaps(A,B) = TRUE
  └───┼─┘   └─┼───┘   (partial overlap)
      └───────┘

     A          B
  ┌─────┐   ┌─────┐
  │     │   │     │   overlaps(A,B) = FALSE
  └─────┘   └─────┘   (disjoint - no overlap)
```

**Example Use Cases**:

```sql
-- Overlapping land claims (ownership disputes)
overlaps(
  $geometry,
  aggregate('parcels', 'collect', $geometry, filter:="parcel_id" != @parcel_id)
)

-- Overlapping zoning designations (planning conflicts)
overlaps(
  $geometry,
  aggregate('zoning_districts', 'collect', $geometry)
)

-- Overlapping service coverage (redundancy analysis)
overlaps(
  $geometry,
  aggregate('service_areas', 'collect', $geometry, filter:="provider_id" != @provider_id)
)
```

**When to use**:
- ✅ Quality control (finding overlaps that shouldn't exist)
- ✅ Conflict detection (competing claims)
- ✅ Coverage analysis (redundant areas)
- ❌ Slower than `intersects()` - use that if you just need "any intersection"

**Performance**: ⚡ Slower (more complex calculation)

**Common use**: Data quality checking - finding overlapping polygons that should be mutually exclusive

---

### 7. disjoint()

**Tests**: Are geometries **completely separate** (no contact)?

**Returns TRUE if**:
- Geometries do NOT intersect
- Do NOT touch
- Do NOT share any point
- Opposite of `intersects()`

**Diagram**:
```
     A          B
  ┌─────┐   ┌─────┐
  │  ✓  │   │  ✓  │     disjoint(A,B) = TRUE
  │     │   │     │     (completely separate)
  └─────┘   └─────┘

     A          B
  ┌─────┐   ┌─────┐
  │  ✗  │   │  ✗  │     disjoint(A,B) = FALSE
  │   ┌─┼───┼─┐   │     (they intersect)
  └───┼─┘   └─┼───┘
      └───────┘
```

**Example Use Cases**:

```sql
-- Properties NOT in flood zones
disjoint(
  $geometry,
  aggregate('flood_zones', 'collect', $geometry)
)

-- Buildings outside protected areas
disjoint(
  $geometry,
  aggregate('protected_areas', 'collect', $geometry)
)

-- Parcels with no road access (isolated)
disjoint(
  $geometry,
  aggregate('roads', 'collect', $geometry)
)
```

**When to use**:
- ✅ "NOT near" queries
- ✅ Finding gaps in coverage
- ✅ Exclusion zones
- ⚠️ Often better to use `NOT intersects()` instead

**Performance**: ⚡ Slower (tests all features)

**Pro tip**: `disjoint(A,B)` = `NOT intersects(A,B)` - use whichever is clearer

---

### 8. distance()

**Tests**: How far apart are geometries? (minimum distance)

**Returns**: Numeric distance in CRS units (usually meters)

**Diagram**:
```
        distance = 500m
     A  ←─────────→  B
  ┌─────┐        ┌─────┐
  │     │        │     │
  └─────┘        └─────┘

  distance(A,B) = 500

  
  Overlapping (distance = 0):
     A          B
  ┌─────┐   ┌─────┐
  │   ┌─┼───┼─┐   │
  └───┼─┘   └─┼───┘
      └───────┘
  
  distance(A,B) = 0
```

**Example Use Cases**:

```sql
-- Properties within 500m of subway station
distance(
  $geometry,
  aggregate('subway_stations', 'collect', $geometry)
) <= 500

-- Calculate distance to nearest hospital
array_min(
  array_foreach(
    overlay_nearest('hospitals', $geometry, limit:=1),
    distance(geometry(@element), $geometry)
  )
)

-- Buildings more than 100m from road (no access)
distance(
  $geometry,
  aggregate('roads', 'collect', $geometry)
) > 100
```

**When to use**:
- ✅ Proximity analysis (near/far queries)
- ✅ Buffer zones without creating buffers
- ✅ Ranking by distance
- ⚠️ Can be slow for large datasets (use ST_DWithin in PostgreSQL)

**Performance**: ⚡⚡ Medium (⚡⚡⚡ Fast in PostgreSQL with ST_DWithin)

**Units**: Distance in CRS units:
- Projected CRS (UTM): meters
- Geographic CRS (WGS84): degrees (⚠️ not useful - reproject!)

---

### 9. ST_DWithin() (PostgreSQL Only)

**Tests**: Are geometries within X distance? (optimized)

**Returns**: Boolean (TRUE/FALSE)

**Available**: PostgreSQL/PostGIS backend only

**Diagram**: Same as `distance() <= X`, but much faster

**Example Use Cases**:

```sql
-- PostgreSQL backend - FAST proximity query
-- Buildings within 1km of fire stations
ST_DWithin(
  buildings.geom,
  fire_stations.geom,
  1000  -- meters
)

-- Compare performance:
-- SLOW:  distance($geometry, ...) <= 1000
-- FAST:  ST_DWithin($geometry, ..., 1000)
```

**When to use**:
- ✅ Large datasets (>10k features)
- ✅ PostgreSQL backend available
- ✅ Proximity queries with specific distance threshold
- ❌ Not available in Spatialite/OGR (use `distance()` instead)

**Performance**: ⚡⚡⚡ Excellent (uses spatial index efficiently)

**Why faster**: Doesn't calculate exact distance, just checks "within X" using optimized algorithms

---

## Combining Predicates

### Multiple Spatial Conditions

**AND** - Must satisfy all conditions:

```sql
-- Buildings in flood zone AND near river
intersects($geometry, aggregate('flood_zones', 'collect', $geometry))
AND distance($geometry, aggregate('rivers', 'collect', $geometry)) < 100
```

**OR** - Must satisfy at least one:

```sql
-- Properties touching road OR railroad
touches($geometry, aggregate('roads', 'collect', $geometry))
OR touches($geometry, aggregate('railroads', 'collect', $geometry))
```

### Negation (NOT)

```sql
-- Buildings NOT in historic district
NOT intersects($geometry, aggregate('historic_districts', 'collect', $geometry))

-- Same as:
disjoint($geometry, aggregate('historic_districts', 'collect', $geometry))
```

### Complex Relationships

```sql
-- Parcels that:
-- 1. Touch a road (access)
-- 2. Are within city limits
-- 3. Are NOT in flood zone
-- 4. Are within 1km of school

touches($geometry, aggregate('roads', 'collect', $geometry))
AND within($geometry, aggregate('city_boundary', 'collect', $geometry))
AND NOT intersects($geometry, aggregate('flood_zones', 'collect', $geometry))
AND distance($geometry, aggregate('schools', 'collect', $geometry)) <= 1000
```

---

## Performance Optimization Guide

### Spatial Index Usage

**Predicates that use spatial index** (fast ⚡⚡⚡):
- `intersects()`
- `touches()`
- `ST_DWithin()` (PostgreSQL)

**Predicates that partially use index** (medium ⚡⚡):
- `within()`
- `contains()`
- `crosses()`

**Predicates that don't use index well** (slow ⚡):
- `overlaps()`
- `disjoint()`
- `distance()` with large datasets

### Optimization Strategies

**1. Filter attributes first, then spatial**:

```sql
-- GOOD (fast):
"property_type" = 'residential'  -- Cheap attribute filter first
AND intersects($geometry, ...)   -- Then spatial filter

-- BAD (slow):
intersects($geometry, ...)       -- Expensive spatial test first
AND "property_type" = 'residential'
```

**2. Use ST_DWithin instead of distance() in PostgreSQL**:

```sql
-- SLOW:
distance($geometry, aggregate('points', 'collect', $geometry)) <= 1000

-- FAST (PostgreSQL only):
ST_DWithin(geom, points.geom, 1000)
```

**3. Simplify complex geometries**:

```
Vector → Geometry → Simplify
Tolerance: 1-10 meters (invisible change, major speedup)
```

**4. Pre-filter to smaller area**:

```sql
-- Add bounding box filter before spatial predicate
"county" = 'Los Angeles'  -- Quick attribute filter
AND intersects(...)        -- Then spatial filter
```

**5. Create spatial indexes**:

```
Layer Properties → Create Spatial Index
(Automatic in PostgreSQL, manual in Spatialite)
```

---

## Backend Compatibility

| Predicate | OGR | Spatialite | PostgreSQL | Notes |
|-----------|-----|------------|------------|-------|
| **intersects** | ✅ | ✅ | ✅ | Universal |
| **within** | ✅ | ✅ | ✅ | Universal |
| **contains** | ✅ | ✅ | ✅ | Universal |
| **touches** | ✅ | ✅ | ✅ | Universal |
| **crosses** | ✅ | ✅ | ✅ | Universal |
| **overlaps** | ✅ | ✅ | ✅ | Universal |
| **disjoint** | ✅ | ✅ | ✅ | Universal |
| **distance** | ✅ | ✅ | ✅ | Units depend on CRS |
| **ST_DWithin** | ❌ | ❌ | ✅ | PostgreSQL only |
| **ST_Distance** | ❌ | ⚠️ | ✅ | Use `distance()` instead |

**Legend**:
- ✅ Fully supported
- ⚠️ Limited support
- ❌ Not available

---

## Common Patterns

### Buffer-like Queries (Without Creating Buffer)

**Using distance()**:
```sql
-- Features within 500m of point
distance($geometry, geometry(get_feature('points', 'id', 1))) <= 500
```

**Using ST_DWithin() (PostgreSQL)**:
```sql
-- Faster for large datasets
ST_DWithin(geom, point.geom, 500)
```

### Inverse Queries (NOT in zone)

```sql
-- Properties NOT in flood zone
NOT intersects($geometry, aggregate('flood_zones', 'collect', $geometry))

-- Or equivalently:
disjoint($geometry, aggregate('flood_zones', 'collect', $geometry))
```

### Nearest Feature

```sql
-- Distance to nearest school
array_min(
  array_foreach(
    overlay_nearest('schools', $geometry, limit:=1),
    distance(geometry(@element), $geometry)
  )
)
```

### Count Features in Area

```sql
-- Number of buildings in parcel
array_length(
  overlay_within('buildings', $geometry)
)

-- Filter parcels with >5 buildings:
array_length(overlay_within('buildings', $geometry)) > 5
```

### Multi-Layer Spatial Join

```sql
-- Properties that:
-- Touch road AND within 1km of school AND in city limits

touches($geometry, aggregate('roads', 'collect', $geometry))
AND distance($geometry, aggregate('schools', 'collect', $geometry)) <= 1000
AND within($geometry, aggregate('city_boundary', 'collect', $geometry))
```

---

## Troubleshooting

### "Function not found" or "Invalid predicate"

**Cause**: Syntax error or backend incompatibility

**Solution**:
1. Check spelling: `intersects()` not `intersect()`
2. Verify backend: `ST_DWithin()` only works in PostgreSQL
3. Use QGIS function: `distance()` not SQL `ST_Distance()`

### Results don't make sense (wrong features selected)

**Cause**: CRS mismatch or incorrect layer reference

**Solution**:
1. Verify CRS: Both layers must use same projected CRS
2. Check layer name: Case-sensitive, must match exactly
3. Test with known feature: Manually verify a single result

### Performance very slow (>30 seconds)

**Cause**: Large dataset without optimization

**Solution**:
1. Switch to PostgreSQL backend
2. Create spatial indexes
3. Add attribute pre-filter
4. Use `ST_DWithin()` instead of `distance()`
5. Simplify geometries

### Distance returns unexpected values

**Cause**: CRS using degrees instead of meters

**Solution**:
1. Reproject to local UTM zone or state plane
2. Check CRS: Properties → Information
3. Never use EPSG:4326 (lat/lon) for distance calculations

---

## Quick Decision Tree

**Which predicate should I use?**

```
Do you need to know distance?
├─ Yes → Use distance() or ST_DWithin()
└─ No → Continue...

Do features need to share area?
├─ Yes, any overlap → Use intersects()
├─ Yes, completely inside → Use within()
├─ Yes, only edges touch → Use touches()
├─ Yes, line passes through → Use crosses()
└─ No overlap allowed → Use disjoint()

Do you need to find neighbors?
└─ Yes → Use touches()

Do you need coverage analysis?
└─ Yes → Use within() or contains()

Do you need to find conflicts?
└─ Yes → Use overlaps()
```

---

## Further Learning

- 📖 [Buffer Operations](../../user-guide/buffer-operations.md)
- 📖 [Geometric Filtering](../../user-guide/geometric-filtering.md)
- 📖 [PostGIS Documentation](https://postgis.net/docs/reference.html)
- 📖 [OGC Simple Features Specification](https://www.ogc.org/standards/sfa)

---

## Summary

✅ **Key takeaways**:
- `intersects()` is fastest and most versatile
- `within()` for "completely inside" tests
- `distance()` for proximity analysis
- `ST_DWithin()` for optimized distance queries (PostgreSQL)
- Use projected CRS (meters) for distance calculations
- Apply attribute filters before spatial filters

🎯 **Pro tips**:
- Start with simple predicates, add complexity gradually
- Test on small datasets first
- Use spatial indexes for performance
- Prefer `intersects()` unless you specifically need another relationship
