# Fix: OGR Layers Show Wrong Feature Count After Filtering (v3.0.8)

**Date**: 2026-01-07  
**Criticité**: 🟠 **MAJEUR** (Affichage incorrect, filtrage fonctionne)  
**Issue**: Les couches OGR/GeoPackage filtrées par le backend Spatialite affichent le compte total au lieu du compte filtré

---

## 🐛 Problème

**Symptôme** :

Après filtrage d'une couche GeoPackage avec le backend Spatialite:

```
batiment: Spatial query completed → 1178 matching features  ← CORRECT
✓ Filter APPLIED: batiment → 1164986 features               ← FAUX! Devrait être 1178
```

Le filtre est **correctement appliqué** (seules 1178 features sont visibles sur la carte), mais le **comptage affiché** montre le nombre total de la couche (1164986).

**Couches affectées** :

- Couches GeoPackage (`.gpkg`) traitées par le backend Spatialite
- Particulièrement les grandes couches utilisant le mode "SOURCE TABLE (R-tree)"

---

## 🔍 Root Cause Analysis

### Le Problème

Dans `finished()` de `filter_task.py`, après application du filtre via `setSubsetString()`, le code appelait `layer.reload()` uniquement pour les providers 'postgres' et 'spatialite':

```python
# AVANT (ligne 11801)
if layer.providerType() in ('postgres', 'spatialite'):
    layer.reload()
feature_count = layer.featureCount()  # ← Retourne le compte périmé pour OGR!
```

**Mais** les couches GeoPackage utilisent le provider `'ogr'` de QGIS, même si FilterMate les traite via le backend Spatialite (qui utilise mod_spatialite pour les requêtes SQL).

Sans `reload()`, le provider OGR ne met pas à jour son cache interne et `featureCount()` retourne le nombre total de la table au lieu du sous-ensemble filtré.

### Pourquoi seules certaines couches sont affectées?

| Couche                 | Mode                | Provider QGIS | Affichage        |
| ---------------------- | ------------------- | ------------- | ---------------- |
| surface_hydrographique | DIRECT SQL          | ogr           | ✓ Correct (21)   |
| batiment               | SOURCE TABLE R-tree | ogr           | ✗ Faux (1164986) |
| troncon_de_route       | SOURCE TABLE R-tree | ogr           | ✗ Faux (382452)  |

Les deux modes utilisent le même code dans `finished()`, mais le timing et l'ordre d'application peuvent affecter le comportement du cache OGR.

---

## ✅ Solution

### Modification dans `filter_task.py`

Ajouter `'ogr'` à la liste des providers qui nécessitent un `reload()`:

```python
# APRÈS (ligne 11801-11805)
# FIX v3.0.8: CRITICAL - Also reload OGR layers (GeoPackage processed by Spatialite backend)
# Without reload(), featureCount() returns stale data for OGR/GeoPackage layers
if layer.providerType() in ('postgres', 'spatialite', 'ogr'):
    layer.reload()
feature_count = layer.featureCount()  # ← Maintenant correct!
```

### Fichiers modifiés

1. **modules/tasks/filter_task.py**
   - Ligne ~11773: Ajout de `'ogr'` au reload pour filtres déjà appliqués
   - Ligne ~11805: Ajout de `'ogr'` au reload pour nouveaux filtres

---

## 📊 Résultat Attendu

```
batiment: Spatial query completed → 1178 matching features
✓ Filter APPLIED: batiment → 1178 features  ← CORRECT!

troncon_de_route: Spatial query completed → 499 matching features
✓ Filter APPLIED: troncon_de_route → 499 features  ← CORRECT!
```

---

## 🧪 Test de Validation

1. Charger un projet avec des couches GeoPackage volumineuses (>10k features)
2. Configurer FilterMate en mode Spatialite
3. Appliquer un filtre spatial sur une couche source
4. Vérifier que:
   - Le message "Spatial query completed → N matching features" correspond
   - Le message "Filter APPLIED → N features" affiche le même nombre N
   - Les couches sur la carte montrent uniquement les features filtrées

---

## ⚠️ Notes

### Performance

L'appel `reload()` peut avoir un léger coût sur les très grandes couches OGR, mais c'est nécessaire pour la cohérence des données affichées. Les sections existantes (11430-11435) qui évitent `reloadData()` pour OGR restent inchangées - elles concernent le refresh post-filtrage, pas l'application initiale.

### Distinction des sections

- **Application initiale** (11800-11830): Nécessite `reload()` pour mise à jour du cache
- **Refresh périodique** (11400-11435): Évite `reloadData()` pour prévenir les freezes
