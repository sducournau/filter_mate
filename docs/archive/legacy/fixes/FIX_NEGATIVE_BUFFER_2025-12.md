# Fix: Problème de Filtrage avec Buffer Négatif sur Couches Polygones

**Date:** 29 Décembre 2025  
**Version:** 2.3.9+  
**Type:** Bugfix + Enhancement

## Problème Identifié

Lors de l'application d'un buffer négatif (érosion) sur une couche polygone, FilterMate pouvait échouer silencieusement ou produire des résultats inattendus quand:

1. **Érosion complète**: Le buffer négatif est plus grand que la largeur du polygone, résultant en une géométrie vide
2. **Manque de feedback**: Aucun message n'informait l'utilisateur du problème
3. **Logs insuffisants**: Difficile de diagnostiquer pourquoi le filtrage échouait

### Exemple de Scénario Problématique

```python
# Polygone de 10m de large
# Buffer négatif de -15m appliqué
# Résultat: Géométrie complètement érodée (vide)
# Avant le fix: Échec silencieux ou erreur peu claire
```

## Solution Implémentée

### 1. Amélioration de `safe_buffer` (geometry_safety.py)

**Changements:**

- ✅ Documentation mise à jour pour expliquer le comportement avec buffers négatifs
- ✅ Log spécifique quand buffer négatif est appliqué
- ✅ Distinction claire entre "érosion complète" et "échec d'opération"

```python
# Log ajouté
if distance < 0:
    logger.debug(f"safe_buffer: Applying negative buffer (erosion) of {distance}m")

# Message différencié pour résultat vide
if distance < 0:
    logger.debug(f"safe_buffer: Negative buffer ({distance}m) produced empty geometry (complete erosion)")
else:
    logger.debug("safe_buffer: Buffer produced empty/null geometry")
```

### 2. Amélioration de `_buffer_all_features` (filter_task.py)

**Changements:**

- ✅ Tracking séparé des features complètement érodées (`eroded_features`)
- ✅ Avertissement utilisateur quand TOUTES les features sont érodées
- ✅ Logs enrichis pour diagnostiquer le problème
- ✅ Message dans la barre de message QGIS

```python
# Retourne maintenant 4 valeurs au lieu de 3
return geometries, valid_features, invalid_features, eroded_features

# Avertissement si toutes les features érodées
if valid_features == 0:
    logger.warning(f"⚠️ TOUTES les features ont été érodées par le buffer de {buffer_dist}m!")
    iface.messageBar().pushWarning(
        "FilterMate",
        f"Le buffer négatif de {buffer_dist}m a complètement érodé toutes les géométries."
    )
```

### 3. Messages Utilisateur Améliorés

**Avant:**
- Aucun message ou message générique d'erreur

**Après:**
- Message clair dans la barre de message QGIS
- Suggestion d'action: "Réduisez la distance du buffer"
- Logs détaillés pour diagnostic

## Tests Ajoutés

Nouveau fichier: `tests/test_negative_buffer.py`

Tests couverts:
1. ✅ Buffer négatif avec érosion complète → retourne None
2. ✅ Buffer négatif avec érosion partielle → retourne géométrie réduite  
3. ✅ Buffer positif → fonctionne normalement

## Comment Tester Manuellement

1. **Ouvrir QGIS** avec une couche polygone
2. **Activer FilterMate**
3. **Appliquer un buffer négatif** de -50m ou plus (grande valeur)
4. **Observer:**
   - Message dans la barre: "Le buffer négatif de -50m a complètement érodé toutes les géométries"
   - Logs Python montrent le nombre de features érodées
   - Aucun crash, comportement gracieux

## Comportement Attendu

### Buffer Négatif Valide (Érosion Partielle)

```
Input:  Polygone 100m x 100m
Buffer: -10m
Output: Polygone 80m x 80m (réduit de 10m de chaque côté)
```

### Buffer Négatif Trop Grand (Érosion Complète)

```
Input:  Polygone 20m x 20m  
Buffer: -15m
Output: Géométrie vide (complètement érodée)
Message: "Le buffer négatif de -15m a complètement érodé toutes les géométries. 
          Réduisez la distance du buffer."
```

## Fichiers Modifiés

1. `modules/geometry_safety.py`
   - Fonction `safe_buffer()` - Lignes 330-388
   
2. `modules/tasks/filter_task.py`  
   - Fonction `_buffer_all_features()` - Lignes 3307-3351
   - Fonction `_create_buffered_memory_layer()` - Lignes 3470-3495

3. **Nouveau:** `tests/test_negative_buffer.py`
   - Tests unitaires pour validation

## Impact

- **Compatibilité:** 100% rétrocompatible
- **Performance:** Aucun impact (seulement logs additionnels)
- **UX:** Amélioration significative - utilisateur comprend pourquoi le buffer ne produit rien

## Notes pour Développeurs

### Pourquoi les Buffers Négatifs Produisent des Géométries Vides?

Un buffer négatif (érosion) fonctionne en "rétrécissant" le polygone. Si la distance de rétrécissement est plus grande que la moitié de la largeur minimale du polygone, celui-ci disparaît complètement.

**Analogie:** 
- Imaginez un donut de 10cm de diamètre avec un trou de 2cm
- Si vous "érodez" de 5cm, le trou devient plus grand que le donut
- Résultat: Plus de donut!

### Considérations Backends

Le comportement est cohérent sur tous les backends:

- **PostgreSQL**: `ST_Buffer(geom, -10)` peut retourner géométrie vide
- **Spatialite**: `ST_Buffer(geom, -10)` même comportement  
- **OGR/QGIS**: `QgsGeometry.buffer(-10)` même comportement

Tous utilisent GEOS en interne, donc comportement identique.

## Changelog Entry

```
### Fixed - v2.3.9+
- Amélioration gestion buffers négatifs sur polygones
  - Tracking séparé des features complètement érodées
  - Message utilisateur clair quand toutes les features sont érodées
  - Logs détaillés pour diagnostiquer le problème  
  - Tests unitaires ajoutés
```

## Références

- Issue: Problème de filtrage avec buffer négatif depuis couche polygone
- Modules modifiés: `geometry_safety`, `filter_task`
- Tests: `test_negative_buffer.py`

---

**Status:** ✅ Résolu  
**Testé:** ✅ Localement  
**Documentation:** ✅ Complète
