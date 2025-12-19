---
sidebar_position: 5
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Analyse Immobilière : Filtrage de Marché

Filtrer les propriétés résidentielles par prix, taille et proximité des écoles pour identifier les opportunités d'investissement optimales.

## Aperçu du Scénario

**Objectif** : Trouver des maisons unifamiliales entre 200k-400k$, >150m², à moins de 1 km d'écoles bien notées.

**Application Réelle** :
- Investisseurs immobiliers trouvant des propriétés correspondant aux critères
- Acheteurs recherchant des quartiers adaptés aux familles
- Agents immobiliers fournissant des recommandations basées sur les données
- Analystes de marché évaluant les valeurs immobilières vs. commodités

**Temps Estimé** : 8 minutes

**Difficulté** : ⭐ Débutant

---

## Prérequis

### Données Requises

1. **Couche Propriétés Résidentielles** (points ou polygones)
   - Annonces immobilières ou données de parcelles
   - Attributs requis :
     - `prix` (numérique)
     - `surface_m2` ou `surface_habitable` (numérique)
     - `type_propriete` (texte : 'maison_individuelle', 'appartement', etc.)
   - Optionnel : `chambres`, `salles_bain`, `annee_construction`

2. **Couche Écoles** (points)
   - Emplacements des écoles
   - Optionnel mais utile : `notation`, `niveau_scolaire`, `nom`
   - Couvre votre zone d'étude

### Sources de Données Exemples

**Données Immobilières** :
- Exports MLS (Multiple Listing Service)
- Flux de données Zillow/Trulia (si disponibles)
- Bases de données d'évaluation foncière municipales
- Bâtiments OpenStreetMap avec tags

**Données Écoles** :
```python
# Plugin QuickOSM de QGIS
Clé: "amenity", Valeur: "school"
Clé: "school", Valeur: "*"

# Ou données gouvernementales:
- National Center for Education Statistics (USA)
- Ministère de l'Éducation
- Bases de données des autorités éducatives locales
```

### Recommandation de Backend

**Comparaison Multi-Backend** - Ce flux de travail démontre les trois :
- **PostgreSQL** : Le plus rapide si vous avez >10k propriétés
- **Spatialite** : Bon compromis pour données à l'échelle de la ville
- **OGR** : Fonctionne partout, performances acceptables pour <5k propriétés

---

## Instructions Étape par Étape

### Étape 1 : Charger et Inspecter les Données Immobilières

1. **Charger la couche propriétés** : `proprietes_residentielles.gpkg`
2. **Ouvrir la Table d'Attributs** (F6)
3. **Vérifier que les champs requis existent** :
   ```
   ✓ prix (numérique)
   ✓ surface_m2 (numérique)
   ✓ type_propriete (texte)
   ```

4. **Vérifier la qualité des données** :
   ```
   Trier par prix: Rechercher des valeurs irréalistes (0, NULL, >10M$)
   Trier par surface: Vérifier les valeurs 0 ou NULL
   Filtrer type_propriete: Identifier les catégories valides
   ```

:::tip Nettoyage des Données
Si vous avez des valeurs manquantes :
```sql
-- Filtrer d'ABORD les enregistrements incomplets
"prix" IS NOT NULL 
AND "surface_m2" > 0 
AND "type_propriete" IS NOT NULL
```
:::

### Étape 2 : Appliquer les Filtres d'Attributs de Base

**Utiliser FilterMate** :

1. Ouvrir le panneau FilterMate
2. Sélectionner la couche **proprietes_residentielles**
3. Choisir **n'importe quel backend** (le filtrage par attributs fonctionne également sur tous)
4. Entrer l'expression :

<Tabs>
  <TabItem value="basic" label="Filtre de Base" default>
    ```sql
    -- Prix entre 200k$ et 400k$
    -- Surface supérieure à 150m²
    -- Maisons unifamiliales uniquement
    
    "prix" >= 200000 
    AND "prix" <= 400000
    AND "surface_m2" >= 150
    AND "type_propriete" = 'maison_individuelle'
    ```
  </TabItem>
  
  <TabItem value="advanced" label="Avancé (Types Multiples)">
    ```sql
    -- Accepter plusieurs types de propriétés
    "prix" BETWEEN 200000 AND 400000
    AND "surface_m2" >= 150
    AND "type_propriete" IN ('maison_individuelle', 'maison_ville')
    AND "chambres" >= 3
    ```
  </TabItem>
  
  <TabItem value="deals" label="Orienté Investissement">
    ```sql
    -- Trouver propriétés sous-évaluées (prix par m²)
    "prix" BETWEEN 200000 AND 400000
    AND "surface_m2" >= 150
    AND "type_propriete" = 'maison_individuelle'
    AND ("prix" / "surface_m2") < 2000  -- Moins de 2000$/m²
    ```
  </TabItem>
