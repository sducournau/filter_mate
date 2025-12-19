---
sidebar_position: 2
---

import Tabs from '@theme/Tabs';
import TabItem from '@theme/TabItem';

# Planification Urbaine : Propriétés Près des Transports

Trouver toutes les parcelles résidentielles à distance de marche des stations de métro pour une analyse de développement orienté vers le transport.

## Aperçu du Scénario

**Objectif** : Identifier les propriétés situées à moins de 500 mètres des stations de métro pour évaluer les opportunités de développement orienté vers le transport.

**Application Réelle** :
- Départements d'urbanisme évaluant les zones de développement
- Promoteurs immobiliers trouvant des propriétés accessibles en transport
- Décideurs politiques évaluant l'équité et la couverture des transports
- Planificateurs environnementaux réduisant la dépendance à la voiture

**Temps Estimé** : 10 minutes

**Difficulté** : ⭐⭐ Intermédiaire

---

## Prérequis

### Données Requises

1. **Couche Parcelles** (polygones)
   - Limites de propriétés résidentielles
   - Doit inclure les attributs d'usage du sol ou de zonage
   - Recommandé : 1 000+ entités pour une analyse réaliste

2. **Couche Stations de Transport** (points)
   - Emplacements des stations de métro/RER
   - Inclut les noms de stations
   - Couvre votre zone d'étude

### Sources de Données Exemples

**Option 1 : OpenStreetMap (Gratuit)**
```bash
# Utiliser le plugin QGIS QuickOSM
1. Vecteur → QuickOSM → Requête Rapide
2. Clé: "railway", Valeur: "station"
3. Sélectionner votre ville/région
4. Télécharger les points
```

**Option 2 : Données Ouvertes Municipales**
- Consultez le portail de données ouvertes de votre ville
- Recherchez des jeux de données "parcelles", "cadastre" ou "propriété"
- Données de transport généralement sous "transport"

### Configuration Système Requise

- **Backend Recommandé** : PostgreSQL (pour 50k+ parcelles)
- **Alternative** : Spatialite (pour <50k parcelles)
- **SCR** : N'importe lequel (FilterMate gère la reprojection automatiquement)

---

## Instructions Étape par Étape

### Étape 1 : Charger Vos Données

1. Ouvrir QGIS et créer un nouveau projet
2. Charger la couche **parcelles** (glisser-déposer ou Couche → Ajouter une Couche)
3. Charger la couche **stations_transport**
4. Vérifier que les deux couches s'affichent correctement sur la carte

:::tip Vérification du SCR
SCR différents ? Pas de problème ! FilterMate reprojette automatiquement les couches lors des opérations spatiales. Vous verrez un indicateur 🔄 lorsque la reprojection se produit.
:::

---

### Étape 2 : Ouvrir FilterMate

1. Cliquer sur l'icône **FilterMate** dans la barre d'outils
2. Ou : **Vecteur** → **FilterMate**
3. Le panneau s'ancre sur le côté droit

**Ce que vous devriez voir** :
- Trois onglets : FILTRAGE / EXPLORATION / EXPORTATION
- Sélecteur de couche en haut
- Constructeur d'expression vide

---

### Étape 3 : Configurer le Filtre

#### 3.1 Sélectionner la Couche Cible

1. Dans le menu déroulant **Sélection de Couche** (haut du panneau)
2. Cocher la couche **parcelles**
3. Notez l'indicateur de backend (PostgreSQL⚡ / Spatialite / OGR)

**Affichage des Informations de Couche** :
```
Fournisseur: postgresql (PostgreSQL)
Entités: 125 347
SCR: EPSG:2154 (Lambert 93)
Clé Primaire: gid
```

:::info Performance du Backend
Si vous voyez "OGR" pour de grands jeux de données de parcelles, envisagez de migrer vers PostgreSQL pour des performances 10 à 50× plus rapides. Voir [Guide des Backends](../backends/choosing-backend).
:::

---

#### 3.2 Ajouter un Filtre d'Attribut (Optionnel)

Filtrer uniquement les parcelles résidentielles :

