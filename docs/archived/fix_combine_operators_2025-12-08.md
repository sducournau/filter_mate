# Correction des Opérateurs de Combinaison de Filtres

## Problème Identifié

Les options de combinaison des filtres (`comboBox_filtering_source_layer_combine_operator` et `comboBox_filtering_other_layers_combine_operator`) ne fonctionnaient pas correctement pour cumuler les anciens et nouveaux subsets.

### Cause Root

Le code utilisait les valeurs UI directement sans distinction entre :
1. **Couche source** : nécessite des opérateurs logiques (`AND`, `AND NOT`, `OR`)
2. **Couches distantes** : nécessite des opérateurs SQL set (`INTERSECT`, `EXCEPT`, `UNION`)

## Solution Implémentée

### 1. Nouvelle méthode `_get_source_combine_operator()`

```python
def _get_source_combine_operator(self):
    """
    Get logical operator for combining with source layer's existing filter.
    
    Returns logical operators (AND, AND NOT, OR) directly from UI.
    These are used in simple SQL WHERE clause combinations.
    
    Returns:
        str: 'AND', 'AND NOT', 'OR', or None
    """
    if not hasattr(self, 'has_combine_operator') or not self.has_combine_operator:
        return None
    
    # Return source layer operator directly (no conversion needed)
    return getattr(self, 'param_source_layer_combine_operator', None)
```

**Usage** : Pour combiner les filtres de la couche source avec logique simple
- `"AND"` → `"AND"` (ET logique)
- `"AND NOT"` → `"AND NOT"` (ET NON logique)
- `"OR"` → `"OR"` (OU logique)

### 2. Méthode `_get_combine_operator()` clarifiée

```python
def _get_combine_operator(self):
    """
    Get SQL set operator for combining with distant layers' existing filters.
    
    Converts UI operators to SQL set operations for distant layer filtering:
    - 'AND' → 'INTERSECT' (intersection of sets)
    - 'AND NOT' → 'EXCEPT' (set difference)
    - 'OR' → 'UNION' (union of sets)
    
    Returns:
        str: 'INTERSECT', 'UNION', 'EXCEPT', or None
    """
    if not hasattr(self, 'has_combine_operator') or not self.has_combine_operator:
        return None
    
    operator_map = {
        'AND': 'INTERSECT',
        'AND NOT': 'EXCEPT',
        'OR': 'UNION'
    }
    
    other_op = getattr(self, 'param_other_layers_combine_operator', None)
    return operator_map.get(other_op, other_op)
```

**Usage** : Pour combiner les filtres des couches distantes avec opérateurs SQL set
- `"AND"` → `"INTERSECT"` (intersection de sets)
- `"AND NOT"` → `"EXCEPT"` (différence de sets)
- `"OR"` → `"UNION"` (union de sets)

### 3. Mise à jour de `_combine_with_old_subset()`

Avant :
```python
if not self.param_source_old_subset or not self.param_source_layer_combine_operator:
    return expression
# ... utilisait param_source_layer_combine_operator directement
```

Après :
```python
combine_operator = self._get_source_combine_operator()
if not self.param_source_old_subset or not combine_operator:
    return expression

# ... utilise combine_operator (valeurs logiques correctes)
# Gestion améliorée des cas sans WHERE clause
if index_where == -1:
    return f'( {self.param_source_old_subset} ) {combine_operator} ( {expression} )'
```

### 4. Mise à jour de `_build_feature_id_expression()`

Avant :
```python
if self.param_source_old_subset and self.param_source_layer_combine_operator:
    expression = (
        f'( {self.param_source_old_subset} ) '
        f'{self.param_source_layer_combine_operator} {expression}'
    )
```

Après :
```python
combine_operator = self._get_source_combine_operator()
if self.param_source_old_subset and combine_operator:
    expression = (
        f'( {self.param_source_old_subset} ) '
        f'{combine_operator} ( {expression} )'
    )
```

## Comportement Corrigé

### Pour la couche source (expression directe)

