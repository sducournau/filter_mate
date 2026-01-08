# FilterMate - Architecture

Ce document décrit l'architecture complète de FilterMate v2.9.12.

> **🚀 Note de Refonte v3.0** : Un document d'architecture de refonte a été créé pour la transition vers FilterMate v3.0.
> Voir : [`_bmad-output/planning-artifacts/architecture-refactoring-v3.md`](../_bmad-output/planning-artifacts/architecture-refactoring-v3.md)
>
> Objectifs v3.0 : Éliminer les god classes, réduire les duplications, améliorer la testabilité.

## 📐 Vue d'Ensemble

FilterMate utilise une architecture multi-couches avec séparation des responsabilités :

```
┌──────────────────────────────────────────────────────────────┐
│                    QGIS Plugin Layer                          │
│  filter_mate.py (Entry Point) → filter_mate_app.py (Core)    │
└───────────────────────┬──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│                    Application Layer                          │
│  - FilterMateApp (orchestrateur principal)                    │
│  - filter_mate_dockwidget.py (UI PyQt5)                      │
│  - UIConfig (thèmes, dimensions, dark mode)                   │
└───────────────────────┬──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│                    Business Logic Layer                       │
│  - HistoryManager (undo/redo)                                │
│  - FavoritesManager (sauvegarde configurations)              │
│  - BackendFactory (sélection backend optimal)                │
└───────────────────────┬──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│                    Backend Layer (Factory Pattern)            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │PostgreSQL│  │Spatialite│  │   OGR    │  │  Memory  │    │
│  │ Backend  │  │ Backend  │  │ Backend  │  │ Backend  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
└───────────────────────┬──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│                    Task Layer (QgsTask)                       │
│  - FilterEngineTask (filtrage principal)                     │
│  - LayersManagementEngineTask (multi-couches)                │
│  - ExpressionEvaluationTask (évaluation expressions)         │
└───────────────────────┬──────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────┐
│                    Data Access Layer                          │
│  - appUtils.py (connexions DB, détection providers)          │
│  - connection_pool.py (pool PostgreSQL)                      │
│  - psycopg2_availability.py (détection psycopg2)             │
└──────────────────────────────────────────────────────────────┘
```

## 🎯 Points d'Entrée

### 1. Initialisation Plugin (filter_mate.py)

```python
class FilterMate:
    """Point d'entrée QGIS Plugin."""

    def __init__(self, iface):
        self.iface = iface
        self.app = False  # Instance de FilterMateApp

    def initGui(self):
        """Initialise l'interface utilisateur."""
        # Crée les actions, menus, toolbar
        # Configure les signaux auto-activation

    def run(self):
        """Lance l'application principale."""
        if not self.app:
            self.app = FilterMateApp(self.iface, self.dockwidget)
        # Active le dockwidget
```

**Responsabilités :**

- Intégration avec QGIS (menus, toolbar, signaux)
- Gestion du cycle de vie du plugin
- Auto-activation basée sur configuration
- Gestion de la traduction (i18n)

### 2. Orchestrateur Principal (filter_mate_app.py)

```python
class FilterMateApp:
    """
    Orchestrateur central de FilterMate.

    Coordonne tous les composants :
    - UI (dockwidget)
    - Backend selection
    - Task management
    - History/Favorites
    - Configuration
    """

    def __init__(self, iface, dockwidget):
        self.iface = iface
        self.dockwidget = dockwidget

        # Gestionnaires principaux
        self.history_manager = None
        self.favorites_manager = FavoritesManager()
        self.ui_config = UIConfig()

        # État de l'application
        self.current_task = None
        self.backend_factory = BackendFactory()
```

**Responsabilités :**

- Coordination entre UI et logique métier
- Gestion des tâches asynchrones
- Gestion de l'état de l'application
- Configuration et préférences utilisateur
- Feedback utilisateur (message bar)

## 🏗️ Composants Principaux

### Architecture Multi-Backend (Pattern Factory)

Le **BackendFactory** sélectionne le backend optimal selon plusieurs critères :

