# FilterMate Backlog - Issues & Fixes

**Date de création:** 2026-01-08  
**Dernière mise à jour:** 2026-01-10  
**Version analysée:** 3.1.0  
**Généré par:** BMAD Master + Claude Opus 4.5

---

## 📊 Résumé Exécutif - Migration v3.0

### État de la Migration Architecture Hexagonale

| Composant                 | Statut         | Détails                      |
| ------------------------- | -------------- | ---------------------------- |
| **Nouvelle Architecture** | ✅ Créée       | 108 fichiers (38,561 lignes) |
| **Ancienne Architecture** | ⚠️ À supprimer | 74 fichiers (68,649 lignes)  |
| **Imports Legacy**        | ✅ Migrés      | 143 imports migrés (Phase A) |
| **God Classes**           | ⚠️ 2 fichiers  | 19,155 lignes (hybride)      |

### Phase A - Migration Imports ✅ COMPLÈTE (2026-01-09)

- **Script créé**: `tools/migrate_imports.py`
- **Imports migrés**: 143 dans 35 fichiers
- **Shims de compatibilité**: 6 modules créés
- **Imports legacy restants**: 0 (hors shims et tests)

### Phase C - Slim God Classes ⏸️ PARTIEL (2026-01-10)

| Vague | Status      | Travail Effectué                                |
| ----- | ----------- | ----------------------------------------------- |
| 1     | ✅ Complète | BackendController, LayerSyncController intégrés |
| 2     | ✅ Complète | flash_features, zoom_to_features délégués       |
| 3+    | ⏸️ Bloqué   | Méthodes trop couplées à l'état interne         |

**Conclusion:** Les God Classes restent car les méthodes sont fortement couplées via `PROJECT_LAYERS`, `widgets`, etc. Voir `SLIM_STRATEGY.md` pour l'analyse détaillée.

### Nouvelle Architecture (prête)

| Dossier           | Fichiers | Lignes | Rôle                        |
| ----------------- | -------- | ------ | --------------------------- |
| `core/`           | ~20      | 8,567  | Domain + Services           |
| `adapters/`       | ~40      | 14,436 | Backends + QGIS integration |
| `ui/`             | ~35      | 13,967 | Controllers + Widgets       |
| `infrastructure/` | ~13      | 1,591  | DI + Utils                  |

### Ancienne Architecture (à supprimer)

| Dossier             | Fichiers | Lignes  | Action                   |
| ------------------- | -------- | ------- | ------------------------ |
| `modules/backends/` | 15       | ~11,000 | → `adapters/backends/`   |
| `modules/tasks/`    | 12       | ~18,000 | → `adapters/qgis/tasks/` |
| `modules/` (autres) | 47       | ~40,000 | Migrer ou supprimer      |

---

## 🎯 Plan de Nettoyage Final (v4.0)

### Phase A: Migration des Imports ✅ COMPLÈTE

**Résultat**: 143 imports migrés automatiquement  
**Script**: `tools/migrate_imports.py`  
**Documentation**: `_bmad-output/planning-artifacts/CLEANUP_PLAN_FINAL.md`

### Phase B: Analyse dossier `modules/` ✅ COMPLÈTE (2026-01-10)

**Résultat**: Analyse complète des 66,675 lignes de code legacy

| Catégorie                  | Fichiers | Lignes  | Action                  |
| -------------------------- | -------- | ------- | ----------------------- |
| SUPPRIMER (shims)          | 2        | ~146    | Prêt à supprimer        |
| MIGRER (équivalent existe) | 28       | ~43,000 | Migration progressive   |
| UNIQUE/GARDER              | 27       | ~23,000 | Pas d'équivalent encore |

**Décision**: Garder `modules/` comme package deprecated jusqu'à v4.0

- Warnings de dépréciation actifs via `modules/__init__.py`
- Tests utilisent encore `modules.*` (104 imports)
- Fallbacks créés dans `adapters/backends/` et `ui/widgets/`
- `adapters/backends/postgresql_availability.py` créé comme équivalent

**Fichiers corrigés**:

- `adapters/backends/__init__.py` - fallback POSTGRESQL_AVAILABLE
- `ui/widgets/tree_view.py` - fallback JsonModel
- `adapters/backends/postgresql_availability.py` - nouveau équivalent

### Phase C: Slim God Classes ✅ PARTIELLE (2026-01-10)

**Documentation**: `_bmad-output/planning-artifacts/SLIM_STRATEGY.md`

| Fichier                     | Actuel | Cible   | Stratégie                       |
| --------------------------- | ------ | ------- | ------------------------------- |
| `filter_mate_dockwidget.py` | 13,049 | < 2,000 | Déléguer vers `ui/controllers/` |
| `filter_mate_app.py`        | 6,063  | < 1,500 | Déléguer vers `core/services/`  |

---

## 📋 Issues par Sévérité

| Sévérité        | Total  | Résolus | Restants |
| --------------- | ------ | ------- | -------- |
| 🔴 **Critique** | 6      | 5       | 1        |
| 🟠 **Haute**    | 18     | 5       | 13       |
| 🟡 **Moyenne**  | 42     | 3       | 39       |
| 🟢 **Basse**    | 25     | 0       | 25       |
| **Total**       | **91** | **13**  | **78**   |

### Critiques Résolus ✅

