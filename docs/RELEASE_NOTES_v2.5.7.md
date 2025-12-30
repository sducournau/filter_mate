# FilterMate v2.5.7 - Release Notes

## Amélioration de la Compatibilité CRS

**Date de sortie**: Décembre 2025

---

## 🎯 Objectif Principal

Cette version améliore significativement la compatibilité entre différents systèmes de coordonnées (CRS) dans FilterMate. Elle garantit que les opérations métriques (comme les buffers) fonctionnent correctement, quel que soit le CRS source des données.

---

## ✨ Nouvelles Fonctionnalités

### 1. Module crs_utils.py

Un nouveau module dédié à la gestion des CRS a été ajouté :

```python
from modules.crs_utils import (
    is_geographic_crs,      # Détecte les CRS géographiques (lat/lon)
    is_metric_crs,          # Détecte les CRS métriques
    get_optimal_metric_crs, # Trouve le meilleur CRS métrique
    CRSTransformer,         # Classe utilitaire pour les transformations
    create_metric_buffer,   # Buffer avec conversion CRS automatique
    calculate_utm_zone      # Calcule la zone UTM optimale
)
```

### 2. Conversion Automatique vers EPSG:3857

Quand des calculs métriques sont nécessaires (buffer, distances), FilterMate convertit automatiquement vers un CRS métrique :

- **EPSG:3857 (Web Mercator)** : CRS métrique par défaut, bon pour la plupart des cas
- **Zones UTM** : Calculées automatiquement pour plus de précision basé sur l'étendue des données

### 3. Détection Améliorée des CRS

Nouvelles fonctions pour une détection plus robuste :

| Fonction                    | Description                                            |
| --------------------------- | ------------------------------------------------------ |
| `is_geographic_crs(crs)`    | Retourne True si CRS en degrés (lat/lon)               |
| `is_metric_crs(crs)`        | Retourne True si CRS en mètres                         |
| `get_crs_units(crs)`        | Retourne le nom des unités ("meters", "degrees", etc.) |
| `get_layer_crs_info(layer)` | Retourne un dict complet d'infos CRS                   |

### 4. CRSTransformer - Classe Utilitaire

Nouvelle classe pour simplifier les transformations :

```python
from modules.crs_utils import CRSTransformer

# Créer un transformateur
transformer = CRSTransformer("EPSG:4326", "EPSG:3857")

# Transformer une géométrie
transformed_geom = transformer.transform_geometry(geom)

# Transformer un point
transformed_point = transformer.transform_point(point)

# Transformer une emprise
transformed_extent = transformer.transform_extent(extent)
```

### 5. Buffer Métrique Automatique

Nouvelle fonction pour les buffers qui gère automatiquement les CRS :

```python
from modules.geometry_safety import safe_buffer_metric

# Buffer de 100m autour d'un point WGS84
geom = QgsGeometry.fromPointXY(QgsPointXY(2.35, 48.86))  # Paris
crs = QgsCoordinateReferenceSystem("EPSG:4326")
buffered = safe_buffer_metric(geom, 100, crs)  # 100 mètres
```

---

## 🔧 Améliorations Techniques

### Calcul de Zone UTM Optimal

FilterMate calcule maintenant automatiquement la zone UTM optimale basée sur l'étendue des données :

```python
# Paris (2.35°E, 48.86°N) → EPSG:32631 (UTM zone 31N)
# New York (-74°W, 40.7°N) → EPSG:32618 (UTM zone 18N)
# Sydney (151.2°E, 33.9°S) → EPSG:32756 (UTM zone 56S)
```

### Priorité de Sélection CRS

1. **CRS du Projet** : Si déjà métrique, il est utilisé
2. **Zone UTM** : Calculée si une étendue est disponible
3. **EPSG:3857** : Fallback par défaut (Web Mercator)

### Gestion des Cas Limites

- Coordonnées près de l'antiméridien (180°/-180°)
- Régions polaires (>84° latitude)
- Étendues vides ou invalides
- Coordonnées NaN/Inf

---

## 📁 Fichiers Modifiés

| Fichier                        | Description                                                       |
| ------------------------------ | ----------------------------------------------------------------- |
| `modules/crs_utils.py`         | **NOUVEAU** - Module utilitaire CRS                               |
| `modules/geometry_safety.py`   | Ajout de `safe_buffer_metric()` et `safe_buffer_with_crs_check()` |
| `modules/tasks/task_utils.py`  | Amélioration de `get_best_metric_crs()`                           |
| `modules/tasks/filter_task.py` | Utilisation du nouveau module CRS                                 |
| `filter_mate_dockwidget.py`    | Zoom amélioré avec CRS optimal                                    |
| `tests/test_crs_utils.py`      | **NOUVEAU** - Tests unitaires                                     |

---

## 📊 Constantes CRS

Le module définit des constantes utiles :

```python
DEFAULT_METRIC_CRS = "EPSG:3857"  # Web Mercator
METRIC_BUFFER_FALLBACK = "EPSG:3857"

GEOGRAPHIC_CRS_LIST = [
    "EPSG:4326",  # WGS84
    "EPSG:4269",  # NAD83
    "EPSG:4267",  # NAD27
    "EPSG:4258",  # ETRS89
]

REGIONAL_METRIC_CRS = {
    "FR": "EPSG:2154",  # Lambert 93
    "GB": "EPSG:27700", # British National Grid
    "DE": "EPSG:25832", # ETRS89 / UTM 32N
    "ES": "EPSG:25830", # ETRS89 / UTM 30N
}
```

---

## 🧪 Tests

Nouveaux tests pour valider la compatibilité CRS :

```bash
# Exécuter les tests CRS
pytest tests/test_crs_utils.py -v

# Tests inclus :
# - Détection CRS géographique/métrique
# - Calcul de zone UTM
# - Conversion d'unités
# - Opérations de buffer
# - Transformations
# - Cas limites
```

---

## ⚠️ Notes de Migration

### Compatibilité Ascendante

Le code existant continue de fonctionner grâce aux fallbacks :

```python
try:
    from modules.crs_utils import is_geographic_crs
except ImportError:
    # Fallback vers l'ancienne méthode
    def is_geographic_crs(crs):
        return crs.isGeographic() if crs else False
```

### Recommandations

1. **Utilisez `safe_buffer_metric()`** au lieu de `safe_buffer()` pour les buffers en mètres
2. **Utilisez `get_optimal_metric_crs()`** pour obtenir le CRS métrique optimal
3. **Vérifiez le CRS** avant les opérations spatiales avec `is_geographic_crs()`

---

## 🐛 Bugs Corrigés

- **Buffer sur CRS géographique** : Les buffers fonctionnent maintenant correctement même avec des données en WGS84
- **Zoom sur features géographiques** : Le zoom utilise maintenant le CRS optimal au lieu de forcer Web Mercator
- **Avertissements CRS** : Messages d'avertissement plus clairs quand un CRS géographique est détecté

---

## 📚 Documentation

Pour plus de détails sur l'utilisation des CRS dans FilterMate :

- [Guide CRS](https://sducournau.github.io/filter_mate/docs/reference/crs)
- [API Reference](https://sducournau.github.io/filter_mate/docs/api/crs_utils)
- [Exemples](https://sducournau.github.io/filter_mate/docs/examples/crs-conversion)

---

## 🔜 Prochaines Étapes

- Support des CRS composites (3D)
- Cache de transformateurs CRS
- Détection automatique du meilleur CRS régional
- Interface utilisateur pour le choix du CRS métrique

---

**Télécharger FilterMate**: [GitHub Releases](https://github.com/sducournau/filter_mate/releases/tag/v2.5.7)
