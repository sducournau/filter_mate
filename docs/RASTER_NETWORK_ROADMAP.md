# 🚀 Roadmap: Raster & Network Analysis pour FilterMate

**Date de création:** 16 décembre 2025  
**Version cible:** 3.0.0  
**Durée estimée:** 9-13 semaines  
**Statut:** 📋 Planification

---

## 📋 Résumé Exécutif

Ce document décrit le plan d'implémentation pour étendre FilterMate avec des capacités d'analyse raster (MNT, NDVI, orthophotos) et d'analyse réseau (graphes, pgRouting, NetworkX). Ces fonctionnalités ciblent principalement les cas d'usage télécom/FTTH mais restent génériques.

### Objectifs Clés
1. **Filtrage par valeurs raster** - Échantillonnage de pixels aux positions vectorielles
2. **Statistiques zonales** - Min, max, mean, std sur polygones
3. **Analyse de réseau** - Calcul de chemins optimaux BRO → Client
4. **Intégration télécom** - Filtres métier spécifiques FTTH

---

## 🏗️ Architecture Proposée

### Structure des Nouveaux Modules

```
modules/
├── backends/
│   ├── base_backend.py              # ✅ Existant
│   ├── factory.py                   # 🔄 À étendre
│   ├── postgresql_backend.py        # ✅ Existant
│   ├── spatialite_backend.py        # ✅ Existant
│   ├── ogr_backend.py               # ✅ Existant
│   ├── raster_backend.py            # 🆕 NOUVEAU - Support raster GDAL
│   └── network_backend.py           # 🆕 NOUVEAU - Analyse graphe
│
├── tasks/
│   ├── filter_task.py               # ✅ Existant
│   ├── layer_management_task.py     # ✅ Existant
│   ├── task_utils.py                # ✅ Existant
│   ├── geometry_cache.py            # ✅ Existant
│   ├── raster_sampling_task.py      # 🆕 NOUVEAU - Tâches raster
│   └── network_analysis_task.py     # 🆕 NOUVEAU - Tâches réseau
│
├── filters/                         # 🆕 NOUVEAU répertoire
│   ├── __init__.py
│   ├── base_filter.py               # Interface abstraite
│   ├── raster_filters.py            # Filtres raster
│   ├── network_filters.py           # Filtres réseau
│   └── telecom_filters.py           # Filtres métier télécom
│
└── analysis/                        # 🆕 NOUVEAU répertoire
    ├── __init__.py
    ├── terrain_analysis.py          # MNT: pente, exposition, altitude
    ├── vegetation_analysis.py       # NDVI, indices végétation
    └── network_graph.py             # Graphe réseau, routage
```

---

## 📅 Planning Détaillé

### Phase 1: Fondations Raster (Semaines 1-3)

#### 1.1 Backend Raster de Base
**Durée:** 1 semaine  
**Fichier:** `modules/backends/raster_backend.py`

**Tâches:**
- [ ] Créer la classe `RasterBackend` héritant de `GeometricFilterBackend`
- [ ] Implémenter lecture GDAL multi-bandes
- [ ] Support formats: GeoTIFF, JPEG2000, VRT, MBTiles
- [ ] Gestion CRS et reprojection à la volée
- [ ] Tests unitaires

**Interface proposée:**
```python
class RasterBackend:
    """Backend pour opérations raster via GDAL."""
    
    def __init__(self, raster_path: str):
        """
        Args:
            raster_path: Chemin vers le fichier raster
        """
        
    def sample_point(self, geom: QgsGeometry, band: int = 1) -> Optional[float]:
        """Échantillonne la valeur raster à une position ponctuelle."""
        
    def sample_points(self, layer: QgsVectorLayer, band: int = 1) -> Dict[int, float]:
        """Échantillonne plusieurs points (batch optimisé)."""
        
    def zonal_stats(self, polygon: QgsGeometry, band: int = 1) -> Dict[str, float]:
        """Calcule statistiques zonales: min, max, mean, std, count."""
        
    def get_metadata(self) -> Dict:
        """Retourne métadonnées: CRS, résolution, extent, n_bands."""
```

