# FilterMate Backend Architecture

**Version**: 4.1.0  
**Date**: Janvier 2025  
**Status**: Production

---

## 📋 Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Backends disponibles](#backends-disponibles)
3. [Architecture hexagonale](#architecture-hexagonale)
4. [Guide d'utilisation](#guide-dutilisation)
5. [Patterns et bonnes pratiques](#patterns-et-bonnes-pratiques)
6. [Performance](#performance)
7. [Extensibilité](#extensibilité)

---

## Vue d'ensemble

FilterMate utilise une **architecture hexagonale** avec 3 backends interchangeables :

```
┌─────────────────────────────────────────────────────────┐
│                    Core Domain                          │
│  (filter/, optimization/, tasks/)                       │
└─────────────────────────────────────────────────────────┘
                         ▲
                         │ Ports (Backend Services)
                         │
┌────────────────────────┼────────────────────────────────┐
│                    Adapters                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │PostgreSQL│  │Spatialite│  │   OGR    │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└──────────────────────────────────────────────────────────┘
                         ▲
                         │
┌────────────────────────┼────────────────────────────────┐
│              Infrastructure                             │
│  (QGIS, psycopg2, SQLite, GDAL)                        │
└──────────────────────────────────────────────────────────┘
```

### Principes clés

✅ **Séparation des préoccupations** : Core → Adapters → Infrastructure  
✅ **Interchangeabilité** : Backends avec interface commune  
✅ **Testabilité** : Mocking facile via ports  
✅ **Performance** : Sélection automatique du meilleur backend

---

## Backends disponibles

### 🐘 PostgreSQL

**Meilleur pour** : Très grands jeux de données (>50k entités)

| Fonctionnalité | Support | Notes |
|----------------|---------|-------|
| **Filtres spatiaux** | ✅ Excellent | PostGIS natif, indexes spatiaux |
| **Vues matérialisées** | ✅ Oui | Performances optimales |
| **Async queries** | ✅ Oui | psycopg2.pool |
| **Transactions** | ✅ ACID | MVCC complet |
| **Taille max** | 🚀 Illimitée | Scalabilité horizontale |
| **Installation** | ⚠️ Requise | PostgreSQL + psycopg2 |

**Seuils recommandés** :
- ✅ **>10 000 entités** avec filtres spatiaux
- ✅ **>50 000 entités** filtres standards
- ✅ **Filtres complexes** (multiples joins, ST_*)

**Exemple** :
```python
# Détection automatique
if layer.providerType() == 'postgres' and layer.featureCount() > 10000:
    backend = 'postgresql'  # Optimal choice
```

---

### 🗄️ Spatialite

**Meilleur pour** : Jeux de données moyens (100 - 50k entités)

| Fonctionnalité | Support | Notes |
|----------------|---------|-------|
| **Filtres spatiaux** | ✅ Bon | mod_spatialite, R-tree indexes |
| **Tables temporaires** | ✅ Oui | Alternative aux vues matérialisées |
| **Transactions** | ✅ Oui | SQLite ACID |
| **Taille max** | ⚠️ ~50k ents | Performance décroît au-delà |
| **Installation** | ✅ QGIS | Fourni avec QGIS |
| **GeoPackage** | ✅ Oui | Format recommandé |

**Seuils recommandés** :
- ✅ **100 - 50 000 entités** (sweet spot)
- ✅ **Filtres attributaires** simples
- ✅ **Filtres spatiaux** légers (ST_Intersects, ST_Within)
- ⚠️ **Éviter** : Très grandes géométries, filtres multiples imbriqués

**Exemple** :
```python
# Configuration Spatialite
conn = sqlite3.connect(db_path)
conn.enable_load_extension(True)
conn.load_extension('mod_spatialite')  # Windows: .dll

# Table temporaire avec index spatial
cursor.execute("""
    CREATE TEMP TABLE temp_filter AS
    SELECT * FROM layer WHERE condition;
""")
cursor.execute("""
    SELECT CreateSpatialIndex('temp_filter', 'geometry');
""")
```

---

### 🗂️ OGR

**Meilleur pour** : Petits datasets (<10k), formats variés

| Fonctionnalité | Support | Notes |
|----------------|---------|-------|
| **Formats** | ✅ 50+ | Shapefile, GeoJSON, KML, etc. |
| **Filtres spatiaux** | ⚠️ Limité | QGIS processing seulement |
| **Performance** | ⚠️ Faible | Pas d'indexes |
| **Taille max** | ⚠️ <10k ents | Ralentissement significatif |
| **Installation** | ✅ QGIS | Fourni avec QGIS |
| **Portabilité** | ✅ Maximale | Aucune dépendance externe |

**Seuils recommandés** :
- ✅ **<1 000 entités** (optimal)
- ✅ **Filtres attributaires** uniquement
- ⚠️ **Éviter** : Filtres spatiaux, grands datasets

**Exemple** :
```python
# Filtrage OGR (subset string QGIS)
layer.setSubsetString('"population" > 10000')
layer.triggerRepaint()
```

---

## Architecture hexagonale

### Structure des dossiers

```
adapters/
├── backends/
│   ├── postgresql/
│   │   ├── __init__.py
│   │   ├── backend.py              # PostgreSQLBackend class
│   │   ├── filter_actions.py       # Reset, unfilter, cleanup
│   │   ├── query_executor.py       # SQL execution
│   │   └── database_manager.py     # Connection pooling
│   │
│   ├── spatialite/
│   │   ├── __init__.py
│   │   ├── backend.py              # SpatialiteBackend class
│   │   ├── filter_actions.py       # Reset, unfilter, cleanup
│   │   ├── query_executor.py       # SQL execution
│   │   └── database_manager.py     # Connection management
│   │
│   └── ogr/
│       ├── __init__.py
│       ├── backend.py              # OGRBackend class
│       └── filter_actions.py       # Reset, unfilter
│
├── backend_registry.py             # Backend factory
└── database_manager.py             # Unified interface
```

### Ports (Interfaces)

**core/ports/backend_services.py** :
```python
class BackendServicePort:
    """Interface commune pour tous les backends."""
    
    def execute_filter(self, layer, expression):
        """Applique un filtre."""
        raise NotImplementedError
    
    def execute_reset(self, layer):
        """Réinitialise le filtre."""
        raise NotImplementedError
    
    def execute_unfilter(self, layer, previous_subset):
        """Restaure le filtre précédent."""
        raise NotImplementedError
    
    def cleanup_temp_resources(self, datasource):
        """Nettoie les ressources temporaires."""
        raise NotImplementedError
```

### Adaptateurs (Implémentations)

Chaque backend implémente `BackendServicePort` :

**adapters/backends/postgresql/backend.py** :
```python
class PostgreSQLBackend(BackendServicePort):
    """Backend PostgreSQL/PostGIS."""
    
    def execute_filter(self, layer, expression):
        # Utilise vues matérialisées
        create_materialized_view(layer, expression)
    
    def cleanup_temp_resources(self, datasource):
        # Supprime vues matérialisées
        drop_temp_views(datasource)
```

**adapters/backends/spatialite/backend.py** :
```python
class SpatialiteBackend(BackendServicePort):
    """Backend Spatialite/GeoPackage."""
    
    def execute_filter(self, layer, expression):
        # Utilise tables temporaires
        create_temp_table(layer, expression)
    
    def cleanup_temp_resources(self, datasource):
        # Supprime tables temporaires
        drop_temp_tables(datasource)
```

---

## Guide d'utilisation

### Sélection automatique

**Auto Backend Selector** (recommandé) :

```python
from core.optimization.auto_backend_selector import AutoBackendSelector

selector = AutoBackendSelector()
recommendation = selector.recommend_backend(
    layer,
    spatial_filter=True,
    complex_expression=False
)

print(f"Backend: {recommendation.backend}")  # 'postgresql'
print(f"Raison: {recommendation.reason}")    # 'Large dataset with spatial filter'
print(f"Confiance: {recommendation.confidence}")  # 0.95
```

### Sélection manuelle

```python
from adapters.backend_registry import BackendRegistry

# Récupérer backend pour une couche
backend = BackendRegistry.get_backend(layer)

# Forcer un backend spécifique
backend = BackendRegistry.get_backend_by_name('spatialite')

# Vérifier disponibilité
if BackendRegistry.is_backend_available('postgresql'):
    backend = BackendRegistry.get_backend_by_name('postgresql')
else:
    backend = BackendRegistry.get_backend_by_name('spatialite')  # Fallback
```

### Actions communes

```python
# Réinitialiser filtre (tous backends)
success, message = backend.execute_reset_action(
    layer,
    "reset",
    layer_props,
    datasource_info
)

# Restaurer filtre précédent (tous backends)
success, message = backend.execute_unfilter_action(
    layer,
    "unfilter",
    layer_props,
    datasource_info,
    previous_subset='"id" > 100'
)

# Nettoyer ressources temporaires (backend-spécifique)
cleanup_count = backend.cleanup_temp_resources(datasource_info)
```

---

## Patterns et bonnes pratiques

### Pattern 1 : Vérification de disponibilité

```python
from adapters.backends.postgresql_availability import POSTGRESQL_AVAILABLE

if POSTGRESQL_AVAILABLE:
    # Utiliser PostgreSQL
    import psycopg2
    conn = psycopg2.connect(...)
else:
    # Fallback Spatialite
    import sqlite3
    conn = sqlite3.connect(...)
```

### Pattern 2 : Gestion des erreurs

```python
try:
    success, message = backend.execute_filter(layer, expression)
    if not success:
        iface.messageBar().pushWarning("FilterMate", message)
except Exception as e:
    logger.error(f"Backend error: {e}")
    iface.messageBar().pushCritical("FilterMate", f"Erreur: {e}")
```

### Pattern 3 : Optimisation multi-étapes

```python
from core.optimization.multi_step_filter import MultiStepFilterOptimizer

optimizer = MultiStepFilterOptimizer()
steps = optimizer.decompose_filter(
    layer,
    complex_expression,
    backend='spatialite'
)

for step in steps:
    logger.info(f"Étape {step.order}: {step.type} - {step.expression}")
    logger.info(f"  Reduction estimée: {step.estimated_reduction_pct}%")
```

### Pattern 4 : Cache Exploring

```python
from infrastructure.cache.exploring_cache import ExploringFeaturesCache

cache = ExploringFeaturesCache.get_instance()

# Vérifier cache avant requête
features = cache.get(cache_key)
if features is None:
    # Cache miss - exécuter requête
    features = layer.getFeatures(request)
    cache.set(cache_key, features, ttl=300)
else:
    logger.info(f"Cache hit - {len(features)} features")
```

---

## Performance

### Benchmarks (FilterMate v4.1)

Temps d'exécution moyen (filtres spatiaux) :

| Taille dataset | PostgreSQL | Spatialite | OGR | Recommandé |
|----------------|------------|------------|-----|------------|
| **1k entities** | 120ms | 80ms | 60ms | OGR |
| **10k entities** | 250ms | 450ms | 3s | PostgreSQL |
| **50k entities** | 800ms | 4.5s | 45s | PostgreSQL |
| **100k entities** | 1.5s | 18s | timeout | PostgreSQL |

### Optimisations v4.1

1. **Auto Backend Selector** : Choix intelligent (-40% temps moyen)
2. **Multi-Step Filter** : Décomposition spatiale → attributaire (-60% filtres complexes)
3. **Exploring Cache** : TTL 300s, hit rate ~65% (-80% requêtes répétées)
4. **Async Evaluation** : Background tasks >10k entités (UI non-bloquante)

### Conseils

✅ **PostgreSQL** : Toujours avec indexes spatiaux + VACUUM ANALYZE  
✅ **Spatialite** : Créer R-tree sur géométries (`CreateSpatialIndex`)  
✅ **Cache** : Ajuster TTL selon taux de modification données  
✅ **Multi-Step** : Activer pour filtres avec >3 conditions

---

## Extensibilité

### Ajouter un nouveau backend

**Étape 1** : Implémenter l'interface

```python
# adapters/backends/mongodb/backend.py
from core.ports.backend_services import BackendServicePort

class MongoDBBackend(BackendServicePort):
    """Backend MongoDB avec géospatial queries."""
    
    def execute_filter(self, layer, expression):
        # Convertir QGIS expression → MongoDB query
        mongo_query = self._convert_expression(expression)
        # Exécuter requête
        collection.find(mongo_query)
    
    def execute_reset(self, layer):
        layer.setSubsetString("")
    
    # ... autres méthodes
```

**Étape 2** : Enregistrer dans le registre

```python
# adapters/backend_registry.py
BACKEND_MAP = {
    'postgres': PostgreSQLBackend,
    'spatialite': SpatialiteBackend,
    'ogr': OGRBackend,
    'mongodb': MongoDBBackend,  # NOUVEAU
}
```

**Étape 3** : Créer tests

```python
# tests/backends/test_mongodb_backend.py
class TestMongoDBBackend(unittest.TestCase):
    def test_filter_execution(self):
        backend = MongoDBBackend()
        success, msg = backend.execute_filter(layer, expression)
        self.assertTrue(success)
```

### Hooks d'extension

FilterMate supporte des hooks pour plugins tiers :

```python
# Dans votre plugin QGIS
from filter_mate.adapters.backend_registry import BackendRegistry

# Enregistrer backend custom
BackendRegistry.register_backend('mybackend', MyCustomBackend)

# Utiliser
backend = BackendRegistry.get_backend_by_name('mybackend')
```

---

## FAQ

**Q : Comment forcer PostgreSQL même pour petits datasets ?**  
R : Définir `ENV_VARS['FORCE_POSTGRESQL'] = True` dans config/config.py

**Q : Spatialite ne trouve pas mod_spatialite ?**  
R : Windows → vérifier `mod_spatialite.dll` dans PATH QGIS  
   Linux → installer `libspatialite` (apt/yum)

**Q : OGR est-il vraiment utile ?**  
R : Oui pour formats non-DB (Shapefile, GeoJSON) et petits datasets portables

**Q : Peut-on mixer backends ?**  
R : Non recommandé. FilterMate choisit 1 backend/couche. Mixing = incohérences.

**Q : Performance dégradée après mise à jour ?**  
R : Vider cache (`rm -rf .qgis3/cache/filter_mate/`)  
   Recréer indexes spatiaux si Spatialite

---

## Ressources

- **Code source** : [/adapters/backends/](../adapters/backends/)
- **Tests** : [/tests/backends/](../../tests/backends/)
- **Changelog** : [CHANGELOG.md](../../CHANGELOG.md)
- **Issues GitHub** : https://github.com/simonimani/filter_mate/issues

---

**Dernière mise à jour** : 2025-01-17  
**Auteur** : FilterMate Team  
**Licence** : Voir LICENSE
