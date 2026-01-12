# FilterMate Backends - v2.4.0

## Architecture Overview

Le système de backends FilterMate utilise une architecture modulaire avec un pattern Factory pour sélectionner automatiquement le backend optimal selon le type de couche.

```
backends/
├── __init__.py              # Exports publics
├── base_backend.py          # Interface abstraite
├── factory.py               # Sélection automatique
├── postgresql_backend.py    # Backend PostgreSQL/PostGIS
├── spatialite_backend.py    # Backend Spatialite/GeoPackage
├── ogr_backend.py           # Backend OGR (fallback universel)
├── mv_registry.py           # [v2.4.0] Gestion des MVs PostgreSQL
├── wkt_cache.py             # [v2.4.0] Cache WKT pour Spatialite
└── spatial_index_manager.py # [v2.4.0] Index spatiaux OGR
```

## Backends Disponibles

### 1. PostgreSQL Backend

**Fichier:** `postgresql_backend.py`

**Utilisation:** Couches PostgreSQL/PostGIS

**Stratégies par taille de dataset:**
| Features | Stratégie | Description |
|----------|-----------|-------------|
| < 50 | WKT Simple | Géométrie littérale directe |
| < 10k | EXISTS Subquery | Sous-requête avec filtre source |
| ≥ 10k | Materialized Views | Vues matérialisées avec index GIST |

**Optimisations v2.4.0:**

- Connection pooling (~50-100ms économisés par requête)
- MVRegistry pour cleanup automatique des vues matérialisées
- Ordonnancement optimal des prédicats (sélectivité)
- Normalisation de casse des colonnes

### 2. Spatialite Backend

**Fichier:** `spatialite_backend.py`

**Utilisation:** Couches Spatialite, GeoPackage (.gpkg), SQLite

**Caractéristiques:**

- Fonctions spatiales compatibles PostGIS
- Support automatique ST_Transform pour reprojection
- Styles de buffer configurables (round/flat/square)

**Optimisations v2.4.0:**

- WKTCache pour éviter le re-parsing des géométries
- Cache par layer_id avec TTL configurable
- Détection automatique des fonctions Spatialite disponibles

### 3. OGR Backend

**Fichier:** `ogr_backend.py`

**Utilisation:** Shapefiles, GeoJSON, et tous formats OGR

**Caractéristiques:**

- Fallback universel pour tous les formats
- Utilise QGIS Processing (selectbylocation)
- Thread-safe avec verrouillage explicite

**Optimisations v2.4.0:**

- SpatialIndexManager pour création automatique d'index
- Support .qix (Shapefile) et R-tree (GeoPackage)
- Validation GEOS-safe des géométries

## Modules d'Optimisation v2.4.0

### MVRegistry (PostgreSQL)

**Fichier:** `mv_registry.py`

**But:** Tracker et nettoyer automatiquement les vues matérialisées créées par FilterMate.

**Fonctionnalités:**

- Enregistrement automatique des MVs créées
- Cleanup périodique en arrière-plan
- Cleanup par layer ou global
- Statistiques de suivi

**Usage:**

```python
from modules.backends import get_mv_registry

registry = get_mv_registry()

# Enregistrer une MV
registry.register("mv_abc123", "public", "layer_id", "My Layer", 5000)

# Nettoyer les MVs anciennes (> 1h par défaut)
registry.cleanup_old()

# Nettoyer pour une couche spécifique
registry.cleanup_for_layer("layer_id")

# Statistiques
stats = registry.get_stats()
print(f"MVs actives: {stats['active_mvs']}")
```

### WKTCache (Spatialite)

**Fichier:** `wkt_cache.py`

**But:** Cache LRU pour les géométries WKT afin d'éviter le re-parsing répété.

**Fonctionnalités:**

- Cache LRU avec éviction automatique
- TTL configurable (5 min par défaut)
- Invalidation par layer
- Limite de taille WKT (500KB max)

**Usage:**

