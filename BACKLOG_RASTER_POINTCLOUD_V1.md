# Backlog FilterMate -- Raster & Point Cloud V1
## Date: 2026-02-11 | Auteur: Jordan (PO) | Veille: Atlas

---

## DECISIONS STRATEGIQUES

### DS-1 : Faut-il finir le refactoring avant raster/PC ?

**Decision : NON, mais on intercale.**

- Le refactoring restant (filter_task pass 3, dockwidget phase 2) est independant des features raster/PC
- Bloquer 3-4 semaines de features pour de la dette technique = perte de momentum
- La branche raster existante prouve que le code supporte deja l'extension

**Plan** : Sprint 0 = merge raster + fin refactoring critique. Puis on alterne : 1 sprint feature, 1 demi-sprint stabilisation.

### DS-2 : QGIS minimum version

**Decision : 3.22 pour raster, 3.26 pour point cloud (avec detection conditionnelle).**

| Scenario | QGIS min | Impact |
|----------|----------|--------|
| Raster features | 3.22 | Zero rupture, toutes les APIs disponibles |
| Point Cloud basic (setSubsetString) | 3.26 | Couvre 85%+ des installations actives |
| Point Cloud avance (PDAL Processing) | 3.32 | Feature optionnelle, detection a l'execution |

Le metadata.txt reste a `qgisMinimumVersion=3.22`. Le point cloud est conditionne par detection runtime.

### DS-3 : Merge branche raster

**Decision : Cherry-pick selectif, pas merge direct.**

- La branche raster a 19 commits d'avance, main a 20 commits de refactoring que la branche n'a pas
- Un merge direct = conflits massifs garantis (dockwidget, filter_task, managers)
- **Plan** : Cherry-pick les fichiers raster purs (domain, services, adapters, widgets) sur main post-refactoring. Adapter le cablage UI aux managers extraits.

### DS-4 : MVP Raster vs MVP Point Cloud

| | MVP Raster | MVP Point Cloud |
|--|-----------|-----------------|
| **Scope** | Dual panel + sampling + zonal stats | Classification filter + attribut/Z filter |
| **Valeur** | Haute -- differentiant unique | Tres haute -- ocean bleu total |
| **Effort** | 20-25j | 15-20j |
| **Priorite** | **Premier** (fondations posees) | **Deuxieme** (part de zero) |
| **QGIS min** | 3.22 | 3.26 |

---

## EPICS

### EPIC-R0 : Fondations Raster (prerequis) -- MUST
Cherry-pick de la branche raster + fin du refactoring critique pour accueillir les features raster.

### EPIC-R1 : Raster Value Sampling -- MUST
Permettre a l'utilisateur de visualiser les valeurs raster en relation avec ses entites vectorielles.

### EPIC-R2 : Zonal Stats as Filter (differenciateur cle) -- MUST
Filtrer des entites vectorielles selon les statistiques raster calculees dans leurs emprises.
**C'est LA feature qui fait de FilterMate un outil unique.**

### EPIC-R3 : Raster-Driven Highlight -- SHOULD
Retour visuel dynamique sur le raster quand un filtre est actif.

### EPIC-R4 : Raster Clip by Vector -- COULD
Exporter un raster decoupe par l'emprise des entites filtrees.

### EPIC-R5 : Multi-Band Composite -- WON'T V1
Operations de filtrage sur des combinaisons de bandes spectrales.

### EPIC-PC1 : Point Cloud Filtrage Basique -- SHOULD
Filtrage interactif des nuages de points par classification, attributs et elevation.

### EPIC-PC2 : Point Cloud Avance -- COULD
Clip polygonal, stats/profil, export filtre via PDAL.

---

## MoSCoW (V1 = prochaine release majeure)

