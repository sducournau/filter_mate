"""
Backend Controller for FilterMate.

Manages the backend indicator widget and selection menu.
Extracted from filter_mate_dockwidget.py (lines 1612-1966, 2945-3100, 12503-12650).

Story: MIG-071
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, List, Tuple, Dict
import logging

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtWidgets import QMenu, QLabel
from qgis.PyQt.QtGui import QCursor
from qgis.core import QgsVectorLayer

from .base_controller import BaseController

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


# Backend display configuration
BACKEND_STYLES = {
    'postgresql': {
        'text': 'PostgreSQL',
        'color': 'white',
        'background': '#27ae60',  # Green
        'icon': '🐘',
        'tooltip': 'Backend: PostgreSQL (High Performance)'
    },
    'spatialite': {
        'text': 'Spatialite',
        'color': 'white',
        'background': '#9b59b6',  # Purple
        'icon': '💾',
        'tooltip': 'Backend: Spatialite (Good Performance)'
    },
    'spatialite_fallback': {
        'text': 'Spatialite*',
        'color': 'white',
        'background': '#8e44ad',  # Dark purple
        'icon': '💾',
        'tooltip': 'Backend: Spatialite → OGR fallback\n(Complex geometry handled by OGR)'
    },
    'ogr': {
        'text': 'OGR',
        'color': 'white',
        'background': '#3498db',  # Blue
        'icon': '📁',
        'tooltip': 'Backend: OGR (Universal)'
    },
    'ogr_fallback': {
        'text': 'OGR*',
        'color': 'white',
        'background': '#e67e22',  # Orange
        'icon': '📁',
        'tooltip': 'Backend: OGR (Fallback - Connection unavailable)'
    },
    'postgresql_fallback': {
        'text': 'PostgreSQL*',
        'color': 'white',
        'background': '#1e8449',  # Dark green
        'icon': '🐘',
        'tooltip': 'Backend: PostgreSQL → OGR fallback'
    },
    'unknown': {
        'text': '...',
        'color': '#7f8c8d',
        'background': '#ecf0f1',
        'icon': '❓',
        'tooltip': 'Backend: Unknown'
    }
}


class BackendController(BaseController):
    """
    Controller for backend indicator management.

    Handles:
    - Backend indicator display and styling
    - Backend selection menu
    - Backend switching per layer
    - Optimization settings
    - PostgreSQL maintenance options

    Signals:
        backend_changed: Emitted when backend is switched
        reload_requested: Emitted when user wants to reload layers

    Example:
        controller = BackendController(dockwidget)
        controller.setup()

        # React to backend changes
        controller.backend_changed.connect(on_backend_changed)
    """

    backend_changed = pyqtSignal(str, str)  # (layer_id, backend_name)
    reload_requested = pyqtSignal()

    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the backend controller.

        Args:
            dockwidget: Main dockwidget reference
        """
        super().__init__(dockwidget)
        self._forced_backends: Dict[str, str] = {}
        self._current_provider_type: Optional[str] = None
        self._current_postgresql_available: Optional[bool] = None
        self._indicator_label: Optional[QLabel] = None
        # Optimization settings
        self._optimization_enabled: bool = True
        self._centroid_auto_enabled: bool = True
        self._optimization_ask_before: bool = True

    @property
    def forced_backends(self) -> Dict[str, str]:
        """Get dictionary of forced backends by layer ID."""
        return self._forced_backends

    def setup(self) -> None:
        """
        Setup backend indicator widget.

        Finds and configures the backend indicator label from dockwidget.
        """
        self._find_indicator_label()
        self._sync_with_dockwidget()
        self._initialized = True
        logger.debug("BackendController setup complete")

    def teardown(self) -> None:
        """Clean up resources."""
        self._forced_backends.clear()
        super().teardown()

    def on_tab_activated(self) -> None:
        """Handle tab activation."""
        super().on_tab_activated()
        # Refresh indicator for current layer
        if self.dockwidget.current_layer:
            self.update_for_layer(self.dockwidget.current_layer)

    def on_tab_deactivated(self) -> None:
        """Handle tab deactivation."""
        super().on_tab_deactivated()

    # === Public API ===

    def update_for_layer(
        self,
        layer: QgsVectorLayer,
        postgresql_connection_available: Optional[bool] = None,
        actual_backend: Optional[str] = None
    ) -> None:
        """
        Update indicator for current layer.

        Args:
            layer: Current QgsVectorLayer
            postgresql_connection_available: Whether PostgreSQL connection is available
            actual_backend: Forced backend name, if any
        """
        if not layer or not layer.isValid():
            self._update_indicator_display('unknown')
            return

        provider_type = layer.providerType()
        self._current_provider_type = provider_type
        self._current_postgresql_available = postgresql_connection_available

        # Determine actual backend type
        backend_type = self._detect_backend_for_layer(
            layer, postgresql_connection_available, actual_backend
        )
        
        # Check if forced
        is_forced = (actual_backend is not None) or (layer.id() in self._forced_backends)

        self._update_indicator_display(backend_type, is_forced, layer)

    def get_available_backends_for_layer(
        self,
        layer: QgsVectorLayer
    ) -> List[Tuple[str, str, str]]:
        """
        Get list of available backends for the given layer.

        Args:
            layer: QgsVectorLayer to check

        Returns:
            List of tuples: (backend_type, backend_name, backend_icon)
        """
        from adapters.backends import POSTGRESQL_AVAILABLE
        
        available = []
        provider_type = layer.providerType()

        # PostgreSQL backend (only for postgres layers with psycopg2 available)
        if provider_type == 'postgres':
            try:
                if POSTGRESQL_AVAILABLE:
                    available.append(('postgresql', 'PostgreSQL', '🐘'))
            except ImportError:
                pass

        # Spatialite backend (for spatialite layers and some OGR layers)
        if provider_type in ['spatialite', 'ogr']:
            source = layer.source()
            if 'gpkg' in source.lower() or 'sqlite' in source.lower() or provider_type == 'spatialite':
                available.append(('spatialite', 'Spatialite', '💾'))

        # OGR backend (always available as fallback)
        available.append(('ogr', 'OGR', '📁'))

        # Remove current backend to show only alternatives (keep at least one)
        if len(available) > 1:
            current_backend = self.get_current_backend(layer)
            available = [b for b in available if b[0] != current_backend]

        return available

    def get_current_backend(self, layer: QgsVectorLayer) -> str:
        """
        Get the current backend for a layer.

        Args:
            layer: Layer to check

        Returns:
            Backend type string ('postgresql', 'spatialite', 'ogr')
        """
        # Check forced backend first
        if layer.id() in self._forced_backends:
            return self._forced_backends[layer.id()]

        # Auto-detection
        return self._detect_backend_for_layer(layer, self._current_postgresql_available)

    def set_forced_backend(
        self,
        layer_id: str,
        backend_type: Optional[str]
    ) -> None:
        """
        Force a specific backend for a layer.

        Args:
            layer_id: Layer ID
            backend_type: Backend type to force, or None for auto
        """
        if backend_type is None:
            if layer_id in self._forced_backends:
                del self._forced_backends[layer_id]
                logger.info(f"Removed forced backend for layer {layer_id}")
        else:
            self._forced_backends[layer_id] = backend_type
            logger.info(f"Forced backend {backend_type} for layer {layer_id}")

        # Sync with dockwidget
        if hasattr(self.dockwidget, 'forced_backends'):
            self.dockwidget.forced_backends = self._forced_backends.copy()

        self.backend_changed.emit(layer_id, backend_type or 'auto')

    def force_backend_for_all_layers(self, backend_type: str) -> int:
        """
        Force a specific backend for all layers in the project.

        Args:
            backend_type: Backend type to force

        Returns:
            Number of layers updated
        """
        from qgis.core import QgsProject

        project = QgsProject.instance()
        layers = project.mapLayers().values()
        
        count = 0
        for layer in layers:
            if isinstance(layer, QgsVectorLayer) and layer.isValid():
                self.set_forced_backend(layer.id(), backend_type)
                count += 1

        logger.info(f"Forced {backend_type} backend for {count} layers")
        return count

    def auto_select_optimal_backends(self) -> int:
        """
        Auto-select optimal backend for each layer.

        Returns:
            Number of layers updated
        """
        from qgis.core import QgsProject

        project = QgsProject.instance()
        layers = project.mapLayers().values()
        
        count = 0
        for layer in layers:
            if isinstance(layer, QgsVectorLayer) and layer.isValid():
                # Remove forced backend, let auto-detection work
                self.set_forced_backend(layer.id(), None)
                count += 1

        logger.info(f"Set auto-backend for {count} layers")
        return count

    def handle_indicator_clicked(self) -> None:
        """
        Handle click on backend indicator.

        Shows backend selection menu or triggers reload if no layers.
        """
        # Check if in waiting state (no layers)
        if self._indicator_label:
            text = self._indicator_label.text()
            if text in ('...', '⟳'):
                logger.info("Backend indicator clicked in waiting state - requesting reload")
                self.reload_requested.emit()
                return

        current_layer = self.dockwidget.current_layer
        if not current_layer:
            self.reload_requested.emit()
            return

        self._show_backend_menu(current_layer)

    # === Private Methods ===

    def _find_indicator_label(self) -> None:
        """Find the backend indicator label in dockwidget."""
        if hasattr(self.dockwidget, 'backend_indicator_label'):
            self._indicator_label = self.dockwidget.backend_indicator_label

    def _sync_with_dockwidget(self) -> None:
        """Sync state with dockwidget attributes."""
        # Sync forced backends
        if hasattr(self.dockwidget, 'forced_backends'):
            self._forced_backends = self.dockwidget.forced_backends.copy()

        # Sync optimization settings
        for attr in ('_optimization_enabled', '_centroid_auto_enabled', '_optimization_ask_before'):
            if hasattr(self.dockwidget, attr):
                setattr(self, attr, getattr(self.dockwidget, attr))

    def _detect_backend_for_layer(
        self,
        layer: QgsVectorLayer,
        postgresql_available: Optional[bool] = None,
        forced_backend: Optional[str] = None
    ) -> str:
        """
        Detect which backend should be used for a layer.

        Args:
            layer: Layer to analyze
            postgresql_available: PostgreSQL connection status
            forced_backend: Explicitly forced backend

        Returns:
            Backend type string
        """
        # Check forced backend
        if forced_backend:
            return forced_backend.lower()

        if layer.id() in self._forced_backends:
            return self._forced_backends[layer.id()].lower()

        # Auto-detection
        provider_type = layer.providerType()
        
        try:
            from adapters.backends import POSTGRESQL_AVAILABLE
        except ImportError:
            POSTGRESQL_AVAILABLE = False

        postgresql_usable = POSTGRESQL_AVAILABLE and (postgresql_available is not False)

        if provider_type == 'postgres' and postgresql_usable:
            return 'postgresql'
        elif provider_type == 'postgres' and not postgresql_usable:
            return 'ogr_fallback'
        elif provider_type == 'spatialite':
            return 'spatialite'
        elif provider_type == 'ogr':
            # Check for GeoPackage/SQLite with Spatialite support
            source = layer.source().split('|')[0]
            if source.lower().endswith(('.gpkg', '.sqlite')):
                return 'spatialite'
            return 'ogr'
        else:
            return 'unknown'

    def _update_indicator_display(
        self,
        backend_type: str,
        is_forced: bool = False,
        layer: Optional[QgsVectorLayer] = None
    ) -> None:
        """
        Update the visual display of the backend indicator.

        Args:
            backend_type: Backend type to display
            is_forced: Whether backend is forced by user
            layer: Current layer for context
        """
        if not self._indicator_label:
            return

        style = BACKEND_STYLES.get(backend_type, BACKEND_STYLES['unknown'])
        
        # Build text with forced indicator
        text = style['text']
        if is_forced:
            text = f"{text}⚡"

        self._indicator_label.setText(text)

        # Build stylesheet
        stylesheet = f"""
            QLabel#label_backend_indicator {{
                color: {style['color']};
                background-color: {style['background']};
                font-size: 9pt;
                font-weight: 600;
                padding: 3px 10px;
                border-radius: 12px;
                border: none;
            }}
            QLabel#label_backend_indicator:hover {{
                opacity: 0.85;
            }}
        """
        self._indicator_label.setStyleSheet(stylesheet)

        # Build tooltip with context
        tooltip = style['tooltip']
        if layer:
            feature_count = layer.featureCount()
            tooltip += f"\nLayer: {layer.name()} ({feature_count:,} features)"
        if is_forced:
            tooltip += "\n⚡ Manually forced"

        self._indicator_label.setToolTip(tooltip)

    def _show_backend_menu(self, layer: QgsVectorLayer) -> None:
        """
        Show the backend selection menu.

        Args:
            layer: Current layer for backend selection
        """
        from infrastructure.feedback import show_info, show_success, show_warning

        available = self.get_available_backends_for_layer(layer)
        
        if not available:
            show_warning("FilterMate", "No alternative backends available for this layer")
            return

        menu = QMenu(self.dockwidget)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #cccccc;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 20px;
            }
            QMenu::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)

        # Header
        header = menu.addAction("Select Backend:")
        header.setEnabled(False)
        menu.addSeparator()

        # Available backends
        current_forced = self._forced_backends.get(layer.id())
        for backend_type, backend_name, backend_icon in available:
            action_text = f"{backend_icon} {backend_name}"
            if current_forced == backend_type:
                action_text += " ✓"
            action = menu.addAction(action_text)
            action.setData(backend_type)

        menu.addSeparator()

        # Auto option
        auto_action = menu.addAction("⚙️ Auto (Default)")
        auto_action.setData(None)
        if not current_forced:
            auto_action.setText(auto_action.text() + " ✓")

        menu.addSeparator()

        # Auto-select all
        auto_all_action = menu.addAction("🎯 Auto-select Optimal for All Layers")
        auto_all_action.setData('__AUTO_ALL__')

        # Force all
        current_backend = self.get_current_backend(layer)
        force_all_action = menu.addAction(f"🔒 Force {current_backend.upper()} for All Layers")
        force_all_action.setData('__FORCE_ALL__')

        # Show menu
        selected_action = menu.exec_(QCursor.pos())

        if selected_action:
            data = selected_action.data()

            if data == '__AUTO_ALL__':
                count = self.auto_select_optimal_backends()
                show_success("FilterMate", f"Auto-selected backends for {count} layers")
            elif data == '__FORCE_ALL__':
                count = self.force_backend_for_all_layers(current_backend)
                show_success("FilterMate", f"Forced {current_backend.upper()} for {count} layers")
            else:
                self.set_forced_backend(layer.id(), data)
                if data:
                    self.update_for_layer(layer, actual_backend=data)
                    show_success("FilterMate", f"Backend forced to {data.upper()} for '{layer.name()}'")
                else:
                    self.update_for_layer(layer)
                    show_info("FilterMate", f"Backend set to Auto for '{layer.name()}'")

    # === Optimization Settings ===

    @property
    def optimization_enabled(self) -> bool:
        """Whether auto-optimization is enabled."""
        return self._optimization_enabled

    @optimization_enabled.setter
    def optimization_enabled(self, value: bool) -> None:
        """Set optimization enabled state."""
        self._optimization_enabled = value
        if hasattr(self.dockwidget, '_optimization_enabled'):
            self.dockwidget._optimization_enabled = value

    @property
    def centroid_auto_enabled(self) -> bool:
        """Whether centroid auto-detection is enabled."""
        return self._centroid_auto_enabled

    @centroid_auto_enabled.setter
    def centroid_auto_enabled(self, value: bool) -> None:
        """Set centroid auto-detection enabled state."""
        self._centroid_auto_enabled = value
        if hasattr(self.dockwidget, '_centroid_auto_enabled'):
            self.dockwidget._centroid_auto_enabled = value

    def toggle_optimization_enabled(self) -> bool:
        """Toggle optimization enabled state."""
        self.optimization_enabled = not self.optimization_enabled
        return self.optimization_enabled

    def toggle_centroid_auto(self) -> bool:
        """Toggle centroid auto-detection."""
        self.centroid_auto_enabled = not self.centroid_auto_enabled
        return self.centroid_auto_enabled
