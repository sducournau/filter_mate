# FilterMate - Component Inventory

Inventaire complet des composants et modules de FilterMate v2.9.12.

## 📦 Modules Principaux

### Core Application

| Fichier | Lignes | Description | Dépendances Clés |
|---------|--------|-------------|------------------|
| **filter_mate.py** | 1,228 | Point d'entrée plugin QGIS | QgsInterface, QTranslator |
| **filter_mate_app.py** | 5,343 | Orchestrateur principal | Tous les modules |
| **filter_mate_dockwidget.py** | ~800 | Interface utilisateur (DockWidget) | PyQt5, QgsMapLayerComboBox |
| **filter_mate_dockwidget_base.py** | Auto | Classe UI générée (compile_ui.sh) | PyQt5 |

**Responsabilités :**
- Intégration QGIS (menus, toolbar, signaux)
- Coordination application (état, tâches, configuration)
- Interface utilisateur (widgets, thèmes, événements)

---

## 🔧 Modules Backend (modules/backends/)

### Factory Pattern

| Fichier | Lignes | Description |
|---------|--------|-------------|
| **factory.py** | 734 | Sélection backend optimal + cache |
| **base_backend.py** | ~200 | Interface abstraite GeometricFilterBackend |

### Backends Spécialisés

| Backend | Fichier | Lignes | Stratégie d'Optimisation |
|---------|---------|--------|--------------------------|
| **PostgreSQL** | postgresql_backend.py | 3,319 | MV + GIST, connection pooling, two-phase filter |
| **Spatialite** | spatialite_backend.py | 4,213 | WKT cache, R-tree, interruptible queries |
| **OGR** | ogr_backend.py | 3,034 | Processing algorithms, spatial index auto |
| **Memory** | memory_backend.py | ~500 | In-memory, pour small datasets |

### Modules Support Backend

| Fichier | Description |
|---------|-------------|
| **auto_optimizer.py** | Détection automatique stratégie optimale |
| **multi_step_optimizer.py** | Filtrage multi-étapes (attribut → spatial) |
| **mv_registry.py** | Registry Materialized Views PostgreSQL |
| **optimizer_metrics.py** | Métriques performance optimisations |
| **parallel_processor.py** | Exécution parallèle multi-couches |
| **postgresql_buffer_optimizer.py** | Optimisation buffers PostGIS |
| **spatial_index_manager.py** | Gestion index spatiaux automatiques |
| **spatialite_cache.py** | Cache FIDs pour filtrage multi-étapes |
| **wkt_cache.py** | Cache WKT géométries source |

**Total Backend Layer :** ~12,000 lignes

---

## ⚙️ Modules Tâches (modules/tasks/)

### Tâches Asynchrones (QgsTask)

| Fichier | Lignes | Description |
|---------|--------|-------------|
| **filter_task.py** | 11,804 | Tâche filtrage principale (source + remote layers) |
| **layer_management_task.py** | ~800 | Gestion multi-couches (refresh, cleanup) |
| **expression_evaluation_task.py** | ~600 | Évaluation expressions complexes |

### Optimisations Tâches

| Fichier | Description |
|---------|-------------|
| **combined_query_optimizer.py** | Combinaison requêtes multiples |
| **geometry_cache.py** | Cache géométries transformées |
| **multi_step_filter.py** | Filtrage progressif (selectivity-based) |
| **parallel_executor.py** | Exécution parallèle safe |
| **progressive_filter.py** | Filtrage progressif/lazy loading |
| **query_cache.py** | Cache résultats requêtes |
| **query_complexity_estimator.py** | Estimation complexité requêtes |
| **result_streaming.py** | Streaming résultats grands datasets |
| **task_utils.py** | Utilitaires communs tâches |

**Total Task Layer :** ~15,000 lignes

---

## 🛠️ Modules Utilitaires (modules/)

### Core Utilities

| Fichier | Lignes | Description | Fonctions Clés |
|---------|--------|-------------|----------------|
| **appUtils.py** | 1,839 | DB connections, provider detection | `get_datasource_connexion_from_layer`, `detect_layer_provider_type`, `get_primary_key_name` |
| **constants.py** | ~300 | Constantes globales | `PROVIDER_POSTGRES`, `PREDICATE_INTERSECTS`, thresholds |
| **customExceptions.py** | ~150 | Exceptions personnalisées | `FilterMateException`, `LayerNotFoundError` |

### Stabilité et Sécurité

| Fichier | Lignes | Description |
|---------|--------|-------------|
| **object_safety.py** | ~800 | Validation objets Qt/QGIS, decorators | `is_sip_deleted`, `is_valid_layer`, `@require_valid_layer` |
| **geometry_safety.py** | ~600 | Validation géométries GEOS-safe | `validate_geometry`, `safe_collect_geometry` |
| **circuit_breaker.py** | ~400 | Protection échecs répétés PostgreSQL | `CircuitBreaker`, `CircuitState` |

### Configuration

