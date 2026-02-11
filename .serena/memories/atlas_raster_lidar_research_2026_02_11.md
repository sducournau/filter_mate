# Atlas Tech Watch — Raster & LiDAR Research (2026-02-11)

## Executive Summary
- **Raster**: APIs matures (QGIS 3.22+), Zonal Stats as Filter = ocean bleu, aucun concurrent
- **LiDAR/Point Cloud**: setSubsetString() depuis QGIS 3.26, même pattern que vectoriel, COPC = format roi
- **Aucun plugin QGIS** ne fait du filtrage interactif raster ou point cloud

## Raster Key Findings

### APIs critiques
- `provider.sample(point, band)` — sampling ponctuel (<1ms/appel)
- `provider.block(band, extent, w, h)` — lecture bloc (10-100x plus rapide pour batch)
- `QgsRasterTransparency` — highlight dynamique (masquer pixels hors filtre)
- `QgsRasterBandStats` — statistiques par bande

### Zonal Stats Recommendation
- Implementation manuelle recommandée (pas QgsZonalStatistics qui modifie la couche in-place)
- Pattern: charger un seul bloc couvrant l'extent, sampler en mémoire avec numpy
- Avec numpy: 50-200x plus rapide que pixel-by-pixel Python

### Performance Thresholds
- sample() x10000 points: ~100ms (acceptable interactif)
- block() + numpy zonal stats 100 polygones sur 1Go raster: ~8s
- COG réduit I/O de 95%+ sur gros fichiers

## Point Cloud Key Findings

### API disponible (QGIS 3.26+)
- `layer.setSubsetString("Classification = 2")` — FONCTIONNE, même pattern que vectoriel
- `layer.setSubsetString("ReturnNumber = 1 AND Intensity > 200")` — combinaisons supportées
- `layer.setSubsetString("Z > 50 AND Z < 150")` — filtrage élévation
- Attributs: X, Y, Z, Classification, Intensity, ReturnNumber, NumberOfReturns, RGB, NIR, GpsTime

### Limitations
- Pas d'accès données brutes point par point en PyQGIS (utiliser PDAL)
- Pas de clip polygonal via setSubsetString (PDAL Processing depuis 3.32)
- QgsPointCloudBlock partiellement exposé en Python

### COPC (Cloud-Optimized Point Cloud)
- Fichier LAZ unique avec octree interne
- Accès spatial direct, LOD natif, HTTP range requests
- Support QGIS natif depuis 3.26 (provider "copc")
- IGN LiDAR HD distribué en COPC

### ASPRS Classification Codes
- 2: Ground, 3-5: Vegetation (Low/Med/High), 6: Building, 7: Noise, 9: Water, 11: Road

## Architecture Extension

### Raster (5 nouveaux fichiers)
- core/services/raster_sampling_service.py
- core/services/zonal_stats_service.py
- core/services/raster_style_service.py
- core/ports/raster_provider_port.py
- adapters/raster/qgis_raster_adapter.py

### Point Cloud (8+ nouveaux fichiers)
- core/domain/point_cloud_info.py, point_cloud_filter.py
- core/services/point_cloud_service.py, point_cloud_stats_service.py
- core/ports/point_cloud_port.py
- adapters/point_cloud/qgis_point_cloud_adapter.py
- ui/controllers/point_cloud_controller.py
- ui/widgets/classification_filter_widget.py, elevation_range_widget.py

## Prioritized Roadmap

### Phase 1 (6-8w): Raster Complete
R1: Merge raster branch (2-3d) → R2: Value Sampling (3-5d) → R3: Zonal Stats (10-15d) → R4: Highlight (5-8d)

### Phase 2 (4-6w): Point Cloud V1
PC1: Port/Adapter (3-5d) → PC2: Classification filter (5-8d) → PC3: Attribute filter (3-5d) → PC4: UI integration (5-8d)

### Phase 3 (6-10w): Point Cloud V2 + Raster Advanced
PC7: PDAL clip (8-12d), PC8: Export (5-8d), R6: Raster clip (5-7d), R7: Multi-band (8-12d)

## QGIS Version Strategy
- Raster: keep 3.22 minimum (all APIs available)
- Point Cloud: require 3.26+ with conditional detection
- PDAL Processing: require 3.32+ (optional advanced features)

## No Competitors
- Raster interactive filtering: NONE in QGIS ecosystem
- Point cloud interactive filtering: NONE in QGIS ecosystem
- Cross-type filtering (vector+raster+PC): VISION, would be industry first
