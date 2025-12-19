---
sidebar_position: 4
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Services d'Urgence : Analyse de Couverture

Identifier les zones manquant de couverture adéquate des services d'urgence pour optimiser l'emplacement des installations et la planification des réponses.

## Aperçu du Scénario

**Objectif** : Trouver les zones résidentielles à plus de 5 km de la caserne de pompiers la plus proche pour identifier les lacunes de couverture.

**Application Réelle** :
- Services d'incendie optimisant l'emplacement des casernes
- Gestion des urgences planifiant les temps de réponse
- Urbanistes évaluant l'équité des services
- Compagnies d'assurance évaluant les zones à risque

**Temps Estimé** : 12 minutes

**Difficulté** : ⭐⭐ Intermédiaire

---

## Prérequis

### Données Requises

1. **Couche Casernes de Pompiers** (points)
   - Emplacements des installations de services d'urgence
   - Doit inclure les noms/ID des casernes
   - Couvre votre zone d'étude

2. **Couche Zones de Population** (polygones)
   - Îlots de recensement, quartiers ou zones postales
   - Attribut de comptage de population (optionnel mais utile)
   - Zones d'occupation résidentielle

3. **Optionnel : Réseau Routier**
   - Pour l'analyse de temps de trajet (avancé)
   - Topologie de réseau pour le routage

### Sources de Données Exemples

**Option 1 : OpenStreetMap**
```python
# Utiliser le plugin QGIS QuickOSM

# Pour les casernes de pompiers:
Clé: "amenity", Valeur: "fire_station"

# Pour les zones résidentielles:
Clé: "landuse", Valeur: "residential"
Clé: "place", Valeur: "neighbourhood"
```

**Option 2 : Données Gouvernementales Ouvertes**
- Bases de données municipales de services d'urgence
- Fichiers de limites de recensement avec population
- HIFLD (Homeland Infrastructure Foundation-Level Data)
- Portails locaux de données SIG

### Recommandation de Backend

**OGR** - Meilleur choix pour ce flux de travail :
- Compatibilité universelle de formats (Shapefiles, GeoJSON, GeoPackage)
- Aucune configuration complexe requise
- Bon pour les jeux de données <10 000 entités
- Fonctionne avec toute installation QGIS

---

## Instructions Étape par Étape

### Étape 1 : Charger et Préparer les Données

1. **Charger les couches** dans QGIS :
   - `casernes_pompiers.gpkg` (ou .shp, .geojson)
   - `zones_residentielles.gpkg`

2. **Vérifier le SCR** :
   ```
   Les deux couches doivent utiliser le même système de coordonnées projeté
   Clic droit → Propriétés → Information → SCR
   
   Recommandé: Zone UTM locale ou grille nationale/régionale
   Exemple: EPSG:32633 (UTM Zone 33N)
   ```

3. **Inspecter les données** :
   - Compter les casernes : Devrait en avoir au moins 3-5 pour une analyse significative
   - Vérifier les zones résidentielles : Rechercher des attributs de population ou nombre de ménages
   - Vérifier la couverture : Les casernes doivent être réparties sur la zone d'étude

