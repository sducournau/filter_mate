---
sidebar_position: 2
---

# Why FilterMate?

Understand when to use FilterMate vs native QGIS tools for your filtering workflows.

## Quick Answer

**Use FilterMate when**:
- You need **fast, repeatable** filtering workflows
- Working with **large datasets** (`>50`k` features)
- Combining **attribute + spatial** filters regularly
- You want **undo/redo** for filter operations
- **Exporting filtered data** frequently
- Need **performance optimization** via backends

**Use QGIS Native when**:
- Simple one-time selections
- Learning basic GIS concepts
- No plugin installation allowed
- Very specific processing tools needed

---

## Feature Comparison

### Filtering Operations

| Task | QGIS Native | FilterMate | Winner |
|------|-------------|------------|--------|
| **Simple attribute filter** | Layer Properties → Source → Query Builder | Expression builder in panel | 🤝 Equal |
| **Quick map selection** | Select by Expression tool | EXPLORING tab | 🤝 Equal |
| **Complex spatial query** | Processing Toolbox (3-5 steps) | Single FILTERING tab operation | ⭐ **FilterMate** |
| **Multi-layer filtering** | Repeat process for each layer | Multi-select layers, apply once | ⭐ **FilterMate** |
| **Combined attribute + spatial** | Separate tools, manual combining | Integrated interface | ⭐ **FilterMate** |
| **Buffer + filter** | Buffer tool → Select by Location → Manual | Buffer setting + apply filter | ⭐ **FilterMate** |

**FilterMate Advantage**: Integrated workflow reduces 5-10 manual steps to 1 operation.

---

### Performance

| Scenario | QGIS Native | FilterMate | Improvement |
|----------|-------------|------------|-------------|
| **Small dataset** (`<10`k` features) | 2-5 seconds | 1-3 seconds | 1.5× |
| **Medium dataset** (10-50k features) | 15-45 seconds | 2-8 seconds (Spatialite) | **5-10× faster** |
| **Large dataset** (`>50`k` features) | 60-300 seconds | 1-5 seconds (PostgreSQL) | **20-50× faster** |
| **Huge dataset** (`>500`k` features) | 5-30+ minutes ⚠️ | 3-10 seconds (PostgreSQL) | **100-500× faster** |

**Key Difference**: FilterMate leverages database backends (PostgreSQL, Spatialite) for server-side processing, while QGIS native tools often use in-memory processing.

---

### Workflow Efficiency

| Task | QGIS Native Steps | FilterMate Steps | Time Saved |
|------|-------------------|------------------|------------|
| **Attribute filter** | 3 clicks (Layer → Properties → Query) | 2 clicks (Select layer → Apply) | ~10 seconds |
| **Spatial filter** | 5 steps (Buffer → Select by Location → Extract → Style) | 1 step (Set buffer → Apply) | **2-5 minutes** |
| **Export filtered** | 4 clicks (Right-click → Export → Configure → Save) | 2 clicks (EXPORTING tab → Export) | **30-60 seconds** |
| **Undo filter** | Manual (reload layer or clear selection) | 1 click (Undo button) | **1-2 minutes** |
| **Repeat filter** | Re-enter all settings manually | 1 click (Load from Favorites) | **3-10 minutes** |

**Real-World Impact**: 
- **Daily users**: Save 20-60 minutes per day
- **Weekly users**: Save 1-3 hours per week
- **Monthly users**: Moderate savings, but quality-of-life improvements

---

## Use Case Analysis

### Case 1: One-Time Simple Selection

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

**Task**: Select cities with population > 100,000

<Tabs>
  <TabItem value="qgis" label="QGIS Native" default>
    ```
    1. Right-click layer → Filter
    2. Enter: population > 100000
    3. Click OK
    
    Time: 15 seconds
    Complexity: Low
    ```
    **Verdict**: QGIS native is fine ✓
  </TabItem>
  
  <TabItem value="filtermate" label="FilterMate">
    ```
    1. Select layer in FilterMate
    2. Enter: population > 100000
    3. Click Apply Filter
    
    Time: 12 seconds
    Complexity: Low
    ```
    **Verdict**: FilterMate slightly faster, but not significant
  </TabItem>
</Tabs>

**Winner**: 🤝 **Equal** - Either tool works well for simple one-time filters.

---

### Case 2: Complex Spatial Query

**Task**: Find residential parcels within 500m of subway stations

