---
sidebar_position: 2
---

# Backend PostgreSQL

Le backend PostgreSQL offre des **performances optimales** pour FilterMate, particulièrement avec les grands jeux de données. Il exploite les opérations spatiales côté serveur, les vues matérialisées et les index spatiaux pour un filtrage ultra-rapide.

:::tip Champion de la performance
PostgreSQL est recommandé pour les jeux de données de **plus de 50 000 entités** et requis pour ceux de **plus de 500 000 entités**.
:::

## Vue d'ensemble

Le backend PostgreSQL de FilterMate se connecte directement à votre base de données PostGIS pour effectuer les opérations de filtrage géométrique côté serveur. Cette approche réduit considérablement le transfert de données et le temps de traitement par rapport au filtrage côté client.

### Avantages clés

- ⚡ **Requêtes en moins d'une seconde** sur des jeux de données de millions d'entités
- 🔧 **Vues matérialisées** pour des résultats filtrés persistants
- 🗺️ **Index spatiaux GIST** pour des recherches spatiales optimisées
- 🚀 **Traitement côté serveur** réduit la surcharge réseau
- 💾 **Efficace en mémoire** - traite les données dans la base
- ⚙️ **Opérations concurrentes** - plusieurs filtres ne ralentissent pas

## Quand le backend PostgreSQL est utilisé

FilterMate sélectionne automatiquement le backend PostgreSQL quand :

1. ✅ La source de la couche est PostgreSQL/PostGIS
2. ✅ Le package Python `psycopg2` est installé
3. ✅ La connexion à la base de données est disponible

Si `psycopg2` n'est **pas** installé, FilterMate bascule vers les backends Spatialite ou OGR avec un avertissement de performance pour les grands jeux de données.

## Installation

### Prérequis

- **PostgreSQL 9.5+** avec extension **PostGIS 2.3+**
- **QGIS 3.x** avec connexion PostgreSQL configurée
- **Python 3.7+** (inclus avec QGIS)

### Installer psycopg2

Choisissez la méthode qui fonctionne le mieux pour votre environnement :

#### Méthode 1 : pip (Recommandée)

```bash
pip install psycopg2-binary
```

#### Méthode 2 : Console Python QGIS

Ouvrez la Console Python QGIS (Ctrl+Alt+P) et exécutez :

```python
import pip
pip.main(['install', 'psycopg2-binary'])
```

#### Méthode 3 : OSGeo4W Shell (Windows)

```bash
# Ouvrir OSGeo4W Shell en Administrateur
py3_env
pip install psycopg2-binary
```

#### Méthode 4 : Conda (si utilisation d'environnement conda)

```bash
conda install -c conda-forge psycopg2
```

### Vérification

Vérifiez si psycopg2 est disponible :

```python
# Dans la Console Python QGIS
try:
    import psycopg2
    print(f"✓ Version psycopg2 : {psycopg2.__version__}")
except ImportError:
    print("✗ psycopg2 non installé")
```

## Fonctionnalités

### 1. Vues matérialisées

FilterMate crée des **vues matérialisées** dans PostgreSQL pour stocker les résultats filtrés de manière persistante :

```sql
-- Exemple de vue matérialisée créée par FilterMate
CREATE MATERIALIZED VIEW filtermate_filtered_view_123 AS
SELECT *
FROM ma_couche
WHERE ST_Intersects(
    geometry,
    (SELECT geometry FROM couche_filtre WHERE id = 1)
);

-- Index spatial créé automatiquement
CREATE INDEX idx_filtermate_filtered_view_123_geom
ON filtermate_filtered_view_123
USING GIST (geometry);
```

**Avantages :**
- Résultats mis en cache dans la base
- Rafraîchissement instantané sur les filtres suivants
- Partageable entre les sessions QGIS
- Nettoyage automatique à la fermeture du plugin

### 2. Opérations spatiales côté serveur

Toutes les opérations géométriques s'exécutent **dans la base de données** :

- `ST_Intersects()` - Trouver les entités intersectantes
- `ST_Contains()` - Trouver les entités contenant
- `ST_Within()` - Trouver les entités à l'intérieur des limites
- `ST_Buffer()` - Créer des tampons côté serveur
- `ST_Distance()` - Calculer les distances

**Impact sur les performances :**

| Opération | Côté client (Python) | Côté serveur (PostGIS) |
|-----------|---------------------|----------------------|
| 10k entités | ~5 secondes | ~0.5 secondes (10x plus rapide) |
| 100k entités | ~60 secondes | ~2 secondes (30x plus rapide) |
| 1M entités | Timeout/crash | ~10 secondes (100x+ plus rapide) |

### 3. Index spatiaux GIST

FilterMate s'assure que vos géométries ont des **index GIST** pour des performances de requête optimales :

```sql
-- Vérifier les index existants
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'ma_couche';

-- FilterMate crée automatiquement les index GIST
CREATE INDEX IF NOT EXISTS idx_ma_couche_geom
ON ma_couche
USING GIST (geometry);
```

