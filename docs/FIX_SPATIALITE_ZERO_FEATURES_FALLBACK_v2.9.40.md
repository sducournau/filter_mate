# Fix: Spatialite Zero Features Fallback (v2.9.40)

**Date**: 2026-01-07  
**Issue**: Spatialite retourne 0 features de manière incorrecte sans déclencher le fallback OGR  
**Status**: ✅ RÉSOLU

## 🐛 Problème

Selon les logs de production, quand Spatialite exécute un filtre spatial :

1. **Premier filtre** (avec erreur SQL MakeValid) :
   - Spatialite échoue avec `MakeValid error - RTTOPO reports: Unknown Reason`
   - Retourne `False` → **OGR fallback activé** → ✅ **268 features trouvés**

2. **Deuxième filtre** (query réussit mais retourne 0) :
   - Spatialite query SQL **réussit** (pas d'exception)
   - Retourne **0 FIDs** de manière incorrecte
   - Retourne `True` → **AUCUN fallback** → ❌ **0 features** (mauvais résultat)

### Logs démontrant le problème

```
# Premier filtre - Spatialite échoue, OGR réussit
2026-01-07T12:52:20 WARNING _apply_filter_direct_sql SQL ERROR for demand_points: MakeValid error - RTTOPO reports: Unknown Reason
2026-01-07T12:52:20 INFO apply_filter: _apply_filter_direct_sql returned False for demand_points
2026-01-07T12:52:20 INFO 🔄 demand_points: Attempting OGR fallback...
2026-01-07T12:52:20 INFO selectbylocation result: 268 features selected on demand_points

# Deuxième filtre - Spatialite retourne 0 sans fallback
2026-01-07T12:53:34 INFO → Direct SQL found 0 matching FIDs for demand_points
2026-01-07T12:53:34 INFO apply_filter: _apply_filter_direct_sql returned True for demand_points
2026-01-07T12:53:40 WARNING ⚠️ demand_points → 0 features (filter may be too restrictive or expression error)
```

**Analyse** :
- Le deuxième filtre utilise une géométrie différente (LineString au lieu de MultiPolygon)
- Spatialite génère une query SQL qui retourne 0 FIDs **sans erreur**
- Aucun fallback n'est déclenché car `apply_filter()` retourne `True`
- Le même filtre avec OGR aurait potentiellement trouvé des features

## 🔧 Solution Implémentée

### 1. Fallback automatique dans `_apply_filter_direct_sql`

**Fichier**: `modules/backends/spatialite_backend.py`  
**Méthode**: `_apply_filter_direct_sql()`  
**Ligne**: ~3487

```python
if len(matching_fids) == 0:
    # v2.9.40: FALLBACK - When Spatialite returns 0 features, trigger OGR fallback
    
    # Check if this is a multi-step filter continuation (already has cache)
    is_multistep_continuation = False
    if SPATIALITE_CACHE_AVAILABLE and old_subset:
        # Get previous filter to check if this is a multi-step continuation
        previous_fids = get_previous_filter_fids(layer, source_wkt, buffer_val, predicates_list)
        is_multistep_continuation = (previous_fids is not None and len(previous_fids) > 0)
    
    # If NOT a multi-step continuation, return False to trigger OGR fallback
    if not is_multistep_continuation:
        self.log_warning(f"⚠️ Spatialite returned 0 features - this may indicate query error")
        self.log_warning(f"  → Returning False to trigger OGR fallback verification")
        QgsMessageLog.logMessage(
            f"⚠️ {layer.name()}: Spatialite found 0 features - attempting OGR fallback",
            "FilterMate", Qgis.Warning
        )
        return False  # ← Trigger OGR fallback
    
    # Multi-step continuation with 0 results - valid (empty intersection)
    fid_expression = 'fid = -1'
    self.log_info(f"  → Multi-step filter resulted in 0 features (valid empty intersection)")
```

### 2. Fallback automatique dans `_apply_filter_with_source_table`

**Fichier**: `modules/backends/spatialite_backend.py`  
**Méthode**: `_apply_filter_with_source_table()`  
**Ligne**: ~4323

```python
if len(matching_fids) == 0:
    # v2.9.40: FALLBACK - When Spatialite returns 0 features, trigger OGR fallback
    
    # Check if negative buffer produced empty geometry (valid case)
    is_negative_buffer_empty = False
    # ... (code to check for negative buffer)
    
    # Check if multi-step continuation (valid case)
    is_multistep_continuation = False
    # ... (code to check for previous cache)
    
    # v2.9.40: Trigger OGR fallback for ALL 0-feature results
    # UNLESS it's a valid case (negative buffer OR multi-step)
    if not is_negative_buffer_empty and not is_multistep_continuation:
        self.log_warning(f"⚠️ Spatialite returned 0 features for {layer.name()}")
        QgsMessageLog.logMessage(
            f"⚠️ {layer.name()}: Spatialite returned 0/{feature_count:,} features - falling back to OGR",
            "FilterMate", Qgis.Warning
        )
        self._spatialite_zero_result_fallback = True  # ← Flag pour filter_task.py
        return False  # ← Trigger OGR fallback
    
    # Valid 0-result case
    fid_expression = 'fid = -1'
```

### 3. Détection améliorée dans filter_task.py

Le code existant dans `filter_task.py` détecte déjà le flag `_spatialite_zero_result_fallback` :

```python
# Ligne 7706
zero_result_fallback = getattr(backend, '_spatialite_zero_result_fallback', False)

# Ligne 7741
if zero_result_fallback:
    logger.warning(f"⚠️ SPATIALITE returned 0 features on large dataset {layer.name()}")
    logger.warning(f"  → Falling back to OGR for reliable feature-by-feature filtering")
```

## 📊 Cas gérés

| Cas | Résultat Spatialite | Fallback OGR ? | Raison |
|-----|-------------------|---------------|---------|
| **Query réussit, 0 FIDs, pas de cache** | 0 features | ✅ **OUI** | Potentielle erreur de query |
| **Query réussit, 0 FIDs, multi-step continuation** | 0 features | ❌ NON | Intersection vide valide |
| **Query réussit, 0 FIDs, buffer négatif vide** | 0 features | ❌ NON | Géométrie vide normale |
| **Query échoue avec exception SQL** | False | ✅ **OUI** | Erreur SQL claire |
| **Query réussit, N features > 0** | N features | ❌ NON | Résultat normal |

## 🎯 Avantages

1. **Robustesse** : Détecte les faux négatifs Spatialite et essaie OGR
2. **Précision** : Évite les filtres qui retournent 0 features de manière incorrecte
3. **Transparent** : L'utilisateur voit le fallback dans les logs
4. **Performant** : N'active pas le fallback pour les cas légitimes (multi-step, buffer négatif)

## ⚠️ Exceptions à la règle

Le fallback **N'EST PAS** déclenché dans ces cas (0 features est attendu) :

### 1. Multi-step filtering (filtrage progressif)

Quand un utilisateur applique plusieurs filtres successifs :
- Filtre 1 : 100 features trouvés → cache stocké
- Filtre 2 : 0 features (intersection avec cache)  
→ **0 est valide** (l'intersection des deux filtres est vide)

### 2. Buffer négatif (érosion)

Buffer négatif sur une feature fine :
- Source : ligne de 2m de largeur
- Buffer : -5m (érosion de 5 mètres)  
→ **Géométrie vide** (la ligne disparaît complètement)  
→ **0 features est normal**

## 📝 Messages de log ajoutés

### Fallback déclenché
```
WARNING ⚠️ Spatialite returned 0 features - this may indicate query error
WARNING   → Returning False to trigger OGR fallback verification
WARNING ⚠️ demand_points: Spatialite found 0 features - attempting OGR fallback
INFO    🔄 demand_points: Attempting OGR fallback...
```

### Cas valide (multi-step)
```
INFO      → Multi-step filter resulted in 0 features (valid empty intersection)
```

### Cas valide (buffer négatif)
```
INFO    ℹ️ 0 features matched for sheaths (negative buffer made geometry empty - valid)
```

## 🧪 Tests suggérés

1. **Test avec géométrie complexe** :
   - Filtre avec MultiPolygon de 35KB (comme dans les logs)
   - Vérifier que OGR trouve des features si Spatialite retourne 0

2. **Test multi-step** :
   - Appliquer filtre 1 → N features
   - Appliquer filtre 2 sur résultat → 0 features
   - Vérifier que le fallback n'est PAS déclenché

3. **Test buffer négatif** :
   - Ligne fine avec buffer -10m
   - Vérifier géométrie vide est acceptée sans fallback

## 🔗 Fichiers modifiés

- `modules/backends/spatialite_backend.py`
  - Méthode `_apply_filter_direct_sql()` (ligne ~3487)
  - Méthode `_apply_filter_with_source_table()` (ligne ~4323)

## 📚 Références

- Issue log : User request du 2026-01-07 12:51:43-12:53:40
- Logs de production montrant le problème
- Documentation Spatialite : https://www.gaia-gis.it/fossil/libspatialite/
- QGIS processing : `native:selectbylocation`

---

**Version**: v2.9.40  
**Auteur**: GitHub Copilot  
**Date**: 2026-01-07
