---
storyId: MIG-087
title: Simplify DockWidget to Orchestrator
epic: 6.7 - Final Refactoring
phase: 6
sprint: 9
priority: P0
status: READY_FOR_DEV
effort: 1 day
assignee: null
dependsOn: [MIG-060, MIG-061, MIG-062, MIG-063, MIG-064, MIG-065, MIG-066, MIG-067, MIG-068, MIG-070, MIG-071, MIG-072, MIG-073, MIG-074, MIG-075, MIG-076, MIG-077, MIG-078, MIG-080, MIG-081, MIG-082, MIG-083, MIG-084, MIG-085, MIG-086]
blocks: [MIG-088, MIG-089]
createdAt: 2026-01-09
updatedAt: 2026-01-09
risk: HIGH
---

# MIG-087: Simplify DockWidget to Orchestrator

## 📋 Story

**En tant que** développeur,  
**Je veux** réduire le dockwidget à un orchestrateur minimal,  
**Afin qu'** il ne contienne que la coordination entre les composants.

---

## 🎯 Objectif

Réduire `filter_mate_dockwidget.py` de ~13,000 lignes à ~500 lignes en remplaçant le code par des délégations vers les managers, controllers et services extraits.

⚠️ **RISQUE ÉLEVÉ**: Cette story est le point de convergence de toute la Phase 6. Elle dépend de TOUTES les stories précédentes.

---

## ✅ Critères d'Acceptation

### Code

- [ ] `filter_mate_dockwidget.py` < 800 lignes (cible: ~500)
- [ ] Toute la logique métier déléguée
- [ ] Aucune méthode > 30 lignes
- [ ] Type hints sur toutes les signatures

### Structure du DockWidget

- [ ] `__init__()` - initialise managers et controllers
- [ ] `closeEvent()` - cleanup propre
- [ ] `setup_ui()` - délègue aux layout managers
- [ ] Propriétés publiques pour accès externe
- [ ] Façades `@deprecated` pour rétrocompatibilité

### Délégation

- [ ] Layout → `SplitterManager`, `DimensionsManager`, `SpacingManager`, `ActionBarManager`
- [ ] Styling → `ThemeManager`, `IconManager`, `ButtonStyler`
- [ ] Controllers → `ConfigController`, `BackendController`, `FavoritesController`, etc.
- [ ] Signals → `SignalManager`, `LayerSignalHandler`
- [ ] Services → Via les controllers

### Tests

- [ ] Tous les tests existants passent
- [ ] Tests de délégation ajoutés
- [ ] Pas de régression fonctionnelle
- [ ] Couverture maintenue > 70%

---

## 📝 Spécifications Techniques

### Structure Finale du DockWidget

