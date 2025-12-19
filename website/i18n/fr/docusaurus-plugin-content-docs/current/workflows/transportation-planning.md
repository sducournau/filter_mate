---
sidebar_position: 6
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Planification des Transports : Export de Données Routières

Extraire et exporter les segments routiers dans les limites municipales avec des attributs spécifiques pour l'analyse de planification des transports.

## Aperçu du Scénario

**Objectif** : Exporter toutes les routes principales (autoroute, primaire, secondaire) dans les limites de la ville avec transformation SCR appropriée pour les logiciels CAO/ingénierie.

**Application Réelle** :
- Départements des transports préparant des données pour les entrepreneurs
- Cabinets d'ingénierie analysant les réseaux routiers
- Analystes SIG créant des sous-ensembles de données pour la modélisation
- Urbanistes évaluant la couverture des infrastructures

**Temps Estimé** : 10 minutes

**Difficulté** : ⭐ Débutant

---

## Prérequis

### Données Requises

1. **Couche Réseau Routier** (lignes)
   - Segments routiers/axes
   - Attributs requis :
     - `type_route` ou classification `highway`
     - `nom` (nom de rue)
   - Optionnel : `surface`, `voies`, `vitesse_max`, `etat`

2. **Limite Municipale** (polygone)
   - Limite de ville, comté ou district
   - Entité unique préférée (utiliser Dissoudre si multiples)
   - Doit correspondre ou chevaucher l'étendue du réseau routier

### Sources de Données Exemples

**Données Routières** :
```python
# OpenStreetMap via QuickOSM
Clé: "highway", Valeur: "*"

# Types de routes à inclure:
- motorway (autoroute)
- trunk (route nationale)  
- primary (route principale)
- secondary (route secondaire)
- tertiary (route tertiaire)
```

**Limites** :
- Portails SIG municipaux (limites officielles)
- Fichiers Census TIGER/Line (USA)
- Limites administratives OpenStreetMap
- Agences cartographiques nationales (IGN, etc.)

### Recommandation de Backend

**N'importe Quel Backend** - Ce flux de travail se concentre sur les fonctionnalités d'export :
- **OGR** : Compatibilité universelle, fonctionne avec tous les formats
- **Spatialite** : Si vous avez besoin de traitement temporaire
- **PostgreSQL** : Si export de très grands réseaux (>100k segments)

Tous les backends exportent de manière identique - choisissez selon votre configuration.

---

## Instructions Étape par Étape

### Étape 1 : Charger et Vérifier les Données

1. **Charger les couches** dans QGIS :
   - `reseau_routier.gpkg` (ou OSM .shp, .geojson)
   - `limite_ville.gpkg`

2. **Vérifier le SCR** :
   ```
   Les deux couches devraient idéalement être dans le même SCR
   Clic droit → Propriétés → Information → SCR
   
   Note : Pas critique pour ce flux de travail (FilterMate gère la reprojection)
   ```

3. **Inspecter les attributs** :
   ```
   Ouvrir la table d'attributs routes (F6)
   Trouver le champ de classification routière : "highway", "type_route", "fclass", etc.
   Noter le nom du champ pour l'étape suivante
   ```

4. **Vérifier la limite** :
   ```
   Sélectionner la couche limite_ville
   Devrait montrer une seule entité couvrant votre zone d'intérêt
   Si plusieurs polygones : Vecteur → Géotraitement → Dissoudre
   ```

:::tip Classifications Routières OSM
Valeurs OpenStreetMap `highway` :
- `motorway` : Autoroute
- `trunk` : Routes nationales entre villes
- `primary` : Routes principales dans les villes
- `secondary` : Routes de liaison  
- `tertiary` : Routes locales importantes
- `residential` : Rues de quartier
:::

### Étape 2 : Filtrer les Routes par Type et Localisation

**Utiliser FilterMate** :

1. Ouvrir le panneau FilterMate
2. Sélectionner la couche **reseau_routier**
3. Choisir **n'importe quel backend** (OGR convient)
4. Entrer l'expression de filtre :