#### 1.2 Tâche d'Échantillonnage Raster
**Durée:** 1 semaine  
**Fichier:** `modules/tasks/raster_sampling_task.py`

**Tâches:**
- [ ] Créer `RasterSamplingTask(QgsTask)` pour opérations asynchrones
- [ ] Support annulation avec `isCanceled()`
- [ ] Rapports de progression
- [ ] Gestion mémoire pour grands rasters

**Interface proposée:**
```python
class RasterSamplingTask(QgsTask):
    """Tâche asynchrone d'échantillonnage raster."""
    
    def __init__(self, description: str, vector_layer: QgsVectorLayer, 
                 raster_path: str, output_field: str, band: int = 1):
        """
        Args:
            description: Description de la tâche
            vector_layer: Couche vectorielle à enrichir
            raster_path: Chemin du raster source
            output_field: Nom du champ pour stocker les valeurs
            band: Numéro de bande (1-based)
        """
    
    def run(self) -> bool:
        """Exécute l'échantillonnage."""
        
    def finished(self, result: bool):
        """Callback de fin avec signal vers UI."""
```

#### 1.3 Interface Utilisateur Raster
**Durée:** 1 semaine  
**Fichiers:** `filter_mate_dockwidget.py`, `modules/widgets.py`

**Tâches:**
- [ ] Ajouter onglet "RASTER" dans le dock widget
- [ ] Sélecteur de couche raster (QgsMapLayerComboBox filtré)
- [ ] Sélecteur de bande
- [ ] Paramètres d'échantillonnage (méthode: nearest, bilinear, cubic)
- [ ] Prévisualisation des statistiques

**Wireframe UI:**
```
┌─────────────────────────────────────────┐
│ ▼ RASTER ANALYSIS                       │
├─────────────────────────────────────────┤
│ Raster Layer: [Dropdown MNT.tif    ▼]   │
│ Band:         [1 - Elevation       ▼]   │
│                                         │
│ ── Sampling Options ──                  │
│ Method: ○ Nearest  ● Bilinear  ○ Cubic  │
│ Output Field: [altitude          ]      │
│                                         │
│ ── Statistics ──                        │
│ □ Add min/max columns                   │
│ □ Add slope/aspect (MNT only)           │
│                                         │
│ [  Sample Selected Features  ]          │
│ [  Sample All Features       ]          │
└─────────────────────────────────────────┘
```

---

### Phase 2: Filtres Raster Avancés (Semaines 4-6)

#### 2.1 Analyse de Terrain (MNT)
**Durée:** 1.5 semaines  
**Fichier:** `modules/analysis/terrain_analysis.py`

**Fonctionnalités:**
- [ ] Calcul d'altitude à partir du MNT
- [ ] Calcul de pente (%)
- [ ] Calcul d'exposition (orientation N/S/E/O)
- [ ] Analyse de visibilité (viewshed simplifié)

**Interface proposée:**
```python
class TerrainAnalyzer:
    """Analyse de terrain à partir d'un MNT."""
    
    def __init__(self, mnt_path: str):
        """
        Args:
            mnt_path: Chemin vers le MNT (GeoTIFF)
        """
    
    def get_elevation(self, point: QgsPointXY) -> float:
        """Retourne l'altitude en mètres."""
        
    def get_slope(self, point: QgsPointXY, radius: float = 10) -> float:
        """Calcule la pente en % autour d'un point."""
        
    def get_aspect(self, point: QgsPointXY) -> float:
        """Retourne l'orientation en degrés (0-360, N=0)."""
        
    def check_visibility(self, observer: QgsPointXY, target: QgsPointXY,
                        observer_height: float = 2.0) -> bool:
        """Vérifie si target est visible depuis observer."""
        
    def filter_by_elevation(self, layer: QgsVectorLayer, 
                           min_elev: float, max_elev: float) -> str:
        """Génère expression de filtre par altitude."""
```

