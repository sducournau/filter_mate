# Fix en cours : Spatialite Multi-Step Filtering

**Date** : 2026-01-07  
**Version** : v2.9.33 (debug)  
**Fichiers modifiés** :
- `modules/backends/spatialite_backend.py`
- `docs/BUG_SPATIALITE_MULTI_STEP_FILTERING_v2.9.33.md` (nouveau)

## 🐛 Problème

Lors d'un filtre géométrique en 2 étapes avec changement de couche source :

**Étape 1** : Batiment (simple sélection) + buffer 1m  
→ ✅ Couches distantes filtrées : demand_points (319), ducts (1129), etc.

**Étape 2** : Ducts (sélection multiple) + buffer 1m  
→ ❌ Couches distantes retournent 0 features au lieu d'intersecter avec étape 1

## 🔍 Analyse

Le cache Spatialite détecte correctement le changement de géométrie source et skip l'intersection automatique. **MAIS** le `old_subset` (filtre FID du step 1) devrait être combiné manuellement avec la nouvelle requête SQL.

**Hypothèse** : `old_subset` n'est pas passé correctement au backend ou n'est pas détecté comme "simple filter".

## 🛠️ Actions

### 1. Documentation du Bug
Création de `BUG_SPATIALITE_MULTI_STEP_FILTERING_v2.9.33.md` avec :
- Symptômes détaillés
- Analyse technique du flux
- Root cause potentiel
- Solutions proposées

### 2. Logs de Debug Ajoutés

Dans `spatialite_backend.py:_apply_filter_direct_sql()` (autour ligne 3247) :

```python
# Debug old_subset
QgsMessageLog.logMessage(
    f"🔍 DEBUG _apply_filter_direct_sql for {layer.name()}:",
    "FilterMate", Qgis.Info
)
QgsMessageLog.logMessage(
    f"  → old_subset type: {type(old_subset)}, is None: {old_subset is None}",
    "FilterMate", Qgis.Info
)
if old_subset:
    QgsMessageLog.logMessage(
        f"  → old_subset length: {len(old_subset)}",
        "FilterMate", Qgis.Info
    )
    QgsMessageLog.logMessage(
        f"  → old_subset preview: '{old_subset[:200]}'...",
        "FilterMate", Qgis.Info
    )

# Detection results
QgsMessageLog.logMessage(
    f"  → Detection: has_source_alias={has_source_alias}, "
    f"has_exists={has_exists}, has_spatial_predicate={has_spatial_predicate}",
    "FilterMate", Qgis.Info
)

# Combination status
if old_subset_sql_filter:
    QgsMessageLog.logMessage(
        f"  ✓ COMBINING with old_subset (simple filter)",
        "FilterMate", Qgis.Info
    )
else:
    QgsMessageLog.logMessage(
        f"  ⚠️ REPLACING old_subset or no old_subset",
        "FilterMate", Qgis.Info
    )
```

Également ajouté après construction de `select_query` :
```python
if old_subset_sql_filter:
    QgsMessageLog.logMessage(
        f"  ✓ Query INCLUDES previous filter (old_subset combined)",
        "FilterMate", Qgis.Info
    )
else:
    QgsMessageLog.logMessage(
        f"  ⚠️ Query does NOT include previous filter (new filter only)",
        "FilterMate", Qgis.Info
    )
```

## 📋 Tests Nécessaires

1. **Reproduire le bug** avec logs activés
2. **Vérifier dans QGIS Python Console** :
   ```
   - Valeur exacte de `old_subset`
   - Résultat des tests booléens
   - Contenu de `old_subset_sql_filter`
   - Requête SQL finale
   ```

3. **Scénarios attendus** :
   
   **Cas A** : `old_subset` est passé et contient `fid IN (...)`  
   → Logs devraient montrer "COMBINING with old_subset"  
   → Requête devrait contenir `(fid IN (...)) AND (ST_Intersects(...))`
   
   **Cas B** : `old_subset` est `None` ou vide  
   → **BUG CONFIRMÉ** : le subset n'est pas passé correctement  
   → Fix : S'assurer que `layer.subsetString()` est bien récupéré avant appel backend

## 🎯 Prochaines Étapes

1. ✅ Logs de debug ajoutés
2. ⏳ **User testera et fournira les logs**
3. ⏳ Analyser les logs pour confirmer l'hypothèse
4. ⏳ Implémenter le fix approprié :
   - Si `old_subset` est vide → Fix dans `filter_task.py` pour récupérer le subset
   - Si détection échoue → Améliorer la logique de détection
   - Si `GEOMFROMGPB` pose problème → Retirer de la liste des spatial predicates

## 💡 Solutions Potentielles

### Solution 1 : Force FID Detection
```python
is_fid_filter = (
    old_subset and 
    bool(re.search(r'\bfid\s+(IN|=)', old_subset, re.IGNORECASE)) and
    not has_spatial_predicate
)

if is_fid_filter:
    old_subset_sql_filter = f"({old_subset}) AND "
```

### Solution 2 : Whitelist Simple Filters
```python
# Only treat as "simple" if it's a clear attribute filter
is_simple_attribute_filter = (
    old_subset and
    not has_source_alias and
    not has_exists and
    not has_spatial_predicate and
    # Additional safety: must not contain geometry functions
    'GEOM' not in old_subset_upper
)
```

### Solution 3 : Log Warning on Skip
```python
if has_spatial_predicate:
    # Identify which predicate caused the skip
    found_predicates = [p for p in spatial_predicates if p in old_subset_upper]
    QgsMessageLog.logMessage(
        f"  ⚠️ old_subset contains spatial predicates: {found_predicates}",
        "FilterMate", Qgis.Warning
    )
```

---

**Status** : 🟡 EN ATTENTE DE RETOUR UTILISATEUR avec logs de debug