- CRIT-001: Bug État Buffer Multi-Étapes (v3.0.10) ✅
- CRIT-002: SQL Injection Risk (v3.0.20) ✅
- CRIT-004: Thread Safety (v2.3.9) ✅
- CRIT-005: Perte Couche Courante (v3.0.21) ✅
- CRIT-006: TypeError feature_count None (v3.0.19) ✅
- CRIT-003: God Classes → **Architecture créée, Phase 6 complète**

### ✅ Tous les bugs critiques résolus!

**Tests manquants:** HIGH-018 (tests multi-step pour valider CRIT-001)

---

## 🔴 CRITIQUES (6 issues)

### ✅ CRIT-005: Perte de Couche Courante Après Filtre (RÉSOLU)

**Statut:** ✅ Corrigé le 2026-01-10 (commit `0dc2961`)  
**Fichiers:** `modules/tasks/filter_task.py`  
**Solution:** Wrap tous les `layer.reload()` avec `blockSignals(True/False)` pour empêcher les émissions `currentLayerChanged` asynchrones

**Correction appliquée à 3 emplacements:**

1. `_delayed_canvas_refresh()` - dataProvider().reloadData()
2. `finished()` pending subset - cas filtre déjà appliqué (ligne ~12330)
3. `finished()` pending subset - cas nouveau filtre (ligne ~12370)

---

### 🆕 CRIT-005-OLD: Perte de Couche Courante Après Filtre (ARCHIVÉ)

**Fichiers:** `filter_mate_app.py`, `filter_mate_dockwidget.py`, `filter_task.py`  
**Impact:** Plugin inutilisable - Déconnexion totale des signaux et widgets  
**Effort:** 3-5 jours  
**Backends affectés:** **TOUS** (OGR, Spatialite, PostgreSQL)

**Symptômes observés:**

1. `comboBox_filtering_current_layer` perd sa valeur (devient vide/None)
2. Déconnexion partielle ou totale des signaux Qt
3. Boutons d'action ne déclenchent plus rien
4. Problèmes d'affichage des widgets dans les groupboxes d'exploring
5. Changements de paramètres ne fonctionnent plus

**Timing du bug par backend:**
| Backend | Moment du bug |
|---------|---------------|
| **OGR** | Directement après le **1er filtre** |
| **Spatialite** | Lors du **multi-step step 2** |
| **PostgreSQL** | Au **2ème filtre** |

**Cause racine identifiée:**
Les appels `layer.reload()` et `canvas.refresh()` dans `FilterEngineTask.finished()` déclenchent des signaux `currentLayerChanged` qui arrivent **APRÈS** que `filter_engine_task_completed()` a :

1. Réinitialisé `_filtering_in_progress = False`
2. Reconnecté les signaux
3. Mis à jour `_filter_completed_time`

**Séquence de l'échec:**

```
1. FilterEngineTask.finished() s'exécute sur main thread
2. layer.reload() déclenche refresh asynchrone du provider
3. canvas.refresh() planifie des repaints
4. filter_engine_task_completed() est appelé
5. Protection de 2s activée + signaux reconnectés
6. APRÈS 2s: provider refresh termine → émet currentLayerChanged avec layer=None
7. current_layer_changed() appelé HORS fenêtre de protection
8. _ensure_valid_current_layer(None) échoue ou sélectionne mauvaise couche
9. comboBox perd sa valeur → signaux se déconnectent en cascade
```

**Localisation du code problématique:**

1. **filter_task.py:11499-11513** - `layer.reload()` dans `finished()`

```python
if layer.providerType() in ('postgres', 'spatialite', 'ogr'):
    layer.reload()  # ⚠️ Déclenche signaux asynchrones
```

2. **filter_task.py:12001-12008** - `canvas.refresh()` après stopRendering

```python
canvas.stopRendering()
canvas.refresh()  # ⚠️ Peut déclencher currentLayerChanged
```

3. **filter_task.py:12043** - `_single_canvas_refresh()` planifié 1500ms

```python
QTimer.singleShot(refresh_delay, lambda: self._single_canvas_refresh())
# ⚠️ S'exécute APRÈS la fenêtre de protection de 2s!
```

4. **filter_mate_app.py:4530** - Protection insuffisante

```python
POST_FILTER_PROTECTION_WINDOW = 2.0  # seconds
# ⚠️ refresh_delay peut aller jusqu'à 1500ms + temps de refresh
```

5. **filter_mate_dockwidget.py:10557-10558** - Fenêtre de protection trop courte

```python
if elapsed < POST_FILTER_PROTECTION_WINDOW:  # 2.0s
    # ⚠️ layer.reload() async peut prendre >2s sur grosses couches
```

**Fix proposé (approche multi-niveaux):**

**Niveau 1: Étendre la fenêtre de protection**

```python
# filter_mate_dockwidget.py et filter_mate_app.py
POST_FILTER_PROTECTION_WINDOW = 5.0  # Étendre de 2s à 5s
```

**Niveau 2: Bloquer signaux pendant reload/refresh dans finished()**

```python
# filter_task.py - dans finished()
# AVANT layer.reload()
if hasattr(layer, 'blockSignals'):
    layer.blockSignals(True)
try:
    layer.reload()
finally:
    layer.blockSignals(False)
```

**Niveau 3: Vérification continue du combobox**

```python
# filter_mate_app.py - Étendre les checks delayed
for delay in [200, 600, 1000, 1500, 2000, 3000, 4000, 5000]:
    QTimer.singleShot(delay, restore_combobox_if_needed)
```