</Tabs>

5. Cliquer sur **Appliquer le Filtre**
6. Examiner le compte : "Affichage de X sur Y entités"

**Résultat Attendu** : Propriétés réduites par prix, taille et type

### Étape 3 : Ajouter un Filtre Spatial pour la Proximité des Écoles

Maintenant ajouter le critère **basé sur la localisation** :

1. **S'assurer que la couche écoles est chargée** : `ecoles.gpkg`
2. **Modifier l'expression FilterMate** pour ajouter la composante spatiale :

<Tabs>
  <TabItem value="ogr" label="OGR / Spatialite" default>
    ```sql
    -- Combiner filtres d'attributs + proximité spatiale
    "prix" >= 200000 
    AND "prix" <= 400000
    AND "surface_m2" >= 150
    AND "type_propriete" = 'maison_individuelle'
    AND distance(
      $geometry,
      aggregate(
        layer:='ecoles',
        aggregate:='collect',
        expression:=$geometry
      )
    ) <= 1000
    ```
    
    **Alternative utilisant les fonctions overlay** :
    ```sql
    -- Mêmes critères + vérifier qu'une école dans 1km existe
    "prix" BETWEEN 200000 AND 400000
    AND "surface_m2" >= 150
    AND "type_propriete" = 'maison_individuelle'
    AND array_length(
      overlay_within(
        'ecoles',
        buffer($geometry, 1000)
      )
    ) > 0
    ```
  </TabItem>
  
  <TabItem value="postgresql" label="PostgreSQL">
    ```sql
    -- Utilisant les fonctions spatiales PostGIS
    prix >= 200000 
    AND prix <= 400000
    AND surface_m2 >= 150
    AND type_propriete = 'maison_individuelle'
    AND EXISTS (
      SELECT 1 
      FROM ecoles e
      WHERE ST_DWithin(
        proprietes.geom,
        e.geom,
        1000  -- 1km en mètres
      )
    )
    ```
    
    **Ou avec calcul de distance** :
    ```sql
    -- Inclure la distance à l'école la plus proche en sortie
    SELECT 
      p.*,
      MIN(ST_Distance(p.geom, e.geom)) AS distance_ecole
    FROM proprietes p
    JOIN ecoles e ON ST_DWithin(p.geom, e.geom, 1000)
    WHERE prix BETWEEN 200000 AND 400000
      AND surface_m2 >= 150
      AND type_propriete = 'maison_individuelle'
    GROUP BY p.id_propriete
    ```
  </TabItem>
</Tabs>

3. Cliquer sur **Appliquer le Filtre**
4. Examiner les résultats sur la carte (devraient être concentrés près des écoles)

### Étape 4 : Affiner par Qualité de l'École (Optionnel)

Si votre couche écoles a des données de notation :

```sql
-- Seulement propriétés près d'écoles bien notées (notation ≥ 8/10)
"prix" BETWEEN 200000 AND 400000
AND "surface_m2" >= 150
AND "type_propriete" = 'maison_individuelle'
AND array_max(
  array_foreach(
    overlay_within('ecoles', buffer($geometry, 1000)),
    attribute(@element, 'notation')
  )
) >= 8
```

**Ce que cela fait** :
1. Trouve toutes les écoles dans un tampon de 1 km
2. Obtient leurs valeurs de notation
3. Conserve les propriétés où au moins une école proche a une notation ≥8

### Étape 5 : Calculer la Distance à l'École la Plus Proche

Ajouter un champ montrant la distance exacte :

1. **Ouvrir la Calculatrice de Champs** (Ctrl+I) sur la couche filtrée
2. Créer un nouveau champ :
   ```
   Nom du champ: ecole_proche_m
   Type: Décimal (double)
   Précision: 1
   
   Expression:
   round(
     array_min(
       array_foreach(
         overlay_nearest('ecoles', $geometry, limit:=1),
         distance(geometry(@element), $geometry)
       )
     ),
     0
   )
   ```

