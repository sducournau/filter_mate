# Primary Key Detection System - FilterMate

**Last Updated:** 16 décembre 2025
**Status:** ✅ Vérifié et Fonctionnel

## Vue d'Ensemble

FilterMate implémente un système robuste de détection des clés primaires qui s'adapte à chaque type de provider (PostgreSQL, Spatialite, OGR, Memory) avec des stratégies optimisées pour la performance et la fiabilité.

## Fichier Principal

**Location:** `modules/tasks/layer_management_task.py`
**Méthode:** `search_primary_key_from_layer()` (lignes 814-926)

## Stratégie de Détection par Provider

### 1. PostgreSQL (`postgres`)

**Objectif:** Éviter le freeze sur grandes tables (uniqueValues() charge tout en mémoire)

**Ordre de détection:**

1. **Clé primaire déclarée** (priorité absolue)
   ```python
   if len(primary_key_index) > 0:
       field = layer.fields()[field_id]
       if is_postgresql:
           # CRITICAL: Pas de vérification d'unicité (évite freeze)
           return (field.name(), field_id, field.typeName(), field.isNumeric())
   ```
   - ✅ Utilisation directe sans vérification
   - ✅ Fait confiance à la contrainte PostgreSQL
   - ✅ Pas d'appel à `uniqueValues()`

2. **Champ contenant 'id'** (fallback si pas de PK)
   ```python
   if 'id' in field_name_lower:
       if is_postgresql:
           logger.info(f"Found field with 'id': '{field.name()}', using as primary key")
           return (field.name(), index, field.typeName(), field.isNumeric())
   ```
   - ✅ Détection case-insensitive
   - ✅ Assume l'unicité (pas de vérification)
   - ✅ Recherche: 'id', 'gid', 'object_id', 'feature_id', etc.

3. **Utilisation de 'ctid'** (dernier recours)
   ```python
   if is_postgresql:
       logger.warning(f"Using 'ctid' with limitations...")
       return ('ctid', -1, 'tid', False)
   ```
   - ⚠️ Identifiant interne PostgreSQL
   - ⚠️ Limitations:
     - Pas de vues matérialisées
     - Historique de filtres limité
     - Performance réduite
   - ✅ Permet quand même le filtrage basique

**Avertissement utilisateur:**
```python
iface.messageBar().pushMessage(
    "FilterMate - PostgreSQL sans clé primaire",
    f"La couche '{layer.name()}' n'a pas de PRIMARY KEY. "
    f"Fonctionnalités limitées : vues matérialisées désactivées. "
    f"Recommandation : ajoutez une PRIMARY KEY pour performances optimales.",
    Qgis.Warning,
    duration=10
)
```

### 2. Spatialite (`spatialite`)

**Stratégie:** Vérification d'unicité acceptable pour tables moyennes

**Ordre de détection:**

1. **Clé primaire déclarée**
   - Vérifie l'unicité si `feature_count` connu
   - Utilise directement si `feature_count == -1`

2. **Champ avec 'id'**
   - Vérifie l'unicité: `len(uniqueValues()) == feature_count`

3. **Premier champ unique**
   - Itère sur tous les champs
   - Vérifie l'unicité de chacun

4. **Création de 'virtual_id'**
   ```python
   new_field = QgsField('virtual_id', QMetaType.Type.LongLong)
   layer.addExpressionField('@row_number', new_field)
   return ('virtual_id', index, 'LongLong', True)
   ```

### 3. OGR/Shapefile (`ogr`)

**Stratégie:** Utilise le FID natif

**Détection:**
- Toujours basée sur `primaryKeyAttributes()` (retourne FID)
- Vérifie l'unicité si table petite/moyenne
- Généralement index 0, nom 'fid' ou 'FID'

**Résultat typique:**
```python
return ('fid', 0, 'Integer64', True)
```

### 4. Memory (`memory`)

**Stratégie:** Création automatique de virtual_id si nécessaire

**Comportement:**
- Cherche d'abord un champ unique existant
- Si aucun: crée `virtual_id` avec `@row_number`
- Fonctionne uniquement pour couches non-base de données

## Optimisations de Performance

### 1. Éviter `uniqueValues()` sur PostgreSQL

**Problème:** `layer.uniqueValues(field_id)` charge TOUTES les valeurs en mémoire

**Solution:**
```python
if is_postgresql:
    # Skip uniqueness check
    return (field.name(), field_id, field.typeName(), field.isNumeric())
```

**Impact:** Évite freeze sur tables > 100k lignes

### 2. Feature Count Inconnu

**Cas:** `layer.featureCount() == -1` (vues, requêtes complexes)

**Stratégie:**
```python
if feature_count == -1:
    # Trust declared PK without verification
    return (field.name(), field_id, field.typeName(), field.isNumeric())
```

### 3. Clé Primaire Composite

**Cas:** Multiple champs dans `primaryKeyAttributes()`

**Stratégie:** Utiliser le premier champ uniquement
```python
if len(primary_key_index) > 0:
    field_id = primary_key_index[0]  # Premier champ seulement
```

**Avertissement:** "Clé primaire composée (N champs). FilterMate utilisera le premier champ."

## Structure de Retour