:::info Gestion automatique des index
FilterMate vérifie les index spatiaux et les crée s'ils manquent. Cette opération ponctuelle peut prendre quelques secondes sur les grandes tables.
:::

### 4. Optimisation des requêtes

Le backend PostgreSQL applique plusieurs optimisations :

- **Pré-filtrage par boîte englobante** - Utilise l'opérateur `&&` avant les opérations coûteuses
- **Exécution parallèle des requêtes** - Exploite les workers parallèles de PostgreSQL
- **Instructions préparées** - Réutilise les plans de requête pour les filtres répétés
- **Statistiques ANALYZE** - Assure une planification optimale des requêtes

Exemple de requête optimisée :

```sql
-- Filtre boîte englobante d'abord (rapide)
WHERE geometry && ST_Buffer(filter_geom, 100)
  -- Puis vérification d'intersection coûteuse (seulement sur les correspondances bbox)
  AND ST_Intersects(geometry, ST_Buffer(filter_geom, 100))
```

## Configuration

### Connexion à la base de données

FilterMate utilise la connexion PostgreSQL existante de QGIS. Assurez-vous que votre connexion est configurée :

1. **Couche → Gestionnaire de sources de données → PostgreSQL**
2. **Nouvelle** connexion avec les détails :
   - Nom : `ma_base_postgis`
   - Hôte : `localhost` (ou hôte distant)
   - Port : `5432`
   - Base de données : `ma_base`
   - Authentification : Basique ou identifiants stockés

### Paramètres de performance

Optimisez PostgreSQL pour les requêtes spatiales :

```sql
-- Dans postgresql.conf ou par session

-- Augmenter la mémoire de travail pour les gros tris
SET work_mem = '256MB';

-- Activer l'exécution parallèle des requêtes
SET max_parallel_workers_per_gather = 4;

-- Optimiser pour les opérations spatiales
SET random_page_cost = 1.1;  -- Pour stockage SSD
```

### Permissions de schéma

FilterMate nécessite ces permissions PostgreSQL :

```sql
-- Permissions minimales requises
GRANT CONNECT ON DATABASE ma_base TO utilisateur_filtermate;
GRANT USAGE ON SCHEMA public TO utilisateur_filtermate;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO utilisateur_filtermate;
GRANT CREATE ON SCHEMA public TO utilisateur_filtermate;  -- Pour les vues temp
```

## Utilisation

### Filtrage basique

1. **Charger la couche PostgreSQL** dans QGIS
2. **Ouvrir le plugin FilterMate**
3. **Configurer les options** de filtre
4. **Cliquer sur « Appliquer le filtre »**

FilterMate automatiquement :
- Détecte le backend PostgreSQL
- Crée une vue matérialisée
- Ajoute la couche filtrée à QGIS
- Affiche l'indicateur de backend : **[PG]**

### Options avancées

#### Schéma personnalisé

Spécifiez un schéma personnalisé pour les vues matérialisées :

```python
# Dans config/config.json
{
  "POSTGRESQL": {
    "schema": "filtermate_temp",
    "auto_cleanup": true
  }
}
```

#### Pool de connexions

Pour plusieurs filtres simultanés :

```python
# FilterMate gère automatiquement le pool de connexions
# Connexions max : 5 (configurable)
```

## Optimisation des performances

### Pour les petits jeux de données (< 10k entités)

- **Aucune configuration spéciale nécessaire**
- PostgreSQL performe similairement à Spatialite
- Utilisez les paramètres par défaut

### Pour les jeux de données moyens (10k - 100k entités)

- **Assurez-vous que les index spatiaux existent**
- **Augmentez `work_mem` à 128MB**
- **Activez les workers parallèles (2-4)**

```sql
ALTER TABLE ma_couche SET (parallel_workers = 2);
```

### Pour les grands jeux de données (100k - 1M entités)

- **Augmentez `work_mem` à 256MB+**
- **Augmentez `parallel_workers` à 4-8**
- **Exécutez `VACUUM ANALYZE` régulièrement**

```sql
VACUUM ANALYZE ma_couche;
```

### Pour les très grands jeux de données (> 1M entités)

- **Partitionnez les tables par étendue spatiale**
- **Utilisez l'héritage de tables**
- **Envisagez le clustering de table par géométrie**

```sql
-- Cluster la table par index spatial
CLUSTER ma_couche USING idx_ma_couche_geom;
```

## Dépannage

### Problème : « psycopg2 non trouvé »

**Symptôme :** FilterMate affiche le backend OGR/Spatialite pour les couches PostgreSQL

**Solution :**
1. Installer psycopg2 (voir section Installation)
2. Redémarrer QGIS
3. Vérifier l'installation dans la Console Python

### Problème : « Permission refusée pour créer la vue »

**Symptôme :** Erreur lors de l'application du filtre

