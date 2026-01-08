# 🔴 ANALYSE CRITIQUE: Multi-Step Filtering avec OR/AND NOT

**Date:** 2026-01-07  
**Version:** 2.9.42+  
**Criticité:** 🟡 MOYENNE (feature manquante, pas de bug sur AND)

## 📋 Problème Identifié

La logique de **cache FID multi-step** dans `spatialite_cache.py` utilise **toujours une INTERSECTION** (`&`), ce qui ne fonctionne correctement que pour l'opérateur `AND`.

**Les opérateurs `OR` et `AND NOT` ne sont PAS supportés** pour le filtrage multi-étapes avec cache.

## 🔍 Analyse Technique

### Opérateurs Supportés par FilterMate

D'après `filter_task.py:6272-6310`, FilterMate supporte:

| Opérateur | Signification | QGIS METHOD | Logique FID |
|-----------|---------------|-------------|-------------|
| `AND` | Intersection | 2 | `previous & new` |
| `OR` | Union | 1 | `previous \| new` |
| `NOT AND` | Différence | 3 | `previous - new` |
| (aucun) | Nouvelle sélection | 0 | `new` (replace) |

### Code Actuel (spatialite_cache.py:560)

```python
def intersect_with_previous(self, ...):
    """Intersect new FIDs with previously cached FIDs for multi-step filtering."""
    # ...
    if previous_fids is not None:
        # ❌ PROBLÈME: Toujours intersection (AND uniquement)
        intersected = new_fids & previous_fids
        return intersected, prev_step + 1
    
    return new_fids, 1
```

**Ce code ne gère que AND !**

### Impact

#### Scénario 1: Utilisateur choisit OR
```
Filtre 1: Sélection zone A → FIDs: {1, 2, 3}
Filtre 2 (OR): Sélection zone B → FIDs: {4, 5, 6}

✅ ATTENDU: {1, 2, 3} | {4, 5, 6} = {1, 2, 3, 4, 5, 6}
❌ ACTUEL:  {1, 2, 3} & {4, 5, 6} = {} (vide!)
```

#### Scénario 2: Utilisateur choisit AND NOT
```
Filtre 1: Sélection zone A → FIDs: {1, 2, 3, 4, 5}
Filtre 2 (NOT AND): Retirer zone B → FIDs: {3, 4, 5}

✅ ATTENDU: {1, 2, 3, 4, 5} - {3, 4, 5} = {1, 2}
❌ ACTUEL:  {1, 2, 3, 4, 5} & {3, 4, 5} = {3, 4, 5} (inverse!)
```

## 🎯 Solution Proposée

### Option 1: Désactiver le Cache pour OR/AND NOT (RAPIDE)

**Avantage:** Simple, pas de risque d'erreur  
**Inconvénient:** Perte de performance pour ces opérateurs

```python
# Dans filter_task.py:7660
if is_fid_only_filter:
    # Vérifier l'opérateur
    current_operator = self._get_combine_operator()
    
    if current_operator in ('OR', 'NOT AND'):
        # OR/AND NOT non supportés avec cache → REPLACE filter
        logger.warning(f"⚠️ Multi-step with {current_operator} - cache not supported, replacing filter")
        old_subset = None  # Force replace
    else:
        # AND supporté avec cache
        logger.info(f"🔄 Existing subset is FID filter - cache intersection with {current_operator}")
        combine_operator = None  # Signal REPLACE in SQL
```

### Option 2: Implémenter OR/AND NOT dans le Cache (COMPLET)

**Avantage:** Support complet, performance optimale  
**Inconvénient:** Plus complexe, nécessite tests approfondis

```python
# Dans spatialite_cache.py
def combine_with_previous(
    self,
    layer,
    new_fids: Set[int],
    operator: str = 'AND',  # 'AND', 'OR', 'NOT AND'
    # ... autres params
) -> Tuple[Set[int], int]:
    """
    Combine new FIDs with previous using specified operator.
    """
    previous_fids = self.get_previous_fids(...)
    
    if previous_fids is not None:
        if operator == 'AND':
            combined = previous_fids & new_fids  # Intersection
        elif operator == 'OR':
            combined = previous_fids | new_fids  # Union
        elif operator == 'NOT AND':
            combined = previous_fids - new_fids  # Différence
        else:
            combined = new_fids  # Replace
        
        return combined, prev_step + 1
    
    return new_fids, 1
```

### Option 3: Validation Stricte (CONSERVATEUR)

**Avantage:** Sécuritaire, évite les erreurs silencieuses  
**Inconvénient:** Pas de support pour OR/AND NOT

