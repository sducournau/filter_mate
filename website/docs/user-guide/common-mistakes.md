---
sidebar_position: 8
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Common Mistakes & Solutions

Avoid frequent pitfalls and resolve issues quickly with this troubleshooting guide.

## Overview

This guide documents the most common mistakes users encounter when using FilterMate, along with clear solutions and prevention strategies.

**Quick Navigation**:
- [Empty Filter Results](#1-empty-filter-results)
- [PostgreSQL Backend Unavailable](#2-postgresql-backend-unavailable)
- [Slow Performance](#3-slow-performance-30-seconds)
- [Incorrect Spatial Results](#4-incorrect-spatial-results)
- [Expression Errors](#5-expression-syntax-errors)
- [Export Failures](#6-export-failures)
- [Filter History Lost](#7-filter-history-lost-after-restart)
- [CRS Issues](#8-crs-mismatch-problems)

---

## 1. Empty Filter Results {#1-empty-filter-results}

**Symptom**: Filter returns 0 features, but you expected matches.

### Common Causes

#### Cause A: CRS Mismatch
**Problem**: Layers have different coordinate systems that don't overlap geographically.

**Example**:
```
Layer 1: EPSG:4326 (WGS84) - Global coordinates
Layer 2: EPSG:2154 (Lambert 93) - France only
```

**Solution**:
✅ FilterMate handles CRS reprojection automatically, but verify layers overlap:
1. Right-click each layer → **Zoom to Layer**
2. Check if both layers appear in same geographic area
3. Look for 🔄 reprojection indicator in FilterMate logs

**Prevention**:
- Use layers from same geographic region
- Check layer extent in Properties → Information

---

#### Cause B: Invalid Geometries
**Problem**: Corrupt or self-intersecting geometries prevent spatial operations.

**Symptoms**:
- "GEOS error" in logs
- Inconsistent results
- Some features missing unexpectedly

**Solution**:
✅ Run geometry repair before filtering:
```bash
# In QGIS Processing Toolbox
1. Vector geometry → Fix geometries
2. Input: Your problematic layer
3. Output: layer_fixed
4. Use fixed layer in FilterMate
```

**Quick Check**:
```bash
# Processing Toolbox
Vector geometry → Check validity
```

---

#### Cause C: Buffer Distance Too Small
**Problem**: Buffer zone doesn't reach any features.

**Example**:
```
Buffer: 10 meters
Reality: Nearest feature is 50 meters away
Result: 0 features found
```

**Solution**:
✅ Progressively increase buffer distance:
```
Try: 50m → 100m → 500m → 1000m
```

✅ Test without buffer first:
- Use "Intersects" predicate without buffer
- If this returns results, buffer distance is the issue

---

#### Cause D: Wrong Attribute Values
**Problem**: Filtering for values that don't exist in the data.

**Example**:
```sql
-- Your expression:
city = 'Paris'

-- Actual values in data:
city = 'PARIS' (uppercase)
city = 'Paris, France' (includes country)
```

**Solution**:
✅ Check actual field values first:
1. Right-click layer → **Attribute Table**
2. Look at actual values in the field
3. Adjust expression to match exactly

✅ Use case-insensitive matching:
```sql
-- Instead of:
city = 'Paris'

-- Use:
upper(city) = 'PARIS'
-- or
city ILIKE 'paris'
```

---

#### Cause E: Layers Don't Overlap Geographically
**Problem**: Reference layer and target layer are in different locations.

**Example**:
```
Target: Buildings in New York
Reference: Roads in London
Result: No overlap = 0 results
```

**Solution**:
✅ Verify geographic overlap:
1. Select both layers in Layers Panel
2. Right-click → **Zoom to Layers**
3. Both should appear in same map view

---

### Debug Workflow for Empty Results

**Step 1**: Test with simple expression
```sql
1 = 1  -- Should return ALL features
```
If this fails → Backend or layer issue

**Step 2**: Test attribute filter only
```sql
-- Remove spatial filter
-- Test: population > 0
```
If this works → Spatial configuration issue

**Step 3**: Test spatial filter only
```sql
-- Remove attribute filter
-- Use basic "Intersects" without buffer
```
If this works → Attribute expression issue

**Step 4**: Check logs
```
QGIS → View → Panels → Log Messages → FilterMate
Look for red error messages
```

---

## 2. PostgreSQL Backend Unavailable {#2-postgresql-backend-unavailable}

**Symptom**: Warning message: `PostgreSQL backend unavailable - using fallback`

### Root Cause

**Problem**: `psycopg2` Python package not installed in QGIS Python environment.

**Impact**:
- 10-50× slower performance on large datasets
- No materialized views or server-side processing
- Falls back to Spatialite or OGR backend

---

### Solution: Install psycopg2

<Tabs>
  <TabItem value="windows" label="Windows" default>
    ```bash
    # Method A: OSGeo4W Shell (Recommended)
    # Open OSGeo4W Shell as Administrator
    # Run these commands:
    py3_env
    pip install psycopg2-binary
    
    # Method B: QGIS Python Console
    # QGIS → Plugins → Python Console
    # Run this code:
    import subprocess
    subprocess.check_call(['python', '-m', 'pip', 'install', 'psycopg2-binary'])
    ```
  </TabItem>
  
  <TabItem value="linux" label="Linux">
    ```bash
    # Ubuntu/Debian
    sudo apt-get install python3-psycopg2
    
    # Or via pip
    pip3 install psycopg2-binary
    
    # Verify installation
    python3 -c "import psycopg2; print(psycopg2.__version__)"
    ```
  </TabItem>
  
  <TabItem value="macos" label="macOS">
    ```bash
    # Via pip (QGIS Python)
    /Applications/QGIS.app/Contents/MacOS/bin/pip3 install psycopg2-binary
    
    # Or via Homebrew
    brew install postgresql
    pip3 install psycopg2-binary
    ```
  </TabItem>
</Tabs>

---

### Verification

**Check if psycopg2 is installed**:
```python
# QGIS Python Console
import psycopg2
print(psycopg2.__version__)
# Expected: '2.9.x (dt dec pq3 ext lo64)'
```

**Check FilterMate logs**:
```
✅ Success: "PostgreSQL backend available"
❌ Warning: "psycopg2 not found, using Spatialite"
```

---

### When NOT to Worry

**You can skip PostgreSQL installation if**:
- Dataset has `<10,000` features (Spatialite is fast enough)
- Using OGR layers (Shapefile, GeoPackage) and can't migrate
- Only occasional filtering (performance not critical)
- No PostgreSQL database available

---

## 3. Slow Performance (>30 seconds) {#3-slow-performance-30-seconds}

**Symptom**: Filter operation takes more than 30 seconds.

### Diagnosis

**Check backend in use**:
```
FilterMate panel → Layer info:
Provider: ogr (⚠️ Slowest)
Provider: spatialite (⏱️ Medium)
Provider: postgresql (⚡ Fastest)
```

---

### Solutions by Backend

#### OGR Backend (Shapefile, GeoPackage)

**Problem**: No native spatial indexes, in-memory processing.

**Solution 1**: Migrate to PostgreSQL
```bash
# Best for datasets >50k` features
1. Set up PostgreSQL+PostGIS
2. DB Manager → Import layer
3. Reconnect in QGIS
4. 10-50× speedup
```

**Solution 2**: Migrate to Spatialite
```bash
# Good for datasets 10k-50k features
1. Processing Toolbox → Vector general → Package layers
2. Choose Spatialite format
3. 3-5× speedup vs Shapefile
```

**Solution 3**: Optimize query
```sql
-- Add attribute filter FIRST (reduces spatial query scope)
population > 10000 AND ...spatial query...

-- Instead of:
...spatial query... AND population > 10000
```

---

#### Spatialite Backend

**Problem**: Large dataset (>50k` features).

**Solution**: Migrate to PostgreSQL
- Expected improvement: 5-10× faster
- Sub-second queries on 100k+ features

**Workaround**: Reduce query scope
```sql
-- Pre-filter with bounding box
bbox($geometry, 
     $xmin, $ymin, 
     $xmax, $ymax)
AND ...your filter...
```

---

#### PostgreSQL Backend (Already Fast)

**Problem**: Slow despite using PostgreSQL (rare).

**Possible Causes**:
1. ❌ Missing spatial index
2. ❌ Invalid geometries
3. ❌ Network latency (remote database)

**Solutions**:
```sql
-- 1. Check spatial index exists
SELECT * FROM pg_indexes 
WHERE tablename = 'your_table' 
  AND indexdef LIKE '%GIST%';

-- 2. Create index if missing
CREATE INDEX idx_geom ON your_table USING GIST(geom);

-- 3. Fix geometries
UPDATE your_table SET geom = ST_MakeValid(geom);
```

---

### Performance Benchmarks

| Backend | 10k features | 50k features | 100k features |
|---------|--------------|--------------|---------------|
| PostgreSQL | 0.1s ⚡ | 0.3s ⚡ | 0.8s ⚡ |
| Spatialite | 0.4s ✓ | 4.5s ⏱️ | 18s ⏱️ |
| OGR (GPKG) | 2.1s | 25s ⚠️ | 95s 🐌 |
| OGR (SHP) | 3.8s | 45s 🐌 | 180s 🐌 |

**Recommendation**: Use PostgreSQL for >50k` features.

---

## 4. Incorrect Spatial Results {#4-incorrect-spatial-results}

**Symptom**: Features far from reference geometry are included in results.

### Common Causes

#### Cause A: Buffer Distance in Wrong Units

**Problem**: Using degrees when you need meters (or vice versa).

**Example**:
```
Buffer: 500 (assumed meters)
Layer CRS: EPSG:4326 (degrees!)
Result: 500-degree buffer (~55,000 km!)
```

**Solution**:
✅ FilterMate auto-converts geographic CRS to EPSG:3857 for metric buffers
- Look for 🌍 indicator in logs
- Manual check: Layer Properties → Information → CRS units

✅ Use appropriate CRS:
```
Degrees: EPSG:4326 (WGS84) - Auto-converted ✓
Meters: EPSG:3857 (Web Mercator)
Meters: Local UTM zones (most accurate)
```

---

#### Cause B: Wrong Spatial Predicate

**Problem**: Using "Contains" when you need "Intersects".

**Predicate Meanings**:
```
Intersects: Touch or overlap (most permissive)
Contains: A completely wraps B (strict)
Within: A completely inside B (opposite of Contains)
Crosses: Linear intersection only
```

**Example**:
```
❌ Wrong: Contains
   - Finds parcels that CONTAIN roads (opposite!)
   
✅ Right: Intersects
   - Finds parcels that TOUCH roads
```

**Solution**:
See [Spatial Predicates Reference](../reference/cheat-sheets/spatial-predicates.md) for visual guide.

---

#### Cause C: Reference Layer is Wrong

**Problem**: Selected wrong layer as spatial reference.

**Example**:
```
Goal: Buildings near ROADS
Actual: Reference layer = RIVERS
Result: Wrong features selected
```

**Solution**:
✅ Double-check reference layer dropdown:
- Layer name should match your intent
- Icon shows geometry type (point/line/polygon)

---

### Verification Steps

**Manual Check**:
1. Use QGIS **Measure Tool** (Ctrl+Shift+M)
2. Measure distance from filtered feature to nearest reference feature
3. Distance should be ≤ your buffer setting

**Visual Check**:
1. **Identify Tool** → Click reference feature
2. Right-click → **Zoom to Feature**
3. Look at surrounding filtered features
4. They should form a ring around reference feature (if buffer used)

---

## 5. Expression Syntax Errors {#5-expression-syntax-errors}

**Symptom**: Red ✗ in expression builder with error message.

### Common Syntax Mistakes

#### Missing Quotes Around Text

```sql
❌ Wrong:
city = Paris

✅ Correct:
city = 'Paris'
```

---

#### Case-Sensitive Field Names (Spatialite)

```sql
❌ Wrong (Spatialite):
name = 'test'  -- Field is 'NAME', not 'name'

✅ Correct:
"NAME" = 'test'  -- Double quotes for case-sensitive fields
```

---

#### Using = with NULL

```sql
❌ Wrong:
population = NULL

✅ Correct:
population IS NULL
```

---

#### String Concatenation

```sql
❌ Wrong:
city + ', ' + country

✅ Correct:
city || ', ' || country
```

---

#### Date Comparisons

```sql
❌ Wrong:
date_field > '2024-01-01'  -- String comparison

✅ Correct:
date_field > to_date('2024-01-01')
-- or
year(date_field) = 2024
```

---

### Expression Debugging

**Step 1**: Test in Expression Builder
```
QGIS Layer → Open Attribute Table → 
Field Calculator → Test expression
```

**Step 2**: Use Expression Preview
```
Click "Preview" button to see result on first feature
```

**Step 3**: Simplify Expression
```sql
-- Start simple:
1 = 1  -- Always true

-- Add complexity gradually:
city = 'Paris'
city = 'Paris' AND population > 100000
```

---

## 6. Export Failures {#6-export-failures}

**Symptom**: Export button does nothing or shows error.

### Common Causes

#### Cause A: Permission Denied

**Problem**: Can't write to destination folder.

**Solution**:
```bash
# Windows: Choose user folder
C:\Users\YourName\Documents\

# Linux/macOS: Check permissions
chmod 755 /path/to/output/folder
```

---

#### Cause B: Invalid Characters in Filename

**Problem**: Special characters not allowed by filesystem.

```bash
❌ Wrong:
exports/data:2024.gpkg  -- Colon not allowed (Windows)

✅ Correct:
exports/data_2024.gpkg
```

---

#### Cause C: Target CRS Invalid

**Problem**: Selected CRS doesn't exist or isn't recognized.

**Solution**:
✅ Use common CRS codes:
```
EPSG:4326 - WGS84 (worldwide)
EPSG:3857 - Web Mercator (web maps)
EPSG:2154 - Lambert 93 (France)
```

---

#### Cause D: Layer Name Contains Spaces (PostgreSQL export)

**Problem**: PostgreSQL table names with spaces require quotes.

**Solution**:
```sql
❌ Wrong: my layer name

✅ Correct: my_layer_name
```

---

## 7. Filter History Lost After Restart {#7-filter-history-lost-after-restart}

**Symptom**: Undo/redo history is empty after closing QGIS.

### Expected Behavior

**Filter history is session-based** - it's not saved to the QGIS project file.

**Why**: 
- History can become large (100+ operations)
- May contain sensitive filter criteria
- Performance optimization

---

### Workaround: Use Favorites

**Save important filters**:
1. Apply your filter
2. Click **"Add to Favorites"** button (⭐ icon)
3. Give it a descriptive name
4. Favorites ARE saved to project file

**Recall favorite filters**:
1. Click **"Favorites"** dropdown
2. Select saved filter
3. Click **"Apply"**

---

## 8. CRS Mismatch Problems {#8-crs-mismatch-problems}

**Symptom**: Features appear in wrong location or spatial queries fail.

### Automatic CRS Handling

**FilterMate automatically reprojects layers** during spatial operations.

**You'll see**:
```
🔄 Reprojecting layer from EPSG:4326 to EPSG:3857
```

**This is NORMAL and expected** - no action needed.

---

### When CRS Causes Issues

#### Issue: Geographic CRS Used for Buffers

**Problem**: Buffer distance interpreted as degrees instead of meters.

**FilterMate Solution**:
✅ Automatically converts EPSG:4326 → EPSG:3857 for metric operations
- 🌍 indicator appears in logs
- No manual intervention needed

**Manual Override** (if needed):
1. Right-click layer → **Export** → **Save Features As**
2. Set CRS to local projected system (UTM, State Plane, etc.)
3. Use exported layer in FilterMate

---

#### Issue: Layer Shows Wrong Location

**Problem**: Layer assigned wrong CRS.

**Symptoms**:
- Layer appears far from expected location
- Might be on opposite side of world
- Jumps to 0°,0° (Gulf of Guinea)

**Solution**:
```bash
# Fix layer CRS
1. Right-click layer → Set Layer CRS
2. Select correct CRS (check data documentation)
3. Don't use "Set Project CRS from Layer" - fixes display only
```

**Identify Correct CRS**:
- Check metadata file (.xml, .prj, .qmd)
- Look at coordinate values in attribute table
  - Large numbers (e.g., 500,000) → Projected CRS
  - Small numbers (-180 to 180) → Geographic CRS
- Google the data source for CRS information

---

## Prevention Checklist

Before filtering, verify:

### Data Quality
- [ ] Layers load and display correctly
- [ ] Geometries are valid (run Check Geometries)
- [ ] Attribute table has expected values
- [ ] Layers overlap geographically

### Configuration
- [ ] Correct target layer selected
- [ ] Correct reference layer (for spatial queries)
- [ ] Expression shows green ✓ checkmark
- [ ] Buffer distance and units appropriate
- [ ] Spatial predicate matches intent

### Performance
- [ ] Backend type is appropriate for dataset size
- [ ] psycopg2 installed if using PostgreSQL
- [ ] Spatial indexes exist (PostgreSQL)

---

## Getting Help

### Self-Service Resources

1. **Check Logs**: QGIS → View → Panels → Log Messages → FilterMate
2. **Read Error Message**: Often tells you exactly what's wrong
3. **Search Documentation**: Use search bar (Ctrl+K)
4. **Try Simplified Version**: Remove complexity to isolate issue

### Community Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/sducournau/filter_mate/issues)
- 💬 **Questions**: [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions)
- 📧 **Contact**: Include QGIS version, FilterMate version, and error logs

---

## Summary

**Most Common Mistakes**:
1. Empty results → Check attribute values and buffer distance
2. PostgreSQL unavailable → Install psycopg2
3. Slow performance → Use PostgreSQL for large datasets
4. Wrong spatial results → Verify buffer units and predicate
5. Expression errors → Check syntax and field names

**Key Takeaways**:
- FilterMate handles CRS automatically (look for indicators)
- Always test with simplified expressions first
- Check logs for detailed error messages
- PostgreSQL provides best performance for >50k` features
- Filter history is session-based (use Favorites for persistence)

---

**Still stuck?** Check the [Troubleshooting Guide](../advanced/troubleshooting.md) or ask on [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions).