**Niveau 4: Protéger current_layer_changed contre layer=None**

```python
# filter_mate_dockwidget.py - current_layer_changed()
def current_layer_changed(self, layer):
    # NOUVEAU: Protection absolue pendant 5s post-filtre
    if self._is_within_post_filter_protection():
        if layer is None:
            logger.warning("BLOCKED layer=None during protection")
            return
        if layer.id() != self._saved_layer_id_before_filter:
            logger.warning(f"BLOCKED layer change to {layer.name()}")
            return
```

**Niveau 5: Synchronisation forcée dans \_single_canvas_refresh**

```python
# filter_task.py - _single_canvas_refresh()
def _single_canvas_refresh(self):
    # AVANT tout refresh
    saved_layer_id = getattr(self, '_saved_layer_id_for_refresh', None)

    # ... refresh logic ...

    # APRÈS refresh: forcer restauration combobox via signal
    if saved_layer_id:
        from qgis.PyQt.QtCore import QTimer
        def ensure_combobox():
            # Émettre signal vers filter_mate_app pour restaurer combobox
            pass
        QTimer.singleShot(100, ensure_combobox)
```

**Tests de régression à créer:**

```python
def test_combobox_preserved_after_ogr_filter():
    """Le combobox doit garder sa valeur après un filtre OGR."""
    pass

def test_combobox_preserved_after_spatialite_multistep():
    """Le combobox doit garder sa valeur pendant multi-step Spatialite."""
    pass

def test_combobox_preserved_after_postgresql_second_filter():
    """Le combobox doit garder sa valeur après 2ème filtre PostgreSQL."""
    pass

def test_signals_remain_connected_after_filter():
    """Les signaux d'action doivent rester connectés après filtre."""
    pass

def test_exploring_widgets_functional_after_filter():
    """Les widgets exploring doivent fonctionner après filtre."""
    pass
```

---

### ✅ CRIT-006: TypeError Multi-Step PostgreSQL (feature_count comparé à None) - **RÉSOLU v3.0.19**

**Statut:** ✅ Corrigé en v3.0.19 (2026-01-09)  
**Fichiers:** `postgresql_backend.py`, `filter_task.py`, `auto_optimizer.py`  
**Impact:** 3ème filtre échoue TOTALEMENT pour TOUTES les couches distantes  
**Effort:** 1 jour  
**Backend affecté:** **PostgreSQL** (multi-step)

**Correction appliquée:**

- `postgresql_backend.py:1648-1650` - Protection None dans apply_filter()
- `postgresql_backend.py:2777-2779` - Protection None avant CLUSTER
- `auto_optimizer.py:361-362` - Protection None dans LayerAnalyzer
- `auto_optimizer.py:1085` - Protection None dans \_check_buffer_segments()
- `filter_task.py:8282` - Protection None dans layer_feature_count
- Tests de régression: `tests/regression/test_crit_006_feature_count.py` (12 tests ✓)

**Symptômes observés:**

1. Le 1er et 2ème filtre fonctionnent correctement
2. Au 3ème filtre, TOUTES les couches distantes échouent
3. Erreur: `'<' not supported between instances of 'int' and 'NoneType'`
4. Le filtrage se termine en échec total (0 couches filtrées)

**Logs d'erreur:**

```log
CRITICAL execute_geometric_filtering EXCEPTION for batiment: '<' not supported between instances of 'int' and 'NoneType'
CRITICAL execute_geometric_filtering EXCEPTION for parcelle: '<' not supported between instances of 'int' and 'NoneType'
# ... Répété pour les 6 couches distantes
```

**Cause racine identifiée:**
Lors du 3ème filtre multi-step, une variable `feature_count` devient `None` au lieu d'un entier. Les comparaisons avec des seuils échouent:

```python
# postgresql_backend.py:2755
if feature_count < self.ASYNC_CLUSTER_THRESHOLD:  # TypeError si None

# postgresql_backend.py:1797
feature_count >= self.MATERIALIZED_VIEW_THRESHOLD  # TypeError si None

# auto_optimizer.py:1082
if target.feature_count < self.buffer_segments_threshold:  # TypeError si None
```

**Localisation des comparaisons problématiques:**

| Fichier                 | Ligne | Expression                                              |
| ----------------------- | ----- | ------------------------------------------------------- |
| `postgresql_backend.py` | 2755  | `feature_count < self.ASYNC_CLUSTER_THRESHOLD`          |
| `postgresql_backend.py` | 2760  | `feature_count < self.LARGE_DATASET_THRESHOLD`          |
| `postgresql_backend.py` | 1797  | `feature_count >= self.MATERIALIZED_VIEW_THRESHOLD`     |
| `postgresql_backend.py` | 1807  | `feature_count >= self.MATERIALIZED_VIEW_THRESHOLD`     |
| `postgresql_backend.py` | 1809  | `feature_count >= self.LARGE_DATASET_THRESHOLD`         |
| `filter_task.py`        | 7861  | `layer_feature_count > 100000`                          |
| `auto_optimizer.py`     | 1082  | `target.feature_count < self.buffer_segments_threshold` |

**Source du None:**
La fonction `layer.featureCount()` peut retourner `None` si:

1. La couche devient invalide entre les étapes
2. La connexion PostgreSQL est perdue
3. Le provider ne peut pas compter les features après un filtre complexe

**Fix proposé:**

