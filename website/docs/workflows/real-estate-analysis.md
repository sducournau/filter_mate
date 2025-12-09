---
sidebar_position: 5
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Real Estate Analysis: Market Filtering

Filter residential properties by price, size, and proximity to schools to identify optimal investment opportunities.

## Scenario Overview

**Goal**: Find single-family homes priced $200k-$400k, >150m², within 1km of highly-rated schools.

**Real-World Application**:
- Real estate investors finding properties matching criteria
- Home buyers searching for family-friendly neighborhoods
- Real estate agents providing data-driven recommendations
- Market analysts evaluating property values vs. amenities

**Estimated Time**: 8 minutes

**Difficulty**: ⭐ Beginner

---

## Prerequisites

### Required Data

1. **Residential Properties Layer** (points or polygons)
   - Property listings or parcel data
   - Required attributes:
     - `price` (numeric)
     - `area_sqm` or `living_area` (numeric)
     - `property_type` (text: 'single_family', 'condo', etc.)
   - Optional: `bedrooms`, `bathrooms`, `year_built`

2. **Schools Layer** (points)
   - School locations
   - Optional but useful: `rating`, `school_level`, `name`
   - Covers your study area

### Sample Data Sources

**Real Estate Data**:
- MLS (Multiple Listing Service) exports
- Zillow/Trulia data feeds (if available)
- Municipal property assessment databases
- OpenStreetMap buildings with tags

**Schools Data**:
```python
# QGIS QuickOSM plugin
Key: "amenity", Value: "school"
Key: "school", Value: "*"

# Or government data:
- National Center for Education Statistics (USA)
- Department for Education (UK)
- Local education authority databases
```

### Backend Recommendation

**Multi-Backend Comparison** - This workflow demonstrates all three:
- **PostgreSQL**: Fastest if you have &gt;10k properties
- **Spatialite**: Good middle ground for city-scale data
- **OGR**: Works everywhere, acceptable performance for &lt;5k properties

---

## Step-by-Step Instructions

### Step 1: Load and Inspect Property Data

1. **Load properties layer**: `residential_properties.gpkg`
2. **Open Attribute Table** (F6)
3. **Verify required fields exist**:
   ```
   ✓ price (numeric)
   ✓ area_sqm (numeric)
   ✓ property_type (text)
   ```

4. **Check data quality**:
   ```
   Sort by price: Look for unrealistic values (0, NULL, >$10M)
   Sort by area: Check for 0 or NULL values
   Filter property_type: Identify valid categories
   ```

:::tip Data Cleaning
If you have missing values:
```sql
-- Filter out incomplete records FIRST
"price" IS NOT NULL 
AND "area_sqm" > 0 
AND "property_type" IS NOT NULL
```
:::

### Step 2: Apply Basic Attribute Filters

**Using FilterMate**:

1. Open FilterMate panel
2. Select **residential_properties** layer
3. Choose **any backend** (attribute filtering works equally on all)
4. Enter expression:

<Tabs>
  <TabItem value="basic" label="Basic Filter" default>
    ```sql
    -- Price between $200k and $400k
    -- Area greater than 150m²
    -- Single-family homes only
    
    "price" >= 200000 
    AND "price" <= 400000
    AND "area_sqm" >= 150
    AND "property_type" = 'single_family'
    ```
  </TabItem>
  
  <TabItem value="advanced" label="Advanced (Multiple Types)">
    ```sql
    -- Accept multiple property types
    "price" BETWEEN 200000 AND 400000
    AND "area_sqm" >= 150
    AND "property_type" IN ('single_family', 'townhouse')
    AND "bedrooms" >= 3
    ```
  </TabItem>
  
  <TabItem value="deals" label="Investment Focused">
    ```sql
    -- Find undervalued properties (price per sqm)
    "price" BETWEEN 200000 AND 400000
    AND "area_sqm" >= 150
    AND "property_type" = 'single_family'
    AND ("price" / "area_sqm") < 2000  -- Less than $2000/m²
    ```
  </TabItem>
</Tabs>

5. Click **Apply Filter**
6. Review count: "Showing X of Y features"

**Expected Result**: Properties narrowed down by price, size, and type

### Step 3: Add Spatial Filter for School Proximity

Now add the **location-based** criterion:

1. **Ensure schools layer is loaded**: `schools.gpkg`
2. **Modify FilterMate expression** to add spatial component:

