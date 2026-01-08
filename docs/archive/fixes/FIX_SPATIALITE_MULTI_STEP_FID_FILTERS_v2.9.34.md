# Fix Multi-Step Filtering Spatialite Backend v2.9.34

**Date**: 7 janvier 2026
**Version**: v2.9.34
**Problème résolu**: Filtrage multi-étapes incorrect (tous les widgets sauf la source retournent 0 features)

## 🐛 Symptômes

Lors d'un filtrage multi-étapes avec le backend Spatialite (mode MULTIPLE_SELECTION) :
1. **Step 1** : Sélection d'une zone (polygone) → Filtrage correct de toutes les couches
2. **Step 2** : Sélection d'une feature (LineString avec buffer) → **Toutes les couches sauf la source retournent 0 features**

### Logs observés

**Step 1** (sélection polygone) :
```
Cache stored: demand_points → 319 FIDs (step 1, key=3b3a58a6)
Cache stored: ducts → 1129 FIDs (step 1, key=4c380d75)
Cache stored: sheaths → 828 FIDs (step 1, key=768f942b)
...
```

**Step 2** (sélection LineString avec buffer) :
```
→ old_subset_sql_filter: '(fid IN (1771, 1772, 1773, ...))'
✓ Query INCLUDES previous filter (old_subset combined)
→ Direct SQL found 0 matching FIDs for demand_points
→ Direct SQL found 0 matching FIDs for sheaths
→ Direct SQL found 0 matching FIDs for structures
...
```

## 🔍 Analyse du problème

### Cause racine

Dans le filtrage multi-étapes Spatialite :

1. **Step 1** : Le backend crée des filtres FID pour chaque couche basés sur l'intersection avec la géométrie source A (polygone)
   - `demand_points` → `fid IN (1771, 1772, ...)`  *(319 FIDs basés sur source A)*
   - `sheaths` → `fid IN (2533, 2535, ...)`  *(828 FIDs basés sur source A)*
   - etc.

2. **Step 2** : Le backend reçoit une nouvelle géométrie source B (LineString + buffer)
   - Le code récupère l'ancien filtre : `old_subset = layer.subsetString()`
   - Ancien filtre = `fid IN (1771, 1772, ...)` *(FIDs de la source A)*
   - Le backend combine l'ancien filtre FID avec le nouveau prédicat spatial basé sur la source B :
     ```sql
     SELECT fid FROM table 
     WHERE (fid IN (1771, 1772, ...))  -- FIDs de source A
       AND ST_Intersects(geom, source_B)  -- Prédicat basé sur source B
     ```
   - **Résultat** : Intersection vide car les FIDs de la source A ne correspondent pas nécessairement à la source B

### Erreur de logique

Le code considérait les filtres FID comme des "simple attribute filters" à **combiner** avec les nouveaux filtres spatiaux. 

Or, dans le contexte multi-étapes, ces filtres FID sont en réalité des **résultats de filtrage spatial précédent** basés sur une géométrie source différente, et doivent donc être **remplacés**, pas combinés.

## ✅ Solution implémentée

### 1. Détection des filtres FID-only dans filter_task.py

**Fichier** : `modules/tasks/filter_task.py`  
**Ligne** : ~7612

**Avant** :
```python
if old_subset:
    old_subset_upper = old_subset.upper()
    is_geometric_filter = ('__source' in old_subset.lower() or ...)
    
    if is_geometric_filter:
        old_subset = None  # REPLACE
    else:
        # Simple attribute filter - COMBINE
        pass
```

**Après** :
```python
if old_subset:
    old_subset_upper = old_subset.upper()
    is_geometric_filter = ('__source' in old_subset.lower() or ...)
    
    # v2.9.34: Detect FID-only filters from previous spatial steps
    import re
    is_fid_only_filter = bool(re.match(
        r'^\s*\(?\s*(["\']{0,1})fid\1\s+(IN\s*\(|=\s*-?\d+)', 
        old_subset, 
        re.IGNORECASE
    ))
    
    if is_geometric_filter:
        old_subset = None  # REPLACE
    elif is_fid_only_filter:
        # v2.9.34: Keep old_subset to trigger cache intersection
        # but set combine_operator=None to prevent SQL combination
        logger.info(f"🔄 FID filter - kept for cache, NOT combined in SQL")
        combine_operator = None  # Don't combine in SQL
    else:
        # True user attribute filter - COMBINE
        pass
```

**Pattern regex** : `^\s*\(?\s*(["']{0,1})fid\1\s+(IN\s*\(|=\s*-?\d+)`

**Stratégie** :
- `old_subset` est **conservé** (pas mis à None) pour déclencher l'intersection du cache
- `combine_operator` est mis à `None` pour que le backend ne combine PAS en SQL
- Le backend détecte déjà les FID-only et ne les combine pas (v2.9.34)

