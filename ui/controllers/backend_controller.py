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


# Backend display configuration - v4.0: Softer "mousse" colors
BACKEND_STYLES = {
    'postgresql': {
        'text': 'PostgreSQL',
        'color': 'white',
        'background': '#58d68d',  # Softer green
        'icon': '🐘',
        'tooltip': 'Backend: PostgreSQL (High Performance)'
    },
    'spatialite': {
        'text': 'Spatialite',
        'color': 'white',
        'background': '#bb8fce',  # Softer purple
        'icon': '💾',
        'tooltip': 'Backend: Spatialite (Good Performance)'
    },
    'spatialite_fallback': {
        'text': 'Spatialite*',
        'color': 'white',
        'background': '#a569bd',  # Softer dark purple
        'icon': '💾',
        'tooltip': 'Backend: Spatialite → OGR fallback\n(Complex geometry handled by OGR)'
    },
    'ogr': {
        'text': 'OGR',
        'color': 'white',
        'background': '#5dade2',  # Softer blue
        'icon': '📁',
        'tooltip': 'Backend: OGR (Universal)'
    },
    'ogr_fallback': {
        'text': 'OGR*',
        'color': 'white',
        'background': '#f0b27a',  # Softer orange
        'icon': '📁',
        'tooltip': 'Backend: OGR (Fallback - Connection unavailable)'
    },
    'postgresql_fallback': {
        'text': 'PostgreSQL*',
        'color': 'white',
        'background': '#45b39d',  # Softer teal green
        'icon': '🐘',
        'tooltip': 'Backend: PostgreSQL → OGR fallback'
    },
    'unknown': {
        'text': '...',
        'color': '#7f8c8d',
        'background': '#f4f6f6',  # Softer light gray
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
        self._initialized: bool = False
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
        from ...adapters.backends import POSTGRESQL_AVAILABLE
        
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

        # Update indicator display if this is the current layer
        current_layer = self.dockwidget.current_layer
        if current_layer and current_layer.id() == layer_id:
            display_backend = backend_type if backend_type else self._detect_backend_for_layer(
                current_layer, self._current_postgresql_available
            )
            self._update_indicator_display(display_backend, is_forced=(backend_type is not None), layer=current_layer)

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
        Auto-select optimal backend for each layer based on characteristics.
        
        v4.0 Sprint 1: Full implementation migrated from dockwidget.
        
        Analyzes each layer's characteristics and sets the most appropriate backend:
        - PostgreSQL for large server-side datasets
        - Spatialite for SQLite/GeoPackage with > 5000 features
        - OGR for small datasets and file-based formats

        Returns:
            Number of layers optimized
        """
        from qgis.core import QgsProject

        project = QgsProject.instance()
        layers = project.mapLayers().values()
        
        optimized_count = 0
        skipped_count = 0
        backend_stats = {'postgresql': 0, 'spatialite': 0, 'ogr': 0, 'auto': 0}
        
        logger.info("=" * 60)
        logger.info("AUTO-SELECTING OPTIMAL BACKENDS FOR ALL LAYERS")
        logger.info("=" * 60)
        
        for layer in layers:
            # Skip non-vector layers
            if not isinstance(layer, QgsVectorLayer):
                continue
            
            if not layer.isValid():
                skipped_count += 1
                continue
            
            layer_name = layer.name()
            logger.info(f"\nAnalyzing layer: {layer_name}")
            
            # Get optimal backend for this layer
            optimal_backend = self._get_optimal_backend_for_layer(layer)
            
            if optimal_backend:
                # Verify backend supports layer
                if self._verify_backend_supports_layer(layer, optimal_backend):
                    self.set_forced_backend(layer.id(), optimal_backend)
                    backend_stats[optimal_backend] += 1
                    optimized_count += 1
                    logger.info(f"  ✓ Set backend to: {optimal_backend.upper()}")
                else:
                    backend_stats['auto'] += 1
                    logger.info(f"  ⚠ Backend {optimal_backend.upper()} not compatible - using auto")
            else:
                backend_stats['auto'] += 1
                logger.info(f"  → Using auto-selection")
        
        logger.info("\n" + "=" * 60)
        logger.info("AUTO-SELECTION COMPLETE")
        logger.info(f"Optimized: {optimized_count} layers")
        logger.info(f"Skipped: {skipped_count} invalid layers")
        logger.info(f"Backend distribution:")
        for backend, count in backend_stats.items():
            if count > 0:
                logger.info(f"  - {backend.upper()}: {count} layer(s)")
        logger.info("=" * 60)
        
        # Emit signal with summary (requires 2 args: layer_id, backend_type)
        self.backend_changed.emit("batch_optimization", f"Optimized {optimized_count} layers")
        
        return optimized_count
    
    def _get_optimal_backend_for_layer(self, layer: QgsVectorLayer) -> Optional[str]:
        """
        Determine optimal backend for a layer based on characteristics.
        
        Args:
            layer: QgsVectorLayer instance
            
        Returns:
            Optimal backend ('postgresql', 'spatialite', 'ogr') or None for auto
        """
        try:
            from ...adapters.backends import POSTGRESQL_AVAILABLE
            from ...adapters.backends.factory import should_use_memory_optimization
            from ...infrastructure.utils import detect_layer_provider_type
        except ImportError:
            logger.warning("Could not import backend detection functions")
            return None
        
        if not layer or not layer.isValid():
            return None
        
        provider_type = detect_layer_provider_type(layer)
        feature_count = layer.featureCount()
        source = layer.source().lower()
        
        logger.debug(f"  Provider: {provider_type}, Features: {feature_count:,}")
        logger.debug(f"  PostgreSQL available: {POSTGRESQL_AVAILABLE}")
        
        # PostgreSQL layers
        if provider_type == 'postgresql':
            if not POSTGRESQL_AVAILABLE:
                logger.debug(f"  → PostgreSQL unavailable - OGR fallback")
                return 'ogr'
            
            if should_use_memory_optimization(layer, provider_type):
                logger.debug(f"  → Small PostgreSQL ({feature_count}) - OGR memory optimization")
                return 'ogr'
            
            logger.debug(f"  → Large PostgreSQL ({feature_count}) - PostgreSQL optimal")
            return 'postgresql'
        
        # SQLite/Spatialite layers
        elif provider_type == 'spatialite':
            if feature_count > 5000:
                logger.debug(f"  → SQLite ({feature_count}) - Spatialite R-tree optimal")
                return 'spatialite'
            else:
                logger.debug(f"  → Small SQLite ({feature_count}) - OGR sufficient")
                return 'ogr'
        
        # OGR layers
        elif provider_type == 'ogr':
            if 'gpkg' in source or 'sqlite' in source:
                if feature_count > 5000:
                    logger.debug(f"  → GeoPackage ({feature_count}) - Spatialite optimal")
                    return 'spatialite'
                else:
                    logger.debug(f"  → Small GeoPackage ({feature_count}) - OGR sufficient")
                    return 'ogr'
            
            logger.debug(f"  → OGR format ({feature_count}) - OGR sufficient")
            return 'ogr'
        
        logger.debug(f"  → Unknown provider '{provider_type}' - auto-selection")
        return None
    
    def _verify_backend_supports_layer(self, layer: QgsVectorLayer, backend: str) -> bool:
        """
        Verify that a backend can actually process the layer.
        
        Args:
            layer: Layer to check
            backend: Backend type to verify
            
        Returns:
            True if backend supports this layer
        """
        try:
            from ...infrastructure.utils import detect_layer_provider_type, POSTGRESQL_AVAILABLE
        except ImportError:
            return True  # Assume compatible if can't check
        
        provider_type = detect_layer_provider_type(layer)
        
        if backend == 'postgresql':
            # PostgreSQL backend only for PostgreSQL layers
            return provider_type == 'postgresql' and POSTGRESQL_AVAILABLE
        elif backend == 'spatialite':
            # Spatialite works with SQLite and GeoPackage
            source = layer.source().lower()
            return provider_type == 'spatialite' or 'gpkg' in source or 'sqlite' in source
        elif backend == 'ogr':
            # OGR is universal fallback
            return True
        
        return False

    def handle_indicator_clicked(self) -> None:
        """
        Handle click on backend indicator.

        Shows backend selection menu or triggers reload if no layers.
        """
        print(f"🔧 BackendController.handle_indicator_clicked() START - _initialized={self._initialized}")
        
        # Lazy initialization fallback
        if not self._initialized:
            print("🔧 BackendController: setup() was never called - performing lazy initialization...")
            self.setup()
            print(f"🔧 After lazy setup: _initialized={self._initialized}")
        
        # Check if in waiting state (no layers)
        if self._indicator_label:
            text = self._indicator_label.text()
            print(f"🔧 indicator_label text = '{text}'")
            if text in ('...', '⟳'):
                logger.info("Backend indicator clicked in waiting state - requesting reload")
                print("🔧 In waiting state - emitting reload_requested")
                self.reload_requested.emit()
                return

        current_layer = self.dockwidget.current_layer
        print(f"🔧 current_layer = {current_layer}")
        if not current_layer:
            print("🔧 No current_layer - emitting reload_requested")
            self.reload_requested.emit()
            return

        print(f"🔧 Calling _show_backend_menu({current_layer.name()})")
        self._show_backend_menu(current_layer)
        print("🔧 BackendController.handle_indicator_clicked() END")

    # === Private Methods ===

    def _find_indicator_label(self) -> None:
        """Find the backend indicator label in dockwidget."""
        if hasattr(self.dockwidget, 'backend_indicator_label') and self.dockwidget.backend_indicator_label:
            self._indicator_label = self.dockwidget.backend_indicator_label
            logger.debug(f"BackendController: Found indicator label: {self._indicator_label}")
        else:
            logger.debug("BackendController: backend_indicator_label not found in dockwidget")

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
            from ...adapters.backends import POSTGRESQL_AVAILABLE
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
        # Try to find indicator label if not set
        if not self._indicator_label:
            self._find_indicator_label()
        
        # Still no indicator label? Try direct access to dockwidget's label
        if not self._indicator_label:
            if hasattr(self.dockwidget, 'backend_indicator_label') and self.dockwidget.backend_indicator_label:
                self._indicator_label = self.dockwidget.backend_indicator_label
                logger.debug("Found backend_indicator_label via direct dockwidget access")
            else:
                logger.warning("BackendController: _indicator_label not found, cannot update display")
                return

        style = BACKEND_STYLES.get(backend_type, BACKEND_STYLES['unknown'])
        
        # Build text with forced indicator
        text = style['text']
        if is_forced:
            text = f"{text}⚡"

        self._indicator_label.setText(text)

        # Build stylesheet - v4.0: Soft "mousse" style with smoother appearance
        stylesheet = f"""
            QLabel#label_backend_indicator {{
                color: {style['color']};
                background-color: {style['background']};
                font-size: 8pt;
                font-weight: 500;
                padding: 2px 8px;
                border-radius: 10px;
                border: none;
            }}
            QLabel#label_backend_indicator:hover {{
                filter: brightness(1.1);
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

    def _refresh_indicator_for_current_layer(self) -> None:
        """
        Refresh the backend indicator for the current layer.
        
        This method ensures the indicator is updated after batch operations
        (like force_backend_for_all_layers or auto_select_optimal_backends).
        """
        current_layer = self.dockwidget.current_layer
        if not current_layer or not current_layer.isValid():
            return
        
        # Get the backend for current layer (may have been changed by batch operation)
        backend_type = self._detect_backend_for_layer(
            current_layer, self._current_postgresql_available
        )
        
        # Check if forced
        is_forced = current_layer.id() in self._forced_backends
        
        # Update the display
        self._update_indicator_display(backend_type, is_forced, current_layer)
        logger.debug(f"Refreshed indicator for layer {current_layer.name()}: {backend_type} (forced: {is_forced})")

    def _show_backend_menu(self, layer: QgsVectorLayer) -> None:
        """
        Show the backend selection menu.

        Args:
            layer: Current layer for backend selection
        """
        print(f"🔧 _show_backend_menu() START for layer '{layer.name()}'")
        from ...infrastructure.feedback import show_info, show_success, show_warning

        available = self.get_available_backends_for_layer(layer)
        print(f"🔧 available backends: {available}")
        
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
        print(f"🔧 About to show backend menu.exec_() at position {QCursor.pos()}")
        selected_action = menu.exec_(QCursor.pos())
        print(f"🔧 backend menu.exec_() returned: {selected_action}")

        if selected_action:
            data = selected_action.data()
            print(f"🔧 Selected backend data: {data}")

            if data == '__AUTO_ALL__':
                count = self.auto_select_optimal_backends()
                show_success("FilterMate", f"Auto-selected backends for {count} layers")
                # Update indicator for current layer after batch operation
                self._refresh_indicator_for_current_layer()
            elif data == '__FORCE_ALL__':
                count = self.force_backend_for_all_layers(current_backend)
                show_success("FilterMate", f"Forced {current_backend.upper()} for {count} layers")
                # Update indicator for current layer after batch operation
                self._refresh_indicator_for_current_layer()
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

    # ========================================
    # POSTGRESQL MAINTENANCE METHODS (Sprint 13)
    # ========================================

    def get_pg_session_context(self):
        """
        Get PostgreSQL session context for maintenance operations.
        
        v4.0 Sprint 13: Migrated from dockwidget._get_pg_session_context()
        
        Returns:
            tuple: (app, session_id, schema, connexion)
        """
        from ..adapters.backends import POSTGRESQL_AVAILABLE
        if not POSTGRESQL_AVAILABLE:
            return None, None, None, None
        
        try:
            from ...infrastructure.utils.layer_utils import get_datasource_connexion_from_layer
        except ImportError:
            from ...infrastructure.utils.layer_utils import get_datasource_connexion_from_layer
        
        # Get app reference
        app = getattr(self.dockwidget, '_app_ref', None)
        if not app:
            parent = self.dockwidget.parent()
            while parent:
                if hasattr(parent, 'session_id'):
                    app = parent
                    break
                parent = parent.parent() if hasattr(parent, 'parent') else None
        
        session_id = getattr(app, 'session_id', None) if app else None
        schema = getattr(app, 'app_postgresql_temp_schema', 'filter_mate_temp') if app else 'filter_mate_temp'
        
        # Find a PostgreSQL connection
        connexion = None
        project_layers = getattr(app, 'PROJECT_LAYERS', {}) if app else {}
        for layer_info in project_layers.values():
            layer = layer_info.get('layer')
            if layer and layer.isValid() and layer.providerType() == 'postgres':
                connexion, _ = get_datasource_connexion_from_layer(layer)
                if connexion:
                    break
        
        return app, session_id, schema, connexion

    @property
    def pg_auto_cleanup_enabled(self) -> bool:
        """Whether PostgreSQL auto-cleanup is enabled."""
        return getattr(self, '_pg_auto_cleanup_enabled', True)

    @pg_auto_cleanup_enabled.setter
    def pg_auto_cleanup_enabled(self, value: bool) -> None:
        """Set PostgreSQL auto-cleanup enabled state."""
        self._pg_auto_cleanup_enabled = value
        if hasattr(self.dockwidget, '_pg_auto_cleanup_enabled'):
            self.dockwidget._pg_auto_cleanup_enabled = value

    def toggle_pg_auto_cleanup(self) -> bool:
        """
        Toggle PostgreSQL auto-cleanup.
        
        v4.0 Sprint 13: Migrated from dockwidget._toggle_pg_auto_cleanup()
        
        Returns:
            bool: New state of pg_auto_cleanup
        """
        self.pg_auto_cleanup_enabled = not self.pg_auto_cleanup_enabled
        return self.pg_auto_cleanup_enabled

    def cleanup_postgresql_session_views(self) -> bool:
        """
        Cleanup PostgreSQL materialized views for current session.
        
        v4.0 Sprint 13: Migrated from dockwidget._cleanup_postgresql_session_views()
        
        Returns:
            bool: True if cleanup successful
        """
        app, session_id, schema, connexion = self.get_pg_session_context()
        
        if not connexion:
            logger.warning("cleanup_postgresql_session_views: No PostgreSQL connection available")
            return False
        
        if not session_id:
            logger.warning("cleanup_postgresql_session_views: Session ID not available")
            return False
        
        try:
            with connexion.cursor() as cursor:
                # Find views for this session
                cursor.execute(
                    "SELECT matviewname FROM pg_matviews WHERE schemaname = %s AND matviewname LIKE %s",
                    (schema, f"mv_{session_id}_%")
                )
                views = [v[0] for v in cursor.fetchall()]
                
                if not views:
                    logger.info(f"No views found for session {session_id[:8]}")
                    return True
                
                # Drop each view
                for view in views:
                    try:
                        cursor.execute(f'DROP MATERIALIZED VIEW IF EXISTS "{schema}"."{view}" CASCADE;')
                    except Exception as e:
                        logger.warning(f"Failed to drop view {view}: {e}")
                
                connexion.commit()
                logger.info(f"Cleaned up {len(views)} view(s) for session {session_id[:8]}")
                return True
                
        except Exception as e:
            logger.error(f"Error cleaning PostgreSQL session views: {e}")
            return False
        finally:
            try:
                connexion.close()
            except Exception:
                pass

    def cleanup_postgresql_schema_if_empty(self, force: bool = False) -> bool:
        """
        Drop PostgreSQL schema if no other sessions are using it.
        
        v4.0 Sprint 13: Migrated from dockwidget._cleanup_postgresql_schema_if_empty()
        
        Args:
            force: If True, skip confirmation for views from other sessions
            
        Returns:
            bool: True if cleanup successful or schema doesn't exist
        """
        app, session_id, schema, connexion = self.get_pg_session_context()
        
        if not connexion:
            logger.warning("cleanup_postgresql_schema_if_empty: No PostgreSQL connection available")
            return False
        
        try:
            with connexion.cursor() as cursor:
                # Check if schema exists
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = %s",
                    (schema,)
                )
                if cursor.fetchone()[0] == 0:
                    logger.info(f"Schema '{schema}' does not exist")
                    return True
                
                # Get all views in schema
                cursor.execute(
                    "SELECT matviewname FROM pg_matviews WHERE schemaname = %s",
                    (schema,)
                )
                views = [v[0] for v in cursor.fetchall()]
                
                # Check for views from other sessions
                other_views = [v for v in views if not (session_id and v.startswith(f"mv_{session_id}_"))]
                
                if other_views and not force:
                    logger.warning(f"Schema '{schema}' has {len(other_views)} view(s) from other sessions")
                    return False
                
                # Drop schema
                cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE;')
                connexion.commit()
                logger.info(f"Schema '{schema}' dropped successfully")
                return True
                
        except Exception as e:
            logger.error(f"Error cleaning PostgreSQL schema: {e}")
            return False
        finally:
            try:
                connexion.close()
            except Exception:
                pass

    def get_postgresql_session_info(self) -> dict:
        """
        Get PostgreSQL session information.
        
        v4.0 Sprint 13: Migrated from dockwidget._show_postgresql_session_info()
        
        Returns:
            dict: Session information with keys: session_id, schema, auto_cleanup,
                  schema_exists, our_views_count, total_views_count, connection_available
        """
        app, session_id, schema, connexion = self.get_pg_session_context()
        
        info = {
            'session_id': session_id,
            'schema': schema,
            'auto_cleanup': self.pg_auto_cleanup_enabled,
            'connection_available': connexion is not None,
            'schema_exists': False,
            'our_views_count': 0,
            'total_views_count': 0
        }
        
        if connexion:
            try:
                with connexion.cursor() as cursor:
                    # Count our views
                    if session_id:
                        cursor.execute(
                            "SELECT COUNT(*) FROM pg_matviews WHERE schemaname = %s AND matviewname LIKE %s",
                            (schema, f"mv_{session_id}_%")
                        )
                        info['our_views_count'] = cursor.fetchone()[0]
                    
                    # Count total views
                    cursor.execute(
                        "SELECT COUNT(*) FROM pg_matviews WHERE schemaname = %s",
                        (schema,)
                    )
                    info['total_views_count'] = cursor.fetchone()[0]
                    
                    # Check schema exists
                    cursor.execute(
                        "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = %s",
                        (schema,)
                    )
                    info['schema_exists'] = cursor.fetchone()[0] > 0
                    
            except Exception as e:
                info['error'] = str(e)[:50]
                logger.warning(f"Error getting PostgreSQL session info: {e}")
            finally:
                try:
                    connexion.close()
                except Exception:
                    pass
        
        return info
