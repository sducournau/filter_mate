---
sidebar_position: 6
---

# Exporter des entités

Exportez des couches (filtrées ou non) vers différents formats en utilisant l'onglet **EXPORTING**.

## Vue d'ensemble

L'onglet **EXPORTING** vous permet d'exporter des couches de votre projet QGIS vers des jeux de données autonomes pour :
- **Partager** avec des collègues ou clients
- **Analyser** dans d'autres logiciels
- **Archiver** des instantanés de données
- **Publier** des cartes web
- **Rapporter** des données tabulaires

**Fonctionnalités clés** :
- Multi-sélection de couches à exporter
- Formats de sortie multiples (GPKG, Shapefile, GeoJSON, etc.)
- Transformation SCR (re-projection)
- Export de style (QML, SLD, ArcGIS)
- Mode batch (fichiers séparés par couche)
- Compression ZIP pour la livraison

:::tip Export de données filtrées
Les couches peuvent être exportées **avec ou sans** filtres appliqués. Si vous avez utilisé l'onglet FILTERING pour créer des sous-ensembles filtrés, ces filtres sont préservés lors de l'export. Pour exporter des données non filtrées, supprimez d'abord les filtres dans l'onglet FILTERING.
:::

## Composants de l'onglet EXPORTING

### Sélection de couches

Sélectionnez les couches à exporter depuis votre projet QGIS :

<img src="/filter_mate/img/ui-exporting-layer-selector.png" alt="ui-exporting-layer-selector" width="300"/>

*Cochez une ou plusieurs couches à exporter*

**Fonctionnalités** :
- **Multi-sélection** : Exportez plusieurs couches à la fois
- **Indicateurs de géométrie** : Icônes visuelles pour les couches point/ligne/polygone
- **Nombre d'entités** : Affiche le nombre actuel d'entités (respecte les filtres actifs)
- **Info backend** : Affiche la source de données (PostgreSQL⚡, Spatialite, OGR)

### Sélection du format

Choisissez le format de sortie pour les données exportées :

<img src="/filter_mate/img/ui-exporting-format-selector.png" alt="ui-exporting-format-selector" width="300"/>

*Menu déroulant avec les formats d'export disponibles*


### Formats supportés

| Format | Type | Optimal pour | Taille max | Extension |
|--------|------|--------------|------------|-----------|
| **GeoPackage** | Vecteur | Usage général, grands jeux de données | Illimité | `.gpkg` |
| **Shapefile** | Vecteur | Compatibilité legacy | 2 Go | `.shp` |
| **GeoJSON** | Vecteur | Cartographie web, APIs | ~500 Mo | `.geojson` |
| **KML/KMZ** | Vecteur | Google Earth, mobile | ~100 Mo | `.kml`, `.kmz` |
| **CSV** | Tabulaire | Tableurs, coordonnées uniquement | Illimité | `.csv` |
| **PostGIS** | Base de données | Grands jeux de données, entreprise | Illimité | `(database)` |
| **Spatialite** | Base de données | Jeux de données moyens, portable | ~140 To | `.sqlite` |

### Transformation SCR

Re-projetez les couches lors de l'export vers un système de coordonnées différent :

<img src="/filter_mate/img/ui-exporting-crs-selector.png" alt="ui-exporting-crs-selector" width="300"/>

*QgsProjectionSelectionWidget pour la sélection du SCR*


**Fonctionnalités** :
- Choisissez n'importe quel code EPSG ou SCR personnalisé
- Présélections SCR courantes (WGS84, Web Mercator, projections locales)
- Re-projection à la volée lors de l'export
- Préserve la couche originale (pas de modification)

**Transformations SCR courantes** :
```
Original → SCR Export  | Cas d'usage
-----------------------|------------------------------------
EPSG:4326 → EPSG:3857 | Cartographie web (Leaflet, OpenLayers)
Local → EPSG:4326      | Compatibilité GPS
EPSG:4326 → zone UTM  | Mesures de distance précises
Divers → SCR unique   | Harmoniser les données multi-sources
```

