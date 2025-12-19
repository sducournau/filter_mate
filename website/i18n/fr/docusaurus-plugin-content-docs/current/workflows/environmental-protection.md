---
sidebar_position: 3
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Analyse Environnementale : Impact des Zones Protégées

Trouver les sites industriels dans les zones tampons d'eau protégées pour évaluer la conformité et les risques environnementaux.

## Aperçu du Scénario

**Objectif** : Identifier les installations industrielles qui se trouvent dans des zones tampons de 1 km autour des plans d'eau protégés pour évaluer l'impact environnemental.

**Application Réelle** :
- Agences environnementales surveillant la conformité
- ONG évaluant les risques de pollution industrielle
- Décideurs politiques créant des réglementations sur les zones tampons
- Urbanistes gérant le zonage industriel

**Temps Estimé** : 15 minutes

**Difficulté** : ⭐⭐⭐ Avancé

---

## Prérequis

### Données Requises

1. **Couche Sites Industriels** (points ou polygones)
   - Emplacements des installations industrielles
   - Doit inclure le type/classification de l'installation
   - Minimum 50+ sites pour une analyse significative

2. **Couche Plans d'Eau** (polygones)
   - Rivières, lacs, zones humides, réservoirs
   - Attribut de statut protégé (optionnel mais utile)
   - Couvre votre zone d'étude

3. **Zones Protégées** (optionnel)
   - Zones de protection environnementale existantes
   - Limites des tampons réglementaires

### Sources de Données Exemples

**Option 1 : OpenStreetMap**
```python
# Utiliser le plugin QGIS QuickOSM
# Pour les plans d'eau:
Clé: "natural", Valeur: "water"
Clé: "waterway", Valeur: "river"

# Pour les sites industriels:
Clé: "landuse", Valeur: "industrial"
Clé: "industrial", Valeur: "*"
```

**Option 2 : Données Gouvernementales**
- Bases de données de l'Agence de Protection de l'Environnement (EPA)
- Bases de données nationales de qualité de l'eau
- Registres des installations industrielles
- Limites des zones protégées (WDPA)

### Recommandation de Backend

**Spatialite** - Meilleur choix pour ce flux de travail :
- Bonnes performances pour les jeux de données régionaux (typiquement <100k entités)
- Opérations de tampon robustes
- Bonnes capacités de réparation de géométrie
- Aucune configuration de serveur requise

---

## Instructions Étape par Étape

### Étape 1 : Charger et Inspecter les Données

1. **Charger les deux couches** dans QGIS :
   - `plans_eau.gpkg` ou `rivieres_lacs.shp`
   - `sites_industriels.gpkg` ou `usines.shp`

2. **Vérifier la compatibilité du SCR** :
   ```
   Clic droit sur la couche → Propriétés → Information
   Vérifier que les deux utilisent le même SCR projeté (ex : UTM, Lambert)
   ```

3. **Vérifier la validité de la géométrie** :
   ```
   Vecteur → Outils de Géométrie → Vérifier la Validité
   Exécuter sur les deux couches
   ```

:::warning Exigences du SCR
Les opérations de tampon nécessitent un **système de coordonnées projeté** (mètres/pieds), pas géographique (lat/lon). Si vos données sont en EPSG:4326, reprojetez d'abord :

```
Vecteur → Outils de Gestion de Données → Reprojeter une Couche
SCR Cible: Choisir la zone UTM appropriée ou projection locale
```
:::

### Étape 2 : Créer un Tampon de 1 km Autour des Plans d'Eau

**Option A : Utiliser FilterMate (Recommandé)**

1. Ouvrir le panneau FilterMate
2. Sélectionner la couche **plans_eau**
3. Entrer l'expression de filtre :
   ```sql
   -- Garder tous les plans d'eau, préparer pour le tampon
   1 = 1
   ```
4. Activer **Modification de Géométrie** → **Tampon**
5. Définir **Distance du Tampon** : `1000` (mètres)
6. **Type de Tampon** : `Positif (expansion)`
7. Cliquer sur **Appliquer le Filtre**
8. **Exporter le Résultat** comme `tampons_eau_1km.gpkg`

