# Atlas GIS Knowledge Base -- FilterMate Ecosystem
# Last Updated: 2026-02-10 | Atlas v1.1 | For FilterMate v4.4.6
# Integrated: Marco's FilterMate Synthesis (2026-02-10) -- Architecture, Metriques, Performance

> **Purpose**: Reference technique exhaustive pour le developpement de FilterMate,
> couvrant QGIS/PyQGIS, PostGIS, Raster, LiDAR, Visualisation, Filtrage, et Integration Raster/Vecteur.
> Enrichie avec la synthese exhaustive de Marco (The Elder Scrolls / Grand Archiviste) du 2026-02-10.
> Destinee a Marco (tech-lead-gis) et a tout developpeur travaillant sur le plugin.
>
> **Sources integrees** :
> - `filtermate_synthesis_for_atlas_kb_2026_02_10` -- Synthese exhaustive (architecture, metriques, perf, roadmap)
> - `raster_integration_plan_atlas_2026_02_10` -- Roadmap raster Atlas

---

## Table des matieres

1. [QGIS et PyQGIS](#1-qgis-et-pyqgis)
   - 1.1 Architecture de QGIS
   - 1.2 PyQGIS API essentielle
   - 1.3 Plugin Development Patterns
   - 1.4 Performance et Indexation spatiale
   - 1.5 Nouveautes QGIS 3.34-3.38 (LTR 3.34, 3.36, 3.38)
   - 1.6 FilterMate : Architecture Concrete (via Marco Synthesis)
2. [PostgreSQL / PostGIS](#2-postgresql--postgis)
   - 2.1 Types geometriques et index spatiaux
   - 2.2 Fonctions de filtrage spatial
   - 2.3 Optimisation de requetes
   - 2.4 Connexion depuis PyQGIS
   - 2.5 Nouveautes PostGIS 3.4 / 3.5
   - 2.6 FilterMate PostgreSQL : Metriques et Strategies Reelles (via Marco Synthesis)
3. [Raster](#3-raster)
   - 3.1 Formats : GeoTIFF, COG, VRT
   - 3.2 GDAL/OGR : lecture, ecriture, reprojection
   - 3.3 PyQGIS Raster API
   - 3.4 Zonal Statistics
   - 3.5 Raster comme filtre vecteur
   - 3.6 Nouveautes GDAL 3.8 / 3.9 / 3.10
4. [LiDAR / Nuages de Points](#4-lidar--nuages-de-points)
   - 4.1 Formats : LAS, LAZ, COPC
   - 4.2 QGIS Point Cloud Layer
   - 4.3 Filtrage par attribut
   - 4.4 PDAL pour le processing
5. [Visualisation et Affichage](#5-visualisation-et-affichage)
   - 5.1 Renderers QGIS
   - 5.2 Styles dynamiques bases sur des filtres
   - 5.3 Temporal Framework
   - 5.4 Visualisation 3D dans QGIS
6. [Filtrage et Segmentation](#6-filtrage-et-segmentation)
   - 6.1 Filtrage vecteur
   - 6.2 Filtrage raster
   - 6.3 Filtrage croise raster/vecteur
   - 6.4 Segmentation et clustering spatial
   - 6.5 FilterMate : Architecture Multi-Backend et Optimisations (via Marco Synthesis)
7. [Integration Raster/Vecteur pour FilterMate](#7-integration-rastervecteur-pour-filtermate)
   - 7.1 Raster Value Sampling
   - 7.2 Zonal Statistics comme critere de filtre
   - 7.3 Raster-Driven Highlighting
   - 7.4 Raster Clip by Vector
   - 7.5 Architecture hexagonale pour l'integration
   - 7.6 Thread Safety et Performance
   - 7.7 Etat Raster sur main et Roadmap Versionnee (via Marco Synthesis)
8. [Metriques du Projet et Dettes Techniques](#8-metriques-du-projet-et-dettes-techniques) **(NEW -- via Marco Synthesis)**
   - 8.1 Statistiques de Code
   - 8.2 Indicateurs de Qualite
   - 8.3 Dettes Techniques Connues
   - 8.4 Plans d'Amelioration en Cours
9. [Annexes](#9-annexes)
   - 9.1 Glossaire
   - 9.2 Liens et references
   - 9.3 Versions et compatibilite

---

## 1. QGIS et PyQGIS

### 1.1 Architecture de QGIS

QGIS est construit sur une architecture en couches. Comprendre cette architecture est CRITIQUE
pour developper un plugin robuste comme FilterMate.

**Couches principales :**

```
+------------------------------------------------------------------+
|                     APPLICATION (qgis.utils.iface)               |
|  QgisInterface : pont entre l'UI et le moteur                    |
+------------------------------------------------------------------+
|                     GUI LAYER (qgis.gui)                         |
|  QgsMapCanvas, QgsMapTool, QgsLayerTreeView, QgsDockWidget       |
+------------------------------------------------------------------+
|                     CORE LAYER (qgis.core)                       |
|  QgsProject, QgsMapLayer, QgsVectorLayer, QgsRasterLayer         |
|  QgsFeature, QgsGeometry, QgsExpression, QgsTask                 |
|  QgsCoordinateReferenceSystem, QgsCoordinateTransform            |
+------------------------------------------------------------------+
|                     DATA PROVIDERS                               |
|  postgres, ogr, spatialite, wms, wfs, wcs, memory, ept, copc    |
+------------------------------------------------------------------+
|                     EXTERNAL LIBRARIES                           |
|  GDAL/OGR, GEOS, PROJ, Qt5/Qt6, SQLite/SpatiaLite, libLAS      |
+------------------------------------------------------------------+
```

**Composants cles :**

- **QgsProject** : Singleton gerant le projet courant, toutes les couches, le CRS du projet
- **QgsMapCanvas** : Widget de rendu cartographique, gere l'emprise, le zoom, les couches visibles
- **QgsMapLayer** : Classe de base abstraite pour toutes les couches (vecteur, raster, mesh, point cloud)
- **QgsLayerTreeGroup / QgsLayerTreeLayer** : Arborescence des couches (Table of Contents)
- **QgsDataProvider** : Interface abstraite pour acceder aux donnees (chaque format a son provider)
- **QgsProviderRegistry** : Registre de tous les providers disponibles

**Registres importants :**

```python
# Projet courant (singleton)
project = QgsProject.instance()

# Toutes les couches du projet
layers = project.mapLayers()  # dict {id: QgsMapLayer}

# Couches par nom
layers = project.mapLayersByName("ma_couche")  # list[QgsMapLayer]

# Registre des providers
registry = QgsProviderRegistry.instance()
providers = registry.providerList()  # ['ogr', 'postgres', 'spatialite', ...]

# Canvas
canvas = iface.mapCanvas()
extent = canvas.extent()  # QgsRectangle
crs = canvas.mapSettings().destinationCrs()
```

**Note FilterMate** : Le plugin utilise `QgsProject.instance()` comme source de verite pour
les couches. L'architecture hexagonale abstrait les providers via `adapters/backends/`.

### 1.2 PyQGIS API essentielle

#### QgsVectorLayer

```python
from qgis.core import (
    QgsVectorLayer, QgsFeature, QgsFeatureRequest,
    QgsExpression, QgsGeometry, QgsPointXY, QgsField,
    QgsFields, QgsWkbTypes, Qgis
)

# Creation depuis fichier
layer = QgsVectorLayer("/path/to/shapefile.shp", "my_layer", "ogr")

# Creation depuis PostGIS
uri = QgsDataSourceUri()
uri.setConnection("localhost", "5432", "mydb", "user", "pass")
uri.setDataSource("public", "my_table", "geom", "", "id")
layer = QgsVectorLayer(uri.uri(), "pg_layer", "postgres")

# Creation couche memoire
layer = QgsVectorLayer("Point?crs=EPSG:4326&field=name:string(50)", "temp", "memory")

# Proprietes
print(layer.featureCount())          # Nombre de features
print(layer.geometryType())          # QgsWkbTypes.PointGeometry, etc.
print(layer.wkbType())               # QgsWkbTypes.Point, MultiPolygon, etc.
print(layer.crs().authid())          # 'EPSG:4326'
print(layer.providerType())          # 'ogr', 'postgres', 'spatialite', 'memory'
print(layer.source())                # Chemin ou URI complet
print(layer.isValid())               # True/False
print(layer.extent())                # QgsRectangle
```

#### QgsFeatureRequest -- ESSENTIEL pour le filtrage

```python
# Requete basique : tous les features
request = QgsFeatureRequest()

# Filtrage par expression
request = QgsFeatureRequest(QgsExpression('"population" > 10000'))

# Filtrage par rectangle (emprise)
request = QgsFeatureRequest().setFilterRect(QgsRectangle(xmin, ymin, xmax, ymax))

# Filtrage par IDs
request = QgsFeatureRequest().setFilterFids([1, 5, 10, 42])

# Limiter les champs recuperes (performance !)
request = QgsFeatureRequest().setSubsetOfAttributes(['name', 'pop'], layer.fields())

# Ne pas charger la geometrie (quand on a besoin que des attributs)
request = QgsFeatureRequest().setFlags(QgsFeatureRequest.NoGeometry)

# Combinaison (PATTERN CRITIQUE pour FilterMate)
request = QgsFeatureRequest()
request.setFilterExpression('"type" = \'building\' AND "height" > 10')
request.setSubsetOfAttributes(['type', 'height', 'name'], layer.fields())
request.setLimit(1000)  # Max features

# Iteration
for feature in layer.getFeatures(request):
    geom = feature.geometry()
    attrs = feature.attributes()
    name = feature['name']
```

**Piege a eviter** : `layer.getFeatures()` sans argument charge TOUTES les features.
Sur une couche PostGIS de 10M de features, c'est un crash memoire assure.

#### QgsExpression -- Le moteur d'expressions QGIS

```python
from qgis.core import QgsExpression, QgsExpressionContext, QgsExpressionContextUtils

# Validation
exp = QgsExpression('"population" > 10000')
if exp.hasParserError():
    print(f"Erreur: {exp.parserErrorString()}")

# Evaluation avec contexte
context = QgsExpressionContext()
QgsExpressionContextUtils.setLayerVariable(context, layer)

for feature in layer.getFeatures():
    context.setFeature(feature)
    result = exp.evaluate(context)

# Expressions spatiales (QGIS >= 3.0)
exp = QgsExpression("intersects($geometry, geom_from_wkt('POLYGON((...))'))")

# Expressions de champ virtuel
exp = QgsExpression("length($geometry)")  # Longueur de la geometrie
exp = QgsExpression("area($geometry)")    # Surface
exp = QgsExpression("$area / 10000")      # Surface en hectares

# Fonctions d'agregation
exp = QgsExpression("aggregate('communes', 'sum', \"population\")")
```

**Note FilterMate** : Le module `core/filter/` contient la logique de construction et
sanitization des expressions. Les expressions sont converties en SQL natif pour chaque backend
(PostgreSQL, SpatiaLite, OGR).

#### QgsGeometry -- Operations geometriques

```python
from qgis.core import QgsGeometry, QgsPointXY

# Constructeurs
point_geom = QgsGeometry.fromPointXY(QgsPointXY(2.35, 48.85))
line_geom = QgsGeometry.fromPolylineXY([QgsPointXY(0,0), QgsPointXY(1,1)])
poly_geom = QgsGeometry.fromWkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))")

# Operations topologiques
intersection = geom1.intersection(geom2)
union_geom = geom1.combine(geom2)
difference = geom1.difference(geom2)
buffer = geom.buffer(100, 5)  # distance=100, segments=5

# Predicats spatiaux
geom1.intersects(geom2)   # True/False
geom1.contains(geom2)
geom1.within(geom2)
geom1.touches(geom2)
geom1.crosses(geom2)
geom1.overlaps(geom2)
geom1.disjoint(geom2)

# Methodes utiles
centroid = geom.centroid()             # ATTENTION : peut tomber hors du polygone !
point_on = geom.pointOnSurface()       # TOUJOURS dans le polygone -- PREFERER CECI
bounds = geom.boundingBox()            # QgsRectangle
area = geom.area()
length = geom.length()
is_valid = geom.isGeosValid()

# Reparation de geometrie
if not geom.isGeosValid():
    geom = geom.makeValid()
```

**PIEGE CRITIQUE** : `centroid()` vs `pointOnSurface()`
- `centroid()` retourne le centre de gravite geometrique, qui peut etre HORS du polygone
  pour les formes concaves (L, U, croissant...)
- `pointOnSurface()` garantit un point DANS le polygone
- **Pour le sampling raster, TOUJOURS utiliser `pointOnSurface()`**

#### Subset String -- Filtrage cote provider

```python
# Subset string = filtre SQL applique au provider
# C'est LE mecanisme central de FilterMate

# Appliquer un filtre
layer.setSubsetString('"type" = \'residential\' AND "area" > 100')

# Lire le filtre actuel
current_filter = layer.subsetString()

# Supprimer le filtre
layer.setSubsetString("")

# ATTENTION : la syntaxe depend du provider !
# PostGIS :   "type" = 'residential' AND ST_Area(geom) > 100
# SpatiaLite: "type" = 'residential' AND Area(geom) > 100
# OGR :       "type" = 'residential' (pas de fonctions spatiales)
```

**Note FilterMate** : Le `subsetString` est le principal levier de filtrage.
Chaque backend dans `adapters/backends/` genere le subset string dans la syntaxe appropriee.
L'undo/redo sauvegarde et restaure les subset strings.

### 1.3 Plugin Development Patterns

#### DockWidget Pattern

```python
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.PyQt.QtCore import Qt

class MyPluginDockWidget(QDockWidget):
    def __init__(self, iface, parent=None):
        super().__init__("My Plugin", parent)
        self.iface = iface
        self.setup_ui()

    def setup_ui(self):
        # Charger le .ui file
        uic.loadUi(os.path.join(os.path.dirname(__file__), 'ui.ui'), self)

    def closeEvent(self, event):
        # Nettoyage propre a la fermeture
        self.disconnect_signals()
        super().closeEvent(event)
```

**Note FilterMate** : `filter_mate_dockwidget.py` (~6925 lignes) est le widget principal.
Il est en cours de refactoring pour extraire la logique dans les controllers (`ui/controllers/`).

#### Signal/Slot Pattern -- CRITIQUE

```python
from qgis.PyQt.QtCore import pyqtSignal, QObject

class MyManager(QObject):
    # Definir des signaux custom
    filter_applied = pyqtSignal(str, str)  # layer_id, expression
    progress_updated = pyqtSignal(int)     # percentage

    def apply_filter(self, layer_id, expression):
        # ... logique ...
        self.filter_applied.emit(layer_id, expression)

# Connexion
manager = MyManager()
manager.filter_applied.connect(self.on_filter_applied)

# PATTERN CRITIQUE : bloquer les signaux pendant les mises a jour programmatiques
widget.blockSignals(True)
widget.setValue(42)  # Pas de signal emis
widget.blockSignals(False)

# Ou avec le context manager (pattern FilterMate)
# from ui.widgets.dockwidget_signal_manager import DockwidgetSignalManager
```

**Piege classique** : Les signaux peuvent creer des boucles infinies.
Si Widget A emet un signal qui modifie Widget B, qui emet un signal qui modifie Widget A...
Solution : `blockSignals(True/False)` ou `SignalBlocker` / `SignalBlockerGroup`.

#### Threading avec QgsTask

```python
from qgis.core import QgsTask, QgsApplication

class HeavyProcessingTask(QgsTask):
    """Tache asynchrone pour le traitement lourd."""

    def __init__(self, description, layer_uri, params):
        super().__init__(description, QgsTask.CanCancel)
        # STOCKER L'URI, PAS LA COUCHE (thread safety !)
        self.layer_uri = layer_uri
        self.layer_provider = "ogr"
        self.params = params
        self.result = None
        self.error = None

    def run(self):
        """Execute dans un thread background. PAS D'ACCES UI ICI."""
        try:
            # Recreer la couche dans le thread worker
            layer = QgsVectorLayer(self.layer_uri, "temp", self.layer_provider)
            if not layer.isValid():
                self.error = "Layer invalide"
                return False

            # Traitement...
            self.result = self._process(layer)
            return True

        except Exception as e:
            self.error = str(e)
            return False

    def finished(self, success):
        """Execute dans le MAIN THREAD apres run(). ACCES UI OK ICI."""
        if success:
            # Mettre a jour l'UI
            iface.messageBar().pushSuccess("Success", f"Resultat: {self.result}")
        else:
            iface.messageBar().pushCritical("Erreur", self.error or "Inconnu")

    def cancel(self):
        """Annulation propre."""
        super().cancel()
        # NE PAS utiliser QgsMessageLog dans cancel() -- risque de crash QGIS
        # Utiliser le logger Python standard a la place

# Lancement
task = HeavyProcessingTask("Mon traitement", layer.source(), params)
QgsApplication.taskManager().addTask(task)
```

**REGLES ABSOLUES pour QgsTask :**

1. **JAMAIS stocker un QgsMapLayer dans `__init__`** -- stocker l'URI et recreer dans `run()`
2. **JAMAIS toucher l'UI dans `run()`** -- seulement dans `finished()`
3. **JAMAIS appeler QgsMessageLog dans `cancel()`** -- crash QGIS a la fermeture
4. Verifier `self.isCanceled()` regulierement dans `run()` pour les boucles longues
5. Les exceptions dans `run()` doivent etre capturees et stockees en attribut

**Note FilterMate** : `core/tasks/filter_task.py` est le coeur du plugin (~5,851 lignes).
Il herite de `QgsTask` et orchestre tout le filtrage asynchrone. C'est le 2e plus gros fichier du projet.

### 1.4 Performance et Indexation spatiale

#### Spatial Index QGIS

```python
from qgis.core import QgsSpatialIndex

# Creer un index spatial
index = QgsSpatialIndex()
for feature in layer.getFeatures():
    index.addFeature(feature)

# Ou directement depuis la couche (plus rapide)
index = QgsSpatialIndex(layer.getFeatures())

# Recherche par rectangle (bbox)
ids = index.intersects(QgsRectangle(xmin, ymin, xmax, ymax))

# Recherche du plus proche voisin
nearest_id = index.nearestNeighbor(QgsPointXY(x, y), 5)  # 5 plus proches

# ATTENTION : l'index spatial QGIS est en MEMOIRE
# Pour les tres gros jeux de donnees, preferer l'index cote base (PostGIS GiST)
```

#### Pattern d'iteration performante

```python
# MAUVAIS : charge tout en memoire
all_features = list(layer.getFeatures())  # OOM sur 10M features

# BON : iteration paresseuse avec filtrage cote provider
request = QgsFeatureRequest()
request.setFilterExpression('"population" > 10000')
request.setSubsetOfAttributes(['name', 'population'], layer.fields())
# Seuls les champs necessaires sont charges
for feature in layer.getFeatures(request):
    process(feature)

# ENCORE MIEUX : combiner avec FilterRect pour limiter l'emprise
canvas_extent = iface.mapCanvas().extent()
request.setFilterRect(canvas_extent)
# Seuls les features dans la vue courante sont charges

# BATCH processing pour les mises a jour
layer.startEditing()
for fid in feature_ids:
    layer.changeAttributeValue(fid, field_idx, new_value)
layer.commitChanges()
```

**Note FilterMate** : Le plugin utilise ces patterns dans `core/tasks/filter_task.py`.
La couche `infrastructure/cache/` ajoute un cache de geometrie LRU (1000 geometries max)
pour le filtrage multi-couches.

### 1.5 Nouveautes QGIS 3.34-3.38

#### QGIS 3.34 Sketsketcher (LTR - Decembre 2023)

- **Mesh editing** ameliore
- **Point cloud rendering** : rendu par classification, taille de points adaptative
- **Annotations** : nouveau framework d'annotations vectorielles
- **Processing** : amelioration des algorithmes natifs
- **GPS** : nouveau panneau GPS integre

#### QGIS 3.36 Sketcher (Fevrier 2025)

- **Sketcher** (nouveau canvas de sketching/croquis)
- **SVG support ameliore** dans les symboles
- **Processing** : meilleur support du batch processing
- **Point cloud** : amelioration du filtrage par expression
- **PyQGIS** : nouveaux signaux et API pour les plugins

#### QGIS 3.38 Sketcher (prevu 2025-2026)

- **Qt6 migration** en cours (futur QGIS 4.0)
- **Mesh temporal** : support ameliore des donnees temporelles mesh
- **Point cloud** : rendu 2D ameliore, support etendu COPC
- **3D** : performance amelioree du rendu 3D

**Compatibilite FilterMate** : Le plugin cible QGIS >= 3.28 (LTR).
Les features specifiques 3.34+ ne sont PAS requises mais peuvent etre exploitees
(notamment le point cloud filtering ameliore pour la future integration LiDAR).

### 1.6 FilterMate : Architecture Concrete (via Marco Synthesis)

> Source : `filtermate_synthesis_for_atlas_kb_2026_02_10` -- Verifie contre main le 2026-02-10

#### Architecture Hexagonale en Couches

FilterMate v4.4.6 suit une architecture hexagonale stricte depuis la v4.0 :

```
Point d'entree QGIS : filter_mate.py -> FilterMate
  -> Auto-activation (projectRead, layersAdded, cleared)
  -> Config migration, geometry validation check

Couche Application : filter_mate_app.py (~2,383 lignes)
  -> Orchestrateur central, DI container, lifecycle management

Couche UI (~32,000 lignes) :
  -> filter_mate_dockwidget.py (~6,925 lignes) -- widget principal
  -> ui/controllers/ -> 13 controleurs MVC
  -> ui/widgets/ -> widgets custom (signal_manager, json_view)
  -> ui/styles/ -> theming (dark/light, QGIS sync, WCAG)

Couche Core (~50,000 lignes) :
  -> core/services/ -> 28 services hexagonaux
  -> core/tasks/ -> QgsTask async (filter_task ~5,851 lignes)
  -> core/domain/ -> modeles (filter_expression, layer_info, etc.)
  -> core/filter/ -> logique (expression_builder, filter_chain, etc.)
  -> core/geometry/ -> utilitaires (buffer, crs, repair, spatial_index)
  -> core/optimization/ -> query analyzer, auto-optimizer, performance advisor
  -> core/ports/ -> 11 interfaces hexagonales
  -> core/strategies/ -> multi_step_filter, progressive_filter
  -> core/export/ -> batch_exporter, style_exporter

Couche Adapters (~33,000 lignes) :
  -> adapters/backends/ -> 4 backends (postgresql, spatialite, ogr, memory)
  -> adapters/qgis/ -> factory, signals, tasks, expression/feature/layer adapters
  -> adapters/repositories/ -> layer_repository, history_repository
  -> adapters/app_bridge.py -> DI Container (Service Locator)

Couche Infrastructure (~15,000 lignes) :
  -> infrastructure/cache/ -> cache_manager, geometry_cache, query_cache, wkt_cache
  -> infrastructure/database/ -> connection_pool, sql_utils, prepared_statements
  -> infrastructure/config/ -> migration entre versions
  -> infrastructure/feedback/ -> feedback utilisateur
  -> infrastructure/state/ -> flag_manager
  -> infrastructure/resilience.py -> resilience patterns
  -> infrastructure/constants.py -> ~600 lignes de constantes
```

#### 13 Controllers MVC

| Controller | Fichier | Lignes | Role |
|-----------|---------|--------|------|
| IntegrationController | `ui/controllers/integration.py` | ~3,028 | Orchestration UI |
| ExploringController | `ui/controllers/exploring_controller.py` | ~3,208 | Exploration features |
| FilteringController | `ui/controllers/filtering_controller.py` | -- | Operations de filtrage |
| ExportingController | `ui/controllers/exporting_controller.py` | -- | Export de donnees |
| FavoritesController | `ui/controllers/favorites_controller.py` | -- | Gestion des favoris |
| BackendController | `ui/controllers/backend_controller.py` | -- | Backend selection |
| ConfigController | `ui/controllers/config_controller.py` | -- | Configuration |
| + 6 autres | `ui/controllers/` | -- | Specialises |

#### Gestion des Signaux (Pattern Critique)

- **DockwidgetSignalManager** (`ui/widgets/dockwidget_signal_manager.py`, 778 lignes) :
  Gestionnaire centralise de tous les signaux Qt du dockwidget
- **SignalBlocker** : Context manager pour bloquer un widget pendant les mises a jour batch
- **SignalBlockerGroup** : Bloquer plusieurs widgets simultanement
- **Anti-loop protection** : Pour la synchronisation bidirectionnelle widgets <-> selection QGIS
- **Debouncer** (`adapters/qgis/signals/debouncer.py`) : Filtrage temporel des signaux rapides

```python
# Patterns de signal safety FilterMate
from ui.widgets.dockwidget_signal_manager import SignalBlocker, SignalBlockerGroup

# Widget unique
with SignalBlocker(widget):
    widget.setValue(42)  # Pas de signal emis

# Groupe de widgets
with SignalBlockerGroup([combo1, combo2, slider]):
    combo1.setCurrentIndex(0)
    combo2.clear()
    slider.setValue(50)

# Decorateur thread principal
from infrastructure.utils.thread_utils import main_thread_only

@main_thread_only
def update_ui_safely(self):
    # Garanti d'etre execute dans le thread principal
    pass
```

#### Design Patterns Utilises

| Pattern | Implementation | Fichiers cles |
|---------|---------------|---------------|
| **Hexagonal (Ports & Adapters)** | Separation stricte core/adapters/infra | `core/ports/`, `adapters/` |
| **Factory** | BackendFactory, QGISFactory | `adapters/backends/factory.py` |
| **Strategy** | Multi-backend, progressive filtering | `core/strategies/` |
| **Repository** | LayerRepository, HistoryRepository | `adapters/repositories/` |
| **Service Locator** | DI Container | `adapters/app_bridge.py` |
| **MVC** | 13 Controllers UI | `ui/controllers/` |
| **Observer** | Signal/slot Qt + DockwidgetSignalManager | `ui/widgets/` |
| **Command** | Undo/Redo (100 etats/couche, FIFO) | `adapters/undo_redo_handler.py` |
| **Circuit Breaker** | Connection pool PostgreSQL | `infrastructure/database/connection_pool.py` |

---

## 2. PostgreSQL / PostGIS

### 2.1 Types geometriques et index spatiaux

#### Types de geometrie PostGIS

```sql
-- Types de base
geometry(Point, 4326)
geometry(LineString, 4326)
geometry(Polygon, 4326)

-- Multi-types
geometry(MultiPoint, 4326)
geometry(MultiLineString, 4326)
geometry(MultiPolygon, 4326)

-- Collections
geometry(GeometryCollection, 4326)

-- Geography (calculs geodesiques automatiques)
geography(Point, 4326)

-- 3D
geometry(PointZ, 4326)
geometry(PolygonZ, 4326)

-- Verifier le type
SELECT ST_GeometryType(geom), ST_SRID(geom), ST_NDims(geom)
FROM ma_table LIMIT 1;
```

#### Index spatiaux -- FONDAMENTAL pour la performance

```sql
-- Index GiST (Generalized Search Tree) -- LE STANDARD
-- Supporte : &&, ST_Intersects, ST_Contains, ST_Within, ST_DWithin, etc.
CREATE INDEX idx_ma_table_geom ON ma_table USING GIST (geom);

-- Index GiST avec FILLFACTOR (optimise les ecritures)
CREATE INDEX idx_ma_table_geom ON ma_table USING GIST (geom)
    WITH (fillfactor = 90);

-- Index GiST INCLUDE (PostgreSQL 12+, PostGIS 3.0+)
-- Evite les table lookups pour les colonnes incluses
CREATE INDEX idx_ma_table_geom ON ma_table USING GIST (geom)
    INCLUDE (id, type);

-- Index SP-GiST (Space-Partitioned GiST)
-- Plus rapide que GiST pour les points (quad-tree interne)
-- Mais ne supporte PAS les requetes kNN (plus proche voisin)
CREATE INDEX idx_points_geom ON points USING SPGIST (geom);

-- Index BRIN (Block Range Index) -- TRES compact pour les donnees ordonnees
-- Ideal pour les donnees inserees dans l'ordre spatial (GPS tracks, scans LiDAR)
CREATE INDEX idx_gps_geom ON gps_tracks USING BRIN (geom);

-- Statistiques pour l'optimiseur
ANALYZE ma_table;

-- Voir les index existants
SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'ma_table';
```

**Strategie d'indexation FilterMate** :

| Type de donnees | Index recommande | Raison |
|-----------------|------------------|--------|
| Table PostGIS standard | GiST | Support complet de tous les predicats |
| Points (capteurs, adresses) | SP-GiST | Plus rapide pour les requetes bbox |
| Tres grandes tables (>10M) | GiST + BRIN | BRIN pour scan seq, GiST pour predicats |
| Vues materialisees FilterMate | GiST INCLUDE (pk) | Evite table lookup |

### 2.2 Fonctions de filtrage spatial

#### Predicats topologiques (DE-9IM)

```sql
-- Intersection (le plus courant -- utilise l'index GiST)
SELECT * FROM parcelles
WHERE ST_Intersects(geom, ST_GeomFromText('POLYGON((...))'));

-- Containment
SELECT * FROM batiments
WHERE ST_Within(geom, ST_Buffer(ST_MakePoint(2.35, 48.85)::geometry, 0.01));

-- Distance
SELECT * FROM ecoles
WHERE ST_DWithin(geom, ma_geom, 1000);  -- dans un rayon de 1000m (units du CRS)
-- ATTENTION : ST_DWithin utilise l'index, ST_Distance ne l'utilise PAS

-- Touches, Crosses, Overlaps
SELECT * FROM routes WHERE ST_Crosses(geom, riviere_geom);
SELECT * FROM parcelles WHERE ST_Touches(geom, limite_commune);
SELECT * FROM zones WHERE ST_Overlaps(geom, zone_inondable);
```

**Ordre optimal des predicats** (du plus rapide au plus lent, pattern FilterMate) :

1. `ST_Disjoint` -- elimine le plus de candidats (inverse d'intersects)
2. `ST_Intersects` -- excellent avec index GiST (le &&)
3. `ST_Touches` -- rapide, teste les frontieres
4. `ST_Crosses` -- moderement couteux
5. `ST_Within` -- moderement couteux (containment)
6. `ST_Contains` -- couteux (inverse de Within)
7. `ST_Overlaps` -- couteux
8. `ST_Equals` -- le plus couteux (comparaison exacte)

#### Fonctions de transformation

```sql
-- Buffer (cree une zone tampon)
ST_Buffer(geom, 100)                 -- buffer de 100 (unites du CRS)
ST_Buffer(geom, 100, 'quad_segs=8')  -- plus de segments pour un cercle plus lisse

-- Centroide / Point on Surface
ST_Centroid(geom)         -- centre de gravite (peut etre HORS du polygone !)
ST_PointOnSurface(geom)   -- TOUJOURS dans le polygone -- PREFERER CECI

-- Reprojection
ST_Transform(geom, 3857)  -- vers Web Mercator
ST_Transform(geom, 2154)  -- vers Lambert-93

-- Simplification
ST_Simplify(geom, 10)           -- Douglas-Peucker
ST_SimplifyPreserveTopology(geom, 10)  -- Preserve la topologie

-- Enveloppe
ST_Envelope(geom)          -- Bounding box en geometrie
ST_Expand(geom, 100)       -- Bounding box elargie de 100 unites
Box2D(geom)                -- Bounding box 2D

-- Reparation
ST_MakeValid(geom)         -- ESSENTIEL pour les geometries corrompues
ST_IsValid(geom)           -- Test de validite
```

#### Fonctions d'aggregation spatiale

```sql
-- Union de toutes les geometries
SELECT ST_Union(geom) FROM parcelles WHERE commune = 'Paris';

-- Enveloppe convexe du groupe
SELECT ST_ConvexHull(ST_Collect(geom)) FROM points_interet;

-- Collecte sans union
SELECT ST_Collect(geom) FROM parcelles WHERE type = 'forest';

-- Statistiques
SELECT ST_Area(ST_Union(geom)) as total_area FROM parcelles;
SELECT ST_Length(ST_Union(geom)) as total_length FROM routes;
```

### 2.3 Optimisation de requetes

#### Pattern Two-Phase (utilise par FilterMate)

```sql
-- Phase 1 : Pre-filtre par bounding box (TRES rapide avec index GiST)
WITH candidates AS (
    SELECT id, geom
    FROM ma_table
    WHERE geom && ST_Envelope(source_geom)  -- operateur && = bbox intersection
)
-- Phase 2 : Predicat exact sur les candidats seulement
SELECT id FROM candidates
WHERE ST_Intersects(geom, source_geom);
```

Ce pattern est exactement ce que fait FilterMate dans sa strategie TWO_PHASE
(activee quand le score de complexite >= 150).

#### Vues materialisees (pattern FilterMate)

```sql
-- Creation d'une MV avec les features filtrees
CREATE MATERIALIZED VIEW fm_temp_mv_123 AS
SELECT pk_column, geom, ST_Envelope(geom) AS bbox
FROM source_table
WHERE condition;

-- Index sur la MV
CREATE INDEX idx_fm_mv_123_geom ON fm_temp_mv_123 USING GIST (geom);
CREATE INDEX idx_fm_mv_123_bbox ON fm_temp_mv_123 USING GIST (bbox);
CREATE INDEX idx_fm_mv_123_pk ON fm_temp_mv_123 (pk_column);

-- Refresh
REFRESH MATERIALIZED VIEW fm_temp_mv_123;

-- Nettoyage
DROP MATERIALIZED VIEW IF EXISTS fm_temp_mv_123;
```

**Note FilterMate** : Les MV sont creees par `adapters/backends/postgresql/optimizer.py`.
Elles sont prefixees `fm_temp_mv_*` et nettoyees automatiquement.
CLUSTER est conditionnel : sync < 50k features, async 50k-100k, skip > 100k.

#### EXPLAIN ANALYZE pour le debug

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT YAML)
SELECT * FROM parcelles
WHERE ST_Intersects(geom, ST_GeomFromText('POLYGON((...))'));

-- Chercher :
-- "Index Scan using idx_parcelles_geom" = BON (utilise l'index)
-- "Seq Scan on parcelles" = MAUVAIS (scan sequentiel complet)
-- "Bitmap Index Scan" = ACCEPTABLE (pre-filtre par index + recheck)
```

### 2.4 Connexion depuis PyQGIS

```python
from qgis.core import QgsDataSourceUri

# Construire l'URI PostGIS
uri = QgsDataSourceUri()
uri.setConnection(
    host="localhost",
    port="5432",
    database="gis_db",
    username="user",
    password="password"
)
uri.setDataSource(
    schema="public",
    table="ma_table",
    geometryColumn="geom",
    sql="",           # Filtre SQL initial
    aKeyColumn="id"   # Cle primaire
)

# Parametres optionnels
uri.setSrid("4326")
uri.setWkbType(QgsWkbTypes.MultiPolygon)
uri.setParam("sslmode", "prefer")

# Creer la couche
layer = QgsVectorLayer(uri.uri(), "Ma couche PostGIS", "postgres")

# Connexion directe psycopg2 (pour les operations backend)
import psycopg2

# TOUJOURS verifier la disponibilite
from adapters.backends.postgresql_availability import POSTGRESQL_AVAILABLE

if POSTGRESQL_AVAILABLE:
    conn = psycopg2.connect(
        host="localhost", port="5432",
        database="gis_db", user="user", password="pass"
    )
    cursor = conn.cursor()
    cursor.execute("SELECT id, ST_AsText(geom) FROM ma_table LIMIT 10")
    rows = cursor.fetchall()
    conn.close()
```

**Note FilterMate** : Le module `infrastructure/database/connection_pool.py` gere le pooling
de connexions. Les connexions sont thread-safe pour PostgreSQL et SpatiaLite.

### 2.5 Nouveautes PostGIS 3.4 / 3.5

#### PostGIS 3.4 (avec PostgreSQL 16, ~2024)

- **ST_LargestEmptyCircle** : Trouve le plus grand cercle vide inscrit dans une geometrie
- **ST_MaximumInscribedCircle** ameliore : Plus rapide, plus precis
- **ST_CoverageUnion / ST_CoverageSimplify** : Operations sur les couvertures (tessellations)
  - Ideal pour simplifier des parcelles adjacentes sans creer de trous
- **Performance** : Ameliorations significatives du moteur GEOS 3.12
  - `ST_Intersection` et `ST_Union` plus rapides (15-30%)
  - `ST_Buffer` ameliore pour les geometries complexes
- **Indexation** : Support ameliore des index SP-GiST pour les requetes range

#### PostGIS 3.5 (avec PostgreSQL 17, ~2025)

- **GEOS 3.13** integre avec les corrections de robustesse
- **ST_Node** ameliore pour les reseaux routiers
- **Geometry validation** plus stricte et plus rapide
- **Performance** : Amelioration continue des operations de superposition (overlay)

**Compatibilite FilterMate** : Le plugin utilise principalement les fonctions PostGIS
standard (ST_Intersects, ST_Within, ST_Buffer, etc.) qui sont stables depuis PostGIS 2.x.
Les fonctions de couverture (3.4+) pourraient etre utiles pour le futur filtrage de
tessellations cadastrales.

### 2.6 FilterMate PostgreSQL : Metriques et Strategies Reelles (via Marco Synthesis)

> Source : `filtermate_synthesis_for_atlas_kb_2026_02_10` -- Verifie contre main le 2026-02-10

#### Performance Mesuree

Le backend PostgreSQL de FilterMate atteint **< 1s sur des millions de features** grace
a la combinaison des optimisations suivantes :

- Vues materialisees `fm_temp_mv_*` avec index GiST + INCLUDE (PG 11+)
- Detection automatique de PK : interrogation `pg_index`, fallback sur noms communs
  (id, fid, gid, etc.), dernier recours `ctid`
- Bbox pre-filter column pour l'operateur `&&`
- Async CLUSTER conditionnel (< 50k: sync, 50k-100k: async, > 100k: skip)
- Covering GiST indexes avec INCLUDE
- ST_PointOnSurface au lieu de ST_Centroid
- Simplification adaptive avant buffer

#### Connection Pooling

```
infrastructure/database/connection_pool.py

Pool de 2-15 connections avec circuit breaker :
- Min connections : 2 (maintenues en permanence)
- Max connections : 15 (pic de charge)
- Circuit breaker : coupe les tentatives de connexion apres N echecs consecutifs
- Thread-safe : chaque thread background recoit sa propre connexion
- Nettoyage automatique des connexions idle
```

#### Strategies de Requete par Score de Complexite

Le `QueryComplexityEstimator` (`infrastructure/utils/complexity_estimator.py`) analyse
chaque expression et route vers la strategie optimale :

| Score | Strategie | Cas d'usage | Performance |
|-------|-----------|-------------|-------------|
| < 50 | **DIRECT** | Requetes simples, petits datasets | Instantane |
| 50-150 | **MATERIALIZED** | Complexite moyenne, taille moderee | < 1s |
| 150-500 | **TWO_PHASE** | Predicats complexes (bbox pre-filter + full) | 3-10x gain |
| >= 500 | **PROGRESSIVE** | Tres complexes + gros datasets (lazy cursor) | Streaming |

**Implementation** : `adapters/backends/postgresql/optimizer.py` cree les vues
materialisees, `core/optimization/query_analyzer.py` calcule le score,
`core/strategies/progressive_filter.py` gere le curseur paresseux.

---

## 3. Raster

### 3.1 Formats : GeoTIFF, COG, VRT

#### GeoTIFF -- Le format raster de reference

```
Caracteristiques :
- Format TIFF avec metadonnees geospatiales embarquees (CRS, extent, resolution)
- Supporte la compression : LZW (lossless), DEFLATE (lossless), JPEG (lossy)
- Supporte les tuiles internes (tiled GeoTIFF)
- Supporte les overviews (pyramides) embarquees
- Supporte les bandes multiples (multispectral, RGB, RGBA, etc.)
- Types de donnees : Byte, UInt16, Int16, UInt32, Int32, Float32, Float64

Options de creation GDAL :
TILED=YES                # Tuiles internes (256x256 par defaut)
COMPRESS=DEFLATE          # Compression lossless
PREDICTOR=2              # Predictor horizontal (ameliore la compression)
BIGTIFF=IF_SAFER         # BigTIFF si necessaire (>4GB)
```

#### COG (Cloud-Optimized GeoTIFF) -- L'AVENIR

```
Un COG est un GeoTIFF avec des contraintes specifiques :
1. Tuiles internes obligatoires (typiquement 512x512)
2. Overviews (pyramides) embarquees
3. Ordonnancement specifique des IFDs (Image File Directories)
   pour permettre le range-request HTTP

Avantages :
- Acces partiel via HTTP Range requests (pas besoin de telecharger tout le fichier)
- Compatible avec le cloud storage (S3, GCS, Azure Blob)
- Compatible avec les anciens lecteurs GeoTIFF
- Support natif dans QGIS >= 3.22

Creation avec GDAL :
gdal_translate input.tif output_cog.tif \
    -of COG \
    -co COMPRESS=DEFLATE \
    -co PREDICTOR=YES \
    -co OVERVIEWS=AUTO \
    -co BLOCKSIZE=512

Verification :
python -c "from osgeo import gdal; ds = gdal.Open('file.tif'); print(ds.GetMetadata('IMAGE_STRUCTURE'))"
# Doit contenir LAYOUT=COG
```

**Note FilterMate** : Pour l'export raster (P3 - Raster Clip by Vector), preferer
le format COG. Verification : `GDAL >= 3.1` requis. Toujours verifier la version GDAL.

#### VRT (Virtual Raster) -- Mosaique sans copie

```xml
<!-- fichier .vrt -- reference d'autres fichiers raster sans copie -->
<VRTDataset rasterXSize="..." rasterYSize="...">
  <SRS>EPSG:4326</SRS>
  <GeoTransform>...</GeoTransform>
  <VRTRasterBand dataType="Float32" band="1">
    <SimpleSource>
      <SourceFilename relativeToVRT="1">tile1.tif</SourceFilename>
      <SourceBand>1</SourceBand>
    </SimpleSource>
    <SimpleSource>
      <SourceFilename relativeToVRT="1">tile2.tif</SourceFilename>
      <SourceBand>1</SourceBand>
    </SimpleSource>
  </VRTRasterBand>
</VRTDataset>
```

```python
# Creation en Python
from osgeo import gdal

# Mosaique de fichiers
vrt = gdal.BuildVRT("output.vrt", ["tile1.tif", "tile2.tif", "tile3.tif"])
vrt = None  # Fermer pour ecrire

# Options
options = gdal.BuildVRTOptions(
    resampleAlg='bilinear',
    addAlpha=True,
    bandList=[1, 2, 3]
)
vrt = gdal.BuildVRT("output.vrt", input_files, options=options)
```

### 3.2 GDAL/OGR : lecture, ecriture, reprojection

#### Lecture d'un raster

```python
from osgeo import gdal, osr

# Ouvrir en lecture
ds = gdal.Open("/path/to/raster.tif", gdal.GA_ReadOnly)

# Metadonnees
print(f"Taille: {ds.RasterXSize} x {ds.RasterYSize}")
print(f"Bandes: {ds.RasterCount}")
print(f"Projection: {ds.GetProjection()}")

# GeoTransform [x_origin, pixel_width, rotation_x, y_origin, rotation_y, pixel_height]
gt = ds.GetGeoTransform()
x_origin, pixel_width = gt[0], gt[1]
y_origin, pixel_height = gt[3], gt[5]  # pixel_height est negatif !

# Lire une bande
band = ds.GetRasterBand(1)
nodata = band.GetNoDataValue()
stats = band.GetStatistics(True, True)  # [min, max, mean, stddev]
data = band.ReadAsArray()  # numpy array

# Coordonnees pixel -> geo
def pixel_to_geo(gt, col, row):
    x = gt[0] + col * gt[1] + row * gt[2]
    y = gt[3] + col * gt[4] + row * gt[5]
    return x, y

# Coordonnees geo -> pixel
def geo_to_pixel(gt, x, y):
    inv_gt = gdal.InvGeoTransform(gt)
    col = inv_gt[0] + x * inv_gt[1] + y * inv_gt[2]
    row = inv_gt[3] + x * inv_gt[4] + y * inv_gt[5]
    return int(col), int(row)

ds = None  # Fermer le dataset
```

#### Reprojection avec GDAL

```python
from osgeo import gdal

# Warp (reprojection + reechantillonnage)
gdal.Warp(
    "output_3857.tif",
    "input_4326.tif",
    dstSRS="EPSG:3857",
    resampleAlg="bilinear",
    format="GTiff",
    creationOptions=["COMPRESS=DEFLATE", "TILED=YES"]
)

# Clip par emprise
gdal.Warp(
    "output_clip.tif",
    "input.tif",
    outputBounds=[xmin, ymin, xmax, ymax],
    outputBoundsSRS="EPSG:4326"
)

# Clip par masque vecteur (PATTERN P3 - Raster Clip by Vector)
gdal.Warp(
    "output_clip.tif",
    "input.tif",
    cutlineDSName="mask.shp",       # Fichier vecteur de decoupe
    cutlineLayer="mask",             # Nom de la couche
    cropToCutline=True,              # Rogner a l'emprise du masque
    dstNodata=-9999                  # Valeur NoData pour les zones hors masque
)
```

### 3.3 PyQGIS Raster API

#### QgsRasterLayer -- Fondamental

```python
from qgis.core import QgsRasterLayer, QgsRasterBandStats, Qgis

# Charger un raster
layer = QgsRasterLayer("/path/to/dem.tif", "MNT")
if not layer.isValid():
    print("Erreur de chargement")

# Proprietes
print(f"Largeur: {layer.width()}")       # Pixels en X
print(f"Hauteur: {layer.height()}")      # Pixels en Y
print(f"Bandes: {layer.bandCount()}")
print(f"CRS: {layer.crs().authid()}")
print(f"Extent: {layer.extent()}")
print(f"Resolution X: {layer.rasterUnitsPerPixelX()}")
print(f"Resolution Y: {layer.rasterUnitsPerPixelY()}")

# Provider
provider = layer.dataProvider()
print(f"Provider: {provider.name()}")  # 'gdal'

# Statistiques par bande
stats = provider.bandStatistics(1, QgsRasterBandStats.All)
print(f"Min: {stats.minimumValue}")
print(f"Max: {stats.maximumValue}")
print(f"Mean: {stats.mean}")
print(f"StdDev: {stats.stdDev}")
```

#### provider.sample() -- CLE pour P1-bis (Raster Value Sampling)

```python
from qgis.core import QgsRasterLayer, QgsPointXY

raster = QgsRasterLayer("/path/to/dem.tif", "MNT")
provider = raster.dataProvider()

# Sampler UNE valeur a un point donne
point = QgsPointXY(2.3522, 48.8566)  # Paris
value, success = provider.sample(point, 1)  # band=1

if success:
    print(f"Altitude a Paris: {value}m")
else:
    print("NoData ou hors emprise")

# PATTERN COMPLET pour le sampling sur des features vecteur
# C'est le coeur de P1-bis

from qgis.core import QgsCoordinateTransform, QgsProject

def sample_raster_at_features(
    vector_layer,  # QgsVectorLayer
    raster_layer,  # QgsRasterLayer
    band=1,
    use_point_on_surface=True  # TOUJOURS True pour les polygones
):
    """
    Sample raster values at each vector feature location.

    Returns:
        dict: {feature_id: raster_value} (None si NoData)
    """
    results = {}

    # Reprojection si CRS different
    transform = None
    if vector_layer.crs() != raster_layer.crs():
        transform = QgsCoordinateTransform(
            vector_layer.crs(),
            raster_layer.crs(),
            QgsProject.instance()
        )

    provider = raster_layer.dataProvider()
    raster_extent = raster_layer.extent()

    for feature in vector_layer.getFeatures():
        geom = feature.geometry()

        # Choisir le point representatif
        if use_point_on_surface and geom.type() == QgsWkbTypes.PolygonGeometry:
            point_geom = geom.pointOnSurface()
        else:
            point_geom = geom.centroid()

        if point_geom.isEmpty():
            results[feature.id()] = None
            continue

        point = point_geom.asPoint()

        # Reprojeter si necessaire
        if transform:
            point = transform.transform(point)

        # Verifier que le point est dans l'emprise du raster
        if not raster_extent.contains(point):
            results[feature.id()] = None
            continue

        # Sampler
        value, success = provider.sample(QgsPointXY(point), band)
        results[feature.id()] = value if success else None

    return results
```

**PIEGES CRITIQUES pour provider.sample() :**

1. **CRS** : Le point DOIT etre dans le CRS du raster. Toujours reprojeter avant.
2. **pointOnSurface vs centroid** : Utiliser `pointOnSurface()` pour les polygones.
3. **NoData** : `success=False` peut signifier NoData OU hors emprise. Verifier les deux.
4. **Thread safety** : `provider.sample()` n'est PAS thread-safe.
   Stocker l'URI, recreer la couche dans le thread worker.
5. **Performance** : ~1ms par point. Pour 100k features, ca fait ~100s.
   Considerer le batch processing ou numpy pour les gros jeux de donnees.

#### QgsRasterCalculator

```python
from qgis.core import QgsRasterCalculator, QgsRasterCalculatorEntry

# Definir les entrees
entry = QgsRasterCalculatorEntry()
entry.ref = 'dem@1'               # Identifiant dans la formule
entry.raster = raster_layer       # QgsRasterLayer
entry.bandNumber = 1

# Calculer NDVI = (NIR - RED) / (NIR + RED)
entries = []
nir_entry = QgsRasterCalculatorEntry()
nir_entry.ref = 'nir@1'
nir_entry.raster = nir_layer
nir_entry.bandNumber = 1
entries.append(nir_entry)

red_entry = QgsRasterCalculatorEntry()
red_entry.ref = 'red@1'
red_entry.raster = red_layer
red_entry.bandNumber = 1
entries.append(red_entry)

calc = QgsRasterCalculator(
    '(nir@1 - red@1) / (nir@1 + red@1)',  # Formule
    '/path/to/ndvi.tif',                     # Sortie
    'GTiff',                                  # Format
    raster_layer.extent(),                    # Extent
    raster_layer.width(),                     # Cols
    raster_layer.height(),                    # Rows
    entries,                                  # Entrees
    QgsProject.instance().transformContext()
)

result = calc.processCalculation()
if result == 0:
    print("Calcul NDVI reussi")
```

**Note FilterMate** : NE PAS recreer le Raster Calculator. Le plugin doit rester
focalise sur le FILTRAGE. Le Calculator existe deja nativement dans QGIS.

### 3.4 Zonal Statistics -- DIFFERENCIATEUR UNIQUE (P1)

#### QgsZonalStatistics (natif QGIS)

```python
from qgis.analysis import QgsZonalStatistics

# ATTENTION : QgsZonalStatistics MODIFIE LA COUCHE EN PLACE
# Toujours travailler sur une copie !

# Creer une copie memoire de la couche vecteur
import processing
result = processing.run("native:saveselectedfeatures", {
    'INPUT': vector_layer,
    'OUTPUT': 'memory:temp_for_zonal'
})
temp_layer = result['OUTPUT']

# OU creer une couche memoire manuellement
temp_layer = QgsVectorLayer(
    f"{vector_layer.wkbType()}?crs={vector_layer.crs().authid()}",
    "temp_zonal",
    "memory"
)
temp_provider = temp_layer.dataProvider()
temp_provider.addAttributes(vector_layer.fields().toList())
temp_layer.updateFields()
temp_provider.addFeatures(list(vector_layer.getFeatures()))

# Calculer les stats zonales
zonal = QgsZonalStatistics(
    temp_layer,                     # Couche vecteur (SERA MODIFIEE)
    raster_layer,                   # Couche raster
    attributePrefix="zs_",         # Prefixe des colonnes ajoutees
    rasterBand=1,                  # Bande du raster
    stats=QgsZonalStatistics.Mean | QgsZonalStatistics.StdDev |
          QgsZonalStatistics.Min | QgsZonalStatistics.Max |
          QgsZonalStatistics.Count | QgsZonalStatistics.Sum
)

result = zonal.calculateStatistics(None)  # None = pas de feedback
if result == 0:
    print("Zonal stats calculees avec succes")

# Les colonnes ajoutees :
# zs_mean, zs_stdev, zs_min, zs_max, zs_count, zs_sum
# Maintenant on peut filtrer !
temp_layer.setSubsetString('"zs_mean" > 500')  # Altitude moyenne > 500m
```

#### Alternative Processing (plus flexible)

```python
import processing

# Via l'algorithme natif
result = processing.run("native:zonalstatisticsfb", {
    'INPUT': vector_layer,
    'INPUT_RASTER': raster_layer,
    'RASTER_BAND': 1,
    'COLUMN_PREFIX': 'zs_',
    'STATISTICS': [0, 1, 2, 3, 4, 5, 6],  # Count, Sum, Mean, Median, StdDev, Min, Max
    'OUTPUT': 'memory:zonal_result'
})
output_layer = result['OUTPUT']
```

**Statistiques disponibles :**

| Code | Statistique | Description | Usage typique |
|------|------------|-------------|---------------|
| 0 | Count | Nb de pixels | Couverture |
| 1 | Sum | Somme des valeurs | Volume, accumulation |
| 2 | Mean | Moyenne | Altitude moyenne, temperature |
| 3 | Median | Mediane | Valeur typique (robuste) |
| 4 | StdDev | Ecart-type | Heterogeneite, relief |
| 5 | Min | Minimum | Point le plus bas |
| 6 | Max | Maximum | Point le plus haut |
| 7 | Range | Etendue (max-min) | Amplitude de variation |
| 8 | Minority | Valeur la moins frequente | Classe rare |
| 9 | Majority | Valeur la plus frequente | Classe dominante |
| 10 | Variety | Nb de valeurs uniques | Diversite |
| 11 | Variance | Variance | Dispersion statistique |

**Pattern FilterMate pour Zonal Stats as Filter (P1) :**

```python
class ZonalStatsFilterService:
    """
    Service de filtrage vecteur par statistiques zonales raster.
    Architecture hexagonale : core/services/raster_filter_service.py
    """

    def filter_by_zonal_stat(
        self,
        vector_layer: QgsVectorLayer,
        raster_layer: QgsRasterLayer,
        stat: str,        # 'mean', 'min', 'max', 'sum', etc.
        operator: str,     # '>', '<', '>=', '<=', '=', '!='
        threshold: float,  # Valeur seuil
        band: int = 1
    ) -> list:
        """
        Filtre les features vecteur dont la stat zonale raster
        satisfait la condition donnee.

        Returns:
            list[int]: IDs des features satisfaisant la condition
        """
        # 1. Creer une couche temporaire (QgsZonalStatistics modifie en place)
        temp_layer = self._create_temp_layer(vector_layer)

        # 2. Calculer les stats zonales
        self._compute_zonal_stats(temp_layer, raster_layer, band, stat)

        # 3. Filtrer par la condition
        matching_ids = self._filter_by_condition(
            temp_layer, stat, operator, threshold
        )

        # 4. Appliquer le subset string a la couche originale
        id_list = ','.join(str(fid) for fid in matching_ids)
        pk_field = self._get_pk_field(vector_layer)
        vector_layer.setSubsetString(f'"{pk_field}" IN ({id_list})')

        return matching_ids
```

### 3.5 Raster comme filtre vecteur

Ce concept est LE differenciateur de FilterMate. L'idee : utiliser les valeurs
d'un raster pour filtrer des features vecteur.

**Cas d'usage concrets :**

| Scenario | Raster | Vecteur | Filtre |
|----------|--------|---------|--------|
| Batiments en altitude | MNT (DEM) | Batiments | "altitude moyenne > 500m" |
| Parcelles fertiles | NDVI | Parcelles agricoles | "NDVI moyen > 0.6" |
| Zones a risque | Carte d'alea | Habitations | "alea max >= 3" |
| Ilots de chaleur | Temperature LST | Quartiers | "temperature > 35C" |
| Forets denses | Canopee (MNH) | Zones forestieres | "hauteur moyenne > 15m" |

**3 approches par complexite croissante :**

```
Approche 1: SAMPLING (P1-bis, 3-5 jours)
+--------+     sample()     +--------+     filtre     +--------+
| Raster | ───────────────> | Valeur | ──────────────> | Vecteur|
+--------+   par centroide  +--------+   par seuil    +--------+
  (rapide, 1 valeur par feature, ~1ms/feature)

Approche 2: ZONAL STATS (P1, 2-3 semaines)
+--------+     stats()      +--------+     filtre     +--------+
| Raster | ───────────────> | Stats  | ──────────────> | Vecteur|
+--------+   par geometrie  +--------+   multi-stats  +--------+
  (plus riche, mean/min/max/std par feature, ~10ms/feature)

Approche 3: MASQUE (P3, 2 semaines)
+--------+     clip()       +--------+     export     +--------+
| Raster | ───────────────> | Raster | ──────────────> | Fichier|
+--------+   par geometrie  | decoupe|                +--------+
  (export, decoupe du raster par les features filtrees)
```

### 3.6 Nouveautes GDAL 3.8 / 3.9 / 3.10

#### GDAL 3.8 (Novembre 2023)

- **GeoParquet** : Support en lecture/ecriture natif (format columnar Apache Arrow)
  - Bien plus rapide que GeoJSON/Shapefile pour les gros fichiers vecteur
  - Supporte le partitionnement spatial
- **PMTiles** : Support en lecture des archives PMTiles (tuiles vectorielles serverless)
- **COG** : Amelioration de la creation de COG multi-bandes
- **FlatGeobuf** : Amelioration du streaming HTTP
- **STAC** : Support ameliore des catalogues STAC

#### GDAL 3.9 (Mai 2024)

- **Arrow IPC** : Driver pour le format Arrow IPC (streaming columnar)
- **GeoParquet 1.1** : Support de la specification 1.1
- **Multidimensional** : Support ameliore des donnees NetCDF/Zarr multidimensionnelles
- **Performance** : Ameliorations des lectures COG par HTTP Range requests
- **WEBP** : Compression WebP pour les GeoTIFF (meilleur ratio que JPEG avec lossless)

#### GDAL 3.10 (Novembre 2024 / debut 2025)

- **MapTiler MBTiles** : Support ameliore
- **COPC** : Support ameliore des nuages de points
- **Performance** : Lecture parallele des bandes raster
- **Zarr** : Support ameliore du format Zarr V3

**Compatibilite FilterMate** :
- GDAL >= 3.1 requis pour l'export COG (verifier avec `gdal.VersionInfo()`)
- GDAL >= 3.8 recommande pour GeoParquet (futur format d'export)
- Le plugin DOIT verifier la version GDAL avant d'utiliser les fonctionnalites avancees :

```python
from osgeo import gdal

gdal_version = int(gdal.VersionInfo())
# 3080000 = GDAL 3.8.0, 3090000 = GDAL 3.9.0, etc.

if gdal_version < 3010000:
    # Pas de support COG natif
    raise RuntimeError("GDAL >= 3.1 requis pour l'export COG")
```

---

## 4. LiDAR / Nuages de Points

### 4.1 Formats : LAS, LAZ, COPC

#### LAS (LASer file format)

```
Version actuelle : LAS 1.4 (ASPRS)
Structure :
  - Header : metadonnees (bounds, CRS, point count, point format)
  - VLR (Variable Length Records) : CRS WKT, classification, etc.
  - Point Records : x, y, z, intensity, return_number, classification, etc.
  - EVLR : Extended VLR (LAS 1.4)

Point formats (LAS 1.4) :
  0-5 : Classique (sans GPS time pour 0)
  6-10 : Etendus (avec GPS time, NIR, wave)

Taille typique : 20-40 octets/point
Fichier 1km2 a 10pts/m2 = ~300 Mo (non compresse)
```

#### LAZ (LASzip compression)

```
Compression lossless du LAS
Ratio : 5:1 a 10:1 typiquement
1km2 a 10pts/m2 ~ 30-60 Mo en LAZ
Compatible avec tous les outils LAS (pdal, lastools, CloudCompare)
Standard de facto pour la distribution (IGN LiDAR HD)
```

#### COPC (Cloud-Optimized Point Cloud) -- L'AVENIR

```
= LAZ + organisation spatiale hierarchique (octree)
Permet le streaming HTTP (range requests) comme le COG pour les rasters
Un seul fichier, pas besoin de serveur de tuiles

Avantages :
  - Acces partiel : charger seulement les points dans une zone
  - LOD : charger d'abord une vue d'ensemble, puis raffiner
  - Compatible avec tous les lecteurs LAZ
  - Support natif QGIS >= 3.26
  - Support natif PDAL >= 2.4

Creation :
  pdal translate input.laz output.copc.laz --writers.copc.forward=all

Ou depuis Python :
  pipeline = [
      {"type": "readers.las", "filename": "input.laz"},
      {"type": "writers.copc", "filename": "output.copc.laz"}
  ]
```

### 4.2 QGIS Point Cloud Layer (QGIS >= 3.18)

```python
from qgis.core import QgsPointCloudLayer

# Charger un nuage de points
layer = QgsPointCloudLayer("/path/to/cloud.copc.laz", "Mon nuage", "copc")
# Ou : "ept" pour Entwine Point Tiles, "pdal" pour LAS/LAZ generique

if layer.isValid():
    QgsProject.instance().addMapLayer(layer)

# Proprietes
print(f"Points: {layer.pointCount()}")
print(f"CRS: {layer.crs().authid()}")
print(f"Extent: {layer.extent()}")

# Attributs disponibles
attributes = layer.attributes()
for attr in attributes.attributes():
    print(f"  {attr.name()} : {attr.type()}")
# Typiquement : X, Y, Z, Intensity, ReturnNumber, Classification, etc.

# Statistiques
stats = layer.statistics()
# Fournit min/max/mean par attribut
```

#### Renderers pour Point Cloud

```python
from qgis.core import (
    QgsPointCloudClassifiedRenderer,
    QgsPointCloudRgbRenderer,
    QgsPointCloudAttributeByRampRenderer,
    QgsPointCloudCategory
)

# Rendu par classification (le plus courant)
renderer = QgsPointCloudClassifiedRenderer()
renderer.setAttribute("Classification")
# Les categories ASPRS standard :
#   2 = Ground, 3 = Low Vegetation, 4 = Medium Vegetation,
#   5 = High Vegetation, 6 = Building, 9 = Water, etc.

# Rendu par rampe de couleur (altitude, intensite)
renderer = QgsPointCloudAttributeByRampRenderer()
renderer.setAttribute("Z")
# Configurer la rampe de couleur...

# Rendu RGB (si les bandes RGB sont disponibles)
renderer = QgsPointCloudRgbRenderer()
renderer.setRedAttribute("Red")
renderer.setGreenAttribute("Green")
renderer.setBlueAttribute("Blue")
```

### 4.3 Filtrage par attribut

```python
# Filtrage par expression (QGIS >= 3.26 pour les point clouds)
# Similaire aux vecteurs mais avec les attributs LiDAR

# Par classification
layer.setSubsetString("Classification = 6")  # Batiments seulement

# Par intensite
layer.setSubsetString("Intensity > 200")

# Par nombre de retours
layer.setSubsetString("ReturnNumber = 1")  # Premiers retours seulement

# Par altitude
layer.setSubsetString("Z > 100 AND Z < 500")

# Combinaison
layer.setSubsetString(
    "Classification IN (3, 4, 5) AND ReturnNumber = 1 AND Intensity > 50"
)
# = Vegetation (basse/moyenne/haute), premiers retours, intensite > 50
```

**Relevance FilterMate** : Le filtrage des point clouds utilise le meme
mecanisme de `subsetString` que les vecteurs. Une future extension de FilterMate
pourrait integrer le filtrage de nuages de points avec la meme UX.

### 4.4 PDAL pour le processing

```python
import pdal
import json

# Pipeline PDAL en Python
pipeline_json = {
    "pipeline": [
        {
            "type": "readers.las",
            "filename": "input.laz"
        },
        {
            # Filtrage par classification
            "type": "filters.range",
            "limits": "Classification[2:2]"  # Ground seulement
        },
        {
            # Filtrage par retour
            "type": "filters.returns",
            "groups": "first"
        },
        {
            # Classification du sol (si pas deja fait)
            "type": "filters.smrf",  # Simple Morphological Filter
            "slope": 0.15,
            "window": 18,
            "threshold": 0.5
        },
        {
            # Calcul de hauteur par rapport au sol
            "type": "filters.hag_nn"  # Height Above Ground (nearest neighbor)
        },
        {
            # Decoupage par emprise
            "type": "filters.crop",
            "bounds": "([xmin, xmax], [ymin, ymax])"
        },
        {
            # Ecriture
            "type": "writers.las",
            "filename": "output.laz",
            "compression": "laszip"
        }
    ]
}

pipeline = pdal.Pipeline(json.dumps(pipeline_json))
count = pipeline.execute()
print(f"{count} points traites")

# Recuperer les donnees en numpy
arrays = pipeline.arrays
points = arrays[0]  # numpy structured array
print(f"Colonnes: {points.dtype.names}")
# ('X', 'Y', 'Z', 'Intensity', 'ReturnNumber', 'Classification', ...)
```

**Pipelines utiles pour FilterMate :**

```python
# Pipeline 1 : Extraire le MNT depuis un LiDAR
pipeline_mnt = [
    {"type": "readers.las", "filename": "input.laz"},
    {"type": "filters.range", "limits": "Classification[2:2]"},  # Sol
    {"type": "writers.gdal",
     "filename": "mnt.tif",
     "gdaldriver": "GTiff",
     "output_type": "mean",
     "resolution": 1.0}  # 1m de resolution
]

# Pipeline 2 : MNH (Modele Numerique de Hauteur = canopee)
pipeline_mnh = [
    {"type": "readers.las", "filename": "input.laz"},
    {"type": "filters.hag_nn"},  # Calcule la hauteur au-dessus du sol
    {"type": "filters.range", "limits": "HeightAboveGround[0.5:]"},
    {"type": "writers.gdal",
     "filename": "mnh.tif",
     "gdaldriver": "GTiff",
     "output_type": "max",  # Hauteur max de la canopee
     "resolution": 1.0}
]

# Pipeline 3 : COPC depuis LAS/LAZ
pipeline_copc = [
    {"type": "readers.las", "filename": "input.laz"},
    {"type": "writers.copc", "filename": "output.copc.laz"}
]
```

---

## 5. Visualisation et Affichage

### 5.1 Renderers QGIS

#### Rendu categorise

```python
from qgis.core import (
    QgsCategorizedSymbolRenderer, QgsRendererCategory,
    QgsSymbol, QgsMarkerSymbol, QgsLineSymbol, QgsFillSymbol
)

# Creer des categories
categories = []
for value, color, label in [
    ('residential', '#FFD700', 'Residential'),
    ('commercial', '#4169E1', 'Commercial'),
    ('industrial', '#DC143C', 'Industrial')
]:
    symbol = QgsFillSymbol.createSimple({
        'color': color,
        'outline_color': '#333333'
    })
    cat = QgsRendererCategory(value, symbol, label)
    categories.append(cat)

renderer = QgsCategorizedSymbolRenderer("land_use", categories)
layer.setRenderer(renderer)
layer.triggerRepaint()
```

#### Rendu gradue (ideal pour les resultats de zonal stats)

```python
from qgis.core import (
    QgsGraduatedSymbolRenderer, QgsRendererRange,
    QgsClassificationQuantile, QgsGradientColorRamp, QgsSymbol
)

# Rampe de couleur
color_ramp = QgsGradientColorRamp(
    QColor('#2b83ba'),  # Bleu (bas)
    QColor('#d7191c')   # Rouge (haut)
)

# Renderer gradue
renderer = QgsGraduatedSymbolRenderer()
renderer.setClassAttribute("zs_mean")  # Colonne de zonal stats

# Classification automatique
renderer.setClassificationMethod(QgsClassificationQuantile())
renderer.updateClasses(layer, 5)  # 5 classes

# OU classes manuelles
ranges = [
    QgsRendererRange(0, 200, symbol_low, "0-200m"),
    QgsRendererRange(200, 500, symbol_mid, "200-500m"),
    QgsRendererRange(500, 1000, symbol_high, "500-1000m"),
]
renderer = QgsGraduatedSymbolRenderer("altitude", ranges)

layer.setRenderer(renderer)
layer.triggerRepaint()
```

**Note FilterMate P2 (Raster-Driven Highlight)** : Le rendu gradue est le compagnon
naturel du filtrage par zonal stats. Quand l'utilisateur ajuste un slider de seuil,
le renderer peut etre mis a jour dynamiquement pour colorier les features selon
leur valeur de stat zonale.

#### Rendu base sur des regles (Rule-Based)

```python
from qgis.core import QgsRuleBasedRenderer

# Rendu par regles -- le plus flexible
root_rule = QgsRuleBasedRenderer.Rule(QgsSymbol.defaultSymbol(layer.geometryType()))

# Regle 1 : Batiments hauts en rouge
rule1 = QgsRuleBasedRenderer.Rule(
    QgsFillSymbol.createSimple({'color': '#FF0000'}),
    0, 0,  # min/max scale (0 = no limit)
    '"height" > 20',  # Expression
    'Batiments hauts'  # Label
)
root_rule.appendChild(rule1)

# Regle 2 : Le reste en gris
rule2 = QgsRuleBasedRenderer.Rule(
    QgsFillSymbol.createSimple({'color': '#CCCCCC'}),
    0, 0, 'ELSE', 'Autres'
)
root_rule.appendChild(rule2)

renderer = QgsRuleBasedRenderer(root_rule)
layer.setRenderer(renderer)
```

### 5.2 Styles dynamiques bases sur des filtres

```python
from qgis.PyQt.QtCore import QTimer

class DynamicStyleManager:
    """
    Met a jour le style de la couche en fonction du filtre actif.
    Pattern utilisable pour P2 (Raster-Driven Highlight).
    """

    def __init__(self, layer, raster_layer):
        self.layer = layer
        self.raster_layer = raster_layer
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._apply_highlight)
        self._pending_range = None

    def on_range_changed(self, min_val, max_val):
        """Appelee quand l'utilisateur deplace le slider."""
        self._pending_range = (min_val, max_val)
        self._debounce_timer.start(300)  # 300ms debounce

    def _apply_highlight(self):
        """Applique le surlignage apres debounce."""
        if not self._pending_range:
            return

        min_val, max_val = self._pending_range

        # Sampler les features visibles
        visible_extent = iface.mapCanvas().extent()
        request = QgsFeatureRequest().setFilterRect(visible_extent)

        matching_ids = []
        for feature in self.layer.getFeatures(request):
            value = self._sample_at_feature(feature)
            if value is not None and min_val <= value <= max_val:
                matching_ids.append(feature.id())

        # Surligner par selection
        self.layer.selectByIds(matching_ids)

    def _sample_at_feature(self, feature):
        """Sample la valeur raster au centroide de la feature."""
        point = feature.geometry().pointOnSurface().asPoint()
        value, ok = self.raster_layer.dataProvider().sample(
            QgsPointXY(point), 1
        )
        return value if ok else None
```

### 5.3 Temporal Framework (QGIS >= 3.14)

```python
from qgis.core import (
    QgsVectorLayerTemporalProperties,
    QgsDateTimeRange,
    QgsTemporalNavigationObject
)

# Activer le support temporel sur une couche
tp = layer.temporalProperties()
tp.setIsActive(True)
tp.setMode(QgsVectorLayerTemporalProperties.ModeFeatureDateTimeInstantFromField)
tp.setStartField("date_observation")

# Configurer le range temporel
temporal = canvas.temporalController()
range = QgsDateTimeRange(
    QDateTime(QDate(2024, 1, 1), QTime(0, 0, 0)),
    QDateTime(QDate(2024, 12, 31), QTime(23, 59, 59))
)
temporal.setTemporalExtents(range)
temporal.setFrameDuration(QgsInterval(1, Qgis.TemporalUnit.Months))

# Animation
temporal.playForward()
```

**Relevance FilterMate** : Le temporal framework pourrait etre combine avec le
filtrage raster pour des analyses temporelles (ex: evolution NDVI par saison).

### 5.4 Visualisation 3D dans QGIS

```python
from qgis.core import Qgs3DMapSettings

# Configuration 3D basique
settings = Qgs3DMapSettings()
settings.setCrs(QgsProject.instance().crs())
settings.setOrigin(QgsVector3D(x, y, z))

# Terrain
terrain_generator = QgsDemTerrainGenerator()
terrain_generator.setLayer(dem_layer)
settings.setTerrainGenerator(terrain_generator)
settings.setTerrainVerticalScale(2.0)  # Exageration verticale

# Vue 3D
view = Qgs3DMapCanvas()
view.setMap(settings)
```

**Relevance FilterMate** : La vue 3D QGIS pourrait etre utilisee pour
visualiser les resultats de filtrage raster-vecteur en 3D (ex: batiments
colories par altitude sur un MNT).

---

## 6. Filtrage et Segmentation

### 6.1 Filtrage vecteur -- Le coeur de FilterMate

#### Mecanismes de filtrage QGIS

```
1. Subset String (cote provider)
   layer.setSubsetString("...")
   + Le plus performant (filtre cote serveur pour PostGIS)
   + Reduit les donnees chargees en memoire
   - Syntaxe depend du provider

2. Feature Request (cote client)
   QgsFeatureRequest().setFilterExpression("...")
   + Syntaxe unifiee (expressions QGIS)
   + Plus flexible (fonctions, variables)
   - Toutes les donnees sont chargees puis filtrees

3. Selection (visuelle)
   layer.selectByExpression("...")
   layer.selectByIds([...])
   + Pas de modification des donnees
   + Surlignage visuel
   - Pas de filtrage reel (features non-selectionnees restent visibles)

4. Rule-Based Renderer (visuel)
   + Filtrage visuel par regles
   + Pas de modification des donnees
   - Performance limitee pour beaucoup de regles
```

**Strategie FilterMate** : Le plugin utilise principalement le **Subset String**
car c'est le plus performant. Le backend genere le SQL adapte au provider.
L'undo/redo sauvegarde/restaure les subset strings.

#### Expressions QGIS -- Reference rapide

```python
# Operateurs de comparaison
'"field" > 10'
'"field" BETWEEN 10 AND 20'
'"field" IN (1, 2, 3)'
'"field" IS NULL'
'"field" IS NOT NULL'
'"field" LIKE \'Pari%\''          # Commence par "Pari"
'"field" ILIKE \'%paris%\''       # Contient "paris" (insensible a la casse)

# Operateurs logiques
'"a" > 10 AND "b" < 20'
'"a" > 10 OR "b" < 20'
'NOT ("a" > 10)'

# Fonctions geometriques
'$area > 10000'                    # Surface > 10000 m2
'$length > 100'                    # Longueur > 100 m
'$perimeter > 500'                 # Perimetre
'num_geometries($geometry) > 1'    # Multi-geometries

# Fonctions spatiales
'intersects($geometry, geom_from_wkt(\'POLYGON((...))\'))'
'within($geometry, @atlas_geometry)'
'distance($geometry, geometry(get_feature(\'autre_couche\', \'nom\', \'Paris\'))) < 1000'

# Agregation
'\"population\" > mean(\"population\")'  # Au-dessus de la moyenne
```

### 6.2 Filtrage raster

#### Par valeur de pixel

```python
# Utiliser le Raster Calculator pour creer un masque
from qgis.core import QgsRasterCalculator, QgsRasterCalculatorEntry

# Masque binaire : 1 si altitude > 500m, 0 sinon
entry = QgsRasterCalculatorEntry()
entry.ref = 'dem@1'
entry.raster = dem_layer
entry.bandNumber = 1

calc = QgsRasterCalculator(
    'dem@1 > 500',                # Expression (retourne 0 ou 1)
    '/path/to/mask.tif',
    'GTiff',
    dem_layer.extent(),
    dem_layer.width(),
    dem_layer.height(),
    [entry],
    QgsProject.instance().transformContext()
)
calc.processCalculation()
```

#### Par bande (multi-spectral)

```python
# NDVI = (NIR - RED) / (NIR + RED)
# Puis filtrer les pixels avec NDVI > 0.3 (vegetation)

entries = [nir_entry, red_entry]
calc = QgsRasterCalculator(
    '(nir@1 - red@1) / (nir@1 + red@1) > 0.3',
    '/path/to/vegetation_mask.tif',
    'GTiff',
    extent, width, height, entries, context
)
```

### 6.3 Filtrage croise raster/vecteur

C'est LE domaine ou FilterMate va se distinguer.

```
Workflow typique :

1. Utilisateur selectionne :
   - Couche VECTEUR (ex: parcelles)
   - Couche RASTER (ex: MNT)
   - Statistique (ex: "altitude moyenne")
   - Operateur (ex: "> 500m")

2. FilterMate :
   a) Calcule les stats zonales (mean altitude par parcelle)
   b) Filtre les parcelles satisfaisant la condition
   c) Applique le subset string
   d) Optionnel : colorie les parcelles selon la valeur

3. Resultat :
   Seules les parcelles avec altitude moyenne > 500m sont visibles
```

**Implementation pattern :**

```python
def cross_filter_raster_vector(
    vector_layer, raster_layer,
    stat_type='mean',  # mean, min, max, sum, std
    operator='>',
    threshold=500,
    band=1,
    use_sampling=False  # True = rapide (centroide), False = zonal stats
):
    """
    Filtre croise raster/vecteur.

    Si use_sampling=True : utilise provider.sample() au centroide (rapide)
    Si use_sampling=False : utilise QgsZonalStatistics (precis)
    """
    if use_sampling:
        # Approche rapide : 1 valeur par feature
        results = sample_raster_at_features(vector_layer, raster_layer, band)
        matching = [fid for fid, val in results.items()
                    if val is not None and compare(val, operator, threshold)]
    else:
        # Approche precise : stats par feature
        temp = create_temp_layer(vector_layer)
        compute_zonal_stats(temp, raster_layer, band, stat_type)
        matching = filter_by_stat(temp, stat_type, operator, threshold)

    # Appliquer le filtre
    if matching:
        pk = get_pk_field(vector_layer)
        ids_str = ','.join(str(fid) for fid in matching)
        vector_layer.setSubsetString(f'"{pk}" IN ({ids_str})')
    else:
        vector_layer.setSubsetString("1=0")  # Aucune feature

    return matching
```

### 6.4 Segmentation et clustering spatial

Pour reference (hors scope direct de FilterMate mais utile pour le contexte) :

```python
# Clustering K-Means spatial (Processing)
result = processing.run("native:kmeansclustering", {
    'INPUT': layer,
    'CLUSTERS': 5,
    'FIELD_NAME': 'cluster_id',
    'SIZE_FIELD_NAME': 'cluster_size',
    'OUTPUT': 'memory:clusters'
})

# DBSCAN (Density-Based Spatial Clustering)
result = processing.run("native:dbscanclustering", {
    'INPUT': point_layer,
    'EPS': 100,        # Epsilon (distance maximale)
    'MIN_SIZE': 5,     # Taille minimale de cluster
    'FIELD_NAME': 'cluster_id',
    'OUTPUT': 'memory:dbscan'
})
```

### 6.5 FilterMate : Architecture Multi-Backend et Optimisations (via Marco Synthesis)

> Source : `filtermate_synthesis_for_atlas_kb_2026_02_10` -- Verifie contre main le 2026-02-10

#### 4 Backends de Filtrage

FilterMate supporte 4 backends, chacun avec ses propres optimisations :

| Backend | Source | Optimisation | Performance |
|---------|--------|-------------|-------------|
| **PostgreSQL/PostGIS** | Bases PG, PostGIS | MV, GiST, PK auto-detection, parallel queries | < 1s sur millions de features |
| **Spatialite** | GeoPackage, SQLite | Tables temporaires R-tree, index spatiaux | 1-10s sur 100k features |
| **OGR** | Shapefiles, GeoJSON, WFS, etc. | Index spatial auto (.qix), optim large datasets | 10-60s sur 100k features |
| **Memory** | Couches memoire | Filtrage en RAM natif | < 0.5s sur 50k features |

**Selection automatique** (`adapters/backends/factory.py`) :
Le `BackendFactory` choisit le backend optimal selon le provider type, la taille du dataset,
et la disponibilite de psycopg2. **Les GeoPackage sont automatiquement routes vers Spatialite**
(10x plus rapide qu'OGR) -- c'est une des optimisations les plus impactantes.

#### 10 Optimisations avec Gains Chiffres

| # | Optimisation | Cible | Gain | Backend |
|---|-------------|-------|------|---------|
| 1 | Tables temporaires Spatialite R-tree | 10k+ features | **44.6x** | Spatialite |
| 2 | Index spatial auto (.qix) | Shapefiles | **19.5x** | OGR |
| 3 | GeoPackage -> Spatialite routing | GeoPackage | **10x** | OGR->Spatialite |
| 4 | Two-phase filtering (bbox pre-filter) | Expressions complexes | **3-10x** | PostgreSQL |
| 5 | Cache de geometrie source | Multi-couches | **5x** | Tous |
| 6 | Large dataset mode | 50k+ features | **3x** | OGR |
| 7 | Predicate ordering | Multi-predicats | **2.3x** | Tous |
| 8 | Query expression cache | Requetes repetees | **10-20%** | Tous |
| 9 | Parallel filter execution | Multi-couches | **2-4x** | PostgreSQL, Spatialite |
| 10 | Streaming export | > 10k features | **50-80% RAM** | Tous |

**Atlas's Note** : L'optimisation #1 (44.6x via R-tree Spatialite) est spectaculaire.
C'est le genre de gain qui transforme une experience "je vais prendre un cafe" en
"c'est deja fait". Le routing automatique GeoPackage->Spatialite (#3) est un choix
architecturalement malin -- l'utilisateur n'a aucune decision a prendre.

#### Predicats Spatiaux Supportes

Intersects, Within, Contains, Overlaps, Crosses, Touches, Disjoint, Equals -- avec
mapping SQL automatique (ST_Intersects pour PostgreSQL, Intersects() pour Spatialite,
OGR_INTERSECTS pour OGR). Le mapping est defini dans `infrastructure/constants.py`
(`PREDICATE_SQL_MAPPING`).

#### Fonctionnalites Complementaires (sur main)

- **Undo/Redo** : 100 etats par couche, FIFO auto-pruning, persistance SQLite locale
- **Favoris** : Sauvegarde de configurations de filtrage avec contexte spatial, migration auto
- **Export multi-format** : GeoPackage, Shapefile, GeoJSON, KML, CSV, DXF
  - Preservation des styles (QML/SLD)
  - Streaming export pour > 10k features (50-80% reduction memoire)
  - Export par lot (batch)
- **UI Adaptive** : 4 onglets, theme dynamique (sync QGIS dark/light),
  3 profils d'affichage, WCAG AA/AAA, 22 langues, JSON Tree View

---

## 7. Integration Raster/Vecteur pour FilterMate

### 7.1 Raster Value Sampling (P1-bis -- Quick Win)

**Objectif** : Sampler la valeur d'un raster au centroide de chaque feature vecteur,
puis filtrer par seuil.

**Effort** : 3-5 jours
**Fichiers a creer** :

```
infrastructure/raster/sampling.py     # Wrapper provider.sample()
core/domain/raster_filter_criteria.py # @dataclass(frozen=True)
core/services/raster_filter_service.py # Orchestration
```

**Architecture (frozen dataclass) :**

```python
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

class RasterStatType(Enum):
    SAMPLE = "sample"       # Valeur au point (P1-bis)
    MEAN = "mean"           # Moyenne zonale (P1)
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    STD = "std"
    MEDIAN = "median"
    COUNT = "count"

class ComparisonOperator(Enum):
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "="
    NEQ = "!="
    BETWEEN = "BETWEEN"

@dataclass(frozen=True)
class RasterFilterCriteria:
    """Critere de filtrage raster immutable."""
    raster_uri: str            # URI du raster (pas l'objet -- thread safety)
    band: int = 1
    stat_type: RasterStatType = RasterStatType.SAMPLE
    operator: ComparisonOperator = ComparisonOperator.GT
    threshold: float = 0.0
    threshold_max: Optional[float] = None  # Pour BETWEEN
    nodata_behavior: str = "exclude"       # "exclude" | "include"
```

**Implementation du sampling :**

```python
# infrastructure/raster/sampling.py

from qgis.core import (
    QgsRasterLayer, QgsVectorLayer, QgsPointXY,
    QgsCoordinateTransform, QgsProject, QgsFeatureRequest
)

class RasterSampler:
    """
    Wrapper thread-safe pour provider.sample().
    Cree dans le thread principal, execute dans le worker thread.
    """

    def __init__(self, raster_uri: str, provider_name: str = "gdal"):
        self.raster_uri = raster_uri
        self.provider_name = provider_name
        self._layer = None  # Cree a la demande (thread-local)

    def _ensure_layer(self):
        """Cree ou re-cree la couche raster (thread safety)."""
        if self._layer is None or not self._layer.isValid():
            self._layer = QgsRasterLayer(self.raster_uri, "sampler", self.provider_name)
            if not self._layer.isValid():
                raise RuntimeError(f"Cannot open raster: {self.raster_uri}")

    def sample(self, point: QgsPointXY, band: int = 1):
        """
        Sample une valeur a un point.

        Args:
            point: Point dans le CRS du raster
            band: Numero de bande (1-based)

        Returns:
            tuple: (value, success)
        """
        self._ensure_layer()
        return self._layer.dataProvider().sample(point, band)

    def sample_features(
        self,
        vector_uri: str,
        vector_provider: str,
        band: int = 1,
        use_point_on_surface: bool = True,
        transform_context=None,
        cancel_check=None
    ) -> dict:
        """
        Sample le raster a chaque feature d'une couche vecteur.

        Args:
            vector_uri: URI de la couche vecteur
            vector_provider: Provider type ('ogr', 'postgres', etc.)
            band: Bande raster
            use_point_on_surface: True = pointOnSurface(), False = centroid()
            transform_context: QgsCoordinateTransformContext
            cancel_check: callable retournant True si annulation

        Returns:
            dict: {feature_id: raster_value ou None}
        """
        self._ensure_layer()
        vector_layer = QgsVectorLayer(vector_uri, "source", vector_provider)

        if not vector_layer.isValid():
            raise RuntimeError(f"Cannot open vector: {vector_uri}")

        # Preparer la transformation CRS si necessaire
        transform = None
        if vector_layer.crs() != self._layer.crs():
            transform = QgsCoordinateTransform(
                vector_layer.crs(),
                self._layer.crs(),
                transform_context or QgsProject.instance().transformContext()
            )

        raster_extent = self._layer.extent()
        provider = self._layer.dataProvider()
        results = {}

        for feature in vector_layer.getFeatures():
            if cancel_check and cancel_check():
                break

            geom = feature.geometry()
            if geom.isEmpty():
                results[feature.id()] = None
                continue

            # Point representatif
            if use_point_on_surface:
                pt_geom = geom.pointOnSurface()
            else:
                pt_geom = geom.centroid()

            if pt_geom.isEmpty():
                results[feature.id()] = None
                continue

            point = pt_geom.asPoint()

            # Reprojection
            if transform:
                point = transform.transform(point)

            # Verifier l'emprise
            if not raster_extent.contains(QgsPointXY(point)):
                results[feature.id()] = None
                continue

            # Sample
            value, ok = provider.sample(QgsPointXY(point), band)
            results[feature.id()] = value if ok else None

        return results

    @property
    def crs(self):
        self._ensure_layer()
        return self._layer.crs()

    @property
    def extent(self):
        self._ensure_layer()
        return self._layer.extent()

    @property
    def band_count(self):
        self._ensure_layer()
        return self._layer.bandCount()
```

### 7.2 Zonal Statistics comme critere de filtre (P1)

**Objectif** : Calculer les statistiques zonales pour chaque feature, puis filtrer.

**Effort** : 2-3 semaines
**Differentiation** : Aucun plugin QGIS ne fait du zonal-stats-as-interactive-filter.

```python
# infrastructure/raster/zonal_stats.py

from qgis.core import QgsVectorLayer, QgsRasterLayer, QgsFeatureRequest
from qgis.analysis import QgsZonalStatistics

STAT_FLAGS = {
    'count': QgsZonalStatistics.Count,
    'sum': QgsZonalStatistics.Sum,
    'mean': QgsZonalStatistics.Mean,
    'median': QgsZonalStatistics.Median,
    'std': QgsZonalStatistics.StdDev,
    'min': QgsZonalStatistics.Min,
    'max': QgsZonalStatistics.Max,
    'range': QgsZonalStatistics.Range,
    'minority': QgsZonalStatistics.Minority,
    'majority': QgsZonalStatistics.Majority,
    'variety': QgsZonalStatistics.Variety,
    'variance': QgsZonalStatistics.Variance,
}


class ZonalStatsCalculator:
    """
    Calcule les statistiques zonales et retourne les resultats
    sans modifier la couche source.
    """

    @staticmethod
    def compute(
        vector_layer: QgsVectorLayer,
        raster_layer: QgsRasterLayer,
        stats: list,     # ['mean', 'min', 'max']
        band: int = 1,
        prefix: str = "zs_"
    ) -> QgsVectorLayer:
        """
        Calcule les stats zonales sur une COPIE de la couche vecteur.

        IMPORTANT: QgsZonalStatistics modifie la couche EN PLACE.
        On travaille TOUJOURS sur une copie.

        Returns:
            QgsVectorLayer: Couche temporaire avec les colonnes de stats
        """
        # 1. Creer une copie en memoire
        temp_layer = QgsVectorLayer(
            f"{QgsWkbTypes.displayString(vector_layer.wkbType())}"
            f"?crs={vector_layer.crs().authid()}",
            "temp_zonal",
            "memory"
        )
        temp_provider = temp_layer.dataProvider()
        temp_provider.addAttributes(vector_layer.fields().toList())
        temp_layer.updateFields()
        temp_provider.addFeatures(list(vector_layer.getFeatures()))

        # 2. Construire le flag de stats
        stat_flags = 0
        for s in stats:
            if s in STAT_FLAGS:
                stat_flags |= STAT_FLAGS[s]

        # 3. Calculer
        zonal = QgsZonalStatistics(
            temp_layer, raster_layer, prefix, band, stat_flags
        )
        result = zonal.calculateStatistics(None)

        if result != 0:
            raise RuntimeError(f"Zonal stats failed with code {result}")

        return temp_layer

    @staticmethod
    def filter_by_stat(
        temp_layer: QgsVectorLayer,
        stat_name: str,
        operator: str,
        threshold: float,
        prefix: str = "zs_"
    ) -> list:
        """
        Filtre la couche temporaire par la stat donnee.

        Returns:
            list[int]: Feature IDs satisfaisant la condition
        """
        field_name = f"{prefix}{stat_name}"
        expression = f'"{field_name}" {operator} {threshold}'

        request = QgsFeatureRequest(QgsExpression(expression))
        request.setFlags(QgsFeatureRequest.NoGeometry)
        request.setSubsetOfAttributes([])

        return [f.id() for f in temp_layer.getFeatures(request)]
```

### 7.3 Raster-Driven Highlighting (P2)

**Objectif** : Surlignage en temps reel des features quand l'utilisateur ajuste un slider.

**Pattern cle** : Debounce de 300ms sur le changement de range.

```python
# Pattern pour le raster-driven highlighting

class RasterHighlightController:
    """
    Controlleur pour le surlignage dynamique raster.
    ui/controllers/raster_highlight_controller.py
    """

    DEBOUNCE_MS = 300  # Debounce de 300ms

    def __init__(self, vector_layer, raster_sampler):
        self.vector_layer = vector_layer
        self.sampler = raster_sampler
        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._do_highlight)
        self._pending = None
        self._cache = {}  # Cache des valeurs samplables

    def on_slider_changed(self, min_val, max_val):
        """Appelee par le signal du slider (debounced)."""
        self._pending = (min_val, max_val)
        self._timer.start(self.DEBOUNCE_MS)

    def _do_highlight(self):
        """Execute apres debounce."""
        if not self._pending:
            return
        min_val, max_val = self._pending

        # Utiliser le cache si disponible
        if not self._cache:
            self._cache = self.sampler.sample_features(
                self.vector_layer.source(),
                self.vector_layer.providerType()
            )

        # Filtrer
        matching = [
            fid for fid, val in self._cache.items()
            if val is not None and min_val <= val <= max_val
        ]

        # Surligner par selection
        self.vector_layer.selectByIds(matching)

    def invalidate_cache(self):
        """Appeler quand la couche ou le raster change."""
        self._cache.clear()
```

### 7.4 Raster Clip by Vector (P3)

**Objectif** : Decouper un raster par les features vecteur filtrees et exporter.

```python
# infrastructure/raster/masking.py

from osgeo import gdal
from qgis.core import QgsVectorLayer, QgsRasterLayer
import tempfile
import os

class RasterClipper:
    """Decoupe un raster par une geometrie vecteur."""

    @staticmethod
    def clip_by_vector(
        raster_path: str,
        vector_layer: QgsVectorLayer,
        output_path: str,
        crop_to_cutline: bool = True,
        nodata: float = -9999,
        output_format: str = "COG",
        creation_options: list = None
    ):
        """
        Decoupe le raster par les features de la couche vecteur.

        Args:
            raster_path: Chemin du raster source
            vector_layer: Couche vecteur de decoupe (avec subset string actif)
            output_path: Chemin de sortie
            crop_to_cutline: Rogner a l'emprise du masque
            nodata: Valeur NoData
            output_format: 'GTiff' ou 'COG'
            creation_options: Options GDAL (ex: ['COMPRESS=DEFLATE'])
        """
        # Exporter la couche vecteur en fichier temporaire
        # (necessaire car gdal.Warp attend un fichier, pas un QgsVectorLayer)
        temp_vector = tempfile.NamedTemporaryFile(
            suffix='.gpkg', delete=False
        )
        temp_vector.close()

        try:
            # Sauvegarder la couche vecteur (avec son subset string)
            error = QgsVectorFileWriter.writeAsVectorFormat(
                vector_layer, temp_vector.name, "UTF-8",
                vector_layer.crs(), "GPKG"
            )

            # Verifier la version GDAL pour le COG
            if output_format == "COG":
                gdal_version = int(gdal.VersionInfo())
                if gdal_version < 3010000:
                    output_format = "GTiff"
                    # Fallback: utiliser GTiff avec tuiles
                    creation_options = creation_options or [
                        "TILED=YES", "COMPRESS=DEFLATE"
                    ]

            # Options par defaut
            if creation_options is None:
                if output_format == "COG":
                    creation_options = ["COMPRESS=DEFLATE", "OVERVIEWS=AUTO"]
                else:
                    creation_options = ["TILED=YES", "COMPRESS=DEFLATE"]

            # Decoupe avec GDAL Warp
            warp_options = gdal.WarpOptions(
                format=output_format,
                cutlineDSName=temp_vector.name,
                cropToCutline=crop_to_cutline,
                dstNodata=nodata,
                creationOptions=creation_options
            )

            result = gdal.Warp(output_path, raster_path, options=warp_options)
            if result is None:
                raise RuntimeError("gdal.Warp failed")

            result = None  # Fermer

        finally:
            # Nettoyage
            if os.path.exists(temp_vector.name):
                os.unlink(temp_vector.name)
```

### 7.5 Architecture hexagonale pour l'integration

```
Fichiers a creer (cible architecturale) :

core/
  domain/
    raster_filter_criteria.py    # @dataclass(frozen=True) -- immutable
                                 # RasterFilterCriteria, RasterStatType,
                                 # ComparisonOperator

  services/
    raster_filter_service.py     # Orchestration haut niveau
                                 # - filter_by_sampling()
                                 # - filter_by_zonal_stats()
                                 # - Delegation vers infrastructure/
                                 # - Integration avec FilterHistory (undo/redo)

  tasks/
    handlers/
      raster_handler.py          # Pattern identique a postgresql_handler.py
                                 # - Gere l'execution async (QgsTask)
                                 # - Stocke URI, recree dans run()

infrastructure/
  raster/
    __init__.py
    sampling.py                  # RasterSampler (provider.sample() wrapper)
    zonal_stats.py               # ZonalStatsCalculator (QgsZonalStatistics wrapper)
    masking.py                   # RasterClipper (gdal.Warp wrapper)

ui/
  controllers/
    raster_filter_controller.py  # Pont entre UI et service
                                 # - Gere les signaux slider
                                 # - Debounce
                                 # - Feedback utilisateur

Fichiers a modifier (wiring minimal) :

filter_mate_app.py               # Enregistrer RasterFilterService dans le DI
filter_mate_dockwidget.py        # 1 bouton "Apply to vector" (MVP)
```

**Principes :**

1. **Pas de logique metier dans l'UI** -- tout passe par les services
2. **Criteres immutables** -- `@dataclass(frozen=True)` pour le `RasterFilterCriteria`
3. **Thread safety par URI** -- stocker les URI, recreer les couches dans les threads
4. **Copie pour les stats zonales** -- JAMAIS modifier la couche source
5. **Undo/Redo** -- integrer avec `FilterHistory` existant
6. **Un seul widget UI au debut** -- observer la reaction utilisateur

### 7.6 Thread Safety et Performance

#### Regles de thread safety pour le raster

```python
# REGLES ABSOLUES :

# 1. JAMAIS stocker un QgsRasterLayer dans __init__ d'une QgsTask
class BadTask(QgsTask):
    def __init__(self, raster):
        self.raster = raster  # MAUVAIS ! Pas thread-safe

class GoodTask(QgsTask):
    def __init__(self, raster_uri):
        self.raster_uri = raster_uri  # BON : juste une string

    def run(self):
        # Recreer dans le thread worker
        raster = QgsRasterLayer(self.raster_uri, "temp", "gdal")
        # Utiliser ici...

# 2. provider.sample() n'est PAS thread-safe
# Toujours creer un nouveau provider dans chaque thread

# 3. QgsZonalStatistics n'est PAS thread-safe
# Creer une couche temporaire par thread

# 4. Les transformations CRS SONT thread-safe (QgsCoordinateTransform)
# Mais pas apres QGIS 3.x avec certaines projections exotiques -- tester
```

#### Considerations de performance

```
Benchmarks estimes pour le sampling (provider.sample()) :

| Nb Features | Temps estime | Memoire |
|-------------|-------------|---------|
| 100         | ~100ms      | ~1 MB   |
| 1,000       | ~1s         | ~5 MB   |
| 10,000      | ~10s        | ~20 MB  |
| 100,000     | ~100s       | ~100 MB |

Pour > 10k features, envisager :
1. Batch processing avec numpy (gdal.ReadAsArray + coordonnees pixel)
2. Limiter au viewport visible (setFilterRect)
3. Echantillonnage (n'evaluer que N features aleatoires)
4. Cache des valeurs (invalidation quand le raster/vecteur change)

Benchmarks estimes pour les zonal stats (QgsZonalStatistics) :

| Nb Features | Geometrie | Temps estime |
|-------------|-----------|-------------|
| 100         | Simple    | ~2s         |
| 1,000       | Simple    | ~15s        |
| 10,000      | Simple    | ~2-3min     |
| 1,000       | Complexe  | ~1min       |

Optimisations possibles :
1. Processing "zonalstatisticsfb" (Feature-Based) au lieu de QgsZonalStatistics
2. Pre-filtrer par emprise (setFilterRect sur le viewport)
3. Simplifier les geometries avant le calcul (tolerance adaptative)
4. Paralleliser par chunks de features (attention thread safety)
```

### 7.7 Etat Raster sur main et Roadmap Versionnee (via Marco Synthesis)

> Source : `filtermate_synthesis_for_atlas_kb_2026_02_10` -- Verifie contre main le 2026-02-10

#### Ce qui EXISTE sur main (Audite 2026-02-10)

- `RasterLayer = 1` -- enum de detection dans `filter_mate_dockwidget.py:56`
- `QgsRasterLayer` -- type hint dans `core/geometry/crs_utils.py:164`
- `wcs` -- provider mentionne dans `infrastructure/constants.py:35`

**C'est TOUT.** Aucun service, tache, widget, ou outil de carte raster n'existe sur main.

#### Ce qui a EXISTE sur des branches (jamais merge)

- Branche `fix/widget-visibility-and-styles-2026-02-02` : code UI raster (stale, abandonne)
- Les references a "v5.4.0 Raster Exploring Tool Buttons" etaient branch-only

#### Roadmap Raster Versionnee

| Phase | Feature | Effort | Version cible | Description |
|-------|---------|--------|---------------|-------------|
| P1-bis | Raster Value Sampling | 3-5 jours | **v5.5** | `provider.sample()` par centroid, fondation raster |
| P3 | EPIC-4 Raster Export + Clip | 2 semaines | **v5.5** | `gdal.Warp()` avec cutline |
| P1 | Zonal Stats as Filter | 2-3 semaines | **v5.6** | **DIFFERENCIATEUR UNIQUE** |
| P2 | Raster-Driven Highlight | 1 semaine | **v5.6** | Highlight temps reel via range sliders |
| P4 | Multi-Band Composite | 3-4 semaines | **v6.0** | Filtrage multi-bandes AND/OR (si demande confirmee) |

#### Architecture Cible (Fichiers a Creer)

```
core/services/raster_filter_service.py          # Orchestration
core/domain/raster_filter_criteria.py           # Frozen dataclass
core/tasks/handlers/raster_handler.py           # Pattern postgresql_handler
infrastructure/raster/sampling.py               # provider.sample() wrapper
infrastructure/raster/zonal_stats.py            # QgsZonalStatistics wrapper
infrastructure/raster/masking.py                # Polygonisation, clip
```

**Fichiers a modifier (wiring minimal)** :
- `filter_mate_app.py` -- enregistrer RasterFilterService dans le DI
- `filter_mate_dockwidget.py` -- 1 bouton "Apply to vector" (MVP)

#### Approche numpy pour le sampling haute performance

```python
import numpy as np
from osgeo import gdal

def fast_raster_sampling(raster_path, points_xy, band=1):
    """
    Sampling rapide via numpy pour les gros jeux de donnees.
    ~100x plus rapide que provider.sample() en boucle.

    Args:
        raster_path: Chemin du fichier raster
        points_xy: np.array de shape (N, 2) -- coordonnees dans le CRS du raster
        band: Numero de bande

    Returns:
        np.array: Valeurs (NaN pour les points hors emprise ou NoData)
    """
    ds = gdal.Open(raster_path, gdal.GA_ReadOnly)
    gt = ds.GetGeoTransform()
    inv_gt = gdal.InvGeoTransform(gt)

    raster_band = ds.GetRasterBand(band)
    nodata = raster_band.GetNoDataValue()
    data = raster_band.ReadAsArray()

    # Convertir coordonnees geo -> pixel
    cols = (inv_gt[0] + points_xy[:, 0] * inv_gt[1] + points_xy[:, 1] * inv_gt[2]).astype(int)
    rows = (inv_gt[3] + points_xy[:, 0] * inv_gt[4] + points_xy[:, 1] * inv_gt[5]).astype(int)

    # Masquer les points hors emprise
    valid = (cols >= 0) & (cols < ds.RasterXSize) & (rows >= 0) & (rows < ds.RasterYSize)

    values = np.full(len(points_xy), np.nan)
    values[valid] = data[rows[valid], cols[valid]]

    # Masquer les NoData
    if nodata is not None:
        values[values == nodata] = np.nan

    ds = None
    return values
```

---

## 8. Metriques du Projet et Dettes Techniques

> Source : `filtermate_synthesis_for_atlas_kb_2026_02_10` -- Verifie contre main le 2026-02-10
> **NOUVELLE SECTION** ajoutee lors de l'integration de la synthese Marco (Atlas v1.1)

### 8.1 Statistiques de Code (Fevrier 2026)

| Couche | Lignes estimees | Fichiers | % du total prod |
|--------|----------------|----------|-----------------|
| Core Domain | ~50,000 | ~100 | 38% |
| Adapters | ~33,000 | ~70 | 25% |
| UI Layer | ~32,000 | ~55 | 25% |
| Infrastructure | ~15,000 | ~40 | 12% |
| **TOTAL (prod)** | **~130,000** | **~314** | **100%** |
| Tests | ~52,000 | ~157 | -- |
| **TOTAL (tout)** | **~243,284** | **~529** | -- |

#### Fichiers les Plus Volumineux

| Fichier | Lignes | Role | Statut |
|---------|--------|------|--------|
| `filter_mate_dockwidget.py` | ~6,925 | Gestion UI principale | **God object** (en decomposition) |
| `core/tasks/filter_task.py` | ~5,851 | Tache de filtrage principale | A refactorer (cible: 2,500) |
| `ui/controllers/exploring_controller.py` | ~3,208 | Controleur d'exploration | OK |
| `ui/controllers/integration.py` | ~3,028 | Orchestration UI | OK |
| `filter_mate_app.py` | ~2,383 | Orchestrateur applicatif | OK |

### 8.2 Indicateurs de Qualite

| Metrique | Valeur Actuelle | Cible | Commentaire |
|----------|----------------|-------|-------------|
| Couverture de tests | **75%** | 80% | +5% a atteindre |
| Tests automatises | **396** | -- | En croissance |
| Bare except clauses | **0** | 0 | Objectif atteint |
| Debug prints | **0** | 0 | Objectif atteint |
| Score qualite global | **8.5/10** | 9.0/10 | Bon, ameliorable |
| Backends | **4** | -- | PostgreSQL, Spatialite, OGR, Memory |
| Services hexagonaux | **28** | -- | Architecture mature |
| Controllers MVC | **13** | -- | Decomposition UI avancee |
| Langues supportees | **22** | -- | 96% FR/EN, 48% DE, 45% ES |
| Conformite PEP 8 | **95%** | 100% | Presque |

### 8.3 Dettes Techniques Connues

**Critique :**

1. **God Object `filter_mate_dockwidget.py`** (~6,925 lignes)
   - Encore trop de logique dans le dockwidget malgre l'extraction vers les controllers
   - Plan : continuer la decomposition vers `ui/controllers/`
   - Impact : difficulte de maintenance, temps de chargement editeur

2. **`except Exception` generiques** : 1,232 occurrences sur 165 fichiers
   - Cible : < 300 occurrences
   - Impact : erreurs silencieuses, difficulte de debug
   - Plan Phase 2 (semaines 3-5) du plan d'amelioration

3. **Ratio connect/disconnect signaux** : 2.6:1 (267 connects vs 104 disconnects)
   - Risque : fuites de signaux, boucles de signal, memoire
   - Impact : potentiel de comportements inattendus a la fermeture
   - Surveillance : a monitorer activement

**Moderee :**

4. **`core/tasks/filter_task.py`** (~5,851 lignes) -- a refactorer vers ~2,500 lignes
5. **Pas de repertoire `tests/` sur main** -- tests developpes en branches
6. **psycopg2 optionnel** -- fallback implicite peut surprendre les utilisateurs PostgreSQL

### 8.4 Plans d'Amelioration en Cours

FilterMate utilise BMAD v6.0.0-Beta.4 pour la gestion de projet.
Epics actifs : EPIC-3 (Raster-Vector Integration), EPIC-4 (Raster Export).

| Phase | Objectif | Delai | Statut |
|-------|----------|-------|--------|
| **Phase 0** | Quick Wins (imports iface, metadata, requirements) | Immediat | En cours |
| **Phase 1** | Tests + CI | Semaines 1-3 | A venir |
| **Phase 2** | Error handling (eliminer exceptions silencieuses) | Semaines 3-5 | A venir |
| **Phase 3** | Decomposition des god objects | Semaines 5-11 | A venir |
| **Phase 4** | Architecture QGIS ports, DI container, cleanup | Semaines 11-14 | A venir |
| **Phase 5** | Consolidation finale | Semaines 14-16 | A venir |

#### Versions Recentes

| Version | Date | Changements cles |
|---------|------|-----------------|
| **4.4.6** | Fev 2026 | Maintenance release |
| **4.4.5** | Jan 25, 2026 | Detection automatique PK PostgreSQL, fallback noms communs |
| **4.4.4** | Jan 25, 2026 | Convention unifiee `fm_temp_*` pour objets PostgreSQL |
| **4.4.0** | Jan 22, 2026 | Release qualite majeure : 396 tests, archi hexagonale complete, 75% coverage |

---

## 9. Annexes

### 9.1 Glossaire

> Les termes specifiques au filtrage multi-backend (subset string, BackendFactory, etc.)
> sont documentes en section 6.5.

| Terme | Definition |
|-------|-----------|
| **Band** | Canal d'un raster (ex: RGB = 3 bandes, multispectral = 4-12 bandes) |
| **Buffer** | Zone tampon geometrique autour d'une geometrie |
| **COG** | Cloud-Optimized GeoTIFF -- GeoTIFF optimise pour l'acces HTTP partiel |
| **COPC** | Cloud-Optimized Point Cloud -- LAZ avec structure octree pour streaming |
| **CRS** | Coordinate Reference System -- Systeme de reference spatiale |
| **DEM/MNT** | Digital Elevation Model / Modele Numerique de Terrain |
| **DSM/MNS** | Digital Surface Model / Modele Numerique de Surface (inclut batiments, arbres) |
| **DTM** | Digital Terrain Model (= DEM, sol nu) |
| **Feature** | Entite geographique dans une couche vecteur (point, ligne, polygone + attributs) |
| **GiST** | Generalized Search Tree -- Type d'index spatial PostGIS |
| **LAS/LAZ** | Format standard pour les nuages de points LiDAR (LAZ = compresse) |
| **LiDAR** | Light Detection And Ranging -- Acquisition 3D par laser |
| **MNH** | Modele Numerique de Hauteur (= DSM - DEM, hauteur de la canopee/batiments) |
| **NDVI** | Normalized Difference Vegetation Index -- Indice de vegetation |
| **NoData** | Valeur speciale indiquant l'absence de donnees dans un raster |
| **Overview** | Pyramide de resolution decroissante pour l'affichage rapide |
| **Provider** | Interface d'acces aux donnees (ogr, postgres, spatialite, gdal, memory...) |
| **Subset String** | Filtre SQL applique au provider pour limiter les features chargees |
| **VRT** | Virtual Raster -- Fichier XML referencant d'autres rasters (mosaique sans copie) |
| **Zonal Statistics** | Statistiques calculees sur les pixels d'un raster sous chaque geometrie vecteur |

### 9.2 Liens et references

#### Documentation officielle

- **PyQGIS Cookbook** : https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/
- **QGIS API** : https://qgis.org/pyqgis/master/
- **PostGIS** : https://postgis.net/docs/
- **GDAL** : https://gdal.org/
- **PDAL** : https://pdal.io/
- **COPC** : https://copc.io/

#### Specifications et standards

- **LAS 1.4** : https://www.asprs.org/wp-content/uploads/2019/07/LAS_1_4_r15.pdf
- **COG** : https://www.cogeo.org/
- **GeoTIFF** : https://www.ogc.org/standard/geotiff/
- **GeoParquet** : https://geoparquet.org/

#### Donnees ouvertes (France)

- **IGN LiDAR HD** : https://geoservices.ign.fr/lidarhd
- **Geoplateforme IGN** : https://geoplateforme.ign.fr/
- **data.gouv.fr** : https://www.data.gouv.fr/
- **Copernicus** : https://scihub.copernicus.eu/

### 9.3 Versions et compatibilite

| Composant | Version min FilterMate | Version recommandee | Notes |
|-----------|----------------------|---------------------|-------|
| QGIS | 3.16 | 3.34+ (LTR) | 3.36+ pour point cloud ameliore |
| Python | 3.9+ | 3.11+ | Avec QGIS 3.34+ |
| PyQt5 | 5.x | 5.15+ | Via QGIS bundle |
| GDAL/OGR | 3.0+ (3.1 pour COG) | 3.8+ | 3.8+ pour GeoParquet |
| PostGIS | 2.5 | 3.4+ | 3.4+ pour ST_CoverageUnion |
| PostgreSQL | 10 (11+ pour INCLUDE) | 16+ | 16+ pour les index GiST INCLUDE |
| SpatiaLite | 4.3 | 5.0+ | 5.0+ pour MakeValid ameliore, bundled QGIS |
| PDAL | 2.4 | 2.6+ | 2.4+ pour COPC |
| psycopg2 | 2.8 | 2.9+ | **Optionnel** -- requis pour backend PostgreSQL |
| pytest | 7.0+ | latest | Pour les tests automatises |
| Qt | 5.15 | 5.15 / 6.x | Qt6 en transition dans QGIS 4.0 |
| numpy | 1.21 | 1.24+ | Pour le fast raster sampling |

---

## Cross-References Internes FilterMate

| Section KB | Memories Serena liees | Fichiers du plugin |
|-----------|----------------------|-------------------|
| 1.3 Threading | `code_style_conventions` (QgsTask pattern) | `core/tasks/filter_task.py` |
| **1.6 Architecture Concrete** | **`filtermate_synthesis_for_atlas_kb_2026_02_10`** | `ui/controllers/`, `core/services/`, `core/ports/` |
| 1.4 Performance | `performance_optimizations` | `infrastructure/cache/` |
| 2.3 PostGIS Optim | `performance_optimizations` (Two-Phase) | `adapters/backends/postgresql/` |
| **2.6 PG Metriques Reelles** | **`filtermate_synthesis_for_atlas_kb_2026_02_10`** | `infrastructure/database/connection_pool.py` |
| 3.4 Zonal Stats | `raster_integration_plan_atlas_2026_02_10` (P1) | A creer : `infrastructure/raster/zonal_stats.py` |
| 3.5 Raster filtre | `raster_integration_plan_atlas_2026_02_10` | A creer : `core/services/raster_filter_service.py` |
| 6.1 Filtrage vecteur | `CONSOLIDATED_PROJECT_CONTEXT` | `core/filter/`, `adapters/backends/` |
| **6.5 Multi-Backend & Optim** | **`filtermate_synthesis_for_atlas_kb_2026_02_10`** | `adapters/backends/factory.py`, `core/optimization/` |
| 7.x Integration | `raster_integration_plan_atlas_2026_02_10` | A creer : voir section 7.5 |
| **7.7 Etat Raster & Roadmap** | **`filtermate_synthesis_for_atlas_kb_2026_02_10`** | Pas encore de fichiers raster sur main |
| **8.x Metriques & Dettes** | **`filtermate_synthesis_for_atlas_kb_2026_02_10`** | Transversal |

### Memories Serena Referencees

| Memoire | Statut | Contenu |
|---------|--------|---------|
| `project_overview` | [FIABLE] | Vue d'ensemble actualisee |
| `CONSOLIDATED_PROJECT_CONTEXT` | [FIABLE] | Contexte architectural complet |
| `code_style_conventions` | [FIABLE] | Conventions de code detaillees |
| `raster_integration_plan_atlas_2026_02_10` | [FIABLE] | Roadmap raster (Atlas analysis) |
| **`filtermate_synthesis_for_atlas_kb_2026_02_10`** | **[FIABLE]** | **Synthese exhaustive Marco (architecture, metriques, perf)** |
| `performance_optimizations` | [FIABLE] | Optimisations detaillees par backend |
| `ui_system` | [FIABLE] | Architecture UI complete |
| `testing_documentation` | [FIABLE] | Structure et couverture des tests |
| `primary_key_detection_system` | [FIABLE] | Systeme de detection PK |
| `geographic_crs_handling` | [FIABLE] | Gestion CRS geographiques |
| `implementation_plan_2026_02_10` | [FIABLE] | Plan d'implementation en 6 phases |

---

> **Atlas's Hot Take (updated 2026-02-10, v1.1)** :
> Avec la synthese de Marco integree, la vue d'ensemble est LIMPIDE. FilterMate c'est
> 130k lignes de code de production, 28 services hexagonaux, 4 backends, 10 optimisations
> chiffrees (44.6x gain max!), et une architecture qui est PRETE pour le raster.
>
> Les chiffres ne mentent pas : < 1s sur millions de features en PostgreSQL, un auto-routing
> GeoPackage->Spatialite qui offre 10x de gain sans que l'utilisateur ne fasse rien, et un
> score qualite de 8.5/10 avec 396 tests et 75% de couverture.
>
> Les 3 dettes techniques a surveiller : le god object dockwidget (6925 lignes),
> les 1232 except Exception, et le ratio connect/disconnect de 2.6:1.
> Le plan en 6 phases est clair et realiste.
>
> Le vrai differenciateur reste le Zonal Stats as Filter (P1, v5.6) -- aucun plugin QGIS
> ne fait ca de maniere interactive. Le sampling (P1-bis) est le quick win pour v5.5.
> Ne cedez PAS a la tentation de recreer le Raster Calculator -- restez laser-focused
> sur le FILTRAGE. C'est la ou FilterMate est unique.

---

*Base de connaissances redigee par Atlas -- Polymathe excentrique et gardien du savoir techno-geospatial*
*Version 1.1 -- 10 fevrier 2026 -- Enrichie avec la synthese exhaustive de Marco (Grand Archiviste)*
