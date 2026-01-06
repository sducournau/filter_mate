# Auto-Optimization System (v2.7.0)

## Overview

FilterMate v2.7.0 introduces an **intelligent auto-optimization system** that automatically detects layer characteristics and recommends/applies performance optimizations. This system analyzes:

- **Backend type**: Local files, local databases, remote databases, remote services (WFS, ArcGIS)
- **Feature count**: Small, medium, large, very large datasets
- **Geometry complexity**: Simple points vs complex polygons with many vertices
- **Spatial predicates**: Type of spatial operation being performed

## Key Optimizations

### 1. Automatic Centroid for Distant Layers 🎯

**Problem**: Filtering WFS or ArcGIS Feature Service layers with polygon geometries requires transferring the full geometry over the network, which is extremely slow for large datasets.

**Solution**: Automatically use `ST_Centroid()` to reduce each polygon to a single point before spatial operations.

**Benefits**:

- **~90% reduction** in network data transfer
- **5-10x faster** queries on remote polygon layers
- Transparent to user - applied automatically

**When it's applied**:

- Remote layers (WFS, ArcGIS, remote PostgreSQL) with > 5,000 features
- Large local layers (> 50,000 features) with complex geometries (> 50 avg vertices)
- Very large layers (> 500,000 features) regardless of complexity

### 2. Geometry Simplification (Optional) 📐

**Problem**: Very complex geometries with thousands of vertices slow down spatial operations.

**Solution**: Automatically simplify geometries using Douglas-Peucker algorithm.

**Benefits**:

- 2-3x faster spatial queries
- Reduced memory usage

**Note**: This is **disabled by default** because it's a **lossy** operation that reduces precision.

### 3. Strategy Selection 📊

Automatically selects the optimal filtering strategy:

| Dataset Size | Strategy           | Description                                |
| ------------ | ------------------ | ------------------------------------------ |
| < 10,000     | Direct             | Simple setSubsetString                     |
| 10k - 50k    | Attribute-First    | Apply attribute filter before spatial      |
| 50k - 200k   | BBox Pre-Filter    | Bounding box elimination before exact test |
| > 200,000    | Progressive Chunks | Process in memory-efficient chunks         |

## Configuration

Configure auto-optimization in `config.json` under `APP > OPTIONS > AUTO_OPTIMIZATION`:

```json
{
  "AUTO_OPTIMIZATION": {
    "enabled": true,
    "auto_centroid_for_distant": true,
    "centroid_threshold_distant": 5000,
    "centroid_threshold_local": 50000,
    "auto_simplify_geometry": false,
    "auto_strategy_selection": true,
    "show_optimization_hints": true
  }
}
```

### Options

| Option                       | Default | Description                                |
| ---------------------------- | ------- | ------------------------------------------ |
| `enabled`                    | `true`  | Master switch for auto-optimization        |
| `auto_centroid_for_distant`  | `true`  | Auto-enable centroid for remote layers     |
| `centroid_threshold_distant` | `5000`  | Feature count threshold for distant layers |
| `centroid_threshold_local`   | `50000` | Feature count threshold for local layers   |
| `auto_simplify_geometry`     | `false` | Auto-simplify complex geometries (lossy)   |
| `auto_strategy_selection`    | `true`  | Auto-select optimal filtering strategy     |
| `show_optimization_hints`    | `true`  | Show hints in message bar                  |

## API Usage

### Python API

```python
from filter_mate.modules.backends import (
    get_optimization_plan,
    should_use_centroids,
    analyze_layer_for_optimization
)

# Get full optimization plan
plan = get_optimization_plan(
    target_layer=my_layer,
    source_layer=selection_layer,
    predicates={'Intersects': True}
)

if plan:
    print(f"Recommendations: {len(plan.recommendations)}")
    print(f"Use centroids: {plan.final_use_centroids}")
    print(f"Expected speedup: {plan.estimated_total_speedup:.1f}x")

# Quick check for centroid usage
use_centroids = should_use_centroids(my_distant_layer)

# Analyze a layer
info = analyze_layer_for_optimization(my_layer)
print(f"Layer type: {info['location_type']}")  # 'remote_service', 'local_file', etc.
print(f"Features: {info['feature_count']}")
print(f"Is distant: {info['is_distant']}")
```

### Layer Types

The system classifies layers into four location types:

| Type              | Examples                                      | Centroid Threshold |
| ----------------- | --------------------------------------------- | ------------------ |
| `remote_service`  | WFS, ArcGIS Feature Service, OGC API Features | 5,000              |
| `remote_database` | Remote PostgreSQL/PostGIS                     | 5,000              |
| `local_database`  | Local PostgreSQL, Spatialite, GeoPackage      | 50,000             |
| `local_file`      | Shapefile, GeoJSON, CSV                       | 50,000             |

## Logging

The auto-optimizer logs its decisions at INFO level:

```
🔧 Auto-Optimization Plan for communes_wfs:
   📊 Features: 35,000
   ☁️ Type: remote_service
   ⚙️ Provider: ogr
   📐 Complexity: 15.2x
   💡 Recommendations (1):
      ✅ use_centroid: ~5.0x speedup - distant layer with 35,000 features
   🎯 CENTROID MODE ENABLED
   🚀 Estimated total speedup: 5.0x
```

## Performance Benchmarks

| Scenario                        | Without Optimization | With Optimization | Speedup |
| ------------------------------- | -------------------- | ----------------- | ------- |
| WFS layer (50k polygons)        | 45 seconds           | 8 seconds         | 5.6x    |
| Remote PostgreSQL (100k)        | 30 seconds           | 6 seconds         | 5.0x    |
| Local GeoPackage (200k complex) | 15 seconds           | 8 seconds         | 1.9x    |

## Limitations

1. **Centroid changes spatial semantics**: Using centroids for polygons means "polygon whose center is in selection" rather than "polygon that intersects selection". For most use cases this is acceptable, but for precise boundary operations it may not be suitable.

2. **Simplification is lossy**: Geometry simplification reduces vertex count and may change topology. Disabled by default.

3. **Auto-detection may be wrong**: The heuristics work well for common cases but may not be optimal for all scenarios. Users can always override with explicit settings.

## Disabling Auto-Optimization

To disable auto-optimization entirely:

```json
{
  "AUTO_OPTIMIZATION": {
    "enabled": false
  }
}
```

Or use the UI checkbox "Use centroids for distant layers" to explicitly control centroid usage per operation.

## User Interface

### Backend Indicator Menu

The backend indicator (🐘, 📦, 📁) in the FilterMate header now includes an **Optimization Settings** submenu:

1. **Click on the backend indicator** to open the menu
2. Select **🔧 Optimization Settings** to access:
   - ✓ **Enable auto-optimization**: Master toggle for the feature
   - ✓ **Auto-centroid for distant layers**: Automatically suggest centroids for WFS/ArcGIS layers
   - ✓ **Ask before applying optimizations**: Show confirmation dialog (recommended)
   - **📊 Analyze current layer**: View optimization recommendations for the selected layer
   - **⚙️ Advanced settings...**: Open detailed configuration dialog

### Confirmation Dialog

When filtering with auto-optimization enabled, a confirmation dialog appears showing:

- **Layer information**: Name, feature count, type (remote/local)
- **Recommended optimizations**: With estimated speedup factors
- **Checkboxes** to accept/reject each optimization individually
- **Remember my choices**: Skip confirmation for similar layers in this session

**v2.7.2 Improvement**: When user accepts centroid optimizations in the dialog, only the "Use centroids for distant layers" checkbox is automatically enabled. The "Use centroids for source layer" checkbox is **NOT** automatically enabled because the source layer geometry must be preserved for accurate spatial intersection operations. This is particularly important when the source layer is a polygon used for intersection with distant layers - using centroids would give geometrically incorrect results.

**v2.7.1 Improvement**: UI checkboxes are automatically updated to reflect the user's optimization choices, ensuring visual consistency between the dialog selections and the main FilterMate interface.

### Settings Dialog

The advanced settings dialog provides:

- **Master enable/disable** for auto-optimization
- **Centroid threshold** configuration (default: 5,000 for remote, 50,000 for local)
- **Strategy selection** options
- **Geometry simplification** toggle (⚠️ lossy operation)
- **Confirmation behavior** settings

## Migration from v2.6.x

If upgrading from v2.6.x, auto-optimization is **enabled by default** with conservative settings:

- Confirmation dialogs are shown before applying optimizations
- Only centroid optimization is auto-suggested
- Geometry simplification remains off

No action is required. Existing projects will benefit from optimization hints without changes.