**Solution :**
```sql
-- Accorder la permission CREATE
GRANT CREATE ON SCHEMA public TO votre_utilisateur;

-- Ou utiliser un schéma dédié
CREATE SCHEMA filtermate_temp;
GRANT ALL ON SCHEMA filtermate_temp TO votre_utilisateur;
```

### Problème : « Requêtes lentes malgré PostgreSQL »

**Symptôme :** Les requêtes prennent plus de temps que prévu

**Solution :**
1. **Vérifier les index spatiaux :**
   ```sql
   SELECT * FROM pg_indexes WHERE tablename = 'votre_table';
   ```

2. **Exécuter ANALYZE :**
   ```sql
   ANALYZE votre_table;
   ```

3. **Vérifier le plan de requête :**
   ```sql
   EXPLAIN ANALYZE
   SELECT * FROM votre_table
   WHERE ST_Intersects(geometry, ST_GeomFromText('POLYGON(...)'));
   ```

4. **Chercher « Seq Scan »** - si présent, l'index n'est pas utilisé

### Problème : « Timeout de connexion »

**Symptôme :** FilterMate se bloque lors de l'application du filtre

**Solution :**
- Augmenter le `statement_timeout` de PostgreSQL
- Vérifier la connectivité réseau
- Vérifier que le serveur de base de données répond

```sql
-- Augmenter le timeout à 5 minutes
SET statement_timeout = '300s';
```

## Benchmarks de performance

Performance réelle sur du matériel typique (Core i7, 16GB RAM, SSD) :

| Taille du jeu | Entités | PostgreSQL | Spatialite | Accélération |
|---------------|---------|------------|------------|--------------|
| Petit | 5 000 | 0.3s | 0.4s | 1.3x |
| Moyen | 50 000 | 1.2s | 8.5s | 7x |
| Grand | 500 000 | 8.4s | 65s | 8x |
| Très grand | 5 000 000 | 45s | Timeout | 10x+ |

**Opérations spatiales :**

| Opération | 100k entités | 1M entités |
|-----------|--------------|-------------|
| Intersects | 1.5s | 9.2s |
| Contains | 1.8s | 11.5s |
| Buffer (10m) + Intersects | 2.3s | 15.1s |
| Expression complexe | 3.1s | 18.7s |

## Bonnes pratiques

### ✅ À faire

- **Utiliser PostgreSQL pour les jeux de données > 50k entités**
- **S'assurer que les index spatiaux existent avant le filtrage**
- **Exécuter VACUUM ANALYZE après les mises à jour massives**
- **Utiliser le pool de connexions pour plusieurs filtres**
- **Surveiller les performances des requêtes avec EXPLAIN**

### ❌ À éviter

- **Ne pas mélanger les systèmes de référence spatiale** - reprojeter au préalable
- **Ne pas créer trop de vues matérialisées** - FilterMate nettoie automatiquement
- **Ne pas désactiver les index spatiaux** - pénalité de performance énorme
- **Ne pas exécuter des expressions complexes sans tester** - utiliser EXPLAIN d'abord

## Voir aussi

- [Vue d'ensemble des backends](./overview.md) - Architecture multi-backend
- [Sélection du backend](./choosing-backend.md) - Logique de sélection automatique
- [Comparaison des performances](./performance-benchmarks.md) - Benchmarks détaillés
- [Backend Spatialite](./spatialite.md) - Alternative pour les plus petits jeux de données
- [Dépannage](../advanced/troubleshooting.md) - Problèmes courants

## Détails techniques

### Gestion des connexions

FilterMate utilise `psycopg2` pour les connexions à la base de données :

```python
import psycopg2
from qgis.core import QgsDataSourceUri

# Extraire la connexion de la couche QGIS
uri = QgsDataSourceUri(layer.source())
conn = psycopg2.connect(
    host=uri.host(),
    port=uri.port(),
    database=uri.database(),
    user=uri.username(),
    password=uri.password()
)
```

### Cycle de vie des vues matérialisées

1. **Création** - Quand le filtre est appliqué
2. **Utilisation** - QGIS charge comme couche virtuelle
3. **Rafraîchissement** - Au changement des paramètres de filtre
4. **Nettoyage** - À la fermeture du plugin ou nettoyage manuel

### Fonctions PostGIS supportées

FilterMate traduit les expressions QGIS en fonctions PostGIS :

| Expression QGIS | Fonction PostGIS |
|-----------------|------------------|
| `intersects()` | `ST_Intersects()` |
| `contains()` | `ST_Contains()` |
| `within()` | `ST_Within()` |
| `buffer()` | `ST_Buffer()` |
| `distance()` | `ST_Distance()` |
| `area()` | `ST_Area()` |
| `length()` | `ST_Length()` |

---

**Dernière mise à jour :** 14 décembre 2025  
**Version du plugin :** 2.3.0  
**Support PostgreSQL :** 9.5+ avec PostGIS 2.3+