```python
# modules/backends/factory.py

def get_backend(
    layer: QgsVectorLayer,
    layer_provider_type: str,
    task_params: Dict
) -> GeometricFilterBackend:
    """
    Sélectionne et retourne le backend optimal.

    Logique de sélection :
    1. Small dataset optimization (PostgreSQL → Memory si < seuil)
    2. Provider type matching (postgres → PostgreSQLBackend)
    3. Fallback to OGR for unknown providers
    """

    # Optimization: small PostgreSQL datasets → Memory backend
    if should_use_memory_optimization(layer, layer_provider_type):
        return MemoryGeometricFilter(layer, task_params)

    # Backend mapping
    backends = {
        PROVIDER_POSTGRES: PostgreSQLGeometricFilter,
        PROVIDER_SPATIALITE: SpatialiteGeometricFilter,
        PROVIDER_OGR: OGRGeometricFilter,
        PROVIDER_MEMORY: MemoryGeometricFilter
    }

    backend_class = backends.get(layer_provider_type, OGRGeometricFilter)
    return backend_class(layer, task_params)
```

#### Backend Base Class

```python
# modules/backends/base_backend.py

class GeometricFilterBackend(ABC):
    """Interface commune pour tous les backends."""

    @abstractmethod
    def apply_geometric_filter(
        self,
        predicate: str,
        source_geometry_wkt: str,
        buffer_distance: float,
        buffer_unit: int,
        **kwargs
    ) -> Tuple[bool, str, int]:
        """
        Applique un filtre géométrique.

        Returns:
            Tuple[success, expression, feature_count]
        """
        pass
```

#### Backends Spécialisés

**1. PostgreSQL Backend** (optimal pour >100k features)

```python
# modules/backends/postgresql_backend.py

class PostgreSQLGeometricFilter(GeometricFilterBackend):
    """
    Backend PostgreSQL/PostGIS.

    Stratégies d'optimisation :
    - Petits datasets (< 10k): setSubsetString direct
    - Grands datasets (≥ 10k): Materialized Views + GIST index
    - Custom buffers: Toujours Materialized Views

    Performance:
    - Connection pooling (~50-100ms gain)
    - Server-side cursors pour streaming
    - Two-phase filtering (3-10x plus rapide)
    - Progressive/lazy loading (50-80% moins de mémoire)
    """

    def apply_geometric_filter(self, ...):
        # 1. Détermine la stratégie (simple/MV)
        # 2. Crée MV si nécessaire avec index GIST
        # 3. Applique le filtre via setSubsetString
        # 4. Enregistre dans MV Registry pour cleanup
```

**2. Spatialite Backend** (bon pour <100k features)

```python
# modules/backends/spatialite_backend.py

class SpatialiteGeometricFilter(GeometricFilterBackend):
    """
    Backend Spatialite/GeoPackage.

    Optimisations :
    - WKT caching pour réutilisation
    - R-tree index automatique
    - Direct SQL pour GeoPackage (prioritaire)
    - Interruptible queries (évite freeze)
    - Bounding box pre-filter pour WKT >500KB

    Compatibilité :
    - 90% des fonctions PostGIS supportées
    - Fallback FID-based pour formats restrictifs
    """

    def apply_geometric_filter(self, ...):
        # 1. Détecte si remote/distant (évite erreurs)
        # 2. Tente Direct SQL (prioritaire GeoPackage)
        # 3. Fallback setSubsetString si supporté
        # 4. Fallback FID-based si restrictions
```

**3. OGR Backend** (fallback universel)

```python
# modules/backends/ogr_backend.py

class OGRGeometricFilter(GeometricFilterBackend):
    """
    Backend OGR (Shapefile, GeoJSON, etc.).

    Utilise QGIS processing algorithms car OGR
    ne supporte pas les expressions SQL complexes.

    Thread Safety :
    - Opérations séquentielles (pas de parallèle)
    - Direct data provider calls (évite signaux)
    - GdalErrorHandler pour warnings SQLite

    Optimisations :
    - Création index spatial automatique
    - Détection et gestion index existants
    """

    def apply_geometric_filter(self, ...):
        # 1. Valide géométrie (GEOS safe)
        # 2. Utilise processing.run() avec feedback
        # 3. Gère les GeometryCollections
        # 4. Crée index spatial si absent
```

**4. Memory Backend** (petits datasets)