1. Dans la section **Constructeur d'Expression**
2. Cliquer sur le menu déroulant **Champs** pour voir les attributs disponibles
3. Entrer cette expression :

```sql
usage_sol = 'residentiel'
-- OU si utilisation de codes de zonage:
zonage LIKE 'R-%'
-- OU plusieurs types résidentiels:
usage_sol IN ('residentiel', 'usage-mixte', 'multi-familial')
```

4. Attendre la coche verte (✓) - indique une syntaxe valide

**Explication de l'Expression** :
- `usage_sol = 'residentiel'` - Correspondance exacte sur le champ d'usage du sol
- `LIKE 'R-%'` - Correspondance de motif pour les codes de zonage résidentiel (R-1, R-2, etc.)
- `IN (...)` - Valeurs multiples autorisées

:::tip Pas de Champ Résidentiel ?
Si vos données n'ont pas d'usage du sol, sautez cette étape. Le filtre spatial fonctionnera sur toutes les parcelles.
:::

---

#### 3.3 Configurer le Filtre Géométrique

Maintenant ajoutez le composant spatial - proximité du transport :

1. **Faire défiler** vers la section **Filtre Géométrique**
2. Cliquer pour développer si replié

**Couche de Référence** :
3. Sélectionner **stations_transport** dans le menu déroulant
4. L'icône de couche de référence apparaît : 🚉

**Prédicat Spatial** :
5. Sélectionner **"Intersecte"** dans le menu déroulant des prédicats
   - (Nous ajouterons une distance de tampon, donc intersecte = "touche le tampon")

**Distance du Tampon** :
6. Entrer `500` dans le champ de distance
7. Sélectionner **mètres** comme unité
8. Laisser le type de tampon comme **Rond (Planaire)** pour les zones urbaines

**Votre Configuration Devrait Ressembler à** :
```
Couche de Référence: stations_transport
Prédicat Spatial: Intersecte
Distance du Tampon: 500 mètres
Type de Tampon: Rond (Planaire)
```

:::tip Conversion Auto des SCR Géographiques
Si vos couches utilisent des coordonnées géographiques (EPSG:4326), FilterMate convertit automatiquement en EPSG:3857 pour des tampons métriques précis. Vous verrez : indicateur 🌍 dans les logs.
:::

---

### Étape 4 : Appliquer le Filtre

1. Cliquer sur le bouton **Appliquer le Filtre** (grand bouton en bas)
2. FilterMate exécute la requête spatiale

**Ce Qui Se Passe** :

<Tabs>
  <TabItem value="postgresql" label="Backend PostgreSQL" default>
    ```sql
    -- Crée une vue matérialisée optimisée
    CREATE MATERIALIZED VIEW temp_filter AS
    SELECT p.*
    FROM parcelles p
    WHERE p.usage_sol = 'residentiel'
      AND EXISTS (
        SELECT 1 FROM stations_transport s
        WHERE ST_DWithin(
          p.geom::geography,
          s.geom::geography,
          500
        )
      );
    
    CREATE INDEX idx_temp_geom 
      ON temp_filter USING GIST(geom);
    ```
    ⚡ **Performance** : 0,3-2 secondes pour 100k+ parcelles
  </TabItem>
  
  <TabItem value="spatialite" label="Backend Spatialite">
    ```sql
    -- Crée une table temporaire avec index spatial
    CREATE TEMP TABLE temp_filter AS
    SELECT p.*
    FROM parcelles p
    WHERE p.usage_sol = 'residentiel'
      AND EXISTS (
        SELECT 1 FROM stations_transport s
        WHERE ST_Distance(p.geom, s.geom) <= 500
      );
    
    SELECT CreateSpatialIndex('temp_filter', 'geom');
    ```
    ⏱️ **Performance** : 5-15 secondes pour 50k parcelles
  </TabItem>
  
  <TabItem value="ogr" label="Backend OGR">
    Utilise le framework QGIS Processing avec des couches en mémoire.
    
    🐌 **Performance** : 30-120 secondes pour de grands jeux de données
    
    **Recommandation** : Migrer vers PostgreSQL pour ce flux de travail.
  </TabItem>
