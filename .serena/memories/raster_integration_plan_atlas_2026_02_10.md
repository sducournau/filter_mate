# Raster-Vector Integration Plan (Atlas Analysis - 2026-02-10)

## Actual Raster State on `main` (Audited 2026-02-10)

### What EXISTS on `main`:
- `RasterLayer = 1` enum in `filter_mate_dockwidget.py:56` (layer type detection only)
- `QgsRasterLayer` type hint in `core/geometry/crs_utils.py:164`
- WCS provider mentioned in `infrastructure/constants.py:35`

### What does NOT EXIST on `main`:
- NO raster files: no `raster_pixel_picker_tool.py`, no `raster_exploring_manager.py`
- NO `ui/tools/` directory
- NO `core/tasks/handlers/` directory
- NO `core/domain/raster_filter_criteria.py`
- NO raster services (`raster_filter_service.py`, etc.)
- NO raster widgets in `.ui` file (no histogram, no band combobox, no min/max spinboxes)
- NO `RasterExploringManager` in `ui/managers/`
- NO raster tool buttons

### What exists on DEV BRANCHES ONLY (not merged):
- Branch `fix/widget-visibility-and-styles-2026-02-02` had raster UI code (stale, never merged)

---

## Atlas Recommendations (5 Features, Prioritized)

### Priority Map

| # | Feature | Effort | Impact | Differentiation | UI Reuse |
|---|---------|--------|--------|-----------------|----------|
| P1-bis | Raster Value Sampling | **S** (3-5d) | HIGH | Strong | 95% |
| P1 | Zonal Stats as Filter | M (2-3w) | VERY HIGH | **UNIQUE** | 80% |
| P2 | Raster-Driven Highlight | M (1-2w) | HIGH | **UNIQUE** | 70% |
| P3 | Raster Clip by Vector | M (2w) | MED-HIGH | Strong | 60% |
| P4 | Multi-Band Composite | L (3-4w) | MED | Strong | 50% |

### P1-bis: Raster Value Sampling (QUICK WIN - Start here)

**What**: Sample raster value at each vector feature centroid, filter by predicate.
**How**: `QgsRasterLayer.dataProvider().sample(QgsPointXY, band)` in a loop + existing predicate.
**Use cases**: Altitude MNT per building, NDVI per parcel, temperature per zone.
**Key detail**: Use `pointOnSurface()` not `centroid()` for concave polygons.
**Creates**: `RasterFilterService` foundation in hexagonal architecture.

### P1: Zonal Stats as Filter (DIFFERENTIATOR)

**What**: Filter vector features by raster statistics under their geometry.
"Show all buildings where mean altitude > 500m"
**How**: `QgsZonalStatistics` (native QGIS) or GDAL for stats per feature → filter by predicate.
**Critical**: QgsZonalStatistics modifies layer in-place → use temp memory layer or calculate externally.
**Unique**: No QGIS plugin does interactive zonal-stats-as-filter with undo/redo.

### P2: Raster-Driven Selection Highlighting

**What**: Real-time highlight of vector features as user adjusts raster range sliders.
**How**: Debounce (300ms) on range change → sample visible features → `layer.selectByIds()`.
**MVP**: Combine with P1-bis (sampling at centroid) instead of full polygonization.

### P3: Raster Clip by Vector (pairs with EPIC-4 Export)

**What**: Export raster clipped by filtered vector features.
**How**: `gdal.Warp()` with `cutlineDSName` or `QgsProcessing` `gdal:cliprasterbymasklayer`.
**Bundle**: Deliver with EPIC-4 Raster Export UI.

### P4: Multi-Band Composite Filtering (Medium-term)

**What**: Filter on multiple bands simultaneously with AND/OR operators.
**How**: Multiple `RasterFilterCriteria` + logical combination → composite numpy mask.
**Reuse**: `CombinationStrategy(Enum)` from `core/filter/filter_chain.py`.

---

## Architecture Target (New files only, minimal modification to existing)

```
core/
  services/
    raster_filter_service.py          # NEW - orchestration
  domain/
    raster_filter_criteria.py         # NEW - frozen dataclass
  tasks/
    handlers/
      raster_handler.py               # NEW - follows postgresql_handler.py pattern
infrastructure/
  raster/
    sampling.py                       # NEW - provider.sample() wrapper
    zonal_stats.py                    # NEW - QgsZonalStatistics wrapper
    masking.py                        # NEW - polygonization, clip
```

Existing files to modify (wiring only):
- `filter_mate_app.py` - register raster services
- `filter_mate_dockwidget.py` - add minimal UI (1 button "Apply to vector")

---

## Sequencing

```
v5.5 (March 2026):
  [1] Raster Value Sampling          -- 5 days   -- Quick Win / foundation
  [2] EPIC-4 Raster Export + Clip    -- 2 weeks  -- Planned

v5.6 (April 2026):
  [3] Zonal Stats as Filter          -- 3 weeks  -- Differentiator
  [4] Raster-Driven Highlight        -- 1 week   -- UX Premium

v6.0 (Q2-Q3 2026):
  [5] Multi-Band Composite           -- 4 weeks  -- If demand confirmed
```

---

## Key Technical Pitfalls

1. **Thread safety**: QgsRasterLayer NOT thread-safe → store URI in `__init__`, recreate in `run()`
2. **CRS mismatch**: Always reproject vector geometries to raster CRS before sampling
3. **Memory on large rasters**: Stream by tiles above configurable threshold
4. **Centroid trap**: Use `pointOnSurface()` not `centroid()` for concave polygons
5. **QgsZonalStatistics**: Writes columns in-place → use temp memory layer
6. **Don't recreate Raster Calculator**: Resist feature creep, stay focused on filtering
7. **UI minimalism**: Add ONE widget first ("Apply to vector"), observe user reaction

## Decision: Branch Strategy

Fresh implementation following Atlas plan on `main` (dev branch code is stale and would require significant adaptation).
