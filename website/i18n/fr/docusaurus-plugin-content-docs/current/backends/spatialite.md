---
sidebar_position: 3
---

# Backend Spatialite

Le backend Spatialite offre d'**excellentes performances** pour les jeux de données petits à moyens sans nécessiter de serveurs de bases de données externes. Il exploite les capacités spatiales intégrées de SQLite avec des index R-tree pour un filtrage efficace.

:::tip Zone de confort
Spatialite est optimal pour les jeux de données de **moins de 50 000 entités** et ne nécessite **aucune installation supplémentaire** — il fonctionne directement avec Python.
:::

## Vue d'ensemble

Le backend Spatialite de FilterMate se connecte aux bases de données SQLite locales avec l'extension spatiale Spatialite. Il crée des tables temporaires avec des index spatiaux pour effectuer le filtrage géométrique efficacement.

### Avantages clés

- ⚡ **Performances rapides** sur les jeux de données < 50k entités
- 🔧 **Aucune configuration requise** — SQLite intégré à Python
- 📦 **Portable** — base de données en fichier unique
- 🗺️ **Index spatiaux R-tree** pour des recherches optimisées
- 💾 **Traitement local** — pas de surcharge réseau
- 🚀 **Automatique** — fonctionne immédiatement avec les fichiers .sqlite

## Quand le backend Spatialite est utilisé

FilterMate sélectionne automatiquement le backend Spatialite quand :

1. ✅ La source de la couche est Spatialite/SQLite avec extension spatiale
2. ✅ Le chemin du fichier pointe vers un fichier `.sqlite`, `.db` ou `.spatialite`
3. ✅ L'extension Spatialite est disponible (automatiquement en Python 3.7+)

:::info Avertissement de performance
Pour les jeux de données de **plus de 50 000 entités**, FilterMate affichera un avertissement de performance suggérant PostgreSQL pour de meilleures performances.
:::

## Installation

### Prérequis

- **Python 3.7+** (inclus avec QGIS 3.x)
- **Extension Spatialite** (généralement pré-installée)

### Vérification

Spatialite est généralement disponible par défaut. Vérifiez dans la Console Python QGIS :

```python
import sqlite3

conn = sqlite3.connect(':memory:')
conn.enable_load_extension(True)

try:
    conn.load_extension('mod_spatialite')
    print("✓ Extension Spatialite disponible")
except Exception as e:
    # Fallback Windows
    try:
        conn.load_extension('mod_spatialite.dll')
        print("✓ Extension Spatialite disponible (Windows)")
    except:
        print(f"✗ Extension Spatialite non trouvée : {e}")

conn.close()
```

### Installation manuelle (si nécessaire)

#### Linux
```bash
sudo apt-get install libspatialite7
# ou
sudo yum install libspatialite
```

#### macOS
```bash
brew install libspatialite
```

#### Windows
Spatialite est inclus avec l'installation QGIS OSGeo4W. Si manquant :
1. Télécharger depuis https://www.gaia-gis.it/gaia-sins/windows-bin-amd64/
2. Extraire `mod_spatialite.dll` dans le dossier `DLLs` de Python

## Fonctionnalités

### 1. Tables temporaires

FilterMate crée des **tables temporaires** pour stocker les résultats filtrés :

```sql
-- Exemple de table temporaire créée par FilterMate
CREATE TEMP TABLE filtermate_filtered_123 AS
SELECT *
FROM ma_couche
WHERE ST_Intersects(
    geometry,
    (SELECT geometry FROM couche_filtre WHERE id = 1)
);

-- Index spatial créé automatiquement
SELECT CreateSpatialIndex('filtermate_filtered_123', 'geometry');
```

**Avantages :**
- Création et requêtage rapides
- Nettoyage automatique en fin de session
- Pas de modifications permanentes de la base
- Efficace en mémoire pour < 50k entités

### 2. Index spatiaux R-tree

Spatialite utilise des **index R-tree** pour les requêtes spatiales :

```sql
-- Vérifier les index spatiaux
SELECT * FROM geometry_columns
WHERE f_table_name = 'ma_couche';

-- FilterMate crée automatiquement les index R-tree
SELECT CreateSpatialIndex('ma_couche', 'geometry');

-- L'index est utilisé automatiquement pour les requêtes spatiales
SELECT * FROM ma_couche
WHERE ST_Intersects(geometry, MakePoint(100, 50, 4326));
```

:::tip Impact sur les performances
Les index R-tree offrent une accélération de 10-100x sur les requêtes spatiales selon la distribution des données.
:::

### 3. Opérations spatiales

Spatialite supporte ~90% des fonctions PostGIS :

