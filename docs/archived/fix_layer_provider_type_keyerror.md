# Fix: KeyError 'layer_provider_type' in _create_spatial_index

**Date**: 8 décembre 2025  
**Issue**: KeyError: 'layer_provider_type' in modules/appTasks.py:4648  
**Status**: ✅ Résolu

## Problème

Lors du chargement de layers existants en base de données (créés avant l'ajout de la fonctionnalité `layer_provider_type`), l'application générait une `KeyError` car la clé `layer_provider_type` était absente du dictionnaire `layer_props["infos"]`.

### Stack Trace
```
KeyError: 'layer_provider_type' 
  File "modules\appTasks.py", line 4648, in _create_spatial_index
    if layer_props["infos"]["layer_provider_type"] == PROVIDER_POSTGRES:
       ~~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
KeyError: 'layer_provider_type'
```

## Cause Racine

1. Les layers créés avant la fonctionnalité `layer_provider_type` n'ont pas cette propriété en base
2. La méthode `_load_existing_layer_properties()` chargeait les propriétés telles quelles
3. La méthode `_create_spatial_index()` tentait d'accéder à `layer_props["infos"]["layer_provider_type"]` sans vérifier son existence

## Solution Implémentée

### 1. Migration automatique dans `_migrate_legacy_geometry_field()` 

Ajout d'un bloc de migration similaire aux migrations existantes (`geometry_field` → `layer_geometry_field`, ajout de `layer_table_name`) :

```python
# Add layer_provider_type if missing (for layers created before this feature)
if "layer_provider_type" not in infos:
    layer_provider_type = detect_layer_provider_type(layer)
    infos["layer_provider_type"] = layer_provider_type
    logger.info(f"Added layer_provider_type='{layer_provider_type}' for layer {layer.id()}")
    
    # Add to database
    try:
        conn = self._safe_spatialite_connect()
        cur = conn.cursor()
        
        cur.execute(
            """INSERT INTO fm_project_layers_properties 
               (fk_project, layer_id, meta_type, meta_key, meta_value)
               VALUES (?, ?, 'infos', 'layer_provider_type', ?)""",
            (str(self.project_uuid), layer.id(), layer_provider_type)
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.debug(f"Added layer_provider_type to database for layer {layer.id()}")
    except Exception as e:
        logger.warning(f"Could not add layer_provider_type to database: {e}")
```

### 2. Défense en profondeur dans `_create_spatial_index()`

Ajout d'une détection dynamique si `layer_provider_type` est toujours manquant :

```python
def _create_spatial_index(self, layer, layer_props):
    """
    Create spatial index for layer based on provider type.
    
    Args:
        layer: QgsVectorLayer to index
        layer_props: Layer properties dictionary
    """
    # Safely get provider type with fallback
    layer_provider_type = layer_props.get("infos", {}).get("layer_provider_type")
    
    # If not found in props, detect it directly
    if not layer_provider_type:
        layer_provider_type = detect_layer_provider_type(layer)
        logger.debug(f"Provider type not in layer_props, detected as: {layer_provider_type}")
    
    if layer_provider_type == PROVIDER_POSTGRES:
        try:
            self.create_spatial_index_for_postgresql_layer(layer, layer_props)
        except (psycopg2.Error, AttributeError, KeyError) as e:
            logger.debug(f"Could not create spatial index for PostgreSQL layer {layer.id()}: {e}")
    else:
        self.create_spatial_index_for_layer(layer)
```

## Fichiers Modifiés

- `modules/appTasks.py` :
  - `_migrate_legacy_geometry_field()` : Ajout migration `layer_provider_type`
  - `_create_spatial_index()` : Accès sécurisé avec fallback

## Tests

- `tests/test_layer_provider_type_migration.py` : Tests unitaires pour la migration
  - `test_migrate_adds_layer_provider_type_if_missing`
  - `test_create_spatial_index_handles_missing_provider_type`
  - `test_layer_with_existing_provider_type_not_modified`

## Comportement Attendu

### Avant le Fix
- ❌ `KeyError` lors du chargement de layers legacy
- ❌ Impossibilité d'utiliser le plugin avec des projets existants

### Après le Fix
- ✅ Migration automatique et transparente des layers legacy
- ✅ Détection dynamique si la migration échoue
- ✅ Compatibilité ascendante totale
- ✅ Logging informatif pour suivi des migrations

## Notes Techniques

### Pattern de Migration Utilisé

Le fix suit le pattern établi dans FilterMate pour les migrations de propriétés :

1. **Détection** : Vérifier si la propriété manque
2. **Calcul** : Déterminer la valeur (via fonction utilitaire)
3. **Mise à jour mémoire** : Ajouter au dictionnaire `infos`
4. **Persistence** : Insérer en base de données Spatialite
5. **Logging** : Tracer l'opération

### Fonction Utilisée

- `detect_layer_provider_type(layer)` (modules/appUtils.py:215)
  - Détecte le type de provider : `postgresql`, `spatialite`, `ogr`, `memory`, `unknown`
  - Gère la distinction Spatialite/OGR (même provider QGIS)
  - Normalise `postgres` → `postgresql`

### Sécurité

- Double protection : migration + fallback
- Logging à chaque étape pour diagnostic
- Gestion d'erreurs appropriée (try/except)
- N'impacte pas les layers récents (avec `layer_provider_type`)

## Vérification

Pour vérifier que le fix fonctionne :

1. Ouvrir un projet QGIS avec des layers FilterMate créés avant le 8/12/2025
2. Activer FilterMate
3. Vérifier dans les logs QGIS :
   ```
   INFO: Added layer_provider_type='postgresql' for layer test_layer_123
   DEBUG: Added layer_provider_type to database for layer test_layer_123
   ```
4. Aucune `KeyError` ne devrait apparaître
5. Les fonctionnalités de filtrage fonctionnent normalement

## Compatibilité

- ✅ QGIS 3.44.5-Solothurn
- ✅ Python 3.12.12
- ✅ Layers PostgreSQL/PostGIS
- ✅ Layers Spatialite
- ✅ Layers OGR
- ✅ Projets existants
- ✅ Nouveaux projets

## Références

- Issue: KeyError lors de `_create_spatial_index()`
- Guidelines: `.github/copilot-instructions.md` - Migration patterns
- Fonction: `detect_layer_provider_type()` - modules/appUtils.py:215