**Niveau 1: Défense en profondeur - Vérifier None avant chaque comparaison**

```python
# postgresql_backend.py
def _get_fast_feature_count(self, layer: QgsVectorLayer, conn) -> int:
    """Get feature count with None protection."""
    try:
        # ... existing logic ...
        result = layer.featureCount()
        if result is None:
            self.log_warning(f"featureCount() returned None for {layer.name()}")
            return 0  # Fallback to 0 (will use simplest strategy)
        return result
    except Exception as e:
        self.log_warning(f"featureCount() failed: {e}")
        return 0
```

**Niveau 2: Protection avant les comparaisons**

```python
# postgresql_backend.py - _create_optimized_mv()
feature_count = self._get_fast_feature_count(layer, conn) or 0

# Protéger toutes les comparaisons
if self.ENABLE_MV_CLUSTER and feature_count is not None:
    if feature_count < self.ASYNC_CLUSTER_THRESHOLD:
        # synchronous CLUSTER
        pass
    elif self.ENABLE_ASYNC_CLUSTER and feature_count < self.LARGE_DATASET_THRESHOLD:
        # async CLUSTER
        pass
```

**Niveau 3: Protection dans apply_filter()**

```python
# postgresql_backend.py - apply_filter()
feature_count = layer.featureCount()
if feature_count is None or feature_count < 0:
    feature_count = 0
    self.log_warning("Using fallback feature_count=0")
```

**Niveau 4: Protection dans auto_optimizer**

```python
# auto_optimizer.py
def _check_buffer_segments(self, target: LayerAnalysis, ...):
    if target.feature_count is None:
        return None  # Skip optimization if count unknown
    if target.feature_count < self.buffer_segments_threshold:
        return None
```

**Tests de régression à créer:**

```python
def test_multi_step_third_filter_postgresql():
    """Le 3ème filtre multi-step ne doit pas échouer."""
    pass

def test_feature_count_none_handling():
    """Les comparaisons feature_count doivent gérer None."""
    pass

def test_all_distant_layers_filtered_on_third_pass():
    """Toutes les couches distantes doivent être filtrées au 3ème passage."""
    pass
```

---

### CRIT-001: Bug État Buffer Multi-Étapes

**Fichiers:** `spatialite_backend.py`, `ogr_backend.py`  
**Impact:** Résultats de filtrage incorrects  
**Effort:** 2-3 jours

**Problème:**  
Lors de filtres multi-étapes (Filter A → Filter B → Filter C), la valeur du buffer de l'étape **courante** écrase ou ignore l'état du buffer des étapes **précédentes**.

**Localisation:**

- `spatialite_backend.py:3820` - Buffer vient de `task_params` courants
- `ogr_backend.py:734` - Stocke la référence de couche, pas l'expression avec buffer

**Scénario d'échec:**

```
Étape 1: Filter commune avec buffer 100m → Crée table temp avec geom_buffered
Étape 2: Appliquer filtre additionnel (pas de buffer spécifié)
Attendu: Utiliser geom_buffered existant de l'Étape 1
Réel: Utilise colonne geom de base (buffer perdu)
Résultat: FILTRAGE INCORRECT
```

**Fix proposé:**

```python
# Dans filter_task.py
task_params['buffer_state'] = {
    'has_buffer': bool,
    'buffer_value': float,
    'is_applied': bool,  # True si géométrie déjà bufferisée
    'buffer_column': str  # 'geom' ou 'geom_buffered'
}
```

---

### CRIT-002: Risque d'Injection SQL

**Fichiers:** `modules/tasks/progressive_filter.py`, `modules/appUtils.py`  
**Impact:** Sécurité  
**Effort:** 1-2 jours

**Problème:**  
Certaines requêtes SQL construites avec f-strings au lieu de requêtes paramétrées.

**Exemple trouvé:**

```python
# progressive_filter.py:575
cursor.execute(f"SELECT ST_Extent(ST_GeomFromText('{wkt}'))")
```

**Fix proposé:**

```python
cursor.execute("SELECT ST_Extent(ST_GeomFromText(?))", (wkt,))
```

---

### CRIT-003: God Classes (>5000 lignes)

**Fichiers:** 3 fichiers critiques  
**Impact:** Maintenabilité, testabilité  
**Effort:** 2-3 semaines

**Fichiers concernés:**
| Fichier | Lignes | Responsabilités mélangées |
|---------|--------|---------------------------|
| `filter_mate_dockwidget.py` | 12,940 | UI + Logic + State + Events |
| `filter_task.py` | 12,177 | Filtering + Caching + DB ops |
| `filter_mate_app.py` | 5,913 | Orchestration + Config + Tasks |

**Fix proposé:**

- Extraire la logique métier vers des services dédiés
- Créer des modules par domaine (UI, État, Tâches)
- Appliquer le pattern MVC/MVP

---

### ✅ CRIT-004: Thread Safety Non Appliquée - **RÉSOLU v2.3.9**

**Fichier:** `modules/tasks/parallel_executor.py`  
**Impact:** Corruption de données en parallèle  
**Effort:** 2 jours

**✅ Solution implémentée (v2.3.9):**  
Le code détecte automatiquement quand l'exécution parallèle n'est pas thread-safe et bascule en mode séquentiel:

- **OGR layers**: Toujours séquentiel (QGIS layer objects non thread-safe)
- **Shared SQLite databases**: Séquentiel (single-writer limitation)
- **Geometric filtering**: Séquentiel (selectByLocation non thread-safe)
- **Database backends (PostgreSQL/Spatialite)**: Parallèle OK quand pas partagés

Documentation complète au début du fichier avec règles de Thread Safety.

---

## 🟠 HAUTE PRIORITÉ (18 issues)

### HIGH-001: Imports Non Utilisés (25+)

**Fichier:** `filter_mate_dockwidget.py`  
**Lignes:** 31, 47, 68, 83, 128, 129  
**Effort:** 30 min

**Imports à supprimer:**

```python
# Ligne 31
from functools import partial  # Non utilisé

# Ligne 47 - Multiple
QAction, QActionGroup, QApplication, QComboBox, QDockWidget,
QDoubleSpinBox, QFileDialog, QGroupBox, QHBoxLayout, QLineEdit,
QMenu, QPushButton, QSizePolicy, QSpacerItem, QSpinBox,
QSplitter, QToolButton, QVBoxLayout, QWidgetAction

# Ligne 68
Qgis  # Non utilisé

# Ligne 83
QgsCollapsibleGroupBox, QgsDoubleSpinBox, QgsPropertyOverrideButton

# Ligne 128
is_sip_deleted

# Ligne 129
get_datasource_connexion_from_layer, get_primary_key_name,
get_value_relation_info, get_field_display_expression,
get_layer_display_expression, get_fields_with_value_relations,
POSTGRESQL_AVAILABLE
```

---

### HIGH-002: Clauses `except:` Nues

**Fichiers:** `widgets.py`, `parallel_executor.py`  
**Lignes:** 1088, 1102, 473  
**Effort:** 1 heure

**Problème:**

```python
# widgets.py:1088, 1102
except:
    pass  # Avale silencieusement TOUTES les exceptions

# parallel_executor.py:473
except:
    pass
```

**Fix proposé:**

```python
except Exception as e:
    logger.warning(f"Operation failed: {e}")
```

---

### HIGH-003: Imports Non au Top du Fichier

**Fichier:** `filter_mate_dockwidget.py`  
**Lignes:** 37, 38, 46, 47, 68, 83, 122, 124, 125-129  
**Effort:** 1 heure

**Problème:** Les imports sont dispersés après des blocs try/except pour compatibilité QGIS.

**Fix proposé:** Regrouper tous les imports au début avec commentaires explicites:

```python
# Standard library
import os
import sys

# Third-party
from qgis.core import ...

# Local imports (after QGIS availability checks)
from .modules import ...
```

---

### ✅ HIGH-004: Duplication de Code Buffer (80%) - **RÉSOLU v3.0.12**

**Fichiers:** `postgresql_backend.py`, `spatialite_backend.py`, `base_backend.py`  
**Effort:** 5-7 jours → **FAIT**

**✅ Solution implémentée:**  
`_build_st_buffer_with_style()` délègue maintenant à `_build_buffer_expression()` centralisée dans `base_backend.py:400`.

**Implémentation:**

- `postgresql_backend.py:461-481` - Thin wrapper avec `dialect='postgresql'`
- `spatialite_backend.py:373-393` - Thin wrapper avec `dialect='spatialite'`
- `base_backend.py:400-480` - Logique commune centralisée

---

### ✅ HIGH-005: Duplication Transformation CRS Géographique (70%) - **RÉSOLU**

**Fichiers:** `modules/crs_utils.py` (centralisé)  
**Effort:** 3-4 jours → **FAIT**

**✅ Solution implémentée:**  
Module `crs_utils.py` centralise toutes les transformations CRS avec:

- Classe `CRSTransformer` (lignes 344-443)
- Fonction `transform_geometry()` réutilisable
- Pas de duplication dans les backends (vérifié: 0 occurrences de `QgsCoordinateTransform` dans backends/)

---

### HIGH-006: OGR Sans Filtrage Progressif

**Fichier:** `ogr_backend.py`  
**Impact:** Performance -70% sur grands jeux de données  
**Effort:** 7-10 jours (optionnel)

**Comparaison performance (100k features):**
| Backend | Temps | Raison |
|---------|-------|--------|
| PostgreSQL | 2-5s | Two-phase avec index |
| Spatialite | 8-15s | Multi-step avec R-tree |
| **OGR** | **45-90s** | Single-phase processing |

**Fix proposé (court-terme):** Ajouter avertissement utilisateur

```python
if layer.featureCount() > 50000 and backend_name == 'OGR':
    iface.messageBar().pushWarning(
        "FilterMate",
        f"Grand jeu de données ({layer.featureCount():,} entités) avec OGR. "
        "Considérez PostgreSQL ou Spatialite pour de meilleures performances."
    )
```

---

### HIGH-007: Lignes Trop Longues (>79 chars)

**Fichier:** `filter_mate_dockwidget.py`  
**Lignes:** 6, 99, 108, 111, 125  
**Effort:** 30 min

---

### HIGH-008: Variables Globales Multiples

**Fichiers:** Plusieurs modules  
**Impact:** Testabilité, isolation  
**Effort:** 2-3 jours

**Pattern problématique:**

```python
# Utilisé dans plusieurs fichiers
POSTGRESQL_AVAILABLE = ...  # Variable globale d'état
```

**Fix proposé:** Encapsuler dans un singleton ou dependency injection.

---

### ✅ HIGH-009: Exception Handlers Vides - **VÉRIFIÉ OK**