| Fichier | Lignes | Description |
|---------|--------|-------------|
| **config_helpers.py** | ~300 | Helpers configuration | `get_optimization_thresholds` |
| **config_metadata.py** | ~500 | Metadata schema configuration |
| **config_metadata_handler.py** | ~400 | Handler metadata |
| **config_migration.py** | ~600 | Migration config v1 → v2 |

### UI et Widgets

| Fichier | Lignes | Description |
|---------|--------|-------------|
| **ui_config.py** | 1,087 | Configuration UI (dimensions, thèmes) | `UIConfig`, `DisplayProfile` |
| **ui_styles.py** | ~800 | Styles Qt (dark/light mode) | `detect_qgis_theme`, `get_*_stylesheet` |
| **ui_elements.py** | ~600 | Éléments UI personnalisés |
| **ui_elements_helpers.py** | ~400 | Helpers UI |
| **ui_widget_utils.py** | ~300 | Utilitaires widgets |
| **widgets.py** | ~1,200 | Widgets personnalisés |

### État et Persistance

| Fichier | Lignes | Description |
|---------|--------|-------------|
| **filter_history.py** | 599 | Gestion undo/redo | `FilterHistory`, `FilterState` |
| **filter_favorites.py** | 854 | Gestion favoris SQLite | `FavoritesManager`, `FilterFavorite` |
| **state_manager.py** | ~400 | Gestion état global application |
| **exploring_cache.py** | ~300 | Cache exploration couches |

### Performance et Logging

| Fichier | Lignes | Description |
|---------|--------|-------------|
| **connection_pool.py** | ~600 | Pool connexions PostgreSQL | `ConnectionPoolManager` |
| **prepared_statements.py** | ~400 | Prepared statements PostgreSQL |
| **postgresql_optimizer.py** | ~500 | Optimiseur requêtes PostgreSQL |
| **logging_config.py** | ~400 | Configuration logging rotation | `get_logger`, `SafeStreamHandler` |

### Autres Utilitaires

| Fichier | Description |
|---------|-------------|
| **psycopg2_availability.py** | Détection psycopg2 centralisée |
| **crs_utils.py** | Utilitaires CRS/projections |
| **type_utils.py** | Conversion types |
| **icon_utils.py** | Gestion icônes |
| **flag_manager.py** | Gestion flags application |
| **signal_utils.py** | Utilitaires signaux Qt |
| **feedback_utils.py** | Messages utilisateur centralisés |

### Widgets Spécialisés