</Tabs>

---

### Étape 5 : Examiner les Résultats

**Vue Carte** :
- Les parcelles filtrées sont surlignées sur la carte
- Les parcelles non correspondantes sont masquées (ou grisées)
- Nombre affiché dans le panneau FilterMate : `Trouvé: 3 247 entités`

**Vérifier les Résultats** :
1. Zoomer sur une station de transport
2. Sélectionner une parcelle filtrée
3. Utiliser l'**Outil de Mesure** pour vérifier qu'elle est à moins de 500m de la station

**Résultats Attendus** :
- Centres urbains : Haute densité de parcelles filtrées
- Zones suburbaines : Parcelles clairsemées près des stations
- Zones rurales : Très peu ou pas de résultats

---

### Étape 6 : Analyser et Exporter

#### Option A : Statistiques Rapides

1. Clic droit sur la couche filtrée
2. **Propriétés** → **Information**
3. Voir le nombre d'entités et l'étendue

#### Option B : Exporter pour Rapport

1. Passer à l'onglet **EXPORTATION** dans FilterMate
2. Sélectionner la couche de parcelles filtrées
3. Choisir le format de sortie :
   - **GeoPackage (.gpkg)** - Meilleur pour QGIS
   - **GeoJSON** - Pour la cartographie web
   - **Shapefile** - Pour les systèmes legacy
   - **PostGIS** - Retour vers la base de données

4. **Optionnel** : Transformer le SCR (ex : WGS84 pour le web)
5. Cliquer sur **Exporter**

**Exemple de Paramètres d'Exportation** :
```
Couche: parcelles (filtré)
Format: GeoPackage
SCR de Sortie: EPSG:4326 (WGS84)
Nom de fichier: parcelles_accessibles_transport.gpkg
```

---

## Comprendre les Résultats

### Interpréter les Comptes d'Entités

**Résultats Exemples** :
```
Total parcelles: 125 347
Parcelles résidentielles: 87 420 (70%)
Résidentiel accessible en transport: 3 247 (3,7% du résidentiel)
```

