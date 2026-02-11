# Systeme Dual Vector/Raster pour FilterMate
## Document de Conception -- Atlas, Veille Technologique Geospatiale

**Date** : 10 fevrier 2026 (cree) | 11 fevrier 2026 (raffine par Marco)
**Version** : 2.0
**Auteurs** : Atlas (conception initiale), Marco (raffinement technique)
**Destinataire** : Simon (Lead Dev FilterMate)
**Branche** : `refactor/quick-wins-2026-02-10`

---

## Statut Global

| Phase | Nom | Statut | Branche | Lignes ajoutees |
|-------|-----|--------|---------|-----------------|
| Phase 0 | Fondation Dual Mode | **DONE** | `refactor/quick-wins-2026-02-10` | ~650 |
| Phase 1 | Layer Info + Value Sampling | **DONE** | `refactor/quick-wins-2026-02-10` | ~1,050 |
| Phase 2 | Histogramme + Band Viewer | **DONE** | `refactor/quick-wins-2026-02-10` | ~1,600 |
| Phase 3 | Statistiques Zonales | TODO | - | ~1,500 (estimation) |
| Phase 4 | Export Raster + Filtering Dual | TODO | - | ~1,200 (estimation) |
| Phase 5 | Detection d'Objets (Niveau 1) | TODO | - | ~800 (estimation) |

**Total code raster ecrit** : ~3,300 lignes dans 8 nouveaux fichiers + ~500 lignes de modifications dans fichiers existants.

---

## Table des Matieres