### Export de style

Exportez le style de couche avec les données :

<!-- <!-- ![Style Selector](/img/ui-components/ui-exporting-style-selector.png --> -->
*Choisissez le format de style : QML (QGIS), SLD (Standard), ou ArcGIS*

**Formats disponibles** :
- **QML** (Style QGIS) - Style QGIS complet, préserve toutes les fonctionnalités
- **SLD** (Styled Layer Descriptor) - Standard OGC, fonctionne dans GeoServer, MapServer
- **ArcGIS** - Style compatible ArcGIS pour les logiciels Esri

**Comportement d'export de style** :
```
Format     | Inclut                      | Compatible avec
-----------|-----------------------------|--------------------------
QML        | Arbre de style QGIS complet | QGIS uniquement
SLD        | Symbologie + étiquettes     | GeoServer, MapServer, QGIS
ArcGIS     | Symbologie Esri             | ArcGIS Desktop, ArcGIS Pro
```

### Options de sortie

Configurez la destination et le mode de livraison :

<img src="/filter_mate/img/ui-exporting-output-folder.png" alt="ui-exporting-output-folder" width="300"/>

*QgsFileWidget pour la sélection de dossier*

<img src="/filter_mate/img/ui-exporting-output-zip.png" alt="ui-exporting-output-zip" width="300"/>

*Cases à cocher pour le mode Batch et la compression ZIP*

**Options** :
- **Dossier de sortie** : Choisissez le répertoire de destination
- **Mode Batch** : Exportez chaque couche dans un fichier séparé (vs un seul fichier pour toutes)
- **Compression ZIP** : Compressez automatiquement la sortie pour la livraison

**Comparaison du mode Batch** :
```
Mode Normal :
dossier_sortie/
  └── export.gpkg (contient toutes les couches)

Mode Batch :
dossier_sortie/
  ├── couche1.gpkg
  ├── couche2.gpkg
  └── couche3.gpkg

Batch + ZIP :
dossier_sortie/
  └── export_2024-12-09.zip
      ├── couche1.gpkg
      ├── couche2.gpkg
      └── couche3.gpkg
```

## Flux d'export

Processus d'export complet depuis l'onglet EXPORTING :

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant E as Onglet EXPORTING
    participant FM as FilterMate
    participant Q as QGIS
    participant DB as Backend
    participant F as Système de fichiers
    
    U->>E: 1. Basculer vers l'onglet EXPORTING
    U->>E: 2. Sélectionner les couches à exporter (multi-sélection)
    E->>U: Afficher indicateur "Has Layers to Export"
    
    U->>E: 3. Choisir le format (GPKG/SHP/GeoJSON/etc.)
    E->>U: Afficher indicateur "Has Datatype"
    
    U->>E: 4. Optionnel : Sélectionner la transformation SCR
    E->>U: Afficher indicateur "Has Projection" (si sélectionné)
    
    U->>E: 5. Optionnel : Choisir l'export de style (QML/SLD/ArcGIS)
    E->>U: Afficher indicateur "Has Styles" (si sélectionné)
    
    U->>E: 6. Sélectionner le dossier de sortie
    E->>U: Afficher indicateur "Has Output Folder"
    
    U->>E: 7. Optionnel : Activer mode batch + ZIP
    E->>U: Afficher indicateur "Has ZIP" (si activé)
    
    U->>FM: 8. Cliquer sur le bouton EXPORT
    FM->>Q: Préparer les paramètres d'export
    
    loop Pour chaque couche sélectionnée
        Q->>DB: Interroger les entités (avec filtres si appliqués)
        DB->>Q: Retourner les données d'entités
        
        alt Transformation SCR nécessaire
            Q->>Q: Re-projeter les géométries
        end
        
        Q->>F: Écrire au format de sortie
        
        alt Export de style activé
            Q->>F: Écrire le fichier de style (.qml/.sld/etc.)
        end
    end
    
    alt Compression ZIP activée
        F->>F: Compresser toutes les sorties en ZIP
    end
    
    F->>FM: Export terminé
    FM->>U: Afficher message de succès avec chemin(s) de fichier
```

### Exemple étape par étape : Export après filtrage

**Scénario** : Exporter les bâtiments dans un rayon de 200m des routes (depuis l'onglet FILTERING) vers GeoPackage

<!-- <!-- ![Step 1 - Filter Applied](/img/workflows/workflow-filtering-11.png --> -->
*1. Onglet FILTERING : Filtre appliqué, 3 847 bâtiments trouvés*

<!-- <!-- ![Step 2 - Switch to EXPORTING](/img/workflows/workflow-exporting-01.png --> -->
*2. Basculer vers l'onglet EXPORTING*

<!-- <!-- ![Step 3 - Select Layers](/img/workflows/workflow-exporting-02.png --> -->
*3. Sélectionner la couche "buildings" à exporter (le sous-ensemble filtré sera exporté)*

<!-- <!-- ![Step 4 - Configure Export](/img/workflows/workflow-exporting-02.png --> -->
*4. Configurer : Format=GPKG, SCR=EPSG:3857 (Web Mercator), Styles=QML*

Tous les indicateurs actifs :
- Has Layers to Export ✓
- Has Datatype (GPKG) ✓
- Has Projection (EPSG:3857) ✓
- Has Styles (QML) ✓

<!-- <!-- ![Step 5 - Output Folder](/img/workflows/workflow-exporting-03.png --> -->
*5. Sélectionner le dossier de sortie + nom de fichier*

<!-- <!-- ![Step 6 - Export](/img/workflows/workflow-exporting-03.png --> -->
*6. Cliquer sur le bouton EXPORT → La barre de progression affiche le traitement*

<!-- <!-- ![Step 7 - Success](/img/workflows/workflow-exporting-04.png --> -->
*7. Notification de succès avec le chemin de sortie : `C:/exports/buildings_filtered.gpkg` (3 847 entités, 2,3 Mo)*

**Résultat** :
- Fichier créé : `buildings_filtered.gpkg`
- Fichier de style : `buildings_filtered.qml` (dans le même dossier)
- SCR : EPSG:3857 (re-projeté depuis l'original EPSG:4326)
- Entités : 3 847 (sous-ensemble filtré uniquement)

## Détails des formats

### GeoPackage (.gpkg)

**Format recommandé** pour la plupart des cas d'usage.

**Avantages :**
- ✅ Fichier unique (portable)
- ✅ Taille illimitée
- ✅ Plusieurs couches par fichier
- ✅ Index spatiaux intégrés
- ✅ Standard ouvert (OGC)
- ✅ Performance rapide
- ✅ Supporte tous les types de géométrie

**Limitations :**
- ⚠️ Requiert GDAL 2.0+ (standard dans QGIS moderne)

**Quand l'utiliser :**
- Choix par défaut pour la plupart des exports
- Grands jeux de données (>100k entités)
- Exports multi-couches
- Archivage long terme

**Exemple d'export :**
```python
fichier_sortie = "/chemin/vers/export.gpkg"
nom_couche = "entités_filtrées"
# Fichier unique, plusieurs couches possibles
```

### Shapefile (.shp)

Format legacy pour la **rétrocompatibilité**.

**Avantages :**
- ✅ Compatibilité universelle
- ✅ Largement supporté
- ✅ Structure simple

**Limitations :**
- ❌ Limite de taille de fichier 2 Go
- ❌ Limite de nom de champ 10 caractères
- ❌ Types de données limités
- ❌ Fichiers multiples (.shp, .dbf, .shx, .prj)
- ❌ Pas de types de géométrie mixtes
- ⚠️ Problèmes d'encodage (caractères non-ASCII)

**Quand l'utiliser :**
- Requis par un logiciel legacy
- Partage avec des utilisateurs ArcGIS Desktop 9.x
- Jeux de données simples et petits

**Recommandations :**
- Utilisez GeoPackage à la place si possible
- Gardez le nombre d'entités < 100k
- Évitez les noms de champs longs
- Testez l'encodage avec des caractères non-ASCII

**Exemple d'export :**
```python
fichier_sortie = "/chemin/vers/export.shp"
# Crée les fichiers .shp, .dbf, .shx, .prj
```

### GeoJSON (.geojson)

Format texte pour les **applications web**.

**Avantages :**
- ✅ Lisible par l'humain
- ✅ Compatible web
- ✅ Natif JavaScript
- ✅ Intégration API
- ✅ Compatible contrôle de version

**Limitations :**
- ⚠️ Tailles de fichier importantes (format texte)
- ⚠️ Performance plus lente que les formats binaires
- ⚠️ Pas d'index spatiaux
- ⚠️ WGS84 (EPSG:4326) recommandé

**Quand l'utiliser :**
- Cartographie web (Leaflet, Mapbox)
- APIs REST
- Petits à moyens jeux de données (<10k entités)
- Contrôle de version Git

**Exemple d'export :**
```python
fichier_sortie = "/chemin/vers/export.geojson"
scr = "EPSG:4326"  # WGS84 recommandé pour le web
```

### KML/KMZ (.kml, .kmz)

Format pour **Google Earth** et applications mobiles.

**Avantages :**
- ✅ Compatibilité Google Earth
- ✅ KMZ inclut le style et les images
- ✅ Support applications mobiles
- ✅ Lisible par l'humain (KML)

**Limitations :**
- ❌ Support d'attributs limité
- ❌ Complexité du style
- ⚠️ Problèmes de performance avec grands jeux de données
- ⚠️ WGS84 uniquement (EPSG:4326)

**Quand l'utiliser :**
- Visualisation Google Earth
- Applications mobiles de terrain
- Présentations aux parties prenantes
- Engagement public

**Exemple d'export :**
```python
fichier_sortie = "/chemin/vers/export.kmz"  # Compressé
# ou
fichier_sortie = "/chemin/vers/export.kml"  # Texte
```

### CSV (.csv)

Format **tabulaire** pour coordonnées et attributs.

**Avantages :**
- ✅ Compatibilité tableur universelle
- ✅ Petite taille de fichier
- ✅ Facile à éditer
- ✅ Import base de données facile

**Limitations :**
- ❌ Pas de géométrie (seulement coordonnées X,Y pour les points)
- ❌ Pas de référence spatiale
- ❌ Pas de style
- ⚠️ Points uniquement (pas de lignes/polygones)

**Quand l'utiliser :**
- Coordonnées de points uniquement
- Analyse Excel/tableur
- Rapports attributaires uniquement
- Imports de base de données

**Exemple d'export :**
```python
fichier_sortie = "/chemin/vers/export.csv"
# Inclut les colonnes X, Y pour la géométrie point
# GEOMETRY_AS: 'AS_XY' ou 'AS_WKT'
```

### PostGIS (PostgreSQL)

Exporter vers une **base de données PostgreSQL** avec l'extension PostGIS.

**Avantages :**
- ✅ Meilleure performance
- ✅ Taille illimitée
- ✅ Accès multi-utilisateur
- ✅ Index spatiaux
- ✅ Requêtes avancées
- ✅ Fonctionnalités entreprise

**Limitations :**
- ⚠️ Requiert PostgreSQL + PostGIS
- ⚠️ Configuration réseau nécessaire
- ⚠️ Administration plus complexe

**Quand l'utiliser :**
- Environnements entreprise
- Grands jeux de données (>1M entités)
- Collaboration multi-utilisateur
- Mises à jour continues
- Intégration avec systèmes backend

**Exemple d'export :**
```python
connexion = "postgresql://user:password@host:5432/database"
schema = "public"
nom_table = "entités_filtrées"
```

### Spatialite (.sqlite)

**Fichier de base de données** léger.

**Avantages :**
- ✅ Fichier unique
- ✅ Index spatiaux
- ✅ Requêtes SQL
- ✅ Bonne performance
- ✅ Pas de serveur nécessaire

**Limitations :**
- ⚠️ Plus lent que PostGIS
- ⚠️ Limitation mono-écriture
- ⚠️ Max théorique 140 To

**Quand l'utiliser :**
- Bases de données portables
- Jeux de données moyens (10k-1M entités)
- Travail hors ligne
- Applications desktop

**Exemple d'export :**
```python
fichier_sortie = "/chemin/vers/export.sqlite"
nom_table = "entités_filtrées"
```

## Options d'export

### Système de Coordonnées de Référence (SCR)

Choisissez le SCR cible pour votre export :

```python
# Garder le SCR original
scr = layer.crs()

# Transformer vers WGS84 (web/GPS)
scr = "EPSG:4326"

# Transformer vers projection locale
scr = "EPSG:32633"  # UTM Zone 33N
```

**Choix SCR courants :**
- **EPSG:4326** (WGS84) - Cartes web, GPS, global
- **EPSG:3857** (Web Mercator) - Tuiles web
- **EPSG:32xxx** (UTM) - Projection locale, métrique
- **SCR Original** - Maintenir la projection source

### Sélection de champs

Exportez des champs spécifiques ou tous les attributs :

```python
# Tous les champs
champs_export = None

# Champs sélectionnés uniquement
champs_export = ['nom', 'population', 'surface', 'date']

# Exclure des champs
champs_exclus = ['id_interne', 'champ_temp']
```

### Type de géométrie

Contrôlez l'export de géométrie :

```python
# Garder la géométrie (par défaut)
geometrie = True

# Attributs uniquement (pas de géométrie)
geometrie = False

# Simplifier la géométrie (réduire la taille)
geometrie = "simplified"
tolerance_simplification = 10  # mètres
```

### Encodage

Encodage de caractères pour les champs texte :

```python
# UTF-8 (recommandé, par défaut)
encodage = "UTF-8"

# Latin-1 (Europe de l'Ouest)
encodage = "ISO-8859-1"

# Windows-1252 (défaut Windows)
encodage = "CP1252"
```

## Stratégies d'export

### Export de grands jeux de données

Pour les jeux de données > 100k entités :

```mermaid
graph TD
    A[Grand jeu de données] --> B{Vérification taille}
    B -->|< 100k| C[Export direct]
    B -->|100k - 1M| D[GeoPackage]
    B -->|> 1M| E[PostGIS]
    
    D --> F[Activer index spatial]
    E --> G[Traitement batch]
    
    F --> H[Export terminé]
    G --> H
    C --> H
    
    style D fill:#90EE90
    style E fill:#87CEEB
```

**Recommandations :**
1. **Utilisez GeoPackage ou PostGIS** - Formats binaires
2. **Activez les index spatiaux** - Accès ultérieur plus rapide
3. **Traitement batch** - Exportez par morceaux si nécessaire
4. **Simplifiez la géométrie** - Réduisez le nombre de sommets si approprié

### Export multi-format

Exportez les mêmes données vers plusieurs formats :

```python
# Flux d'export
filtre_applique = True

# Version web (GeoJSON)
export_geojson(scr="EPSG:4326", simplifie=True)

# Version desktop (GeoPackage)
export_geopackage(scr=scr_original, precision_complete=True)

# Version tableur (CSV)
export_csv(coordonnees="XY", attributs_uniquement=False)
```

### Exports incrémentaux

Exportez les changements depuis la dernière mise à jour :

```python
# Filtrer par date
expression_filtre = "last_modified >= '2024-01-01'"

# Export avec horodatage
fichier_sortie = f"mises_a_jour_{datetime.now().strftime('%Y%m%d')}.gpkg"
```

## Exemples pratiques

### Export urbanisme

```python
# Exporter les parcelles filtrées pour révision
expression_filtre = """
zone = 'commercial'
AND surface > 5000
AND statut = 'propose'
"""

# Formats multiples pour différentes parties prenantes
export_geopackage("parcelles_revision.gpkg")  # Équipe SIG
export_kml("parcelles_revision.kmz")  # Présentation publique
export_csv("liste_parcelles.csv")  # Commission d'urbanisme
```

### Surveillance environnementale

```python
# Exporter les sites de surveillance avec données récentes
expression_filtre = """
type_site = 'qualite_eau'
AND dernier_prelevement >= now() - interval '30 days'
AND nombre_parametres > 5
"""

# GeoJSON pour tableau de bord web
export_geojson(
    sortie="sites_surveillance.geojson",
    scr="EPSG:4326",
    champs=['id_site', 'dernier_prelevement', 'statut']
)
```

### Réponse d'urgence

```python
# Exporter les zones d'évacuation
expression_filtre = """
intersects(
    $geometry,
    buffer(geometry(get_feature('danger', 'statut', 'actif')), 2000)
)
AND occupation > 0
"""

# KML pour équipes terrain
export_kml("zones_evacuation.kmz")

# GeoPackage pour analyse SIG
export_geopackage("analyse_evacuation.gpkg")
```

## Optimisation des performances

### Comparaison des backends

| Backend | Vitesse d'export | Recommandé |
|---------|------------------|------------|
| PostgreSQL | ⚡⚡⚡⚡ Le plus rapide | GeoPackage, PostGIS |
| Spatialite | ⚡⚡⚡ Rapide | GeoPackage, Spatialite |
| OGR | ⚡⚡ Modéré | GeoPackage |

### Conseils d'optimisation

1. **Simplifier la géométrie**
   ```python
   # Réduire le nombre de sommets
   tolerance_simplification = 10  # mètres
   ```

2. **Sélectionner les champs nécessaires**
   ```python
   # Exporter uniquement les attributs nécessaires
   champs = ['id', 'nom', 'statut']
   ```

3. **Utiliser le format approprié**
   ```python
   # Formats binaires plus rapides que texte
   GeoPackage > Shapefile > GeoJSON
   ```

4. **Activer les index spatiaux**
   ```python
   # Pour GeoPackage/Spatialite
   creer_index_spatial = True
   ```

## Dépannage

### L'export échoue

**Problèmes courants :**

1. **Fichier verrouillé**
   - Fermez les applications utilisant le fichier
   - Vérifiez les permissions de fichier

2. **Espace disque**
   - Vérifiez l'espace disponible
   - Utilisez la compression (KMZ, GPKG)

3. **Géométries invalides**
   ```sql
   -- Filtrez les géométries invalides avant l'export
   is_valid($geometry)
   ```

4. **Problèmes d'encodage**
   - Utilisez l'encodage UTF-8
   - Testez avec des entités échantillon

### Taille de fichier importante

**Solutions :**

1. **Simplifier la géométrie**
   ```python
   tolerance_simplification = 10  # Réduire la précision
   ```

2. **Réduire les attributs**
   ```python
   champs = ['champ_essentiel_1', 'champ_essentiel_2']
   ```

3. **Utiliser la compression**
   ```python
   # KMZ au lieu de KML
   # GPKG a une compression interne
   ```

4. **Diviser en tuiles**
   ```python
   # Exporter par région ou grille
   expression_filtre = "region = 'nord'"
   ```

### Problèmes de projection

**Solutions :**

1. **Vérifier le SCR source**
   ```python
   scr_source = layer.crs()
   print(f"Source : {scr_source.authid()}")
   ```

2. **Transformer explicitement**
   ```python
   scr_cible = "EPSG:4326"
   ```

3. **Vérifier la précision de transformation**
   ```python
   # Utilisez la transformation appropriée
   # Surtout pour les datums historiques
   ```

## Exemples d'export batch

### Plusieurs couches filtrées

Exportez plusieurs couches avec différentes configurations :

**Scénario** : Exporter 3 couches avec différents filtres, formats et SCR

**Étape 1 - Filtrer les couches** (dans l'onglet FILTERING) :
```
Couche 1 (parcelles) : zone = 'commercial'
Couche 2 (batiments) : annee_construction > 2020
Couche 3 (routes) : classe_route = 'autoroute'
```

**Étape 2 - Configurer l'export batch** (dans l'onglet EXPORTING) :
```
Configuration de l'onglet EXPORTING :
- Couches sélectionnées : parcelles, batiments, routes (les 3)
- Format : GeoPackage
- SCR : EPSG:3857 (Web Mercator)
- Styles : QML
- Dossier de sortie : C:/exports/
- Mode batch : ACTIVÉ
- ZIP : ACTIVÉ
```

**Résultat** :
```
C:/exports/export_2024-12-09.zip
  ├── parcelles.gpkg (zones commerciales, filtrées)
  ├── parcelles.qml
  ├── batiments.gpkg (bâtiments récents, filtrés)
  ├── batiments.qml
  ├── routes.gpkg (autoroutes, filtrées)
  └── routes.qml
```

**Avantages** :
- Opération unique exporte toutes les couches
- Chaque couche dans un fichier séparé (mode batch)
- Toutes re-projetées vers Web Mercator
- Styles préservés
- Compressé pour livraison

### Exporter des données non filtrées

Pour exporter des couches complètes (sans filtres) :

**Option 1 - Supprimer les filtres d'abord** (onglet FILTERING) :
1. Basculer vers l'onglet FILTERING
2. Cliquer sur le bouton RESET pour effacer tous les filtres
3. Basculer vers l'onglet EXPORTING
4. Exporter normalement

**Option 2 - Exporter différentes couches** :
- Sélectionnez simplement les couches qui n'ont pas de filtres appliqués
- L'onglet EXPORTING exporte l'état actuel de la couche

:::info Export filtré vs non filtré
- **Avec filtres** : L'onglet EXPORTING exporte uniquement les entités correspondant aux filtres actuels
- **Sans filtres** : Exporte la couche complète (toutes les entités)
- Vérifiez le nombre d'entités dans le sélecteur de couches pour confirmer ce qui sera exporté
:::

## Sujets connexes

- [Bases du filtrage](filtering-basics.md) - Créer des filtres pour exporter des sous-ensembles filtrés (onglet FILTERING)
- [Filtrage géométrique](geometric-filtering.md) - Appliquer des filtres spatiaux avant l'export
- [Opérations de tampon](buffer-operations.md) - Filtrage basé sur la proximité avant l'export
- [Vue d'ensemble de l'interface](interface-overview.md) - Guide complet des composants de l'onglet EXPORTING

:::info Flux de travail des trois onglets principaux
1. **Onglet FILTERING** : Créer des sous-ensembles filtrés (optionnel)
2. **Onglet EXPLORING** : Visualiser et vérifier les entités (optionnel)
3. **Onglet EXPORTING** : Exporter vers différents formats (filtré ou non filtré)

Les trois onglets fonctionnent ensemble pour fournir un flux de travail complet de traitement de données.
:::

## Étapes suivantes

- **[Historique des filtres](filter-history.md)** - Réutiliser les configurations de filtres pour les exports
- **[Vue d'ensemble de l'interface](interface-overview.md)** - Découvrir les trois onglets principaux