```python
# Dans backends (spatialite, ogr)
if SPATIALITE_CACHE_AVAILABLE and old_subset:
    current_operator = self._get_combine_operator()
    
    if current_operator in ('OR', 'NOT AND'):
        # Cache non supporté pour ces opérateurs
        self.log_warning(f"⚠️ Cache FID multi-step not supported for {current_operator}")
        self.log_warning(f"   Skipping cache intersection")
        # Continuer sans cache (pas d'intersection)
    else:
        # AND supporté - utiliser cache
        matching_fids_set, step_number = intersect_filter_fids(...)
```

## 📊 Recommandation

**COURT TERME (v2.9.43):** Option 1 ou 3  
- Désactiver/avertir pour OR/AND NOT  
- Documenter la limitation
- Garantir que AND fonctionne correctement

**MOYEN TERME (v2.10.x):** Option 2  
- Implémenter support complet OR/AND NOT
- Tests unitaires pour tous les opérateurs
- Migration progressive

## 🧪 Tests Requis

### Scénarios de Test

1. **AND (doit fonctionner):**
   ```
   Filtre 1: Zone A → 100 features
   Filtre 2 (AND): Zone B → 150 features
   Résultat: Intersection ~50 features ✅
   ```

2. **OR (actuellement bugué):**
   ```
   Filtre 1: Zone A → 100 features
   Filtre 2 (OR): Zone B → 150 features
   Résultat actuel: 0 features ❌
   Résultat attendu: Union ~250 features
   ```

3. **NOT AND (actuellement bugué):**
   ```
   Filtre 1: Zone A → 100 features
   Filtre 2 (NOT AND): Zone B → 150 features
   Résultat actuel: Intersection ❌
   Résultat attendu: Différence ~50-100 features
   ```

## 📝 État Actuel du Code

### Appels au Cache

**Spatialite Backend** (`spatialite_backend.py:3456`):
```python
matching_fids_set, step_number = intersect_filter_fids(
    layer, set(matching_fids), source_wkt, buffer_val, predicates_list
)
```
❌ Pas d'opérateur passé → toujours AND

**OGR Backend** (`ogr_backend.py:559`):
```python
matching_fids_set, step_number = intersect_filter_fids(
    layer, set(matching_fids), source_wkt, buffer_val, predicates_list
)
```
❌ Pas d'opérateur passé → toujours AND

### Où Récupérer l'Opérateur

L'opérateur est disponible via `combine_operator` dans le contexte:

```python
# filter_task.py:7610
old_subset = layer.subsetString() if layer.subsetString() != '' else None
combine_operator = self._get_combine_operator()  # ← ICI!

# Plus tard:
backend.apply_filter(layer, expression, old_subset, combine_operator)
```

**Mais** `combine_operator` n'est **pas transmis** à `intersect_filter_fids()` !

## 🎯 Action Immédiate Recommandée

### Ajout de Validation (v2.9.43)

Ajouter une vérification dans les backends pour avertir l'utilisateur:

```python
# Dans spatialite_backend.py et ogr_backend.py
if SPATIALITE_CACHE_AVAILABLE and old_subset:
    # CRITICAL CHECK v2.9.43: Cache multi-step only supports AND
    # OR and NOT AND require full re-filtering (no cache intersection)
    
    if combine_operator in ('OR', 'NOT AND'):
        self.log_warning(
            f"⚠️ Multi-step filtering with {combine_operator} - "
            f"cache intersection not supported, performing full filter"
        )
        # Ne PAS faire d'intersection cache
        # Laisser matching_fids tel quel
    elif combine_operator is None or combine_operator == 'AND':
        # AND supporté - utiliser cache
        matching_fids_set, step_number = intersect_filter_fids(...)
```

Cette approche:
1. ✅ Évite les résultats incorrects pour OR/AND NOT
2. ✅ Maintient la performance pour AND (cas le plus courant)
3. ✅ Informe l'utilisateur de la limitation
4. ✅ Prépare le terrain pour le support futur

## 📚 Références

- **combine_operator documentation:** `filter_task.py:7610-7700`
- **QGIS selectbylocation METHODs:** `filter_task.py:6272-6310`
- **Cache intersection:** `spatialite_cache.py:534-580`
- **Backend usage:** `spatialite_backend.py:3450-3470`, `ogr_backend.py:555-570`

---

**Auteur:** GitHub Copilot  
**Date:** 2026-01-07  
**Status:** 🔴 ANALYSE - Action requise
