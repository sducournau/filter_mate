# GeoPackage Backend Detection Fix

## Problème identifié

Les fichiers GeoPackage (`.gpkg`) étaient détectés comme provider `'ogr'` et utilisaient donc le backend OGR (fallback) au lieu du backend Spatialite optimisé. Cela causait :

1. **Performances réduites** : Utilisation de QGIS processing au lieu de requêtes SQL directes
2. **Fonctionnalités limitées** : Pas d'accès aux fonctions spatiales Spatialite/SQLite
3. **Buffer failures** : Problèmes avec CRS géographiques non détectés correctement

## Solution implémentée

### 1. Correction de `detect_layer_provider_type()` (appUtils.py)

**Avant :**
```python
if source_path.lower().endswith('.sqlite'):
    return 'spatialite'
```

**Après :**
```python
if source_path.lower().endswith('.sqlite') or source_path.lower().endswith('.gpkg'):
    return 'spatialite'
```

Les fichiers `.gpkg` et `.sqlite` sont maintenant tous deux détectés comme `'spatialite'`.

### 2. Amélioration de `SpatialiteGeometricFilter.supports_layer()` (spatialite_backend.py)

**Avant :**
```python
def supports_layer(self, layer: QgsVectorLayer) -> bool:
    return layer.providerType() == PROVIDER_SPATIALITE
```

**Après :**
```python
def supports_layer(self, layer: QgsVectorLayer) -> bool:
    provider_type = layer.providerType()
    
    # Native Spatialite
    if provider_type == PROVIDER_SPATIALITE:
        return True
    
    # OGR provider - check if it's actually GeoPackage or SQLite
    if provider_type == 'ogr':
        source = layer.source()
        source_path = source.split('|')[0] if '|' in source else source
        if source_path.lower().endswith('.gpkg') or source_path.lower().endswith('.sqlite'):
            return True
    
    return False
```

Le backend vérifie maintenant explicitement les extensions de fichiers pour accepter GeoPackage.

### 3. Documentation améliorée

- Docstrings mis à jour pour mentionner le support GeoPackage
- Commentaires clarifiés sur le format pipe `|` utilisé par QGIS pour GeoPackage

## Corrections supplémentaires (Buffer CRS)

En analysant le problème initial, nous avons également corrigé :

### 4. Détection CRS géographique dans `prepare_ogr_source_geom()` (appTasks.py)

Ajout de validation précoce :
```python
if is_geographic and eval_distance and float(eval_distance) > 1:
    logger.warning("⚠️ Geographic CRS detected, auto-reprojecting to EPSG:3857")
    self.has_to_reproject_source_layer = True
    self.source_layer_crs_authid = 'EPSG:3857'
```

**Résultat :** Reprojection automatique avant buffer si CRS géographique détecté.

### 5. Messages d'erreur améliorés

Ajout d'hints contextuels :
```python
💡 HINT: Your layer uses a GEOGRAPHIC CRS (EPSG:4326) where buffer units are DEGREES.
   This often causes buffer failures. Please reproject your layer to a PROJECTED CRS:
   - For worldwide data: EPSG:3857 (Web Mercator)
   - For France: EPSG:2154 (Lambert 93)
```

## Impact

### Avant
```
Layer: roads_m (GeoPackage)
Provider detected: ogr
Backend selected: OGR (fallback)
→ Uses QGIS processing algorithms
→ Slower for large datasets
→ Buffer failures on geographic CRS
```

### Après
```
Layer: roads_m (GeoPackage)
Provider detected: spatialite
Backend selected: Spatialite
→ Uses SQL expressions with Spatialite functions
→ Much faster (direct DB queries)
→ Auto-reprojection for buffer on geographic CRS
→ Better error messages
```

## Tests

Exécuter :
```bash
python3 tests/test_geopackage_detection.py
```

Dans QGIS, vérifier les logs pour :
```
Using Spatialite backend for <layer_name>
```

## Fichiers modifiés

1. `modules/appUtils.py` - Détection provider type
2. `modules/backends/spatialite_backend.py` - Support GeoPackage
3. `modules/appTasks.py` - Validation CRS et reprojection auto
4. `tests/test_geopackage_detection.py` - Tests unitaires

## Compatibilité

- ✅ GeoPackage (.gpkg)
- ✅ SQLite/Spatialite (.sqlite)
- ✅ Shapefiles (.shp) - continue d'utiliser OGR
- ✅ PostgreSQL - inchangé
- ✅ Memory layers - inchangé

## Migration

Aucune migration nécessaire. Les changements sont rétrocompatibles et s'appliquent automatiquement au prochain rechargement du plugin.
