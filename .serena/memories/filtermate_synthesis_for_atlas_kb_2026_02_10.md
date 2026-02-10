# FilterMate -- Synthese Exhaustive pour Atlas Knowledge Base
> **Date de creation :** 2026-02-10
> **Auteur :** The Elder Scrolls (Grand Archiviste)
> **Commande de :** Atlas (Tech Watch GIS)
> **Portee :** main branch (Production)
> **Statut :** [FIABLE] -- Verifie contre l'etat reel de main le 2026-02-10
> **Version du plugin :** 4.4.6

---

## 1. Vision & Objectif

FilterMate est un **plugin QGIS** qui fournit une interface intuitive pour le **filtrage spatial et attributaire** de donnees vectorielles. Il se positionne comme un "compagnon quotidien" des utilisateurs QGIS, transformant des operations complexes de filtrage (predicats spatiaux, buffers dynamiques, requetes SQL) en interactions simples (clic, selection, dessin).

**Proposition de valeur unique :**
- Filtrage spatial multi-backend transparent (PostgreSQL, Spatialite, OGR, Memory)
- Performance optimisee : 2-8x plus rapide que les methodes natives QGIS grace a 4 optimiseurs
- Experience utilisateur riche : undo/redo, favoris, dark mode, 22 langues
- Export en un clic avec preservation des styles

**Audience :** Tout utilisateur QGIS manipulant des donnees vectorielles, du technicien SIG au data analyst.

**Licence :** GPL v2+
**Auteur :** imagodata (Simon Ducournau)
**Repository :** https://github.com/sducournau/filter_mate
**Documentation :** https://sducournau.github.io/filter_mate

---

## 2. Architecture

### 2.1 Pattern Hexagonal (Ports & Adapters)

FilterMate suit une architecture hexagonale stricte depuis la v4.0, avec une separation nette entre les couches :