| Priorite | Epic | Justification |
|----------|------|---------------|
| **MUST** | EPIC-R0 | Prerequis technique, debloque tout le reste |
| **MUST** | EPIC-R1 | Fondation du raster, valeur immediate, 80% deja code |
| **MUST** | EPIC-R2 | Differenciateur unique, ocean bleu, ROI maximal |
| **SHOULD** | EPIC-R3 | UX forte mais pas bloquante pour la valeur fonctionnelle |
| **SHOULD** | EPIC-PC1 | Ocean bleu, effort modere, timing IGN parfait |
| **COULD** | EPIC-R4 | Valeur reelle mais dependante d'EPIC-R2 |
| **COULD** | EPIC-PC2 | Haute valeur mais QGIS 3.32 requis, audience reduite |
| **WON'T** | EPIC-R5 | Complexite moyenne, audience niche, pas de demande confirmee |

---

## USER STORIES DETAILLEES

### EPIC-R0 : Fondations Raster

#### US-R0.1 : Merge des fondations raster sur main
**En tant que** developpeur, **je veux** integrer les fichiers raster de la branche `refactor/quick-wins-2026-02-10` sur main **afin de** disposer des fondations (DualModeToggle, domain, services, adapters) sans conflits avec le refactoring.

**Priorite** : MUST | **Effort** : M (2-3j) | **Sprint** : 0

**Criteres d'acceptation :**
- GIVEN la branche main actuelle avec les 4 managers extraits
- WHEN je cherry-pick les fichiers raster purs (domain, services, adapters, widgets, DualModeToggle)
- THEN les fichiers raster sont presents sur main sans conflit
- AND les 311 tests existants passent toujours
- AND le plugin demarre sans erreur dans QGIS

**Notes Marco :**
- Cherry-pick, PAS merge
- Adapter les imports si les managers ont change la structure
- Ne PAS inclure les modifications dockwidget de la branche (obsoletes vu les extractions E1-E4)

---

#### US-R0.2 : Pass 3 filter_task.py
**En tant que** developpeur, **je veux** extraire MaterializedViewHandler, ExpressionBuilder et SpatialQueryBuilder de filter_task.py **afin de** passer sous les 3 000 lignes et faciliter l'extension raster/PC.

**Priorite** : MUST | **Effort** : M (2-3j) | **Sprint** : 0

**Criteres d'acceptation :**
- GIVEN filter_task.py a 3 977 lignes
- WHEN les 3 handlers sont extraits
- THEN filter_task.py < 3 000 lignes
- AND les 311 tests passent
- AND le filtrage vectoriel fonctionne identiquement (regression zero)

---

#### US-R0.3 : Cablage UI raster dans le dockwidget refactore
**En tant que** developpeur, **je veux** integrer le panneau raster (DualModeToggle, QStackedWidget) dans le dockwidget refactore avec les managers extraits **afin de** avoir une UI fonctionnelle pour les features raster.

**Priorite** : MUST | **Effort** : M (3-5j) | **Sprint** : 0

**Criteres d'acceptation :**
- GIVEN le dockwidget avec les 4 managers extraits (E1-E4)
- WHEN j'ouvre FilterMate avec une couche raster dans le projet
- THEN le DualModeToggle apparait et bascule correctement entre panneau vecteur et panneau raster
- AND la detection auto du type de couche fonctionne
- AND les GroupBoxes raster sont construits dynamiquement
- AND aucune regression sur le panneau vecteur existant

---

### EPIC-R1 : Raster Value Sampling

#### US-R1.1 : Sampling par centroide
**En tant que** analyste SIG, **je veux** voir les valeurs raster au centroide de mes entites vectorielles **afin de** comprendre la relation entre mes geometries et les donnees raster sous-jacentes.

**Priorite** : MUST | **Effort** : S (3-5j) | **Sprint** : 1

**Criteres d'acceptation :**
- GIVEN une couche vectorielle polygonale et une couche raster chargees dans QGIS
- WHEN je selectionne la couche raster dans FilterMate et lance le sampling
- THEN les valeurs raster au centroide (pointOnSurface, pas centroid) de chaque entite sont calculees
- AND les valeurs sont affichees dans le panneau raster
- AND le calcul pour 10 000 points prend < 500ms
- AND la reprojection CRS est automatique si les couches ont des CRS differents
- AND les valeurs NoData sont gerees (affichees comme "NoData", pas comme un nombre)

**Regles metier :**
- Utiliser `pointOnSurface()` (pas `centroid()`) pour les polygones concaves
- Reprojection vector -> raster CRS avant sampling
- `provider.sample(point, band)` pour chaque bande