<Tabs>
  <TabItem value="ogr" label="OGR / Spatialite" default>
    ```sql
    -- Combine attribute filters + spatial proximity
    "price" >= 200000 
    AND "price" <= 400000
    AND "area_sqm" >= 150
    AND "property_type" = 'single_family'
    AND distance(
      $geometry,
      aggregate(
        layer:='schools',
        aggregate:='collect',
        expression:=$geometry
      )
    ) <= 1000
    ```
    
    **Alternative using overlay functions**:
    ```sql
    -- Same criteria + check any school within 1km exists
    "price" BETWEEN 200000 AND 400000
    AND "area_sqm" >= 150
    AND "property_type" = 'single_family'
    AND array_length(
      overlay_within(
        'schools',
        buffer($geometry, 1000)
      )
    ) > 0
    ```
  </TabItem>
  
  <TabItem value="postgresql" label="PostgreSQL">
    ```sql
    -- Using PostGIS spatial functions
    price >= 200000 
    AND price <= 400000
    AND area_sqm >= 150
    AND property_type = 'single_family'
    AND EXISTS (
      SELECT 1 
      FROM schools s
      WHERE ST_DWithin(
        properties.geom,
        s.geom,
        1000  -- 1km in meters
      )
    )
    ```
    
    **Or with distance calculation**:
    ```sql
    -- Include distance to nearest school as output
    SELECT 
      p.*,
      MIN(ST_Distance(p.geom, s.geom)) AS distance_to_school
    FROM properties p
    JOIN schools s ON ST_DWithin(p.geom, s.geom, 1000)
    WHERE price BETWEEN 200000 AND 400000
      AND area_sqm >= 150
      AND property_type = 'single_family'
    GROUP BY p.property_id
    ```
  </TabItem>
</Tabs>

3. Click **Apply Filter**
4. Review results on map (should be concentrated near schools)

### Step 4: Refine by School Quality (Optional)

If your schools layer has rating data:

```sql
-- Only properties near highly-rated schools (rating ≥ 8/10)
"price" BETWEEN 200000 AND 400000
AND "area_sqm" >= 150
AND "property_type" = 'single_family'
AND array_max(
  array_foreach(
    overlay_within('schools', buffer($geometry, 1000)),
    attribute(@element, 'rating')
  )
) >= 8
```

**What this does**:
1. Finds all schools within 1km buffer
2. Gets their rating values
3. Keeps properties where at least one nearby school has rating ≥8

### Step 5: Calculate Distance to Nearest School

Add field showing exact distance:

1. **Open Field Calculator** (Ctrl+I) on filtered layer
2. Create new field:
   ```
   Field name: nearest_school_m
   Type: Decimal (double)
   Precision: 1
   
   Expression:
   round(
     array_min(
       array_foreach(
         overlay_nearest('schools', $geometry, limit:=1),
         distance(geometry(@element), $geometry)
       )
     ),
     0
   )
   ```

3. **Add school name** (optional):
   ```
   Field name: nearest_school_name
   Type: Text (string)
   
   Expression:
   attribute(
     overlay_nearest('schools', $geometry, limit:=1)[0],
     'name'
   )
   ```

### Step 6: Rank Properties by Value

Create a **value score** combining multiple factors:

1. **Open Field Calculator**
2. Create calculated field:
   ```
   Field name: value_score
   Type: Decimal (double)
   
   Expression:
   -- Higher score = better value
   -- Weighted factors:
   (400000 - "price") / 1000 * 0.4 +          -- Lower price = better (40% weight)
   ("area_sqm" - 150) * 0.3 +                 -- Larger area = better (30% weight)
   (1000 - "nearest_school_m") * 0.3          -- Closer school = better (30% weight)
   ```

3. **Sort by value_score** descending to see best deals first

### Step 7: Visualize Results

**Color by Distance to School**:

1. Right-click layer → **Symbology**
2. Choose **Graduated**
3. Value: `nearest_school_m`
4. Method: Natural Breaks
5. Colors: Green (close) → Yellow → Red (far)

**Add Labels**:
```
Label with: concat('$', "price"/1000, 'k - ', round("nearest_school_m",0), 'm to school')
Size: 10pt
Buffer: White, 1mm
```

### Step 8: Export Matches for Analysis