| Fonction | Spatialite | Équivalent |
|----------|-----------|------------|
| `ST_Intersects()` | ✅ Support complet | Identique à PostGIS |
| `ST_Contains()` | ✅ Support complet | Identique à PostGIS |
| `ST_Within()` | ✅ Support complet | Identique à PostGIS |
| `ST_Buffer()` | ✅ Support complet | Identique à PostGIS |
| `ST_Distance()` | ✅ Support complet | Identique à PostGIS |
| `ST_Area()` | ✅ Support complet | Identique à PostGIS |
| `ST_Length()` | ✅ Support complet | Identique à PostGIS |
| `ST_Union()` | ✅ Support complet | Identique à PostGIS |
| `ST_Difference()` | ✅ Support complet | Identique à PostGIS |
| `ST_Intersection()` | ✅ Support complet | Identique à PostGIS |

**Exemple de requête :**

```sql
-- Trouver toutes les entités à moins de 100m d'un point
SELECT *
FROM ma_couche
WHERE ST_Intersects(
    geometry,
    ST_Buffer(MakePoint(100, 50, 4326), 100)
);
```

### 4. Optimisation de base de données

FilterMate applique plusieurs optimisations :

- **VACUUM** — Récupère l'espace inutilisé
- **ANALYZE** — Met à jour les statistiques de requête
- **Hints d'index spatial** — Force l'utilisation du R-tree
- **Regroupement des transactions** — Groupe les opérations

Exemple :

```sql
-- Après création de table temp
ANALYZE filtermate_filtered_123;

-- Vacuum au nettoyage
VACUUM;
```

## Configuration

### Emplacement de la base de données

Les bases de données Spatialite sont des fichiers uniques :

```
/chemin/vers/donnees/
  ├── mes_donnees.sqlite       # Base de données principale
  ├── mes_donnees.sqlite-shm   # Mémoire partagée (auto-créé)
  └── mes_donnees.sqlite-wal   # Journal d'écriture anticipée (auto-créé)
```

### Paramètres de cache

Optimisez Spatialite pour les performances :

```sql
-- Dans la Console Python QGIS (par session)
import sqlite3

conn = sqlite3.connect('/chemin/vers/donnees.sqlite')

-- Augmenter la taille du cache (en KB)
conn.execute("PRAGMA cache_size = 100000")  -- Cache de 100MB

-- Activer les E/S mappées en mémoire
conn.execute("PRAGMA mmap_size = 268435456")  -- mmap de 256MB

-- Mode WAL pour une meilleure concurrence
conn.execute("PRAGMA journal_mode = WAL")

conn.close()
```

### Paramètres de performance

Pour des performances optimales dans `config/config.json` :

```json
{
  "SPATIALITE": {
    "cache_size_kb": 100000,
    "enable_mmap": true,
    "journal_mode": "WAL",
    "vacuum_on_cleanup": true
  }
}
```

## Utilisation

### Filtrage basique

1. **Charger la couche Spatialite** dans QGIS (Couche → Ajouter une couche → Vecteur)
2. **Ouvrir le plugin FilterMate**
3. **Configurer les options** de filtre
4. **Cliquer sur « Appliquer le filtre »**

FilterMate automatiquement :
- Détecte le backend Spatialite
- Crée une table temporaire avec index spatial
- Ajoute la couche filtrée à QGIS
- Affiche l'indicateur de backend : **[SQLite]**

### Créer une base de données Spatialite

À partir de données existantes :

```python
# Dans la Console Python QGIS
from qgis.core import QgsVectorFileWriter

layer = iface.activeLayer()
options = QgsVectorFileWriter.SaveVectorOptions()
options.driverName = "SQLite"
options.layerName = "ma_couche"
options.datasourceOptions = ["SPATIALITE=YES"]

QgsVectorFileWriter.writeAsVectorFormatV3(
    layer,
    "/chemin/vers/sortie.sqlite",
    QgsCoordinateTransformContext(),
    options
)
```

### Traitement par lots

Pour plusieurs couches Spatialite :

```python
# FilterMate gère efficacement plusieurs couches
# Chacune obtient sa propre table temporaire
```

## Optimisation des performances

### Pour les petits jeux de données (< 10k entités)

- **Aucune configuration spéciale nécessaire**
- Utilisez les paramètres par défaut
- Performance comparable à PostgreSQL

### Pour les jeux de données moyens (10k - 50k entités)

- **Augmentez la taille du cache :**
  ```sql
  PRAGMA cache_size = 50000;  -- 50MB
  ```

- **Activez le mode WAL :**
  ```sql
  PRAGMA journal_mode = WAL;
  ```

