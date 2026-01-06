# FilterMate - Project Overview

**Version:** 2.9.12  
**Status:** Production-Ready  
**Type:** QGIS Plugin  
**License:** GPL-3.0

## 📋 Description

FilterMate est un plugin QGIS qui fournit des capacités avancées de filtrage et d'export pour les données vectorielles. Il fonctionne avec **toutes les sources de données** (PostgreSQL, Spatialite, OGR, fichiers) grâce à une architecture multi-backend intelligente.

## 🎯 Objectif

Permettre aux utilisateurs QGIS de :
- Filtrer efficacement des données vectorielles avec des prédicats spatiaux
- Sauvegarder et réutiliser des configurations de filtres (favoris)
- Naviguer dans l'historique des filtres (undo/redo)
- Exporter les données filtrées vers différents formats
- Bénéficier de performances optimales quel que soit le backend utilisé

## 🛠️ Stack Technologique

| Composant | Technologie |
|-----------|-------------|
| **Langage** | Python 3.7+ |
| **Framework** | QGIS Plugin API 3.0+ |
| **Interface** | PyQt5 |
| **Géométrie** | PostGIS, Spatialite, OGR/GDAL |
| **Base de données** | PostgreSQL, Spatialite, SQLite |
| **Tests** | pytest |
| **Logging** | Python logging (rotation) |

## 🏗️ Architecture Clé

### Multi-Backend System (Pattern Factory)

FilterMate sélectionne automatiquement le backend optimal selon la source de données :

```
┌─────────────────────────────────────┐
│     BackendFactory (factory.py)     │
│   Sélection intelligente du backend │
└──────────────┬──────────────────────┘
               │
       ┌───────┴───────┬───────────┬──────────┐
       │               │           │          │
┌──────▼─────┐  ┌─────▼────┐  ┌───▼────┐  ┌─▼────────┐
│ PostgreSQL │  │Spatialite│  │  OGR   │  │  Memory  │
│  Backend   │  │ Backend  │  │Backend │  │ Backend  │
└────────────┘  └──────────┘  └────────┘  └──────────┘
 Optimal pour    Bon pour     Fallback    Petits
 >100k features  <100k feat.  universel   datasets
```

### Système de Tâches Asynchrones (QgsTask)

Toutes les opérations lourdes sont exécutées dans des tâches asynchrones pour ne pas bloquer l'interface :

- **FilterEngineTask** : Filtrage principal (attribut + géométrie)
- **LayersManagementEngineTask** : Gestion multi-couches
- **ExpressionEvaluationTask** : Évaluation d'expressions complexes

### Fonctionnalités Principales

| Fonctionnalité | Description |
|---------------|-------------|
| **Filtrage Avancé** | Attributs + prédicats spatiaux (intersects, within, contains, etc.) |
| **Favoris** | Sauvegarde/chargement de configurations de filtres |
| **Historique** | Undo/redo complet avec navigation contextuelle |
| **Multi-Backend** | PostgreSQL, Spatialite, OGR - sélection automatique |
| **Optimisations** | Vues matérialisées (PostgreSQL), index R-tree (Spatialite), cache WKT |
| **Internationalisation** | 21 langues supportées |
| **Dark Mode** | Détection et synchronisation automatiques avec QGIS |
| **Export** | GeoPackage, Shapefile, GeoJSON, etc. |

## 📁 Structure du Projet

```
filter_mate/
├── filter_mate.py              # Point d'entrée plugin QGIS
├── filter_mate_app.py          # Orchestrateur principal (5343 lignes)
├── filter_mate_dockwidget.py   # Interface utilisateur (DockWidget)
├── modules/
│   ├── backends/               # Architecture multi-backend
│   │   ├── factory.py          # Sélection du backend
│   │   ├── postgresql_backend.py
│   │   ├── spatialite_backend.py
│   │   └── ogr_backend.py
│   ├── tasks/                  # Tâches asynchrones (QgsTask)
│   │   ├── filter_task.py      # Tâche de filtrage principale
│   │   └── layer_management_task.py
│   ├── filter_history.py       # Gestion undo/redo
│   ├── filter_favorites.py     # Gestion des favoris
│   ├── appUtils.py             # Utilitaires DB et connexions
│   └── [30+ autres modules]
├── config/                     # Système de configuration v2.0
├── i18n/                       # Fichiers de traduction (21 langues)
├── docs/                       # Documentation technique
└── tests/                      # Tests unitaires (pytest)
```

