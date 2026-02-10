# Analyse Strategique de FilterMate dans l'Ecosysteme QGIS

## par Atlas -- Veille Technologique Geospatiale

*Analyse realisee sur la base du code source complet (v5.4.0/v6.0.0-dev), des 26 memories Serena du projet, et de la connaissance de l'ecosysteme QGIS/Python geospatial.*

---

## 1. Cartographie de l'Ecosysteme Concurrent

### Filtrage vectoriel / Exploration

| Plugin | Fonction principale | Installs (estim.) | Derniere MAJ |
|--------|--------------------|--------------------|--------------|
| **QuickMapServices** | Acces rapide aux fonds de carte | >500k | Actif |
| **Select by Relationship** | Selection par relations topologiques | ~15k | Sporadique |
| **refFunctions** | Fonctions de reference dans les expressions | ~20k | Sporadique |
| **Group Stats** | Statistiques par groupe d'entites | ~30k | Rarement |
| **DataPlotly** | Visualisation interactive de donnees attributaires | ~50k | Actif |

**Outils natifs QGIS concurrents directs :**
- Le **panneau "Selectionner par expression"** (Ctrl+F3) -- outil standard
- Le **panneau "Selectionner par localisation"** (Processing > Vector Selection) -- filtrage spatial natif
- Le **"Query Builder"** (clic droit > Filter) -- clause WHERE sur la couche
- Le **panneau Statistiques** -- statistiques basiques sur un champ

### Interaction Raster

| Plugin | Fonction principale | Installs | Positionnement |
|--------|--------------------|---------:|----------------|
| **Value Tool** | Affiche les valeurs raster sous le curseur (toutes bandes) | ~100k | Le classique |
| **Point Sampling Tool** | Echantillonne des valeurs raster aux emplacements de points vectoriels | ~80k | Export ponctuel |
| **Sketcher** | Edition et annotation sur canvas | ~5k | Niche |
| **Raster Stats** (natif Processing) | Statistiques zonales | N/A | Pipeline Processing |
| **SCP (Semi-Automatic Classification Plugin)** | Classification supervisee raster | ~200k | Teledetection |

### Export

| Plugin/Outil | Fonction | Positionnement |
|-------------|----------|----------------|
| **Processing "Sauvegarder sous..."** | Export natif multi-format | Standard QGIS |
| **QConsolidate** | Package projet + donnees | Partage de projets |
| **Export natif GeoPackage** | Export avec ou sans styles | Basique mais fonctionnel |

---

## 2. Ce que FilterMate Apporte de Vraiment Nouveau

### Les VRAIS differenciateurs (ce qu'aucun plugin ne fait)

#### A. Systeme multi-backend intelligent avec selection automatique

C'est LA killer feature architecturale. Aucun plugin QGIS ne fait ca :

```
PostgreSQL (>50k) --> Spatialite (10-50k) --> Memory (<10k) --> OGR (fallback)
```

Avec en plus :
- Detection automatique de la cle primaire (interrogation de `pg_index`)
- Routage automatique GeoPackage vers Spatialite (gain 10x)
- Optimisation "small PostgreSQL" : charger en memoire les petites tables PG pour eviter le reseau
- Vues materialisees automatiques avec GIST + FILLFACTOR

Le **Query Builder** natif de QGIS fait un simple `setSubsetString()` -- FilterMate construit des strategies de filtrage adaptatives. On est dans deux mondes differents.

#### B. Filtrage progressif a deux phases avec estimation de complexite

Le `QueryComplexityEstimator` analyse les expressions SQL pour router vers la strategie optimale (DIRECT / MATERIALIZED / TWO_PHASE / PROGRESSIVE). C'est de l'optimisation de plan de requete artisanale -- le genre de chose qu'on trouve dans un moteur de base de donnees, pas dans un plugin QGIS.

#### C. Filtrage vector-by-raster integre

Filtrer des entites vectorielles en fonction des valeurs raster sous-jacentes, avec selection de plage sur histogramme, picking de pixels, et masques -- ca n'existe nulle part ailleurs comme experience integree dans QGIS.

On peut le faire a la main avec une combinaison de :
1. `Point Sampling Tool` pour echantillonner
2. `Select by Expression` pour filtrer les resultats
3. Du Processing pour les zones

Mais FilterMate unifie tout ca dans un seul workflow interactif : 5-6 clics au lieu de 15-20 etapes manuelles.

