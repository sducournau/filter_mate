# Raster & Network Analysis Roadmap

**Créé:** 16 décembre 2025  
**Document complet:** `docs/RASTER_NETWORK_ROADMAP.md`  
**Version cible:** 3.0.0  
**Durée estimée:** 9-13 semaines

## Résumé des Phases

### Phase 1: Fondations Raster (Semaines 1-3)
- `modules/backends/raster_backend.py` - Backend GDAL
- `modules/tasks/raster_sampling_task.py` - Tâches asynchrones
- UI: Onglet RASTER dans dockwidget

### Phase 2: Filtres Raster Avancés (Semaines 4-6)
- `modules/analysis/terrain_analysis.py` - MNT (altitude, pente, exposition)
- `modules/analysis/vegetation_analysis.py` - NDVI et indices
- `modules/filters/raster_filters.py` - Filtres composés

### Phase 3: Analyse Réseau (Semaines 7-10)
- `modules/backends/network_backend.py` - NetworkX/pgRouting
- `modules/analysis/network_graph.py` - Routage télécom
- `modules/tasks/network_analysis_task.py` - Tâches asynchrones

### Phase 4: Filtres Télécom (Semaines 11-12)
- `modules/filters/telecom_filters.py` - Filtres métier FTTH
- UI: Onglet NETWORK ANALYSIS

### Phase 5: Tests & Docs (Semaine 13)
- Tests unitaires (>80% couverture)
- Documentation utilisateur et développeur

## Nouveaux Répertoires
```
modules/
├── backends/raster_backend.py (NOUVEAU)
├── backends/network_backend.py (NOUVEAU)
├── tasks/raster_sampling_task.py (NOUVEAU)
├── tasks/network_analysis_task.py (NOUVEAU)
├── filters/ (NOUVEAU)
│   ├── raster_filters.py
│   ├── network_filters.py
│   └── telecom_filters.py
└── analysis/ (NOUVEAU)
    ├── terrain_analysis.py
    ├── vegetation_analysis.py
    └── network_graph.py
```

## Dépendances
- GDAL (inclus dans QGIS) - obligatoire
- NetworkX - recommandé
- pgRouting - optionnel (si PostgreSQL)

## Points Clés
- Réutilise le pattern Factory existant
- Compatibilité totale avec backends existants
- Intégration non intrusive via onglets UI
- Support undo/redo étendu