1. [Vision Globale](#1-vision-globale)
2. [Architecture du Dual Panel](#2-architecture-du-dual-panel)
3. [Panel Raster Exploring -- Conception Detaillee](#3-panel-raster-exploring--conception-detaillee)
4. [Panel Vector Exploring -- Evolution](#4-panel-vector-exploring--evolution)
5. [Extension aux Autres Panels](#5-extension-aux-autres-panels)
6. [Wireframes Textuels](#6-wireframes-textuels)
7. [Integration Technique dans l'Architecture Hexagonale](#7-integration-technique-dans-larchitecture-hexagonale)
8. [Priorisation et Feuille de Route](#8-priorisation-et-feuille-de-route)
9. [Considerations Techniques](#9-considerations-techniques)
10. [Lecons Apprises (Phases 0-2)](#10-lecons-apprises-phases-0-2)
11. [Risques et Dependances](#11-risques-et-dependances)

---

## 1. Vision Globale

### Le Probleme

FilterMate est aujourd'hui un outil 100% vectoriel. Les analystes SIG travaillent pourtant quotidiennement sur des donnees hybrides : BD TOPO en PostGIS *et* MNT IGN en GeoTIFF, parcelles cadastrales *et* images Sentinel-2, bati 3D *et* LiDAR HD rasterise. Le passage d'un monde a l'autre necessite aujourd'hui des outils separes -- Value Tool pour les pixels, Select by Expression pour les vecteurs, Processing pour les stats zonales. C'est l'equivalent de devoir jongler entre trois cartes papier alors qu'on veut une seule vue unifiee.

### La Solution : Dual Mode Context-Aware

Le systeme dual ne se contente pas d'ajouter un onglet "Raster" a cote du "Vecteur". Il **detecte automatiquement** le type de la couche active dans le panneau QGIS Layers et bascule le contexte de l'interface en consequence.

### Principes Directeurs

1. **Context-Aware avant tout** : Le panel s'adapte a la couche active, pas l'inverse
2. **Decouplage strict** : Les composants raster sont des modules independants, pas des greffes sur le code vectoriel
3. **Progressive Disclosure** : Les fonctions avancees (detection d'objets, multi-bandes) sont cachees par defaut
4. **Coherence UI** : Memes patterns visuels (QGroupBox checkable, meme disposition keys/content)
5. **Performance** : Tout calcul raster lourd passe par QgsTask (thread-safe)
6. **Zero regression** : Les modifications aux fichiers existants sont minimales (wiring/registration uniquement)

---

## 2. Architecture du Dual Panel

### 2.1 Mecanisme de Basculement

**Choix technique retenu : QStackedWidget + Auto-Detection + Toggle Fallback**

| Approche | Avantage | Inconvenient | Verdict |
|----------|----------|-------------|---------|
| QTabWidget (onglets V/R) | Explicite, toujours accessible | Encombrement vertical, choix manuel | NON |
| QStackedWidget + toggle | Compact, basculement rapide | Bouton supplementaire | PARTIELLEMENT |
| QStackedWidget + auto-detect | Zero friction, intelligent | Necessite fallback manuel | **OUI** |

**Implementation reelle** (validee en Phase 0) : combine auto-detection + toggle fallback.

```
Quand l'utilisateur selectionne une couche dans le panneau Layers QGIS :
  - Si QgsVectorLayer  -->  stackedWidget.setCurrentIndex(0)  [Panel Vector]
  - Si QgsRasterLayer  -->  stackedWidget.setCurrentIndex(1)  [Panel Raster]
  - Si autre (mesh, point cloud, ...)  -->  rester sur le panel actuel

Fallback : DualModeToggle (segment control V/R) en haut du frame_exploring.
```

### 2.2 Structure Widget Implementee

```
frame_exploring (QFrame) -- INCHANGE dans la structure .ui
|
+-- verticalLayout_main_content
    |
    +-- DualModeToggle (insere a l'index 0)                    [DONE Phase 0]
    |   +-- QPushButton "V" | QPushButton "R" (QButtonGroup exclusive)
    |
    +-- scrollArea_frame_exploring (QScrollArea) -- INCHANGE
        |
        +-- verticalLayout_exploring_tabs_content
            |
            +-- _stacked_exploring (QStackedWidget)            [DONE Phase 0]
                |
                +-- page_exploring_vector (QWidget) -- index 0
                |   +-- mGroupBox_exploring_single_selection   (existant, deplace)
                |   +-- mGroupBox_exploring_multiple_selection (existant, deplace)
                |   +-- mGroupBox_exploring_custom_selection   (existant, deplace)
                |
                +-- page_exploring_raster (QWidget) -- index 1
                    +-- mGroupBox_raster_layer_info            [DONE Phase 1]
                    +-- mGroupBox_raster_value_sampling         [DONE Phase 1]
                    +-- mGroupBox_raster_histogram             [DONE Phase 2]
                    +-- mGroupBox_raster_band_viewer            [DONE Phase 2]
                    +-- mGroupBox_raster_zonal_stats            [TODO Phase 3]
                    +-- mGroupBox_raster_object_detection       [TODO Phase 5]
```

**Decision d'implementation** : Toute la construction des widgets est programmatique (dans `_setup_dual_mode_exploring()`, ~500 lignes). Aucune modification au fichier `.ui`. Ce choix permet un rollout graduel sans casser le fichier Qt Designer.

### 2.3 Le Toggle Vector/Raster -- Implementation Reelle

Le toggle est implemente dans `ui/widgets/dual_mode_toggle.py` (128 lignes).

```python
# ui/widgets/dual_mode_toggle.py -- Code reel (simplifie)
class DualMode(IntEnum):
    VECTOR = 0
    RASTER = 1

class DualModeToggle(QWidget):
    """Segment control for Vector/Raster mode switching."""
    modeChanged = pyqtSignal(int)  # 0=vector, 1=raster

    def __init__(self, parent=None):
        super().__init__(parent)
        self._btn_vector = QPushButton("V")
        self._btn_raster = QPushButton("R")
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        # ...
        self._btn_group.idClicked.connect(self.modeChanged.emit)

    def setMode(self, mode: int):
        """Programmatic mode switch with blockSignals."""
        btn = self._btn_vector if mode == DualMode.VECTOR else self._btn_raster
        btn.blockSignals(True)
        btn.setChecked(True)
        btn.blockSignals(False)
        self._stacked_exploring.setCurrentIndex(mode)  # Direct update
```

**Point notable** : Le `setMode()` utilise `blockSignals()` pour eviter les boucles de signaux lors du basculement programmatique (lecon apprise en Phase 0).

Auto-detection sur changement de couche active :

```python
# Dans filter_mate_dockwidget.py -- Code reel
def _on_dual_mode_layer_changed(self, layer):
    if layer is None:
        return
    from qgis.core import QgsRasterLayer
    from .ui.widgets.dual_mode_toggle import DualMode
    if isinstance(layer, QgsRasterLayer):
        self._dual_mode_toggle.setMode(DualMode.RASTER)
        if self._raster_exploring_ctrl:
            self._raster_exploring_ctrl.set_raster_layer(layer)
    elif isinstance(layer, QgsVectorLayer):
        self._dual_mode_toggle.setMode(DualMode.VECTOR)
```

---

## 3. Panel Raster Exploring -- Conception Detaillee

### 3.1 GroupBox 1 : Informations Couche Raster -- **DONE**

**Statut** : Implemente et committe (`0ce2c85f`)
**Fichiers** : `filter_mate_dockwidget.py` (construction), `raster_exploring_controller.py` (logique)

**Contenu** :

```
+---[LAYER INFO]-------------------------------------+
| Nom:      MNT_IGN_75m.tif                          |
| Format:   GeoTIFF (COG: Oui)                       |
| Taille:   4096 x 4096 px  |  Pixel: 75m x 75m     |
| Bandes:   1 (Float32)     |  NoData: -9999.0       |
| CRS:      EPSG:2154 (RGF93 / Lambert-93)           |
| Emprise:  [xmin, ymin, xmax, ymax]                  |
+----------------------------------------------------+
```

**Implementation reelle** :
- 6 `QLabel` en lecture seule dans un `QFormLayout`, rafraichis via `set_raster_layer()`
- Detection COG automatique via `_detect_cog()` (cherche `LAYOUT=COG` dans les metadonnees GDAL)
- Types de donnees mappes par `_data_type_string()` (Qgis.DataType enum -> string lisible)
- Unites de carte mappees par `_map_unit_string()` (QgsUnitTypes -> string)
- Pas de bouton "Copier l'emprise" ni "Zoom sur l'emprise" -- ces fonctions sont reportees a Phase 4 (nice-to-have)

**Infra sous-jacente** : `infrastructure/raster/sampling.py:get_raster_info()` -- extrait les metadonnees raster de maniere thread-safe.

**Criteres d'acceptance** :
- [x] Les metadonnees se rafraichissent a chaque changement de couche raster
- [x] Detection COG fonctionne (True/False)
- [x] Gestion propre quand le raster n'a pas de NoData
- [x] Fonctionne avec les providers gdal, wms, wcs
- [ ] (Nice-to-have) Boutons copier emprise / zoom emprise

### 3.2 GroupBox 2 : Echantillonnage de Valeurs Raster -- **DONE**

**Statut** : Implemente et committe (`0ce2c85f`)
**Fichiers** : `filter_mate_dockwidget.py`, `raster_exploring_controller.py`, `infrastructure/raster/sampling.py`, `core/domain/raster_filter_criteria.py`, `core/tasks/raster_sampling_task.py`

**Contenu** :

```
+---[VALUE SAMPLING]----------------------------------+
|                                                      |
| Couche raster :  [QgsMapLayerComboBox - raster only] |
| Bande :          [QComboBox - Band 1, Band 2, ...]   |
| Couche vecteur : [QgsMapLayerComboBox - vector only] |
| Methode :        [QComboBox]                         |
|                  ( ) Point sur surface               |
|                  ( ) Centroide                        |
|                                                      |
| --- Filtre sur valeur echantillonnee ---             |
| Operateur : [>=]  Valeur : [____500.0____]           |
| (si BETWEEN) et : [____1500.0____]                   |
|                                                      |
| [Echantillonner]  [Appliquer le filtre]              |
|                                                      |
| Resultat : 342/1204 entites retenues                 |
| [========================================] 100%      |
+-----------------------------------------------------+
```

**Implementation reelle** :
- `QgsMapLayerComboBox` (filtre `RasterLayer`) pour la couche raster
- `QComboBox` pour le choix de bande (peuple dynamiquement via `_update_band_combo()`)
- `QgsMapLayerComboBox` (filtre `VectorLayer`, geometries polygones/points uniquement) pour la couche vecteur cible
- `QComboBox` pour la methode de sampling : `PointOnSurface` / `Centroid`
  - **Note** : La methode "Moyenne sous polygone" (MeanUnderPolygon) est reportee a Phase 3 (Zonal Stats). Elle necessite `QgsZonalStatistics` et sort du scope du simple sampling.
- `QComboBox` pour l'operateur : `=`, `!=`, `>`, `>=`, `<`, `<=`, `BETWEEN`
  - Le spinbox "max" pour BETWEEN est masque/affiche dynamiquement via `_on_raster_operator_changed()`
- `QDoubleSpinBox` pour la valeur seuil (plage -999999 a 999999, 2 decimales)
- `QPushButton` "Sample" : lance `RasterSamplingTask` via `QgsApplication.taskManager()`
- `QPushButton` "Apply Filter" : appelle `layer.selectByIds()` avec les IDs correspondants
- `QProgressBar` pendant le calcul
- `QLabel` resultat (format : "X/Y features retained")

**Objets de domaine** (`core/domain/raster_filter_criteria.py` -- 221 lignes, frozen dataclasses) :
- `SamplingMethod(Enum)` : CENTROID, POINT_ON_SURFACE
- `ComparisonOperator(Enum)` : 7 operateurs, chacun avec `.evaluate(value, threshold, max_threshold)`
- `RasterSamplingCriteria(@dataclass(frozen=True))` : parametres de sampling immutables
- `RasterSamplingResult(@dataclass)` : feature_values dict, matching_ids set, stats
- `SamplingStats(@dataclass(frozen=True))` : min/max/mean/std/median avec `from_values()` factory

**Pattern thread-safe** (`core/tasks/raster_sampling_task.py` -- 255 lignes) :
- Stocke les URI (pas les objets layer) dans `__init__()`
- Recree `QgsRasterLayer` et `QgsVectorLayer` dans `run()` (worker thread)
- `RasterSamplingSignals(QObject)` : completed, error, progress_updated
- Reprojection CRS integree (vecteur vers raster CRS avant sampling)
- Support `QgsFeedback` pour annulation

**Criteres d'acceptance** :
- [x] Echantillonnage fonctionne avec raster single-band et multi-band
- [x] CRS differents entre raster et vecteur : reprojection automatique
- [x] Calcul asynchrone via QgsTask (pas de freeze UI)
- [x] Annulation du calcul via feedback
- [x] Operateur BETWEEN masque/affiche le spinbox max dynamiquement
- [x] Domaine pur (zero import QGIS dans raster_filter_criteria.py)
- [x] pointOnSurface() utilise par defaut (pas centroid)
- [ ] (Manquant) Tests unitaires pour le sampling (pas de repertoire tests/)
- [ ] (Manquant) MeanUnderPolygon (reporte a Phase 3)

### 3.3 GroupBox 3 : Histogramme -- **DONE**

**Statut** : Implemente et committe (`0ce2c85f` + `511cefe0`)
**Fichiers** : `ui/widgets/raster_histogram_widget.py`, `infrastructure/raster/histogram.py`, `ui/controllers/raster_exploring_controller.py`

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
|                                                      |
| Stats: min=12.3 | max=987.6 | mean=456.2 | std=123  |
|                                                      |
| [Calculer]  [Appliquer comme filtre vecteur]         |
+-----------------------------------------------------+
```

**Implementation reelle** :
- `RasterHistogramWidget` (509 lignes, QPainter custom, **zero dependance externe**)
  - Dessine barres d'histogramme avec couleurs basees sur la palette QGIS
  - Zone de selection orange (drag souris) avec signal `rangeChanged(float, float)`
  - Double-clic pour annuler la selection
  - Tooltip au survol (valeur bin, count)
  - API : `set_data(counts, bin_edges, stats)`, `set_range()`, `get_range()`, `clear()`, `has_data()`
- `QComboBox` bande (partage avec le GroupBox Value Sampling? Non, combobox independante)
- `QComboBox` bins (64, 128, 256, 512)
- `QPushButton` "Compute" (lance le calcul)
- `QPushButton` "Apply as Vector Filter" (filtre les features dont la valeur sampled tombe dans la plage)
- `QLabel` statistiques (min/max/mean/std/range)

**Decision architecturale** : Pas de QgsRangeSlider. Le widget histogramme custom integre directement la selection par drag. Cela evite une dependance a QGIS >= 3.18 et offre un controle visuel plus intuitif (la selection est visuellement liee aux barres de l'histogramme).

**Debounce** : 300ms sur le `rangeChanged` pour eviter le recalcul excessif pendant le drag. Le timer est un `QTimer(singleShot=True)` nettoye dans `teardown()`.

**Infra** (`infrastructure/raster/histogram.py` -- 196 lignes) :
- `compute_band_histogram(raster_uri, band, n_bins, min_value, max_value)` : retourne (counts, bin_edges) via `QgsRasterBandStats` + numpy
- `compute_band_statistics(raster_uri, band)` : retourne dict {min, max, mean, std_dev, range, sum, count}
- `VALID_BIN_COUNTS = (64, 128, 256, 512)` : constantes validees
- Thread-safe : cree les layers depuis URI

**Criteres d'acceptance** :
- [x] Widget histogramme custom sans dependance externe (pas de matplotlib)
- [x] Selection par drag avec feedback visuel
- [x] Signal rangeChanged debounce a 300ms
- [x] Statistiques affichees sous l'histogramme
- [x] Double-clic pour annuler la selection
- [x] Tooltip au survol
- [ ] (Manquant) Mode "visible extent only" (calculer l'histogramme uniquement sur l'emprise visible)
- [ ] (Manquant) Highlight temps reel des features pendant le drag (necessite integration avec sampling)

### 3.4 GroupBox 6 : Visualiseur de Bandes -- **DONE**

**Statut** : Implemente et committe (`0ce2c85f` + `511cefe0`)
**Fichiers** : `infrastructure/raster/band_utils.py`, `filter_mate_dockwidget.py`, `raster_exploring_controller.py`

**Note** : Reordonne en GroupBox 4 dans l'UI reelle (apres Histogram), avant les futures GroupBoxes Zonal Stats et Object Detection.

**Contenu** :

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
| [Couleur naturelle] [Fausse couleur IRC] [NDVI]      |
|                                                      |
| Bande R: [QComboBox]  G: [QComboBox]  B: [QComboBox] |
| [Appliquer]                                          |
+-----------------------------------------------------+
```

**Implementation reelle** :
- `QTableWidget` (readonly, 5 colonnes : #, Name, Type, Min, Max) -- peuple dynamiquement via `_populate_band_table()`
- 3 `QPushButton` flat pour les presets : Couleur naturelle, Fausse couleur IRC, NDVI
  - Chaque bouton stocke le nom du preset dans `QObject.property("preset_name")`
  - Presets desactives si le raster n'a pas assez de bandes (ex: NDVI necessite >= 4 bandes)
- 3 `QComboBox` pour R/G/B band assignment (peuples dynamiquement)
- `QPushButton` "Apply" pour appliquer la composition custom

**Infra** (`infrastructure/raster/band_utils.py` -- 317 lignes) :
- `get_band_info(raster_uri)` : retourne liste de dicts {number, name, data_type, min, max, no_data}
- `apply_band_composition(layer, red, green, blue)` : applique `QgsMultiBandColorRenderer`
- `apply_single_band(layer, band)` : applique `QgsSingleBandGrayRenderer`
- `apply_preset_composition(layer, preset_name)` : lookup dans `PRESET_COMPOSITIONS`
- `PRESET_COMPOSITIONS` : natural_color(1,2,3), false_color_irc(4,3,2), ndvi_false_color(4,3,2), swir_composite(6,4,3), agriculture(5,4,3)

**Criteres d'acceptance** :
- [x] Table de bandes peuplee automatiquement
- [x] Presets fonctionnels (couleur naturelle, IRC, NDVI)
- [x] Presets desactives si bandes insuffisantes
- [x] Composition custom R/G/B applicable
- [x] `triggerRepaint()` appele apres changement de renderer
- [ ] (Manquant) Formule d'index spectral custom (ex: `(B4-B3)/(B4+B3)`) -- reportee
- [ ] (Manquant) Widget `band_composition_widget.py` separe (logique gardee dans le controller pour l'instant)

### 3.5 GroupBox 4 : Statistiques Zonales -- **TODO Phase 3**

**Statut** : Non implemente. C'est LE differenciateur majeur.
**Priorite** : P1 -- Critique pour la proposition de valeur unique de FilterMate.

**Objectif** : Filtrer des entites vectorielles par les statistiques raster calculees sous leur emprise geometrique. "Montre-moi les communes ou l'altitude moyenne depasse 800m" -- en 3 clics.

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

**Fichiers a creer** :

| Fichier | Role | Estimation |
|---------|------|-----------|
| `infrastructure/raster/zonal_stats.py` | Wrapper QgsZonalStatistics, calcul sur copie memoire | 1.5j |
| `core/services/raster_stats_service.py` | Orchestration stats zonales | 1j |
| `core/tasks/raster_stats_task.py` | QgsTask pour calcul async | 1j |
| `core/domain/raster_stats_result.py` | Dataclasses pour resultats | 0.5j |
| Modifications `raster_exploring_controller.py` | UI wiring GroupBox zonal stats | 1.5j |
| Modifications `filter_mate_dockwidget.py` | Construction GroupBox dans page_raster | 1j |

**ATTENTION -- Piege connu** : `QgsZonalStatistics` ecrit les colonnes en dur dans la couche vectorielle source. Il faut TOUJOURS travailler sur une copie memoire via `QgsVectorLayer.materialize(QgsFeatureRequest())`. C'est le piege documentee par Atlas.

**Backend technique** :

```python
# infrastructure/raster/zonal_stats.py (A CREER)
from qgis.analysis import QgsZonalStatistics

def compute_zonal_stats(raster_uri, vector_uri, band=1, stats=None, prefix='fm_zs_'):
    """
    Compute zonal statistics for vector features over a raster.

    CRITICAL: QgsZonalStatistics writes in-place.
    Strategy: Clone to memory layer -> compute -> extract -> discard.

    Returns: {feature_id: {'mean': 456.2, 'min': 12.3, 'max': 987.6}}
    """
    # 1. Recreate layers from URI (thread safety)
    raster_layer = QgsRasterLayer(raster_uri, "temp_raster")
    vector_layer = QgsVectorLayer(vector_uri, "temp_vector", "ogr")

    # 2. Clone to memory layer (QgsZonalStatistics writes in-place)
    mem_layer = vector_layer.materialize(QgsFeatureRequest())

    # 3. Run QgsZonalStatistics on the clone
    zs = QgsZonalStatistics(mem_layer, raster_layer, prefix, band, stat_flags)
    zs.calculateStatistics(None)  # None = no feedback

    # 4. Extract results from memory layer attributes
    results = {}
    for feature in mem_layer.getFeatures():
        results[feature.id()] = {stat: feature[f'{prefix}{stat}'] for stat in stats}

    return results  # Memory layer is GC'd
```

**Dependances** :
- Necessite que Phase 1 (sampling) soit fonctionnelle (reutilise le pattern URI/thread-safe)
- Reutilise `ComparisonOperator` de `raster_filter_criteria.py`
- Peut reutiliser `RasterSamplingSignals` pattern pour les signaux async

**Risques** :
- Performance sur grands rasters (> 2 GB) avec beaucoup de polygones (> 10 000) : necessaire de profiler
- `QgsZonalStatistics` ne supporte pas l'annulation native -- il faut implementer un workaround (decoupe par blocs?)
- Provider-dependent : le comportement peut varier entre gdal, wms, virtual raster

**Use cases critiques** :
- Urbaniste : "Communes ou l'altitude moyenne > 800m" (MNT + Admin Express)
- Ecologue : "Parcelles ou le NDVI moyen < 0.3 (sols nus)" (Sentinel-2 + RPG)
- Risques : "Batiments ou la pente max > 45 degres (glissement)" (MNT derive + bati)
- Forestier : "Peuplements ou la hauteur canopee mediane > 15m" (MNH LiDAR + placettes)

**Estimation revisee** : 2 semaines (reduit de 2-3 semaines grace a la fondation existante -- le pattern task/signals/controller est reutilisable directement).

**Criteres d'acceptance** :
- [ ] Calcul zonal stats sur copie memoire (jamais sur la couche originale)
- [ ] Support des statistiques : Mean, Min, Max, StdDev, Median, Count, Sum, Majority
- [ ] Filtrage par predicat (meme operateurs que Value Sampling)
- [ ] Calcul asynchrone via QgsTask avec barre de progression
- [ ] Annulation du calcul
- [ ] Option "ajouter les stats comme attributs temporaires"
- [ ] Reprojection CRS automatique si vecteur et raster dans des CRS differents
- [ ] Temps d'execution affiche dans les resultats
- [ ] Tests unitaires

### 3.6 GroupBox 5 : Detection d'Objets -- **TODO Phase 5**

**Statut** : Non implemente. Panel le plus ambitieux, collapse par defaut.
**Priorite** : P3 -- Innovant mais optionnel pour la premiere release raster.

**Architecture en 3 niveaux de complexite** :

#### Niveau 1 -- Template Matching (Quick Win, 1 semaine)

Correlation de motifs basee sur OpenCV. L'utilisateur dessine un rectangle sur le canvas autour d'un objet type, et le systeme cherche les occurrences similaires.

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

**Fichiers a creer** :

| Fichier | Role | Estimation |
|---------|------|-----------|
| `infrastructure/raster/detection/__init__.py` | Package | trivial |
| `infrastructure/raster/detection/template_matching.py` | OpenCV/scipy template match | 2j |
| `ui/tools/raster_pixel_picker_tool.py` | QgsMapTool pour capture template | 1j |
| Modifications controller + dockwidget | UI GroupBox | 1.5j |

**Dependance optionnelle** : OpenCV (`cv2`). Si absent, fallback vers `scipy.signal.correlate2d`.

#### Niveau 2 -- Segmentation SAM (Medium, 2-3 semaines)

Integration de Segment Anything Model (Meta) via `segment-anything` ou `samgeo`.
**Dependances lourdes** : `segment-anything`, `torch`. GPU recommande.
**Reporte a** : Q3 2026 (v6.0)

#### Niveau 3 -- YOLO Geospatial (Long terme, 4+ semaines)

Detection d'objets supervises avec YOLOv8/v11 sur donnees geospatiales.
**Reporte a** : Q3-Q4 2026 (si demande confirmee)

**IMPORTANT** : Le plugin ne livre PAS les modeles. Il fournit une interface pour charger des modeles ONNX/PyTorch, et documente comment les obtenir. Le plugin reste leger (<10MB).

**Criteres d'acceptance (Niveau 1 seulement)** :
- [ ] Template matching fonctionne avec OpenCV ou scipy fallback
- [ ] Map tool pour capturer un template depuis le canvas
- [ ] Seuil de similarite configurable
- [ ] Resultats vectorises en couche points
- [ ] Export GeoJSON
- [ ] Graceful degradation si cv2/scipy absent

### 3.7 Recapitulatif des GroupBoxes Raster Exploring

| # | GroupBox | Statut | Effort reel/estime | Fichiers principaux |
|---|---------|--------|-------------------|---------------------|
| 1 | Layer Info | **DONE** | 0.5j (reel) | dockwidget, controller, sampling.py |
| 2 | Value Sampling | **DONE** | 1j (reel) | dockwidget, controller, sampling.py, raster_filter_criteria.py, raster_sampling_task.py |
| 3 | Histogram | **DONE** | 1j (reel) | raster_histogram_widget.py, histogram.py, controller |
| 4 | Band Viewer | **DONE** | 0.5j (reel) | band_utils.py, dockwidget, controller |
| 5 | Zonal Stats | **TODO** | 2w (estime) | zonal_stats.py, raster_stats_task.py, raster_stats_result.py, controller |
| 6 | Object Detection | **TODO** | 1w (estime, L1 seulement) | template_matching.py, raster_pixel_picker_tool.py, controller |

**Observation velocite** : Les Phases 0-2 ont ete completees en une seule session (~1 jour). Cela s'explique par l'assistance AI pour la generation de code boilerplate, et le fait que les patterns (controller, task, signals) etaient deja etablis. Les Phases 3+ necessitent de la logique metier plus complexe (zonal stats, template matching) et prendront proportionnellement plus de temps.

---

## 4. Panel Vector Exploring -- Evolution

### 4.1 Ce qui reste INCHANGE

Toute la logique vectorielle existante est preservee telle quelle :

- `mGroupBox_exploring_single_selection` : Selection unitaire avec `QgsFeaturePickerWidget`
- `mGroupBox_exploring_multiple_selection` : Selection multiple avec `QgsCheckableComboBoxFeaturesListPickerWidget`
- `mGroupBox_exploring_custom_selection` : Selection par expression
- Les boutons lateraux : Identify, Zoom, Selecting, Tracking, Linking, Reset
- Le `ExploringController` existant dans `ui/controllers/exploring_controller.py`

Le panel vectoriel n'a PAS ete modifie fonctionnellement par les Phases 0-2. Les 3 groupboxes existants ont simplement ete **deplaces** dans `page_exploring_vector` (index 0 du QStackedWidget). Zero regression.

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

**Statut** : TODO (nice-to-have, pas dans la roadmap critique)
**Effort** : 0.5 jour

### 4.3 Ajout Futur : Lien Raster-Vecteur dans le Panel Vecteur

Un bouton "Enrichir avec valeurs raster" dans le panel vectoriel qui ouvre directement le GroupBox Value Sampling du panel raster. Cross-navigation entre les deux modes.

**Statut** : TODO (post-Phase 3)

---

## 5. Extension aux Autres Panels

### 5.1 Principe General

Le dual Vector/Raster s'applique a chaque page du QToolBox (`toolBox_tabTools`). La structure est la meme : un `QStackedWidget` a l'interieur de chaque page, avec basculement synchronise par le toggle global.

```
Quand l'utilisateur toggle V/R dans frame_header :
  --> stacked_exploring.setCurrentIndex(idx)
  --> stacked_filtering.setCurrentIndex(idx)     [TODO Phase 4]
  --> stacked_exporting.setCurrentIndex(idx)     [TODO Phase 4]
  --> stacked_configuration : pas de dual mode necessaire
```

Un seul toggle controle TOUS les panels. Coherence absolue.

**Risque** : Aujourd'hui seul `stacked_exploring` existe. Les QStackedWidget pour Filtering et Exporting devront etre crees sur le meme pattern programmatique que Phase 0. Estimation : 0.5j par panel.

### 5.2 FILTERING -- Dual Mode (TODO Phase 4)

#### Page Vector (existante) -- Inchangee

Predicats geometriques, operateurs de combinaison, selection de couches, buffer dynamique. Tout le systeme multi-backend reste 100% vectoriel.

#### Page Raster (NOUVELLE -- TODO)

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

**Fichiers a creer** :

| Fichier | Role |
|---------|------|
| `ui/controllers/raster_filtering_controller.py` | Controller pour le filtering raster |
| `infrastructure/raster/masking.py` | Masque binaire, clip raster |

### 5.3 EXPORTING -- Dual Mode (TODO Phase 4)

#### Page Vector (existante) -- Inchangee

#### Page Raster (NOUVELLE -- TODO)

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
| CRS cible : [QgsProjectionSelectionWidget]           |
|                                                      |
| --- Options avancees ---                             |
| [ ] Exporter uniquement les bandes selectionnees     |
| [ ] Appliquer le masque de filtre actif              |
| [ ] Ajouter overview pyramids                        |
|                                                      |
| Dossier : [____/home/user/exports____] [Parcourir]   |
| Nom :     [____export_20260210____]                  |
|                                                      |
| [Exporter]                                           |
+-----------------------------------------------------+
```

**Fichiers a creer** :

| Fichier | Role |
|---------|------|
| `ui/controllers/raster_exporting_controller.py` | Controller export raster |
| `infrastructure/raster/export.py` | gdal.Warp wrapper, COG export |
| `core/tasks/raster_export_task.py` | QgsTask pour export async |

**Point fort** : Export COG (Cloud-Optimized GeoTIFF) -- positionne FilterMate sur le cloud-native. Necessite GDAL >= 3.1.

### 5.4 CONFIGURATION -- Pas de Dual Mode Necessaire

Ajouter une section `"RASTER"` dans le `config.json` existant :

```json
{
  "RASTER": {
    "DEFAULT_SAMPLING_METHOD": {
      "value": "point_on_surface",
      "choices": ["centroid", "point_on_surface"],
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

**Statut** : TODO (Phase 4). Le systeme `ChoicesType`/`ConfigValueType` du JSON tree view existant gere deja ces cas.

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
| [Z] |  +---[SINGLE SELECTION]-----(collapsible)---+   [DONE]   |
| [S] |  | Feature: [QgsFeaturePickerWidget        ] |            |
| [T] |  | Field:   [QgsFieldExpressionWidget      ] |            |
| [L] |  +------------------------------------------+            |
| [R] |  +---[MULTIPLE SELECTION]---(collapsible)---+   [DONE]   |
|     |  | Features: [QgsCheckableComboBox          ] |            |
|     |  | Field:    [QgsFieldExpressionWidget      ] |            |
|     |  +------------------------------------------+            |
|     |  +---[CUSTOM SELECTION]------(collapsible)---+  [DONE]   |
|     |  | Expression: [                            ] |            |
|     |  +------------------------------------------+            |
|     |                                                           |
|     |  <<< Si mode RASTER (page 1 du stacked) >>>              |
|     |  +---[LAYER INFO]-----------(always open)---+   [DONE]   |
|     |  | MNT_IGN_75m.tif | 4096x4096 | 1 bande   |            |
|     |  +------------------------------------------+            |
|     |  +---[VALUE SAMPLING]--------(collapsible)---+  [DONE]   |
|     |  | Raster: [______] Band: [1]                |            |
|     |  | Vector: [______] Method: [PointOnSurface] |            |
|     |  | Filter: [>=] [500.0]    [Sample] [Apply]  |            |
|     |  +------------------------------------------+            |
|     |  +---[HISTOGRAM]-------------(collapsible)---+  [DONE]   |
|     |  | Band: [1]  Bins: [256]                    |            |
|     |  |    ####                                   |            |
|     |  |   ######  ##                              |            |
|     |  |  #########_###___                         |            |
|     |  | [===DRAG SELECTION===]                    |            |
|     |  | Stats: mean=456 std=123                   |            |
|     |  +------------------------------------------+            |
|     |  +---[BAND VIEWER]-----------(collapsible)---+  [DONE]   |
|     |  | [Natural] [IRC] [NDVI]                    |            |
|     |  | R:[Band1] G:[Band2] B:[Band3]   [Apply]   |            |
|     |  +------------------------------------------+            |
|     |  +---[ZONAL STATS]-----------(collapsed)-----+  [TODO]   |
|     |  +---[OBJECT DETECTION]------(collapsed)-----+  [TODO]   |
|     |                                                           |
+=====+===========================================================+
|     FILTERING  |  EXPORTING  |  CONFIGURATION                   |
+=================+============+==================================+
|                                                                  |
|  <<< Contenu Filtering/Exporting/Config                          |
|      avec leur propre dual V/R interne (TODO Phase 4) >>>        |
|                                                                  |
+==================================================================+
```

### 6.2 Boutons Lateraux Raster (TODO -- pas encore implemente)

Les boutons lateraux raster (Pixel Picker, Histogram toggle, Zonal Stats toggle, Detection toggle, Band Viewer toggle, Reset) ne sont PAS encore implementes. L'acces aux GroupBoxes se fait actuellement par scroll dans le panel raster.

**A implementer quand** : Phase 4 ou quand le nombre de GroupBoxes rend le scroll peu pratique.

```
+------+
| [P]  |  Pixel Picker (clic sur canvas pour echantillonner)     [TODO]
|------|
| [H]  |  Histogram (toggle visibilite du groupbox)              [TODO]
|------|
| [Z]  |  Zonal Stats (toggle visibilite du groupbox)            [TODO]
|------|
| [D]  |  Detection (toggle visibilite du groupbox)              [TODO]
|------|
| [B]  |  Band Viewer (toggle visibilite du groupbox)            [TODO]
|------|
|      |
| [R]  |  Reset (reinitialiser tous les filtres raster)          [TODO]
+------+
```

---

## 7. Integration Technique dans l'Architecture Hexagonale

### 7.1 Fichiers Crees et a Creer

#### Fichiers CREES (Phases 0-2) -- Total : ~3,300 lignes

```
filter_mate/
|
+-- core/
|   +-- domain/
|   |   +-- raster_filter_criteria.py      # 221 lignes, frozen dataclasses, ZERO QGIS imports
|   |
|   +-- tasks/
|       +-- raster_sampling_task.py        # 255 lignes, QgsTask async sampling
|
+-- infrastructure/
|   +-- raster/
|       +-- __init__.py                    # 48 lignes, exports
|       +-- sampling.py                    # 373 lignes, sample_raster_at_point/for_features/get_raster_info
|       +-- histogram.py                  # 196 lignes, compute_band_histogram/statistics
|       +-- band_utils.py                 # 317 lignes, get_band_info/apply_composition/presets
|
+-- ui/
    +-- controllers/
    |   +-- raster_exploring_controller.py # 1302 lignes, full Phase 0/1/2 controller
    |
    +-- widgets/
        +-- dual_mode_toggle.py            # 128 lignes, DualModeToggle + DualMode enum
        +-- raster_histogram_widget.py     # 509 lignes, QPainter custom histogram
```

#### Fichiers A CREER (Phases 3-5) -- Estimation : ~3,000 lignes

```
filter_mate/
|
+-- core/
|   +-- domain/
|   |   +-- raster_stats_result.py         # Phase 3 - dataclasses pour resultats zonaux
|   |
|   +-- services/
|   |   +-- raster_filter_service.py       # Phase 4 - orchestration filtre raster
|   |   +-- raster_stats_service.py        # Phase 3 - orchestration stats zonales
|   |
|   +-- tasks/
|       +-- raster_stats_task.py           # Phase 3 - QgsTask stats zonales async
|       +-- raster_export_task.py          # Phase 4 - QgsTask export async
|
+-- infrastructure/
|   +-- raster/
|       +-- zonal_stats.py                 # Phase 3 - QgsZonalStatistics wrapper
|       +-- masking.py                     # Phase 4 - mask binaire, clip
|       +-- export.py                      # Phase 4 - gdal.Warp export
|       +-- detection/
|           +-- __init__.py                # Phase 5
|           +-- template_matching.py       # Phase 5 - OpenCV/scipy template match
|
+-- ui/
|   +-- controllers/
|   |   +-- raster_filtering_controller.py # Phase 4
|   |   +-- raster_exporting_controller.py # Phase 4
|   |
|   +-- tools/
|       +-- raster_pixel_picker_tool.py    # Phase 5 - QgsMapTool pour clic canvas
```

#### Fichiers NON NECESSAIRES (simplification vs design initial)

Ces fichiers prevus dans le design initial d'Atlas ne sont finalement PAS necessaires :

| Fichier prevu | Raison d'annulation |
|---------------|---------------------|
| `core/services/raster_sampling_service.py` | Logique integree directement dans le controller + task. Pas besoin d'un service intermediaire pour le sampling. |
| `ui/widgets/band_composition_widget.py` | Logique gardee dans le controller. Un widget separe n'apporte pas de valeur ajoutee pour cette complexite. |
| `config/raster_config.py` | Les constantes sont dans les modules respectifs (histogram.py, band_utils.py). Config JSON suffit. |
| `infrastructure/raster/detection/sam_integration.py` | Reporte a Q3 2026, pas dans les 5 phases |
| `infrastructure/raster/detection/model_loader.py` | Reporte a Q3 2026, pas dans les 5 phases |

### 7.2 Modifications aux Fichiers Existants

#### Modifications FAITES (Phases 0-2)

| Fichier | Modification | Lignes ajoutees |
|---------|-------------|-----------------|
| `filter_mate_dockwidget.py` | `_setup_dual_mode_exploring()` + `_on_dual_mode_layer_changed()` + `_on_raster_operator_changed()` | ~500 |
| `ui/widgets/__init__.py` | Export DualModeToggle, DualMode, RasterHistogramWidget | +5 |
| `ui/controllers/integration.py` | Enregistrer RasterExploringController | +15 |
| `core/domain/__init__.py` | Export SamplingMethod, ComparisonOperator, RasterSamplingCriteria, etc. | +14 |
| `core/tasks/__init__.py` | Export RasterSamplingSignals, RasterSamplingTask | +14 |
| `infrastructure/raster/__init__.py` | Exports pour sampling, histogram, band_utils | +48 |

#### Modifications PREVUES (Phases 3-5)

| Fichier | Modification | Impact |
|---------|-------------|--------|
| `filter_mate_dockwidget.py` | Ajout GroupBox Zonal Stats et Object Detection dans `_setup_dual_mode_exploring()` | MEDIUM |
| `ui/controllers/integration.py` | Enregistrer raster_filtering et raster_exporting controllers | LOW |
| `ui/controllers/registry.py` | Ajouter les nouvelles entrees controller | LOW |
| `filter_mate_app.py` | Enregistrer raster services dans le DI container | LOW |
| `adapters/app_bridge.py` | Exposer les raster services | LOW |
| `config/config.json` | Ajouter section "RASTER" | LOW |

**Principe cle** : Les modifications aux fichiers existants sont minimales (wiring/registration). Toute la logique raster vit dans des fichiers NOUVEAUX.

### 7.3 Pattern de Controller Raster -- Implementation Reelle

Le `RasterExploringController` (1302 lignes) suit le pattern `BaseController` existant.

```python
# ui/controllers/raster_exploring_controller.py -- Structure reelle

class RasterExploringController(BaseController):
    raster_layer_changed = pyqtSignal(object)

    def __init__(self, dockwidget, signal_manager=None):
        super().__init__(dockwidget, signal_manager=signal_manager)
        self._current_raster_layer = None
        self._current_band = 1
        self._histogram_data = None
        self._sampling_results = None
        self._debounce_timer = None

    def setup(self):
        # Phase 1: sampling connections
        self._setup_sampling_connections()
        # Phase 2: histogram connections
        self._setup_histogram_connections()
        # Phase 2: band viewer connections
        self._setup_band_viewer_connections()

    def set_raster_layer(self, layer):
        # Update layer info labels
        # Update band combos
        # Auto-compute histogram
        pass

    def teardown(self):
        # Stop debounce timer
        # Clear state
        # Disconnect signals
        pass
```

**Sections principales du controller** :
1. **Layer info** (~100 lignes) : `set_raster_layer()`, `_update_layer_info()`, helpers statiques
2. **Sampling** (~200 lignes) : `_on_sample_clicked()`, `_on_sampling_complete()`, `_on_apply_filter_clicked()`
3. **Histogram** (~300 lignes) : `_on_compute_histogram()`, `_on_histogram_range_changed()`, debounce, `_on_apply_histogram_filter()`
4. **Band viewer** (~200 lignes) : `_populate_band_table()`, `_on_band_composition_preset()`, `_on_apply_band_composition()`
5. **Teardown** (~50 lignes) : nettoyage timer, state, signals

### 7.4 Diagramme de Flux de Donnees

```
[Couche Raster Active]
         |
         v
+---[RasterExploringController]---+
|                                  |
|  set_raster_layer()              |
|    |                             |
|    +--> _update_layer_info()     |  --> GroupBox Layer Info (labels)
|    +--> _update_band_combo()     |  --> ComboBoxes bande (sampling, histogram)
|    +--> _populate_band_table()   |  --> GroupBox Band Viewer (QTableWidget)
|    +--> _on_compute_histogram()  |  --> GroupBox Histogram (auto-compute)
|                                  |
|  _on_sample_clicked()            |
|    |                             |
|    +--> RasterSamplingTask       |  --> QgsApplication.taskManager()
|          |                       |
|          +--> sampling.py        |  --> infrastructure/raster/
|          |    (provider.sample())|
|          |                       |
|          v                       |
|    _on_sampling_complete()       |  --> update result label, enable Apply
|                                  |
|  _on_apply_filter_clicked()      |
|    |                             |
|    +--> layer.selectByIds()      |  --> highlight on canvas
|                                  |
|  _on_histogram_range_changed()   |
|    |                             |
|    +--> debounce 300ms           |  --> QTimer singleShot
|    +--> filter matching_ids      |  --> subset of sampling results
|                                  |
|  _on_band_composition_preset()   |
|    |                             |
|    +--> band_utils.py            |  --> apply_preset_composition()
|    +--> triggerRepaint()         |
+----------------------------------+
```

---

## 8. Priorisation et Feuille de Route

### 8.1 Phase 0 -- Fondation du Dual Mode -- **DONE**

**Commit** : `0ce2c85f` (10 fevrier 2026)
**Effort reel** : < 1 jour (incluant Phase 1 et Phase 2)

| Tache | Statut | Fichiers |
|-------|--------|----------|
| Creer `QStackedWidget` dans `frame_exploring` | DONE | `dockwidget.py` |
| Creer le toggle V/R `DualModeToggle` | DONE | `dual_mode_toggle.py` |
| Auto-detection du type de couche | DONE | `dockwidget.py` |
| Creer `RasterExploringController` (skeleton) | DONE | `raster_exploring_controller.py` |
| Enregistrer dans `integration.py` | DONE | `integration.py` |
| Creer `infrastructure/raster/__init__.py` | DONE | `raster/__init__.py` |

**Resultat** : Le dual mode fonctionne mecaniquement. Quand on selectionne un raster, le panel bascule. Le toggle fonctionne. La detection auto fonctionne. Zero regression sur le vectoriel.

### 8.2 Phase 1 -- Layer Info + Value Sampling -- **DONE**

**Commit** : `0ce2c85f` (10 fevrier 2026)
**Effort reel** : < 1 jour (avec Phase 0 et Phase 2)

| Tache | Statut | Fichiers |
|-------|--------|----------|
| `mGroupBox_raster_layer_info` | DONE | dockwidget, controller |
| `infrastructure/raster/sampling.py` | DONE | 373 lignes |
| `core/domain/raster_filter_criteria.py` | DONE | 221 lignes |
| `core/tasks/raster_sampling_task.py` | DONE | 255 lignes |
| `mGroupBox_raster_value_sampling` (UI) | DONE | dockwidget, controller |
| Tests unitaires sampling | **MISSING** | Pas de repertoire tests/ |

**Resultat** : Un utilisateur peut charger un MNT et une couche batiment, echantillonner l'altitude sous chaque batiment, et filtrer "batiments > 500m d'altitude".

### 8.3 Phase 2 -- Histogramme + Band Viewer -- **DONE**

**Commits** : `0ce2c85f` + `511cefe0` (10 fevrier 2026)
**Effort reel** : < 1 jour (avec Phases 0 et 1)

| Tache | Statut | Fichiers |
|-------|--------|----------|
| `RasterHistogramWidget` (QPainter custom) | DONE | 509 lignes |
| `infrastructure/raster/histogram.py` | DONE | 196 lignes |
| `mGroupBox_raster_histogram` (UI) | DONE | dockwidget |
| `infrastructure/raster/band_utils.py` | DONE | 317 lignes |
| `mGroupBox_raster_band_viewer` (UI) | DONE | dockwidget |
| Integration debounce histogram | DONE | controller |
| Integration QgsRangeSlider | SKIPPED | Remplace par drag selection dans le widget histogram |

**Resultat** : L'histogramme interactif avec selection par drag est fonctionnel. Compositions de bandes predefinies (naturel, IRC, NDVI) fonctionnelles.

### 8.4 Phase 3 -- Zonal Stats -- **TODO**

**Estimation revisee** : 2 semaines (vs 2-3 semaines initiale)
**Justification reduction** : Le pattern task/signals/controller est maintenant bien etabli et reutilisable. La fondation (CRS reprojection, thread-safe URI pattern, controller setup pattern) est en place.

| Tache | Effort | Fichiers |
|-------|--------|----------|
| `infrastructure/raster/zonal_stats.py` | 1.5j | Nouveau |
| `core/domain/raster_stats_result.py` | 0.5j | Nouveau |
| `core/services/raster_stats_service.py` | 1j | Nouveau |
| `core/tasks/raster_stats_task.py` | 1j | Nouveau |
| `mGroupBox_raster_zonal_stats` (UI dans dockwidget) | 1j | dockwidget.py |
| Integration dans `raster_exploring_controller.py` | 1.5j | Existant |
| Gestion attributs temporaires | 1j | Service |
| Tests unitaires + integration | 1.5j | Nouveau |

**Resultat** : Le DIFFERENCIATEUR est livre. Aucun plugin QGIS ne fait du filtrage interactif par stats zonales.

**Dependances** :
- Phase 1 (sampling) : reutilise ComparisonOperator, pattern URI/thread-safe
- Phase 2 (histogram) : peut utiliser l'histogramme pour visualiser la distribution des stats

**Pre-requis techniques** :
- Verifier que `QgsZonalStatistics` fonctionne correctement avec des polygones multi-parties
- Profiler sur un dataset > 10,000 polygones pour valider les estimations de performance
- Tester avec differents providers (gdal, wms, virtual raster)

### 8.5 Phase 4 -- Export Raster + Filtering Dual -- **TODO**

**Estimation** : 2 semaines

| Tache | Effort | Fichiers |
|-------|--------|----------|
| `infrastructure/raster/export.py` | 2j | Nouveau |
| `infrastructure/raster/masking.py` | 2j | Nouveau |
| `core/tasks/raster_export_task.py` | 1j | Nouveau |
| QStackedWidget dans EXPORTING | 0.5j | dockwidget.py |
| `RasterExportingController` | 2j | Nouveau |
| QStackedWidget dans FILTERING | 0.5j | dockwidget.py |
| `RasterFilteringController` | 1j | Nouveau |
| Support COG export (check GDAL >= 3.1) | 0.5j | export.py |
| Section RASTER dans config.json | 0.5j | config.json |

**Pre-requis** : GDAL >= 3.1 pour COG. Verifier la version avant d'activer l'option.

### 8.6 Phase 5 -- Detection d'Objets, Niveau 1 -- **TODO**

**Estimation** : 1-2 semaines

| Tache | Effort | Fichiers |
|-------|--------|----------|
| `infrastructure/raster/detection/template_matching.py` | 2j | Nouveau |
| `mGroupBox_raster_object_detection` (UI) | 2j | dockwidget, controller |
| `ui/tools/raster_pixel_picker_tool.py` (QgsMapTool) | 2j | Nouveau |
| Vectorisation des resultats en couche points | 1j | Service |
| Graceful degradation (cv2 absent) | 0.5j | template_matching.py |

### 8.7 Calendrier Revise

La velocite observee (Phases 0-2 en 1 jour) permet de revoir le calendrier a la baisse. Cependant, les Phases 3+ ont une complexite metier superieure et il serait imprudent d'appliquer le meme ratio.

```
Fevrier 2026 (branche refactor/quick-wins):
  [DONE] Phase 0 (Fondation) + Phase 1 (Sampling) + Phase 2 (Histogram + Band Viewer)

Mars 2026 (v5.5):
  Semaine 1-2 : Phase 3 (Zonal Stats -- LE differenciateur)
  Semaine 3 : Tests + stabilisation + merge vers main

Avril 2026 (v5.6):
  Semaine 1-2 : Phase 4 (Export + Filtering dual)

Mai 2026 (v5.7):
  Semaine 1-2 : Phase 5 (Detection objets L1)

Q3 2026 (v6.0):
  Detection objets L2/L3 (SAM, YOLO) -- si demande confirmee
  Multi-band composite filtering
  Point cloud support (extension future)
```

**Gate de release** : Chaque phase doit etre testee dans QGIS avant merge vers main. Beta (QA) valide les criteres d'acceptance.

---

## 9. Considerations Techniques

### 9.1 Thread Safety

Rappel CRITIQUE : les objets QGIS (`QgsRasterLayer`, `QgsVectorLayer`) ne sont PAS thread-safe.

**Pattern obligatoire valide en implementation** :

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

**Lecon apprise** : Le signal pattern `RasterSamplingSignals(QObject)` est plus fiable que les signaux natifs de `QgsTask` pour passer des donnees complexes (dictionnaires, dataclasses) entre le worker thread et le main thread.

### 9.2 Signal Safety

**Pattern obligatoire valide en implementation** :

```python
# Toujours blockSignals autour des mises a jour programmatiques
def _update_band_combo(self, band_count):
    combo = self._dockwidget._combo_raster_band
    combo.blockSignals(True)
    combo.clear()
    for i in range(1, band_count + 1):
        combo.addItem(f"Band {i}", i)
    combo.blockSignals(False)
```

Sans `blockSignals`, remplir un QComboBox declenche `currentIndexChanged` pour chaque `addItem()`, ce qui peut lancer des calculs non desires (ex: recalcul d'histogramme pour chaque bande ajoutee).

### 9.3 CRS Management

Toujours reprojeter les geometries vectorielles vers le CRS du raster avant sampling :

```python
from qgis.core import QgsCoordinateTransform, QgsProject

def ensure_same_crs(vector_geom, vector_crs, raster_crs):
    if vector_crs != raster_crs:
        transform = QgsCoordinateTransform(
            vector_crs, raster_crs, QgsProject.instance()
        )
        vector_geom.transform(transform)
    return vector_geom
```

**Implementation reelle** : La reprojection est integree dans `sample_raster_for_features()` (sampling.py). Chaque geometrie est transformee avant l'appel a `provider.sample()`.

### 9.4 Performance sur Gros Rasters

Pour les rasters > 2 GB (courant avec LiDAR HD IGN, Sentinel-2 L2A) :

1. **Sampling direct** : `provider.sample()` est O(1), pas besoin de lire le raster entier
2. **Histogramme approche** : Sous-echantillonner pour les rasters enormes, puis affiner
3. **Zonal stats par blocs** : Decouper en blocs de 1024x1024 pour le calcul (Phase 3)
4. **Indicateur visuel** : Barre de progression et estimateur de temps (implemente en Phase 1)
5. **Avertissement taille** : Afficher un warning si raster > MAX_RASTER_SIZE_MB (a configurer)

### 9.5 Dependances Optionnelles

Le design suit le pattern "graceful degradation" :

```python
try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False

# Si OpenCV absent : template matching desactive (bouton grise)
# Si SAM absent : SAM desactive (bouton grise, message "pip install segment-anything")
```

**Dependances actuelles (Phases 0-2)** : Aucune nouvelle dependance. Tout est base sur QGIS/PyQt5/numpy (deja disponibles).
**Dependances futures (Phase 5)** : OpenCV optionnel. Ajoute dans `requirements-optional.txt`.

### 9.6 Internationalisation

Tous les textes UI raster utilisent `self.tr()` comme le reste du plugin :

```python
self.mGroupBox_raster_value_sampling.setTitle(self.tr("VALUE SAMPLING"))
self.btn_raster_sample.setText(self.tr("Sample"))
```

**Implementation reelle** : Confirme. Tous les textes visibles dans les GroupBoxes raster passent par `self.tr()`.

### 9.7 Tests

**Situation actuelle** : Le repertoire `tests/` n'existe pas sur la branche `refactor/quick-wins-2026-02-10`. C'est une lacune significative.

**Plan de tests pour chaque phase** :

```
tests/
+-- unit/
|   +-- test_raster_filter_criteria.py     # Phase 1 - domaine (PRIORITAIRE)
|   +-- test_raster_sampling.py            # Phase 1 - infra sampling
|   +-- test_raster_histogram.py           # Phase 2 - infra histogram
|   +-- test_raster_band_utils.py          # Phase 2 - infra band utils
|   +-- test_raster_zonal_stats.py         # Phase 3
|   +-- test_raster_export.py              # Phase 4
|   +-- test_template_matching.py          # Phase 5
|   +-- test_dual_mode_toggle.py           # Phase 0 widget
|
+-- integration/
    +-- test_raster_exploring_flow.py      # Flow complet sampling->filter
    +-- test_raster_export_flow.py         # Flow complet clip->export
```

**Priorite** : Les tests de domaine (`test_raster_filter_criteria.py`) peuvent etre ecrits immediatement car ils n'ont aucune dependance QGIS. Les tests d'infra necessitent un environnement QGIS de test.

---

## 10. Lecons Apprises (Phases 0-2)

### 10.1 Decisions d'Architecture Validees

1. **Approche programmatique (pas de .ui)** : Construire les widgets raster en Python plutot que modifier le fichier Qt Designer a ete le bon choix. Le fichier `.ui` est complexe (~7000 lignes de dockwidget) et les modifications programmatiques permettent un rollout graduel sans risque de regression.

2. **Controller monolithique** : Un seul `RasterExploringController` (1302 lignes) gere les 4 GroupBoxes. C'est plus pragmatique que 4 controllers separes. Si le controller depasse 2000 lignes (Phase 3+), envisager un refactoring en mixins.

3. **DualMode enum (IntEnum)** : Utiliser `IntEnum` avec VECTOR=0 et RASTER=1 comme indices du QStackedWidget est elegant et auto-documentant.

4. **Pas de service intermediaire pour le sampling** : Le design initial prevoyait un `RasterSamplingService` separe. En pratique, le controller appelle directement le `RasterSamplingTask` et recoit les resultats. Un service intermediaire aurait ajoute de la complexite sans benefice.

### 10.2 Pieges Evites

1. **`pointOnSurface()` vs `centroid()`** : Pour les polygones concaves ou multi-parties, `centroid()` peut retourner un point en dehors du polygone. `pointOnSurface()` est toujours a l'interieur. Decision correcte validee.

2. **`blockSignals()` systematique** : Chaque mise a jour programmatique de QComboBox ou QSpinBox est encadree par `blockSignals(True/False)`. Cela previent les cascades de signaux non desires.

3. **Frozen dataclasses** : `RasterSamplingCriteria` est un `@dataclass(frozen=True)`. On ne peut pas modifier ses champs directement. Si besoin de modification, creer une nouvelle instance. Cela garantit l'immutabilite dans un contexte multi-thread.

4. **Exception handling** : Le bloc `_setup_dual_mode_exploring()` est enveloppe dans un `try/except` global. Si la construction echoue (import manquant, widget absent), le plugin continue de fonctionner en mode vectoriel uniquement.

### 10.3 Dette Technique Identifiee

1. **Pas de tests** : Les Phases 0-2 n'ont pas de tests. Les tests de domaine (pure Python) sont une priorite avant Phase 3.

2. **Controller potentiellement trop gros** : 1302 lignes avec Phase 2. Ajouter Phase 3 (zonal stats) va le pousser a ~1600-1800 lignes. Surveiller. Seuil de refactoring : 2000 lignes.

3. **Pas de tests en conditions reelles QGIS** : Le code a ete valide par `ast.parse()` et `py_compile` mais pas teste dans QGIS avec des vrais rasters. Tester avant merge vers main.

4. **Serena memory Phase 2 stale** : La memory `dual_panel_phase2_implementation` indique que les GroupBoxes sont manquants alors qu'ils sont presents. Cette memory doit etre mise a jour.

5. **Pas de boutons lateraux raster** : Les boutons lateraux (Pixel Picker, Histogram toggle, etc.) ne sont pas implementes. L'acces aux GroupBoxes se fait uniquement par scroll. Acceptable pour le moment mais a ameliorer.

---

## 11. Risques et Dependances

### 11.1 Risques Techniques

| Risque | Probabilite | Impact | Mitigation |
|--------|-------------|--------|-----------|
| Performance zonal stats sur > 10K polygones | Moyenne | High | Profiler avec QgsZonalStatistics, chunking si necessaire |
| QgsZonalStatistics incompatible multi-parties | Basse | High | Tester explicitement, fallback GDAL si besoin |
| GDAL < 3.1 sur certaines installations QGIS | Moyenne | Medium | Check version, desactiver COG si absent |
| Controller > 2000 lignes apres Phase 3 | Haute | Medium | Refactoring en mixins prevu |
| OpenCV absent pour Phase 5 | Haute | Low | Fallback scipy deja prevu |
| Regression panel vectoriel | Basse | High | Tester panel vectoriel apres chaque modification du stacked widget |

### 11.2 Dependances Inter-Phases

```
Phase 0 (Fondation)
  |
  +--> Phase 1 (Sampling) -- depend du stacked widget + controller skeleton
  |     |
  |     +--> Phase 2 (Histogram) -- depend du sampling pour le range filter
  |     |
  |     +--> Phase 3 (Zonal Stats) -- depend du sampling pattern (URI, tasks, signals)
  |           |
  |           +--> Phase 4 (Export + Filtering) -- depend des zonal stats pour le filtering raster
  |
  +--> Phase 5 (Detection) -- depend uniquement de Phase 0 (peut etre fait en parallele de Phase 3/4)
```

**Quick wins restants** (peuvent etre faits independamment) :
- Boutons "Copier l'emprise" et "Zoom sur l'emprise" dans Layer Info (0.5j)
- Section RASTER dans config.json (0.5j)
- Tests unitaires domaine (raster_filter_criteria.py) (0.5j)
- Mise a jour de la memory Serena Phase 2 (trivial)

**Taches complexes** (necessite du travail de fond) :
- Phase 3 : Zonal Stats (2 semaines -- logique metier complexe, QgsZonalStatistics quirks)
- Phase 4 : Export COG + Filtering dual (2 semaines -- integration GDAL, nouveaux controllers)
- Phase 5 : Template matching (1-2 semaines -- QgsMapTool, vectorisation, dependance optionnelle)

### 11.3 Criteres de Merge vers Main

Avant de merger la branche `refactor/quick-wins-2026-02-10` vers `main`, les conditions suivantes doivent etre remplies :

1. **Tests en conditions reelles** : Charger un raster et un vecteur dans QGIS, valider chaque GroupBox
2. **Zero regression vectoriel** : Tester le panel vectoriel (single/multiple/custom selection)
3. **Tests de domaine** : Au minimum `test_raster_filter_criteria.py` (pure Python, pas de QGIS)
4. **Code review** : Review adversarial du controller (1302 lignes)
5. **Cleanup** : Pas de print(), pas de logger avec emojis, pas de TODO laisses sans ticket

---

## Annexe A -- Comparaison avec l'Ecosysteme

| Feature | FilterMate (etat) | Value Tool | Point Sampling | SCP | QGIS Natif |
|---------|-------------------|------------|----------------|-----|------------|
| Pixel picking | TODO (Phase 5) | Oui | Non | Non | Non |
| Histogramme interactif | **DONE** (range select) | Non | Non | Oui (basique) | Proprietes |
| Sampling at features | **DONE** (centroid + POS) | Non | Oui (pts only) | Non | Processing |
| Zonal stats as filter | TODO (Phase 3) **UNIQUE** | Non | Non | Non | Non |
| Band composition UI | **DONE** (presets + custom) | Non | Non | Oui (avance) | Symbologie |
| Object detection | TODO (Phase 5) | Non | Non | Oui (SVM/RF) | Non |
| Raster export COG | TODO (Phase 4) | Non | Non | Non | gdal_translate |
| Lien vector-raster | **DONE** (sampling) **UNIQUE** | Non | Non | Non | Non |
| Undo/Redo | Existant (vectoriel) | Non | Non | Non | Non |
| Dual mode auto-detect | **DONE** **UNIQUE** | Non | Non | Non | Non |

---

## Annexe B -- Inventaire des Fichiers Raster

### Fichiers existants (8 fichiers, ~3,300 lignes)

| Fichier | Lignes | Phase | Role |
|---------|--------|-------|------|
| `ui/widgets/dual_mode_toggle.py` | 128 | 0 | Toggle V/R segment control |
| `ui/controllers/raster_exploring_controller.py` | 1302 | 0-2 | Controller principal raster exploring |
| `core/domain/raster_filter_criteria.py` | 221 | 1 | Domaine pur, frozen dataclasses |
| `core/tasks/raster_sampling_task.py` | 255 | 1 | QgsTask sampling async |
| `infrastructure/raster/__init__.py` | 48 | 0 | Exports du package raster |
| `infrastructure/raster/sampling.py` | 373 | 1 | Sampling infra, thread-safe |
| `infrastructure/raster/histogram.py` | 196 | 2 | Calcul histogramme + stats |
| `infrastructure/raster/band_utils.py` | 317 | 2 | Info bandes, compositions, presets |
| `ui/widgets/raster_histogram_widget.py` | 509 | 2 | Widget QPainter custom |

### Fichiers a creer (estimation ~3,000 lignes)

| Fichier | Phase | Estimation lignes |
|---------|-------|-------------------|
| `infrastructure/raster/zonal_stats.py` | 3 | ~200 |
| `core/domain/raster_stats_result.py` | 3 | ~100 |
| `core/services/raster_stats_service.py` | 3 | ~150 |
| `core/tasks/raster_stats_task.py` | 3 | ~200 |
| `infrastructure/raster/export.py` | 4 | ~250 |
| `infrastructure/raster/masking.py` | 4 | ~200 |
| `core/tasks/raster_export_task.py` | 4 | ~200 |
| `ui/controllers/raster_filtering_controller.py` | 4 | ~400 |
| `ui/controllers/raster_exporting_controller.py` | 4 | ~500 |
| `infrastructure/raster/detection/__init__.py` | 5 | ~10 |
| `infrastructure/raster/detection/template_matching.py` | 5 | ~250 |
| `ui/tools/raster_pixel_picker_tool.py` | 5 | ~200 |

---

## Annexe C -- Glossaire

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
- **POS** : Point On Surface -- synonyme de `pointOnSurface()` dans ce document
- **IRC** : InfraRouge Couleur -- composition fausse couleur (NIR, Red, Green)

---

> *Document v2.0 -- Raffine par Marco le 11 fevrier 2026 sur la base du design initial d'Atlas et de l'implementation reelle des Phases 0-2. Les estimations, statuts et decisions techniques refletent l'etat du code sur la branche `refactor/quick-wins-2026-02-10` au commit `511cefe0`.*