<Tabs>
  <TabItem value="qgis" label="QGIS Native" default>
    ```
    1. Processing → Buffer
       - Input: subway_stations
       - Distance: 500
       - Output: stations_buffer
    
    2. Processing → Select by Location
       - Select features from: parcels
       - Where features: intersect
       - Reference: stations_buffer
    
    3. Processing → Extract Selected Features
       - Input: parcels
       - Output: parcels_filtered
    
    4. Right-click parcels_filtered → Filter
       - Enter: land_use = 'residential'
    
    5. Style result layer
    
    Time: 3-5 minutes
    Steps: 5 separate operations
    Complexity: High
    ```
    **Verdict**: Tedious, error-prone, not reusable
  </TabItem>
  
  <TabItem value="filtermate" label="FilterMate">
    ```
    1. Select parcels layer
    2. Expression: land_use = 'residential'
    3. Reference layer: subway_stations
    4. Buffer: 500 meters
    5. Predicate: Intersects
    6. Click Apply Filter
    
    Time: 30-60 seconds
    Steps: 1 integrated operation
    Complexity: Low
    ```
    **Verdict**: Fast, simple, saveable as Favorite
  </TabItem>
</Tabs>

**Winner**: ⭐ **FilterMate** - 5× faster, 80% fewer steps, repeatable workflow.

---

### Case 3: Multi-Layer Analysis

**Task**: Filter buildings, parcels, and roads near river (3 layers)

<Tabs>
  <TabItem value="qgis" label="QGIS Native" default>
    ```
    1. Buffer river layer
    2. Select by Location for buildings → Extract
    3. Select by Location for parcels → Extract
    4. Select by Location for roads → Extract
    5. Style 3 result layers
    6. Manage 6 layers total (original + filtered)
    
    Time: 8-12 minutes
    Steps: 15+ operations
    Complexity: Very High
    ```
    **Verdict**: Time-consuming, clutters layer panel
  </TabItem>
  
  <TabItem value="filtermate" label="FilterMate">
    ```
    1. Multi-select: buildings, parcels, roads
    2. Reference layer: river
    3. Buffer: 100 meters
    4. Click Apply Filter
    
    All 3 layers filtered simultaneously!
    
    Time: 1-2 minutes
    Steps: 4 clicks
    Complexity: Low
    ```
    **Verdict**: Dramatically simpler
  </TabItem>
</Tabs>

**Winner**: ⭐⭐ **FilterMate** - 5-10× faster, maintains clean workspace.

---

### Case 4: Large Dataset Performance

**Task**: Filter 150,000 parcels by attribute and proximity

<Tabs>
  <TabItem value="qgis" label="QGIS Native" default>
    ```
    Processing Tools on 150k features:
    - Buffer: 45-90 seconds
    - Select by Location: 120-180 seconds
    - Extract: 30-60 seconds
    - Attribute filter: 15-30 seconds
    
    Total Time: 3.5-6 minutes
    Memory Usage: High (in-memory processing)
    ```
    **Verdict**: Slow, may crash on large datasets
  </TabItem>
  
  <TabItem value="filtermate" label="FilterMate (PostgreSQL)">
    ```
    Server-side processing with spatial indexes:
    - All operations combined: 0.5-2 seconds
    
    Total Time: 0.5-2 seconds
    Memory Usage: Low (database handles it)
    ```
    **Verdict**: 100-500× faster!
  </TabItem>
</Tabs>

**Winner**: ⭐⭐⭐ **FilterMate** - Transforms impossible into instant.

---

## Unique FilterMate Features

### 1. Filter History & Undo/Redo

**QGIS Native**: No built-in filter history
- To "undo" a filter: Manually remove filter or reload layer
- No way to step back through filter changes
- Lost work if you make a mistake

**FilterMate**: Full history management
- Undo button (↩️) - Go back to previous filter
- Redo button (↪️) - Go forward in history
- History persists during session
- Up to 100 operations tracked

**Real-World Value**: 
- Experimental filtering without fear
- Compare multiple filter variations
- Quick recovery from mistakes

---

### 2. Filter Favorites

**QGIS Native**: Must manually re-enter filters each time
- No way to save commonly-used filters
- Prone to typos when re-typing
- Difficult to share filters with colleagues

**FilterMate**: Save & load filters as Favorites
- ⭐ Click to save current filter
- Load from dropdown menu
- Saved with project file
- Shareable across team