---

#### US-R1.2 : Affichage info couche raster
**En tant que** utilisateur SIG, **je veux** voir les metadonnees de la couche raster selectionnee (nombre de bandes, type de donnees, CRS, etendue, resolution) **afin de** comprendre ce que je manipule avant de filtrer.

**Priorite** : MUST | **Effort** : XS (1-2j) | **Sprint** : 1

**Criteres d'acceptation :**
- GIVEN une couche raster selectionnee dans FilterMate
- WHEN le panneau raster s'affiche
- THEN je vois : nom, nombre de bandes, type de pixel, CRS, dimensions (px), resolution, extent
- AND les infos se mettent a jour quand je change de couche raster

---

#### US-R1.3 : Sampling multi-bandes
**En tant que** analyste SIG, **je veux** choisir sur quelles bandes effectuer le sampling **afin de** ne pas calculer inutilement sur des bandes non pertinentes.

**Priorite** : SHOULD | **Effort** : S (2-3j) | **Sprint** : 1

**Criteres d'acceptation :**
- GIVEN une couche raster multi-bandes (ex: RGB, multispectral)
- WHEN j'ouvre le panneau sampling
- THEN je vois la liste des bandes avec leur nom/numero
- AND je peux cocher/decocher les bandes a sampler
- AND par defaut toutes les bandes sont cochees
- AND le sampling ne porte que sur les bandes selectionnees

---

### EPIC-R2 : Zonal Stats as Filter

#### US-R2.1 : Calcul de statistiques zonales
**En tant que** analyste SIG, **je veux** calculer des statistiques (min, max, moyenne, ecart-type, mediane) des valeurs raster dans l'emprise de chaque entite vectorielle **afin de** pouvoir ensuite filtrer mes entites par ces valeurs.

**Priorite** : MUST | **Effort** : L (8-10j) | **Sprint** : 2

**Criteres d'acceptation :**
- GIVEN une couche vectorielle et une couche raster
- WHEN je lance le calcul de statistiques zonales sur une bande donnee
- THEN pour chaque entite, les statistiques (min, max, mean, std, median, count, sum) sont calculees
- AND les resultats sont stockes en memoire (pas de modification de la couche source)
- AND le calcul utilise `provider.block()` + numpy (pas pixel-by-pixel)
- AND le calcul pour 100 polygones sur un raster de 1 Go prend < 10s
- AND un indicateur de progression est affiche pendant le calcul
- AND le calcul s'execute en background thread (pas de freeze UI)

**Regles metier :**
- Ne PAS utiliser `QgsZonalStatistics` (modifie la couche in-place)
- Charger un seul bloc couvrant l'extent global, sampler en memoire avec numpy
- Les polygones hors de l'extent raster retournent NoData

---

#### US-R2.2 : Filtrage par statistique zonale
**En tant que** analyste SIG, **je veux** filtrer mes entites vectorielles selon les statistiques zonales calculees (ex: "moyenne > 500", "ecart-type < 10") **afin de** selectionner uniquement les zones qui m'interessent selon le raster.

**Priorite** : MUST | **Effort** : M (5-7j) | **Sprint** : 2

**Criteres d'acceptation :**
- GIVEN des statistiques zonales calculees pour mes entites
- WHEN je definis un filtre (operateur + valeur seuil) sur une statistique
- THEN seules les entites qui satisfont le critere sont conservees
- AND le filtre est applicable via l'interface standard de FilterMate (subset string)
- AND je peux combiner plusieurs criteres (AND/OR)
- AND le resultat est visible immediatement sur la carte
- AND je peux reinitialiser le filtre

---

#### US-R2.3 : Histogramme des valeurs raster
**En tant que** analyste SIG, **je veux** visualiser un histogramme des valeurs raster dans la zone couverte par mes entites **afin de** choisir intelligemment mes seuils de filtrage.

**Priorite** : SHOULD | **Effort** : M (3-5j) | **Sprint** : 2