3. **Ajouter le nom de l'école** (optionnel) :
   ```
   Nom du champ: nom_ecole_proche
   Type: Texte (chaîne)
   
   Expression:
   attribute(
     overlay_nearest('ecoles', $geometry, limit:=1)[0],
     'nom'
   )
   ```

### Étape 6 : Classer les Propriétés par Valeur

Créer un **score de valeur** combinant plusieurs facteurs :

1. **Ouvrir la Calculatrice de Champs**
2. Créer un champ calculé :
   ```
   Nom du champ: score_valeur
   Type: Décimal (double)
   
   Expression:
   -- Score plus élevé = meilleure valeur
   -- Facteurs pondérés:
   (400000 - "prix") / 1000 * 0.4 +          -- Prix plus bas = mieux (40% poids)
   ("surface_m2" - 150) * 0.3 +              -- Plus grande surface = mieux (30% poids)
   (1000 - "ecole_proche_m") * 0.3           -- École plus proche = mieux (30% poids)
   ```

3. **Trier par score_valeur** décroissant pour voir les meilleures affaires en premier

### Étape 7 : Visualiser les Résultats

**Colorer par Distance à l'École** :

1. Clic droit sur la couche → **Symbologie**
2. Choisir **Gradué**
3. Valeur : `ecole_proche_m`
4. Méthode : Ruptures Naturelles
5. Couleurs : Vert (proche) → Jaune → Rouge (loin)

**Ajouter des Étiquettes** :
```
Étiqueter avec: concat('$', "prix"/1000, 'k - ', round("ecole_proche_m",0), 'm école')
Taille: 10pt
Tampon: Blanc, 1mm
```

### Étape 8 : Exporter les Correspondances pour Analyse

1. **Dans FilterMate** : Cliquer sur **Exporter les Entités Filtrées**
   ```
   Format: GeoPackage
   Nom de fichier: proprietes_cibles_investissement.gpkg
   SCR: WGS84 (pour portabilité)
   Inclure tous les attributs: ✓
   ```

2. **Exporter la table d'attributs comme tableur** :
   ```
   Clic droit sur la couche → Exporter → Sauvegarder les Entités Sous
   Format: CSV ou XLSX
   Champs: Sélectionner seulement les colonnes pertinentes
   ```

3. **Créer un rapport simple** (optionnel) :
   ```python
   # Console Python
   layer = iface.activeLayer()
   features = list(layer.getFeatures())
   
   print("=== Rapport d'Investissement Immobilier ===")
   print(f"Propriétés correspondantes: {len(features)}")
   print(f"Prix moyen: ${sum(f['prix'] for f in features)/len(features):,.0f}")
   print(f"Surface moyenne: {sum(f['surface_m2'] for f in features)/len(features):.0f} m²")
   print(f"Distance moyenne à l'école: {sum(f['ecole_proche_m'] for f in features)/len(features):.0f} m")
   print(f"Fourchette de prix: ${min(f['prix'] for f in features):,} - ${max(f['prix'] for f in features):,}")
   ```

---

## Comprendre les Résultats

### Ce Que Montre le Filtre

✅ **Propriétés sélectionnées** : Correspondent à TOUS les critères :
- Prix : 200 000$ - 400 000$
- Taille : ≥150m²
- Type : Maison unifamiliale
- Localisation : ≤1km d'une école

❌ **Propriétés exclues** : Échouent à N'IMPORTE QUEL critère ci-dessus

### Interpréter les Correspondances de Propriétés

**Score de Valeur Élevé** (>500) :
- Prix inférieur au marché pour la zone
- Bonne taille pour le prix
- Très proche d'une école (attrait familial)
- **Action** : Visite/offre prioritaire

**Score Moyen** (250-500) :
- Juste valeur marchande
- Localisation acceptable
- Considérer autres facteurs (état, quartier)
- **Action** : Comparer avec propriétés similaires

**Score Faible** (<250) :
- Peut être surévalué
- Extrémité lointaine de proximité d'école
- Taille plus petite pour le prix
- **Action** : Négocier ou attendre de meilleures options

### Contrôles de Qualité

