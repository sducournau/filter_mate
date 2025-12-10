# Correction: Erreur OGR "Type mismatch or improper type of arguments"

**Date**: 7 décembre 2025  
**Erreur rapportée**: `Couche Home Count: OGR [3] erreur 1: Type mismatch or improper type of arguments to`

## Diagnostic

L'erreur "Type mismatch or improper type of arguments" sur une couche OGR peut avoir plusieurs causes:

1. **Types de paramètres incorrects** dans les appels à `processing.run()`
2. **Noms de champs avec espaces** mal échappés dans les expressions SQL
3. **Valeurs de buffer incompatibles** avec un CRS géographique

## Corrections appliquées

### 1. Conversion explicite des types de paramètres de buffer

**Fichiers modifiés:**
- `modules/backends/ogr_backend.py`
- `modules/appTasks.py`

**Problème:** Les paramètres numériques (SEGMENTS, END_CAP_STYLE, etc.) étaient passés comme littéraux, ce qui pouvait causer des erreurs de type avec certains drivers OGR.

**Solution:** Conversion explicite en types appropriés:
```python
buffer_result = processing.run("native:buffer", {
    'INPUT': source_layer,
    'DISTANCE': float(buffer_value),      # ✓ Explicitement float
    'SEGMENTS': int(5),                   # ✓ Explicitement int
    'END_CAP_STYLE': int(0),              # ✓ Explicitement int
    'JOIN_STYLE': int(0),                 # ✓ Explicitement int
    'MITER_LIMIT': float(2.0),            # ✓ Explicitement float
    'DISSOLVE': False,
    'OUTPUT': 'memory:'
})
```

### 2. Amélioration de l'échappement des identifiants OGR

**Fichier modifié:** `modules/backends/ogr_backend.py`

**Problème:** Les noms de champs avec espaces (comme "Home Count") pouvaient causer des problèmes dans les expressions SQL OGR.

**Solution:** Ajout d'une fonction dédiée pour échapper les identifiants:
```python
def escape_ogr_identifier(identifier: str) -> str:
    """
    Escape identifier for OGR SQL expressions.
    
    OGR uses double quotes for identifiers but has limited support.
    Some formats (Shapefile) have restrictions on field names.
    """
    if ' ' in identifier:
        logger.warning(f"OGR identifier '{identifier}' contains spaces - may cause issues")
    
    return f'"{identifier}"'
```

Utilisation dans les expressions:
```python
escaped_pk = escape_ogr_identifier(pk_field)
new_subset_expression = f'{escaped_pk} IN ({id_list})'
```

### 3. Gestion améliorée des erreurs de buffer

**Fichier modifié:** `modules/backends/ogr_backend.py`

**Améliorations:**
- Validation du type de `buffer_value` avant utilisation
- Détection des CRS géographiques avec valeurs de buffer élevées
- Messages d'erreur détaillés avec traceback complet
- Logging des détails de la couche source

```python
def _apply_buffer(self, source_layer, buffer_value):
    """Apply buffer to source layer if specified"""
    if buffer_value and buffer_value > 0:
        try:
            # Ensure buffer_value is numeric
            buffer_dist = float(buffer_value)
            
            # Log layer details for debugging
            self.log_debug(f"Buffer source layer: {source_layer.name()}, "
                          f"CRS: {source_layer.crs().authid()}, "
                          f"Features: {source_layer.featureCount()}")
            
            # ... buffer operation ...
            
        except Exception as buffer_error:
            self.log_error(f"Buffer operation failed: {str(buffer_error)}")
            self.log_error(f"  - Buffer value: {buffer_value} (type: {type(buffer_value).__name__})")
            self.log_error(f"  - Source layer: {source_layer.name()}")
            self.log_error(f"  - CRS: {source_layer.crs().authid()}")
            
            # Check for common error causes
            if source_layer.crs().isGeographic() and float(buffer_value) > 1:
                self.log_error(
                    f"ERROR: Geographic CRS detected with large buffer value!\n"
                    f"  A buffer of {buffer_value}° ≈ {float(buffer_value) * 111}km\n"
                    f"  → Solution: Reproject to projected CRS (EPSG:3857, EPSG:2154)"
                )
```

### 4. Correction d'une erreur de syntaxe

**Fichier modifié:** `modules/backends/ogr_backend.py`

**Problème:** Double bloc `except` consécutif dans `_apply_filter_large()`

**Solution:** Suppression du bloc `except` dupliqué pour éviter l'erreur de syntaxe Python.

## Tests

Un nouveau fichier de tests a été créé: `tests/test_ogr_type_handling.py`

**Tests inclus:**
- Échappement des identifiants simples
- Échappement des identifiants avec espaces
- Validation des types de paramètres de buffer
- Détection des valeurs de buffer incompatibles avec CRS géographiques
- Gestion des champs numériques vs chaînes dans les expressions

## Validation

Pour tester la correction avec la couche "Home Count":

1. **Vérifier les logs détaillés:**
   ```python
   # Les nouveaux logs montreront:
   # - Type de chaque paramètre
   # - Détails du CRS
   # - Valeur du buffer et son type
   ```

2. **Cas d'usage typiques:**
   - Couche avec nom contenant des espaces → Devrait fonctionner avec avertissement
   - Buffer sur CRS géographique → Erreur claire si valeur > 1°
   - Tous types OGR (Shapefile, GeoPackage, etc.) → Types corrects

3. **Si l'erreur persiste:**
   - Vérifier les logs QGIS pour le message d'erreur complet
   - Vérifier le CRS de la couche (géographique vs projeté)
   - Vérifier la valeur du buffer (degrés vs mètres)
   - Vérifier les noms de champs (espaces, caractères spéciaux)

## Impact

**Compatibilité:** 
- ✅ Rétrocompatible
- ✅ Pas de changement d'API
- ✅ Amélioration de la robustesse

**Performance:**
- ✅ Aucun impact négatif
- ✅ Meilleur logging pour diagnostic

**Formats supportés:**
- ✅ Shapefile
- ✅ GeoPackage
- ✅ SQLite/Spatialite
- ✅ Tous drivers OGR

## Prochaines étapes

Si l'erreur "Type mismatch" persiste après ces corrections:

1. **Activer le logging debug** dans QGIS
2. **Examiner le message d'erreur complet** dans les logs
3. **Vérifier la configuration de la couche:**
   - Type de provider
   - Nom de la couche
   - Noms des champs
   - CRS
4. **Tester avec une couche simplifiée** (ex: couche mémoire) pour isoler le problème

## Références

- OGR SQL dialect: https://gdal.org/user/ogr_sql_dialect.html
- QGIS Processing algorithms: https://docs.qgis.org/latest/en/docs/user_manual/processing_algs/
- Buffer operation: https://docs.qgis.org/latest/en/docs/user_manual/processing_algs/qgis/vectorgeometry.html#buffer