**Fichiers:** `ui_widget_utils.py`, `ui_styles.py`, multiples  
**Lignes:** Multiples (voir grep)  
**Effort:** 2 heures → **NON REQUIS**

**✅ Vérification v3.0.20:**  
Les `except Exception: pass` identifiés sont des **graceful degradations légitimes**:

- `geometry_safety.py:118` - `isGeosValid()` peut échouer mais géométrie utilisable (commenté)
- `ui_styles.py:577` - Déconnexion signal (peut échouer si déjà déconnecté)
- `postgresql_optimizer.py:690` - `DEALLOCATE` peut échouer si statement n'existe pas
- `parallel_executor.py:198,402` - Extraction path/featureCount non critique
- `feedback_utils.py` - Fallback si iface indisponible (commenté)

Ces patterns sont appropriés et ne nécessitent pas de logging supplémentaire.

---

### HIGH-010: Nettoyage Tables Temporaires Incohérent

**Fichier:** `spatialite_backend.py`  
**Effort:** 1-2 jours

**Problème:**

- Cleanup dispersé dans plusieurs méthodes
- Peut laisser des tables orphelines si exception
- Cleanup uniquement à des points spécifiques

**Fix proposé:**

```python
@contextmanager
def temp_table_context(self, db_path, table_name):
    try:
        yield table_name
    finally:
        self._drop_table_if_exists(db_path, table_name)
```

---

### HIGH-011 à HIGH-018: Issues Diverses Haute Priorité

| ID       | Issue                             | Fichier            | Effort                                 |
| -------- | --------------------------------- | ------------------ | -------------------------------------- |
| HIGH-011 | Type hints manquants              | Tous backends      | 3 jours                                |
| HIGH-012 | Docstrings absentes               | Méthodes publiques | 2 jours                                |
| HIGH-013 | Magic numbers hardcodés           | Multiples          | ✅ constants.py                        |
| HIGH-014 | Validation géométrie redondante   | spatialite_backend | ✅ geometry_safety.py                  |
| HIGH-015 | Simplification WKT redondante     | filter_task        | ⚠️ Intentionnel (contextes différents) |
| HIGH-016 | Pas de cache unifié               | Tous backends      | ✅ 6 caches spécialisés                |
| HIGH-017 | Messages d'erreur peu informatifs | Multiples          | ✅ customExceptions.py                 |
| HIGH-018 | Tests multi-step < 10% couverture | tests/             | 3-4 jours                              |

---

## 🟡 MOYENNE PRIORITÉ (42 issues)

### MED-001 à MED-010: Style et Format

| ID      | Issue                               | Fichiers          | Fix                  |
| ------- | ----------------------------------- | ----------------- | -------------------- |
| MED-001 | Mélange f-strings/.format()/%       | Multiples         | ✅ Partiel (2 conv.) |
| MED-002 | Indentation incohérente             | Quelques fichiers | Auto-format          |
| MED-003 | Espaces trailing                    | Multiples         | Strip whitespace     |
| MED-004 | Commentaires obsolètes              | Multiples         | Révision             |
| MED-005 | TODO/FIXME non traités              | Multiples         | Prioriser            |
| MED-006 | Noms de variables peu clairs        | Quelques méthodes | Renommer             |
| MED-007 | Fonctions trop longues (>50 lignes) | Multiples         | Extraire             |
| MED-008 | Complexité cyclomatique élevée      | Quelques méthodes | Simplifier           |
| MED-009 | Imports circulaires potentiels      | Modules           | Restructurer         |
| MED-010 | Fichiers **pycache** dans git       | Racine            | ✅ .gitignore ok     |

### MED-011 à MED-020: Architecture

| ID      | Issue                     | Description     | Effort                                      |
| ------- | ------------------------- | --------------- | ------------------------------------------- |
| MED-011 | Couplage fort UI/Logic    | dockwidget.py   | ⚠️ Partiel (7 controllers, limite atteinte) |
| MED-012 | État global non encapsulé | filter_mate_app | 3 jours                                     |
| MED-013 | Callbacks imbriqués       | Tasks           | 2 jours                                     |
| MED-014 | Signaux Qt mal gérés      | Widgets         | 2 jours                                     |
| MED-015 | Pas de pattern Observer   | État            | 3 jours                                     |
| MED-016 | Factory pattern incomplet | Backends        | ✅ VÉRIFIÉ                                  |
| MED-017 | Configuration éparpillée  | Config          | 2 jours                                     |
| MED-018 | Logging incohérent        | Multiples       | 1 jour                                      |
| MED-019 | Metrics/telemetry absents | -               | 3 jours                                     |
| MED-020 | Health checks manquants   | Backends        | ✅ VÉRIFIÉ                                  |

### MED-021 à MED-030: Performance

| ID      | Issue                    | Impact          | Fix                         |
| ------- | ------------------------ | --------------- | --------------------------- |
| MED-021 | Requêtes N+1             | Lenteur         | Batch queries               |
| MED-022 | Pas de pagination        | Mémoire         | Implement pagination        |
| MED-023 | Cache non invalidé       | Données stales  | ✅ TTL + invalidate_layer() |
| MED-024 | Connexions non poolées   | Overhead        | ✅ connection_pool.py       |
| MED-025 | Lazy loading absent      | Startup lent    | ✅ LazyResultIterator       |
| MED-026 | Index manquants          | Requêtes lentes | ✅ spatial_index_manager.py |
| MED-027 | Sérialisation inefficace | CPU             | Optimize                    |
| MED-028 | Mémoire non libérée      | Leaks           | Explicit cleanup            |
| MED-029 | Profiling absent         | Blind spots     | Add profiling               |
| MED-030 | Benchmarks manquants     | Regression      | Add benchmarks              |