**Ce Que Cela Signifie** :
- Seulement 3,7% des parcelles résidentielles sont accessibles en transport
- Opportunité pour le développement orienté transport
- La plupart des résidents dépendent de la voiture (préoccupation d'équité)

### Motifs Spatiaux

**Rechercher** :
- **Clusters** autour des grands hubs de transport → Zones de haute densité
- **Lacunes** entre les stations → Développement de remplissage potentiel
- **Parcelles isolées** → Déserts de transport nécessitant une extension de service

---

## Meilleures Pratiques

### Optimisation des Performances

✅ **Utiliser PostgreSQL** pour les jeux de données de parcelles >50k entités
- 10-50× plus rapide que le backend OGR
- Temps de requête sub-seconde même sur 500k+ parcelles

✅ **Filtrer par attribut d'abord** si possible
- `usage_sol = 'residentiel'` réduit la portée de la requête spatiale
- Amélioration des performances de 30-50%

✅ **Unités de Distance du Tampon**
- Utiliser **mètres** pour l'analyse urbaine (cohérent dans le monde entier)
- Éviter **degrés** pour les requêtes basées sur la distance (imprécis)

### Considérations de Précision

⚠️ **Sélection du Type de Tampon** :
- **Rond (Planaire)** : Rapide, précis pour de petites zones (<10km)
- **Rond (Géodésique)** : Plus précis pour de grandes régions
- **Carré** : Optimisation computationnelle (rarement nécessaire)

⚠️ **Choix du SCR** :
- SCR projeté local (ex : Lambert, UTM) - Meilleure précision
- Web Mercator (EPSG:3857) - Bon pour l'analyse mondiale
- WGS84 (EPSG:4326) - Auto-converti par FilterMate ✓

### Qualité des Données

🔍 **Vérifier** :
- **Parcelles qui se chevauchent** - Peut gonfler les comptes
- **Géométries manquantes** - Utiliser l'outil "Vérifier les Géométries"
- **Données de transport obsolètes** - Vérifier le statut opérationnel des stations

---

## Problèmes Courants et Solutions

### Problème 1 : Aucun Résultat Trouvé

**Symptômes** : Le filtre renvoie 0 entité, mais vous attendez des correspondances.

**Causes Possibles** :
1. ❌ Distance du tampon trop petite (essayer 1000m)
2. ❌ Mauvaise valeur d'attribut (vérifier les valeurs du champ `usage_sol`)
3. ❌ Les couches ne se chevauchent pas géographiquement
4. ❌ Incompatibilité de SCR (bien que FilterMate gère cela)

**Étapes de Débogage** :
```sql
-- Test 1: Supprimer le filtre d'attribut
-- Juste exécuter la requête spatiale sur toutes les parcelles

-- Test 2: Augmenter la distance du tampon
-- Essayer 1000 ou 2000 mètres

-- Test 3: Inverser la requête
-- Filtrer les stations dans les parcelles (devrait toujours renvoyer des résultats)
```

---

### Problème 2 : Performances Lentes (>30 secondes)

**Cause** : Grand jeu de données avec backend OGR.

**Solutions** :
1. ✅ Installer PostgreSQL + PostGIS
2. ✅ Charger les données dans la base de données PostgreSQL
3. ✅ Utiliser une couche PostgreSQL dans QGIS
4. ✅ Ré-exécuter le filtre (attendre une accélération de 10-50×)

**Configuration Rapide PostgreSQL** :
```bash
# Installer psycopg2 pour Python QGIS
pip install psycopg2-binary

# Ou dans OSGeo4W Shell (Windows):
py3_env
pip install psycopg2-binary
```

---

### Problème 3 : Les Résultats Semblent Incorrects

**Symptômes** : Des parcelles loin des stations sont incluses.

**Causes Possibles** :
1. ❌ Distance du tampon dans les mauvaises unités (degrés au lieu de mètres)
2. ❌ Prédicat "Contient" au lieu de "Intersecte"
3. ❌ La couche de référence est incorrecte (routes au lieu de stations)

**Vérification** :
1. Utiliser l'**Outil de Mesure** QGIS
2. Mesurer la distance de la parcelle filtrée à la station la plus proche
3. Devrait être ≤ 500 mètres

---

## Prochaines Étapes

### Flux de Travail Associés

- **[Couverture des Services d'Urgence](./emergency-services)** - Analyse de distance similaire
- **[Zones de Protection Environnementale](./environmental-protection)** - Filtrage multi-critères
- **[Analyse Immobilière](./real-estate-analysis)** - Filtrage d'attributs combinés

### Techniques Avancées

**Tampons Gradués** :
Exécuter plusieurs filtres avec différentes distances (250m, 500m, 1000m) pour créer des zones de marchabilité.

**Combiner avec la Démographie** :
Joindre les données de recensement pour estimer la population accessible en transport.

**Analyse Temporelle** :
Utiliser des données historiques pour suivre le développement orienté transport au fil du temps.

---

## Résumé

**Vous Avez Appris** :
- ✅ Filtrage combiné d'attributs et géométrique
- ✅ Opérations de tampon avec paramètres de distance
- ✅ Sélection de prédicat spatial (Intersecte)
- ✅ Optimisation des performances du backend
- ✅ Exportation de résultats et transformation de SCR

**Points Clés** :
- FilterMate gère la reprojection SCR automatiquement
- Le backend PostgreSQL fournit les meilleures performances pour de grands jeux de données
- 500m est la "distance de marche" typique pour la planification urbaine
- Toujours vérifier les résultats avec un échantillonnage de mesure manuelle

**Temps Économisé** :
- Sélection manuelle : ~2 heures
- Boîte à Outils de Traitement (multi-étapes) : ~20 minutes
- Flux de travail FilterMate : ~10 minutes ⚡

---

Besoin d'aide ? Consultez le [Guide de Dépannage](../advanced/troubleshooting) ou posez des questions sur [GitHub Discussions](https://github.com/sducournau/filter_mate/discussions).
