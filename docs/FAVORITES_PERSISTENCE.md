# 🔖 Persistance des Favoris FilterMate

## Statut: ✅ IMPLÉMENTÉ (v4.0+)

Les favoris FilterMate sont **automatiquement persistants** via SQLite depuis la version 4.0.

---

## 📋 Architecture de Persistance

### Base de données SQLite

- **Fichier**: `~/.qgis3/FilterMate/filterMate_db.sqlite`
- **Table**: `fm_favorites`
- **Isolation**: Par `project_uuid` (chaque projet QGIS a ses propres favoris)

### Schéma de la table `fm_favorites`

```sql
CREATE TABLE fm_favorites (
    id TEXT PRIMARY KEY,
    project_uuid TEXT NOT NULL,
    name TEXT NOT NULL,
    expression TEXT NOT NULL,
    layer_name TEXT,
    layer_id TEXT,
    layer_provider TEXT,
    description TEXT,
    tags TEXT,  -- JSON array
    created_at TEXT,
    updated_at TEXT,
    use_count INTEGER DEFAULT 0,
    last_used_at TEXT,
    remote_layers TEXT,  -- JSON object
    spatial_config TEXT  -- JSON object
);

CREATE INDEX idx_favorites_project ON fm_favorites(project_uuid);
```

---

## ⚙️ Flux de Persistance

### 1. Ajout d'un favori

```
Utilisateur clique "Sauvegarder comme favori"
    ↓
FavoritesController._create_favorite()
    ↓
FavoritesService.add_favorite()
    ↓
FavoritesManager.add_favorite()  ← SAUVEGARDE IMMÉDIATE dans SQLite
    ↓
Émission du signal: favorite_added
    ↓
Rafraîchissement de l'interface
```

**Important**: La sauvegarde est **immédiate** et **atomique**. Pas besoin d'appeler `.save()`.

### 2. Chargement au démarrage

```
Ouverture du projet QGIS
    ↓
FilterMateApp.init_filterMate_db()
    ↓
DatabaseManager.initialize_database()
    ↓
FavoritesService.set_database(db_path, project_uuid)
    ↓
FavoritesManager._initialize_database()  ← Créer/migrer table
    ↓
FavoritesManager._load_favorites()  ← CHARGEMENT depuis SQLite
    ↓
Favoris disponibles dans l'interface
```

### 3. Changement de projet

```
Nouveau projet chargé
    ↓
Nouveau project_uuid détecté
    ↓
FavoritesService.set_database(db_path, new_project_uuid)
    ↓
FavoritesManager._load_favorites()  ← Charge favoris du nouveau projet
    ↓
Interface mise à jour avec favoris du nouveau projet
```

---

## 🔍 Logs de Debug

Les logs suivants indiquent une persistance correcte:

```
✓ FavoritesManager: Configuring database
  → Path: /home/user/.qgis3/FilterMate/filterMate_db.sqlite
  → Project UUID: a1b2c3d4-e5f6-7890-abcd-ef1234567890

✓ FavoritesManager: Database initialized at /home/user/.qgis3/FilterMate/filterMate_db.sqlite

✓ Loaded 3 favorites for project a1b2c3d4-e5f6-7890-abcd-ef1234567890
  → Database: /home/user/.qgis3/FilterMate/filterMate_db.sqlite
  → Favorites: Filtre Villes, Filtre Routes, Filtre Bâtiments

✓ Favorite 'Mon Filtre' saved to database (ID: f1e2d3c4-b5a6-7890-cdef-1234567890ab, Project: a1b2...)
  → Database: /home/user/.qgis3/FilterMate/filterMate_db.sqlite
  → Expression: "population" > 10000 AND "type" = 'city'
```

---

## 🚨 Diagnostic de Problèmes

### Problème: "Les favoris ne sont pas sauvegardés"

**Vérifications**:

1. ✅ **Vérifier que la base SQLite existe**:
   ```python
   from config.config import ENV_VARS
   db_path = ENV_VARS["PLUGIN_CONFIG_DIRECTORY"] + "/filterMate_db.sqlite"
   print(f"DB existe? {os.path.exists(db_path)}")
   ```

2. ✅ **Vérifier que la table fm_favorites existe**:
   ```python
   import sqlite3
   conn = sqlite3.connect(db_path)
   cursor = conn.cursor()
   cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fm_favorites'")
   print(f"Table existe? {cursor.fetchone() is not None}")
   conn.close()
   ```

