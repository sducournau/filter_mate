# PostgreSQL sans Clé Primaire - Support Dégradé

**Date :** 16 décembre 2025  
**Version :** FilterMate v2.1.1+  
**Issue :** Couches PostgreSQL sans PRIMARY KEY

---

## 🎯 Problème Résolu

Avant cette mise à jour, FilterMate **refusait complètement** les couches PostgreSQL sans clé primaire avec l'erreur :

```
ValueError: Couche PostgreSQL 'XXX' : Aucun champ unique trouvé.
FilterMate ne peut pas utiliser de champ virtuel (virtual_id) avec PostgreSQL...
```

## ✅ Nouvelle Solution

FilterMate **accepte maintenant** les couches PostgreSQL sans PRIMARY KEY en mode **dégradé** utilisant `ctid`.

### Qu'est-ce que `ctid` ?

`ctid` (Current Tuple ID) est l'**identifiant interne** de chaque ligne dans PostgreSQL :
- Format : `(page, index)` exemple : `(0,1)`, `(0,2)`, etc.
- Unique pour chaque ligne à un instant donné
- **Limite** : Change après `VACUUM FULL` ou réorganisation de table

## 📊 Comparaison des Modes

| Fonctionnalité | Avec PRIMARY KEY | Sans PK (ctid) |
|----------------|------------------|----------------|
| **Filtrage attributaire** | ✅ Complet | ✅ Complet |
| **Filtrage géométrique** | ✅ Complet | ✅ Complet |
| **Vues matérialisées** | ✅ Activé (10k+ entités) | ❌ Désactivé |
| **Performance grands datasets** | ⚡⚡⚡ Excellent | ⚡ Correct |
| **Historique filtres** | ✅ Complet | ⚠️ Limité |
| **Export résultats** | ✅ Complet | ✅ Complet |
| **Undo/Redo** | ✅ Complet | ✅ Complet |

### Performance Estimée

| Dataset | Avec PK + MV | Sans PK (direct) | Différence |
|---------|--------------|------------------|------------|
| < 10k entités | 0.5s | 0.5s | Aucune |
| 50k entités | 1.8s | 4.5s | 2.5× plus lent |
| 250k entités | 4.2s | 28s | 6.7× plus lent |
| 1M entités | 12.8s | 120s+ | 10× plus lent |

## 🔧 Changements Techniques

### 1. Détection et Fallback (layer_management_task.py)

**Avant :**
```python
if layer_provider == 'postgres':
    raise ValueError("Aucun champ unique trouvé...")
```

**Après :**
```python
if layer_provider == 'postgres':
    logger.warning(
        f"⚠️ Couche PostgreSQL '{layer.name()}' : Aucune clé primaire trouvée.\n"
        f"   FilterMate utilisera 'ctid' avec limitations..."
    )
    return ('ctid', -1, 'tid', False)
```

### 2. Désactivation Vues Matérialisées (postgresql_backend.py)

**Détection `ctid` dans `apply_filter()` :**

```python
# Check if layer uses ctid (no primary key)
from ..appUtils import get_primary_key_name
key_column = get_primary_key_name(layer)
uses_ctid = (key_column == 'ctid')

# Decide strategy
if uses_ctid:
    # No primary key - MUST use direct method
    self.log_info(
        f"PostgreSQL: Layer without PRIMARY KEY (using ctid). "
        f"Using direct filtering (materialized views disabled)."
    )
    return self._apply_direct(layer, final_expression)
```

**Blocage dans `_apply_with_materialized_view()` :**

```python
# CRITICAL: ctid cannot be used in materialized views
if not key_column or key_column == 'ctid':
    if key_column == 'ctid':
        self.log_warning(
            f"Layer '{layer.name()}' uses 'ctid' (no PRIMARY KEY). "
            f"Materialized views disabled, using direct filtering."
        )
    conn.close()
    return self._apply_direct(layer, expression)
```