#### D. Historique Undo/Redo a 100 niveaux

Aucun systeme de filtrage dans QGIS -- ni natif ni plugin -- ne propose un historique de 100 etats avec undo/redo global multi-couches. Le Query Builder natif ? Pas d'historique. Select by Expression ? Pas d'historique. Avantage UX enorme pour l'exploration iterative.

#### E. Chainage de filtres avec buffer dynamique

La capacite a enchainer source -> buffer dynamique -> filtre spatial -> couches distantes, le tout avec des expressions de buffer parametriques. C'est du workflow spatial avance que normalement on code dans un script Processing ou en Python pur.

### Les ameliorations incrementales (mieux que l'existant, mais pas uniques)

- **Statistiques raster en temps reel** -- Le Value Tool fait ca depuis 15 ans, mais FilterMate l'integre directement dans le workflow de filtrage.
- **Export avec preservation de styles** -- QGIS le fait nativement depuis la 3.x. L'apport est le "one-click" et le batch export.
- **Support multi-formats** -- QGIS les supporte tous nativement. L'apport est l'optimisation specifique par format.

---

## 3. Forces et Faiblesses de l'Architecture Hexagonale

### Forces

**1. Separation des preoccupations exemplaire**

La structure `core/` (domaine) / `adapters/` (backends) / `infrastructure/` (transversal) / `ui/` (presentation) est probablement la plus propre d'un plugin QGIS. Pour perspective : la plupart des plugins populaires sont un seul fichier de 500-2000 lignes. FilterMate a 28 services, 4 backends, 13 controleurs. C'est une application a part entiere.

**2. Testabilite**

396 tests unitaires, 75% de couverture -- exceptionnel pour un plugin QGIS. La moyenne de l'ecosysteme est proche de 0%. L'architecture hexagonale permet de tester les services sans dependre de l'instance QGIS.

**3. Extensibilite backend**

Ajouter un nouveau backend (DuckDB Spatial ? Arrow/Parquet ?) revient a implementer une interface bien definie. Le Factory Pattern + Port/Adapter rendent ca realiste.

**4. Pattern Strategy pour les filtres**

`multi_step_filter.py` et `progressive_filter.py` dans `core/strategies/` -- chaque strategie est independante, testable, interchangeable. On peut ajouter une strategie "GPU-accelerated" ou "cloud-delegated" sans toucher au reste.

### Faiblesses

**1. La complexite est le prix de l'architecture**

~130 000 lignes de production pour un plugin QGIS -- c'est MASSIF :
- `Value Tool` : ~500 lignes
- `Point Sampling Tool` : ~800 lignes
- `DataPlotly` : ~15 000 lignes
- `SCP (Semi-Automatic Classification)` : ~50 000 lignes

FilterMate est 2.5x plus gros que SCP. La dette cognitive pour un nouveau contributeur est considerable.

**2. Le dockwidget reste un God Object**

Meme apres extraction du `RasterExploringManager` et du `DockwidgetSignalManager`, le fichier `filter_mate_dockwidget.py` fait encore ~7000 lignes. La couche hexagonale est propre, mais l'UI reste monolithique.

**3. Overhead pour les cas simples**

Pour "filtrer les batiments de plus de 100m2", l'architecture multi-backend + strategies + optimiseur + cache est du sur-engineering. Le Query Builder natif fait ca en une ligne d'expression.

**4. Dependance implicite a l'ecosysteme QGIS**

Les concepts QGIS (QgsVectorLayer, QgsTask, iface) infiltrent le coeur du domaine. C'est un defi inherent a tout plugin QGIS ambitieux, mais cela limite la portabilite theorique promise par l'hexagonal.

---

## 4. Positionnement Face aux Outils Natifs QGIS