```python
from modules.backends import get_wkt_cache

cache = get_wkt_cache()

# Get or compute pattern
wkt, srid = cache.get_or_compute(
    key="layer_xyz_selection",
    compute_func=lambda: compute_wkt_from_layer(layer),
    source_layer_id="layer_xyz"
)

# Invalidation quand le layer change
cache.invalidate_for_layer("layer_xyz")

# Statistiques
stats = cache.get_stats()
print(f"Hit rate: {stats['hit_rate']:.1%}")
```

### SpatialIndexManager (OGR)

**Fichier:** `spatial_index_manager.py`

**But:** Création et gestion automatique des index spatiaux pour les formats fichier.

**Formats supportés:**
| Format | Type d'index | Fichier créé |
|--------|-------------|--------------|
| Shapefile | QIX | .qix |
| GeoPackage | R-tree | interne |
| SQLite | R-tree | interne |

**Usage:**

```python
from modules.backends import get_spatial_index_manager

manager = get_spatial_index_manager()

# Vérifier si l'index existe
has_index = manager.has_index(layer)

# Créer l'index si nécessaire
manager.ensure_index(layer)

# Forcer la recréation
manager.ensure_index(layer, force=True)

# Statistiques
stats = manager.get_stats()
print(f"Indexes créés: {stats['indexes_created']}")
```

## Factory et Cache

### BackendFactory

**Fichier:** `factory.py`

**Sélection automatique:**

1. Check backend forcé par l'utilisateur
2. Optimisation petits datasets PostgreSQL (< 5k → OGR memory)
3. PostgreSQL si disponible et compatible
4. Spatialite pour GeoPackage/SQLite
5. OGR comme fallback universel

**Cache amélioré v2.4.0:**

- Validation du cache par âge (TTL 5 min)
- Invalidation si feature count change
- Méthodes d'invalidation explicites

```python
from modules.backends import BackendFactory

# Obtenir le backend approprié
backend = BackendFactory.get_backend(
    layer_provider_type='postgresql',
    layer=my_layer,
    task_params=params
)

# Invalider le cache pour un layer modifié
BackendFactory.invalidate_layer_cache(layer.id())

# Nettoyer tout le cache
BackendFactory.clear_memory_cache()
```

## Configuration

Les constantes de configuration sont dans `modules/constants.py`:

```python
# PostgreSQL Materialized View settings
MV_MAX_AGE_SECONDS = 3600        # Max age before auto-cleanup
MV_CLEANUP_INTERVAL = 600        # Check every 10 minutes
MV_PREFIX = 'filtermate_mv_'

# Spatialite WKT Cache settings
WKT_CACHE_MAX_SIZE = 10          # Max entries
WKT_CACHE_MAX_LENGTH = 500000    # Max WKT size (500KB)
WKT_CACHE_TTL_SECONDS = 300      # 5 minutes

# OGR Spatial Index settings
SPATIAL_INDEX_AUTO_CREATE = True
SPATIAL_INDEX_MIN_FEATURES = 1000

# Factory Cache settings
FACTORY_CACHE_MAX_AGE = 300      # 5 minutes
```

## Performances Attendues

### Gains par Backend

| Backend    | Amélioration        | Cas d'usage          |
| ---------- | ------------------- | -------------------- |
| PostgreSQL | +10% stabilité      | Cleanup auto des MVs |
| PostgreSQL | -50ms/requête       | Connection pooling   |
| Spatialite | +50% répétitions    | WKT caching          |
| OGR        | +200% gros fichiers | Auto spatial index   |
| Factory    | +100% fiabilité     | Cache invalidation   |

### Seuils de Performance

| Features | Backend recommandé | Performance |
| -------- | ------------------ | ----------- |
| < 5k     | OGR memory (auto)  | Excellente  |
| 5k-50k   | Spatialite         | Bonne       |
| 50k-100k | PostgreSQL         | Très bonne  |
| > 100k   | PostgreSQL + MV    | Optimale    |

## Tests

Les tests sont dans `tests/`:

- `test_backends.py` - Tests unitaires des backends
- `test_mv_registry.py` - Tests du MVRegistry
- `test_wkt_cache.py` - Tests du WKTCache
- `test_spatial_index_manager.py` - Tests de l'IndexManager
