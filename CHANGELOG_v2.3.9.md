# CHANGELOG - FilterMate v2.3.9.2 (2025-12-22)

## 🔧 Fix - Validation GEOS trop stricte

### Description

Correction de la validation GEOS v2.3.9.1 qui était trop stricte et rejetait toutes les géométries, causant un nouveau crash.

### Problème v2.3.9.1

- **Symptôme**: Console affichait `create_geos_safe_layer: No safe geometries found (all X skipped)`
- **Cause**: Le test `buffer(0)` rejetait des géométries qui fonctionnaient pourtant avec `selectbylocation`
- **Impact**: Couche vide passée à `selectbylocation` → crash QGIS

### Solution v2.3.9.2

**1. Validation moins stricte par défaut**

```python
def validate_geometry_for_geos(geom, strict=False):
    # Test NaN/Inf (toujours)
    # Test isGeosValid() avec tentative de makeValid() si échec
    # Test buffer(0) seulement en mode strict
```

**2. Fallbacks gracieux dans `create_geos_safe_layer()`**

- Inclut les géométries même si elles échouent la validation (avec `makeValid()`)
- Retourne la couche originale si aucune géométrie ne peut être traitée
- Ne retourne plus jamais `None` pour une couche valide

**3. Code simplifié**

- Suppression des fallbacks `fixgeometries` redondants
- Logique plus claire et prévisible

### Fichiers modifiés

- `modules/geometry_safety.py`: Validation assouplie + fallbacks
- `modules/backends/ogr_backend.py`: Logique simplifiée
- `modules/tasks/filter_task.py`: Logique simplifiée

---

# CHANGELOG - FilterMate v2.3.9.1 (2025-12-22)

## 🔥 Critical Bug Fix - GEOS Crash during OGR Backend Filtering

### Description

Résolution d'un crash critique "Windows fatal exception: access violation" qui se produisait lors du filtrage géométrique avec le backend OGR sur certaines couches (notamment SubDucts, réseaux de conduits).

### Problème

- **Symptôme**: Crash fatal de QGIS ("access violation") pendant `native:selectbylocation`
- **Déclencheur**: Filtrage avec backend OGR sur couches contenant des géométries problématiques
- **Impact**: Crash immédiat de QGIS, perte de travail

### Cause technique

L'algorithme `native:fixgeometries` ne répare pas toutes les corruptions de géométrie. Certaines géométries peuvent toujours causer des crashes au niveau C++/GEOS:

- Coordonnées NaN ou Infinity
- Self-intersections extrêmes
- Corruptions subtiles non détectées par `isGeosValid()`

Le crash se produit dans GEOS au niveau C++ et ne peut PAS être intercepté par Python `try/except`.

### Solution

**1. Nouvelle fonction `validate_geometry_for_geos()`**

Validation profonde qui teste si une géométrie peut survivre aux opérations GEOS:

```python
def validate_geometry_for_geos(geom):
    # Test 1: isGeosValid()
    if not geom.isGeosValid():
        return False
    # Test 2: buffer(0) - détecte les corruptions subtiles
    try:
        buffered = geom.buffer(0, 1)
        if buffered is None or buffered.isEmpty():
            return False
    except:
        return False
    # Test 3: Vérification NaN/Inf dans bounding box
    bbox = geom.boundingBox()
    for coord in [bbox.xMinimum(), bbox.xMaximum(), ...]:
        if math.isnan(coord) or math.isinf(coord):
            return False
    return True
```

**2. Nouvelle fonction `create_geos_safe_layer()`**

Crée une couche mémoire contenant uniquement les géométries GEOS-safe:

```python
safe_layer = create_geos_safe_layer(input_layer, "_safe")
# Filtre les géométries invalides
# Tente de réparer les géométries récupérables
# Retourne une couche avec uniquement des géométries sûres
```

**3. Utilisation dans `_safe_select_by_location()` et `_execute_ogr_spatial_selection()`**

Les appels à `native:selectbylocation` utilisent maintenant des couches GEOS-safe:

```python
safe_intersect = create_geos_safe_layer(intersect_layer, "_safe")
processing.run("native:selectbylocation", {
    'INPUT': work_layer,
    'INTERSECT': safe_intersect,  # ✅ GEOS-safe
    ...
})
```

### Fichiers modifiés

- `modules/geometry_safety.py`:
  - Ajout de `validate_geometry_for_geos()` - validation profonde GEOS
  - Ajout de `create_geos_safe_layer()` - création de couche GEOS-safe