| Fichier | Description |
|---------|-------------|
| **backend_optimization_widget.py** | Widget config optimisations backend |
| **config_editor_widget.py** | Éditeur configuration visuel |
| **optimization_dialogs.py** | Dialogues optimisations |
| **qt_json_view/** | Viewer JSON Qt (4 fichiers) |

**Total Utilities :** ~15,000 lignes

---

## ⚙️ Configuration (config/)

| Fichier | Description |
|---------|-------------|
| **config.py** | Initialisation configuration, `ENV_VARS` |
| **config.json** | Configuration utilisateur actuelle |
| **config.default.json** | Configuration par défaut |
| **config_schema.json** | Schema JSON validation |
| **config.v2.example.json** | Exemple config v2.0 |
| **feedback_config.py** | Config niveaux feedback |
| **README_CONFIG.md** | Documentation configuration |
| **backups/** | Sauvegardes auto config |

---

## 🌍 Internationalisation (i18n/)

**21 langues supportées :**
- Fichiers `.ts` (source XML)
- Fichiers `.qm` (compilés pour Qt)

| Code | Langue | Code | Langue |
|------|--------|------|--------|
| am | Amharique | ko | Coréen |
| da | Danois | nl | Néerlandais |
| de | Allemand | no | Norvégien |
| en | Anglais | pl | Polonais |
| es | Espagnol | pt | Portugais |
| fi | Finnois | ru | Russe |
| fr | Français | sv | Suédois |
| hi | Hindi | tr | Turc |
| id | Indonésien | zh_CN | Chinois simplifié |
| it | Italien | zh_TW | Chinois traditionnel |
| ja | Japonais | | |

**Total :** 42 fichiers (21 × 2 formats)

---

## 🎨 Ressources (resources/)

| Type | Description |
|------|-------------|
| **icons/** | Icônes SVG/PNG (40+ fichiers) |
| **resources.qrc** | Qt Resource Collection |
| **resources.py** | Ressources compilées Python |

---

## 📚 Documentation (docs/)

### Guides Utilisateur
- **TUTORIAL_ROAD_FILTERING.md** - Tutorial filtrage routes

### Documentation Technique

| Fichier | Description |
|---------|-------------|
| **project-overview.md** | Vue d'ensemble projet |
| **architecture.md** | Architecture complète |
| **component-inventory.md** | Inventaire composants (ce fichier) |
| **development-guide.md** | Guide développeur |
| **source-tree-analysis.md** | Arborescence annotée |
| **index.md** | Index maître |

### Notes de Version
- **RELEASE_NOTES_v2.5.3.md** → **v2.5.7.md**
- **CHANGELOG.md** (racine)

### Documentation Fixes

| Pattern | Description | Nombre |
|---------|-------------|--------|
| **FIX_*.md** | Documentation correctifs critiques | 15+ |
| **ENHANCED_*.md** | Améliorations optimisations | 3 |
| **SYNC_*.md** | Synchronisation architecture | 1 |

**Exemples :**
- `FIX_OGR_SOURCE_LAYER_GC_2026-01.md` - Garbage collection OGR
- `FIX_NEGATIVE_BUFFER_SPATIALITE_2026-01.md` - Buffers négatifs
- `FIX_SPATIALITE_FREEZE_2026-01.md` - Freeze Spatialite
- `ENHANCED_OPTIMIZATION_v2.8.0.md` - Optimisations v2.8

### Rapports et Plans
- **project-scan-report.json** - Rapport scan automatique
- **TRANSLATION_PLAN_2025-12.md** - Plan traductions
- **TRANSLATION_UPDATE_PLAN_v2.8.9.md** - Mise à jour traductions

---

## 🧪 Tests (tests/)

| Type | Description |
|------|-------------|
| **test_*.py** | Tests unitaires pytest |
| **requirements-test.txt** | Dépendances tests |
| **setup_tests.sh/.bat** | Scripts setup tests |

**Coverage actuel :** ~70%  
**Objectif :** 80%

---

## 🔧 Outils (tools/)

Scripts utilitaires pour développement et maintenance.

---

## 🌐 Website (website/)

Documentation site web statique (GitHub Pages).

---

## 📊 Statistiques Globales

### Par Catégorie

| Catégorie | Fichiers | Lignes de Code (estimé) |
|-----------|----------|-------------------------|
| **Core Application** | 4 | ~7,400 |
| **Backend Layer** | 18 | ~12,000 |
| **Task Layer** | 14 | ~15,000 |
| **Utilities** | 30+ | ~15,000 |
| **Configuration** | 8 | ~1,500 |
| **UI/Widgets** | 12 | ~6,000 |
| **Tests** | 10+ | ~2,000 |
| **Documentation** | 30+ | N/A |
| **Traductions** | 42 | N/A |
| **TOTAL** | **~170 fichiers** | **~60,000 lignes** |

### Top 10 Fichiers par Taille

| Rang | Fichier | Lignes | Catégorie |
|------|---------|--------|-----------|
| 1 | filter_task.py | 11,804 | Tasks |
| 2 | filter_mate_app.py | 5,343 | Core |
| 3 | spatialite_backend.py | 4,213 | Backend |
| 4 | postgresql_backend.py | 3,319 | Backend |
| 5 | ogr_backend.py | 3,034 | Backend |
| 6 | appUtils.py | 1,839 | Utilities |
| 7 | filter_mate.py | 1,228 | Core |
| 8 | widgets.py | 1,200 | UI |
| 9 | ui_config.py | 1,087 | UI |
| 10 | filter_favorites.py | 854 | Utilities |

### Dépendances Externes

| Package | Usage | Obligatoire |
|---------|-------|-------------|
| **QGIS API** | Framework principal | ✅ Oui |
| **PyQt5** | Interface utilisateur | ✅ Oui |
| **psycopg2** | PostgreSQL support | ❌ Non (fallback OGR) |
| **sqlite3** | Spatialite, favoris | ✅ Oui (Python stdlib) |
| **osgeo (GDAL/OGR)** | Formats vectoriels | ✅ Oui (via QGIS) |
| **pytest** | Tests | ❌ Non (dev only) |

---

## 🔍 Index des Fonctions Clés

### Backend Selection
```python
# modules/backends/factory.py
BackendFactory.get_backend(layer, provider_type, task_params)
should_use_memory_optimization(layer, provider_type)
```

### Database Operations
```python
# modules/appUtils.py
get_datasource_connexion_from_layer(layer)
detect_layer_provider_type(layer)
get_primary_key_name(layer)
safe_set_subset_string(layer, expression)
```

### Task Management
```python
# modules/tasks/filter_task.py
FilterEngineTask(description, task_parameters)
FilterEngineTask.run()
FilterEngineTask.finished(result)
```

### History Management
```python
# modules/filter_history.py
HistoryManager.push_state(expression, count, description)
HistoryManager.undo()
HistoryManager.redo()
```

### Favorites Management
```python
# modules/filter_favorites.py
FavoritesManager.save_favorite(favorite, project_id)
FavoritesManager.load_favorites(project_id)
FavoritesManager.search_favorites(query, tags)
```

### UI Configuration
```python
# modules/ui_config.py
UIConfig.get_button_config()
UIConfig.get_active_theme()
UIConfig.set_display_profile(profile)
```

### Safety Utilities
```python
# modules/object_safety.py
is_valid_layer(layer)
is_sip_deleted(qobject)
@require_valid_layer  # Decorator
safe_disconnect(signal, slot)
```

---

## 🔗 Navigation

- **[Retour Overview](project-overview.md)**
- **[Architecture Détaillée](architecture.md)**
- **[Guide Développement](development-guide.md)**
- **[Arborescence Source](source-tree-analysis.md)**
- **[Index Principal](index.md)**

---

**Dernière mise à jour :** 6 janvier 2026  
**Version :** 2.9.12