| Fonctionnalite | QGIS Natif | FilterMate | Verdict |
|---------------|------------|------------|---------|
| **Filtre par expression** | Query Builder (expression SQL) | Interface graphique + multi-backend | FilterMate plus accessible, QGIS natif plus flexible pour les experts SQL |
| **Selection spatiale** | Processing > Select by Location | Filtrage geometrique avec buffer dynamique, chainage, multi-predicats | FilterMate nettement superieur |
| **Statistiques raster** | Panneau Statistiques (basique) | Temps reel, multi-bandes, integration avec filtrage | FilterMate superieur en integration |
| **Valeurs pixel** | Value Tool (plugin) | Pixel picker + rectangle range + histogramme | FilterMate integre mieux ; Value Tool plus leger |
| **Export** | "Sauvegarder sous..." | One-click avec styles + batch | FilterMate ajoute du confort |
| **Performance gros jeux** | Depends du provider | 4 optimiseurs, vues materialisees, cache | FilterMate clairement superieur |
| **Historique filtrage** | Aucun | Undo/Redo 100 niveaux, global multi-couches | FilterMate unique |
| **Favoris de filtres** | Aucun | Systeme de favoris avec contexte spatial | FilterMate unique |
| **Vector-by-raster** | Combinaison manuelle de 3-4 outils | Workflow integre | FilterMate unique |

> **Resume** : FilterMate n'est PAS un remplacement des outils natifs -- c'est une **couche d'orchestration** qui les transcende. Les outils natifs sont les `vi`/`nano` du filtrage spatial ; FilterMate est le VSCode.

---

## 5. Potentiel dans l'Ecosysteme QGIS

### Points forts du positionnement

**1. Niche non occupee : le "filtrage spatial intelligent"**

Il n'existe pas de plugin QGIS qui combine filtrage vectoriel + raster + multi-backend + historique + favoris dans une interface unifiee. FilterMate cree sa propre categorie.

**2. Le public cible est reel et mal servi**

Les analystes SIG qui travaillent quotidiennement avec des jeux de donnees heterogenes (BD TOPO en PostgreSQL + orthophotos en GeoTIFF + shapefiles en local + WFS) passent un temps considerable a jongler entre outils.

**3. La performance comme argument**

Benchmarks : 3-45x de gain selon les scenarios. Pour les collectivites et bureaux d'etudes qui travaillent sur des departements entiers de BD TOPO (millions d'entites), c'est un argument concret et mesurable.

### Risques et axes d'amelioration

**1. Le probleme de la decouverte**

Les tags du plugin repository sont corrects mais manquent des termes de recherche utilisateur comme `spatial query`, `select by location`, `raster values`.

**2. Le risque de l'usine a gaz percue**

Avec 22 langues, 4 backends, 28 services, un systeme de themes, des favoris, de l'undo/redo... l'interface peut intimider.

**3. L'opportunite du Cloud-Optimized**

Si FilterMate peut devenir le plugin de reference pour produire des COG depuis QGIS, c'est un angle de differenciation fort (STAC, cloud-native). De meme, un futur support GeoParquet et PMTiles placerait FilterMate a l'avant-garde.

**4. L'integration Processing manquante**

FilterMate n'a pas de `ProcessingProvider`. Si les algorithmes etaient exposes comme des algorithmes Processing, ils deviendraient utilisables dans les modeles graphiques, chainables, scriptables en PyQGIS, et disponibles sur QGIS Server. L'architecture hexagonale actuelle le rendrait relativement faisable.

**5. Le potentiel "point cloud"**

Avec le support natif des nuages de points dans QGIS 3.32+ (via PDAL), un "FilterMate for Point Clouds" qui permettrait de filtrer interactivement des dalles LiDAR serait une extension naturelle et totalement inexploree.

---

## 6. Recommandations Prioritaires

1. **Processing Provider** -- Exposer 3-5 algorithmes cles en Processing. C'est le multiplicateur d'impact le plus evident.
2. **Mode Simple/Expert** -- Reduire la barriere d'entree pour les 80% d'utilisateurs qui veulent juste filtrer simplement.
3. **COG + GeoParquet** -- Se positionner sur les formats cloud-native avant la concurrence.
4. **Continuer la consolidation v6.0** -- Les -19 000 lignes prevues sont essentielles pour la maintenabilite long terme.
5. **Documentation utilisateur** -- Le code est la, l'architecture est solide. Maintenant il faut que le monde le sache.

---

> *"FilterMate n'est pas 'juste un autre plugin de filtrage'. C'est une tentative serieuse de construire un outil de niveau professionnel avec les bonnes pratiques logicielles, dans un ecosysteme ou c'est extremement rare. Le defi n'est plus technique -- il est de communication et de positionnement. Le code est la. L'architecture est solide. Maintenant il faut que le monde le sache."*
>
> -- Atlas, Veille Technologique Geospatiale, 10 fevrier 2026