**Exemple 1 : Filtre initial**
- Ancien subset : `"POPULATION" > 10000`
- Nouveau filtre : `"TYPE" = 'VILLE'`
- Opérateur : `AND`
- **Résultat** : `( "POPULATION" > 10000 ) AND ( "TYPE" = 'VILLE' )`

**Exemple 2 : Exclusion**
- Ancien subset : `"POPULATION" > 10000`
- Nouveau filtre : `"TYPE" = 'VILLAGE'`
- Opérateur : `AND NOT`
- **Résultat** : `( "POPULATION" > 10000 ) AND NOT ( "TYPE" = 'VILLAGE' )`

**Exemple 3 : Union**
- Ancien subset : `"POPULATION" > 10000`
- Nouveau filtre : `"CAPITALE" = TRUE`
- Opérateur : `OR`
- **Résultat** : `( "POPULATION" > 10000 ) OR ( "CAPITALE" = TRUE )`

### Pour les couches distantes (opérations sur sets)

Les backends (PostgreSQL, Spatialite, OGR) reçoivent maintenant les bons opérateurs :
- PostgreSQL : `INTERSECT`, `EXCEPT`, `UNION` dans les sous-requêtes
- Spatialite : Idem (compatible SQL)
- OGR : `AND`, `AND NOT`, `OR` pour les subset strings

## Tests Recommandés

1. **Test Couche Source - AND**
   - Filtrer une couche avec `POPULATION > 10000`
   - Ajouter un filtre avec AND : `TYPE = 'VILLE'`
   - Vérifier que les deux conditions sont appliquées

2. **Test Couche Source - OR**
   - Filtrer une couche avec `POPULATION > 10000`
   - Ajouter un filtre avec OR : `CAPITALE = TRUE`
   - Vérifier que les entités répondant à l'une OU l'autre condition sont affichées

3. **Test Couche Source - AND NOT**
   - Filtrer une couche avec `POPULATION > 10000`
   - Ajouter un filtre avec AND NOT : `TYPE = 'VILLAGE'`
   - Vérifier que les villages sont exclus

4. **Test Couches Distantes**
   - Même tests mais avec des couches distantes filtrées par prédicats géométriques
   - Vérifier que les opérateurs SQL set fonctionnent correctement

## Impact

### Fichiers Modifiés
- `modules/appTasks.py` : 3 méthodes modifiées

### Changements Breaking
Aucun - comportement externe identique, mais logique interne corrigée

### Améliorations
- ✅ Distinction claire entre opérateurs logiques (source) et opérateurs SQL set (distants)
- ✅ Meilleure gestion des cas edge (pas de WHERE clause)
- ✅ Documentation explicite des conversions d'opérateurs
- ✅ Parenthèses correctes pour éviter les problèmes de priorité

## Notes Techniques

### Pourquoi cette distinction ?

1. **Couche source** : Utilise `setSubsetString()` avec expressions SQL WHERE simples
   - Exemples : `"field" > 10 AND "type" = 'A'`
   - Opérateurs : AND, OR, AND NOT (logique booléenne)

2. **Couches distantes** : Utilise des sous-requêtes avec opérations sur sets
   - Exemples : `"pk" IN (subquery1) INTERSECT "pk" IN (subquery2)`
   - Opérateurs : INTERSECT, UNION, EXCEPT (algèbre ensembliste)

Cette distinction est essentielle car :
- Les expressions WHERE n'acceptent pas INTERSECT/UNION/EXCEPT
- Les sous-requêtes ne peuvent pas utiliser AND/OR pour combiner des sets

### Compatibilité Backends

| Backend | Source Layer | Distant Layers |
|---------|--------------|----------------|
| PostgreSQL | AND/OR/AND NOT | INTERSECT/UNION/EXCEPT |
| Spatialite | AND/OR/AND NOT | INTERSECT/UNION/EXCEPT |
| OGR | AND/OR/AND NOT | AND/OR/AND NOT (via subset) |

## Date
8 décembre 2025