```python
"""
FilterMate DockWidget - Main Plugin UI.

Minimal orchestrator that coordinates between:
- Layout managers (splitter, dimensions, spacing, action bar)
- Styling managers (theme, icons, buttons)
- Controllers (filtering, exploring, exporting, config, etc.)
- Signal management (signal manager, layer handler)

After Phase 6 refactoring: ~500 lines (from ~13,000).
"""

from typing import TYPE_CHECKING, Optional
import logging

from qgis.PyQt.QtWidgets import QDockWidget
from qgis.PyQt.QtCore import Qt, pyqtSignal

# Layout managers
from ui.layout import (
    SplitterManager,
    DimensionsManager,
    SpacingManager,
    ActionBarManager,
)

# Styling managers
from ui.styling import (
    ThemeManager,
    IconManager,
    ButtonStyler,
)

# Controllers
from ui.controllers import (
    FilteringController,
    ExploringController,
    ExportingController,
    ConfigController,
    BackendController,
    FavoritesController,
    LayerSyncController,
    PropertyController,
)

# Signal management
from adapters.qgis.signals import SignalManager, LayerSignalHandler

# Services (injected via controllers)
from core.services import (
    FilterService,
    BackendService,
    FavoritesService,
    LayerService,
)

if TYPE_CHECKING:
    from filter_mate_app import FilterMateApp

logger = logging.getLogger(__name__)


class FilterMateDockWidget(QDockWidget):
    """
    Main dockwidget for FilterMate plugin.

    Acts as an orchestrator, delegating all functionality to:
    - Managers: Layout and styling
    - Controllers: User interaction handling
    - Services: Business logic (via controllers)

    This class should contain:
    - Initialization and dependency injection
    - Public properties for external access
    - Deprecated façades for backward compatibility
    - Cleanup on close

    Target: ~500 lines after Phase 6 refactoring.
    """

    # Signals for external communication
    filter_applied = pyqtSignal(str, str)  # layer_id, expression
    export_completed = pyqtSignal(str)  # output_path

    def __init__(
        self,
        app: 'FilterMateApp',
        iface,
        parent=None
    ) -> None:
        """
        Initialize the FilterMate dockwidget.

        Args:
            app: Main application instance
            iface: QGIS interface
            parent: Parent widget
        """
        super().__init__(parent)
        self.app = app
        self.iface = iface

        # Setup base UI from .ui file
        self._setup_base_ui()

        # Initialize managers and controllers
        self._init_managers()
        self._init_services()
        self._init_controllers()
        self._init_signals()

        # Perform initial setup
        self._perform_setup()

        logger.info("FilterMateDockWidget initialized")

    def _setup_base_ui(self) -> None:
        """Load base UI from .ui file."""
        from filter_mate_dockwidget_base import Ui_FilterMateDockWidgetBase
        self.ui = Ui_FilterMateDockWidgetBase()
        self.ui.setupUi(self)

    def _init_managers(self) -> None:
        """Initialize layout and styling managers."""
        # Layout managers
        self._splitter_manager = SplitterManager(self)
        self._dimensions_manager = DimensionsManager(self)
        self._spacing_manager = SpacingManager(self)
        self._action_bar_manager = ActionBarManager(self)

        # Styling managers
        self._theme_manager = ThemeManager(self)
        self._icon_manager = IconManager(self)
        self._button_styler = ButtonStyler(self)

    def _init_services(self) -> None:
        """Initialize business services."""
        # Services are created here but owned by controllers
        from adapters.backends import PostgresSessionManager
        from core.ports import BackendPort

        self._backend_port = BackendPort()
        self._backend_service = BackendService(self._backend_port)
        self._filter_service = FilterService(self._backend_port)
        self._favorites_service = FavoritesService(self._favorites_repo)
        self._layer_service = LayerService(self._layer_adapter)
        self._postgres_session_manager = PostgresSessionManager()

    def _init_controllers(self) -> None:
        """Initialize UI controllers."""
        self._filtering_controller = FilteringController(
            self, self._filter_service
        )
        self._exploring_controller = ExploringController(self)
        self._exporting_controller = ExportingController(self)
        self._config_controller = ConfigController(self)
        self._backend_controller = BackendController(
            self, self._backend_service
        )
        self._favorites_controller = FavoritesController(
            self, self._favorites_service
        )
        self._layer_sync_controller = LayerSyncController(
            self, self._layer_service
        )
        self._property_controller = PropertyController(self)

    def _init_signals(self) -> None:
        """Initialize signal management."""
        self._signal_manager = SignalManager(self)
        self._layer_signal_handler = LayerSignalHandler(
            self, self._signal_manager
        )

    def _perform_setup(self) -> None:
        """Perform initial setup after all components initialized."""
        # Setup layout
        self._splitter_manager.setup()
        self._dimensions_manager.setup()
        self._spacing_manager.setup()
        self._action_bar_manager.setup()

        # Setup styling
        self._theme_manager.setup()
        self._icon_manager.setup()
        self._button_styler.setup()

        # Setup controllers
        for controller in self._get_all_controllers():
            controller.setup()

        # Connect all signals
        self._signal_manager.connect_widgets_signals()

    def _get_all_controllers(self):
        """Get list of all controllers."""
        return [
            self._filtering_controller,
            self._exploring_controller,
            self._exporting_controller,
            self._config_controller,
            self._backend_controller,
            self._favorites_controller,
            self._layer_sync_controller,
            self._property_controller,
        ]

    # =========================================================================
    # Public Properties
    # =========================================================================

    @property
    def current_layer(self):
        """Get the currently selected layer."""
        return self._layer_sync_controller.current_layer

    @property
    def current_backend(self) -> str:
        """Get the current backend name."""
        return self._backend_controller.current_backend

    @property
    def is_filtering_in_progress(self) -> bool:
        """Check if a filter operation is in progress."""
        return self._filtering_controller.is_in_progress

    # =========================================================================
    # Cleanup
    # =========================================================================

    def closeEvent(self, event) -> None:
        """Handle widget close event."""
        logger.debug("DockWidget closing")

        # Disconnect all signals
        self._signal_manager.teardown()
        self._layer_signal_handler.disconnect_all_layers()

        # Cleanup managers
        self._splitter_manager.teardown()
        self._dimensions_manager.teardown()
        self._spacing_manager.teardown()
        self._action_bar_manager.teardown()

        # Cleanup PostgreSQL session
        self._postgres_session_manager.cleanup_on_close()

        super().closeEvent(event)
        logger.info("DockWidget closed")

    # =========================================================================
    # Deprecated Façades (Backward Compatibility)
    # =========================================================================

    # These methods are kept for backward compatibility with external code.
    # They delegate to the appropriate controller/manager.
    # Will be removed in v4.0.

    def apply_filter(self, expression: str):
        """
        @deprecated Use FilteringController.apply_filter() instead.
        """
        import warnings
        warnings.warn(
            "apply_filter() is deprecated. "
            "Use _filtering_controller.apply_filter()",
            DeprecationWarning
        )
        return self._filtering_controller.apply_filter(expression)

    def clear_filter(self):
        """
        @deprecated Use FilteringController.clear_filter() instead.
        """
        import warnings
        warnings.warn(
            "clear_filter() is deprecated. "
            "Use _filtering_controller.clear_filter()",
            DeprecationWarning
        )
        return self._filtering_controller.clear_filter()
```