#### 2.2 Indices de Végétation (NDVI)
**Durée:** 1 semaine  
**Fichier:** `modules/analysis/vegetation_analysis.py`

**Fonctionnalités:**
- [ ] Calcul NDVI depuis bandes NIR/Red
- [ ] Classification végétation (dense, modérée, absente)
- [ ] Support indices alternatifs (SAVI, EVI)

**Interface proposée:**
```python
class VegetationAnalyzer:
    """Analyse de végétation par indices spectraux."""
    
    def __init__(self, nir_raster: str, red_raster: str = None,
                 nir_band: int = 1, red_band: int = 1):
        """
        Args:
            nir_raster: Raster contenant bande NIR
            red_raster: Raster contenant bande Rouge (ou même fichier)
            nir_band: Numéro de bande NIR
            red_band: Numéro de bande Rouge
        """
    
    def compute_ndvi(self, geometry: QgsGeometry) -> float:
        """Calcule NDVI moyen sur une géométrie."""
        
    def classify_vegetation(self, ndvi: float) -> str:
        """Classifie: 'bare', 'sparse', 'moderate', 'dense'."""
        
    def filter_by_ndvi(self, layer: QgsVectorLayer,
                      min_ndvi: float, max_ndvi: float) -> str:
        """Génère expression de filtre par NDVI."""
```

#### 2.3 Filtres Raster Composés
**Durée:** 0.5 semaine  
**Fichier:** `modules/filters/raster_filters.py`

**Interface proposée:**
```python
class RasterFilter:
    """Filtres combinant données vectorielles et raster."""
    
    @staticmethod
    def filter_by_elevation_range(layer: QgsVectorLayer, mnt: str,
                                  min_elev: float, max_elev: float) -> List[int]:
        """Retourne IDs des entités dans la plage d'altitude."""
        
    @staticmethod
    def filter_by_slope(layer: QgsVectorLayer, mnt: str,
                       max_slope_percent: float) -> List[int]:
        """Retourne IDs des entités en zone de pente acceptable."""
        
    @staticmethod
    def filter_by_vegetation_density(layer: QgsVectorLayer, ndvi: str,
                                    density: str) -> List[int]:
        """Retourne IDs par densité de végétation."""
        
    @staticmethod
    def filter_accessible_zones(layer: QgsVectorLayer, mnt: str,
                               start_point: QgsPointXY,
                               max_slope: float = 15,
                               max_distance: float = 1000) -> List[int]:
        """Zones accessibles depuis un point avec contraintes de pente."""
```

---

### Phase 3: Analyse Réseau (Semaines 7-10)

#### 3.1 Backend Réseau
**Durée:** 1.5 semaines  
**Fichier:** `modules/backends/network_backend.py`

**Dépendances:**
- NetworkX (Python, toujours disponible)
- pgRouting (optionnel, si PostgreSQL disponible)

**Tâches:**
- [ ] Créer `NetworkBackend` avec support dual NetworkX/pgRouting
- [ ] Construction de graphe depuis couche linéaire
- [ ] Calcul plus court chemin (Dijkstra)
- [ ] Support coûts multi-critères
- [ ] Gestion topologie (snapping, nœuds)