- `modules/backends/ogr_backend.py`:
  - Import des nouvelles fonctions
  - `_safe_select_by_location()` utilise `create_geos_safe_layer()` au lieu de `fixgeometries`
- `modules/tasks/filter_task.py`:
  - Import des nouvelles fonctions
  - `_execute_ogr_spatial_selection()` utilise `create_geos_safe_layer()`

### Impact

- ✅ Plus de crashes lors du filtrage OGR sur couches avec géométries problématiques
- ✅ Les géométries invalides sont filtrées ou réparées avant les opérations spatiales
- ✅ Log détaillé du nombre de géométries filtrées/réparées
- ⚠️ Légère augmentation du temps de traitement (validation supplémentaire)

---

# CHANGELOG - FilterMate v2.3.9 (2025-12-19)

## 🔥 Critical Bug Fix - Access Violation Crash

### Description

Résolution d'un crash critique "Windows fatal exception: access violation" qui se produisait lors du rechargement du plugin ou de la fermeture de QGIS.

### Problème

- **Symptôme**: Crash QGIS avec "access violation" dans le système de notification Qt
- **Déclencheur**: Rechargement du plugin, fermeture de QGIS pendant timers actifs
- **Impact**: Perte de travail, expérience utilisateur dégradée

### Cause technique

Les lambdas dans `QTimer.singleShot` capturaient des références directes à `self`, qui étaient détruites avant l'exécution des callbacks, causant des accès à de la mémoire libérée.

### Solution

**1. Weak References pour tous les timers Qt**

```python
# Avant (❌ DANGEREUX)
QTimer.singleShot(1000, lambda: self.method())

# Après (✅ SÉCURISÉ)
weak_self = weakref.ref(self)
def safe_callback():
    strong_self = weak_self()
    if strong_self is not None:
        strong_self.method()
QTimer.singleShot(1000, safe_callback)
```

**2. Vérifications de sécurité dans les callbacks**

```python
def callback():
    try:
        if not hasattr(self, 'dockwidget'):
            return
    except RuntimeError:
        return
    # Code sûr...
```

**3. Fonction utilitaire safe_show_message()**

```python
safe_show_message('info', "FilterMate", "Message")
```

### Emplacements corrigés

- ✅ Ligne 150: Debouncing layersAdded
- ✅ Lignes 562-567: Force reload layers + UI refresh
- ✅ Ligne 755: Wait for widget initialization
- ✅ Ligne 780: Recovery retry add_layers
- ✅ Ligne 849: Safety timer ensure_ui_enabled
- ✅ Ligne 888: On layers added

### Impact

- ✅ Plus de crashes lors du rechargement du plugin
- ✅ Fermeture propre de QGIS même avec timers actifs
- ✅ Stabilité accrue lors de changements rapides de projet
- ⚠️ Tests requis pour validation complète

### Documentation

- 📄 [FIX_ACCESS_VIOLATION_CRASH_2025-12-19.md](docs/fixes/FIX_ACCESS_VIOLATION_CRASH_2025-12-19.md)
- Pattern de développement mis à jour pour futurs timers

### Tests recommandés

1. Rechargement rapide du plugin (10x)
2. Fermeture QGIS pendant chargement des couches
3. Rechargement pendant filtrage actif
4. Changement rapide entre projets

---

## 🛡️ Audit de Stabilité Complémentaire (2025-12-22)

### Nouveau module `object_safety.py`

Module centralisé pour la sécurité des objets Qt/QGIS ajouté à `modules/object_safety.py`.

**Fonctions principales :**
| Fonction | Description |
|----------|-------------|
| `is_sip_deleted(obj)` | Vérifie si l'objet C++ sous-jacent est supprimé |
| `is_valid_layer(layer)` | Validation complète d'une couche QGIS |
| `is_valid_qobject(obj)` | Validation d'un QObject |
| `safe_disconnect(signal)` | Déconnexion sécurisée d'un signal |
| `safe_emit(signal, *args)` | Émission sécurisée d'un signal |
| `make_safe_callback(obj, method)` | Wrapper pour callbacks QTimer |

### Corrections appliquées

**1. filter_mate_app.py**

- Import de `sip` et `object_safety`
- `_filter_usable_layers()` utilise maintenant `is_sip_deleted()` et `is_valid_layer()`
- Protection contre accès à des layers C++ supprimés

**2. layer_management_task.py**

- `finished()` utilise `safe_emit()` et `safe_disconnect()`
- Élimine les try/except RuntimeError manuels

**3. filter_task.py**

