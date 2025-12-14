---
sidebar_position: 4
---

# Backend OGR

Le backend OGR offre une **compatibilité universelle** avec tous les formats vectoriels supportés par QGIS via la bibliothèque GDAL/OGR. Il sert de repli fiable lorsque les backends PostgreSQL ou Spatialite ne sont pas disponibles.

:::tip Compatibilité universelle
Le backend OGR fonctionne avec **tous les formats vectoriels** : Shapefiles, GeoPackage, GeoJSON, KML, DXF, CSV et plus de 80 autres formats.
:::

## Vue d'ensemble

Le backend OGR de FilterMate utilise le framework de traitement de QGIS et les couches en mémoire pour effectuer le filtrage géométrique. Bien qu'il ne soit pas aussi rapide que les backends de base de données pour les grands jeux de données, il offre une excellente compatibilité et ne nécessite aucune configuration supplémentaire.

### Avantages clés

- ✅ **Support universel des formats** — fonctionne avec tout format lisible par OGR
- 🔧 **Aucune configuration requise** — intégré à QGIS
- 📦 **Portable** — fonctionne avec les fichiers locaux et distants
- 🌐 **Formats web** — GeoJSON, KML, etc.
- 💾 **Couches en mémoire** — traitement temporaire en mémoire
- 🚀 **Automatique** — repli quand les autres backends ne sont pas disponibles

## Quand le backend OGR est utilisé

FilterMate sélectionne automatiquement le backend OGR quand :

1. ✅ La source de la couche n'est **pas** PostgreSQL ou Spatialite
2. ✅ Le fournisseur de la couche est `ogr` (Shapefile, GeoPackage, etc.)
3. ✅ Repli quand psycopg2 n'est pas disponible pour les couches PostgreSQL

**Formats courants utilisant le backend OGR :**
- Shapefile (`.shp`)
- GeoPackage (`.gpkg`)
- GeoJSON (`.geojson`, `.json`)
- KML/KMZ (`.kml`, `.kmz`)
- DXF/DWG (formats CAO)
- CSV avec géométrie (`.csv`)
- GPS Exchange (`.gpx`)
- Et plus de 80 autres formats

## Installation

### Prérequis

- **QGIS 3.x** (inclut GDAL/OGR)
- **Aucun package supplémentaire nécessaire**

### Vérification

OGR est toujours disponible dans QGIS. Vérifiez les formats supportés :

```python
# Dans la Console Python QGIS
from osgeo import ogr

driver_count = ogr.GetDriverCount()
print(f"✓ {driver_count} pilotes OGR disponibles")

# Lister quelques pilotes courants
for driver_name in ['ESRI Shapefile', 'GPKG', 'GeoJSON', 'KML']:
    driver = ogr.GetDriverByName(driver_name)
    if driver:
        print(f"  ✓ {driver_name}")
```

## Fonctionnalités

### 1. Couches en mémoire

FilterMate crée des **couches en mémoire** pour les résultats filtrés :

```python
# Exemple de couche en mémoire créée par FilterMate
from qgis.core import QgsVectorLayer

memory_layer = QgsVectorLayer(
    f"Point?crs=epsg:4326&field=id:integer&field=name:string",
    "couche_filtree",
    "memory"
)

# Copier les entités filtrées
for feature in source_layer.getFeatures(expression):
    memory_layer.dataProvider().addFeature(feature)
```

**Avantages :**
- Création rapide
- Pas d'E/S disque
- Nettoyage automatique
- Fonctionne avec tous les formats

**Limitations :**
- Stocké en RAM — pas adapté aux très grands jeux de données
- Perdu à la fermeture de QGIS (sauf si sauvegardé)

### 2. Framework de traitement QGIS

Le backend OGR exploite les algorithmes de traitement QGIS :

```python
# FilterMate utilise le traitement QGIS pour les opérations complexes
import processing

result = processing.run("native:extractbyexpression", {
    'INPUT': layer,
    'EXPRESSION': 'ST_Intersects($geometry, geometry(@filter_layer))',
    'OUTPUT': 'memory:'
})

filtered_layer = result['OUTPUT']
```