```python
# modules/backends/memory_backend.py

class MemoryGeometricFilter(GeometricFilterBackend):
    """
    Backend mémoire pour optimisation small datasets.

    Utilisé automatiquement pour PostgreSQL < seuil.
    Charge toutes les features en mémoire.
    """
```

### Système de Tâches Asynchrones (QgsTask)

Toutes les opérations bloquantes utilisent **QgsTask** pour ne pas figer l'interface.

```python
# modules/tasks/filter_task.py

class FilterEngineTask(QgsTask):
    """
    Tâche principale de filtrage.

    Workflow :
    1. Préparation (détection provider, sélection backend)
    2. Filtrage source layer (attribut + géométrie)
    3. Filtrage remote layers (multi-couches spatiales)
    4. Export (optionnel)
    5. History update
    """

    def __init__(self, description, task_parameters):
        super().__init__(description, QgsTask.CanCancel)
        self.task_parameters = task_parameters
        self.result_data = None

    def run(self):
        """
        Exécuté dans un thread séparé.

        Returns:
            bool: True si succès, False si échec
        """
        try:
            # 1. Détecte provider type
            provider_type = detect_layer_provider_type(layer)

            # 2. Obtient backend optimal
            backend = BackendFactory.get_backend(
                layer, provider_type, self.task_parameters
            )

            # 3. Applique filtre attribut (si présent)
            if attribute_expression:
                safe_set_subset_string(layer, attribute_expression)

            # 4. Applique filtre géométrique (si présent)
            if source_geometry_wkt:
                success, expr, count = backend.apply_geometric_filter(
                    predicate, source_geometry_wkt, buffer_distance, ...
                )

            # 5. Filtre remote layers (multi-couches)
            if remote_layers:
                for remote_layer in remote_layers:
                    # Applique même logique backend
                    pass

            # 6. Export (optionnel)
            if export_params:
                self._export_layer(...)

            return True

        except Exception as e:
            self.exception = e
            return False

    def finished(self, result):
        """
        Exécuté dans le thread principal après run().

        Gère l'UI et les notifications utilisateur.
        """
        if result:
            # Succès : mise à jour UI, history, message bar
            if self.task_parameters.get('update_history', True):
                history_manager.push_state(expression, count, description)

            show_success_with_backend("Filter applied", backend_type)
        else:
            # Échec : affiche erreur
            show_error_with_context("Filter failed", str(self.exception))
```

**Autres tâches disponibles :**

```python
# modules/tasks/layer_management_task.py
class LayersManagementEngineTask(QgsTask):
    """Gestion multi-couches (refresh, cleanup)."""

# modules/tasks/expression_evaluation_task.py
class ExpressionEvaluationTask(QgsTask):
    """Évaluation d'expressions complexes."""
```

### Gestion de l'Historique (Undo/Redo)

```python
# modules/filter_history.py

class FilterHistory:
    """
    Gestion undo/redo pour filtres.

    Stack linéaire : appliquer un nouveau filtre efface les états "futurs".
    Limite configurable (défaut: 100 états).
    Persistant via layer variables.
    """

    def __init__(self, layer_id: str, max_size: int = 100):
        self._states: List[FilterState] = []
        self._current_index = -1
        self._is_undoing = False

    def push_state(self, expression, feature_count, description, metadata):
        """Ajoute un état à l'historique."""
        # Crée FilterState
        # Efface états futurs si pas à la fin
        # Applique max_size

    def undo(self) -> Optional[FilterState]:
        """Retour en arrière d'un état."""
        if not self.can_undo():
            return None

        self._current_index -= 1
        self._is_undoing = True
        state = self._states[self._current_index]
        # Applique le filtre
        self._is_undoing = False
        return state

    def redo(self) -> Optional[FilterState]:
        """Avance d'un état."""
        # Logique inverse de undo()
```

**Integration dans FilterMateApp :**

```python
# Shortcuts clavier
QShortcut(QKeySequence("Ctrl+Z"), self.dockwidget, self.undo_filter)
QShortcut(QKeySequence("Ctrl+Y"), self.dockwidget, self.redo_filter)
```

### Gestion des Favoris

