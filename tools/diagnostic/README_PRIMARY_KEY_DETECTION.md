# Outils de Diagnostic - Détection des Clés Primaires

Ce dossier contient des outils pour vérifier et diagnostiquer la détection des clés primaires dans FilterMate.

## 📋 Fichiers

### 1. `test_pk_detection_live.py` - Diagnostic en temps réel

Script à exécuter dans la console Python de QGIS pour analyser les couches du projet actuel.

**Utilisation dans QGIS :**

```python
# Dans la console Python de QGIS
import sys
sys.path.append('/chemin/vers/filter_mate/tools/diagnostic')
import test_pk_detection_live
test_pk_detection_live.analyze_all_layers()
```

Ou simplement ouvrir le script et l'exécuter dans QGIS.

**Ce qu'il fait :**
- ✅ Analyse toutes les couches vectorielles du projet
- ✅ Vérifie les clés primaires déclarées
- ✅ Cherche les champs avec 'id' dans le nom
- ✅ Identifie les problèmes de configuration
- ✅ Fournit des recommandations spécifiques par provider

**Rapport généré :**
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

### 2. Tests Unitaires

Les tests unitaires sont dans `/tests/test_primary_key_detection.py`

**Exécution :**

```bash
# Depuis la racine du plugin
python -m pytest tests/test_primary_key_detection.py -v
```

**Coverage des tests :**
- PostgreSQL avec PRIMARY KEY déclarée
- PostgreSQL sans PRIMARY KEY (utilise `ctid`)
- PostgreSQL avec champ 'id' non déclaré comme PK
- Spatialite avec/sans PRIMARY KEY
- OGR/Shapefile (utilise FID)
- Memory layers (crée `virtual_id`)
- Clés primaires composites
- Grandes tables (pas de vérification d'unicité)
- Feature count inconnu (-1)

## 🔍 Comment FilterMate Détecte les Clés Primaires

### Ordre de Recherche

```
1. Clé primaire déclarée par QGIS
   └─> PostgreSQL: utilise directement (pas de vérification d'unicité)
   └─> Autres: vérifie l'unicité si < 1000 features

2. Champ contenant 'id' dans le nom
   └─> PostgreSQL: utilise sans vérification
   └─> Autres: vérifie l'unicité

3. Premier champ avec valeurs uniques
   └─> PostgreSQL: saute (évite freeze)
   └─> Autres: teste l'unicité

4. Fallback
   └─> PostgreSQL: utilise 'ctid' (avec limitations)
   └─> Memory/autres: crée 'virtual_id'
```

### Cas Spéciaux par Provider

#### PostgreSQL (`postgres`)

**Avec PRIMARY KEY déclarée :**
```python
# ✅ Utilisation directe, pas de vérification d'unicité
# Évite le freeze sur grandes tables
result = ('id', 0, 'INTEGER', True)
```

**Sans PRIMARY KEY mais avec champ 'id' :**
```python
# ✅ Détection automatique du champ 'id'
# Suppose que le champ est unique (pas de vérification)
result = ('object_id', 2, 'BIGINT', True)
```

**Sans PRIMARY KEY ni champ 'id' :**
```python
# ⚠️ Utilise 'ctid' avec limitations
# - Pas de vues matérialisées
# - Pas d'historique de filtres
result = ('ctid', -1, 'tid', False)
```

#### Spatialite (`spatialite`)

**Avec PRIMARY KEY :**
```python
# Vérifie l'unicité si < 1000 features
result = ('fid', 0, 'INTEGER', True)
```

**Sans PRIMARY KEY :**
```python
# Cherche champ avec 'id', vérifie unicité
# Ou crée 'virtual_id'
result = ('virtual_id', 5, 'LongLong', True)
```

#### OGR/Shapefile (`ogr`)

**Toujours avec FID :**
```python
# Utilise automatiquement le FID
result = ('fid', 0, 'Integer64', True)
```

#### Memory (`memory`)

**Sans champ unique :**
```python
# Crée automatiquement virtual_id
result = ('virtual_id', 3, 'LongLong', True)
```

## ⚠️ Problèmes Courants et Solutions

### Problème 1: PostgreSQL sans PRIMARY KEY

**Symptômes :**
- Message: "La couche n'a pas de PRIMARY KEY"
- Utilisation de `ctid`
- Performances réduites

**Solution :**
```sql
-- Ajoutez une PRIMARY KEY à votre table PostgreSQL
ALTER TABLE ma_table ADD PRIMARY KEY (id);

-- Ou créez une colonne serial
ALTER TABLE ma_table ADD COLUMN gid SERIAL PRIMARY KEY;
```

### Problème 2: Clé Primaire Composite

**Symptômes :**
- Avertissement: "Clé primaire composée (N champs)"
- Seul le premier champ est utilisé

**Solution :**
```sql
-- Option 1: Créer une colonne ID unique
ALTER TABLE ma_table ADD COLUMN id SERIAL PRIMARY KEY;

-- Option 2: Accepter que seul le premier champ soit utilisé
-- (FilterMate fonctionne mais moins optimal)
```

### Problème 3: Shapefile sans FID visible

**Symptômes :**
- Pas de champ 'fid' dans la table attributaire
- FilterMate ne trouve pas de clé primaire

**Solution :**
Le FID existe toujours en interne. Si problème :
1. Convertir en GeoPackage (meilleure gestion des IDs)
2. Ou ajouter un champ ID explicite dans le Shapefile

### Problème 4: Memory Layer sans ID

**Symptômes :**
- FilterMate crée 'virtual_id'
- Avertissement dans les logs

**Solution :**
C'est normal et attendu pour les couches mémoire. Le `virtual_id` fonctionne correctement.

## 📊 Analyse des Résultats

### Rapport Optimal

```
Provider: postgres
  Avec PK déclarée: 5
  Sans PK déclarée: 0

✅ Toutes les couches ont une configuration optimale
```

### Rapport avec Avertissements

```
Provider: postgres
  Avec PK déclarée: 3
  Sans PK déclarée: 2

⚠️ 2 couche(s) PostgreSQL sans PRIMARY KEY!
   Recommandation: ajoutez des PRIMARY KEY pour performances optimales
```

## 🧪 Tests de Validation

Pour vérifier que tout fonctionne :

```bash
# 1. Tests unitaires
pytest tests/test_primary_key_detection.py -v

# 2. Tests avec vraies données
# Dans QGIS, exécutez test_pk_detection_live.py

# 3. Vérification manuelle
# Ouvrez FilterMate et vérifiez les logs pour chaque couche ajoutée
```

## 📝 Logs Utiles

Activez le debug logging dans FilterMate pour voir les détails :

```python
import logging
logging.getLogger('filter_mate').setLevel(logging.DEBUG)
```

**Logs attendus pour PostgreSQL avec PK :**
```
DEBUG: PostgreSQL layer: trusting declared primary key 'gid' (no uniqueness check)
```

**Logs attendus pour PostgreSQL sans PK :**
```
WARNING: ⚠️ Couche PostgreSQL 'ma_table' : Aucune clé primaire ou champ 'id' trouvé.
         FilterMate utilisera 'ctid' (identifiant interne PostgreSQL) avec limitations
```

## 🔗 Références

- Code source: `modules/tasks/layer_management_task.py` (ligne 814)
- Tests: `tests/test_primary_key_detection.py`
- Documentation: `.github/copilot-instructions.md`