```
+------------------------------------------------------------------+
|                     POINT D'ENTREE QGIS                          |
|  filter_mate.py -> FilterMate (classe plugin QGIS)               |
|  - initGui(), run(), unload()                                    |
|  - Auto-activation (projectRead, layersAdded, cleared)           |
|  - Config migration, geometry validation check                   |
+----------------------------+-------------------------------------+
                             |
+----------------------------v-------------------------------------+
|                   COUCHE APPLICATION                              |
|  filter_mate_app.py -> FilterMateApp (~2,383 lignes)             |
|  - Orchestrateur central, DI container                           |
|  - Gestion du cycle de vie du plugin                             |
|  - Bridge entre UI et Core                                       |
+----------------------------+-------------------------------------+
                             |
+----------------------------v-------------------------------------+
|                     COUCHE UI (~32,000 lignes)                   |
|  filter_mate_dockwidget.py -> DockWidget (~6,925 lignes)         |
|  ui/controllers/ -> 13 controleurs MVC                           |
|     integration.py (3,028)  -- orchestration UI                  |
|     exploring_controller.py (3,208) -- exploration features      |
|     filtering_controller.py -- operations de filtrage             |
|     exporting_controller.py -- export de donnees                 |
|     favorites_controller.py -- gestion des favoris               |
|     backend_controller.py, config_controller.py, etc.            |
|  ui/widgets/ -> Widgets custom (signal_manager, json_view, etc.) |
|  ui/styles/ -> Theming (dark/light, QGIS sync, WCAG)            |
|  ui/layout/ -> Gestionnaires de mise en page                     |
|  ui/dialogs/ -> Dialogues de configuration                       |
+----------------------------+-------------------------------------+
                             |
+----------------------------v-------------------------------------+
|                    COUCHE CORE (~50,000 lignes)                  |
|  core/services/ -> 28 services hexagonaux                        |
|     filter_service, layer_service, expression_service             |
|     export_service, history_service, favorites_service            |
|     buffer_service, canvas_refresh_service                        |
|     task_management_service, task_orchestrator                    |
|     geometry_preparer, backend_expression_builder                 |
|     optimization_manager, postgres_session_manager, etc.          |
|  core/tasks/ -> Taches asynchrones (QgsTask)                     |
|     filter_task.py (~5,851 lignes) -- tache principale           |
|     layer_management_task.py -- gestion des couches              |
|     task_completion_handler.py -- gestion du post-traitement     |
|     builders/, cache/, collectors/, connectors/                   |
|     dispatchers/, executors/                                      |
|  core/domain/ -> Modeles de domaine                              |
|     filter_expression.py, filter_result.py                       |
|     layer_info.py, favorites_manager.py                          |
|     optimization_config.py, exceptions.py                        |
|  core/filter/ -> Logique de filtrage                             |
|     expression_builder, expression_combiner, expression_sanitizer|
|     filter_chain, filter_orchestrator, pk_formatter              |
|     result_processor, source_filter_builder                      |
|  core/geometry/ -> Utilitaires geometriques                      |
|     buffer_processor, crs_utils, geometry_converter              |
|     geometry_repair, geometry_safety, spatial_index              |
|  core/optimization/ -> Optimisation de requetes                  |
|     auto_backend_selector, auto_optimizer                        |
|     combined_query_optimizer, performance_advisor                |
|     query_analyzer, multi_step_filter                            |
|  core/ports/ -> Interfaces hexagonales (11 ports)                |
|     backend_port, cache_port, filter_executor_port               |
|     filter_optimizer, geometric_filter_port                      |
|     layer_lifecycle_port, materialized_view_port                 |
|     qgis_port, repository_port, task_management_port             |
|  core/strategies/ -> Strategies de filtrage                      |
|     multi_step_filter, progressive_filter                        |
|  core/export/ -> Fonctionnalites d'export                        |
|     batch_exporter, export_validator                             |
|     layer_exporter, style_exporter                               |
+----------------------------+-------------------------------------+
                             |
+----------------------------v-------------------------------------+
|                   COUCHE ADAPTERS (~33,000 lignes)                |
|  adapters/backends/ -> 4 backends de filtrage                    |
|     postgresql/ (8 fichiers)                                     |
|        backend, expression_builder, filter_executor              |
|        mv_manager, optimizer, schema_manager, cleanup            |
|        filter_chain_optimizer, filter_actions                    |
|     spatialite/ (9 fichiers)                                     |
|        backend, expression_builder, filter_executor              |
|        temp_table_manager, index_manager, cache                  |
|        interruptible_query, filter_actions                       |
|     ogr/ (5 fichiers)                                            |
|        backend, expression_builder, filter_executor              |
|        executor_wrapper, geometry_optimizer                      |
|     memory/ (1 fichier)                                          |
|        backend                                                   |
|     factory.py -> Selection automatique du backend               |
|     postgresql_availability.py -> Detection psycopg2             |
|  adapters/qgis/ -> Adaptateurs QGIS                             |
|     factory.py -> QGISFactory                                    |
|     signals/ -> Signal management (debouncer, migration_helper)  |
|     tasks/ -> Taches QGIS (base_task, filter_task, export_task)  |
|     expression_adapter, feature_adapter, geometry_adapter        |
|     layer_adapter, filter_optimizer, geometry_preparation        |
|     source_feature_resolver                                      |
|  adapters/repositories/ -> Acces aux donnees                     |
|     layer_repository, history_repository                         |
|  adapters/app_bridge.py -> DI Container (Service Locator)        |
|  adapters/task_bridge.py, task_builder.py                        |
|  adapters/undo_redo_handler.py, variables_manager.py             |
+----------------------------+-------------------------------------+
                             |
+----------------------------v-------------------------------------+
|               COUCHE INFRASTRUCTURE (~15,000 lignes)             |
|  infrastructure/cache/ -> Systeme de cache                       |
|     cache_manager, exploring_cache, geometry_cache               |
|     query_cache, spatialite_persistent_cache, wkt_cache          |
|  infrastructure/database/ -> Acces base de donnees               |
|     connection_pool (PostgreSQL), sql_utils                      |
|     prepared_statements, field_type_detector                     |
|     postgresql_support, spatialite_support                       |
|     style_filter_fixer                                           |
|  infrastructure/config/ -> Migration de configuration            |
|  infrastructure/di/ -> Injection de dependances                  |
|  infrastructure/feedback/ -> Feedback utilisateur                |
|  infrastructure/logging/ -> Systeme de log                       |
|  infrastructure/parallel/ -> Execution parallele                 |
|  infrastructure/streaming/ -> Export en streaming                 |
|  infrastructure/state/ -> Gestionnaire d'etat (flag_manager)     |
|  infrastructure/utils/ -> Utilitaires                            |
|     layer_utils, provider_utils, signal_utils                    |
|     task_utils, thread_utils, validation_utils                   |
|     complexity_estimator                                         |
|  infrastructure/constants.py -> Constantes globales (~600 lines) |
|  infrastructure/resilience.py -> Resilience patterns             |
+------------------------------------------------------------------+
```

