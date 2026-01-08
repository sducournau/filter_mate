# Bug Analysis: Spatialite Multi-Step Filtering with Geometry Change

**Date**: 2026-01-07  
**Version**: FilterMate v2.9.33  
**Reporter**: User (sducournau)

## 📋 Symptômes

Lors d'un second filtre géométrique en mode Spatialite avec **changement de source** :

1. **Premier filtre** : Sélection simple batiment + buffer 1m → OK  
2. **Second filtre** : Sélection **MULTIPLE** ducts + buffer 1m → **ÉCHEC (0 features)**

**Logs clés** :
```
11:40:13  INFO  Cache SKIP: demand_points → source geometry changed (hash mismatch)
11:40:13  INFO   → Direct SQL found 0 matching FIDs for demand_points
```

## 🔍 Analyse Technique

### Flux Normal (Premier Filtre)

```
Batiment (source) + buffer 1m + intersects
├─ demand_points: 319 features  ✅
├─ ducts: 1129 features         ✅
├─ sheaths: 828 features        ✅
└─ structures: 613 features     ✅
```

**Subset après filtre** : `fid IN (1771, 1772, 1773, ...)`

### Flux Problématique (Second Filtre)

```
Ducts sélection multiple (source) + buffer 1m + intersects
├─ demand_points: 0 features    ❌ (devrait intersecter avec step 1)
├─ sheaths: 0 features          ❌
├─ structures: 0 features       ❌
└─ subducts: 0 features         ❌
```

**Cause** : Les couches distantes ne combinent PAS leur filtre FID du step 1

## 🐛 Root Cause

### 1. Cache Invalidation Correcte

`spatialite_cache.py:491-498`
```python
if current_geom_hash != cached_geom_hash:
    return None  # Different source geometry, don't intersect
```

✅ **OK** : Le cache détecte correctement le changement de géométrie source  
  - Step 1 : source = batiment (Polygon)
  - Step 2 : source = ducts (MultiLineString)
  - → Pas d'intersection de cache (correct)

### 2. old_subset Récupération

`filter_task.py:7608`
```python
old_subset = layer.subsetString() if layer.subsetString() != '' else None
```

✅ **OK** : Récupère le subset actuel (`fid IN (...)`)

### 3. old_subset Détection de Type

`filter_task.py:7620-7646`
```python
is_geometric_filter = (
    '__source' in old_subset.lower() or
    'EXISTS (' in old_subset_upper or
    any(pred in old_subset_upper for pred in ['ST_INTERSECTS', ...])
)

if is_geometric_filter:
    old_subset = None  # REPLACE
else:
    # COMBINE
```

✅ **OK** : Un filtre FID ne contient pas de prédicats spatiaux  
  → Devrait être préservé et combiné

### 4. Backend Combination Logic

`spatialite_backend.py:3247-3265`
```python
old_subset_sql_filter = ""
if old_subset:
    has_spatial_predicate = any(pred in old_subset_upper for pred in [
        'ST_INTERSECTS', 'ST_CONTAINS', 'GEOMFROMTEXT', 'GEOMFROMGPB', ...
    ])
    
    if not has_source_alias and not has_exists and not has_spatial_predicate:
        old_subset_sql_filter = f"({old_subset}) AND "
```

**❌ PROBLÈME ICI** : Le filtre FID devrait être combiné, mais ne l'est pas !

## 🔎 Investigation Nécessaire

**Hypothèses** :

1. ❓ `old_subset` est `None` ou vide lors de l'appel au backend ?
2. ❓ La détection de `has_spatial_predicate` échoue sur un filtre FID ?
3. ❓ `GEOMFROMGPB` apparaît dans la liste mais est présent dans `old_subset` ?

**Tests requis** :

```python
# Dans spatialite_backend.py:_apply_filter_direct_sql (avant ligne 3247)
QgsMessageLog.logMessage(
    f"🔍 DEBUG old_subset: '{old_subset[:200] if old_subset else 'None'}'",
    "FilterMate", Qgis.Info
)
QgsMessageLog.logMessage(
    f"🔍 DEBUG old_subset type: {type(old_subset)}, length: {len(old_subset) if old_subset else 0}",
    "FilterMate", Qgis.Info
)
```

## 🛠️ Solution Proposée

### Option 1: Logs Détaillés (Debug)

Ajouter des logs dans `spatialite_backend.py` pour confirmer :
- `old_subset` contenu exact
- Résultat de chaque test booléen
- Valeur de `old_subset_sql_filter`

### Option 2: Force Combination pour FID

```python
# Détection explicite de filtre FID
is_fid_filter = (
    old_subset and 
    ('fid IN' in old_subset_upper or 'fid =' in old_subset_upper) and
    not has_spatial_predicate
)

if is_fid_filter:
    old_subset_sql_filter = f"({old_subset}) AND "
    QgsMessageLog.logMessage(
        f"✓ FID filter detected - will be combined",
        "FilterMate", Qgis.Info
    )
```

### Option 3: Cache Intelligent avec Parameters

Au lieu de simplement skip cache sur geometry change, stocker les FIDs
même avec géométrie différente, mais ne PAS intersecter automatiquement.
Laisser le backend SQL combiner via `old_subset_sql_filter`.

## ✅ Tests de Validation

1. **Scenario 1** : Filter batiment → filter ducts
   - ✅ Couches distantes devraient avoir intersection des 2 filtres
   
2. **Scenario 2** : Filter ducts → filter ducts (même source, buffer change)
   - ✅ Devrait remplacer (buffer change détecté)
   
3. **Scenario 3** : Filter batiment → filter batiment (même source, buffer identique)
   - ✅ Devrait intersecter via cache

## 📊 Impact

**Criticité** : 🔴 **HAUTE**  
**Affectées** : Toutes les couches distantes en mode multi-step avec changement de source  
**Workaround** : Reset filtre avant d'appliquer un nouveau filtre

---

**Next Steps** :
1. Ajouter logs de debug dans `spatialite_backend.py:_apply_filter_direct_sql`
2. Tester avec données réelles
3. Implémenter fix approprié selon résultats