**Criteres d'acceptation :**
- GIVEN des statistiques zonales calculees
- WHEN j'affiche l'histogramme
- THEN je vois la distribution des valeurs raster
- AND je peux cliquer/glisser sur l'histogramme pour definir le seuil de filtrage
- AND l'histogramme se met a jour quand je change de bande ou de couche

---

### EPIC-R3 : Raster-Driven Highlight

#### US-R3.1 : Masquage dynamique des pixels hors filtre
**En tant que** cartographe, **je veux** que les pixels raster en dehors des zones filtrees soient rendus transparents **afin de** visualiser clairement l'effet de mon filtre sur le raster.

**Priorite** : SHOULD | **Effort** : M (5-8j) | **Sprint** : 3

**Criteres d'acceptation :**
- GIVEN un filtre zonal actif sur des entites vectorielles
- WHEN le filtre est applique
- THEN les pixels raster hors des geometries des entites filtrees deviennent transparents
- AND l'effet est visible en temps reel lors du changement de filtre
- AND je peux activer/desactiver le highlight sans perdre le filtre
- AND la performance reste interactive (< 1s pour un raster de 500 Mo)

**Regles metier :**
- Utiliser `QgsRasterTransparency` (pas de copie raster)
- Restaurer la transparence originale quand le filtre est desactive

---

### EPIC-R4 : Raster Clip by Vector

#### US-R4.1 : Export raster decoupe
**En tant que** analyste SIG, **je veux** exporter la portion du raster correspondant a mes entites filtrees **afin de** partager ou traiter uniquement les donnees pertinentes.

**Priorite** : COULD | **Effort** : M (5-7j) | **Sprint** : 4

**Criteres d'acceptation :**
- GIVEN un filtre actif avec des entites vectorielles selectionnees
- WHEN je clique sur "Exporter raster"
- THEN le raster est decoupe selon l'enveloppe des entites filtrees
- AND le format de sortie est GeoTIFF (option COG si GDAL >= 3.1)
- AND les metadonnees (CRS, resolution) sont preservees
- AND un dialogue de progression est affiche

---

### EPIC-PC1 : Point Cloud Filtrage Basique

#### US-PC1.0 : Detection et architecture point cloud
**En tant que** developpeur, **je veux** implementer le port/adapter point cloud et la detection conditionnelle (QGIS >= 3.26) **afin de** poser les fondations pour toutes les features PC.

**Priorite** : SHOULD | **Effort** : M (3-5j) | **Sprint** : 3