**Interface proposée:**
```python
class NetworkBackend:
    """Backend d'analyse de réseau de transport."""
    
    NETWORKX_AVAILABLE = True  # Toujours disponible
    PGROUTING_AVAILABLE = False  # Détecté dynamiquement
    
    def __init__(self, network_layer: QgsVectorLayer, 
                 cost_field: str = None, direction_field: str = None):
        """
        Args:
            network_layer: Couche linéaire représentant le réseau
            cost_field: Champ de coût (distance si None)
            direction_field: Champ de direction (bidirectionnel si None)
        """
    
    def build_graph(self) -> bool:
        """Construit le graphe NetworkX depuis la couche."""
        
    def shortest_path(self, start: QgsPointXY, end: QgsPointXY) -> Dict:
        """
        Calcule le plus court chemin.
        
        Returns:
            {
                'path': List[QgsPointXY],
                'cost': float,
                'edges': List[int],  # FIDs des arêtes
                'length': float      # Distance géométrique
            }
        """
        
    def service_area(self, center: QgsPointXY, max_cost: float) -> QgsGeometry:
        """Zone de desserte (isochrone) depuis un point."""
        
    def nearest_facility(self, origin: QgsPointXY, 
                        facilities: QgsVectorLayer) -> Dict:
        """Trouve l'équipement le plus proche par le réseau."""
```

#### 3.2 Analyse Réseau pour Télécom
**Durée:** 1.5 semaines  
**Fichier:** `modules/analysis/network_graph.py`

**Fonctionnalités spécifiques FTTH:**
- [ ] Calcul distance réseau BRO → Client
- [ ] Détection de contraintes de capacité
- [ ] Optimisation multi-clients
- [ ] Export rapport de faisabilité

**Interface proposée:**
```python
class TelecomNetworkAnalyzer:
    """Analyse réseau spécifique télécom/FTTH."""
    
    def __init__(self, network_layer: QgsVectorLayer,
                 bro_layer: QgsVectorLayer,
                 client_layer: QgsVectorLayer):
        """
        Args:
            network_layer: Réseau câble/conduite
            bro_layer: Points de raccordement optique (BRO)
            client_layer: Clients à desservir
        """
    
    def compute_network_distance(self, bro_id: str, 
                                client_id: str) -> float:
        """Distance réseau entre BRO et client (mètres)."""
        
    def find_nearest_bro(self, client_geometry: QgsGeometry) -> Dict:
        """Trouve le BRO le plus proche par le réseau."""
        
    def compute_feasibility(self, bro_id: str, 
                           max_clients: int = 128) -> Dict:
        """
        Évalue faisabilité de raccordement.
        
        Returns:
            {
                'bro_id': str,
                'current_clients': int,
                'capacity': int,
                'feasible_clients': List[str],
                'infeasible_clients': List[str],
                'reasons': Dict[str, str]  # client_id -> raison
            }
        """
    
    def optimize_assignment(self, max_distance: float = 2000) -> Dict:
        """
        Optimise l'affectation clients → BRO.
        
        Returns:
            {
                'assignments': Dict[str, str],  # client_id -> bro_id
                'total_length': float,
                'unserved_clients': List[str]
            }
        """
```

#### 3.3 Tâche d'Analyse Réseau
**Durée:** 1 semaine  
**Fichier:** `modules/tasks/network_analysis_task.py`

**Tâches:**
- [ ] Créer `NetworkAnalysisTask(QgsTask)`
- [ ] Construction graphe en arrière-plan
- [ ] Calculs de chemin asynchrones
- [ ] Génération rapport exportable

---

### Phase 4: Filtres Télécom Métier (Semaines 11-12)

#### 4.1 Filtres Combinés Raster + Réseau
**Durée:** 1 semaine  
**Fichier:** `modules/filters/telecom_filters.py`