- **Créez manuellement les index spatiaux** s'ils manquent :
  ```sql
  SELECT CreateSpatialIndex('ma_couche', 'geometry');
  ```

### Pour les grands jeux de données (50k - 500k entités)

:::warning Considération de performance
Envisagez d'utiliser le **backend PostgreSQL** pour de meilleures performances. Spatialite peut gérer ces tailles mais sera plus lent.
:::

Si vous utilisez Spatialite :

- **Maximisez le cache :**
  ```sql
  PRAGMA cache_size = 200000;  -- 200MB
  ```

- **Activez les E/S mappées en mémoire :**
  ```sql
  PRAGMA mmap_size = 536870912;  -- 512MB
  ```

- **Exécutez VACUUM ANALYZE :**
  ```sql
  VACUUM;
  ANALYZE;
  ```

## Limitations

### Comparé à PostgreSQL

| Fonctionnalité | Spatialite | PostgreSQL |
|----------------|-----------|-----------|
| Taille max pratique | ~500k entités | 10M+ entités |
| Accès concurrent | Limité | Excellent |
| Opérations côté serveur | ❌ Non | ✅ Oui |
| Requêtes parallèles | ❌ Non | ✅ Oui |
| Accès réseau | ❌ Non (basé fichier) | ✅ Oui |
| Isolation des transactions | Basique | Avancée |
| Optimisation des requêtes | Bonne | Excellente |

### Limitations connues

1. **Mono-utilisateur** — Le verrouillage de fichier empêche le vrai accès concurrent
2. **Pas de traitement parallèle** — Les requêtes s'exécutent en mono-thread
3. **Contraintes de mémoire** — Les grosses opérations peuvent consommer beaucoup de RAM
4. **Pas d'accès distant** — Doit avoir un accès local au fichier

:::tip Quand changer
Si vous travaillez régulièrement avec **plus de 50k entités**, envisagez de migrer vers PostgreSQL pour une amélioration de performance de 5-10x.
:::

## Dépannage

### Problème : « Extension Spatialite non trouvée »

**Symptôme :** Erreur lors de l'ouverture de la base de données Spatialite

**Solution :**

1. **Vérifier l'environnement Python :**
   ```python
   import sqlite3
   print(sqlite3.sqlite_version)  # Devrait être 3.7+
   ```

2. **Essayer des noms d'extension alternatifs :**
   ```python
   conn.load_extension('mod_spatialite')      # Linux/macOS
   conn.load_extension('mod_spatialite.dll')  # Windows
   conn.load_extension('libspatialite')       # Alternative
   ```

3. **Installer Spatialite** (voir section Installation)

### Problème : « Requêtes lentes malgré l'index spatial »

**Symptôme :** Le filtrage prend plus de temps que prévu

**Solution :**

1. **Vérifier que l'index spatial existe :**
   ```sql
   SELECT * FROM geometry_columns WHERE f_table_name = 'ma_couche';
   ```

2. **Vérifier l'index R-tree :**
   ```sql
   SELECT * FROM sqlite_master
   WHERE type = 'table' AND name LIKE 'idx_%_geometry';
   ```

3. **Reconstruire l'index spatial :**
   ```sql
   SELECT DisableSpatialIndex('ma_couche', 'geometry');
   SELECT CreateSpatialIndex('ma_couche', 'geometry');
   ```

4. **Exécuter ANALYZE :**
   ```sql
   ANALYZE ma_couche;
   ```

### Problème : « Base de données verrouillée »

**Symptôme :** Impossible d'écrire dans la base de données

**Solution :**

- Fermer les autres instances QGIS utilisant le même fichier
- Vérifier les fichiers de verrouillage orphelins (`.sqlite-shm`, `.sqlite-wal`)
- Passer en mode WAL pour une meilleure concurrence :
  ```sql
  PRAGMA journal_mode = WAL;
  ```

### Problème : « Mémoire insuffisante »

**Symptôme :** La requête échoue sur un grand jeu de données

**Solution :**

- **Réduire la taille du cache** (aide paradoxalement parfois) :
  ```sql
  PRAGMA cache_size = 10000;  -- 10MB
  ```

- **Passer à PostgreSQL** pour les jeux de données > 100k entités

- **Filtrer par étapes** — découper les grosses opérations

## Benchmarks de performance

Performance réelle sur du matériel typique (Core i7, 16GB RAM, SSD) :

| Taille du jeu | Entités | Spatialite | PostgreSQL | Ratio |
|---------------|---------|-----------|-----------|-------|
| Petit | 5 000 | 0.4s | 0.3s | 1.3x plus lent |
| Moyen | 50 000 | 8.5s | 1.2s | 7x plus lent |
| Grand | 500 000 | 65s | 8.4s | 8x plus lent |
| Très grand | 5 000 000 | Timeout | 45s | Non viable |