**Opérations disponibles :**
- Extraction par expression
- Extraction par localisation
- Tampon
- Intersection
- Union
- Découpage
- Et plus de 300 autres algorithmes

### 3. Matrice de compatibilité des formats

| Format | Lecture | Écriture | Index spatial | Performance |
|--------|---------|----------|---------------|-------------|
| Shapefile | ✅ | ✅ | ⚠️ Fichiers .qix | Bonne |
| GeoPackage | ✅ | ✅ | ✅ R-tree | Excellente |
| GeoJSON | ✅ | ✅ | ❌ | Bonne |
| KML/KMZ | ✅ | ✅ | ❌ | Bonne |
| CSV | ✅ | ✅ | ❌ | Correcte |
| DXF/DWG | ✅ | ⚠️ Limité | ❌ | Correcte |
| GPX | ✅ | ✅ | ❌ | Bonne |
| GML | ✅ | ✅ | ❌ | Bonne |
| FlatGeobuf | ✅ | ✅ | ✅ Intégré | Excellente |

:::tip Meilleurs formats pour le backend OGR
Pour des performances optimales : **GeoPackage** ou **FlatGeobuf** (les deux ont des index spatiaux)
:::

### 4. Support des prédicats spatiaux

Le backend OGR supporte la plupart des prédicats spatiaux via les expressions QGIS :

| Prédicat | Support | Notes |
|----------|---------|-------|
| `intersects` | ✅ Complet | Via expression QGIS |
| `contains` | ✅ Complet | Via expression QGIS |
| `within` | ✅ Complet | Via expression QGIS |
| `touches` | ⚠️ Limité | Certains formats |
| `crosses` | ⚠️ Limité | Certains formats |
| `overlaps` | ⚠️ Limité | Certains formats |
| `disjoint` | ✅ Complet | Via expression QGIS |
| `buffer` | ✅ Complet | Traitement QGIS |

**Exemple :**

```python
# Expression QGIS pour intersects
expression = 'intersects($geometry, geometry(@filter_layer))'

# FilterMate applique à la couche OGR
layer.setSubsetString(expression)  # Si le format le supporte
# OU
filtered_features = [f for f in layer.getFeatures() if expression.evaluate(f)]
```

## Configuration

### Options spécifiques au format

Configurez le comportement du backend OGR dans `config/config.json` :

```json
{
  "OGR": {
    "use_memory_layers": true,
    "enable_spatial_index": true,
    "max_features_in_memory": 100000,
    "prefer_geopackage": true
  }
}
```

### Index spatiaux Shapefile

Pour les Shapefiles, créez l'index spatial `.qix` :

```python
# Dans la Console Python QGIS
layer = iface.activeLayer()
layer.dataProvider().createSpatialIndex()

# Ou via traitement
processing.run("native:createspatialindex", {
    'INPUT': layer
})
```

Cela crée `monfichier.qix` à côté de `monfichier.shp`.

### Optimisation GeoPackage

GeoPackage a des index R-tree intégrés :

```sql
-- Vérifier l'index spatial (dans GeoPackage)
SELECT * FROM sqlite_master
WHERE type = 'table' AND name LIKE 'rtree_%';

-- Reconstruire si nécessaire
DROP TABLE IF EXISTS rtree_ma_couche_geometry;
-- QGIS recréera automatiquement
```

## Utilisation

### Filtrage basique

1. **Charger n'importe quelle couche vectorielle** dans QGIS
2. **Ouvrir le plugin FilterMate**
3. **Configurer les options** de filtre
4. **Cliquer sur « Appliquer le filtre »**

FilterMate automatiquement :
- Détecte le backend OGR
- Crée une couche en mémoire
- Copie les entités filtrées
- Ajoute la couche à QGIS
- Affiche l'indicateur de backend : **[OGR]**

### Recommandations de format