**Option B : Utiliser les Outils Natifs QGIS**

```
Vecteur → Outils de Géotraitement → Tampon
Distance: 1000 mètres
Segments: 16 (courbes lisses)
Enregistrer sous: tampons_eau_1km.gpkg
```

### Étape 3 : Filtrer les Sites Industriels dans les Zones Tampons

Maintenant l'opération FilterMate principale :

1. **Sélectionner la couche sites_industriels** dans FilterMate
2. **Choisir le Backend** : Spatialite (ou PostgreSQL si disponible)
3. Entrer l'**expression de filtre spatial** :

<Tabs>
  <TabItem value="spatialite" label="Spatialite / OGR" default>
    ```sql
    -- Sites industriels intersectant les tampons d'eau de 1km
    intersects(
      $geometry,
      geometry(get_feature('tampons_eau_1km', 'fid', fid))
    )
    ```
    
    **Alternative utilisant la référence de couche** :
    ```sql
    -- Plus efficace si la couche tampon est déjà chargée
    intersects(
      $geometry,
      aggregate(
        layer:='tampons_eau_1km',
        aggregate:='collect',
        expression:=$geometry
      )
    )
    ```
  </TabItem>
  
  <TabItem value="postgresql" label="PostgreSQL (Avancé)">
    ```sql
    -- Approche PostGIS plus efficace avec tampon direct
    ST_DWithin(
      sites.geom,
      eau.geom,
      1000  -- Tampon de 1km appliqué à la volée
    )
    WHERE eau.statut_protege = true
    ```
    
    **Approche complète avec vue matérialisée** :
    ```sql
    -- Crée une table temporaire optimisée
    CREATE MATERIALIZED VIEW risque_industriel AS
    SELECT 
      s.*,
      e.nom AS plan_eau_proche,
      ST_Distance(s.geom, e.geom) AS distance_metres
    FROM sites_industriels s
    JOIN plans_eau e ON ST_DWithin(s.geom, e.geom, 1000)
    ORDER BY distance_metres;
    ```
  </TabItem>
</Tabs>

4. Cliquer sur **Appliquer le Filtre**
5. Examiner les résultats sur le canevas (les entités doivent être surlignées)

### Étape 4 : Ajouter des Calculs de Distance (Optionnel)

Pour voir **à quelle distance** chaque site industriel se trouve des zones protégées :

1. Ouvrir la **Calculatrice de Champs** (F6)
2. Créer un nouveau champ :
   ```
   Nom du champ: distance_eau
   Type de champ: Décimal (double)
   
   Expression:
   distance(
     $geometry,
     aggregate(
       'tampons_eau_1km',
       'collect',
       $geometry
     )
   )
   ```
3. Les entités à l'intérieur du tampon afficheront `0` ou de petites valeurs

### Étape 5 : Catégoriser par Niveau de Risque

Créer des catégories visuelles basées sur la proximité :

1. **Clic droit sur la couche filtrée** → Propriétés → Symbologie
2. Choisir **Catégorisé**
3. Utiliser l'expression :
   ```python
   CASE
     WHEN "distance_eau" = 0 THEN 'Risque Élevé (Dans le Tampon)'
     WHEN "distance_eau" <= 500 THEN 'Risque Moyen (0-500m)'
     WHEN "distance_eau" <= 1000 THEN 'Risque Faible (500-1000m)'
     ELSE 'Pas de Risque (Hors Tampon)'
   END
   ```
4. Appliquer un schéma de couleurs (rouge → jaune → vert)

### Étape 6 : Exporter les Résultats

1. Dans FilterMate, **Exporter les Entités Filtrées** :
   ```
   Format: GeoPackage
   Nom de fichier: sites_industriels_risque_environnemental.gpkg
   Inclure les attributs: ✓ Tous les champs
   SCR: Garder l'original ou choisir standard (ex : WGS84 pour partage)
   ```