**Real-World Value**:
- Standardized filtering for teams
- Instant access to complex filters
- Reduced errors from manual re-entry

---

### 3. Backend Optimization

**QGIS Native**: Uses Processing framework
- Always in-memory or temporary files
- No spatial index optimization
- Same speed regardless of data source

**FilterMate**: Intelligent backend selection
- **PostgreSQL**: Server-side processing, materialized views
- **Spatialite**: File-based with spatial indexes
- **OGR**: Fallback for compatibility
- Automatic selection based on layer type

**Real-World Value**:
- 10-50× performance improvement (PostgreSQL)
- No workflow changes needed
- Transparent optimization

**See**: [Backend Comparison](../backends/choosing-backend)

---

### 4. Integrated Export Workflow

**QGIS Native**: Multi-step export process
```
1. Apply filter
2. Right-click layer → Export → Save Features As
3. Configure format
4. Set CRS transformation
5. Choose fields to export
6. Set filename
7. Click OK
```

**FilterMate**: One-click export tab
```
1. Switch to EXPORTING tab
2. Select format (GPKG, SHP, GeoJSON, PostGIS, etc.)
3. Optional: Transform CRS
4. Click Export

Filtered state automatically applied!
```

**Real-World Value**:
- 70% fewer clicks
- Less error-prone
- Batch export multiple layers
- Style export (QML/SLD) included

---

### 5. Multi-Layer Operations

**QGIS Native**: Process one layer at a time
- Repeat entire workflow for each layer
- Manage multiple result layers
- Easy to miss a layer or apply inconsistent filters

**FilterMate**: Multi-select checkbox interface
- Check all layers to filter
- Apply filter once → affects all
- Consistent parameters across layers
- Clean workspace (original layers filtered, not duplicated)

**Real-World Value**:
- 3-10× faster for multi-layer workflows
- Consistency guaranteed
- Cleaner layer panel

---

### 6. Visual Feedback & Warnings

**QGIS Native**: Minimal feedback
- Processing may run without progress indicator
- No performance warnings
- Errors often cryptic

**FilterMate**: Comprehensive feedback system
- ✅ Success messages with feature counts
- ⚠️ Performance warnings for large datasets
- 🔄 CRS reprojection indicators
- 🌍 Geographic coordinate handling notices
- ⚡ Backend performance indicators
- Detailed error messages with context

**Real-World Value**:
- Understand what's happening
- Prevent performance issues
- Troubleshoot problems faster

---

## When QGIS Native Is Better

### Processing Toolbox Advantages

**QGIS Native wins when you need**:

1. **Specialized Algorithms**
   - Complex topology operations
   - Advanced geometric transformations
   - Statistical analysis tools
   - Raster-vector integration

2. **Batch Processing**
   - Multiple unrelated operations in sequence
   - Processing across many disconnected files
   - Automated workflows via Model Builder

3. **Graph Algorithms**
   - Network analysis (shortest path, service areas)
   - Requires pgRouting (PostgreSQL) or QGIS tools

4. **Raster Operations**
   - FilterMate only works with vector data
   - Use Processing for raster analysis

---

### Learning & Education

**QGIS Native better for**:
- Understanding GIS concepts step-by-step
- Learning individual tool functions
- Academic/teaching environments
- Certification exam preparation

**FilterMate better for**:
- Production workflows
- Time-critical projects
- Repetitive tasks
- Real-world GIS work

---

## Migration Path

### Starting with QGIS Native?