**Interface proposée:**
```python
class TelecomFilters:
    """Filtres métier pour réseaux FTTH combinant toutes les analyses."""
    
    def __init__(self, config: Dict):
        """
        Args:
            config: Configuration incluant:
                - network_layer: Réseau câble
                - bro_layer: BRO
                - client_layer: Clients
                - mnt_layer: MNT (optionnel)
                - ndvi_layer: NDVI (optionnel)
                - constraints: Dict de contraintes
        """
    
    def filter_by_cable_capacity(self, bro_id: str) -> List[int]:
        """Clients non raccordables car BRO saturé."""
        
    def filter_by_terrain_constraints(self, max_slope: float = 30) -> List[int]:
        """Tracés avec dénivelé acceptable."""
        
    def filter_by_vegetation_risk(self, max_ndvi: float = 0.6) -> List[int]:
        """Câbles aériens hors zone végétation dense."""
        
    def filter_optimal_clients(self, bro_id: str, count: int = 50,
                              constraints: Dict = None) -> List[int]:
        """
        Sélectionne les N meilleurs clients à raccorder.
        
        Args:
            bro_id: Identifiant du BRO
            count: Nombre de clients à sélectionner
            constraints: Dict optionnel:
                - max_distance: Distance réseau max (m)
                - max_slope: Pente max (%)
                - max_ndvi: NDVI max (végétation)
                - avoid_layers: Couches d'obstacles
        
        Returns:
            Liste des IDs clients ordonnés par priorité
        """
    
    def generate_feasibility_report(self, output_path: str) -> bool:
        """
        Génère rapport CSV/Excel de faisabilité.
        
        Colonnes: BRO_ID, Client_ID, Distance_Reseau, Pente_Max,
                  NDVI_Moyen, Obstacles, Faisabilite, Cout_Estime
        """
```

#### 4.2 Interface Utilisateur Réseau
**Durée:** 1 semaine  
**Fichiers:** `filter_mate_dockwidget.py`, `modules/widgets.py`

**Wireframe UI:**
```
┌─────────────────────────────────────────┐
│ ▼ NETWORK ANALYSIS                      │
├─────────────────────────────────────────┤
│ Network Layer: [Cables_FO        ▼]     │
│ BRO Layer:     [Points_BRO       ▼]     │
│ Client Layer:  [Clients          ▼]     │
│                                         │
│ ── Analysis Type ──                     │
│ ○ Shortest Path  ○ Service Area         │
│ ● Optimal Assignment                    │
│                                         │
│ ── Constraints ──                       │
│ Max Distance: [2000    ] m              │
│ Max Slope:    [30      ] %  □ Use MNT   │
│ Max NDVI:     [0.6     ]    □ Use NDVI  │
│ BRO Capacity: [128     ] clients        │
│                                         │
│ ── Obstacles ──                         │
│ □ Forests          □ Protected Areas    │
│ □ Water Bodies     □ Buildings          │
│                                         │
│ [  Run Analysis  ]   [  Export Report ] │
├─────────────────────────────────────────┤
│ Results: 47/50 clients feasible         │
│ Total cable length: 12,450 m            │
│ Avg cost per client: 245 €              │
└─────────────────────────────────────────┘
```

---

### Phase 5: Tests et Documentation (Semaine 13)

#### 5.1 Tests Unitaires
**Fichiers:** `tests/test_raster_*.py`, `tests/test_network_*.py`

**Tests à créer:**
- [ ] `test_raster_backend.py` - Lecture/échantillonnage raster
- [ ] `test_terrain_analysis.py` - Pente, altitude, exposition
- [ ] `test_vegetation_analysis.py` - NDVI, classification
- [ ] `test_network_backend.py` - Graphe, routage
- [ ] `test_telecom_filters.py` - Filtres métier

#### 5.2 Documentation
**Fichiers à créer/mettre à jour:**
- [ ] `docs/RASTER_ANALYSIS.md` - Guide analyse raster
- [ ] `docs/NETWORK_ANALYSIS.md` - Guide analyse réseau
- [ ] `docs/TELECOM_USE_CASES.md` - Cas d'usage télécom
- [ ] `website/docs/features/raster.md` - Doc utilisateur raster
- [ ] `website/docs/features/network.md` - Doc utilisateur réseau
- [ ] Mise à jour `README.md` et `CHANGELOG.md`

---

## 🔧 Dépendances à Ajouter

### Obligatoires (incluses dans QGIS)
```python
# Déjà disponibles via QGIS
from osgeo import gdal, ogr, osr  # Lecture raster/vecteur
import numpy as np                 # Calculs matriciels
```