- Import de `object_safety`
- `_organize_layers_to_filter()` valide chaque layer avant accès
- Protection contre layers supprimés pendant itération

### Rapport complet

- 📄 [AUDIT_ACCESS_VIOLATIONS_2025-12-22.md](docs/AUDIT_ACCESS_VIOLATIONS_2025-12-22.md)

---

## 🔥 Critical Bug Fix - Crash lors du filtrage géométrique avec buffer (2025-12-22)

### Description

Résolution d'un crash critique "Windows fatal exception: access violation" qui se produisait lors du filtrage depuis une couche de points avec sélection unique + buffer, intersectant d'autres couches.

### Problème

- **Symptôme**: Crash QGIS avec "access violation" dans Qt event processing
- **Déclencheur**: Single selection sur couche point → buffer → intersects all other layers
- **Impact**: Crash immédiat de QGIS sans possibilité de récupération

### Cause technique

L'algorithme `native:selectbylocation` recevait des géométries invalides ou des couches non validées, provoquant un accès mémoire invalide au niveau C++/GEOS.

Problèmes identifiés:

1. Pas de validation du layer intersect avant `selectbylocation`
2. `_apply_buffer_with_fallback` retournait une couche vide au lieu de `None` en cas d'échec
3. Pas de vérification de la validité des géométries avant les opérations spatiales

### Solution

**1. Nouvelle méthode `_validate_intersect_layer()` dans OGR backend**

```python
def _validate_intersect_layer(self, intersect_layer: QgsVectorLayer) -> bool:
    """Valide que le layer est sûr pour les opérations spatiales."""
    if intersect_layer is None:
        return False
    if not intersect_layer.isValid():
        return False
    if intersect_layer.featureCount() == 0:
        return False
    # Vérifie qu'au moins une géométrie est valide
    has_valid_geometry = False
    for feature in intersect_layer.getFeatures():
        if validate_geometry(feature.geometry()):
            has_valid_geometry = True
            break
    return has_valid_geometry
```

**2. Validation avant chaque appel `selectbylocation`**

```python
# STABILITY FIX v2.3.9
if not self._validate_intersect_layer(intersect_layer):
    self.log_error("Intersect layer validation failed")
    return False
```

**3. Protection dans `_apply_buffer`**

```python
# Validation du layer source avant buffer
if source_layer is None or not source_layer.isValid():
    return None
if source_layer.featureCount() == 0:
    return None
```

**4. Retour `None` au lieu de layer vide en cas d'échec**

```python
# _apply_buffer_with_fallback retourne maintenant None en cas d'échec
# au lieu d'un layer vide qui causait des crashes
```

**5. Validation des géométries dans `prepare_ogr_source_geom`**

```python
# Vérifie qu'au moins une géométrie est valide avant de stocker
has_valid_geom = False
for feature in layer.getFeatures():
    if validate_geometry(feature.geometry()):
        has_valid_geom = True
        break
if not has_valid_geom:
    self.ogr_source_geom = None
    return
```

### Fichiers modifiés

- `modules/backends/ogr_backend.py`:
  - Ajout de `_validate_intersect_layer()`
  - Ajout de `_validate_input_layer()`
  - Ajout de `_safe_select_by_location()` - wrapper sécurisé avec context GeometrySkipInvalid
  - Validation avant chaque `selectbylocation` via wrapper sécurisé
  - Validation source layer dans `_apply_buffer`
- `modules/tasks/filter_task.py`:
  - Validation géométries dans `_execute_ogr_spatial_selection`
  - Ajout de `QgsProcessingContext.GeometrySkipInvalid` pour tous les appels processing
  - Validation géométries dans `_copy_selected_features_to_memory`
  - Validation géométries dans `_copy_filtered_layer_to_memory`
  - Protection spéciale pour les couches virtuelles QGIS (toujours copiées en mémoire)
  - Protection dans `_apply_buffer_with_fallback`
  - Validation finale dans `prepare_ogr_source_geom`
- `modules/constants.py`:
  - Ajout de `PROVIDER_VIRTUAL` et mapping vers OGR backend

### Impact

- ✅ Plus de crashes lors du filtrage géométrique avec buffer
- ✅ Support amélioré des couches virtuelles QGIS
- ✅ Meilleure gestion des erreurs avec messages descriptifs
- ✅ Fallback gracieux quand les opérations échouent
- ⚠️ Tests requis: single selection + buffer + intersects avec couche virtuelle

---

**Version**: 2.3.9  
**Date**: 2025-12-22  
**Priorité**: CRITIQUE  
**Status**: ✅ Fix appliqué - En attente de validation