2. **Générer un rapport** (optionnel) :
   ```python
   # Dans la Console Python (étape avancée optionnelle)
   layer = iface.activeLayer()
   total = layer.featureCount()
   risque_eleve = sum(1 for f in layer.getFeatures() if f['distance_eau'] == 0)
   
   print(f"Total sites industriels dans le tampon: {total}")
   print(f"Risque élevé (directement dans tampon eau): {risque_eleve}")
   print(f"Pourcentage à risque: {(risque_eleve/total)*100:.1f}%")
   ```

---

## Comprendre les Résultats

### Ce Que Montre le Filtre

✅ **Entités sélectionnées** : Sites industriels à moins de 1 km des plans d'eau protégés

❌ **Entités exclues** : Sites industriels à plus de 1 km de tout plan d'eau

### Interpréter l'Analyse

**Sites à Risque Élevé** (distance = 0) :
- Directement dans les zones tampons réglementées
- Peuvent violer les réglementations environnementales
- Nécessitent un examen de conformité immédiat
- Potentiel de contamination de l'eau

**Sites à Risque Moyen** (0-500m) :
- Proches des limites du tampon
- Doivent être surveillés
- Peuvent nécessiter des protections supplémentaires
- Les expansions futures du tampon pourraient les affecter

**Sites à Risque Faible** (500-1000m) :
- Dans le tampon analytique mais hors réglementation typique
- Utile pour la planification proactive
- Préoccupation immédiate moindre

### Contrôles de Qualité

1. **Inspection visuelle** : Zoomer sur plusieurs résultats et vérifier qu'ils sont réellement près de l'eau
2. **Vérification des attributs** : S'assurer que les types d'installations correspondent aux attentes
3. **Validation de distance** : Mesurer la distance dans QGIS pour confirmer la précision du tampon
4. **Problèmes de géométrie** : Rechercher des sites sur la limite du tampon (peut indiquer des problèmes de géométrie)

---

## Meilleures Pratiques

### Optimisation des Performances

**Pour les Grands Jeux de Données (>10 000 sites industriels)** :

1. **Simplifier la géométrie des plans d'eau** d'abord :
   ```
   Vecteur → Outils de Géométrie → Simplifier
   Tolérance: 10 mètres (maintient la précision)
   ```

2. **Utiliser un index spatial** (automatique dans PostgreSQL, manuel dans Spatialite) :
   ```
   Couche → Propriétés → Créer un Index Spatial
   ```

3. **Pré-filtrer les plans d'eau** uniquement aux zones protégées :
   ```sql
   "statut_protege" = 'oui' OR "designation" IS NOT NULL
   ```

**Sélection du Backend** :
```
Entités     | Backend Recommandé
--------    | ------------------
< 1 000     | OGR (plus simple)
1k - 50k    | Spatialite (bon équilibre)
> 50k       | PostgreSQL (plus rapide)
```

### Considérations de Précision

1. **Unités de distance du tampon** : Toujours vérifier que les unités correspondent à votre SCR :
   ```
   Mètres: UTM, Lambert, Web Mercator
   Pieds: Certaines zones State Plane
   Degrés: NE JAMAIS utiliser pour les tampons (reprojeter d'abord !)
   ```

2. **Réparation de géométrie** : Les plans d'eau ont souvent des géométries invalides :
   ```
   Vecteur → Outils de Géométrie → Réparer les Géométries
   Exécuter avant l'opération de tampon
   ```

3. **Topologie** : Les plans d'eau qui se chevauchent peuvent créer des formes de tampon inattendues :
   ```
   Vecteur → Géotraitement → Dissoudre (unir tous les plans d'eau)
   Puis créer un tampon unifié unique
   ```

### Conformité Réglementaire

- **Documenter la méthodologie** : Sauvegarder l'historique des expressions FilterMate
- **Contrôle de version** : Conserver données originales + résultats filtrés + métadonnées
- **Validation** : Croiser avec les bases de données réglementaires officielles
- **Mises à jour** : Ré-exécuter l'analyse lorsque le registre industriel est mis à jour

---

## Problèmes Courants

### Problème 1 : "Aucune entité sélectionnée"

**Cause** : Incompatibilité de SCR ou distance de tampon trop petite