**Meilleures performances :**
- GeoPackage (`.gpkg`) — a des index spatiaux
- FlatGeobuf (`.fgb`) — optimisé pour le streaming

**Bonnes performances :**
- Shapefile (`.shp`) — avec index `.qix`
- GeoJSON (`.geojson`) — pour les petits jeux de données

**Performances acceptables :**
- KML (`.kml`) — pour web/Google Earth
- CSV (`.csv`) — pour des données ponctuelles simples

**Performances plus lentes :**
- DXF/DWG — formats CAO complexes
- Services distants (WFS) — latence réseau

### Sauvegarder les résultats filtrés

Les couches en mémoire sont temporaires. Pour les conserver :

```python
# Dans QGIS, clic droit sur la couche filtrée → Exporter → Sauvegarder les entités sous
# Ou via code :
from qgis.core import QgsVectorFileWriter

QgsVectorFileWriter.writeAsVectorFormat(
    memory_layer,
    "/chemin/vers/sortie.gpkg",
    "UTF-8",
    layer.crs(),
    "GPKG"
)
```

## Optimisation des performances

### Pour les petits jeux de données (< 10k entités)

- **Aucune configuration spéciale nécessaire**
- Tous les formats fonctionnent bien
- Les couches en mémoire sont rapides

### Pour les jeux de données moyens (10k - 50k entités)

- **Utilisez GeoPackage ou Shapefile avec index .qix**
- **Activez les couches en mémoire** (par défaut)
- **Envisagez le backend Spatialite** à la place (5x plus rapide)

```json
{
  "OGR": {
    "use_memory_layers": true,
    "enable_spatial_index": true
  }
}
```

### Pour les grands jeux de données (50k - 500k entités)

:::warning Recommandation de performance
**Passez à PostgreSQL ou Spatialite** pour des performances 5-10x meilleures. Le backend OGR n'est pas optimal pour les grands jeux de données.
:::