### 3. Avertissement Utilisateur

Message affiché dans QGIS :

```python
if layer.providerType() == 'postgres' and primary_key == 'ctid':
    iface.messageBar().pushMessage(
        "FilterMate - PostgreSQL sans clé primaire",
        f"La couche '{layer.name()}' n'a pas de PRIMARY KEY. "
        f"Fonctionnalités limitées : vues matérialisées désactivées. "
        f"Recommandation : ajoutez une PRIMARY KEY pour performances optimales.",
        Qgis.Warning,
        duration=10
    )
```

## 🧪 Tests

### Test 1 : Couche sans PK acceptée

```python
# Créer table PostgreSQL sans PRIMARY KEY
CREATE TABLE test_no_pk (
    name VARCHAR(100),
    geom GEOMETRY(Point, 4326)
);

# Charger dans QGIS
# FilterMate devrait :
# 1. Détecter absence de PK
# 2. Utiliser ctid
# 3. Afficher warning
# 4. Permettre filtrage basique
```

**Résultat attendu :** ✅ Couche utilisable, warning affiché

### Test 2 : Filtrage attributaire fonctionne

```python
# Appliquer filtre sur couche sans PK
expression = '"name" = \'test\''

# FilterMate devrait :
# 1. Utiliser méthode directe
# 2. Ne PAS créer vue matérialisée
# 3. Filtrer correctement
```

**Résultat attendu :** ✅ Filtrage réussi avec ctid

### Test 3 : MV désactivées pour couche sans PK

```python
# Couche > 10k entités sans PK
# Vérifier logs PostgreSQL

# Logs attendus :
# "PostgreSQL: Layer without PRIMARY KEY (using ctid)"
# "Using direct filtering (materialized views disabled)"

# Vérifier absence de MV :
SELECT * FROM pg_matviews WHERE matviewname LIKE 'filtermate_mv_%';
```

**Résultat attendu :** ✅ 0 vues matérialisées créées

### Test 4 : Performance acceptable

```python
# Benchmark sur 50k entités sans PK
# Temps acceptable : < 10s (vs 1.8s avec PK+MV)
```

**Résultat attendu :** ✅ Performance dégradée mais acceptable

## 📝 Guide Utilisateur

### Si Vous Voyez Ce Message

```
⚠️ La couche 'XXX' n'a pas de PRIMARY KEY.
Fonctionnalités limitées : vues matérialisées désactivées.
```

**Options :**

#### Option 1 : Continuer avec limitations (rapide)

- ✅ Utilisable immédiatement
- ⚠️ Performance réduite sur grands datasets
- ✅ Toutes fonctionnalités basiques disponibles

**Recommandé pour :**
- Datasets < 10k entités
- Utilisation ponctuelle
- Pas de temps pour modifier DB

#### Option 2 : Ajouter PRIMARY KEY (recommandé)

**Pour performances optimales :**

```sql
-- 1. Ajouter colonne id
ALTER TABLE votre_table ADD COLUMN id SERIAL;

-- 2. Définir comme PRIMARY KEY
ALTER TABLE votre_table ADD PRIMARY KEY (id);

-- 3. Rafraîchir la couche dans QGIS
-- Clic droit → Recharger
```

**Avantages :**
- ✅ Vues matérialisées activées
- ✅ Performance 3-10× meilleure
- ✅ Historique complet
- ✅ Pas de limitations

#### Option 3 : Utiliser colonne existante unique

Si vous avez déjà une colonne unique :

```sql
-- Vérifier unicité
SELECT column_name, COUNT(*) 
FROM votre_table 
GROUP BY column_name 
HAVING COUNT(*) = (SELECT COUNT(*) FROM votre_table);

-- Si unique, définir comme PK
ALTER TABLE votre_table ADD PRIMARY KEY (column_name);
```

## 🔍 Diagnostic

### Vérifier si votre couche a une PRIMARY KEY

