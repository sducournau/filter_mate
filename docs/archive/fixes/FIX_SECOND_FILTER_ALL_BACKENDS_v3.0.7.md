# Fix: Second Filter Incorrectly Replaces First Filter (v3.0.7)

**Date**: 2026-01-07  
**Criticité**: 🔴 **CRITIQUE**  
**Issue**: Le 2ème filtre remplace le 1er filtre au lieu de les combiner (tous les backends)

---

## 🐛 Problème Critique

**Symptôme** :

- 1er filtre appliqué correctement (ex: 319 features)
- 2ème filtre **remplace** le 1er au lieu de combiner
- Résultat: Perte des résultats du 1er filtre

**Affecté** :

- PostgreSQL backend
- Spatialite backend (mode NATIVE)
- OGR backend (toutes les méthodes)

---

## 🔍 Root Cause Analysis

### Le Problème

Le code v2.9.42 utilisait `combine_operator=None` comme signal pour REMPLACER les filtres:

```python
# filter_task.py - Détection des filtres FID
if is_fid_only_filter:
    combine_operator = None  # Signal de REPLACE (INCORRECT!)
```

```python
# Backends - Interprétation
if combine_operator is None:
    final_expression = expression  # REPLACE au lieu de COMBINE!
```

### Pourquoi c'est Faux

1. `None` est aussi la **valeur par défaut** quand l'utilisateur n'a pas choisi d'opérateur
2. Les filtres FID (`fid IN (...)`) du 1er filtre **DOIVENT** être combinés avec le 2ème filtre
3. Le fix v3.0.3 a corrigé les modes DIRECT_SQL et SOURCE_TABLE mais PAS:
   - Le mode NATIVE de Spatialite
   - Le backend PostgreSQL (apply_filter)
   - Le backend OGR (4 endroits différents)

---

## ✅ Solution v3.0.7

### Logique Corrigée

Pour **tous les backends**, le nouveau comportement est:

```python
if old_subset and not self._should_clear_old_subset(old_subset):
    # v3.0.7: Check if old_subset is a FID-only filter from previous step
    is_fid_only = bool(re.match(
        r'^\s*\(?\s*(["\']?)fid\1\s+(IN\s*\(|=\s*-?\d+|BETWEEN\s+)',
        old_subset,
        re.IGNORECASE
    ))

    if is_fid_only:
        # FID filter from previous step - ALWAYS combine
        final_expression = f"({old_subset}) AND ({expression})"
    elif combine_operator is None:
        # v3.0.7: Use default AND instead of REPLACE
        final_expression = f"({old_subset}) AND ({expression})"
    else:
        # Use provided operator
        final_expression = f"({old_subset}) {combine_operator} ({expression})"
```

### Fichiers Modifiés

1. **modules/backends/spatialite_backend.py**

   - Mode NATIVE (ligne ~2591)
   - Ajout de la détection FID et utilisation de AND par défaut

2. **modules/backends/postgresql_backend.py**

   - `apply_filter()` (ligne ~1825)
   - Ajout de la détection FID et utilisation de AND par défaut

3. **modules/backends/ogr_backend.py**
   - `_apply_filter_standard()` (ligne ~2633)
   - `_try_multi_step_filter()` (ligne ~642)
   - `_apply_filter_large_dataset()` (ligne ~3043)
   - `_apply_filter_with_memory_optimization()` (ligne ~3216)
   - Ajout de la détection FID et utilisation de AND par défaut

---

## 📊 Changements de Comportement

| Scénario                             | Avant v3.0.7 | Après v3.0.7  |
| ------------------------------------ | ------------ | ------------- |
| 2ème filtre avec FID existant        | REPLACE      | COMBINE (AND) |
| 2ème filtre sans opérateur (None)    | REPLACE      | COMBINE (AND) |
| 2ème filtre avec opérateur explicite | COMBINE (OK) | COMBINE (OK)  |
| Filtre spatial existant              | REPLACE (OK) | REPLACE (OK)  |

---

## 🧪 Tests de Validation

### Scénario 1: Multi-Step Filtering

1. Step 1: Filtrer "batiment" → demand_points = 319 features
2. Step 2: Filtrer "ducts" (source différente)
3. **Résultat attendu**: demand_points = intersection (< 319 features)
4. **Résultat avant fix**: demand_points = tous features ducts (WRONG)

### Scénario 2: 2ème Filtre Simple

1. 1er filtre: Quelques features sélectionnées
2. 2ème filtre: Autre géométrie source
3. **Résultat attendu**: Intersection des 2 filtres
4. **Résultat avant fix**: 2ème filtre seulement

### Scénario 3: Filtre Attributaire + Géométrique

1. Filtre attributaire: `importance > 5`
2. Filtre géométrique: Intersection avec polygone
3. **Résultat attendu**: Features avec importance > 5 ET dans le polygone
4. **Ce scénario fonctionnait déjà** (attributaire n'est pas FID)

---

## 📝 Notes Techniques

### Pourquoi les Modes DIRECT_SQL/SOURCE_TABLE Fonctionnaient

Ces modes ont leur **propre logique de détection FID** (lignes ~3347-3360):

```python
# v3.0.3: FID filters MUST be combined in multi-step filtering!
if not has_source_alias and not has_exists and not has_spatial_predicate:
    old_subset_sql_filter = f"({old_subset}) AND "  # TOUJOURS combiner
```

Cette logique **ignorait** `combine_operator=None` et combinait quand même.

### Pourquoi les Autres Modes ne Fonctionnaient Pas

- **Mode NATIVE Spatialite**: Utilisait uniquement `combine_operator` sans détection FID
- **PostgreSQL apply_filter**: Même problème
- **OGR backend**: Même problème (4 endroits!)

### La Correction

Aligner TOUS les backends sur la même logique:

1. Détecter si `old_subset` est un filtre FID
2. Si oui, TOUJOURS combiner (ignore `combine_operator=None`)
3. Si non et `combine_operator=None`, utiliser AND par défaut

---

## 🔄 Historique des Fixes Liés

- **v2.9.34**: Introduction de `combine_operator=None` comme signal REPLACE
- **v2.9.42**: Respect de `combine_operator=None` dans les backends (INCORRECT)
- **v3.0.3**: Fix DIRECT_SQL/SOURCE_TABLE pour combiner FID filters
- **v3.0.7**: Fix TOUS les backends pour combiner FID filters

---

## ⚠️ Impact sur le Code Existant

Ce fix change le comportement par défaut quand `combine_operator=None`:

- **Avant**: REPLACE (perte du filtre existant)
- **Après**: AND (préserve le filtre existant)

Cela peut affecter des workflows qui dépendaient du comportement REPLACE.
Cependant, le comportement REPLACE était considéré comme un **BUG** car:

- L'utilisateur ne s'attend pas à perdre le 1er filtre sans avertissement
- Le comportement correct est de combiner (intersection)

---

**Résumé** : Ce fix assure que le 2ème filtre combine correctement avec le 1er filtre au lieu de le remplacer, sur TOUS les backends (PostgreSQL, Spatialite, OGR).