```python
def search_primary_key_from_layer(layer) -> tuple:
    """
    Returns:
        tuple: (field_name, field_index, field_type, is_numeric)
        False: if canceled
    """
    return (
        'id',        # str: Nom du champ
        0,           # int: Index du champ (-1 pour ctid)
        'INTEGER',   # str: Type du champ
        True         # bool: Est numérique
    )
```

## Utilisation dans PROJECT_LAYERS

**Template JSON:**
```python
self.json_template_layer_infos = '{
    "primary_key_name": "%s",
    "primary_key_idx": %s,
    "primary_key_type": "%s",
    "primary_key_is_numeric": %s
}'
```

**Utilisation dans expressions:**
```python
# Dans _ensure_all_layer_properties_exist() (ligne 361)
exploring[prop_name] = str(primary_key)  # Initialise expressions avec PK
```

## Tests et Validation

### Tests Unitaires

**Fichier:** `tests/test_primary_key_detection.py`

**Coverage:**
- ✅ PostgreSQL avec PRIMARY KEY
- ✅ PostgreSQL sans PRIMARY KEY (ctid)
- ✅ PostgreSQL avec champ 'id' non déclaré
- ✅ Spatialite avec/sans PRIMARY KEY
- ✅ OGR/Shapefile (FID)
- ✅ Memory layers (virtual_id)
- ✅ Clés composites
- ✅ Grandes tables (pas de vérification)
- ✅ Feature count inconnu
- ✅ Variantes de noms ('id', 'ID', 'gid', 'object_id', etc.)

**Exécution:**
```bash
pytest tests/test_primary_key_detection.py -v
```

### Diagnostic en Temps Réel

**Fichier:** `tools/diagnostic/test_pk_detection_live.py`

**Usage dans QGIS:**
```python
import test_pk_detection_live
test_pk_detection_live.analyze_all_layers()
```

**Output exemple:**
```
================================================================================
Couche: ma_table_postgresql
Provider: postgres
Features: 1250
--------------------------------------------------------------------------------
✅ Clé primaire déclarée:
   - gid (index 0, type INTEGER)

✨ FilterMate utilisera: gid
```

## Problèmes Connus et Solutions

### 1. PostgreSQL sans PRIMARY KEY

**Symptôme:** Message "n'a pas de PRIMARY KEY", utilise 'ctid'

**Solution:**
```sql
ALTER TABLE ma_table ADD PRIMARY KEY (id);
-- ou
ALTER TABLE ma_table ADD COLUMN gid SERIAL PRIMARY KEY;
```

### 2. Clé Primaire Composite

**Symptôme:** Seul le premier champ est utilisé

**Solution:**
```sql
-- Créer une colonne ID unique
ALTER TABLE ma_table ADD COLUMN id SERIAL PRIMARY KEY;
```

### 3. virtual_id dans PostgreSQL

**Problème:** Ne peut pas être utilisé dans les requêtes SQL serveur

**État:** Impossible - PostgreSQL retourne toujours 'ctid' comme fallback

**Impact:** Vues matérialisées désactivées, mais filtrage basique fonctionne

## Logs de Diagnostic

**Activer debug logging:**
```python
import logging
logging.getLogger('filter_mate').setLevel(logging.DEBUG)
```

**Messages clés:**

PostgreSQL avec PK:
```
DEBUG: PostgreSQL layer: trusting declared primary key 'gid' (no uniqueness check)
```

PostgreSQL sans PK:
```
WARNING: ⚠️ Couche PostgreSQL 'ma_table' : Aucune clé primaire ou champ 'id' trouvé.
         FilterMate utilisera 'ctid' avec limitations
```

## Intégration avec Backends

**PostgreSQL Backend:**
- Détecte `primary_key == 'ctid'`
- Désactive vues matérialisées
- Utilise requêtes directes uniquement

**Spatialite Backend:**
- Utilise le primary_key normalement
- Crée des tables temporaires avec index

**OGR Backend:**
- Utilise FID pour identifier les features
- Génère des fichiers d'index (.qix)

## Recommandations

### Pour Développeurs

1. **Toujours vérifier `is_postgresql`** avant d'appeler `uniqueValues()`
2. **Tester avec grandes tables** (> 100k lignes)
3. **Logger les décisions de détection** pour diagnostic
4. **Gérer le cas 'ctid'** dans les backends

### Pour Utilisateurs

1. **PostgreSQL:** Toujours définir PRIMARY KEY sur les tables
2. **Spatialite:** S'assurer qu'un champ 'id' existe
3. **Shapefiles:** Convertir en GeoPackage pour meilleure gestion
4. **Memory:** Accepter 'virtual_id' (fonctionne correctement)

## Évolutions Futures

**Possibles améliorations:**

1. **Cache de détection** (éviter re-détection à chaque session)
2. **Configuration manuelle** (permettre override du PK)
3. **Support multi-champs** (clés composites natives)
4. **Détection de séquences** (SERIAL, IDENTITY)
5. **Validation de contraintes** (via metadata PostgreSQL)

## Références

- Code: `modules/tasks/layer_management_task.py:814-926`
- Tests: `tests/test_primary_key_detection.py`
- Test ancien (obsolète): `tests/test_postgresql_layer_handling.py:218-265`
- Diagnostic: `tools/diagnostic/test_pk_detection_live.py`
- Documentation: `tools/diagnostic/README_PRIMARY_KEY_DETECTION.md`
