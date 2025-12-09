---
sidebar_position: 3
---

# Votre Premier Filtre

Ce tutoriel vous guide pas à pas pour créer votre premier filtre avec FilterMate.

## Scénario

**Objectif** : Trouver tous les bâtiments situés à moins de 200 mètres d'une route principale.

**Données nécessaires** :
- Une couche **bâtiments** (polygones)
- Une couche **routes** (lignes)

## Tutoriel Étape par Étape

### 1. Charger Vos Données

Commencez par charger les deux couches dans QGIS :

1. Ouvrez QGIS
2. Chargez la couche **bâtiments** (la couche à filtrer)
3. Chargez la couche **routes** (la couche de référence)

:::info Données d'exemple
Si vous n'avez pas de données d'exemple, vous pouvez utiliser les données OpenStreetMap :
- Téléchargez depuis [Geofabrik](https://download.geofabrik.de/)
- Ou utilisez le plugin QGIS **QuickOSM** pour récupérer les données
:::

### 2. Ouvrir FilterMate

1. Cliquez sur l'icône **FilterMate** dans la barre d'outils
2. Ou allez dans **Extensions** → **FilterMate**
3. Le panneau ancrable apparaît sur le côté droit

<!-- ![Configuration du premier filtre](/img/first-filter-1.png -->
*Panneau FilterMate prêt pour votre premier filtre géométrique*

### 3. Sélectionner la Couche Cible

1. Dans la liste déroulante **Sélection de couche** en haut
2. Sélectionnez **bâtiments** (la couche que nous voulons filtrer)

FilterMate analysera la couche et affichera :
- Le backend utilisé (PostgreSQL, Spatialite ou OGR)
- Le nombre d'entités
- Les champs disponibles

### 4. Configurer le Filtre Géométrique

Créons maintenant un filtre spatial pour trouver les bâtiments proches des routes :

1. **Allez dans l'onglet Filtre Géométrique**
   - Cliquez sur l'onglet **Filtre Géométrique** dans le panneau

2. **Sélectionnez la Couche de Référence**
   - Choisissez **routes** dans la liste déroulante des couches de référence

3. **Choisissez le Prédicat Spatial**
   - Sélectionnez **"à distance"** ou **"intersecte"** (si vous utilisez un tampon)

4. **Définir la Distance de Tampon**
   - Entrez **200** dans le champ distance de tampon
   - Unités : **mètres** (ou les unités du SCR de votre couche)

:::tip Reprojection SCR
FilterMate reprojette automatiquement les couches si elles ont des SCR différents. Pas besoin de reprojection manuelle !
:::

### 5. Appliquer le Filtre

1. Cliquez sur le bouton **Appliquer le filtre**
2. FilterMate va :
   - Créer une vue filtrée temporaire
   - Mettre en évidence les entités correspondantes sur la carte
   - Mettre à jour le nombre d'entités dans le panneau

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

**Ce qui se passe en coulisses :**

<Tabs>
  <TabItem value="postgresql" label="Backend PostgreSQL" default>
    ```sql
    -- Crée une vue matérialisée avec index spatial
    CREATE MATERIALIZED VIEW temp_filter AS
    SELECT b.*
    FROM buildings b
    JOIN roads r ON ST_DWithin(b.geom, r.geom, 200);
    
    CREATE INDEX idx_temp_geom ON temp_filter USING GIST(geom);
    ```
    ⚡ **Ultra-rapide** (moins d'une seconde sur 100k+ entités)
  </TabItem>
  <TabItem value="spatialite" label="Backend Spatialite">
    ```sql
    -- Crée une table temporaire avec index R-tree
    CREATE TEMP TABLE filtered_buildings AS
    SELECT b.*
    FROM buildings b
    JOIN roads r ON ST_Distance(b.geom, r.geom) <= 200;
    
    -- Utilise l'index spatial R-tree
    SELECT CreateSpatialIndex('filtered_buildings', 'geom');
    ```
    ✅ **Rapide** (~2-10s sur 50k entités)
  </TabItem>
  <TabItem value="ogr" label="Backend OGR">
    ```python
    # Utilise le framework de traitement QGIS
    processing.run("native:buffer", {
        'INPUT': roads,
        'DISTANCE': 200,
        'OUTPUT': 'memory:'
    })
    
    processing.run("native:selectbylocation", {
        'INPUT': buildings,
        'INTERSECT': buffered_roads,
        'METHOD': 0
    })
    ```
    ⚠️ **Plus lent** (~10-30s sur 50k entités)
  </TabItem>
</Tabs>

### 6. Examiner les Résultats

Après filtrage :

- **Canevas de carte** : Les bâtiments filtrés sont mis en évidence
- **Panneau** : Affiche le nombre d'entités filtrées
- **Table d'attributs** : Ouvrez pour voir les entités filtrées

:::tip Zoomer sur les résultats
Clic droit sur la couche → **Zoomer sur la couche** pour voir toutes les entités filtrées
:::

### 7. Affiner le Filtre (Optionnel)

Voulez-vous ajouter des critères d'attributs ? Combinez avec un filtre d'attributs :

1. Allez dans l'onglet **Filtre d'attributs**
2. Ajoutez une expression comme :
   ```
   "building_type" = 'residential'
   ```
3. Cliquez sur **Appliquer le filtre**

Vous avez maintenant des bâtiments qui sont :
- ✅ À moins de 200m des routes
- ✅ ET sont des bâtiments résidentiels

### 8. Exporter les Résultats (Optionnel)

Pour sauvegarder les bâtiments filtrés :

1. Allez dans l'onglet **Exporter**
2. Choisissez le format de sortie :
   - **GeoPackage** (recommandé pour les flux de travail modernes)
   - **Shapefile** (pour la compatibilité)
   - **PostGIS** (pour enregistrer dans une base de données)
3. Configurez les options :
   - SCR de sortie (par défaut : identique à la source)
   - Emplacement de sortie
4. Cliquez sur **Exporter**

## Ce Que Vous Avez Appris

✅ Comment ouvrir FilterMate et sélectionner une couche  
✅ Comment créer un filtre géométrique avec tampon  
✅ Comprendre la sélection du backend (automatique)  
✅ Comment combiner des filtres d'attributs et géométriques  
✅ Comment exporter les résultats filtrés  

## Prochaines Étapes

Maintenant que vous avez créé votre premier filtre, explorez davantage :

- **[Bases du filtrage](../user-guide/filtering-basics.md)** - Apprenez les expressions QGIS
- **[Filtrage géométrique](../user-guide/geometric-filtering.md)** - Prédicats spatiaux avancés
- **[Opérations de tampon](../user-guide/buffer-operations.md)** - Différents types de tampons
- **[Exporter des entités](../user-guide/export-features.md)** - Options d'exportation avancées

## Problèmes Courants

### Aucune entité retournée ?

Vérifiez :
- ✅ La distance du tampon est appropriée pour votre SCR (mètres vs. degrés)
- ✅ Les couches ont des emprises qui se chevauchent
- ✅ La couche de référence contient des entités

### Le filtre est lent ?

Pour les grands jeux de données :
- Installez le backend PostgreSQL pour une accélération de 10 à 50×
- Voir [Optimisation des performances](../advanced/performance-tuning.md)

### Mauvais SCR ?

FilterMate reprojette automatiquement, mais vous pouvez vérifier :
1. Propriétés de la couche → onglet SCR
2. Assurez-vous que les deux couches ont un SCR valide défini
3. FilterMate s'occupe du reste !