### MED-031 à MED-042: Tests et Documentation

| ID      | Issue                        | Description                                          |
| ------- | ---------------------------- | ---------------------------------------------------- |
| MED-031 | Couverture PostgreSQL ~60%   | ✅ 383 lignes tests (test_postgresql_integration.py) |
| MED-032 | Couverture Spatialite ~50%   | ✅ 401 lignes tests (test_spatialite_integration.py) |
| MED-033 | Couverture OGR ~40%          | ✅ 306 lignes tests (test_ogr_integration.py)        |
| MED-034 | Tests d'intégration absents  | ✅ 6 suites workflows (2426 lignes)                  |
| MED-035 | Tests E2E absents            | ✅ test_e2e_complete_workflow.py (665 lignes)        |
| MED-036 | Mocks incomplets             | Améliorer                                            |
| MED-037 | Fixtures non réutilisables   | ✅ conftest.py dans tests/                           |
| MED-038 | Documentation API incomplète | ✅ api-reference.md (740 lignes)                     |
| MED-039 | Guide utilisateur manquant   | ✅ TUTORIAL_ROAD_FILTERING.md + development-guide.md |
| MED-040 | Changelog non automatisé     | Automatiser                                          |
| MED-041 | README.md à jour?            | ✅ 385 lignes                                        |
| MED-042 | Exemples de code absents     | ✅ TUTORIAL_ROAD_FILTERING.md, api-reference.md      |

---

## 🟢 BASSE PRIORITÉ (25 issues)

### LOW-001 à LOW-010: Cosmétique

| ID      | Issue                            | Fichier               |
| ------- | -------------------------------- | --------------------- | --------------------- |
| LOW-001 | Commentaires en français/anglais | Multiples             | ⚠️ Mineur (auteur FR) |
| LOW-002 | Print statements debug           | Quelques fichiers     |
| LOW-003 | Logging level incorrect          | Modules               | ✅ Vérifié OK         |
| LOW-004 | Constantes mal nommées           | constants.py          | ✅ UPPER_SNAKE_CASE   |
| LOW-005 | Fichiers vides                   | ✅ Tous ont contenu   |
| LOW-006 | Imports alphabétiques            | Tous                  |
| LOW-007 | Docstrings format PEP257         | Méthodes              |
| LOW-008 | Type hints optionnels            | Fonctions utilitaires |
| LOW-009 | Trailing newlines                | Fichiers              |
| LOW-010 | Encoding déclaré                 | Fichiers Python       |

### LOW-011 à LOW-025: Améliorations Futures

| ID      | Issue                         | Description   |
| ------- | ----------------------------- | ------------- |
| LOW-011 | Support Python 3.12           | Compatibilité |
| LOW-012 | Support QGIS 4.x              | Préparation   |
| LOW-013 | Internationalisation complète | i18n          |
| LOW-014 | Thèmes additionnels           | UI            |
| LOW-015 | Export formats additionnels   | Feature       |
| LOW-016 | Plugin API                    | Extensibilité |
| LOW-017 | Raccourcis clavier            | UX            |
| LOW-018 | Tooltips complets             | UX            |
| LOW-019 | Aide contextuelle             | UX            |
| LOW-020 | Mode offline                  | Feature       |
| LOW-021 | Backup automatique            | Feature       |
| LOW-022 | Historique persistant         | Feature       |
| LOW-023 | Favoris cloud sync            | Feature       |
| LOW-024 | Statistiques usage            | Analytics     |
| LOW-025 | A/B testing framework         | Analytics     |

---

## 📋 Plan d'Action Recommandé

### 🚨 Phase 0: Bug Bloquant (IMMÉDIAT - Cette Semaine)

- [x] **CRIT-005**: Fix perte de couche courante après filtre (BLOQUANT) ✅ **v3.0.18**

  - [x] Étendre POST_FILTER_PROTECTION_WINDOW de 2s à 5s
  - [x] Bloquer signaux pendant layer.reload() dans finished()
  - [x] Étendre delayed checks à 5000ms
  - [x] Ajouter protection absolue contre layer=None
  - [ ] Tests de régression pour OGR/Spatialite/PostgreSQL

- [x] **CRIT-006**: Fix TypeError feature_count None ✅ **v3.0.19**

### Phase 1: Corrections Critiques (Semaine 1-2)

- [x] **CRIT-001**: Fix bug état buffer multi-étapes ✅ **v3.0.10** (buffer_state déjà implémenté)
- [x] **CRIT-002**: Corriger injections SQL ✅ **v3.0.20**
- [x] **CRIT-004**: Thread Safety ✅ **v2.3.9** (détection auto + fallback séquentiel)
- [x] **HIGH-001**: Supprimer imports inutilisés ✅ **v3.1.1** (160 imports nettoyés dans 47 fichiers)
- [x] **HIGH-002**: Corriger clauses except nues ✅ **v3.0.20**
- [x] **HIGH-018**: Ajouter tests multi-step ✅ **v3.1.1** (19 tests dans test_buffer_state_multistep.py)

### Phase 2: Qualité de Code (Semaine 3-4)