### 2. Détection dans le backend Spatialite

**Fichiers** : `modules/backends/spatialite_backend.py`  
**Méthodes** : 
- `_apply_filter_direct_sql` (ligne ~3289)
- `_apply_filter_with_source_table` (ligne ~3997)

**Avant** :
```python
if old_subset:
    has_spatial_predicate = any(pred in old_subset_upper for pred in [...])
    
    if not has_spatial_predicate:
        # Include FID filter in SQL
        old_subset_sql_filter = f"({old_subset}) AND "
    else:
        # Replace spatial predicate
        old_subset_sql_filter = ""
```

**Après** :
```python
if old_subset:
    has_spatial_predicate = any(pred in old_subset_upper for pred in [...])
    
    # v2.9.34: Check if FID-only filter
    import re
    is_fid_only = bool(re.match(
        r'^\s*\(?\s*(["\']{0,1})fid\1\s+(IN\s*\(|=\s*-?\d+)', 
        old_subset, 
        re.IGNORECASE
    ))
    
    if not has_spatial_predicate and not is_fid_only:
        # True attribute filter - COMBINE
        old_subset_sql_filter = f"({old_subset}) AND "
    elif is_fid_only:
        # v2.9.34: FID-only from previous step - REPLACE
        self.log_info(f"→ FID filter from previous spatial step - REPLACED")
        old_subset_sql_filter = ""
    else:
        # Spatial predicate - REPLACE
        old_subset_sql_filter = ""
```

## 📊 Résultats attendus

### Avant le fix

**Step 2** avec LineString + buffer :
```
demand_points   → 0 features  ❌
sheaths         → 0 features  ❌
structures      → 0 features  ❌
subducts        → 0 features  ❌
zone_distribution → 0 features  ❌
```

### Après le fix

**Step 2** avec LineString + buffer :
```
demand_points   → N features (intersection réelle)  ✅
sheaths         → M features (intersection réelle)  ✅
structures      → P features (intersection réelle)  ✅
subducts        → Q features (intersection réelle)  ✅
zone_distribution → R features (intersection réelle)  ✅
```

### Logs attendus

```
🔄 Existing subset on sheaths is FID filter from PREVIOUS spatial step - will be REPLACED
  → Existing: '(fid IN (2533, 2535, 2569, ...))'
  → Reason: FID filter from different source geometry (multi-step filtering)
  
→ old_subset_sql_filter: '(empty)'
⚠️ Query does NOT include previous filter (new filter only)
→ Direct SQL found 12 matching FIDs for sheaths  ✅
```

## 🧪 Tests recommandés

1. **Test multi-step basique** :
   - Step 1 : Sélectionner un grand polygone
   - Step 2 : Sélectionner une feature LineString avec buffer
   - Vérifier que toutes les couches retournent des résultats corrects

2. **Test avec filtre attributaire utilisateur** :
   - Appliquer manuellement un filtre attributaire : `importance > 5`
   - Step 1 : Sélectionner un polygone
   - Vérifier que le filtre attributaire est **préservé** (combiné avec AND)

3. **Test FID = -1** :
   - Simuler une couche avec filtre `fid = -1` (aucune feature)
   - Appliquer un nouveau filtre spatial
   - Vérifier que le `fid = -1` est **remplacé**

## 🔄 Impact sur les fonctionnalités existantes

### ✅ Préservées

- **Filtres attributaires utilisateurs** continuent d'être combinés avec AND
  - Exemple : `importance > 5` est préservé lors d'un filtrage spatial
  
- **Filtres géométriques complexes** continuent d'être remplacés
  - Exemple : `EXISTS (SELECT ...)` est remplacé lors d'un nouveau filtrage

### 🔧 Modifiées

- **Filtres FID simples** sont maintenant **remplacés** au lieu d'être combinés
  - **Avant** : `(fid IN (...)) AND ST_Intersects(...)` → 0 résultats
  - **Après** : `ST_Intersects(...)` → résultats corrects

## 📝 Notes de version

**v2.9.34** - Fix filtrage multi-étapes Spatialite
- FIX : Détection des filtres FID-only provenant d'étapes précédentes
- FIX : Remplacement au lieu de combinaison pour les filtres FID multi-step
- FIX : Logs améliorés pour différencier FID-only vs attributs utilisateurs
- IMPROVE : Regex pattern pour détecter tous les formats de FID filter

## 🔗 Références

- Issue reportée : 7 janvier 2026
- Documentation : `docs/BUG_SPATIALITE_MULTI_STEP_FILTERING_v2.9.33.md`
- Files modifiés :
  - `modules/tasks/filter_task.py` (ligne ~7612)
  - `modules/backends/spatialite_backend.py` (lignes ~3289, ~3997)
