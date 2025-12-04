# Correction du bug des géométries invalides (2024-12-04)

## Problème

Lors du filtrage géométrique avec buffer sur des couches OGR (GeoPackage, Shapefile), toutes les géométries (23/23) étaient marquées comme invalides, empêchant la création du buffer :

```
Exception: Both buffer methods failed. 
QGIS: Impossible d'écrire l'entité dans OUTPUT, 
Manual: No valid geometries could be buffered. Total features: 23, Valid after buffer: 0, Invalid: 23
```

## Cause

Les géométries dans certains fichiers OGR peuvent être techniquement invalides selon les critères GEOS (auto-intersections, trous mal formés, etc.) même si elles s'affichent correctement dans QGIS. L'opération de buffer échoue sur ces géométries invalides.

## Solution

Ajout d'une validation et réparation automatique des géométries **avant** l'opération de buffer :

### Nouvelle fonction : `_repair_invalid_geometries()`

```python
def _repair_invalid_geometries(self, layer):
    """
    Validate and repair invalid geometries in a layer.
    Creates a new memory layer with repaired geometries if needed.
    
    Returns:
        QgsVectorLayer: Original layer if all valid, or new layer with repaired geometries
    """
```

### Processus de réparation

1. **Première passe** : Détection des géométries invalides via `geom.isGeosValid()`
2. **Si toutes valides** : Retourne la couche originale (pas de traitement supplémentaire)
3. **Si invalides détectées** :
   - Création d'une couche mémoire temporaire
   - Pour chaque géométrie invalide : tentative de réparation avec `geom.makeValid()`
   - Les géométries réparables sont conservées
   - Les géométries irréparables sont exclues avec warning
   - Retourne la nouvelle couche avec géométries réparées

### Intégration

La fonction est appelée automatiquement dans `_apply_buffer_with_fallback()` :

```python
def _apply_buffer_with_fallback(self, layer, buffer_distance):
    # CRITICAL: Validate and repair geometries before buffer
    layer = self._repair_invalid_geometries(layer)
    
    try:
        return self._apply_qgis_buffer(layer, buffer_distance)
    except Exception as e:
        # Fallback to manual buffer...
```

## Logging

La fonction fournit un feedback détaillé :

```
✓ All 23 geometries are valid  # Si tout va bien
```

```
⚠️ Found 5/23 invalid geometries, attempting repair...
  ✓ Repaired geometry for feature 3
  ✓ Repaired geometry for feature 7
  ✗ Could not repair geometry for feature 12
✓ Geometry repair complete: 4/5 successfully repaired, 22/23 features kept
```

## Tests

Tests unitaires créés dans `tests/test_geometry_repair.py` :

1. `test_all_valid_geometries` : Vérifie que les géométries valides ne sont pas modifiées
2. `test_invalid_geometries_repaired` : Vérifie la réparation des géométries invalides
3. `test_buffer_with_geometry_repair` : Vérifie l'intégration dans le workflow de buffer

## Impact

- ✅ Résout le crash sur les couches OGR avec géométries invalides
- ✅ Transparent pour l'utilisateur (réparation automatique)
- ✅ Performance : pas de surcoût si toutes les géométries sont valides
- ✅ Robustesse : logging détaillé pour diagnostiquer les problèmes

## Fichiers modifiés

- `modules/appTasks.py` : Ajout de `_repair_invalid_geometries()` et modification de `_apply_buffer_with_fallback()`
- `tests/test_geometry_repair.py` : Nouveaux tests unitaires

## Recommandation utilisateur

Si des géométries ne peuvent pas être réparées, l'utilisateur devrait :
1. Utiliser "Vérifier la validité" dans QGIS (Vector > Geometry Tools > Check Validity)
2. Utiliser "Réparer les géométries" (Vector > Geometry Tools > Fix Geometries)
3. Exporter vers un nouveau fichier après réparation