Si vous devez utiliser OGR :
- **Utilisez GeoPackage** (meilleur format pour les grandes données)
- **Désactivez les couches en mémoire** (réduire l'usage RAM) :
  ```json
  {
    "OGR": {
      "use_memory_layers": false,
      "write_to_disk": true,
      "temp_directory": "/chemin/ssd/rapide"
    }
  }
  ```
- **Créez des index spatiaux**
- **Filtrez par étapes** si très lent

### Pour les très grands jeux de données (> 500k entités)

❌ **Backend OGR non recommandé**

**Alternatives :**
1. **Migrer vers PostgreSQL** — 10-100x plus rapide
2. **Utiliser Spatialite** — 5-10x plus rapide
3. **Tuiler/partitionner les données** — diviser en morceaux gérables

## Limitations

### Comparé aux backends de base de données

| Fonctionnalité | OGR | Spatialite | PostgreSQL |
|----------------|-----|-----------|-----------|
| Taille max pratique | ~50k entités | ~500k entités | 10M+ entités |
| Index spatiaux | ⚠️ Dépend du format | ✅ R-tree | ✅ GIST |
| Usage mémoire | ⚠️ Élevé | ✅ Faible | ✅ Très faible |
| Opérations côté serveur | ❌ Non | ❌ Non | ✅ Oui |
| Accès concurrent | ⚠️ Limité | ⚠️ Limité | ✅ Excellent |
| Optimisation requêtes | ❌ Basique | ✅ Bonne | ✅ Excellente |

### Limitations spécifiques aux formats

**Shapefile :**
- Limite de taille de fichier 2GB
- Limite de 254 caractères pour les noms de champs
- Pas de types de géométrie mixtes
- Précision date/heure limitée

**GeoJSON :**
- Pas de support d'index spatial
- Peut être très volumineux (format verbeux)
- Analyse plus lente sur les gros fichiers

**KML :**
- Support limité des attributs
- Pas de vraies opérations spatiales
- Mieux pour la visualisation que l'analyse

**CSV :**
- Géométrie stockée en WKT (analyse lente)
- Pas d'index spatial
- Non recommandé pour les grands jeux de données

## Dépannage

### Problème : « La couche n'a pas d'index spatial »

**Symptôme :** Requêtes lentes malgré un petit jeu de données

**Solution :**

Pour **Shapefile**, créer l'index .qix :
```python
layer.dataProvider().createSpatialIndex()
```

Pour **GeoPackage**, reconstruire le R-tree :
```python
# Ouvrir dans DB Manager et exécuter :
# DROP TABLE rtree_nom_couche_geometry;
# Puis recharger la couche
```

### Problème : « Mémoire insuffisante »

**Symptôme :** QGIS plante sur un grand jeu de données

**Solution :**

1. **Désactiver les couches en mémoire :**
   ```json
   {
     "OGR": {
       "use_memory_layers": false
     }
   }
   ```

2. **Passer au format GeoPackage** (plus efficace)

3. **Utiliser le backend PostgreSQL ou Spatialite** à la place

### Problème : « Filtrage très lent »

**Symptôme :** Prend des minutes pour un petit jeu de données

**Solution :**

1. **Vérifier l'index spatial :**
   ```python
   # Shapefile - vérifier le fichier .qix
   # GeoPackage - vérifier la table rtree
   ```

2. **Simplifier la géométrie** si complexe :
   ```python
   processing.run("native:simplifygeometries", {
       'INPUT': layer,
       'METHOD': 0,  # Distance
       'TOLERANCE': 1,  # mètres
       'OUTPUT': 'memory:'
   })
   ```

3. **Utiliser des prédicats plus simples** — `intersects` plus rapide que `touches`

### Problème : « Format non supporté »

**Symptôme :** Impossible d'ouvrir le fichier

**Solution :**

1. **Vérifier la version GDAL/OGR :**
   ```python
   from osgeo import gdal
   print(gdal.VersionInfo())
   ```

2. **Lister les pilotes disponibles :**
   ```python
   from osgeo import ogr
   for i in range(ogr.GetDriverCount()):
       print(ogr.GetDriver(i).GetName())
   ```

3. **Convertir vers un format supporté :**
   ```bash
   ogr2ogr -f GPKG sortie.gpkg entree.xyz
   ```

## Conversion de format

### Vers GeoPackage (Recommandé)

```bash
# Ligne de commande (ogr2ogr)
ogr2ogr -f GPKG sortie.gpkg entree.shp

# Python
import processing
processing.run("native:package", {
    'LAYERS': [layer],
    'OUTPUT': '/chemin/vers/sortie.gpkg'
})
```

### Vers Shapefile

```bash
ogr2ogr -f "ESRI Shapefile" sortie.shp entree.gpkg
```

### Vers GeoJSON

```bash
ogr2ogr -f GeoJSON sortie.geojson entree.shp
```

## Benchmarks de performance

Performance réelle sur du matériel typique (Core i7, 16GB RAM, SSD) :

| Taille du jeu | Entités | OGR (Shapefile) | OGR (GeoPackage) | Spatialite | PostgreSQL |
|---------------|---------|----------------|-----------------|-----------|-----------|
| Petit | 5 000 | 0.8s | 0.6s | 0.4s | 0.3s |
| Moyen | 50 000 | 25s | 15s | 8.5s | 1.2s |
| Grand | 500 000 | Timeout | 180s | 65s | 8.4s |

**Comparaison des formats (50k entités) :**

| Format | Temps de chargement | Temps de filtre | Total | Index spatial |
|--------|---------------------|-----------------|-------|---------------|
| GeoPackage | 2.3s | 12.7s | 15.0s | ✅ Oui |
| Shapefile + .qix | 3.1s | 21.9s | 25.0s | ✅ Oui |
| Shapefile (sans index) | 3.1s | 87.2s | 90.3s | ❌ Non |
| GeoJSON | 4.8s | 45.3s | 50.1s | ❌ Non |
| KML | 6.2s | 52.7s | 58.9s | ❌ Non |

## Bonnes pratiques

### ✅ À faire

- **Utiliser GeoPackage pour les meilleures performances OGR**
- **Créer des index spatiaux** (.qix pour Shapefile)
- **Garder les jeux de données < 50k entités** pour le backend OGR
- **Utiliser pour la compatibilité universelle des formats**
- **Tester la conversion de format** si les performances sont mauvaises

### ❌ À éviter

- **Ne pas utiliser OGR pour > 100k entités** — trop lent
- **Ne pas oublier les index spatiaux** — impact énorme sur les performances
- **Ne pas utiliser CSV/GeoJSON pour les grandes données** — pas d'index spatial
- **Ne pas se fier à Shapefile pour la production** — envisagez GeoPackage
- **Ne pas utiliser les couches en mémoire pour les énormes jeux de données** — va planter

## Migrer vers de meilleurs backends

### Quand passer à Spatialite

**Indicateurs :**
- Jeu de données > 10k entités
- Besoin de meilleures performances de requête
- Veut des résultats persistants

**Migration :**
```python
# Exporter vers Spatialite
from qgis.core import QgsVectorFileWriter

options = QgsVectorFileWriter.SaveVectorOptions()
options.driverName = "SQLite"
options.datasourceOptions = ["SPATIALITE=YES"]

QgsVectorFileWriter.writeAsVectorFormatV3(
    layer,
    "/chemin/vers/sortie.sqlite",
    QgsCoordinateTransformContext(),
    options
)
```

### Quand passer à PostgreSQL

**Indicateurs :**
- Jeu de données > 50k entités
- Besoin d'accès concurrent
- Veut des opérations côté serveur
- Besoin des meilleures performances

**Migration :**
```bash
# Avec ogr2ogr
ogr2ogr -f PostgreSQL \
  PG:"host=localhost dbname=mabase user=monutilisateur" \
  entree.gpkg \
  -lco GEOMETRY_NAME=geometry \
  -lco SPATIAL_INDEX=GIST
```

## Voir aussi

- [Vue d'ensemble des backends](./overview.md) — Architecture multi-backend
- [Sélection du backend](./choosing-backend.md) — Logique de sélection automatique
- [Backend PostgreSQL](./postgresql.md) — Pour les meilleures performances
- [Backend Spatialite](./spatialite.md) — Pour les jeux de données moyens
- [Comparaison des performances](./performance-benchmarks.md) — Benchmarks détaillés

## Détails techniques

### Création de couche en mémoire

```python
# FilterMate crée les couches en mémoire comme ceci
from qgis.core import QgsVectorLayer, QgsFeature

# Créer une couche en mémoire avec la même structure
uri = f"{geom_type}?crs={crs_string}"
for field in source_layer.fields():
    uri += f"&field={field.name()}:{field.typeName()}"

memory_layer = QgsVectorLayer(uri, "filtree", "memory")

# Copier les entités filtrées
features = []
for feature in source_layer.getFeatures(expression):
    features.append(QgsFeature(feature))

memory_layer.dataProvider().addFeatures(features)
```

### Pilotes OGR supportés

Pilotes courants dans QGIS 3.x :

- `ESRI Shapefile` — fichiers .shp
- `GPKG` — GeoPackage
- `GeoJSON` — .geojson, .json
- `KML` — .kml, .kmz
- `CSV` — .csv avec géométrie
- `GPX` — GPS Exchange
- `DXF` — AutoCAD DXF
- `GML` — Geography Markup Language
- `Memory` — Couches en mémoire
- `FlatGeobuf` — .fgb (format streaming)

Vérifiez tous les disponibles :
```python
from osgeo import ogr
for i in range(ogr.GetDriverCount()):
    driver = ogr.GetDriver(i)
    print(f"{driver.GetName()}: {driver.GetMetadata().get('DMD_LONGNAME', '')}")
```

---

**Dernière mise à jour :** 14 décembre 2025  
**Version du plugin :** 2.3.0  
**Support OGR/GDAL :** Version incluse avec QGIS 3.x