```python
# modules/filter_favorites.py

@dataclass
class FilterFavorite:
    """Représente un favori sauvegardé."""
    id: str
    name: str
    expression: str
    layer_name: Optional[str]
    spatial_config: Optional[Dict]
    remote_layers: Optional[Dict]
    created_at: str
    last_used: str
    use_count: int
    tags: List[str]
    description: str

class FavoritesManager:
    """
    Gestion des favoris avec persistance SQLite.

    Base de données : filtermate.db dans CONFIG_DIRECTORY
    Tables :
    - favorites: favoris globaux
    - project_favorites: favoris par projet
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()

    def save_favorite(self, favorite: FilterFavorite, project_id: str):
        """Sauvegarde un favori."""
        # INSERT INTO project_favorites

    def load_favorites(self, project_id: str) -> List[FilterFavorite]:
        """Charge les favoris du projet."""
        # SELECT FROM project_favorites WHERE project_id = ?

    def search_favorites(self, query: str, tags: List[str]) -> List:
        """Recherche par nom/tags."""
```

### Configuration Système (v2.0)

```python
# config/config.py

ENV_VARS = {}  # Configuration globale chargée

def init_env_vars():
    """
    Initialise la configuration.

    1. Lit config.json depuis CONFIG_DIRECTORY
    2. Merge avec config.default.json
    3. Migration automatique si obsolète
    4. Fallback vers FALLBACK_CONFIG si échec
    """

FALLBACK_CONFIG = {
    "_CONFIG_VERSION": "2.0",
    "APP": {
        "AUTO_ACTIVATE": {"value": False},
        "DOCKWIDGET": {
            "FEEDBACK_LEVEL": {"value": "normal"},
            "LANGUAGE": {"value": "auto"},
            "THEME": {"value": "auto"}
        }
    }
}
```

**Configuration Metadata :**

```python
# modules/config_metadata.py

CONFIG_SCHEMA = {
    "APP.DOCKWIDGET.THEME": {
        "type": "string",
        "choices": ["auto", "light", "dark"],
        "description": "UI theme",
        "category": "Appearance"
    }
}
```

### Interface Utilisateur (PyQt5)

```python
# modules/ui_config.py

class DisplayProfile(Enum):
    COMPACT = "compact"
    NORMAL = "normal"
    HIDPI = "hidpi"

class UIConfig:
    """
    Configuration UI centralisée.

    Gère :
    - Dimensions (boutons, frames, combobox)
    - Espacement et padding
    - Profils d'affichage (compact/normal)
    - Thèmes (light/dark, auto-détection)
    """

    _active_profile = DisplayProfile.COMPACT

    PROFILES = {
        "compact": {
            "button": {"height": 48, "icon_size": 27},
            "action_button": {"height": 32, "icon_size": 20},
            "frame": {"min_height": 35},
            "splitter": {"handle_width": 4}
        },
        "normal": {
            # Dimensions plus grandes
        }
    }

    @classmethod
    def get_button_config(cls) -> Dict:
        """Retourne config bouton actuelle."""
        return cls.PROFILES[cls._active_profile.value]["button"]
```

**Dark Mode Auto-Detection :**

```python
# modules/ui_styles.py

def detect_qgis_theme() -> str:
    """
    Détecte le thème QGIS actuel.

    Returns:
        'dark' ou 'light'
    """
    app = QApplication.instance()
    palette = app.palette()
    bg_color = palette.color(QPalette.Window)

    # Luminosité < 128 = dark
    luminance = 0.299 * bg_color.red() + 0.587 * bg_color.green() + 0.114 * bg_color.blue()
    return 'dark' if luminance < 128 else 'light'
```

### Utilitaires et Services