1. **Vérification de cohérence** : Voir 5-10 résultats aléatoires
   - Vérifier que les prix sont réalistes
   - Mesurer la distance d'école manuellement
   - Vérifier que type_propriete correspond aux attentes

2. **Détection de valeurs aberrantes** :
   ```sql
   -- Trouver propriétés anormalement bon marché (peuvent être erreurs ou bonnes affaires)
   "prix" / "surface_m2" < 1500  -- Moins de 1500$/m²
   ```

3. **Modèles cartographiques** : Les résultats devraient se regrouper près des écoles (sinon, vérifier SCR)

---

## Meilleures Pratiques

### Affinage de Stratégie de Recherche

**Commencer Large, Affiner Graduellement** :

1. **Premier passage** : Appliquer seulement filtres prix + taille
2. **Examiner le compte** : Si >100 résultats, ajouter filtre type_propriete
3. **Ajouter spatial** : Appliquer proximité école
4. **Ajustement fin** : Ajouter notation école, chambres, etc.

**Sauvegarder l'Historique de Filtre** :
- FilterMate sauvegarde automatiquement vos expressions
- Utiliser le panneau **Historique de Filtre** pour comparer différents ensembles de critères
- Sauvegarder les meilleurs filtres comme **Favoris**

### Considérations de Performance

**Guide de Sélection du Backend** :

```
Propriétés | Écoles | Backend Recommandé
-----------|--------|-------------------
< 1 000    | Tout   | OGR (plus simple)
1k - 10k   | < 100  | Spatialite
> 10k      | Tout   | PostgreSQL
Tout       | > 500  | PostgreSQL + index spatial
```

**Astuces d'Optimisation** :

1. **Appliquer d'abord les filtres d'attributs** (moins coûteux) :
   ```sql
   -- Bon: Attributs d'abord, spatial en dernier
   "prix" BETWEEN 200000 AND 400000 AND distance(...) <= 1000
   
   -- Mauvais: Spatial d'abord (plus lent)
   distance(...) <= 1000 AND "prix" BETWEEN 200000 AND 400000
   ```

2. **Utiliser un index spatial** (automatique dans PostgreSQL, créer manuellement pour Spatialite) :
   ```
   Propriétés de la Couche → Créer un Index Spatial
   ```

3. **Simplifier la géométrie des écoles** si complexe :
   ```
   Vecteur → Géométrie → Centroïdes (écoles → points)
   ```

### Meilleures Pratiques Immobilières

**Analyse de Marché** :
- Exécuter ce filtre hebdomadairement pour suivre les nouvelles annonces
- Comparer les tendances de score_valeur au fil du temps
- Exporter les résultats avec horodatages pour analyse historique

**Ajustement de Prix** :
```sql
-- Ajuster pour inflation ou changements de marché
"prix" * 1.05 BETWEEN 200000 AND 400000  -- +5% croissance du marché
```

**Modèles Saisonniers** :
```sql
-- Proximité école plus précieuse au printemps (saison de déménagement familial)
-- Ajuster le poids dans le calcul de score_valeur
```

---

## Problèmes Courants

### Problème 1 : Aucun résultat ou très peu de résultats

**Cause** : Critères trop stricts ou problèmes de qualité des données

**Solutions** :
```
1. Assouplir la fourchette de prix: 150k-500k au lieu de 200k-400k
2. Réduire la surface minimale: 120m² au lieu de 150m²
3. Augmenter la distance école: 2000m au lieu de 1000m
4. Vérifier les valeurs NULL dans les attributs
5. Vérifier que la couche écoles couvre la même zone que les propriétés
```

### Problème 2 : Le calcul de distance retourne des erreurs

**Cause** : Incompatibilité de SCR ou couche introuvable

**Solution** :
```
1. Vérifier que le nom de la couche écoles correspond exactement (sensible à la casse)
2. Vérifier que les deux couches utilisent le même SCR (reprojeter si nécessaire)
3. S'assurer que la couche écoles est dans le projet actuel
4. Essayer l'approche aggregate plus simple:
   
   distance(
     $geometry,
     aggregate('ecoles', 'collect', $geometry)
   ) <= 1000
```

### Problème 3 : Performances lentes (>30 secondes)

**Cause** : Grand jeu de données ou requête spatiale complexe