## 🔗 Documentation Détaillée

- **[Architecture](architecture.md)** - Architecture complète du système
- **[Component Inventory](component-inventory.md)** - Inventaire des composants
- **[Development Guide](development-guide.md)** - Guide pour développeurs
- **[Source Tree Analysis](source-tree-analysis.md)** - Arborescence annotée

## 🚀 Changements Récents (v2.9.12)

### Correctif Critique - Garbage Collection OGR
- **CRITICAL FIX:** Élimination du crash "wrapped C/C++ object has been deleted" lors du filtrage multi-couches
- **FIX:** Couche source_geom maintenue vivante pendant toute l'opération de filtrage
- **✅ Taux de succès:** 100% pour 8+ couches OGR (avant : 50-75%)

### Versions Antérieures
- **v2.9.11:** Protection contre l'access violation Windows dans processing.run()
- **v2.9.10:** Références de couches temporaires correctement scopées
- **v2.9.6:** Prédicats Spatialite NULL-safe
- **v2.9.3:** Correction filtrage UUID avec détection clé primaire

## 👥 Équipe et Support

- **Auteur:** imagodata
- **Email:** simon.ducournau+filter_mate@gmail.com
- **GitHub:** https://github.com/sducournau/filter_mate
- **Issues:** https://github.com/sducournau/filter_mate/issues
- **Website:** https://sducournau.github.io/filter_mate

## 📊 Statistiques du Projet

- **Lignes de code:** ~60,000+
- **Modules Python:** 45+
- **Backends supportés:** 4 (PostgreSQL, Spatialite, OGR, Memory)
- **Langues:** 21
- **Score qualité:** 9.0/10
- **Tests:** pytest (70% coverage, objectif 80%)

## 🎯 Phases de Développement

### ✅ Phases Complétées
- **Phase 1-3:** Multi-backend (PostgreSQL/Spatialite/OGR)
- **Phase 4:** Refonte UI (dark mode, thèmes)
- **Phase 5:** Qualité du code (score 9.0/10)
- **Phase 6:** Configuration v2.0 (metadata, migration)
- **Phase 7:** Fonctionnalités avancées (undo/redo, favoris)

### 🔄 Phase Actuelle
- **Phase 8:** Tests & Documentation (objectif: 80% coverage)

### 📋 Phases Futures
- **Phase 9:** Optimisations performance (caching)
- **Phase 10:** Extensibilité (API plugin)
- **Phase 11:** Fonctionnalités entreprise

## 🔑 Concepts Clés pour Développeurs IA

1. **Toujours vérifier POSTGRESQL_AVAILABLE** avant d'utiliser psycopg2
2. **Utiliser BackendFactory.get_backend()** pour obtenir le backend optimal
3. **QgsTask obligatoire** pour les opérations bloquantes
4. **safe_set_subset_string()** pour appliquer les filtres (gestion erreurs)
5. **HistoryManager et FavoritesManager** gèrent l'état persistant
6. **UIConfig** centralise toute la configuration UI (dimensions, thèmes)

## 📖 Références Rapides

### Fichiers Critiques
- [filter_mate_app.py](../filter_mate_app.py) - Orchestrateur (5343 lignes)
- [modules/backends/factory.py](../modules/backends/factory.py) - Sélection backend
- [modules/tasks/filter_task.py](../modules/tasks/filter_task.py) - Tâche filtrage principale
- [modules/appUtils.py](../modules/appUtils.py) - Utilitaires DB (1839 lignes)

### Patterns Importants
```python
# Vérification PostgreSQL
from modules.appUtils import POSTGRESQL_AVAILABLE

if POSTGRESQL_AVAILABLE and provider == 'postgresql':
    # Code PostgreSQL sécurisé
    pass

# Sélection Backend
backend = BackendFactory.get_backend(layer, layer_provider_type, task_params)
success = backend.apply_geometric_filter(...)

# Tâche Asynchrone
task = FilterEngineTask("Description", task_parameters)
QgsApplication.taskManager().addTask(task)
```

---

**Note:** Cette documentation est optimisée pour le développement assisté par IA. Pour la documentation utilisateur, voir https://sducournau.github.io/filter_mate