---

## 🔗 Dépendances

### Entrée

- **TOUTES** les stories MIG-060 à MIG-086

### Sortie

- MIG-088: Deprecation warnings
- MIG-089: Regression testing

---

## 📊 Métriques

| Métrique        | Avant   | Après         |
| --------------- | ------- | ------------- |
| Lignes de code  | ~13,000 | ~500          |
| Méthodes        | ~200    | ~30           |
| Responsabilités | Toutes  | Orchestration |
| Couplage        | Fort    | Faible        |

---

## ⚠️ Risques et Mitigations

| Risque                   | Impact      | Mitigation                  |
| ------------------------ | ----------- | --------------------------- |
| Régression fonctionnelle | 🔴 Critique | Tests exhaustifs            |
| Dépendances manquantes   | 🟠 Élevé    | Vérifier toutes les stories |
| Performance              | 🟡 Moyen    | Profiling avant/après       |
| Breaking changes         | 🟠 Élevé    | Façades deprecated          |

---

## 📋 Checklist Développeur

- [ ] Vérifier que TOUTES les stories MIG-060 à MIG-086 sont complètes
- [ ] Backup de `filter_mate_dockwidget.py` actuel
- [ ] Créer la nouvelle structure `__init__`
- [ ] Migrer section par section
- [ ] Valider les tests après chaque section
- [ ] Ajouter façades deprecated
- [ ] Mesurer lignes finales
- [ ] Profiler les performances

---

_Story générée par 🏃 SM Agent (Bob) - 9 janvier 2026_