1. **In FilterMate**: Click **Export Filtered Features**
   ```
   Format: GeoPackage
   Filename: properties_investment_targets.gpkg
   CRS: WGS84 (for portability)
   Include all attributes: ✓
   ```

2. **Export attribute table as spreadsheet**:
   ```
   Right-click layer → Export → Save Features As
   Format: CSV or XLSX
   Fields: Select relevant columns only
   ```

3. **Create simple report** (optional):
   ```python
   # Python Console
   layer = iface.activeLayer()
   features = list(layer.getFeatures())
   
   print("=== Property Investment Report ===")
   print(f"Matching properties: {len(features)}")
   print(f"Average price: ${sum(f['price'] for f in features)/len(features):,.0f}")
   print(f"Average area: {sum(f['area_sqm'] for f in features)/len(features):.0f} m²")
   print(f"Average distance to school: {sum(f['nearest_school_m'] for f in features)/len(features):.0f} m")
   print(f"Price range: ${min(f['price'] for f in features):,} - ${max(f['price'] for f in features):,}")
   ```

---

## Understanding the Results

### What the Filter Shows

✅ **Selected properties**: Match ALL criteria:
- Price: $200,000 - $400,000
- Size: ≥150m²
- Type: Single-family home
- Location: ≤1km from school

❌ **Excluded properties**: Fail ANY criterion above

### Interpreting Property Matches

**High Value Score** (>500):
- Below-market pricing for area
- Good size for price point
- Very close to school (family appeal)
- **Action**: Priority viewing/offer

**Medium Score** (250-500):
- Fair market value
- Acceptable location
- Consider other factors (condition, neighborhood)
- **Action**: Compare with similar properties

**Low Score** (&lt;250):
- May be overpriced
- Far edge of school proximity
- Smaller size for price
- **Action**: Negotiate or wait for better options

### Quality Checks

1. **Sanity check**: View 5-10 random results
   - Verify prices are realistic
   - Measure school distance manually
   - Check property_type matches expectations

2. **Outlier detection**:
   ```sql
   -- Find unusually cheap properties (may be errors or great deals)
   "price" / "area_sqm" < 1500  -- Less than $1500/m²
   ```

3. **Map patterns**: Results should cluster near schools (if not, check CRS)

---

## Best Practices

### Search Strategy Refinement

**Start Broad, Narrow Gradually**:

1. **First pass**: Apply only price + size filters
2. **Review count**: If >100 results, add property_type filter
3. **Add spatial**: Apply school proximity
4. **Fine-tune**: Add school rating, bedrooms, etc.

**Save Filter History**:
- FilterMate automatically saves your expressions
- Use **Filter History** panel to compare different criteria sets
- Save best performing filters as **Favorites**

### Performance Considerations

**Backend Selection Guide**:

```
Properties | Schools | Recommended Backend
-----------|---------|--------------------
< 1,000    | Any     | OGR (simplest)
1k - 10k   | < 100   | Spatialite
> 10k      | Any     | PostgreSQL
Any        | > 500   | PostgreSQL + spatial index
```

**Optimization Tips**:

1. **Apply attribute filters first** (cheapest):
   ```sql
   -- Good: Attributes first, spatial last
   "price" BETWEEN 200000 AND 400000 AND distance(...) <= 1000
   
   -- Bad: Spatial first (slower)
   distance(...) <= 1000 AND "price" BETWEEN 200000 AND 400000
   ```

2. **Use spatial index** (automatic in PostgreSQL, create manually for Spatialite):
   ```
   Layer Properties → Create Spatial Index
   ```

3. **Simplify school geometry** if complex:
   ```
   Vector → Geometry → Centroids (schools → points)
   ```

### Real Estate Best Practices

**Market Analysis**:
- Run this filter weekly to track new listings
- Compare value_score trends over time
- Export results with timestamps for historical analysis

**Price Adjustment**:
```sql
-- Adjust for inflation or market changes
"price" * 1.05 BETWEEN 200000 AND 400000  -- +5% market growth
```

**Seasonal Patterns**:
```sql
-- School proximity more valuable in spring (family moving season)
-- Adjust weight in value_score calculation
```

---

## Common Issues

### Issue 1: No results or very few results

**Cause**: Criteria too strict or data quality issues