:::tip Trouver Votre Zone UTM
Utilisez [epsg.io](https://epsg.io/) et cliquez sur la carte pour trouver la zone UTM appropriée pour votre région.
:::

### Étape 2 : Créer des Zones de Service de 5 km Autour des Casernes

**Utiliser FilterMate** :

1. Ouvrir FilterMate, sélectionner la couche **casernes_pompiers**
2. Entrer l'expression :
   ```sql
   -- Garder toutes les casernes
   1 = 1
   ```
3. Activer l'opération **Tampon** :
   - Distance : `5000` mètres
   - Type : Positif (expansion)
   - Segments : 16 (pour des cercles lisses)
4. **Appliquer le Filtre**
5. **Exporter** comme `couverture_pompiers_5km.gpkg`

**Résultat** : Tampons circulaires de 5 km autour de chaque caserne (zones de couverture de service)

### Étape 3 : Identifier les Zones Résidentielles Sous-Desservies (Requête Inverse)

C'est l'étape clé - trouver les zones **NON** dans les 5 km de toute caserne :

<Tabs>
  <TabItem value="ogr" label="OGR / Spatialite" default>
    **Méthode 1 : Utiliser FilterMate (Recommandé)**
    
    1. Sélectionner la couche **zones_residentielles**
    2. Choisir le backend **OGR**
    3. Entrer l'expression :
    ```sql
    -- Zones résidentielles N'intersectant PAS la couverture pompiers
    NOT intersects(
      $geometry,
      aggregate(
        layer:='couverture_pompiers_5km',
        aggregate:='collect',
        expression:=$geometry
      )
    )
    ```
    
    **Méthode 2 : Utiliser le prédicat disjoint()**
    ```sql
    -- Zones complètement en dehors de toutes les zones de couverture
    disjoint(
      $geometry,
      aggregate('couverture_pompiers_5km', 'collect', $geometry)
    )
    ```
  </TabItem>
  
  <TabItem value="postgresql" label="PostgreSQL (Avancé)">
    ```sql
    -- Zones résidentielles sans caserne proche
    NOT EXISTS (
      SELECT 1
      FROM casernes_pompiers cp
      WHERE ST_DWithin(
        zones_residentielles.geom,
        cp.geom,
        5000  -- Seuil de 5km
      )
    )
    ```
    
    **Ou utilisant une jointure spatiale** :
    ```sql
    SELECT zr.*
    FROM zones_residentielles zr
    LEFT JOIN casernes_pompiers cp
      ON ST_DWithin(zr.geom, cp.geom, 5000)
    WHERE cp.id_caserne IS NULL  -- Aucune caserne correspondante trouvée
    ```
  </TabItem>
</Tabs>

4. Cliquer sur **Appliquer le Filtre**
5. Examiner la carte - les zones rouges/surlignées montrent les lacunes de couverture

### Étape 4 : Calculer la Distance Exacte à la Caserne la Plus Proche

Ajouter un champ montrant à quelle distance chaque zone sous-desservie se trouve de la caserne la plus proche :

1. Ouvrir la **Table d'Attributs** (F6) de la couche filtrée
2. **Ouvrir la Calculatrice de Champs**
3. Créer un nouveau champ :
   ```
   Nom du champ: distance_caserne_proche
   Type: Décimal (double)
   Précision: 2
   
   Expression:
   array_min(
     array_foreach(
       overlay_nearest('casernes_pompiers', $geometry, limit:=5),
       distance(geometry(@element), $geometry)
     )
   ) / 1000  -- Convertir mètres en kilomètres
   ```

**Résultat** : Chaque zone résidentielle montre maintenant la distance à la caserne la plus proche

### Étape 5 : Prioriser par Population à Risque

Si votre couche résidentielle a des données de population :

1. **Calculer la population totale** dans les zones sous-desservies :
   ```sql
   -- Dans le filtre d'expression ou la calculatrice de champs
   "population" > 0
   ```

2. **Trier par priorité** :
   ```
   Table d'Attributs → Cliquer sur l'en-tête de colonne "population"
   → Trier en ordre décroissant
   ```

3. **Créer des catégories de priorité** :
   ```sql
   CASE
     WHEN "distance_caserne_proche" > 10 THEN 'Critique (>10km)'
     WHEN "distance_caserne_proche" > 7 THEN 'Priorité Haute (7-10km)'
     WHEN "distance_caserne_proche" > 5 THEN 'Priorité Moyenne (5-7km)'
     ELSE 'Acceptable (<5km)'
   END
   ```

### Étape 6 : Visualiser les Lacunes de Couverture

**Configuration de la Symbologie** :

1. Clic droit sur **zones_residentielles** → Symbologie
2. Choisir **Gradué**
3. Valeur : `distance_caserne_proche`
4. Méthode : Ruptures Naturelles (Jenks)
5. Classes : 5
6. Rampe de couleurs : Rouge (loin) → Jaune → Vert (proche)
7. Appliquer

**Ajouter des Étiquettes** (optionnel) :
```
Étiqueter avec: concat("nom", ' - ', round("distance_caserne_proche", 1), ' km')
Taille: Basée sur "population" (plus grand = plus de personnes affectées)
```

### Étape 7 : Exporter les Résultats et Générer un Rapport

1. **Exporter les zones sous-desservies** :
   ```
   FilterMate → Exporter les Entités Filtrées
   Format: GeoPackage
   Nom de fichier: zones_residentielles_sous_desservies.gpkg
   SCR: WGS84 (pour partage) ou garder SCR du projet
   ```

2. **Générer des statistiques récapitulatives** :
   ```
   Vecteur → Outils d'Analyse → Statistiques de Base
   Entrée: zones_residentielles_sous_desservies
   Champ: population
   ```

3. **Créer un rapport récapitulatif** (Console Python - optionnel) :
   ```python
   layer = iface.activeLayer()
   features = list(layer.getFeatures())
   
   total_zones = len(features)
   total_population = sum(f['population'] for f in features if f['population'])
   distance_moy = sum(f['distance_caserne_proche'] for f in features) / total_zones
   distance_max = max(f['distance_caserne_proche'] for f in features)
   
   print(f"=== Analyse des Lacunes de Couverture Services d'Urgence ===")
   print(f"Zones résidentielles sous-desservies: {total_zones}")
   print(f"Population affectée: {total_population:,}")
   print(f"Distance moyenne à la caserne la plus proche: {distance_moy:.1f} km")
   print(f"Distance maximale: {distance_max:.1f} km")
   ```

---

## Comprendre les Résultats

### Ce Que Montre le Filtre

✅ **Zones sélectionnées** : Zones résidentielles >5 km de TOUTE caserne de pompiers

❌ **Zones exclues** : Zones résidentielles dans le rayon de service de 5 km

### Interpréter les Lacunes de Couverture

**Lacunes Critiques (>10km)** :
- Le temps de réponse dépasse probablement les normes nationales (ex : NFPA 1710 : 8 minutes)
- Priorité élevée pour l'emplacement d'une nouvelle caserne
- Envisager des casernes temporaires ou de volontaires
- Peut nécessiter des accords d'entraide avec juridictions voisines

**Priorité Haute (7-10km)** :
- Temps de réponse limite acceptable
- Devrait être traité dans le prochain cycle de planification
- Envisager casernes mobiles/saisonnières
- Évaluer la qualité du réseau routier (temps de trajet peut être plus long)

**Priorité Moyenne (5-7km)** :
- Techniquement sous-desservi selon normes strictes
- Faible urgence si densité de population est faible
- Surveiller pour croissance future
- Peut être acceptable pour zones rurales

### Contrôles de Validation

1. **Vérification visuelle ponctuelle** : Utiliser l'outil de Mesure QGIS pour vérifier les distances
2. **Cas limites** : Les zones juste en dehors de 5 km peuvent s'arrondir différemment
3. **Précision de population** : Vérifier que la somme correspond aux totaux de recensement connus
4. **Validité de géométrie** : Rechercher des éclats ou polygones invalides

---

## Meilleures Pratiques

### Normes de Couverture

**Recommandations NFPA 1710 (USA)** :
- Zones urbaines : 1.5 mile (2,4 km) distance de trajet
- Zones rurales : Jusqu'à 5 miles (8 km) acceptable
- Objectif de temps de réponse : 8 minutes de l'appel à l'arrivée

**Ajuster le seuil** selon votre région :
```
Zones urbaines:    2-3 km
Zones suburbaines: 5 km (comme dans ce tutoriel)
Zones rurales:     8-10 km
```

### Optimisation des Performances

**Pour les grands jeux de données** :

1. **Simplifier la géométrie des zones résidentielles** :
   ```
   Vecteur → Géométrie → Simplifier
   Tolérance: 50 mètres (maintient la précision de couverture)
   ```

2. **Pré-filtrer uniquement aux zones peuplées** :
   ```sql
   "population" > 0 OR "occupation" = 'residential'
   ```

3. **Utiliser un index spatial** (OGR crée automatiquement pour GeoPackage)

4. **Guide de sélection du backend** :
   ```
   < 1 000 zones:    OGR (suffisant)
   1k - 50k:         Spatialite
   > 50k:            PostgreSQL
   ```

### Ajustements Réels

**Considérer la réalité du réseau routier** :
- 5 km en ligne droite peut être 8 km par route
- Montagnes/rivières peuvent bloquer l'accès direct
- Utiliser l'analyse de réseau pour le temps de trajet (avancé)

**Alternative d'Analyse de Réseau** (intégré QGIS) :
```
Traitement → Analyse de Réseau → Zone de Service (depuis une couche)
Entrée: casernes_pompiers
Coût de trajet: 5000 mètres OU 10 minutes
Crée des polygones de temps de trajet au lieu de cercles
```

### Considérations de Qualité des Données

1. **Précision des casernes** :
   - Vérifier que les casernes sont opérationnelles (pas désaffectées)
   - Vérifier si les casernes de volontaires devraient avoir un rayon plus petit
   - Considérer les casernes spécialisées (aéroport, industriel)

2. **Qualité des zones résidentielles** :
   - Retirer parcs, zones industrielles mal classées comme résidentielles
   - Mettre à jour avec données de recensement récentes
   - Tenir compte des nouveaux développements

3. **Importance du SCR** :
   - Les calculs de distance nécessitent un SCR projeté
   - Géographique (lat/lon) donnera des résultats incorrects
   - Toujours reprojeter si nécessaire avant l'analyse

---

## Problèmes Courants

### Problème 1 : Toutes les zones résidentielles sélectionnées (ou aucune)

**Cause** : Incompatibilité de SCR ou tampon non créé correctement

**Solution** :
```
1. Vérifier que la couche couverture_pompiers_5km existe et a des entités
2. Vérifier que les deux couches sont dans le même SCR
3. Re-créer les tampons avec l'unité de distance correcte (mètres)
4. Vérifier que le nom de la couche tampon correspond exactement à l'expression
```

### Problème 2 : Le calcul de distance retourne NULL ou erreurs

**Cause** : overlay_nearest() ne trouve pas la couche casernes_pompiers

**Solution** :
```
1. S'assurer que la couche casernes_pompiers est chargée dans le projet
2. Vérifier que le nom de la couche correspond exactement (sensible à la casse)
3. Alternative: Utiliser aggregate() avec distance minimale:

distance(
  $geometry,
  aggregate('casernes_pompiers', 'collect', $geometry)
)
```

### Problème 3 : Les résultats montrent des motifs inattendus

**Cause** : Problèmes de qualité de données ou de projection

**Dépannage** :
```
1. Zoomer sur un résultat spécifique et mesurer la distance manuellement
2. Vérifier les polygones résidentiels qui se chevauchent
3. Vérifier que casernes_pompiers couvrent réellement la zone
4. Rechercher des géométries invalides:
   Vecteur → Outils de Géométrie → Vérifier la Validité
```

### Problème 4 : Performances très lentes

**Cause** : Grandes géométries ou zones résidentielles complexes

**Solutions** :
```
1. Simplifier la géométrie résidentielle (tolérance 50-100m)
2. Créer un index spatial sur les deux couches
3. Traiter par districts administratifs séparément
4. Utiliser le backend PostgreSQL pour >10k entités
```

---

## Prochaines Étapes

### Flux de Travail Associés

- **[Planification Urbaine Transport](./urban-planning-transit)** : Motif d'analyse de tampon similaire
- **[Protection Environnementale](./environmental-protection)** : Requêtes spatiales inverses
- **[Analyse Immobilière](./real-estate-analysis)** : Filtrage multi-critères

### Techniques Avancées

**1. Couverture Multi-Casernes** (zones desservies par ≥2 casernes) :
```sql
-- Compter les zones de couverture qui se chevauchent
array_length(
  overlay_intersects('couverture_pompiers_5km', $geometry)
) >= 2
```

**2. Score de Priorité** (distance + population) :
```sql
-- Score plus élevé = priorité plus élevée pour nouvelle caserne
("distance_caserne_proche" - 5) * "population" / 1000
```

**3. Emplacement Optimal Nouvelle Caserne** :
```
1. Exporter zones sous-desservies avec population
2. Trouver centroïde pondéré par population:
   Traitement → Géométrie Vectorielle → Centroïdes
3. Analyse manuelle: Placer nouvelle caserne au centroïde de priorité la plus élevée
```

**4. Modélisation du Temps de Réponse** (avancé) :
```python
# Nécessite réseau routier et routage
# Utilise outils d'Analyse de Réseau QGIS
# Modélise temps de trajet réel vs. distance en ligne droite
# Tient compte limites de vitesse et restrictions de virage
```

**5. Analyse Temporelle** (croissance future) :
```sql
-- Si vous avez des données de projection de population
("population_2030" - "population_2024") / "population_2024" > 0.2
-- Zones attendant >20% de croissance
```

### Pour Aller Plus Loin

- 📖 [Référence des Prédicats Spatiaux](../reference/cheat-sheets/spatial-predicates)
- 📖 [Opérations de Tampon](../user-guide/buffer-operations)
- 📖 [Analyse de Réseau dans QGIS](https://docs.qgis.org/latest/fr/docs/user_manual/processing_algs/qgis/networkanalysis.html)
- 📖 [Ajustement des Performances](../advanced/performance-tuning)

---

## Résumé

✅ **Vous avez appris** :
- Créer des tampons de zone de service autour des installations
- Filtrage spatial inverse (NOT intersects)
- Calculs de distance à l'entité la plus proche
- Analyse de priorité pondérée par la population
- Export de résultats pour rapports de planification

✅ **Techniques clés** :
- `NOT intersects()` pour analyse de lacunes de couverture
- `overlay_nearest()` pour calculs de distance
- `aggregate()` avec prédicats spatiaux
- Score de priorité avec données d'attribut + spatiales

🎯 **Impact réel** : Ce flux de travail aide les agences de gestion des urgences à identifier les lacunes de service, optimiser l'allocation des ressources, améliorer les temps de réponse et assurer une couverture équitable des services d'urgence dans les communautés.

💡 **Astuce pro** : Exécutez cette analyse annuellement avec les données de recensement mises à jour pour suivre les changements de couverture à mesure que les populations évoluent et ajustez l'emplacement des casernes en conséquence.