- [x] **HIGH-004**: Refactorer logique buffer dupliquée ✅ **v3.0.12**
- [x] **HIGH-005**: Standardiser transformation CRS ✅ (centralisé dans crs_utils.py)
- [x] **HIGH-009**: Exception handlers vides ✅ (vérifié OK - graceful degradations)
- [x] **HIGH-011**: Ajouter type hints ✅ **v3.1.1** (89% nouvelle archi, 1439/1605 fonctions)
- [x] **HIGH-017**: Améliorer messages d'erreur ✅ **v3.0.20** (customExceptions.py + feedback_utils.py)
- [x] **MED-001**: Standardiser f-strings ✅ **v3.1.1** (861 f-strings, 4 .format SQL legacy = 99.5%)

### Phase 3: Performance (Semaine 5-6)

- [x] **HIGH-016**: Implémenter cache unifié ✅ (6 caches spécialisés)
- [x] **HIGH-014/15**: Éliminer validations redondantes ✅ geometry_safety.py centralise (v3.0.20)
- [x] **MED-021**: Corriger requêtes N+1 ✅ (batch_size configurable, single-pass iteration)
- [x] **MED-024**: Implémenter connection pooling ✅ (connection_pool.py)

### Phase 4: Refactoring (Semaine 7-8)

- [x] **CRIT-003**: Découper God Classes ⚠️ PARTIEL (7 controllers créés, 6578 lignes, voir SLIM_STRATEGY.md)
- [x] **MED-011**: Séparer UI/Logic ⚠️ PARTIEL (ControllerIntegration avec délégation, limite architecturale atteinte)
- [x] **HIGH-010**: Unifier cleanup tables temp ✅ **v3.0.12** (TemporaryTableManager existe)
- [x] **HIGH-006**: Ajouter warnings OGR (quick fix) ✅ **v3.0.20**

### Phase 5: Tests & Documentation (Semaine 9-10)

- [x] **MED-031-033**: Augmenter couverture tests ✅ (144 fichiers, 46362 lignes, ~70%)
- [x] **MED-034-035**: Ajouter tests intégration/E2E ✅ (6 suites workflows, test_e2e_complete_workflow.py)
- [x] **MED-038-039**: Compléter documentation ✅ (4756 lignes, 10 fichiers docs/)

---

## 🔧 Commandes Utiles

### Linting

```bash
# Check all Python files
flake8 --max-line-length=120 --exclude=__pycache__,i18n,.git

# Auto-fix avec black
black --line-length=120 .

# Check types
mypy modules/ --ignore-missing-imports
```

### Tests

```bash
# Run all tests
pytest tests/ -v

# Coverage report
pytest tests/ --cov=modules --cov-report=html

# Only failed tests
pytest tests/ --lf
```

### Recherche Issues

```bash
# Trouver tous les TODO/FIXME
grep -rn "TODO\|FIXME\|HACK\|XXX" --include="*.py" .

# Trouver except nus
grep -rn "except:" --include="*.py" .

# Compter lignes par fichier
wc -l *.py modules/*.py modules/**/*.py | sort -n
```

---

## 📊 Métriques Actuelles vs Cibles (mise à jour v3.0.20)

| Métrique           | Actuel | Cible | Gap  | Notes                        |
| ------------------ | ------ | ----- | ---- | ---------------------------- |
| Couverture Tests   | ~50%   | 80%   | -30% |                              |
| Lignes max/fichier | 12,940 | 500   | 🔴   | CRIT-003 (God Classes)       |
| Imports inutilisés | 25+    | 0     | 🟠   | HIGH-001 (risqué sans tests) |
| Exceptions nues    | 0      | 0     | ✅   | HIGH-002 corrigé v3.0.20     |
| Type hints         | ~30%   | 80%   | -50% |                              |
| Docstrings         | ~40%   | 90%   | -50% |                              |
| Code dupliqué      | ~5%    | <5%   | ✅   | HIGH-004/005 centralisés     |

---

## 📝 Notes

### Points Positifs Observés ✅

- Architecture backend avec Factory pattern complet (MED-016 ✅)
- Thread safety avec main_thread_executor
- Module object_safety pour éviter violations C++
- Circuit Breaker pour connexions PostgreSQL
- Connection Pooling avec health checks (MED-020, MED-024 ✅)
- Implémentation de caching (géométrie, requêtes)
- Compatibilité QGIS multi-versions
- Commentaires de version (FIX v2.5.12:)
- Buffer logic centralisée (HIGH-004 ✅ v3.0.12)
- CRS transformations centralisées dans crs_utils.py (HIGH-005 ✅)
- SQL injection fix (CRIT-002 ✅ v3.0.20)
- Graceful degradation patterns validés (HIGH-009 ✅)

### Risques Identifiés ⚠️

1. ~~**Bug multi-step buffer**~~ ✅ Corrigé v3.0.10 (buffer_state)
2. ~~**Code dupliqué**~~ ✅ Centralisé (base_backend.py, crs_utils.py)
3. **Performance OGR** peut causer lenteurs sur grands datasets (warning ajouté v3.0.20)
4. **God Classes** rendent le refactoring difficile (CRIT-003 planifié)

---

**Dernière mise à jour:** 2026-01-08 (v3.0.20)  
**Auteur:** BMAD Master Agent + Dev Agent  
**Prochaine révision:** Phase de refactoring CRIT-003