<Tabs>
  <TabItem value="osm" label="Données OpenStreetMap" default>
    ```sql
    -- Routes principales uniquement (exclure résidentiel, voies de service)
    "highway" IN ('motorway', 'trunk', 'primary', 'secondary')
    
    -- Dans la limite de la ville
    AND intersects(
      $geometry,
      aggregate(
        layer:='limite_ville',
        aggregate:='collect',
        expression:=$geometry
      )
    )
    ```
  </TabItem>
  
  <TabItem value="generic" label="Données Routières Génériques">
    ```sql
    -- Ajuster le nom du champ selon vos données
    "type_route" IN ('autoroute', 'artere', 'collectrice')
    
    -- Dans la municipalité
    AND within(
      $geometry,
      aggregate('limite_ville', 'collect', $geometry)
    )
    ```
  </TabItem>
  
  <TabItem value="advanced" label="Filtrage Avancé">
    ```sql
    -- Routes principales + critères additionnels
    "highway" IN ('motorway', 'trunk', 'primary', 'secondary')
    AND intersects($geometry, aggregate('limite_ville', 'collect', $geometry))
    
    -- Optionnel : Ajouter des filtres de condition
    AND ("surface" = 'paved' OR "surface" IS NULL)  -- Exclure non pavé
    AND "lanes" >= 2  -- Multi-voies uniquement
    AND "access" != 'private'  -- Routes publiques uniquement
    ```
  </TabItem>
</Tabs>

5. Cliquer sur **Appliquer le Filtre**
6. Examiner le compte : "Affichage de X sur Y entités"
7. Inspecter visuellement : Seules les routes principales dans la limite doivent être surlignées

**Résultat Attendu** : Segments routiers filtrés aux types principaux dans les limites de la ville

### Étape 3 : Examiner et Affiner la Sélection

**Vérifier la couverture** :

1. Zoomer sur l'étendue complète de limite_ville
2. Vérifier que les routes filtrées couvrent toute la municipalité
3. Rechercher des lacunes ou segments manquants

**Ajuster si nécessaire** :

```sql
-- Si trop de routes incluses, être plus strict :
"highway" IN ('motorway', 'trunk', 'primary')  -- Exclure secondary

-- Si routes importantes manquantes, élargir :
"highway" IN ('motorway', 'trunk', 'primary', 'secondary', 'tertiary')

-- Si utilisation classification personnalisée :
"classe_fonctionnelle" IN (1, 2, 3)  -- Codes numériques
```

**Cas limites** - Routes partiellement hors limite :

<Tabs>
  <TabItem value="include" label="Inclure Segments Partiels" default>
    ```sql
    -- Utiliser intersects (inclut les chevauchements partiels)
    intersects($geometry, aggregate('limite_ville', 'collect', $geometry))
    ```
  </TabItem>
  
  <TabItem value="exclude" label="Uniquement Complètement à l'Intérieur">
    ```sql
    -- Utiliser within (seulement routes entièrement contenues)
    within($geometry, aggregate('limite_ville', 'collect', $geometry))
    ```
  </TabItem>
  
  <TabItem value="clip" label="Découper à la Limite (Manuel)">
    Après filtrage, utiliser l'outil Découper de QGIS :
    ```
    Vecteur → Géotraitement → Découper
    Entrée : routes filtrées
    Superposition : limite_ville
    Résultat : Routes coupées exactement à la limite
    ```
  </TabItem>
</Tabs>

### Étape 4 : Sélectionner les Attributs à Exporter

**Identifier les champs utiles** :

1. Ouvrir la **Table d'Attributs** de la couche filtrée
2. Noter les colonnes pertinentes :
   ```
   Essentiels :
   - id_route, osm_id (identifiant)
   - nom (nom de rue)
   - highway / type_route (classification)
   
   Utiles :
   - surface (pavé, non pavé, etc.)
   - voies (nombre de voies)
   - vitesse_max (limitation de vitesse)
   - longueur_m (calculé ou existant)
   ```

3. Optionnel : **Supprimer les colonnes inutiles** avant l'export :
   ```
   Couche → Propriétés → Champs
   Activer mode édition (icône crayon)
   Supprimer champs non désirés (métadonnées osm, etc.)
   Sauvegarder les modifications
   ```

### Étape 5 : Ajouter des Champs Calculés (Optionnel)

**Ajouter la longueur de route** dans vos unités préférées :