**Solution** :
```
1. Vérifier que les deux couches sont dans le même SCR projeté
2. Vérifier la distance du tampon: 1000 en mètres, pas en degrés
3. Essayer un tampon plus grand (ex : 2000m) pour tester
4. Vérifier que les plans d'eau existent réellement dans votre zone d'étude
```

### Problème 2 : "Erreurs de géométrie" lors du tampon

**Cause** : Géométries de plans d'eau invalides

**Solution** :
```
Vecteur → Outils de Géométrie → Réparer les Géométries
Puis recréer les tampons
```

### Problème 3 : Performances très lentes (>2 minutes)

**Cause** : Grands jeux de données sans optimisation

**Solutions** :
```
1. Créer des index spatiaux sur les deux couches
2. Simplifier la géométrie des plans d'eau (tolérance 10m)
3. Passer au backend PostgreSQL
4. Pré-filtrer sur une zone d'intérêt plus petite
```

### Problème 4 : Le tampon crée des formes étranges

**Cause** : SCR géographique (lat/lon) au lieu de projeté

**Solution** :
```
Reprojeter les DEUX couches dans la zone UTM appropriée :
Vecteur → Gestion de Données → Reprojeter une Couche
Trouver la zone correcte: https://epsg.io/
```

---

## Prochaines Étapes

### Flux de Travail Associés

- **[Couverture des Services d'Urgence](./emergency-services)** : Techniques d'analyse de tampon similaires
- **[Planification Urbaine Transport](./urban-planning-transit)** : Filtrage spatial multi-couches
- **[Analyse Immobilière](./real-estate-analysis)** : Combinaison de filtres spatiaux + attributs

### Techniques Avancées

**1. Tampons Multi-Anneaux** (zones de risque graduées) :
```
Créer 3 tampons séparés: 500m, 1000m, 1500m
Catégoriser les installations selon le tampon dans lequel elles tombent
```

**2. Proximité au Plan d'Eau le Plus Proche** (pas n'importe quel plan d'eau) :
```sql
-- Trouver la distance au plan d'eau le plus proche uniquement
array_min(
  array_foreach(
    overlay_nearest('plans_eau', $geometry),
    distance(@element, $geometry)
  )
)
```

**3. Analyse Temporelle** (si vous avez des données d'âge des installations) :
```sql
-- Anciennes installations dans zones sensibles (risque le plus élevé)
"annee_construction" < 1990 
AND distance_eau < 500
```

**4. Impact Cumulatif** (plusieurs installations près du même plan d'eau) :
```sql
-- Compter les installations affectant chaque plan d'eau
WITH comptes_risque AS (
  SELECT id_eau, COUNT(*) as nombre_installations
  FROM sites_filtres
  GROUP BY id_eau
)
-- Montrer les plans d'eau avec >5 installations à proximité
```

### Pour Aller Plus Loin

- 📖 [Référence des Prédicats Spatiaux](../reference/cheat-sheets/spatial-predicates)
- 📖 [Guide des Opérations de Tampon](../user-guide/buffer-operations)
- 📖 [Optimisation des Performances](../advanced/performance-tuning)
- 📖 [Dépannage](../advanced/troubleshooting)

---

## Résumé

✅ **Vous avez appris** :
- Créer des zones tampons autour des plans d'eau
- Filtrage par intersection spatiale avec des sites industriels
- Calcul de distance et catégorisation des risques
- Validation et réparation de géométrie
- Techniques d'optimisation spécifiques au backend

✅ **Points clés** :
- Toujours utiliser un SCR projeté pour les opérations de tampon
- Réparer les erreurs de géométrie avant l'analyse spatiale
- Choisir le backend en fonction de la taille du jeu de données
- Documenter la méthodologie pour la conformité réglementaire
- La validation visuelle est essentielle

🎯 **Impact réel** : Ce flux de travail aide les agences environnementales à identifier les risques de conformité, soutient l'élaboration de politiques fondées sur des preuves et protège la qualité de l'eau en mettant en évidence les installations nécessitant une surveillance ou une remédiation.
