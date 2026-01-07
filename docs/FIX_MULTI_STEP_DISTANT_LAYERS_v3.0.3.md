# Fix: Multi-Step Filter - Distant Layers Not Filtered (v3.0.3)

**Date**: 2026-01-07  
**Criticité**: 🔴 **CRITIQUE**  
**Issue**: Step 2 filters only source layer, distant layers keep ALL features instead of intersection

---

## 🐛 Problème Critique

**Symptôme** :
- Step 1 (batiment): demand_points = 319 features ✅
- Step 2 (ducts): demand_points = 0 features (Spatialite) → 9231 features (OGR fallback) ❌

**Attendu** : Intersection des 2 steps (319 ∩ X features du step 2)  
**Réel** : Step 2 remplace complètement step 1, perd le filtre FID

**Affecté** : Toutes les couches distantes en filtrage multi-étapes avec changement de source

---

## 🔍 Root Cause Analysis

### Flux du Problème

**Step 1**: Filter batiment (Polygon) → `demand_points`: `fid IN (1771, 1772, ...)`  
**Step 2**: Filter ducts (LineString) → Source géométrique différente

#### Backend Spatialite (`_apply_filter_direct_sql`)

**Ancien code (v2.9.34-v3.0.2)** :
```python
is_fid_only = bool(re.match(r'fid\s+(IN\s*\(|=)', old_subset))

if not has_source_alias and not has_exists and not has_spatial_predicate and not is_fid_only:
    old_subset_sql_filter = f"({old_subset}) AND "  # Combine attribute filter
elif is_fid_only:
    old_subset_sql_filter = ""  # ❌ SKIP FID filter - WRONG!
```

**Résultat** :
```sql
-- Step 2 query (❌ INCORRECT):
SELECT "fid" FROM "demand_points" 
WHERE ST_Intersects(...)  -- Pas de fid IN (...) !
```

**Impact** : Query ALL features matching new spatial filter, ignore step 1 FID filter.

---

## ✅ Solution v3.0.3

### Fix Spatialite Backend

**Nouveau code** :
```python
is_fid_only = bool(re.match(r'fid\s+(IN\s*\(|=)', old_subset))

# v3.0.3: FID filters MUST be combined in multi-step filtering!
if not has_source_alias and not has_exists and not has_spatial_predicate:
    # Combine BOTH attribute filters AND FID filters
    old_subset_sql_filter = f"({old_subset}) AND "
    
    if is_fid_only:
        self.log_info("✅ Combining FID filter from step 1 with new spatial filter (MULTI-STEP)")
        self.log_info(f"  → This ensures intersection of step 1 AND step 2 results")
```

**Résultat correct** :
```sql
-- Step 2 query (✅ CORRECT):
SELECT "fid" FROM "demand_points" 
WHERE (fid IN (1771, 1772, ...)) AND ST_Intersects(...)
```

**Impact** : Query only features matching BOTH step 1 FID filter AND step 2 spatial filter = intersection!

---

## 📋 Fichiers Modifiés

1. **modules/backends/spatialite_backend.py**
   - `_apply_filter_direct_sql()` (ligne ~3315)
   - `_apply_filter_with_source_table()` (ligne ~4110)
   - **Fix** : Remove `and not is_fid_only` condition
   - **Result** : FID filters now combined instead of replaced

---

## 🧪 Tests de Validation

### Scénario 1: Multi-Step avec Changement de Source

**Setup** :
1. Step 1: Filter batiment (Polygon) + buffer 1m
2. Step 2: Filter ducts (LineString) + buffer 1m

**Résultat Attendu** :
- demand_points: Intersection step 1 ∩ step 2 (PAS ALL features)
- sheaths: Intersection step 1 ∩ step 2
- Autres layers: Intersection step 1 ∩ step 2

**Logs Attendus** :
```
✅ Combining FID filter from step 1 with new spatial filter (MULTI-STEP)
  → FID filter: fid IN (1771, 1772, ...)
  → This ensures intersection of step 1 AND step 2 results
```

### Scénario 2: Multi-Step Même Source, Buffer Différent

**Setup** :
1. Step 1: Filter batiment + buffer 0.5m
2. Step 2: Filter batiment (MÊME source) + buffer 1.5m

**Résultat Attendu** :
- Step 2 remplace step 1 (source identique mais buffer différent)
- Cache détecte hash mismatch → skip intersection

---

## 📊 Impact Avant/Après

| Aspect | Avant v3.0.2 | Après v3.0.3 |
|--------|-------------|--------------|
| **Step 1 Results** | ✅ Correct | ✅ Correct |
| **Step 2 Distant Layers** | ❌ ALL features (wrong) | ✅ Intersection (correct) |
| **Logging** | "will be REPLACED" | "Combining FID filter (MULTI-STEP)" |
| **SQL Query** | Missing `fid IN (...)` | ✅ Includes `fid IN (...)` |

---

## 🔗 Contexte

### Pourquoi ce Bug Existait (v2.9.34)

**Intent Original** (v2.9.34) :
- Éviter de combiner des filtres FID de sources géométriques différentes
- **Logique** : "Source a changé → FID filter n'est plus valide → REMPLACER"

**Erreur de Logique** :
- Pour les **couches DISTANTES**, le FID filter du step 1 est toujours VALIDE
- Il représente les features qui ont intersecté la géométrie du step 1
- Step 2 doit filtrer PARMI ces features, pas toutes les features de la table

**Correction** :
- FID filters = "résultats du step précédent"
- Toujours les combiner en multi-step, peu importe si source a changé
- Seuls les filtres SPATIAUX (ST_*, EXISTS) doivent être remplacés

---

## 📝 Documentation Associée

- `docs/BUG_SPATIALITE_MULTI_STEP_FILTERING_v2.9.33.md` : Analyse initiale
- `docs/FIX_SECOND_FILTER_LIST_LOAD_v2.9.44.md` : Fix précédent (UI)
- **NOUVEAU** : `docs/FIX_MULTI_STEP_DISTANT_LAYERS_v3.0.3.md` (ce document)

---

**Version** : 3.0.3  
**Date** : 2026-01-07  
**Status** : ✅ READY FOR TESTING