1. Ouvrir la **Calculatrice de Champs** (Ctrl+I)
2. Créer un nouveau champ :
   ```
   Nom du champ : longueur_m
   Type : Décimal (double)
   Précision : 2
   
   Expression :
   $length
   ```

**Ajouter la longueur en différentes unités** :
   ```
   Nom du champ : longueur_km
   Expression : $length / 1000  -- mètres vers kilomètres
   ```

**Ajouter une classification fonctionnelle** (si conversion données OSM) :
   ```
   Nom du champ : classe_fonctionnelle
   Type : Entier
   
   Expression :
   CASE
     WHEN "highway" IN ('motorway', 'trunk') THEN 1
     WHEN "highway" = 'primary' THEN 2
     WHEN "highway" = 'secondary' THEN 3
     WHEN "highway" = 'tertiary' THEN 4
     ELSE 5
   END
   ```

### Étape 6 : Choisir le SCR Cible pour l'Export

**Choix de SCR courants** :

<Tabs>
  <TabItem value="wgs84" label="WGS84 (Universel)" default>
    ```
    EPSG:4326 - WGS84 Géographique
    
    Utiliser pour :
    - Cartographie web (Leaflet, Google Maps)
    - Applications GPS
    - Interopérabilité maximale
    
    ⚠️ Pas adapté pour CAO (utilise degrés, pas mètres)
    ```
  </TabItem>
  
  <TabItem value="utm" label="UTM (Ingénierie)">
    ```
    EPSG:326XX - Zones UTM
    Exemples :
    - EPSG:32633 - UTM Zone 33N (Europe centrale)
    - EPSG:32631 - UTM Zone 31N (France métropolitaine)
    
    Utiliser pour :
    - Logiciels CAO (AutoCAD, MicroStation)
    - Dessins d'ingénierie
    - Mesures de distance précises
    
    ✓ Basé mètres, préserve la précision
    ```
  </TabItem>
  
  <TabItem value="local" label="Grille Locale">
    ```
    Systèmes Nationaux/Régionaux
    Exemples :
    - EPSG:27700 - British National Grid (UK)
    - EPSG:2154 - Lambert 93 (France)
    - EPSG:3857 - Web Mercator (cartes web)
    
    Utiliser pour :
    - Compatibilité agence cartographique nationale
    - Conformité aux standards régionaux
    ```
  </TabItem>
</Tabs>