```python
# modules/appUtils.py

# Détection PostgreSQL
from modules.psycopg2_availability import POSTGRESQL_AVAILABLE

def get_datasource_connexion_from_layer(layer):
    """
    Obtient connexion PostgreSQL pour une couche.

    Returns:
        Tuple[connection, uri] ou (None, None)
    """
    if not POSTGRESQL_AVAILABLE:
        return None, None

    uri = QgsDataSourceUri(layer.source())
    conn = psycopg2.connect(
        host=uri.host(),
        port=uri.port(),
        dbname=uri.database(),
        user=uri.username(),
        password=uri.password()
    )
    return conn, uri

def detect_layer_provider_type(layer) -> str:
    """
    Détecte le type de provider.

    Returns:
        'postgresql', 'spatialite', 'ogr', 'memory', 'unknown'
    """
    provider = layer.providerType()

    if provider == 'postgres':
        return PROVIDER_POSTGRES
    elif provider == 'spatialite':
        return PROVIDER_SPATIALITE
    elif provider == 'ogr':
        return PROVIDER_OGR
    elif provider == 'memory':
        return PROVIDER_MEMORY
    else:
        return 'unknown'
```

**Connection Pooling (PostgreSQL) :**

```python
# modules/connection_pool.py

class ConnectionPoolManager:
    """
    Pool de connexions PostgreSQL.

    Évite overhead de ~50-100ms par requête.
    Gère le cycle de vie des connexions.
    """

    def get_connection(self, uri: QgsDataSourceUri):
        """Obtient connexion du pool ou en crée une."""
```

## 🔒 Thread Safety et Stabilité

### Object Safety (v2.3.9+)

```python
# modules/object_safety.py

def is_sip_deleted(qobject) -> bool:
    """Vérifie si l'objet Qt a été détruit par C++."""
    try:
        sip.isdeleted(qobject)
        return False
    except RuntimeError:
        return True

def is_valid_layer(layer) -> bool:
    """Vérifie validité complète d'une couche."""
    return (
        layer is not None and
        not is_sip_deleted(layer) and
        layer.isValid()
    )

@require_valid_layer
def safe_function(layer: QgsVectorLayer):
    """Décorateur pour validation automatique."""
```

### Circuit Breaker (PostgreSQL)

```python
# modules/circuit_breaker.py

class CircuitBreaker:
    """
    Protection contre échecs répétés PostgreSQL.

    États :
    - CLOSED: Fonctionnement normal
    - OPEN: Trop d'échecs, bloque les requêtes
    - HALF_OPEN: Test de récupération
    """

    def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            raise CircuitOpenError("Too many failures")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise
```

## 📊 Optimisations Performance

### PostgreSQL

- **Materialized Views** avec index GIST pour grands datasets
- **Connection pooling** (~50-100ms gain par requête)
- **Two-phase filtering** (3-10x plus rapide)
- **Progressive loading** (50-80% moins de mémoire)
- **Server-side cursors** pour streaming

### Spatialite

- **WKT caching** (réutilisation entre filtres)
- **R-tree index** automatique
- **Bounding box pre-filter** pour WKT >500KB
- **Interruptible queries** (évite freeze QGIS)
- **Direct SQL mode** prioritaire pour GeoPackage

### OGR

- **Spatial index** automatique pour fichiers
- **Geometry validation** GEOS-safe
- **Sequential execution** (thread safety)

### Global

- **Backend caching** avec invalidation automatique
- **Expression result caching**
- **Geometry caching** (évite reprojection)

## 🌍 Internationalisation (i18n)

```python
# filter_mate.py

def __init__(self, iface):
    # Détection langue
    config_language = config.get('app.ui.language.value', 'auto')

    if config_language == 'auto':
        locale = QSettings().value('locale/userLocale')[0:2]
    else:
        locale = config_language

    # Chargement traduction
    locale_path = f'i18n/FilterMate_{locale}.qm'
    if os.path.exists(locale_path):
        translator = QTranslator()
        translator.load(locale_path)
        QCoreApplication.installTranslator(translator)
```

**Langues supportées (21) :**
am, da, de, en, es, fi, fr, hi, id, it, ja, ko, nl, no, pl, pt, ru, sv, tr, zh_CN, zh_TW

## 🧪 Tests

```python
# tests/ (pytest)

def test_backend_selection():
    """Vérifie sélection correcte du backend."""

def test_geometric_filter_postgresql():
    """Test filtrage PostgreSQL avec MV."""

def test_undo_redo():
    """Test historique undo/redo."""

def test_favorites_persistence():
    """Test sauvegarde/chargement favoris."""
```

**Coverage actuel :** ~70%  
**Objectif :** 80%

---

**Prochaine étape :** [Component Inventory](component-inventory.md)