**Opérations spatiales (50k entités) :**

| Opération | Temps | vs PostgreSQL |
|-----------|-------|---------------|
| Intersects | 8.2s | 6x plus lent |
| Contains | 9.1s | 5x plus lent |
| Buffer (10m) + Intersects | 12.5s | 5x plus lent |
| Expression complexe | 18.3s | 6x plus lent |

## Bonnes pratiques

### ✅ À faire

- **Utiliser Spatialite pour < 50k entités** — excellente performance
- **Créer des index spatiaux** — énorme boost de performance
- **Utiliser le mode journal WAL** — meilleure concurrence
- **Exécuter VACUUM périodiquement** — maintient les performances
- **Sauvegarder avant les opérations en masse** — facile avec un fichier unique

### ❌ À éviter

- **Ne pas utiliser pour > 500k entités** — trop lent
- **Ne pas oublier les index spatiaux** — pénalité de performance 10-100x
- **Ne pas ouvrir le même fichier dans plusieurs processus** — verrouillage de base de données
- **Ne pas désactiver les index R-tree** — les requêtes spatiales seront lentes

## Migrer vers PostgreSQL

Si votre base de données Spatialite devient trop grande :

### Option 1 : QGIS DB Manager

1. **Ouvrir DB Manager** (Base de données → DB Manager)
2. **Sélectionner la base de données Spatialite**
3. **Clic droit sur la couche → Exporter vers PostgreSQL**
4. **Configurer la connexion et importer**

### Option 2 : Ligne de commande (ogr2ogr)

```bash
ogr2ogr -f PostgreSQL \
  PG:"host=localhost dbname=mabase user=monutilisateur password=monmotdepasse" \
  mes_donnees.sqlite \
  -lco GEOMETRY_NAME=geometry \
  -lco SPATIAL_INDEX=GIST
```

### Option 3 : Script Python

```python
from qgis.core import QgsVectorLayer, QgsDataSourceUri

# Charger la couche Spatialite
sqlite_layer = QgsVectorLayer(
    "/chemin/vers/donnees.sqlite|layername=ma_couche",
    "sqlite_layer",
    "ogr"
)

# Exporter vers PostgreSQL
uri = QgsDataSourceUri()
uri.setConnection("localhost", "5432", "mabase", "utilisateur", "motdepasse")
uri.setDataSource("public", "ma_couche", "geometry")

# Utiliser le traitement QGIS ou l'export DB Manager
```

## Voir aussi

- [Vue d'ensemble des backends](./overview.md) — Architecture multi-backend
- [Sélection du backend](./choosing-backend.md) — Logique de sélection automatique
- [Backend PostgreSQL](./postgresql.md) — Pour les plus grands jeux de données
- [Comparaison des performances](./performance-benchmarks.md) — Benchmarks détaillés
- [Dépannage](../advanced/troubleshooting.md) — Problèmes courants

## Détails techniques

### Structure de la base de données

FilterMate crée des tables temporaires avec cette structure :

```sql
-- Table filtrée temporaire
CREATE TEMP TABLE filtermate_filtered_123 (
    fid INTEGER PRIMARY KEY,
    geometry BLOB,
    -- Colonnes d'attributs originales
    ...
);

-- Enregistrer la colonne géométrique
SELECT RecoverGeometryColumn(
    'filtermate_filtered_123',
    'geometry',
    4326,  -- SRID
    'POLYGON',
    'XY'
);

-- Créer l'index spatial
SELECT CreateSpatialIndex('filtermate_filtered_123', 'geometry');
```

### Fonctions supportées

Expressions QGIS traduites en SQL Spatialite :

| Expression QGIS | Fonction Spatialite |
|-----------------|---------------------|
| `intersects()` | `ST_Intersects()` |
| `contains()` | `ST_Contains()` |
| `within()` | `ST_Within()` |
| `buffer()` | `ST_Buffer()` |
| `distance()` | `ST_Distance()` |
| `area()` | `ST_Area()` |
| `length()` | `ST_Length()` |

### Nettoyage

FilterMate nettoie automatiquement les tables temporaires :

```sql
-- À la fermeture du plugin ou effacement du filtre
DROP TABLE IF EXISTS filtermate_filtered_123;

-- Récupérer l'espace
VACUUM;
```

---

**Dernière mise à jour :** 14 décembre 2025  
**Version du plugin :** 2.3.0  
**Support Spatialite :** SQLite 3.7+ avec Spatialite 4.3+