**Trouver votre SCR** :
- Rechercher sur [epsg.io](https://epsg.io/) par localisation
- Vérifier exigences/spécifications du projet
- Demander à l'organisation destinataire le SCR préféré

### Étape 7 : Exporter les Routes Filtrées

**Utiliser l'Export FilterMate** (Recommandé) :

1. Dans le panneau FilterMate, cliquer sur **Exporter les Entités Filtrées**
2. Configurer les paramètres d'export :

   ```
   Format : Choisir selon les besoins du destinataire
   
   Pour SIG :
   ├── GeoPackage (.gpkg) - Meilleur pour QGIS/SIG modernes
   ├── Shapefile (.shp) - Format SIG universel
   └── GeoJSON (.geojson) - Cartographie web, léger
   
   Pour CAO :
   ├── DXF (.dxf) - AutoCAD, plus compatible
   └── DWG (.dwg) - AutoCAD (nécessite plugin)
   
   Pour Bases de Données :
   ├── PostGIS - Export base de données direct
   └── Spatialite - Base de données embarquée
   
   Pour Autre :
   ├── CSV avec géométrie WKT - Texte
   ├── KML - Google Earth
   └── GPX - Appareils GPS
   ```

3. **Définir le SCR** (Système de Référence de Coordonnées) :
   ```
   Cliquer sur le sélecteur SCR
   Rechercher le SCR cible (ex : "Lambert 93" ou "EPSG:2154")
   Sélectionner et confirmer
   
   ℹ️ FilterMate reprojette automatiquement
   ```

4. **Configurer les options** :
   ```
   ✓ Exporter uniquement entités sélectionnées (déjà filtrées)
   ✓ Ignorer champs d'attributs : [choisir champs inutiles]
   ✓ Ajouter colonne géométrie (pour exports CSV)
   ✓ Forcer type multi-lignes (si requis)
   ```

5. **Nommer et sauvegarder** :
   ```
   Nom de fichier : ville_routes_principales_lambert93_2024.gpkg
   
   Convention de nommage conseil :
   [lieu]_[contenu]_[scr]_[date].[ext]
   ```

6. Cliquer sur **Exporter** → Attendre la confirmation

### Étape 8 : Valider l'Export

**Contrôles qualité** :

1. **Recharger le fichier exporté** dans QGIS :
   ```
   Couche → Ajouter une Couche → Ajouter une Couche Vecteur
   Parcourir vers fichier exporté
   ```

2. **Vérifier le SCR** :
   ```
   Clic droit couche → Propriétés → Information
   Vérifier que SCR correspond à votre cible (ex : EPSG:2154)
   ```

3. **Vérifier le compte d'entités** :
   ```
   Devrait correspondre au compte filtré de l'Étape 2
   Ouvrir table d'attributs (F6) pour vérifier
   ```

4. **Inspecter les attributs** :
   ```
   Tous les champs sélectionnés présents et remplis
   Pas de valeurs NULL dans champs critiques
   Encodage texte correct (pas de caractères corrompus)
   ```

5. **Comparaison visuelle** :
   ```
   Superposer couche exportée avec originale
   Vérifier que géométries correspondent exactement
   Vérifier qu'aucun segment perdu ou dupliqué
   ```

**Tester avec le logiciel du destinataire** (si possible) :
- Ouvrir dans AutoCAD/MicroStation (pour exports DXF)
- Charger dans ArcGIS/MapInfo (pour Shapefile)
- Importer en base de données (pour exports SQL)

---

## Comprendre les Résultats

### Ce Que Vous Avez Exporté

✅ **Inclus** :
- Routes principales (motorway, trunk, primary, secondary) uniquement
- Routes intersectant/dans la limite de ville
- Attributs sélectionnés pertinents pour l'analyse
- Géométrie reprojetée vers SCR cible

❌ **Exclu** :
- Routes mineures (résidentiel, service, chemins)
- Routes hors municipalité
- Métadonnées OSM et champs techniques
- SCR original (si reprojeté)

### Attentes de Taille de Fichier

**Tailles typiques** pour ville moyenne (500km² surface) :

```
Format      | ~10k segments | Notes
------------|---------------|----------------------------
GeoPackage  | 2-5 MB        | Plus petit, plus rapide
Shapefile   | 3-8 MB        | Fichiers multiples (.shp/.dbf/.shx)
GeoJSON     | 5-15 MB       | Basé texte, plus grand mais lisible
DXF         | 4-10 MB       | Format CAO
CSV+WKT     | 10-30 MB      | Géométrie texte, très grand
```

---

## Meilleures Pratiques

### Préparation des Données

**Liste de vérification avant export** :

```
□ Filtre appliqué et vérifié
□ Table d'attributs examinée
□ Champs inutiles supprimés
□ Champs calculés ajoutés (longueur, etc.)
□ Géométries validées
□ SCR déterminé
□ Format d'export confirmé avec destinataire
```

### Conventions de Nommage

**Bonnes pratiques de nommage de fichier** :

```
Bon :
✓ paris_routes_principales_lambert93_20240312.gpkg
✓ lyon_autoroutes_lambert93_v2.shp
✓ marseille_reseau_transport_wgs84_2024.geojson

Mauvais :
✗ routes.shp (trop générique)
✗ export_final_FINAL_v3.gpkg (versioning flou)
✗ données.gpkg (nom peu descriptif)
```

### Documentation des Métadonnées

**Toujours inclure un fichier de métadonnées** :

```
metadata.txt ou README.txt contenu :

=== Export Réseau Routier ===
Date : 2024-03-12
Analyste : Jean Dupont
Projet : Plan Directeur Transport Ville

Données Source :
- Routes : OpenStreetMap (téléchargé 2024-03-01)
- Limite : Portail SIG Ville (limite officielle 2024)

Traitement :
- Filtre : Routes principales uniquement (motorway, trunk, primary, secondary)
- Zone : Dans limites de ville
- Outil : Plugin QGIS FilterMate v2.8.0

Spécifications Export :
- Format : GeoPackage
- SCR : EPSG:2154 (Lambert 93)
- Nombre d'Entités : 8 432 segments
- Longueur Totale : 1 247,3 km

Attributs :
- osm_id : Identifiant OpenStreetMap
- nom : Nom de rue
- highway : Classification routière
- surface : Type de revêtement
- voies : Nombre de voies
- longueur_m : Longueur segment en mètres

Notes Qualité :
- Géométries validées et réparées
- Routes partiellement hors limite incluses (intersects)
- Limitations vitesse : 15% données manquantes (défaut standard ville)

Contact : jean.dupont@ville.fr
```

---

## Problèmes Courants

### Problème 1 : Routes le long de la limite partiellement coupées

**Cause** : Utilisation de `within()` au lieu de `intersects()`

**Solution** :
```sql
-- Changer de :
within($geometry, aggregate('limite_ville', 'collect', $geometry))

-- À :
intersects($geometry, aggregate('limite_ville', 'collect', $geometry))

-- Ou découper géométriquement après export :
Vecteur → Géotraitement → Découper
```

### Problème 2 : Export échoue avec "erreur d'écriture"

**Cause** : Permissions fichier, problèmes chemin, ou espace disque

**Solutions** :
```
1. Vérifier espace disque (besoin 2-3x taille fichier final)
2. Exporter vers emplacement différent (ex : Bureau au lieu lecteur réseau)
3. Fermer fichier s'il est ouvert dans autre programme
4. Utiliser chemin fichier plus court (<100 caractères)
5. Retirer caractères spéciaux du nom de fichier
```

### Problème 3 : Logiciel CAO n'ouvre pas le DXF

**Cause** : Export DXF QGIS peut ne pas correspondre aux attentes version CAO

**Solutions** :
```
Option A : Essayer paramètres export DXF différents
   Projet → Import/Export → Exporter Projet vers DXF
   - Version format DXF : AutoCAD 2010
   - Mode symbologie : Symbologie entité

Option B : Utiliser format intermédiaire
   Exporter vers Shapefile → Ouvrir dans AutoCAD (support SHP intégré)

Option C : Utiliser plugin spécialisé
   Installer plugin "Another DXF Exporter"
   Meilleure compatibilité CAO que export natif
```

---

## Prochaines Étapes

### Flux de Travail Associés

- **[Analyse Immobilière](./real-estate-analysis)** : Techniques de filtrage par attributs
- **[Services d'Urgence](./emergency-services)** : Sélection basée sur tampons
- **[Planification Urbaine Transport](./urban-planning-transit)** : Filtrage spatial multi-couches

### Techniques Avancées

**1. Export Topologie de Réseau** :
```
Exporter routes avec connectivité maintenue pour analyse routage
Traitement → Analyse Vectorielle → Analyse de Réseau → Zones de Service
```

**2. Export Batch Multi-SCR** :
```python
# Console Python - exporter vers plusieurs SCR simultanément
liste_scr_cibles = [2154, 4326, 32631]  # Codes EPSG
layer = iface.activeLayer()

for epsg in liste_scr_cibles:
    fichier_sortie = f'routes_epsg{epsg}.gpkg'
    # Utiliser QgsVectorFileWriter pour export programmatique
```

**3. Automatisation Export Planifié** :
```python
# Créer modèle de traitement QGIS
# Planifier avec cron (Linux) ou Planificateur Tâches (Windows)
# Auto-exporter données routières mises à jour hebdomadairement
```

---

## Résumé

✅ **Vous avez appris** :
- Filtrer routes par classification et limite
- Sélectionner et préparer attributs pour export
- Choisir SCR cible approprié
- Exporter vers multiples formats (GeoPackage, Shapefile, DXF, etc.)
- Valider qualité d'export
- Créer documentation métadonnées

✅ **Techniques clés** :
- Prédicats spatiaux : `intersects()` vs `within()`
- Transformation SCR durant export
- Sélection format selon cas d'usage
- Calculatrice de champs pour attributs dérivés
- Traitement batch pour grands jeux de données

🎯 **Impact réel** : Ce flux de travail simplifie la préparation de données pour projets de transport, assure l'interopérabilité données entre systèmes SIG et CAO, et maintient la qualité des données tout au long du pipeline d'analyse.

💡 **Astuce pro** : Créez un **Modèle de Traitement QGIS** pour ce flux de travail pour automatiser filtrage + export en un clic. Sauvegardez le modèle et réutilisez pour différentes villes ou périodes.