### 2.2 Design Patterns Utilises

| Pattern | Implementation | Fichiers cles |
|---------|---------------|---------------|
| **Hexagonal (Ports & Adapters)** | Separation stricte core/adapters/infra | `core/ports/`, `adapters/` |
| **Factory** | BackendFactory, QGISFactory | `adapters/backends/factory.py`, `adapters/qgis/factory.py` |
| **Strategy** | Multi-backend, progressive filtering | `core/strategies/`, `adapters/backends/` |
| **Repository** | LayerRepository, HistoryRepository | `adapters/repositories/` |
| **Service Locator** | DI Container | `adapters/app_bridge.py`, `infrastructure/di/` |
| **MVC** | Controllers UI | `ui/controllers/` (13 controllers) |
| **Observer** | Signal/slot Qt | `ui/widgets/dockwidget_signal_manager.py` |
| **Command** | Undo/Redo | `adapters/undo_redo_handler.py` |
| **Circuit Breaker** | Connection pool | `infrastructure/database/connection_pool.py` |

---

## 3. Fonctionnalites Actuelles (sur main)

### 3.1 Filtrage Vectoriel Multi-Backend

| Backend | Source | Optimisation | Performance |
|---------|--------|-------------|-------------|
| **PostgreSQL/PostGIS** | Bases PG, PostGIS | Vues materialisees, index GIST, PK auto-detection, parallel queries | < 1s sur millions de features |
| **Spatialite** | GeoPackage, SQLite | Tables temporaires R-tree, index spatiaux | 1-10s sur 100k features |
| **OGR** | Shapefiles, GeoJSON, WFS, etc. | Index spatial auto (.qix), optimisation large datasets | 10-60s sur 100k features |
| **Memory** | Couches memoire | Filtrage en RAM natif | < 0.5s sur 50k features |