### Optionnelles
```python
# À vérifier disponibilité
try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False

# pgRouting via PostgreSQL
# Détecté via requête SQL: SELECT * FROM pgr_version()
```

### Requirements Update
```txt
# requirements-optional.txt (NOUVEAU)
networkx>=2.5      # Analyse graphe (recommandé)
scipy>=1.6         # Optimisation (optionnel)
```

---

## 📊 Métriques de Succès

### Performance
| Opération | Objectif | Mesure |
|-----------|----------|--------|
| Échantillonnage 10k points | < 5s | Temps d'exécution |
| Statistiques zonales 1k polygones | < 10s | Temps d'exécution |
| Construction graphe 50k arêtes | < 3s | Temps d'exécution |
| Plus court chemin | < 100ms | Temps par requête |
| Assignation optimale 1k clients | < 30s | Temps d'exécution |

### Qualité
- [ ] Couverture tests > 80%
- [ ] Zéro régression sur fonctionnalités existantes
- [ ] Documentation complète
- [ ] Compatibilité QGIS 3.16+

---

## ⚠️ Risques et Mitigations

| Risque | Impact | Probabilité | Mitigation |
|--------|--------|-------------|------------|
| NetworkX indisponible | Moyen | Faible | Fallback QGIS Processing |
| Rasters très grands (>10GB) | Élevé | Moyen | Chunking, sous-échantillonnage |
| pgRouting non installé | Faible | Élevé | NetworkX par défaut |
| Performance graphe > 100k nœuds | Moyen | Moyen | Spatial indexing, simplification |

---

## 📝 Prochaines Actions

### Immédiat (Cette semaine)
1. [ ] Valider architecture avec équipe
2. [ ] Créer structure de répertoires
3. [ ] Implémenter squelette `RasterBackend`

### Court terme (2 semaines)
1. [ ] Compléter Phase 1.1 (Backend raster)
2. [ ] Tests unitaires basiques
3. [ ] Prototype UI raster

### Moyen terme (1 mois)
1. [ ] Phases 1-2 complètes
2. [ ] Démonstration filtrage MNT/NDVI
3. [ ] Début Phase 3 (Réseau)

---

## 🔗 Références

### Documentation GDAL
- [GDAL Python API](https://gdal.org/api/python.html)
- [Raster API Tutorial](https://gdal.org/tutorials/raster_api_tut.html)

### NetworkX
- [NetworkX Documentation](https://networkx.org/documentation/stable/)
- [Shortest Paths](https://networkx.org/documentation/stable/reference/algorithms/shortest_paths.html)

### pgRouting
- [pgRouting Documentation](https://pgrouting.org/documentation.html)
- [pgr_dijkstra](https://docs.pgrouting.org/latest/en/pgr_dijkstra.html)

### QGIS
- [QgsRasterLayer](https://qgis.org/pyqgis/master/core/QgsRasterLayer.html)
- [QgsProcessing](https://qgis.org/pyqgis/master/core/QgsProcessingAlgorithm.html)

---

## 📌 Notes de Compatibilité

### Avec l'existant FilterMate
- ✅ Pattern Factory étendu (pas de breaking change)
- ✅ QgsTask réutilisé pour toutes les nouvelles tâches
- ✅ UI intégrée via nouveaux onglets (non intrusif)
- ✅ Configuration JSON étendue (rétrocompatible)
- ✅ Historique undo/redo étendu aux opérations raster

### Avec les backends existants
- PostgreSQL: Requêtes raster via PostGIS Raster (optionnel)
- Spatialite: Pas de support raster natif (GDAL uniquement)
- OGR: Pas de support raster (GDAL uniquement)

---

*Ce document sera mis à jour au fur et à mesure de l'avancement du projet.*

**Auteur:** FilterMate Team  
**Dernière mise à jour:** 16 décembre 2025