**Solutions** :
```
1. Passer au backend PostgreSQL (accélération majeure)
2. Créer un index spatial sur les deux couches
3. Pré-filtrer les propriétés à une région plus petite:
   "ville" = 'Paris' AND [reste de l'expression]
4. Réduire la complexité de la requête école:
   - Utiliser buffer une fois: overlay_within('ecoles', buffer($geometry, 1000))
   - Mettre en cache dans un champ temporaire
```

### Problème 4 : Les résultats ne sont pas près des écoles visuellement

**Cause** : SCR utilisant des degrés au lieu de mètres

**Solution** :
```
1. Vérifier le SCR de la couche: Propriétés → Information
2. Si EPSG:4326 (lat/lon), reprojeter vers UTM local:
   Vecteur → Gestion de Données → Reprojeter une Couche
3. Mettre à jour la distance de 1000 à 0.01 si utilisation de degrés (non recommandé)
```

---

## Prochaines Étapes

### Flux de Travail Associés

- **[Planification Urbaine Transport](./urban-planning-transit)** : Analyse de proximité similaire
- **[Services d'Urgence](./emergency-services)** : Requêtes de distance inverse
- **[Planification des Transports](./transportation-planning)** : Gestion d'export et de SCR

### Techniques Avancées

**1. Score Multi-Commodités** (écoles + parcs + commerces) :
```sql
-- Propriétés près de multiples commodités
array_length(overlay_within('ecoles', buffer($geometry, 1000))) > 0
AND array_length(overlay_within('parcs', buffer($geometry, 500))) > 0
AND array_length(overlay_within('commerces', buffer($geometry, 800))) > 0
```

**2. Potentiel d'Appréciation** (combiner démographie) :
```sql
-- Zones avec démographie en amélioration
"revenu_median_2023" > "revenu_median_2020" * 1.1  -- 10% croissance revenu
AND distance(centroide, aggregate('nouveaux_developpements', 'collect', $geometry)) < 2000
```

**3. Analyse Temps de Trajet** (nécessite réseau routier) :
```
Traitement → Analyse de Réseau → Zone de Service
Origine: Propriétés
Destination: Centres d'emploi
Limite de temps: 30 minutes
```

**4. Comparaison de Marché** (prix par m² par quartier) :
```sql
-- Trouver propriétés sous la moyenne du quartier
"prix" / "surface_m2" < 
  aggregate(
    layer:='toutes_proprietes',
    aggregate:='avg',
    expression:="prix"/"surface_m2",
    filter:="quartier" = attribute(@parent, 'quartier')
  ) * 0.9  -- 10% sous la moyenne
```

**5. Suivi Temporel** (surveiller la durée d'inscription) :
```sql
-- Propriétés sur le marché >30 jours (vendeurs motivés)
"jours_marche" > 30
AND "prix_reduit" = 1
```

### Pour Aller Plus Loin

- 📖 [Référence des Prédicats Spatiaux](../reference/cheat-sheets/spatial-predicates)
- 📖 [Bases du Filtrage](../user-guide/filtering-basics)
- 📖 [Historique de Filtre & Favoris](../user-guide/filter-history)
- 📖 [Plongée Profonde Calculatrice de Champs](https://docs.qgis.org/latest/fr/docs/user_manual/working_with_vector/attribute_table.html#using-the-field-calculator)

---

## Résumé

✅ **Vous avez appris** :
- Combiner filtres d'attributs et spatiaux
- Calculs de distance aux entités les plus proches
- Créer des scores de valeur à partir de critères multiples
- Exporter des résultats filtrés pour analyse
- Gérer l'historique de filtre pour différentes recherches

✅ **Techniques clés** :
- Opérateur `BETWEEN` pour filtrage par plage
- Fonction `distance()` pour proximité
- `overlay_within()` pour relations spatiales
- Calculatrice de champs pour attributs dérivés
- Comparaison multi-backend

🎯 **Impact réel** : Ce flux de travail aide les professionnels de l'immobilier à prendre des décisions basées sur les données, les investisseurs à identifier rapidement les opportunités, et les acheteurs à trouver des propriétés correspondant à des critères complexes qui prendraient des jours à rechercher manuellement.

💡 **Astuce pro** : Sauvegardez plusieurs variantes de filtre comme **Favoris** avec des noms descriptifs comme "Investissement: Maisons Familiales Près Écoles" ou "Budget: Maisons Starter Accès Transport" pour recréer instantanément les recherches.