**Try FilterMate when**:
1. ✅ You've done the same filter 3+ times
2. ✅ Filtering takes `>2` minutes manually
3. ✅ Working with `>50`k` features
4. ✅ Combining attribute + spatial filters
5. ✅ Need undo/redo capability

**Transition Strategy**:
```
Week 1: Learn FilterMate basics (simple attribute filters)
Week 2: Try geometric filtering (spatial predicates)
Week 3: Use EXPORTING tab for filtered exports
Week 4: Save Favorites for common filters
Week 5+: Primary tool, QGIS native for specialized tasks
```

---

### Already Using FilterMate?

**When to use QGIS Native**:
- Specialized processing not in FilterMate
- Model Builder automation
- Learning/teaching specific concepts
- Troubleshooting (compare results)

**Best Practice**: 
Use **FilterMate for 80% of filtering tasks**, QGIS native for specialized 20%.

---

## Performance Comparison: Real Numbers

### Test Dataset: Urban Parcel Analysis

**Data**:
- 125,000 parcel polygons
- 5,000 road lines
- Task: Find residential parcels within 200m of main roads

**Hardware**: Standard laptop (16GB RAM, SSD)

| Method | Time | Memory | Steps | Result Layers |
|--------|------|--------|-------|---------------|
| **QGIS Processing (OGR)** | 287 seconds | 4.2 GB | 5 | 3 layers |
| **QGIS Processing (PostGIS)** | 12 seconds | 0.5 GB | 4 | 2 layers |
| **FilterMate (OGR)** | 45 seconds | 1.8 GB | 1 | 1 layer (filtered) |
| **FilterMate (Spatialite)** | 8.3 seconds | 0.6 GB | 1 | 1 layer (filtered) |
| **FilterMate (PostgreSQL)** | 1.2 seconds | 0.3 GB | 1 | 1 layer (filtered) |

**Key Insights**:
- FilterMate (PostgreSQL): **240× faster** than QGIS Processing (OGR)
- FilterMate (Spatialite): **35× faster** than QGIS Processing (OGR)
- Even FilterMate (OGR): **6× faster** due to optimized workflow

---

## Cost-Benefit Analysis

### Time Investment

**Learning Curve**:
- **QGIS Processing**: 2-4 weeks to master tools
- **FilterMate**: 2-4 hours to become proficient
- **FilterMate Advanced**: 1-2 days for optimization

**Setup Time**:
- **QGIS Processing**: Built-in (0 minutes)
- **FilterMate**: Plugin install (2 minutes)
- **FilterMate + PostgreSQL**: Full setup (30-60 minutes)

---

### Time Savings

**Daily User** (10 filters/day):
- Manual time: ~60 minutes
- FilterMate time: ~15 minutes
- **Savings: 45 minutes/day = 180 hours/year**

**Weekly User** (20 filters/week):
- Manual time: ~120 minutes/week
- FilterMate time: ~30 minutes/week
- **Savings: 90 minutes/week = 75 hours/year**

**Monthly User** (10 filters/month):
- Manual time: ~60 minutes/month
- FilterMate time: ~15 minutes/month
- **Savings: 45 minutes/month = 9 hours/year**

---

### Break-Even Analysis

**FilterMate installation** (2 minutes):
- Break-even after: **1-2 filters**

**PostgreSQL setup** (60 minutes):
- Break-even after: **15-30 filters** (large datasets)
- Or: **2-3 hours** of filtering work

**Return on Investment**: 
- FilterMate: **Immediate** (first use)
- PostgreSQL: **Within first week** for power users

---

## Summary Recommendations

### Use FilterMate When...

✅ **Performance matters**
- Large datasets (`>50`k` features)
- Complex spatial queries
- Repetitive workflows

✅ **Efficiency matters**
- Multi-layer operations
- Combined attribute + spatial filters
- Frequent filtered exports

✅ **Convenience matters**
- Need undo/redo capability
- Filter history with session tracking
- Prefer integrated interface

---

### Use QGIS Native When...

✅ **Specialized tools needed**
- Raster operations
- Advanced topology tools
- Network analysis
- Statistical processing

✅ **Learning/Teaching**
- Understanding individual steps
- Academic environments
- Demonstrating concepts

✅ **One-time simple tasks**
- Quick map selections
- Single-layer attribute filters
- Exploring unfamiliar data

---

## Conclusion

**FilterMate complements QGIS native tools**, not replaces them.

**Think of it as**:
- **Power drill** (FilterMate) vs **Hand screwdriver** (QGIS native)
- Both have their place
- Power drill saves time on most tasks
- Hand screwdriver better for delicate work

**Recommended Workflow**:
```
80% of filtering → FilterMate (speed & efficiency)
20% specialized tasks → QGIS Processing (flexibility)
```

**Bottom Line**: 
Install FilterMate. Use it for daily filtering. Fall back to QGIS native for specialized tasks. **Best of both worlds.**

---

## Next Steps

1. **Install FilterMate**: [Installation Guide](../installation)
2. **Quick Start**: [5-minute tutorial](../getting-started/quick-start)
3. **Learn Workflows**: [Real-world examples](../workflows/)
4. **Optimize Performance**: [Backend setup](../backends/choosing-backend)

---

**Questions?** Ask on [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions)