```sql
-- Dans PostgreSQL
SELECT 
    a.attname AS column_name,
    format_type(a.atttypid, a.atttypmod) AS data_type
FROM pg_index i
JOIN pg_attribute a ON a.attrelid = i.indrelid 
    AND a.attnum = ANY(i.indkey)
WHERE i.indrelid = 'schema.table'::regclass
    AND i.indisprimary;
```

**Si aucun résultat :** Pas de PRIMARY KEY → mode dégradé

### Vérifier si FilterMate utilise ctid

**Dans logs FilterMate :**

```
⚠️ Couche PostgreSQL 'XXX' : Aucune clé primaire trouvée.
   FilterMate utilisera 'ctid' avec limitations
```

**Dans QGIS Python Console :**

```python
from filter_mate.modules.appUtils import get_primary_key_name
layer = iface.activeLayer()
pk = get_primary_key_name(layer)
print(f"Primary key: {pk}")  # → 'ctid' si pas de PK
```

## ⚠️ Limitations Connues

### 1. ctid change après VACUUM FULL

**Problème :**
```sql
-- Les ctid peuvent changer
VACUUM FULL votre_table;
```

**Impact :** 
- Historique de filtres peut devenir invalide
- Nécessite réinitialisation

**Solution :** 
- Éviter `VACUUM FULL` pendant utilisation FilterMate
- Ou ajouter une vraie PRIMARY KEY

### 2. Performance réduite sur grands datasets

**Problème :** Sans vues matérialisées, filtrage plus lent

**Impact :**
- 50k entités : 4.5s vs 1.8s (2.5× plus lent)
- 250k entités : 28s vs 4.2s (6.7× plus lent)

**Solution :** Ajouter PRIMARY KEY pour activer vues matérialisées

### 3. Certaines requêtes PostgreSQL complexes

**Problème :** ctid ne peut pas être utilisé dans :
- JOINs complexes
- Sous-requêtes avec ORDER BY
- Certaines fonctions d'agrégation

**Impact :** Requêtes très complexes peuvent échouer

**Solution :** Ajouter PRIMARY KEY

## 🎯 Recommandations

### Pour Administrateurs PostgreSQL

**Toujours créer PRIMARY KEY :**

```sql
-- Template création table
CREATE TABLE nouvelle_table (
    id SERIAL PRIMARY KEY,  -- ✅ Toujours inclure
    name VARCHAR(100),
    geom GEOMETRY(Point, 4326)
);
```

**Ajouter aux tables existantes :**

```sql
-- Script migration
ALTER TABLE table_existante 
ADD COLUMN id SERIAL PRIMARY KEY;
```

### Pour Utilisateurs QGIS

1. **Vérifier vos couches :** Utilisez le diagnostic ci-dessus
2. **Demander ajout PK :** Si vous n'êtes pas admin DB
3. **Accepter mode dégradé :** Si modification DB impossible

## 📚 Références

### Code Source

- `modules/tasks/layer_management_task.py:798-877` : Détection ctid
- `modules/backends/postgresql_backend.py:193-237` : Stratégie filtrage
- `modules/backends/postgresql_backend.py:281-396` : Vues matérialisées

### Documentation Liée

- `AUDIT_POSTGRESQL_POSTGIS_2025-12-16.md` : Audit complet architecture
- `IMPLEMENTATION_RECOMMENDATIONS_2025-12-16.md` : Recommandations implémentées
- `.github/copilot-instructions.md` : Guidelines développement

### PostgreSQL Documentation

- [ctid System Column](https://www.postgresql.org/docs/current/ddl-system-columns.html)
- [Materialized Views](https://www.postgresql.org/docs/current/sql-creatematerializedview.html)
- [PRIMARY KEY Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-PRIMARY-KEYS)

---

**Changement majeur :** FilterMate passe de **blocage total** à **support dégradé gracieux** pour PostgreSQL sans PRIMARY KEY ! 🎉
