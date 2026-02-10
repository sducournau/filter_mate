# Systeme Dual Vector/Raster pour FilterMate
## Document de Conception -- Atlas, Veille Technologique Geospatiale

**Date** : 10 fevrier 2026
**Version** : 1.0
**Auteur** : Atlas (Marco)
**Destinataire** : Simon (Lead Dev FilterMate)
**Branche cible** : `main` (implementation progressive)

---

## Table des Matieres

1. [Vision Globale](#1-vision-globale)
2. [Architecture du Dual Panel](#2-architecture-du-dual-panel)
3. [Panel Raster Exploring -- Conception Detaillee](#3-panel-raster-exploring)
4. [Panel Vector Exploring -- Evolution](#4-panel-vector-exploring)
5. [Extension aux Autres Panels](#5-extension-aux-autres-panels)
6. [Wireframes Textuels](#6-wireframes-textuels)
7. [Integration Technique dans l'Architecture Hexagonale](#7-integration-technique)
8. [Priorisation et Feuille de Route](#8-priorisation)
9. [Considerations Techniques](#9-considerations-techniques)

---

## 1. Vision Globale

### Le Probleme

FilterMate est aujourd'hui un outil 100% vectoriel. Les analystes SIG travaillent pourtant quotidiennement sur des donnees hybrides : BD TOPO en PostGIS *et* MNT IGN en GeoTIFF, parcelles cadastrales *et* images Sentinel-2, bati 3D *et* LiDAR HD rasterise. Le passage d'un monde a l'autre necessite aujourd'hui des outils separes -- Value Tool pour les pixels, Select by Expression pour les vecteurs, Processing pour les stats zonales. C'est l'equivalent de devoir jongler entre trois cartes papier alors qu'on veut une seule vue unifiee.

### La Solution : Dual Mode Context-Aware

Le systeme dual ne se contente pas d'ajouter un onglet "Raster" a cote du "Vecteur". Il **detecte automatiquement** le type de la couche active dans le panneau QGIS Layers et bascule le contexte de l'interface en consequence. C'est le pattern que Microsoft Flight Simulator 2024 utilise pour son HUD : les instruments changent selon que vous etes en VFR ou IFR, mais le cockpit reste le meme.

### Principes Directeurs

1. **Context-Aware avant tout** : Le panel s'adapte a la couche active, pas l'inverse
2. **Decouplage strict** : Les composants raster sont des modules independants, pas des greffes sur le code vectoriel
3. **Progressive Disclosure** : Les fonctions avancees (detection d'objets, multi-bandes) sont cachees par defaut
4. **Coherence UI** : Memes patterns visuels (QgsCollapsibleGroupBox, meme disposition keys/content)
5. **Performance** : Tout calcul raster lourd passe par QgsTask (thread-safe)

---

## 2. Architecture du Dual Panel

### 2.1 Mecanisme de Basculement

**Choix technique : QStackedWidget + Auto-Detection**

J'ai evalue trois approches :

| Approche | Avantage | Inconvenient | Verdict |
|----------|----------|-------------|---------|
| QTabWidget (onglets V/R) | Explicite, toujours accessible | Encombrement vertical, choix manuel | NON |
| QStackedWidget + toggle | Compact, basculement rapide | Bouton supplementaire | PARTIELLEMENT |
| QStackedWidget + auto-detect | Zero friction, intelligent | Necessite fallback manuel | OUI |

**La solution retenue** combine les deux derniers : auto-detection du type de couche active + bouton toggle en fallback.

```
Quand l'utilisateur selectionne une couche dans le panneau Layers QGIS :
  - Si QgsVectorLayer  -->  stackedWidget.setCurrentIndex(0)  [Panel Vector]
  - Si QgsRasterLayer  -->  stackedWidget.setCurrentIndex(1)  [Panel Raster]
  - Si autre (mesh, point cloud, ...)  -->  rester sur le panel actuel

Fallback : un bouton toggle dans frame_header permet le basculement manuel.
```

### 2.2 Structure Widget Proposee

```
frame_exploring (QFrame) -- INCHANGE dans la structure .ui
|
+-- verticalLayout_main_content
    |
    +-- frame_header (QFrame) -- MODIFIE : ajout du toggle V/R
    |   +-- [logo] [titre] [toggle_vector_raster] [boutons action]
    |
    +-- scrollArea_frame_exploring (QScrollArea) -- INCHANGE
        |
        +-- stacked_exploring (QStackedWidget) -- NOUVEAU
            |
            +-- page_vector (QWidget) -- index 0
            |   +-- widget_exploring_keys (existant, deplace)
            |   +-- verticalLayout_exploring_tabs_content (existant, deplace)
            |       +-- mGroupBox_exploring_single_selection
            |       +-- mGroupBox_exploring_multiple_selection
            |       +-- mGroupBox_exploring_custom_selection
            |
            +-- page_raster (QWidget) -- index 1, NOUVEAU
                +-- widget_raster_exploring_keys (NOUVEAU)
                +-- verticalLayout_raster_exploring_content (NOUVEAU)
                    +-- mGroupBox_raster_layer_info
                    +-- mGroupBox_raster_value_sampling
                    +-- mGroupBox_raster_histogram
                    +-- mGroupBox_raster_zonal_stats
                    +-- mGroupBox_raster_object_detection
                    +-- mGroupBox_raster_band_viewer
```

### 2.3 Le Toggle Vector/Raster

Le toggle s'implemente comme un segment control avec deux QPushButton dans un QButtonGroup (exclusive=True) :

```
+-------------------+
| [V] Vector | [R] Raster |
+-------------------+
```

Plus elegant et lisible qu'un simple QToolButton checkable. Stylise pour ressembler a un segment control iOS/macOS.

```python
# ui/widgets/dual_mode_toggle.py
class DualModeToggle(QWidget):
    """Segment control for Vector/Raster mode switching."""

    modeChanged = pyqtSignal(int)  # 0=vector, 1=raster

    def __init__(self, parent=None):
        super().__init__(parent)
        self._btn_vector = QPushButton("V")
        self._btn_raster = QPushButton("R")
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        self._btn_group.addButton(self._btn_vector, 0)
        self._btn_group.addButton(self._btn_raster, 1)
        self._btn_vector.setCheckable(True)
        self._btn_raster.setCheckable(True)
        self._btn_vector.setChecked(True)  # Default: vector
        self._btn_group.idClicked.connect(self.modeChanged.emit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._btn_vector)
        layout.addWidget(self._btn_raster)
```

Auto-detection sur changement de couche active :

```python
# Dans filter_mate_dockwidget.py
iface.layerTreeView().currentLayerChanged.connect(self._on_active_layer_changed)

def _on_active_layer_changed(self, layer):
    from qgis.core import QgsRasterLayer, QgsVectorLayer
    if isinstance(layer, QgsVectorLayer):
        self.dual_mode_toggle.setMode(0)  # Vector
    elif isinstance(layer, QgsRasterLayer):
        self.dual_mode_toggle.setMode(1)  # Raster
```

---

## 3. Panel Raster Exploring -- Conception Detaillee

### 3.1 GroupBox 1 : Informations Couche Raster (`mGroupBox_raster_layer_info`)

**Objectif** : Vue d'ensemble rapide de la couche raster active. L'equivalent du "panneau Proprietes" mais condense et contextuellement pertinent.

**Contenu** :

```
+---[LAYER INFO]-------------------------------------+
| Nom:      MNT_IGN_75m.tif                          |
| Format:   GeoTIFF (COG: Oui)                       |
| Taille:   4096 x 4096 px  |  Pixel: 75m x 75m     |
| Bandes:   1 (Float32)     |  NoData: -9999.0       |
| CRS:      EPSG:2154 (RGF93 / Lambert-93)           |
| Emprise:  [xmin, ymin, xmax, ymax]                  |
| Provider: gdal                                      |
+----------------------------------------------------+
```

**Widgets** :
- 7 `QLabel` en lecture seule, rafraichis a chaque changement de couche
- Un bouton "Copier l'emprise" (vers presse-papiers en WKT)
- Un bouton "Zoom sur l'emprise" (utilise `iface.mapCanvas().setExtent()`)

**Use case** : L'urbaniste charge un MNT et veut immediatement savoir la resolution, le CRS, le nombre de bandes. Aujourd'hui il faut ouvrir Proprietes > Information. Avec FilterMate c'est visible d'un coup d'oeil.

**Effort** : 0.5 jour -- Quick win absolu.

### 3.2 GroupBox 2 : Echantillonnage de Valeurs Raster (`mGroupBox_raster_value_sampling`)

**Objectif** : C'est le coeur du P1-bis (Raster Value Sampling). Echantillonner les valeurs raster aux emplacements de features vectorielles, puis filtrer sur ces valeurs.

**Contenu** :

```
+---[VALUE SAMPLING]----------------------------------+
|                                                      |
| Couche raster :  [QgsMapLayerComboBox - raster only] |
| Bande :          [QComboBox - Band 1, Band 2, ...]   |
| Couche vecteur : [QgsMapLayerComboBox - vector only] |
| Methode :        [QComboBox]                         |
|                  ( ) Centroide                        |
|                  ( ) Point sur surface               |
|                  ( ) Moyenne sous polygone            |
|                                                      |
| --- Filtre sur valeur echantillonnee ---             |
| Operateur : [>=]  Valeur : [____500.0____]           |
|                                                      |
| [Echantillonner]  [Appliquer le filtre]              |
|                                                      |
| Resultat : 342/1204 entites retenues                 |
+-----------------------------------------------------+
```

**Widgets** :
- `QgsMapLayerComboBox` (filtre `RasterLayer`) pour la couche raster
- `QComboBox` pour le choix de bande (peuple dynamiquement selon le raster)
- `QgsMapLayerComboBox` (filtre `VectorLayer`) pour la couche vecteur cible
- `QComboBox` pour la methode de sampling : Centroid / PointOnSurface / MeanUnderPolygon
- `QComboBox` pour l'operateur : `=`, `!=`, `>`, `>=`, `<`, `<=`, `BETWEEN`
- `QDoubleSpinBox` pour la valeur seuil (ou deux pour BETWEEN)
- `QPushButton` "Echantillonner" : lance le calcul async
- `QPushButton` "Appliquer le filtre" : filtre la couche vecteur
- `QLabel` pour le resultat (entites retenues / total)
- `QProgressBar` pendant le calcul

**Backend technique** :

```python
# infrastructure/raster/sampling.py
from qgis.core import QgsRasterLayer, QgsPointXY

def sample_raster_at_point(
    raster: QgsRasterLayer,
    point: QgsPointXY,
    band: int = 1
) -> Optional[float]:
    """Sample raster value at a point. Thread-safe via URI recreation."""
    val, ok = raster.dataProvider().sample(point, band)
    return val if ok else None

def sample_raster_for_features(
    raster_uri: str,
    vector_uri: str,
    band: int = 1,
    method: str = 'point_on_surface'  # 'centroid' | 'point_on_surface' | 'mean'
) -> Dict[int, Optional[float]]:
    """
    Sample raster values for all features of a vector layer.

    IMPORTANT: Recreate layers from URI for thread safety.
    Uses pointOnSurface() and NOT centroid() for concave polygons.
    Reprojects vector geometries to raster CRS before sampling.
    """
    ...
```

**Use cases concrets** :
- Urbaniste : "Montrer les batiments au-dessus de 500m d'altitude" (MNT + bati BD TOPO)
- Ecologue : "Selectionner les parcelles avec NDVI > 0.6" (Sentinel-2 NDVI + RPG)
- Geologue : "Filtrer les affleurements sur pente > 30 degres" (MNT derive + carte geol)

**Effort** : 3-5 jours (P1-bis). C'est LE quick win qui justifie le dual panel.

### 3.3 GroupBox 3 : Histogramme (`mGroupBox_raster_histogram`)

**Objectif** : Visualisation interactive de la distribution des valeurs raster avec selection de plage directement sur l'histogramme. C'est le bridge entre exploration et filtrage -- l'utilisateur *voit* les donnees avant de filtrer.

**Contenu** :

```
+---[HISTOGRAM]---------------------------------------+
|                                                      |
| Bande : [Band 1 - Elevation v]  Bins: [256 v]       |
|                                                      |
| 800|                                                 |
| 600|        #####                                    |
| 400|      #########                                  |
| 200|    #############  ##                             |
|   0|__################_####_________________________  |
|    0    200    400    600    800    1000              |
|         [=====SELECTION=====]                        |
|    Min: [__350__]  Max: [__750__]                    |
|                                                      |
| Stats: min=12.3 | max=987.6 | mean=456.2 | std=123  |
|        median=441.0 | mode=420-430                   |
|                                                      |
| [Appliquer comme filtre vecteur]                     |
+-----------------------------------------------------+
```

**Widgets** :
- `QComboBox` pour le choix de bande
- `QComboBox` pour le nombre de bins (64, 128, 256, 512)
- Widget histogramme custom (`RasterHistogramWidget`) base sur :
  - **Option A** : `matplotlib` embed dans un `FigureCanvasQTAgg` (rapide a implementer, lourd en dependance)
  - **Option B** : `QCustomPlot` ou `pyqtgraph` (plus leger, interactif natif)
  - **Option C recommandee** : QPainter custom widget (zero dependance, 100% controle, ~300 lignes)
- `QgsRangeSlider` (widget QGIS natif depuis 3.18) pour la selection de plage
- 2x `QDoubleSpinBox` pour min/max (lies au range slider)
- `QLabel` multiligne pour les statistiques
- `QPushButton` "Appliquer comme filtre vecteur"

**Fonctionnement interactif** :

```
L'utilisateur drag le range slider sur l'histogramme
  --> Debounce 300ms
  --> Echantillonnage rapide des features visibles (via le sampling du 3.2)
  --> Highlight en temps reel sur le canvas (layer.selectByIds())
  --> Feedback : "234 entites dans la plage [350, 750]"
```

C'est le P2 (Raster-Driven Highlight) combine avec l'histogramme. Le pouvoir de cette interaction, c'est que l'utilisateur *decouvre* ses donnees en temps reel -- comme un equalizer audio ou vous entendez le changement en direct.

**Calcul des statistiques** :

```python
# infrastructure/raster/histogram.py
from qgis.core import QgsRasterLayer, QgsRasterBandStats
import numpy as np

def compute_band_histogram(
    raster_uri: str,
    band: int = 1,
    n_bins: int = 256,
    extent: Optional[QgsRectangle] = None
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Compute histogram for a raster band.

    If extent is provided, only computes within that extent
    (useful for "histogram of visible extent" mode).

    Returns (counts, bin_edges).
    """
    ...

def compute_band_statistics(
    raster_uri: str,
    band: int = 1
) -> Dict[str, float]:
    """Compute min, max, mean, std, median for a band."""
    provider = QgsRasterLayer(raster_uri, "temp").dataProvider()
    stats = provider.bandStatistics(band, QgsRasterBandStats.All)
    return {
        'min': stats.minimumValue,
        'max': stats.maximumValue,
        'mean': stats.mean,
        'std_dev': stats.stdDev,
        'range': stats.range
    }
```

**Use cases** :
- Teledetecteur : Explorer la distribution d'un NDVI Sentinel-2 avant de poser un seuil
- Hydrologue : Visualiser la repartition altimetrique d'un bassin versant
- Climatologue : Identifier des anomalies dans une grille de temperatures

**Effort** : 1-2 semaines (histogramme basique 3j, interactivite 3j, range slider 2j).

### 3.4 GroupBox 4 : Statistiques Zonales (`mGroupBox_raster_zonal_stats`)

**Objectif** : C'est LE differenciateur majeur (P1). Filtrer des entites vectorielles par les statistiques raster calculees sous leur emprise geometrique. "Montre-moi les communes ou l'altitude moyenne depasse 800m" -- en 3 clics.

**Contenu** :

```
+---[ZONAL STATISTICS]--------------------------------+
|                                                      |
| Couche raster :  [QgsMapLayerComboBox - raster]      |
| Bande :          [Band 1 v]                          |
| Couche vecteur : [QgsMapLayerComboBox - vector poly] |
|                                                      |
| Statistiques a calculer :                            |
| [x] Moyenne  [x] Min  [x] Max  [ ] Ecart-type       |
| [ ] Mediane  [ ] Comptage  [ ] Somme  [ ] Majorite   |
|                                                      |
| --- Critere de filtre ---                            |
| Stat:  [Moyenne v]                                   |
| Oper:  [>= v]     Valeur: [____800.0____]           |
|                                                      |
| [ ] Ajouter les stats comme attributs temporaires    |
|                                                      |
| [Calculer]  [Filtrer]  [Exporter les stats]          |
|                                                      |
| Resultat : 87/342 communes retenues                  |
| Temps : 2.3s pour 342 polygones                      |
+-----------------------------------------------------+
```

**Widgets** :
- 2x `QgsMapLayerComboBox` (raster + vecteur polygone)
- `QComboBox` bande
- 8x `QCheckBox` pour les statistiques souhaitees
- `QComboBox` pour la stat de filtre
- `QComboBox` operateur + `QDoubleSpinBox` valeur
- `QCheckBox` "Ajouter comme attributs" (ecrit les stats dans des colonnes temporaires)
- 3x `QPushButton` : Calculer / Filtrer / Exporter
- `QLabel` resultat + temps
- `QProgressBar` (calcul potentiellement long)

**Backend technique** :

```python
# infrastructure/raster/zonal_stats.py
from qgis.analysis import QgsZonalStatistics

def compute_zonal_stats(
    raster_uri: str,
    vector_uri: str,
    band: int = 1,
    stats: List[str] = ['mean', 'min', 'max'],
    prefix: str = 'fm_zs_'
) -> Dict[int, Dict[str, float]]:
    """
    Compute zonal statistics for vector features over a raster.

    CRITICAL: QgsZonalStatistics writes in-place.
    Strategy: Clone to memory layer -> compute -> extract -> discard.

    Returns: {feature_id: {'mean': 456.2, 'min': 12.3, 'max': 987.6}}
    """
    # 1. Clone vector layer to memory
    mem_layer = vector_layer.materialize(QgsFeatureRequest())

    # 2. Run QgsZonalStatistics on the clone
    zs = QgsZonalStatistics(
        mem_layer, raster_layer,
        prefix, band,
        QgsZonalStatistics.Mean | QgsZonalStatistics.Min | QgsZonalStatistics.Max
    )
    zs.calculateStatistics(None)

    # 3. Extract results from memory layer attributes
    results = {}
    for feature in mem_layer.getFeatures():
        fid = feature.id()
        results[fid] = {
            'mean': feature[f'{prefix}mean'],
            'min': feature[f'{prefix}min'],
            'max': feature[f'{prefix}max']
        }

    # 4. Memory layer is discarded (GC)
    return results
```

**ATTENTION -- Piege connu** : `QgsZonalStatistics` ecrit les colonnes en dur dans la couche vectorielle source. Il faut TOUJOURS travailler sur une copie memoire. C'est le piege #5 de la liste des pitfalls Atlas.

**Use cases critiques** :
- Urbaniste : "Communes ou l'altitude moyenne > 800m" (MNT + Admin Express)
- Ecologue : "Parcelles ou le NDVI moyen < 0.3 (sols nus)" (Sentinel-2 + RPG)
- Risques : "Batiments ou la pente max > 45 degres (glissement)" (MNT derive + bati)
- Forestier : "Peuplements ou la hauteur canopee mediane > 15m" (MNH LiDAR + placettes)

**Effort** : 2-3 semaines. C'est le gros morceau mais c'est LE feature qui n'existe nulle part ailleurs en QGIS.

### 3.5 GroupBox 5 : Detection d'Objets (`mGroupBox_raster_object_detection`)

**Objectif** : Identification semi-automatique d'objets dans l'imagerie raster. C'est le panel le plus ambitieux -- mais avec la bonne architecture, il peut commencer simple et grandir.

**Architecture en 3 niveaux de complexite** :

#### Niveau 1 -- Template Matching (Quick Win, 1 semaine)

Correlation de motifs basee sur OpenCV (via `cv2` ou GDAL). L'utilisateur dessine un rectangle sur le canvas autour d'un objet type, et le systeme cherche les occurrences similaires.

```
+---[OBJECT DETECTION]--(collapsed by default)---------+
|                                                       |
| Mode : [Template Matching v]                          |
|                                                       |
| Template :  [Capturer depuis le canvas]               |
|             Taille : 32x32 px | Apercu : [thumb]      |
|                                                       |
| Seuil de similarite : [====O=====] 0.75               |
| Methode :  [Correlation normalisee v]                 |
|                                                       |
| [Detecter]                                            |
|                                                       |
| Resultats : 23 occurrences trouvees                   |
| [Creer couche points]  [Exporter en GeoJSON]          |
+------------------------------------------------------+
```

**Implementation** :

```python
# infrastructure/raster/detection/template_matching.py
import numpy as np

def template_match(
    raster_array: np.ndarray,
    template_array: np.ndarray,
    method: str = 'cv2.TM_CCOEFF_NORMED',
    threshold: float = 0.8
) -> List[Tuple[int, int, float]]:
    """
    Template matching on a raster band.

    Si OpenCV est disponible : cv2.matchTemplate() (rapide, GPU possible)
    Sinon : scipy.signal.correlate2d() (fallback pur Python/NumPy)

    Returns: List of (x, y, score) for matches above threshold.
    """
    try:
        import cv2
        result = cv2.matchTemplate(
            raster_array, template_array, cv2.TM_CCOEFF_NORMED
        )
        locations = np.where(result >= threshold)
        return [(int(x), int(y), float(result[y, x]))
                for y, x in zip(*locations)]
    except ImportError:
        from scipy.signal import correlate2d
        ...
```

#### Niveau 2 -- Segmentation SAM (Medium, 2-3 semaines)

Integration de Segment Anything Model (Meta) via le package `segment-anything` ou mieux, `samgeo` (SAM pour geospatial). L'utilisateur clique sur le canvas pour poser des points/boites prompt, SAM segmente.

```
| Mode : [SAM Segmentation v]                          |
|                                                       |
| Modele :  [sam_vit_b v]  (308 MB)                    |
| [ ] Utiliser GPU  [ ] Mode automatique                |
|                                                       |
| Prompts : 3 points positifs, 1 negatif               |
| [Ajouter point +]  [Ajouter point -]  [Reset]        |
|                                                       |
| [Segmenter]                                           |
|                                                       |
| Segments trouves : 47                                 |
| [Vectoriser les segments]  [Filtrer par surface]      |
```

**Dependances** :
- `segment-anything` (Meta) ou `samgeo` (wrapper geospatial)
- `torch` (lourd mais souvent deja present via d'autres plugins)
- GPU recommande mais pas obligatoire (CPU OK pour petites zones)

#### Niveau 3 -- YOLO Geospatial (Long terme, 4+ semaines)

Detection d'objets supervises avec YOLOv8/v11 entraines sur des donnees geospatiales.

```
| Mode : [YOLO Detection v]                            |
|                                                       |
| Modele : [buildings_sentinel2_v1.pt v]               |
|          [Charger modele personnalise...]              |
| Confiance min : [====O=====] 0.5                      |
| Classes :  [x] Batiment  [x] Route  [ ] Vegetation   |
|                                                       |
| [Detecter sur l'emprise visible]                      |
```

**IMPORTANT -- Principe Atlas** : On ne livre PAS les modeles avec le plugin. On fournit une interface pour charger des modeles ONNX/PyTorch, et on documente comment les obtenir. Le plugin reste leger (<10MB) et l'utilisateur charge les modeles selon ses besoins.

**Use cases** :
- Template : Compter les arbres isoles sur une orthophoto (template d'un arbre type)
- SAM : Segmenter des batiments sur une image satellite pour creer un shapefile
- YOLO : Detecter les panneaux solaires sur une ortho IGN, les piscines, les toitures

**Effort total** : Niveau 1 = 1 semaine, Niveau 2 = 2-3 semaines, Niveau 3 = 4+ semaines.

### 3.6 GroupBox 6 : Visualiseur de Bandes (`mGroupBox_raster_band_viewer`)

**Objectif** : Navigation et visualisation rapide des bandes d'un raster multi-bandes. Indispensable pour le Sentinel-2 (13 bandes), Landsat (11 bandes), ou les orthophotos RGBN.

```
+---[BAND VIEWER]-------------------------------------+
|                                                      |
| Bandes disponibles :                                 |
| +----+--------+---------+--------+---------+         |
| | #  | Nom    | Type    | Min    | Max     |         |
| +----+--------+---------+--------+---------+         |
| | 1  | Red    | Float32 | 0.0    | 10000.0 |         |
| | 2  | Green  | Float32 | 0.0    | 10000.0 |         |
| | 3  | Blue   | Float32 | 0.0    | 10000.0 |         |
| | 4  | NIR    | Float32 | 0.0    | 12000.0 |         |
| +----+--------+---------+--------+---------+         |
|                                                      |
| Composition rapide :                                 |
| [Couleur naturelle] [Fausse couleur IRC]             |
| [NDVI] [NDWI] [Personnalise...]                      |
|                                                      |
| Bande R: [4-NIR v]  G: [3-Red v]  B: [2-Green v]    |
| [Appliquer]                                          |
|                                                      |
| --- Index spectral ---                               |
| Formule : (B4-B3)/(B4+B3)                           |
| [Calculer et afficher]                               |
+-----------------------------------------------------+
```

**Widgets** :
- `QTableWidget` listant les bandes (readonly)
- Boutons predefinis pour les compositions courantes (QPushButton flat)
- 3x `QComboBox` pour R/G/B band assignment
- `QLineEdit` pour formule d'index spectral personnalise
- `QPushButton` Appliquer / Calculer

**Implementation** : Change uniquement le rendering du raster via `QgsRasterRenderer` :

```python
renderer = QgsMultiBandColorRenderer(
    provider, redBand=4, greenBand=1, blueBand=2
)
raster_layer.setRenderer(renderer)
raster_layer.triggerRepaint()
```

**Use cases** :
- Teledetecteur : Basculer rapidement entre compositions pour identifier les cultures
- Ecologue : Calculer un NDVI rapide pour reperer le stress hydrique
- Geologue : Composer les bandes SWIR pour la mineralogie

**Effort** : 1 semaine.

### 3.7 Recapitulatif des GroupBoxes Raster Exploring

| # | GroupBox | Contenu Principal | Effort | Priorite |
|---|---------|-------------------|--------|----------|
| 1 | Layer Info | Metadonnees resume | 0.5j | P0 (trivial) |
| 2 | Value Sampling | Echantillonnage + filtre | 3-5j | P1-bis |
| 3 | Histogram | Histogramme interactif + range | 1-2w | P2 |
| 4 | Zonal Stats | Stats zonales + filtre | 2-3w | P1 |
| 5 | Object Detection | Template / SAM / YOLO | 1w-1m | P3 |
| 6 | Band Viewer | Composition bandes + index | 1w | P2-bis |

---

## 4. Panel Vector Exploring -- Evolution

### 4.1 Ce qui reste INCHANGE

Toute la logique vectorielle existante est preservee telle quelle :

- `mGroupBox_exploring_single_selection` : Selection unitaire avec `QgsFeaturePickerWidget`
- `mGroupBox_exploring_multiple_selection` : Selection multiple avec `QgsCheckableComboBoxFeaturesListPickerWidget`
- `mGroupBox_exploring_custom_selection` : Selection par expression
- Les boutons lateraux : Identify, Zoom, Selecting, Tracking, Linking, Reset
- Le `ExploringController` existant dans `ui/controllers/exploring_controller.py`

Le panel vectoriel n'a PAS besoin de modifications fonctionnelles pour la Phase 1 du dual mode.

### 4.2 Ajout Optionnel : Info Couche Vectorielle

Par symetrie avec le raster, on pourrait ajouter un `mGroupBox_vector_layer_info` collapse par defaut :

```
+---[LAYER INFO]-------(collapsed)--------------------+
| Nom:     bati_indifferencie_75.gpkg                  |
| Format:  GeoPackage (Spatialite backend)             |
| Entites: 45,231 | Geometrie: MultiPolygon            |
| CRS:     EPSG:2154 | Champs: 23                     |
| Backend: spatialite (auto-detecte)                   |
+-----------------------------------------------------+
```

**Effort** : 0.5 jour. Nice-to-have, pas bloquant.

### 4.3 Ajout Futur : Lien Raster-Vecteur dans le Panel Vecteur

Un bouton "Enrichir avec valeurs raster" dans le panel vectoriel qui ouvre directement le GroupBox Value Sampling du panel raster. Cross-navigation entre les deux modes.

---

## 5. Extension aux Autres Panels

### 5.1 Principe General

Le dual Vector/Raster s'applique a chaque page du QToolBox (`toolBox_tabTools`). La structure est la meme : un `QStackedWidget` a l'interieur de chaque page, avec basculement synchronise par le toggle global.

```
Quand l'utilisateur toggle V/R dans frame_header :
  --> stacked_exploring.setCurrentIndex(idx)
  --> stacked_filtering.setCurrentIndex(idx)
  --> stacked_exporting.setCurrentIndex(idx)
  --> stacked_configuration.setCurrentIndex(idx)
```

Un seul toggle controle TOUS les panels. Coherence absolue.

### 5.2 FILTERING -- Dual Mode

#### Page Vector (existante)

Inchangee : predicats geometriques, operateurs de combinaison, selection de couches, buffer dynamique. Tout le systeme multi-backend reste 100% vectoriel.

#### Page Raster (NOUVELLE)

```
+---[RASTER FILTERING]--------------------------------+
|                                                      |
| --- Filtre par valeur de bande ---                   |
| Bande : [Band 1 v]                                  |
| Condition : [>= v]  Valeur : [____500____]          |
|                                                      |
| --- Filtre par statistique zonale ---                |
| (Raccourci vers Zonal Stats du panel Exploring)      |
|                                                      |
| --- Masque raster ---                                |
| [ ] Creer masque binaire depuis le filtre            |
| [ ] Appliquer NoData hors selection                  |
|                                                      |
| --- Combinaison multi-bandes ---                     |
| Bande 1 : [>= 500]  AND                             |
| Bande 4 : [<= 2000] AND                             |
| Index (B4-B1)/(B4+B1) : [>= 0.3]                    |
|                                                      |
| [Appliquer]  [Reinitialiser]                         |
+-----------------------------------------------------+
```

### 5.3 EXPORTING -- Dual Mode

#### Page Vector (existante)

Inchangee : export multi-format, preservation de styles, batch export.

#### Page Raster (NOUVELLE)

```
+---[RASTER EXPORT]-----------------------------------+
|                                                      |
| Source : [QgsMapLayerComboBox - raster]               |
|                                                      |
| --- Decoupage ---                                    |
| [ ] Decouper par l'emprise de la carte               |
| [ ] Decouper par couche vecteur : [combobox]         |
| [ ] Decouper par selection vecteur active             |
|                                                      |
| --- Format de sortie ---                             |
| Format : [GeoTIFF v] [Cloud-Optimized (COG) v]      |
| Compression : [DEFLATE v]                            |
| Resolution : [Garder l'originale v]                  |
| CRS cible : [QgsProjectionSelectionWidget]           |
|                                                      |
| --- Options avancees ---                             |
| [ ] Exporter uniquement les bandes selectionnees     |
|     Bandes : [x]1 [x]2 [x]3 [ ]4                    |
| [ ] Appliquer le masque de filtre actif              |
| [ ] Ajouter overview pyramids                        |
|                                                      |
| Dossier : [____/home/user/exports____] [Parcourir]   |
| Nom :     [____export_20260210____]                  |
|                                                      |
| [Exporter]                                           |
+-----------------------------------------------------+
```

**Points forts** :
- Export COG (Cloud-Optimized GeoTIFF) -- positionne FilterMate sur le cloud-native
- Clip par vecteur -- le P3 du plan Atlas, directement dans l'UI d'export
- Export selectif de bandes -- utile pour extraire le NIR d'un Sentinel-2
- Application du masque de filtre -- chainage filter->export seamless

**Backend** :

```python
# infrastructure/raster/export.py
from osgeo import gdal

def export_raster(
    input_uri: str,
    output_path: str,
    format: str = 'GTiff',
    creation_options: List[str] = None,
    cutline_uri: str = None,
    target_crs: str = None,
    bands: List[int] = None
) -> str:
    """
    Export raster with optional clip, reproject, band selection.

    Pour COG : creation_options = [
        'COMPRESS=DEFLATE', 'TILED=YES', 'COPY_SRC_OVERVIEWS=YES'
    ]

    Uses gdal.Warp() pour le clip + reproject en un seul pass.
    """
    warp_options = gdal.WarpOptions(
        format=format,
        cutlineDSName=cutline_uri,
        cropToCutline=True if cutline_uri else False,
        dstSRS=target_crs,
        creationOptions=creation_options or []
    )
    gdal.Warp(output_path, input_uri, options=warp_options)
    return output_path
```

### 5.4 CONFIGURATION -- Pas de Dual Mode Necessaire

Ajouter une section `"RASTER"` dans le `config.json` existant :

```json
{
  "RASTER": {
    "DEFAULT_SAMPLING_METHOD": {
      "value": "point_on_surface",
      "choices": ["centroid", "point_on_surface", "mean"],
      "description": "Methode par defaut pour l'echantillonnage raster"
    },
    "HISTOGRAM_BINS": {
      "value": 256,
      "description": "Nombre de bins par defaut pour les histogrammes"
    },
    "ZONAL_STATS_PREFIX": {
      "value": "fm_zs_",
      "description": "Prefixe pour les colonnes de statistiques zonales"
    },
    "DETECTION_ENABLED": {
      "value": false,
      "description": "Activer le panel de detection d'objets (experimental)"
    },
    "COG_DEFAULT_COMPRESSION": {
      "value": "DEFLATE",
      "choices": ["DEFLATE", "LZW", "ZSTD", "NONE"],
      "description": "Compression par defaut pour l'export COG"
    },
    "MAX_RASTER_SIZE_MB": {
      "value": 2048,
      "description": "Taille max raster avant avertissement (MB)"
    },
    "DEBOUNCE_MS": {
      "value": 300,
      "description": "Delai de debounce pour le highlight temps reel (ms)"
    }
  }
}
```

Le systeme `ChoicesType`/`ConfigValueType` du JSON tree view existant gere deja ces cas. Pas besoin de dual mode pour la configuration.

---

## 6. Wireframes Textuels

### 6.1 Vue d'Ensemble du Dockwidget avec Dual Mode

```
+================================================================+
|  FilterMate                                               [_][x] |
+================================================================+
| [logo]  FilterMate v5.5       [V] Vector | [R] Raster  [?][S]  |
+-----+----------------------------------------------------------+
|     |  EXPLORING                                                |
|     +----------------------------------------------------------+
|     |                                                           |
| [I] |  <<< Si mode VECTOR (page 0 du stacked) >>>              |
| [Z] |  +---[SINGLE SELECTION]-----(collapsible)---+            |
| [S] |  | Feature: [QgsFeaturePickerWidget        ] |            |
| [T] |  | Field:   [QgsFieldExpressionWidget      ] |            |
| [L] |  +------------------------------------------+            |
| [R] |  +---[MULTIPLE SELECTION]---(collapsible)---+            |
|     |  | Features: [QgsCheckableComboBox          ] |            |
|     |  | Field:    [QgsFieldExpressionWidget      ] |            |
|     |  +------------------------------------------+            |
|     |  +---[CUSTOM SELECTION]------(collapsible)---+            |
|     |  | Expression: [                            ] |            |
|     |  +------------------------------------------+            |
|     |                                                           |
|     |  <<< Si mode RASTER (page 1 du stacked) >>>              |
| [P] |  +---[LAYER INFO]-----------(collapsible)---+            |
| [H] |  | MNT_IGN_75m.tif | 4096x4096 | 1 bande   |            |
| [Z] |  +------------------------------------------+            |
| [D] |  +---[VALUE SAMPLING]--------(collapsible)---+            |
| [B] |  | Raster: [______] Band: [1]                |            |
|     |  | Vector: [______] Method: [PointOnSurface] |            |
|     |  | Filter: [>=] [500.0]    [Sample] [Apply]  |            |
|     |  +------------------------------------------+            |
|     |  +---[HISTOGRAM]-------------(collapsible)---+            |
|     |  | Band: [1]  Bins: [256]                    |            |
|     |  |    ####                                   |            |
|     |  |   ######  ##                              |            |
|     |  |  #########_###___                         |            |
|     |  | [==RANGE SLIDER==]                        |            |
|     |  | Min: [350] Max: [750]                     |            |
|     |  | Stats: mean=456 std=123                   |            |
|     |  +------------------------------------------+            |
|     |  +---[ZONAL STATS]-----------(collapsed)-----+            |
|     |  +---[OBJECT DETECTION]------(collapsed)-----+            |
|     |  +---[BAND VIEWER]-----------(collapsed)-----+            |
|     |                                                           |
+=====+===========================================================+
|     FILTERING  |  EXPORTING  |  CONFIGURATION                   |
+=================+============+==================================+
|                                                                  |
|  <<< Contenu Filtering/Exporting/Config                          |
|      avec leur propre dual V/R interne >>>                       |
|                                                                  |
+==================================================================+
```

### 6.2 Boutons Lateraux Raster (widget_raster_exploring_keys)

```
+------+
| [P]  |  Pixel Picker (clic sur canvas pour echantillonner)
|------|
| [H]  |  Histogram (toggle visibilite du groupbox)
|------|
| [Z]  |  Zonal Stats (toggle visibilite du groupbox)
|------|
| [D]  |  Detection (toggle visibilite du groupbox)
|------|
| [B]  |  Band Viewer (toggle visibilite du groupbox)
|------|
|      |
| [R]  |  Reset (reinitialiser tous les filtres raster)
+------+
```

Memes dimensions que les boutons vectoriels existants (32x32 en NORMAL, 24x24 en COMPACT).

### 6.3 Wireframe Panel Filtering Raster

```
+=================================================================+
|  FILTERING (mode Raster)                                         |
+=================================================================+
| +---[BAND VALUE FILTER]-----------------------------------+      |
| | Band: [1-Elevation v]                                   |      |
| | [>=] [500.0]  AND  [<=] [1500.0]                        |      |
| |                                                         |      |
| | [+ Ajouter critere de bande]                            |      |
| +---------------------------------------------------------+      |
|                                                                   |
| +---[SPATIAL MASK]--------------------------------------------+   |
| | [ ] Masque par vecteur actif                                |   |
| | [ ] Masque par emprise visible                              |   |
| | [ ] Masque personnalise (dessiner sur canvas)               |   |
| +-------------------------------------------------------------+   |
|                                                                   |
| +---[INDEX FILTER]--------------------------------------------+   |
| | Formule : [(B4-B3)/(B4+B3)               ]                 |   |
| | Condition : [>=] [0.3]                                      |   |
| | Presets : [NDVI] [NDWI] [NDBI] [Custom]                    |   |
| +-------------------------------------------------------------+   |
|                                                                   |
| [Appliquer]  [Reinitialiser]  [Undo] [Redo]                      |
+=================================================================+
```

### 6.4 Wireframe Panel Exporting Raster

```
+=================================================================+
|  EXPORTING (mode Raster)                                         |
+=================================================================+
| Source : [MNT_IGN_75m.tif v]                                     |
|                                                                   |
| +---[CLIP]------------------------------------------------+      |
| | ( ) Emprise complete                                     |      |
| | ( ) Emprise de la carte                                  |      |
| | ( ) Par couche vecteur : [communes_75 v]                 |      |
| | ( ) Par selection vecteur active                         |      |
| +----------------------------------------------------------+      |
|                                                                   |
| +---[FORMAT]-----------------------------------------------+      |
| | Format :      [GeoTIFF v]                                |      |
| | Profil :      [Cloud-Optimized (COG) v]                  |      |
| | Compression : [DEFLATE v]                                |      |
| | CRS :         [EPSG:2154 v]                              |      |
| | Bandes :      [x]1 [x]2 [x]3 [ ]4                       |      |
| +----------------------------------------------------------+      |
|                                                                   |
| Sortie : [/home/user/exports/export.tif] [...]                    |
|                                                                   |
| [Exporter]                                   Taille estim.: 45MB  |
+=================================================================+
```

---

## 7. Integration Technique dans l'Architecture Hexagonale

### 7.1 Nouveaux Fichiers a Creer

```
filter_mate/
|
+-- core/
|   +-- domain/
|   |   +-- raster_filter_criteria.py      # Frozen dataclasses pour les criteres
|   |   +-- raster_stats_result.py         # ResultSet pour les stats zonales
|   |
|   +-- services/
|   |   +-- raster_filter_service.py       # Service principal d'orchestration
|   |   +-- raster_sampling_service.py     # Sampling centroid/polygon
|   |   +-- raster_stats_service.py        # Zonal stats service
|   |
|   +-- tasks/
|       +-- raster_sampling_task.py        # QgsTask pour sampling async
|       +-- raster_stats_task.py           # QgsTask pour stats zonales async
|       +-- raster_export_task.py          # QgsTask pour export async
|
+-- infrastructure/
|   +-- raster/
|       +-- __init__.py
|       +-- sampling.py                    # provider.sample() wrapper
|       +-- zonal_stats.py                 # QgsZonalStatistics wrapper
|       +-- histogram.py                   # Calcul histogramme numpy/GDAL
|       +-- masking.py                     # Mask binaire, clip
|       +-- export.py                      # gdal.Warp export
|       +-- band_utils.py                  # Infos bandes, compositions
|       +-- detection/
|           +-- __init__.py
|           +-- template_matching.py       # OpenCV/scipy template match
|           +-- sam_integration.py         # SAM wrapper (optionnel)
|           +-- model_loader.py            # Chargement modeles ONNX/PT
|
+-- ui/
|   +-- controllers/
|   |   +-- raster_exploring_controller.py # pendant de exploring_controller.py
|   |   +-- raster_filtering_controller.py
|   |   +-- raster_exporting_controller.py
|   |
|   +-- widgets/
|   |   +-- raster_histogram_widget.py     # widget histogramme custom
|   |   +-- band_composition_widget.py     # widget composition bandes
|   |   +-- dual_mode_toggle.py            # toggle V/R
|   |
|   +-- tools/
|       +-- raster_pixel_picker_tool.py    # QgsMapTool pour clic canvas
|
+-- config/
    +-- raster_config.py                   # constantes raster
```

### 7.2 Modifications aux Fichiers Existants

| Fichier | Modification | Impact |
|---------|-------------|--------|
| `filter_mate_dockwidget_base.ui` | Ajout QStackedWidget dans frame_exploring, toggle dans header | MEDIUM |
| `filter_mate_dockwidget.py` | Init QStackedWidget, connexion toggle, auto-detect layer type | LOW |
| `ui/controllers/integration.py` | Enregistrer les 3 nouveaux controllers raster | LOW |
| `ui/controllers/registry.py` | Ajouter les nouvelles entrees | LOW |
| `filter_mate_app.py` | Enregistrer raster services dans le DI container | LOW |
| `adapters/app_bridge.py` | Exposer les raster services | LOW |
| `config/config.json` | Ajouter section "RASTER" | LOW |
| `infrastructure/constants.py` | Constantes raster | LOW |

**Principe cle** : Les modifications aux fichiers existants sont minimales (wiring/registration). Toute la logique raster vit dans des fichiers NOUVEAUX. On ne pollue pas le code vectoriel.

### 7.3 Pattern de Controller Raster

```python
# ui/controllers/raster_exploring_controller.py

class RasterExploringController(BaseController):
    """
    Controller for the Raster Exploring panel.

    Manages:
    - Layer info display
    - Raster value sampling
    - Histogram interaction
    - Zonal statistics
    - Band viewer
    """

    def __init__(self, dockwidget, raster_service=None, signal_manager=None):
        super().__init__(dockwidget, signal_manager=signal_manager)
        self._raster_service = raster_service
        self._current_raster_layer = None
        self._current_band = 1
        self._histogram_data = None

    def setup(self):
        """Connect signals to raster exploring widgets."""
        dw = self._dockwidget

        self._connect_signal(
            iface.layerTreeView(), 'currentLayerChanged',
            self._on_layer_changed
        )

        self._connect_signal(
            dw.btn_raster_sample, 'clicked',
            self._on_sample_clicked
        )

        self._connect_signal(
            dw.raster_range_slider, 'rangeChanged',
            self._on_range_changed
        )

    def _on_layer_changed(self, layer):
        """Update raster info when active layer changes."""
        from qgis.core import QgsRasterLayer
        if isinstance(layer, QgsRasterLayer):
            self._current_raster_layer = layer
            self._update_layer_info()
            self._update_band_list()
            self._compute_histogram()

    def _on_sample_clicked(self):
        """Launch async raster value sampling."""
        from qgis.core import QgsApplication
        task = RasterSamplingTask(
            raster_uri=self._current_raster_layer.source(),
            vector_uri=self._get_target_vector_layer().source(),
            band=self._current_band,
            method=self._get_sampling_method()
        )
        task.completed.connect(self._on_sampling_complete)
        QgsApplication.taskManager().addTask(task)
```

### 7.4 Diagramme de Flux de Donnees

```
[Couche Raster Active]
         |
         v
+---[RasterExploringController]---+
|                                  |
|  _on_layer_changed()             |
|    |                             |
|    +--> _update_layer_info()     |  --> GroupBox Layer Info
|    +--> _update_band_list()      |  --> GroupBox Band Viewer
|    +--> _compute_histogram()     |  --> GroupBox Histogram
|                                  |
|  _on_sample_clicked()            |
|    |                             |
|    +--> RasterSamplingTask       |  --> (async)
|          |                       |
|          v                       |
|    RasterSamplingService         |
|      |                           |
|      +--> sampling.py            |  --> infrastructure/raster/
|      |    (provider.sample())    |
|      |                           |
|      v                           |
|    _on_sampling_complete()       |  --> update UI, highlight features
|                                  |
|  _on_zonal_stats_clicked()       |
|    |                             |
|    +--> RasterStatsTask          |  --> (async)
|          |                       |
|          v                       |
|    RasterStatsService            |
|      |                           |
|      +--> zonal_stats.py         |  --> infrastructure/raster/
|      |    (QgsZonalStatistics)   |
|      |                           |
|      v                           |
|    _on_stats_complete()          |  --> filter vector, update UI
+----------------------------------+
```

### 7.5 Integration du DI Container

```python
# adapters/app_bridge.py -- ajouts

from core.services.raster_filter_service import RasterFilterService
from core.services.raster_sampling_service import RasterSamplingService
from core.services.raster_stats_service import RasterStatsService

_raster_filter_service = None
_raster_sampling_service = None
_raster_stats_service = None

def initialize_raster_services():
    """Initialize raster services (called from filter_mate_app.py)."""
    global _raster_filter_service, _raster_sampling_service, _raster_stats_service
    _raster_filter_service = RasterFilterService()
    _raster_sampling_service = RasterSamplingService()
    _raster_stats_service = RasterStatsService()

def get_raster_filter_service():
    return _raster_filter_service

def get_raster_sampling_service():
    return _raster_sampling_service

def get_raster_stats_service():
    return _raster_stats_service
```

---

## 8. Priorisation et Feuille de Route

### 8.1 Phase 0 -- Fondation du Dual Mode (1 semaine)

**Ce qu'on livre** : Le mecanisme de basculement V/R, sans aucune fonctionnalite raster.

| Tache | Effort | Fichiers |
|-------|--------|----------|
| Ajouter `QStackedWidget` dans `frame_exploring` | 0.5j | `.ui`, `dockwidget.py` |
| Creer le toggle V/R dans `frame_header` | 0.5j | `dual_mode_toggle.py`, `.ui` |
| Auto-detection du type de couche | 0.5j | `dockwidget.py` |
| Page raster vide avec placeholder | 0.5j | `.ui` |
| Creer `RasterExploringController` (skeleton) | 1j | `raster_exploring_controller.py` |
| Enregistrer dans `integration.py` | 0.5j | `integration.py`, `registry.py` |
| Creer `infrastructure/raster/__init__.py` | 0.5j | `raster/` package |

**Resultat** : Le dual mode fonctionne mecaniquement. Quand on selectionne un raster, le panel bascule sur un placeholder "Raster Exploring - Coming Soon". Le toggle fonctionne. La detection auto fonctionne. Zero regression sur le vectoriel.

### 8.2 Phase 1 -- Layer Info + Value Sampling (1 semaine)

**Ce qu'on livre** : Les deux premiers GroupBoxes fonctionnels.

| Tache | Effort | Fichiers |
|-------|--------|----------|
| `mGroupBox_raster_layer_info` | 0.5j | `.ui`, controller |
| `infrastructure/raster/sampling.py` | 1j | Nouveau |
| `core/services/raster_sampling_service.py` | 1j | Nouveau |
| `core/tasks/raster_sampling_task.py` (async) | 1j | Nouveau |
| `mGroupBox_raster_value_sampling` (UI) | 1j | `.ui`, controller |
| `core/domain/raster_filter_criteria.py` | 0.5j | Nouveau |
| Tests unitaires sampling | 1j | `tests/` |

**Resultat** : Un urbaniste peut charger un MNT et une couche batiment, echantillonner l'altitude sous chaque batiment, et filtrer "batiments > 500m d'altitude". En 4 clics.

### 8.3 Phase 2 -- Histogramme + Band Viewer (2 semaines)

| Tache | Effort | Fichiers |
|-------|--------|----------|
| `RasterHistogramWidget` (QPainter custom) | 3j | Nouveau |
| `infrastructure/raster/histogram.py` | 1j | Nouveau |
| Integration QgsRangeSlider | 1j | Widget, controller |
| Debounce + highlight temps reel | 2j | Controller, service |
| `mGroupBox_raster_band_viewer` | 2j | `.ui`, controller |
| `infrastructure/raster/band_utils.py` | 1j | Nouveau |

**Resultat** : L'histogramme interactif avec range slider est fonctionnel. Compositions de bandes predefinies fonctionnelles.

### 8.4 Phase 3 -- Zonal Stats (2-3 semaines)

| Tache | Effort | Fichiers |
|-------|--------|----------|
| `infrastructure/raster/zonal_stats.py` | 3j | Nouveau |
| `core/services/raster_stats_service.py` | 2j | Nouveau |
| `core/tasks/raster_stats_task.py` | 2j | Nouveau |
| `mGroupBox_raster_zonal_stats` (UI) | 2j | `.ui`, controller |
| Gestion attributs temporaires | 2j | Service |
| Integration avec le systeme Undo/Redo | 2j | Service, controller |
| Tests unitaires + integration | 2j | `tests/` |

**Resultat** : Le DIFFERENCIATEUR est livre. Aucun plugin QGIS ne fait ca de maniere integree.

### 8.5 Phase 4 -- Export Raster + Filtering Dual (2 semaines)

| Tache | Effort | Fichiers |
|-------|--------|----------|
| `infrastructure/raster/export.py` | 2j | Nouveau |
| `infrastructure/raster/masking.py` | 2j | Nouveau |
| Page raster dans EXPORTING (QStackedWidget) | 2j | `.ui`, controller |
| `RasterExportingController` | 2j | Nouveau |
| Page raster dans FILTERING (QStackedWidget) | 2j | `.ui`, controller |
| `RasterFilteringController` | 1j | Nouveau |
| Support COG export | 1j | `export.py` |

### 8.6 Phase 5 -- Detection d'Objets, Niveau 1 (1-2 semaines)

| Tache | Effort | Fichiers |
|-------|--------|----------|
| `infrastructure/raster/detection/template_matching.py` | 2j | Nouveau |
| `mGroupBox_raster_object_detection` (UI) | 2j | `.ui`, controller |
| Map tool pour capturer template | 2j | Nouveau |
| Vectorisation des resultats | 1j | Service |
| Integration SAM (optionnel) | 3j | Nouveau |

### 8.7 Calendrier Global

```
Mars 2026 (v5.5):
  Semaine 1 : Phase 0 (Fondation) + Phase 1 (Sampling)
  Semaine 2-3 : Phase 2 (Histogramme + Band Viewer)

Avril 2026 (v5.6):
  Semaine 1-3 : Phase 3 (Zonal Stats -- le differenciateur)

Mai 2026 (v5.7):
  Semaine 1-2 : Phase 4 (Export + Filtering dual)

Juin 2026 (v5.8):
  Semaine 1-2 : Phase 5 (Detection objets L1)

Q3 2026 (v6.0):
  Detection objets L2/L3 (SAM, YOLO)
  Multi-band composite filtering (P4)
  Point cloud support (extension future)
```

---

## 9. Considerations Techniques

### 9.1 Thread Safety

Rappel CRITIQUE : les objets QGIS (QgsRasterLayer, QgsVectorLayer) ne sont PAS thread-safe.

**Pattern obligatoire pour les QgsTask** :

```python
class RasterSamplingTask(QgsTask):
    def __init__(self, raster_uri, vector_uri, band, method):
        super().__init__("Raster Sampling", QgsTask.CanCancel)
        # Stocker les URI, PAS les objets layer
        self._raster_uri = raster_uri
        self._vector_uri = vector_uri
        self._band = band
        self._method = method
        self._results = {}

    def run(self):
        """Execute in worker thread -- recreate layers from URI."""
        raster = QgsRasterLayer(self._raster_uri, "temp_raster")
        vector = QgsVectorLayer(self._vector_uri, "temp_vector", "ogr")
        # ... sampling logic avec ces instances locales ...
        return True

    def finished(self, result):
        """Called in main thread -- safe to update UI."""
        if result:
            self.completed.emit(self._results)
```

### 9.2 CRS Management

Toujours reprojeter les geometries vectorielles vers le CRS du raster avant sampling :

```python
from qgis.core import QgsCoordinateTransform, QgsProject

def ensure_same_crs(vector_geom, vector_crs, raster_crs):
    """Reproject vector geometry to raster CRS if needed."""
    if vector_crs != raster_crs:
        transform = QgsCoordinateTransform(
            vector_crs, raster_crs, QgsProject.instance()
        )
        vector_geom.transform(transform)
    return vector_geom
```

### 9.3 Performance sur Gros Rasters

Pour les rasters > 2 GB (courant avec LiDAR HD IGN, Sentinel-2 L2A) :

1. **Streaming par tuiles** : Ne jamais charger le raster entier en memoire
2. **Sampling direct** : `provider.sample()` est O(1), pas besoin de lire le raster entier
3. **Histogramme approche** : Sous-echantillonner pour les rasters enormes, puis affiner
4. **Zonal stats par blocs** : Decouper en blocs de 1024x1024 pour le calcul
5. **Indicator visuel** : Afficher une barre de progression et un estimateur de temps

```python
def estimate_raster_size_mb(layer):
    """Estimate raster size in MB for performance warnings."""
    provider = layer.dataProvider()
    w, h = provider.xSize(), provider.ySize()
    bands = provider.bandCount()
    dtype_size = 4  # Assume Float32 = 4 bytes
    return (w * h * bands * dtype_size) / (1024 * 1024)

def should_warn_large_raster(layer, threshold_mb=2048):
    """Warn user if raster is very large."""
    return estimate_raster_size_mb(layer) > threshold_mb
```

### 9.4 Dependances Optionnelles

Le design suit le pattern "graceful degradation" deja utilise par FilterMate :

```python
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

try:
    from segment_anything import SamPredictor
    SAM_AVAILABLE = True
except ImportError:
    SAM_AVAILABLE = False

# Si OpenCV absent : template matching desactive (bouton grise)
# Si SAM absent : SAM desactive (bouton grise, message "pip install segment-anything")
```

### 9.5 Internationalisation

Tous les textes UI raster utilisent `self.tr()` comme le reste du plugin :

```python
self.mGroupBox_raster_value_sampling.setTitle(self.tr("VALUE SAMPLING"))
self.btn_raster_sample.setText(self.tr("Sample"))
self.lbl_sampling_result.setText(
    self.tr("{count}/{total} features retained").format(
        count=retained, total=total
    )
)
```

### 9.6 Tests

Chaque phase inclut des tests unitaires :

```
tests/
+-- unit/
|   +-- test_raster_sampling.py        # Phase 1
|   +-- test_raster_histogram.py       # Phase 2
|   +-- test_raster_zonal_stats.py     # Phase 3
|   +-- test_raster_export.py          # Phase 4
|   +-- test_template_matching.py      # Phase 5
|   +-- test_dual_mode_toggle.py       # Phase 0
|
+-- integration/
    +-- test_raster_exploring_flow.py  # Flow complet sampling->filter
    +-- test_raster_export_flow.py     # Flow complet clip->export
```

---

## Annexe A -- Comparaison avec l'Ecosysteme

| Feature | FilterMate (prevu) | Value Tool | Point Sampling | SCP | QGIS Natif |
|---------|-------------------|------------|----------------|-----|------------|
| Pixel picking | Oui (via MapTool) | Oui | Non | Non | Non |
| Histogramme interactif | Oui (range select) | Non | Non | Oui (basique) | Proprietes |
| Sampling at features | Oui (centroid + poly) | Non | Oui (pts only) | Non | Processing |
| Zonal stats as filter | **OUI (unique)** | Non | Non | Non | Non |
| Band composition UI | Oui | Non | Non | Oui (avance) | Symbologie |
| Object detection | Oui (template+SAM) | Non | Non | Oui (SVM/RF) | Non |
| Raster export COG | Oui | Non | Non | Non | gdal_translate |
| Lien vector-raster | **OUI (unique)** | Non | Non | Non | Non |
| Undo/Redo | **OUI (unique)** | Non | Non | Non | Non |

---

## Annexe B -- Glossaire

- **COG** : Cloud-Optimized GeoTIFF -- un GeoTIFF structure pour lecture par plages HTTP
- **MNT/MNS/MNH** : Modele Numerique de Terrain / Surface / Hauteur (derives LiDAR)
- **NDVI** : (NIR-Red)/(NIR+Red) -- indice de vegetation, -1 a +1
- **Zonal Stats** : Statistiques (moy, min, max...) calculees sur la zone d'un polygone
- **Band** : Canal spectral d'un raster multi-bandes (R, G, B, NIR, SWIR...)
- **Sampling** : Echantillonner = lire la valeur du raster a un point donne
- **QgsTask** : Mecanisme QGIS pour les taches asynchrones (worker threads)
- **pointOnSurface()** : Point garanti a l'interieur du polygone (vs centroid qui peut etre dehors)
- **SAM** : Segment Anything Model (Meta) -- segmentation zero-shot par prompts
- **YOLO** : You Only Look Once -- detection d'objets temps reel par deep learning

---

> *"Ce qui me fait vibrer dans ce design, c'est le pont raster-vecteur. PERSONNE ne fait ca correctement en QGIS. Les outils existent en pieces detachees -- Value Tool par-ci, Processing Zonal Stats par-la, Select by Expression encore ailleurs. FilterMate va etre le premier a unifier tout ca dans un flux continu : je vois mon raster, je l'explore, je le croise avec mes vecteurs, je filtre, j'exporte. 5 clics au lieu de 15 etapes. C'est comme passer de MapInfo a QGIS -- le meme saut en termes d'experience utilisateur. Et le meilleur ? L'architecture hexagonale existante est FAITE pour ca. Les ports sont la, les patterns sont la, il suffit d'ajouter les briques raster dans les bons emplacements. C'est de la belle ingenierie qui attend d'etre completee."*
>
> -- Atlas, 10 fevrier 2026
