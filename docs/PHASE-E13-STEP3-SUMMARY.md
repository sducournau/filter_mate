# Phase E13 Step 3: GeometryCache Integration

**Date:** 14 janvier 2026  
**Status:** ✅ Complété  
**Author:** FilterMate Team

## Objectif

Intégrer le `GeometryCache` au `SpatialFilterExecutor` pour améliorer les performances lors du filtrage de plusieurs couches avec la même source.

## Contexte

Le `GeometryCache` existait déjà dans deux niveaux :
- **Infrastructure** : `infrastructure/cache/geometry_cache.py` → `SourceGeometryCache`
- **Tasks** : `core/tasks/cache/geometry_cache.py` → `GeometryCache` (wrapper)

L'objectif était d'intégrer ce cache au `SpatialFilterExecutor` pour éviter les recalculs inutiles.

## Travail réalisé

### 1. Import du GeometryCache

**Fichier:** [spatial_filter_executor.py](../core/tasks/executors/spatial_filter_executor.py)

```python
from ..cache.geometry_cache import GeometryCache
```

### 2. Modification du constructeur

Ajout d'un paramètre optionnel `geometry_cache` :

```python
def __init__(
    self,
    source_layer: QgsVectorLayer,
    project: Optional[QgsProject] = None,
    backend_registry: Optional[Any] = None,
    task_bridge: Optional[Any] = None,
    postgresql_available: bool = False,
    geometry_cache: Optional[GeometryCache] = None  # NOUVEAU
):
    # ...
    self._geometry_cache = geometry_cache or GeometryCache.get_shared_instance()
```

### 3. Méthode `prepare_source_geometry_via_executor()` améliorée

Ajout du caching avec les fonctionnalités suivantes :

| Fonctionnalité | Description |
|----------------|-------------|
| **Cache lookup** | Vérification du cache avant calcul |
| **Cache storage** | Stockage du résultat après calcul |
| **Cache key** | layer_id + feature_ids + buffer + CRS + subset_string |
| **Paramètre use_cache** | Désactivation optionnelle du cache |

### 4. Nouvelles méthodes de gestion du cache

```python
def invalidate_geometry_cache(self, layer_id: Optional[str] = None):
    """Invalidate cache for a layer or all layers."""

def get_cache_stats(self) -> Dict:
    """Get cache statistics (hits, misses, size)."""
```

### 5. Tests unitaires

**Fichier:** [test_spatial_filter_executor.py](../tests/unit/tasks/executors/test_spatial_filter_executor.py)

Nouvelle classe `TestGeometryCacheIntegration` avec 7 tests :

| Test | Description |
|------|-------------|
| `test_cache_is_used` | Vérification de l'initialisation du cache |
| `test_cache_lookup_on_prepare` | Cache lookup lors de la préparation |
| `test_cache_hit_skips_calculation` | Cache hit évite le recalcul |
| `test_cache_disabled` | Fonctionnement sans cache |
| `test_invalidate_layer_cache` | Invalidation par couche |
| `test_clear_all_cache` | Nettoyage complet |
| `test_get_cache_stats` | Récupération des statistiques |

## Performance attendue

| Scénario | Sans cache | Avec cache | Gain |
|----------|------------|------------|------|
| 5 couches, même source (2000 features) | 10s | 2.04s | **~5×** |
| 10 couches, même source | 20s | 2.1s | **~10×** |
| Couche unique | 2s | 2s | 0% |

## Architecture de cache

```
SpatialFilterExecutor
    │
    ├─► _geometry_cache (GeometryCache)
    │       │
    │       └─► _underlying_cache (SourceGeometryCache)
    │               │
    │               ├─► _cache (Dict)
    │               └─► _access_order (FIFO list)
    │
    └─► prepare_source_geometry_via_executor()
            │
            ├─► 1. Check cache (get)
            │
            ├─► 2. Calculate if miss
            │
            └─► 3. Store in cache (put)
```

## Clé de cache

La clé de cache est composée de :

```python
cache_key = (
    feature_ids,       # Tuple trié des IDs
    buffer_value,      # Distance de buffer
    target_crs_authid, # CRS cible
    layer_id,          # ID de la couche source
    subset_string      # Filtre actif (invalide le cache si modifié)
)
```

## Prochaines étapes

| Phase | Description | Status |
|-------|-------------|--------|
| E13 Step 4 | SubsetStringBuilder extraction | ⏳ |
| E13 Step 5 | FeatureCollector extraction | ⏳ |
| E13 Step 6 | FilterOrchestrator simplification | ⏳ |

## Métriques

| Métrique | Avant | Après |
|----------|-------|-------|
| LOC SpatialFilterExecutor | ~520 | ~570 |
| Tests unitaires | 18 | 25 |
| Couverture estimée | 85% | 90% |