**Criteres d'acceptation :**
- GIVEN un QGIS >= 3.26 avec une couche point cloud chargee
- WHEN FilterMate detecte la couche
- THEN le type "point cloud" est reconnu et le panneau adapte s'affiche
- AND sur QGIS < 3.26, les features PC sont invisibles (pas d'erreur, pas de menu)
- AND l'architecture suit le pattern hexagonal existant (port + adapter)

---

#### US-PC1.1 : Filtrage par classification ASPRS
**En tant que** utilisateur LiDAR, **je veux** filtrer mon nuage de points par code de classification (Sol, Vegetation, Batiment, Eau, Bruit...) **afin de** ne visualiser que les categories qui m'interessent.

**Priorite** : SHOULD | **Effort** : M (5-8j) | **Sprint** : 3

**Criteres d'acceptation :**
- GIVEN une couche point cloud COPC/LAS/LAZ chargee dans QGIS
- WHEN j'ouvre FilterMate et selectionne la couche PC
- THEN je vois une liste a cocher des classes de classification ASPRS presentes dans le fichier
- AND les labels ASPRS standard sont affiches (2=Sol, 5=Vegetation haute, 6=Batiment...)
- AND quand je coche/decoche une classe, `setSubsetString("Classification IN (2,6)")` est applique
- AND le rendu se met a jour immediatement
- AND je peux tout cocher / tout decocher en un clic

**Regles metier :**
- Utiliser `layer.setSubsetString()` -- meme pattern que le filtrage vectoriel
- Seules les classes effectivement presentes dans le nuage sont listees
- Codes ASPRS standards (0-18) avec labels lisibles

---

#### US-PC1.2 : Filtrage par attributs et elevation
**En tant que** utilisateur LiDAR, **je veux** filtrer mon nuage de points par plage de valeurs (elevation Z, intensite, numero de retour) **afin d'** isoler les points qui m'interessent pour mon analyse.

**Priorite** : SHOULD | **Effort** : S (3-5j) | **Sprint** : 4

**Criteres d'acceptation :**
- GIVEN une couche point cloud chargee
- WHEN je definis un filtre par plage (ex: Z entre 50 et 150, Intensity > 200)
- THEN `setSubsetString("Z > 50 AND Z < 150")` est applique
- AND je peux combiner avec le filtre classification (AND logique)
- AND les sliders/inputs refletent le min/max reel de l'attribut dans le nuage
- AND la mise a jour est interactive

---

#### US-PC1.3 : Filtrage combine multi-criteres PC
**En tant que** utilisateur LiDAR, **je veux** combiner filtres de classification, d'elevation et d'attributs **afin de** construire des requetes complexes.

**Priorite** : SHOULD | **Effort** : S (3-5j) | **Sprint** : 4

**Criteres d'acceptation :**
- GIVEN des filtres classification et attribut deja definis individuellement
- WHEN je les combine
- THEN le subset string combine est applique : `"Classification = 6 AND Z > 100 AND Intensity > 500"`
- AND chaque critere peut etre active/desactive independamment
- AND je peux sauvegarder/charger des combinaisons de filtres

---

### EPIC-PC2 : Point Cloud Avance

#### US-PC2.1 : Clip par polygone
**En tant que** utilisateur LiDAR, **je veux** decouper mon nuage de points selon un polygone vectoriel **afin d'** extraire les points d'une zone d'interet.

**Priorite** : COULD | **Effort** : L (8-12j) | **Sprint** : 5+

**Criteres d'acceptation :**
- GIVEN QGIS >= 3.32 avec PDAL Processing disponible
- WHEN je selectionne un polygone et lance le clip
- THEN les points a l'interieur du polygone sont extraits
- AND le resultat est enregistrable en LAZ/COPC
- AND sur QGIS < 3.32, cette fonctionnalite est grisee avec un message explicatif

---

#### US-PC2.2 : Export filtre
**En tant que** utilisateur LiDAR, **je veux** exporter les points filtres dans un nouveau fichier **afin de** partager ou traiter uniquement les donnees pertinentes.

**Priorite** : COULD | **Effort** : M (5-8j) | **Sprint** : 5+

**Criteres d'acceptation :**
- GIVEN un filtre PC actif
- WHEN je clique sur "Exporter nuage filtre"
- THEN les points filtres sont exportes en LAZ (option COPC si PDAL disponible)
- AND les attributs sont preserves
- AND un dialogue de progression est affiche

---

## SEQUENCAGE EN SPRINTS

### Sprint 0 -- Fondations (1.5 semaine)
| Story | Effort | Prerequis |
|-------|--------|-----------|
| US-R0.1 : Merge fondations raster | 2-3j | Aucun |
| US-R0.2 : Pass 3 filter_task.py | 2-3j | Aucun (parallele) |
| US-R0.3 : Cablage UI raster | 3-5j | US-R0.1 |

**Sortie** : Plugin avec panneau raster visible, filter_task < 3000 lignes, 311 tests passent.

### Sprint 1 -- Raster Sampling (1.5 semaine)
| Story | Effort | Prerequis |
|-------|--------|-----------|
| US-R1.2 : Info couche raster | 1-2j | US-R0.3 |
| US-R1.1 : Sampling par centroide | 3-5j | US-R0.3 |
| US-R1.3 : Sampling multi-bandes | 2-3j | US-R1.1 |

**Milestone** : **Alpha Raster**

### Sprint 2 -- Zonal Stats (2.5 semaines)
| Story | Effort | Prerequis |
|-------|--------|-----------|
| US-R2.1 : Calcul stats zonales | 8-10j | US-R1.1 |
| US-R2.2 : Filtrage par stat zonale | 5-7j | US-R2.1 |
| US-R2.3 : Histogramme | 3-5j | US-R2.1 |

**Milestone** : **Beta Raster** -- Beta teste

### Sprint 3 -- Highlight + PC Fondations (2.5 semaines)
| Story | Effort | Prerequis |
|-------|--------|-----------|
| US-R3.1 : Masquage dynamique | 5-8j | US-R2.2 |
| US-PC1.0 : Architecture PC | 3-5j | Aucun (parallele) |
| US-PC1.1 : Filtrage classification | 5-8j | US-PC1.0 |

**Milestone** : **Release Raster V1** + **Alpha Point Cloud**

### Sprint 4 -- PC Complet V1 (2 semaines)
| Story | Effort | Prerequis |
|-------|--------|-----------|
| US-PC1.2 : Filtrage attributs/Z | 3-5j | US-PC1.1 |
| US-PC1.3 : Filtrage combine | 3-5j | US-PC1.2 |
| US-R4.1 : Raster clip export | 5-7j | US-R2.2 (parallele) |

**Milestone** : **Release Point Cloud V1** → **FilterMate 5.0**

### Sprint 5+ -- Avance (futur)
| Story | Effort | Priorite |
|-------|--------|----------|
| US-PC2.1 : Clip par polygone | 8-12j | COULD |
| US-PC2.2 : Export filtre | 5-8j | COULD |
| EPIC-R5 : Multi-Band Composite | 8-12j | WON'T V1 |

---

## CRITERES DE RELEASE

### Alpha Raster (fin Sprint 1)
- [ ] Panneau dual mode fonctionnel (bascule vecteur/raster)
- [ ] Info couche raster affichee
- [ ] Sampling par centroide operationnel
- [ ] Zero regression sur le filtrage vectoriel
- [ ] Tests unitaires raster ecrits

### Beta Raster (fin Sprint 2)
- [ ] Zonal stats calculees en background
- [ ] Filtrage par stat zonale fonctionnel
- [ ] Histogramme interactif
- [ ] Performance : 100 polygones / 1 Go raster < 10s
- [ ] Beta teste et valide

### Release Raster V1 (fin Sprint 3)
- [ ] Highlight dynamique
- [ ] Documentation utilisateur raster
- [ ] Pas de bug bloquant ouvert

### Alpha Point Cloud (fin Sprint 3)
- [ ] Detection conditionnelle QGIS >= 3.26
- [ ] Filtrage par classification ASPRS
- [ ] Architecture hexagonale respectee
- [ ] Pas de crash sur QGIS < 3.26

### Release Point Cloud V1 (fin Sprint 4)
- [ ] Filtrage classification + attributs + elevation
- [ ] Combinaison multi-criteres
- [ ] Documentation utilisateur PC
- [ ] Pas de bug bloquant ouvert

### FilterMate 5.0 (globale)
- [ ] Raster V1 + Point Cloud V1 mergees
- [ ] Tous les tests passent (objectif : > 500 tests)
- [ ] filter_task.py < 3 000 lignes
- [ ] metadata.txt a jour (version, changelog)
- [ ] 0 bug bloquant, < 3 bugs mineurs connus

---

## RISQUES

| Risque | Probabilite | Impact | Mitigation |
|--------|-------------|--------|------------|
| Conflits cherry-pick branche raster | Moyenne | Medium | Cherry-pick fichier par fichier |
| Performance zonal stats gros rasters | Faible | Haute | Numpy + block loading, COG recommande |
| QGIS < 3.26 et features PC | Faible | Faible | Detection conditionnelle |
| Thread safety raster sampling | Moyenne | Haute | Stocker URI, recreer provider en thread |
| PDAL pas installe | Moyenne | Medium | Features PDAL marquees optionnelles |
| Scope creep multi-band | Haute | Medium | WON'T V1, fermement hors scope |

---

## EFFORT TOTAL

- Sprint 0-2 (MUST) : ~30-40 jours ouvrables
- Sprint 3-4 (SHOULD + COULD) : ~25-35 jours ouvrables
- **Total V1 : ~55-75 jours ouvrables (11-15 semaines)**

---

*Backlog genere par Jordan (PO) avec veille technologique Atlas, 2026-02-11*
*Rapport technique complet Atlas : `.serena/memories/atlas_raster_lidar_research_2026_02_11`*