3. ✅ **Vérifier le project_uuid**:
   ```python
   from qgis.core import QgsExpressionContextUtils, QgsProject
   project_uuid = QgsExpressionContextUtils.projectScope(QgsProject.instance()).variable('filterMate_db_project_uuid')
   print(f"Project UUID: {project_uuid}")
   ```

4. ✅ **Compter les favoris dans la base**:
   ```python
   conn = sqlite3.connect(db_path)
   cursor = conn.cursor()
   cursor.execute("SELECT COUNT(*) FROM fm_favorites WHERE project_uuid = ?", (project_uuid,))
   count = cursor.fetchone()[0]
   print(f"Favoris dans la base: {count}")
   conn.close()
   ```

### Problème: "Les favoris disparaissent au redémarrage"

**Causes possibles**:

- ❌ **project_uuid change** → Vérifier que le projet est sauvegardé (pas "untitled")
- ❌ **Base SQLite effacée** → Vérifier permissions en écriture
- ❌ **Mauvais chemin de base** → Vérifier `ENV_VARS["PLUGIN_CONFIG_DIRECTORY"]`

**Solution**: Exécuter le script de test:
```python
exec(open('/path/to/TEST_FAVORITES_PERSISTENCE.py').read())
```

### Problème: "Favoris d'autres projets visibles"

**Cause**: Problème d'isolation par `project_uuid`

**Vérification**:
```python
# Lister tous les favoris de tous les projets
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT project_uuid, name FROM fm_favorites")
for row in cursor.fetchall():
    print(f"Project: {row[0][:8]}... → Favori: {row[1]}")
conn.close()
```

---

## 🔧 Migration depuis version < 4.0

Les anciennes versions de FilterMate stockaient les favoris dans les **variables de projet QGIS** (format JSON dans le fichier `.qgs`/`.qgz`).

La migration est **automatique** au premier chargement:

```
Chargement du projet (avec anciens favoris dans .qgs)
    ↓
FavoritesManager._migrate_from_project_variables()
    ↓
Favoris copiés dans SQLite
    ↓
Suppression des variables de projet (nettoyage)
```

**Note**: Les anciens favoris restent dans le fichier `.qgs` mais ne sont plus utilisés.

---

## 📊 Statistiques d'utilisation

Chaque favori garde des **statistiques d'utilisation**:

- `use_count`: Nombre de fois utilisé
- `last_used_at`: Timestamp dernière utilisation
- `created_at`: Timestamp de création
- `updated_at`: Timestamp dernière modification

Ces données permettent de trier les favoris par:
- Plus récents (`get_recent_favorites()`)
- Plus utilisés (`get_most_used_favorites()`)

---

## 🎯 Points Clés

✅ **Sauvegarde automatique** - Pas besoin d'appeler `.save()`
✅ **Isolation par projet** - Chaque projet QGIS a ses propres favoris
✅ **Persistance SQLite** - Pas de dépendance au fichier `.qgs`
✅ **Migration automatique** - Depuis anciennes versions
✅ **Robuste** - Gestion d'erreurs et logging détaillé

---

## 📝 API Développeur

### Ajouter un favori

```python
from core.services.favorites_service import FavoritesService

service = FavoritesService()
service.set_database(db_path, project_uuid)

favorite_id = service.add_favorite(
    name="Mon Filtre",
    expression='"population" > 10000',
    layer_name="cities",
    description="Grandes villes"
)
```

### Charger les favoris

```python
favorites = service.get_all_favorites()
for fav in favorites:
    print(f"{fav.name}: {fav.expression}")
```

### Appliquer un favori

```python
favorite = service.get_favorite(favorite_id)
if favorite:
    # L'expression est dans favorite.expression
    layer.setSubsetString(favorite.expression)
```

---

## 🧪 Test Automatisé

Exécuter le script de test:

```bash
# Dans QGIS Python Console
exec(open('/path/to/TEST_FAVORITES_PERSISTENCE.py').read())
```

Résultat attendu:
```
========================================
TEST DE PERSISTANCE DES FAVORIS FILTERMATE
========================================
✓ Modules importés avec succès
✓ FavoritesManager créé
✓ Favori ajouté: Test Filtre 1
✓ Favori ajouté: Test Filtre 2
✓ Favori ajouté: Test Filtre 3
✓ Nouveau FavoritesManager créé
  → Favoris chargés: 3
✓ TEST RÉUSSI!
  → Persistance SQLite: FONCTIONNELLE ✓
  → Isolation par projet: FONCTIONNELLE ✓
```

---

**Dernière mise à jour**: 2026-01-18
**Version**: 4.0-alpha
**Auteur**: Barry (Quick Flow Solo Dev)