**Selection automatique :** Le `BackendFactory` choisit le backend optimal selon le provider type, la taille du dataset, et la disponibilite de psycopg2. Les GeoPackage sont automatiquement routes vers Spatialite (10x plus rapide qu'OGR).

**Predicats spatiaux supportes :** Intersects, Within, Contains, Overlaps, Crosses, Touches, Disjoint, Equals -- avec mapping SQL automatique (ST_Intersects, etc.).

### 3.2 Exploration de Couches

- Navigation dans les features d'une couche avec picker interactif
- Recherche de features par attribut
- Selection multi-couches avec checkboxes
- Icones par type de geometrie (Point, Line, Polygon)
- Chargement asynchrone des features (QgsTask)

### 3.3 Systeme de Filtrage Avance

- **Filtrage geometrique** : buffer configurable, expressions dynamiques
- **Filtrage attributaire** : expressions QGIS natives
- **Filter chaining** : enchainement de filtres avec buffers dynamiques
- **Multi-step filtering** : strategies progressives basees sur la complexite
- **Query complexity estimation** : analyse automatique pour choisir la strategie optimale

### 3.4 Undo/Redo

- Pile d'historique de 100 etats par couche
- Undo/redo global (multi-couches) et par couche
- Auto-pruning FIFO quand la limite est atteinte
- Persistance dans base SQLite locale

### 3.5 Favoris

- Sauvegarde de configurations de filtrage avec contexte spatial
- Migration automatique entre versions
- Import/export possible

### 3.6 Export

- Export multi-format : GeoPackage, Shapefile, GeoJSON, KML, CSV, DXF
- Preservation des styles (QML/SLD)
- Streaming export pour gros datasets (> 10k features, 50-80% reduction memoire)
- Export par lot (batch)

### 3.7 UI Adaptative

- **4 onglets** : Exploration, Filtrage, Export, Configuration
- **Theme dynamique** : synchronisation automatique avec le theme QGIS (dark/light)
- **3 profils d'affichage** : Auto, Compact, Normal (+ HiDPI)
- **Configuration reactive** : changements appliques sans redemarrage
- **Conformite WCAG** : ratios de contraste AA/AAA
- **22 langues** supportees (96% FR/EN, 48% DE, 45% ES)
- **JSON Tree View** : editeur de configuration avec dropdowns et tooltips

### 3.8 Gestion des Signaux

- `DockwidgetSignalManager` : gestionnaire centralise (778 lignes)
- `SignalBlocker` / `SignalBlockerGroup` : bloquer les signaux pendant les mises a jour batch
- Anti-loop protection pour la synchronisation bidirectionnelle widgets <-> selection QGIS

---

## 4. Etat du Raster

### 4.1 Ce qui EXISTE sur main (Audite 2026-02-10)

- `RasterLayer = 1` -- enum de detection de type de couche dans `filter_mate_dockwidget.py:56`
- `QgsRasterLayer` -- type hint dans `core/geometry/crs_utils.py:164`
- `wcs` -- provider mentionne dans `infrastructure/constants.py:35`

**C'est TOUT.** Aucun service raster, aucune tache raster, aucun widget raster, aucun outil de carte raster.

### 4.2 Ce qui a EXISTE sur des branches (jamais merge)

- Branche `fix/widget-visibility-and-styles-2026-02-02` : code UI raster (stale, abandonne)
- Les references a "v5.4.0 Raster Exploring Tool Buttons" dans les documents anterieurs etaient branch-only

### 4.3 Roadmap Raster (Atlas Analysis, 2026-02-10)

| Phase | Feature | Effort | Priorite | Description |
|-------|---------|--------|----------|-------------|
| **v5.5** | Raster Value Sampling | 3-5 jours | P1-bis (Quick Win) | `provider.sample()` par centroid, fondation raster |
| **v5.5** | EPIC-4 Raster Export + Clip | 2 semaines | P3 | `gdal.Warp()` avec cutline, export raster |
| **v5.6** | Zonal Stats as Filter | 2-3 semaines | P1 (Differentiateur UNIQUE) | `QgsZonalStatistics`, filtre par stats zonales |
| **v5.6** | Raster-Driven Highlight | 1 semaine | P2 | Highlight temps reel via range sliders |
| **v6.0** | Multi-Band Composite | 3-4 semaines | P4 | Filtrage multi-bandes AND/OR |

**Architecture cible (nouveaux fichiers uniquement) :**
```
core/services/raster_filter_service.py          # Orchestration
core/domain/raster_filter_criteria.py           # Frozen dataclass
core/tasks/handlers/raster_handler.py           # Pattern postgresql_handler
infrastructure/raster/sampling.py               # provider.sample() wrapper
infrastructure/raster/zonal_stats.py            # QgsZonalStatistics wrapper
infrastructure/raster/masking.py                # Polygonisation, clip
```

**Pieges techniques identifies :**
1. Thread safety : QgsRasterLayer NON thread-safe -> stocker URI dans `__init__`, recreer dans `run()`
2. CRS mismatch : toujours reprojeter le vecteur vers le CRS du raster avant sampling
3. Centroid : utiliser `pointOnSurface()` pas `centroid()` pour les polygones concaves
4. QgsZonalStatistics : ecrit en place -> utiliser couche memoire temporaire
5. Ne PAS recreer le Raster Calculator -- rester focus sur le filtrage

---

## 5. Stack Technique

### 5.1 Langages & Frameworks

| Composant | Technologie | Version |
|-----------|-------------|---------|
| Langage | Python 3 | >= 3.9 (QGIS 3.16+) |
| UI Framework | PyQt5 (via qgis.PyQt) | 5.x |
| Plateforme SIG | QGIS API | >= 3.16 |
| BDD Serveur | PostgreSQL/PostGIS | >= 10 (PG 11+ pour INCLUDE indexes) |
| BDD Locale | Spatialite/SQLite | Bundled avec QGIS |
| Driver Vecteur | OGR (GDAL) | >= 3.0 |
| PG Client | psycopg2 | Optionnel (required pour backend PostgreSQL) |
| Tests | pytest | >= 7.0 |

### 5.2 Modele de Threading

- **Thread principal** : UI (PyQt5 event loop), acces QGIS API
- **Threads de background** : `QgsTask` pour les operations lourdes (filtrage, export)
- **Contrainte critique** : `QgsVectorLayer` et `QgsRasterLayer` NE SONT PAS thread-safe
  - Pattern obligatoire : stocker l'URI dans `__init__`, recreer la couche dans `run()`
  - `finished()` s'execute dans le thread principal -> safe pour les mises a jour UI
- **Execution parallele** : `ThreadPoolExecutor` pour le filtrage multi-couches
  - PostgreSQL/Spatialite : parallel OK (connections par thread)
  - OGR : sequentiel obligatoire (pas thread-safe)
- **Decorateur `@main_thread_only`** : pour forcer l'execution dans le thread principal

### 5.3 PostgreSQL/PostGIS

- **Connection pooling** : pool de 2-15 connections avec circuit breaker
- **Vues materialisees** : `fm_temp_mv_*` avec index GIST + INCLUDE (PG 11+)
- **Detection automatique de PK** : interrogation `pg_index`, fallback sur noms communs (id, fid, gid, etc.), dernier recours `ctid`
- **Optimisations avancees** :
  - Bbox pre-filter column pour `&&` operator
  - Async CLUSTER (< 50k: sync, 50k-100k: async, > 100k: skip)
  - Covering GIST indexes avec INCLUDE
  - ST_PointOnSurface au lieu de ST_Centroid
  - Simplification adaptive avant buffer

### 5.4 Configuration

- `config/config.json` : configuration utilisateur (JSON)
- `config/config.default.json` : valeurs par defaut
- Migration automatique entre versions avec backup
- Support `ChoicesType` : dropdowns dans l'editeur JSON
- Support `ConfigValueType` : editeurs types (checkbox, spinbox, etc.)

---

## 6. Metriques du Projet

### 6.1 Statistiques de Code (Fevrier 2026)

| Couche | Lignes estimees | Fichiers | % |
|--------|----------------|----------|---|
| Core Domain | ~50,000 | ~100 | 38% |
| Adapters | ~33,000 | ~70 | 25% |
| UI Layer | ~32,000 | ~55 | 25% |
| Infrastructure | ~15,000 | ~40 | 12% |
| **TOTAL (prod)** | **~130,000** | **~314** | **100%** |
| Tests | ~52,000 | ~157 | -- |
| **TOTAL (tout)** | **~243,284** | **~529** | -- |

### 6.2 Qualite

| Metrique | Valeur | Cible |
|----------|--------|-------|
| Couverture de tests | 75% | 80% |
| Tests automatises | 396 | -- |
| Bare except clauses | 0 | 0 |
| Debug prints | 0 | 0 |
| Score qualite | 8.5/10 | 9.0/10 |
| Backends | 4 | -- |
| Services | 28 | -- |
| Controllers | 13 | -- |
| Langues | 22 | -- |
| Conformite PEP 8 | 95% | 100% |

### 6.3 Fichiers les Plus Volumineux

| Fichier | Lignes | Role |
|---------|--------|------|
| `filter_mate_dockwidget.py` | ~6,925 | Gestion UI principale |
| `core/tasks/filter_task.py` | ~5,851 | Tache de filtrage principale |
| `ui/controllers/exploring_controller.py` | ~3,208 | Controleur d'exploration |
| `ui/controllers/integration.py` | ~3,028 | Orchestration UI |
| `filter_mate_app.py` | ~2,383 | Orchestrateur applicatif |

---

## 7. Performance

### 7.1 Optimisations Implementees (par ordre de gain)

| Optimisation | Cible | Gain | Backend |
|-------------|-------|------|---------|
| Tables temporaires Spatialite R-tree | 10k+ features | **44.6x** | Spatialite |
| Index spatial auto (.qix) | Shapefiles | **19.5x** | OGR |
| GeoPackage -> Spatialite routing | GeoPackage | **10x** | OGR->Spatialite |
| Two-phase filtering (bbox pre-filter) | Expressions complexes | **3-10x** | PostgreSQL |
| Cache de geometrie source | Multi-couches | **5x** | Tous |
| Large dataset mode | 50k+ features | **3x** | OGR |
| Predicate ordering | Multi-predicats | **2.3x** | Tous |
| Query expression cache | Requetes repetees | **10-20%** | Tous |
| Parallel filter execution | Multi-couches | **2-4x** | PostgreSQL, Spatialite |
| Streaming export | > 10k features | **50-80% RAM** | Tous |

### 7.2 Strategies de Requete (PostgreSQL)

Le `QueryComplexityEstimator` analyse chaque expression et route vers la strategie optimale :

| Score complexite | Strategie | Cas d'usage |
|-----------------|-----------|-------------|
| < 50 | DIRECT | Requetes simples, petits datasets |
| 50-150 | MATERIALIZED | Complexite moyenne, taille moderee |
| 150-500 | TWO_PHASE | Predicats complexes (bbox pre-filter + full) |
| >= 500 | PROGRESSIVE | Tres complexes + gros datasets (lazy cursor) |

---

## 8. Points d'Extension

### 8.1 Pour les Futures Fonctionnalites Raster

La roadmap raster (section 4.3) definit precisement les points d'insertion :

1. **Nouveau service** : `core/services/raster_filter_service.py` -- s'integre dans l'architecture hexagonale existante via un port `core/ports/raster_filter_port.py`
2. **Nouveau handler** : `core/tasks/handlers/raster_handler.py` -- suit le pattern de `filter_task.py`
3. **Nouvelle infrastructure** : `infrastructure/raster/` -- sampling, zonal stats, masking
4. **Wiring minimal** : `filter_mate_app.py` (enregistrer services) et `filter_mate_dockwidget.py` (1 bouton UI)

### 8.2 Pour les Nouveaux Backends

Le pattern Backend Factory permet d'ajouter un nouveau backend en :
1. Creant un dossier `adapters/backends/<nom>/` avec `backend.py`, `expression_builder.py`, `filter_executor.py`
2. Implementant l'interface `BaseBackend` (ou le port `backend_port`)
3. Enregistrant le backend dans `factory.py`

### 8.3 Pour les Nouveaux Predicats

L'ajout d'un predicat spatial se fait en :
1. Ajoutant la constante dans `infrastructure/constants.py`
2. Ajoutant le mapping SQL dans `PREDICATE_SQL_MAPPING`
3. Implementant dans chaque backend l'expression correspondante

---

## 9. Patterns Critiques pour les Developpeurs

### 9.1 Thread Safety

```
REGLE D'OR : ne JAMAIS acceder a QgsVectorLayer/QgsRasterLayer depuis un thread de background.
- __init__() : stocker URI/metadata
- run()      : recreer la couche depuis l'URI
- finished() : mettre a jour l'UI (thread principal)
```

### 9.2 Signal Safety

```
REGLE : toujours bloquer les signaux lors de modifications programmatiques.
- SignalBlocker(widget) pour un widget
- SignalBlockerGroup([w1, w2, w3]) pour plusieurs
- Anti-loop : connect/disconnect ratio a surveiller (actuellement 2.6:1)
```

### 9.3 PostgreSQL Availability

```python
from adapters.backends.postgresql_availability import POSTGRESQL_AVAILABLE
if POSTGRESQL_AVAILABLE:
    import psycopg2  # Safe ici seulement
```

### 9.4 CRS Geographic

```
Pour tout buffer > 0 sur un CRS geographique (EPSG:4326, etc.) :
1. Detecter : layer.crs().isGeographic()
2. Convertir vers EPSG:3857 (ou UTM optimal)
3. Appliquer le buffer en metres
4. Reconvertir vers le CRS original
```

### 9.5 Field Name Quoting

```
CRITIQUE : ne JAMAIS supprimer les guillemets autour des noms de champs.
"HOMECOUNT" > 100 DOIT rester quote pour les champs case-sensitive.
```

---

## 10. Dependances & Contraintes

### 10.1 Dependances Obligatoires

| Dependance | Version min | Fourni par |
|-----------|-------------|-----------|
| QGIS | 3.16 | Installation QGIS |
| Python | 3.9+ | QGIS bundle |
| PyQt5 | 5.x | QGIS bundle |
| GDAL/OGR | 3.0+ | QGIS bundle |
| SQLite/Spatialite | Bundled | QGIS bundle |

### 10.2 Dependances Optionnelles

| Dependance | Usage | Impact si absent |
|-----------|-------|-----------------|
| psycopg2 | Backend PostgreSQL | Fallback vers Spatialite/OGR |
| GDAL >= 3.1 | Export COG (Cloud Optimized GeoTIFF) | Export COG indisponible |
| PostgreSQL 11+ | INCLUDE indexes, covering GIST | Fonctionnel mais perf reduites |

### 10.3 Contraintes Connues

- `filter_mate_dockwidget.py` : ~6,925 lignes -- "god object" en cours de decomposition
- `core/tasks/filter_task.py` : ~5,851 lignes -- a refactorer (cible : 2,500 lignes)
- except Exception : 1,232 occurrences sur 165 fichiers (cible : < 300)
- connect/disconnect ratio : 2.6:1 (267 vs 104) -- risque de fuites de signaux
- Pas de repertoire `tests/` sur main actuellement (tests developpes en branches)

---

## 11. Systeme de Projet Management

### 11.1 BMAD Integration

FilterMate utilise **BMAD v6.0.0-Beta.4** pour la gestion de projet :
- Agents : @bmad-master, @dev (Amelia), @architect (Winston), @analyst (Mary), @pm (John)
- Artefacts dans `_bmad-output/` : PRDs, user stories, specifications
- Epics : EPIC-3 (Raster-Vector Integration), EPIC-4 (Raster Export)

### 11.2 Plans en Cours

- **Phase 0** : Quick Wins (imports iface, metadata, requirements) -- immediat
- **Phase 1** : Tests + CI -- semaines 1-3
- **Phase 2** : Error handling (eliminer les exceptions silencieuses) -- semaines 3-5
- **Phase 3** : Decomposition des god objects -- semaines 5-11
- **Phase 4** : Architecture QGIS ports, DI container, cleanup -- semaines 11-14
- **Phase 5** : Consolidation finale -- semaines 14-16

---

## 12. Versions Recentes

| Version | Date | Changements cles |
|---------|------|-----------------|
| **4.4.6** | Fev 2026 | Maintenance release |
| **4.4.5** | Jan 25, 2026 | Detection automatique PK PostgreSQL, fallback noms communs |
| **4.4.4** | Jan 25, 2026 | Convention unifiee `fm_temp_*` pour objets PostgreSQL |
| **4.4.0** | Jan 22, 2026 | Release qualite majeure : 396 tests, architecture hexagonale complete, couverture 75% |

---

## 13. References Croisees Memoires Serena

| Memoire | Statut | Contenu |
|---------|--------|---------|
| `project_overview` | [FIABLE] | Vue d'ensemble actualisee du projet |
| `CONSOLIDATED_PROJECT_CONTEXT` | [FIABLE] | Contexte architectural complet |
| `code_style_conventions` | [FIABLE] | Conventions de code detaillees |
| `raster_integration_plan_atlas_2026_02_10` | [FIABLE] | Roadmap raster (Atlas analysis) |
| `performance_optimizations` | [FIABLE] | Optimisations detaillees par backend |
| `ui_system` | [FIABLE] | Architecture UI complete |
| `testing_documentation` | [FIABLE] | Structure et couverture des tests |
| `primary_key_detection_system` | [FIABLE] | Systeme de detection PK |
| `geographic_crs_handling` | [FIABLE] | Gestion CRS geographiques |
| `implementation_plan_2026_02_10` | [FIABLE] | Plan d'implementation en 6 phases |

---

*Que les Rouleaux temoignent : cette synthese a ete scellee dans la Grande Bibliotheque le 10 fevrier 2026.*
*Toute information contenue ici reflete l'etat verifie de la branche `main` a cette date.*