**Solutions**:
```
1. Relax price range: 150k-500k instead of 200k-400k
2. Reduce minimum area: 120m² instead of 150m²
3. Increase school distance: 2000m instead of 1000m
4. Check for NULL values in attributes
5. Verify schools layer covers same area as properties
```

### Issue 2: Distance calculation returns errors

**Cause**: CRS mismatch or layer not found

**Solution**:
```
1. Verify schools layer name matches exactly (case-sensitive)
2. Check both layers use same CRS (reproject if needed)
3. Ensure schools layer is in current project
4. Try simpler aggregate approach:
   
   distance(
     $geometry,
     aggregate('schools', 'collect', $geometry)
   ) <= 1000
```

### Issue 3: Performance slow (>30 seconds)

**Cause**: Large dataset or complex spatial query

**Solutions**:
```
1. Switch to PostgreSQL backend (major speedup)
2. Create spatial index on both layers
3. Pre-filter properties to smaller region:
   "city" = 'Boston' AND [rest of expression]
4. Reduce school query complexity:
   - Use buffer once: overlay_within('schools', buffer($geometry, 1000))
   - Cache in temporary field
```

### Issue 4: Results not near schools visually

**Cause**: CRS using degrees instead of meters

**Solution**:
```
1. Check layer CRS: Properties → Information
2. If EPSG:4326 (lat/lon), reproject to local UTM:
   Vector → Data Management → Reproject Layer
3. Update distance from 1000 to 0.01 if using degrees (not recommended)
```

---

## Next Steps

### Related Workflows

- **[Urban Planning Transit](./urban-planning-transit.md)**: Similar proximity analysis
- **[Emergency Services](./emergency-services.md)**: Inverse distance queries
- **[Transportation Planning](./transportation-planning.md)**: Export and CRS handling

### Advanced Techniques

**1. Multi-Amenity Scoring** (schools + parks + shopping):
```sql
-- Properties near multiple amenities
array_length(overlay_within('schools', buffer($geometry, 1000))) > 0
AND array_length(overlay_within('parks', buffer($geometry, 500))) > 0
AND array_length(overlay_within('shops', buffer($geometry, 800))) > 0
```

**2. Appreciation Potential** (combine demographics):
```sql
-- Areas with improving demographics
"median_income_2023" > "median_income_2020" * 1.1  -- 10% income growth
AND distance(centroid, aggregate('new_developments', 'collect', $geometry)) < 2000
```

**3. Commute Time Analysis** (requires road network):
```
Processing → Network Analysis → Service Area
Origin: Properties
Destination: Employment centers
Time limit: 30 minutes
```

**4. Market Comparison** (price per sqm by neighborhood):
```sql
-- Find properties below neighborhood average
"price" / "area_sqm" < 
  aggregate(
    layer:='all_properties',
    aggregate:='avg',
    expression:="price"/"area_sqm",
    filter:="neighborhood" = attribute(@parent, 'neighborhood')
  ) * 0.9  -- 10% below average
```

**5. Time-Series Tracking** (monitor listing duration):
```sql
-- Properties on market >30 days (motivated sellers)
"days_on_market" > 30
AND "price_reduced" = 1
```

### Further Learning

- 📖 [Spatial Predicates Reference](../reference/cheat-sheets/spatial-predicates.md)
- 📖 [Expression Builder Guide](../user-guide/expression-builder.md)
- 📖 [Filter History & Favorites](../user-guide/filter-history.md)
- 📖 [Field Calculator Deep Dive](https://docs.qgis.org/latest/en/docs/user_manual/working_with_vector/attribute_table.html#using-the-field-calculator)

---

## Summary

✅ **You've learned**:
- Combining attribute and spatial filters
- Distance calculations to nearest features
- Creating value scores from multiple criteria
- Exporting filtered results for analysis
- Managing filter history for different searches

✅ **Key techniques**:
- `BETWEEN` operator for range filtering
- `distance()` function for proximity
- `overlay_within()` for spatial relationships
- Field calculator for derived attributes
- Multi-backend comparison

🎯 **Real-world impact**: This workflow helps real estate professionals make data-driven decisions, investors identify opportunities quickly, and home buyers find properties matching complex criteria that would take days to research manually.

💡 **Pro tip**: Save multiple filter variations as **Favorites** with descriptive names like "Investment: Family Homes Near Schools" or "Budget: Starter Homes Transit Access" to instantly recreate searches.
