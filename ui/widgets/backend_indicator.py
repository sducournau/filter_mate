"""
FilterMate BackendIndicatorWidget.

Widget showing current backend with selection menu.
Extracted from filter_mate_dockwidget.py for better modularity.
"""
from typing import Optional, Callable, List, Tuple, Dict
import logging

try:
    from qgis.PyQt.QtWidgets import QLabel, QMenu, QWidget
    from qgis.PyQt.QtCore import pyqtSignal, Qt
    from qgis.PyQt.QtGui import QCursor
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False
    QLabel = object
    QWidget = object
    Qt = None
    pyqtSignal = lambda *args: None

logger = logging.getLogger(__name__)


# Backend display configuration
BACKEND_CONFIG = {
    'postgresql': {
        'name': 'PostgreSQL',
        'icon': '🐘',
        'color': '#27ae60',
        'hover_color': '#1e8449',
    },
    'spatialite': {
        'name': 'Spatialite',
        'icon': '💾',
        'color': '#9b59b6',
        'hover_color': '#7d3c98',
    },
    'ogr': {
        'name': 'OGR',
        'icon': '📁',
        'color': '#3498db',
        'hover_color': '#2980b9',
    },
    'memory': {
        'name': 'Memory',
        'icon': '💭',
        'color': '#e67e22',
        'hover_color': '#d35400',
    },
    'unknown': {
        'name': 'Unknown',
        'icon': '❓',
        'color': '#95a5a6',
        'hover_color': '#7f8c8d',
    },
}


class BackendIndicatorWidget(QLabel if HAS_QGIS else object):
    """
    Widget showing current backend with selection menu.
    
    Displays a badge indicating which backend is being used for filtering,
    and provides a context menu to select alternative backends.
    
    Signals:
        backendChanged: Emitted when backend is changed for a layer (layer_id, backend_type)
        backendForAllChanged: Emitted when backend is forced for all layers (backend_type)
        autoSelectRequested: Emitted when user requests auto-select optimal
        reloadRequested: Emitted when reload is triggered (waiting state click)
    """
    
    if HAS_QGIS:
        backendChanged = pyqtSignal(str, str)  # layer_id, backend_type
        backendForAllChanged = pyqtSignal(str)  # backend_type
        autoSelectRequested = pyqtSignal()
        reloadRequested = pyqtSignal()
    
    def __init__(
        self,
        get_current_layer_func: Optional[Callable] = None,
        get_available_backends_func: Optional[Callable] = None,
        detect_backend_func: Optional[Callable] = None,
        parent=None
    ):
        """
        Initialize BackendIndicatorWidget.
        
        Args:
            get_current_layer_func: Callback to get current layer
            get_available_backends_func: Callback to get available backends for a layer
            detect_backend_func: Callback to detect current backend for a layer
            parent: Parent widget
        """
        if HAS_QGIS:
            super().__init__(parent)
        
        self._get_current_layer = get_current_layer_func
        self._get_available_backends = get_available_backends_func
        self._detect_backend = detect_backend_func
        
        # Storage for forced backends per layer
        self._forced_backends: Dict[str, str] = {}
        
        # State
        self._is_waiting = True
        self._current_backend = 'ogr'
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the backend indicator UI."""
        if not HAS_QGIS:
            return
        
        self.setObjectName("label_backend_indicator")
        self.setCursor(Qt.PointingHandCursor)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumWidth(40)
        self.setMaximumHeight(20)
        
        # Initial waiting state
        self.set_waiting_state()
    
    def mousePressEvent(self, event):
        """Handle click to show backend menu or trigger reload."""
        if not HAS_QGIS:
            return
        
        # If in waiting state, trigger reload
        if self._is_waiting:
            logger.info("Backend indicator clicked in waiting state - triggering reload")
            self.reloadRequested.emit()
            return
        
        # Get current layer
        current_layer = None
        if self._get_current_layer:
            current_layer = self._get_current_layer()
        
        if not current_layer:
            logger.info("Backend indicator clicked with no current layer - triggering reload")
            self.reloadRequested.emit()
            return
        
        self._show_backend_menu(current_layer)
    
    def _show_backend_menu(self, current_layer):
        """Show the backend selection context menu."""
        if not HAS_QGIS:
            return
        
        # Get available backends
        available_backends = []
        if self._get_available_backends:
            available_backends = self._get_available_backends(current_layer)
        
        if not available_backends:
            logger.warning("No alternative backends available for this layer")
            return
        
        menu = QMenu(self)
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
        
        # Get current forced backend
        layer_id = current_layer.id()
        current_forced = self._forced_backends.get(layer_id)
        
        # Add available backends
        for backend_type, backend_name, backend_icon in available_backends:
            action_text = f"{backend_icon} {backend_name}"
            if current_forced == backend_type:
                action_text += " ✓"
            action = menu.addAction(action_text)
            action.setData(('backend', backend_type))
        
        menu.addSeparator()
        
        # Auto option
        auto_action = menu.addAction("⚙️ Auto (Default)")
        auto_action.setData(('backend', None))
        if not current_forced:
            auto_action.setText(auto_action.text() + " ✓")
        
        menu.addSeparator()
        
        # Auto-select all
        auto_all_action = menu.addAction("🎯 Auto-select Optimal for All Layers")
        auto_all_action.setData(('action', 'auto_all'))
        
        # Force all layers
        menu.addSeparator()
        current_backend = self._current_backend
        if self._detect_backend:
            current_backend = self._detect_backend(current_layer)
        
        backend_name = current_backend.upper() if current_backend else "CURRENT"
        force_all_action = menu.addAction(f"🔒 Force {backend_name} for All Layers")
        force_all_action.setData(('action', 'force_all'))
        
        # Show menu
        selected_action = menu.exec_(QCursor.pos())
        
        if selected_action:
            self._handle_menu_action(selected_action.data(), current_layer)
    
    def _handle_menu_action(self, action_data, current_layer):
        """Handle menu action selection."""
        if not action_data:
            return
        
        action_type, value = action_data
        layer_id = current_layer.id()
        
        if action_type == 'backend':
            self.set_forced_backend(layer_id, value)
            if value:
                self.update_for_backend(value)
            else:
                # Auto - detect backend
                if self._detect_backend:
                    detected = self._detect_backend(current_layer)
                    self.update_for_backend(detected)
            self.backendChanged.emit(layer_id, value or '')
        
        elif action_type == 'action':
            if value == 'auto_all':
                self.autoSelectRequested.emit()
            elif value == 'force_all':
                current_backend = self._current_backend
                if self._detect_backend:
                    current_backend = self._detect_backend(current_layer)
                self.backendForAllChanged.emit(current_backend)
    
    def set_waiting_state(self):
        """Set indicator to waiting state (no layers loaded)."""
        self._is_waiting = True
        self.setText("...")
        self.setToolTip("Click to reload layers")
        
        style = """
            QLabel#label_backend_indicator {
                color: white;
                font-size: 9pt;
                font-weight: 600;
                padding: 3px 10px;
                border-radius: 12px;
                border: none;
                background-color: #95a5a6;
            }
            QLabel#label_backend_indicator:hover {
                background-color: #7f8c8d;
            }
        """
        self.setStyleSheet(style)
    
    def update_for_backend(self, backend_type: str):
        """
        Update indicator display for a specific backend.
        
        Args:
            backend_type: Backend type ('postgresql', 'spatialite', 'ogr', etc.)
        """
        if not HAS_QGIS:
            return
        
        self._is_waiting = False
        self._current_backend = backend_type
        
        config = BACKEND_CONFIG.get(backend_type, BACKEND_CONFIG['unknown'])
        
        self.setText(backend_type.upper() if backend_type else "AUTO")
        self.setToolTip(
            f"Backend: {config['name']}\n"
            f"Click to change backend"
        )
        
        style = f"""
            QLabel#label_backend_indicator {{
                color: white;
                font-size: 9pt;
                font-weight: 600;
                padding: 3px 10px;
                border-radius: 12px;
                border: none;
                background-color: {config['color']};
            }}
            QLabel#label_backend_indicator:hover {{
                background-color: {config['hover_color']};
            }}
        """
        self.setStyleSheet(style)
        self.adjustSize()
    
    def update_for_layer(self, layer):
        """
        Update indicator for a specific layer.
        
        Args:
            layer: QGIS vector layer
        """
        if not layer:
            self.set_waiting_state()
            return
        
        # Check for forced backend
        layer_id = layer.id()
        if layer_id in self._forced_backends:
            backend = self._forced_backends[layer_id]
        elif self._detect_backend:
            backend = self._detect_backend(layer)
        else:
            backend = 'ogr'
        
        self.update_for_backend(backend)
    
    def set_forced_backend(self, layer_id: str, backend_type: Optional[str]):
        """
        Set or clear forced backend for a layer.
        
        Args:
            layer_id: Layer ID
            backend_type: Backend type or None to clear
        """
        if backend_type:
            self._forced_backends[layer_id] = backend_type
        elif layer_id in self._forced_backends:
            del self._forced_backends[layer_id]
    
    def get_forced_backend(self, layer_id: str) -> Optional[str]:
        """
        Get forced backend for a layer.
        
        Args:
            layer_id: Layer ID
        
        Returns:
            Forced backend type or None
        """
        return self._forced_backends.get(layer_id)
    
    def clear_forced_backends(self):
        """Clear all forced backend preferences."""
        self._forced_backends.clear()
    
    def get_forced_backends(self) -> Dict[str, str]:
        """Get all forced backend preferences."""
        return self._forced_backends.copy()
    
    def set_forced_backends(self, backends: Dict[str, str]):
        """Set forced backend preferences."""
        self._forced_backends = backends.copy()
    
    @property
    def current_backend(self) -> str:
        """Get current displayed backend."""
        return self._current_backend
    
    @property
    def is_waiting(self) -> bool:
        """Check if indicator is in waiting state."""
        return self._is_waiting
    
    def set_current_backend(self, backend_type: str):
        """
        Set current backend - convenience method.
        
        Args:
            backend_type: Backend type string
        """
        self._current_backend = backend_type
        if HAS_QGIS:
            self.update_for_backend(backend_type)


def get_available_backends_for_layer(layer, postgresql_available: bool = False) -> List[Tuple[str, str, str]]:
    """
    Get list of available backends for a layer.
    
    This is a standalone helper function that can be used without the widget.
    
    Args:
        layer: QGIS vector layer
        postgresql_available: Whether psycopg2 is available
    
    Returns:
        List of tuples: (backend_type, backend_name, backend_icon)
    """
    if not layer:
        return []
    
    available = []
    
    try:
        provider_type = layer.providerType()
        source = layer.source().lower()
    except (RuntimeError, AttributeError):
        return [('ogr', 'OGR', '📁')]
    
    # PostgreSQL backend
    if provider_type == 'postgres' and postgresql_available:
        available.append(('postgresql', 'PostgreSQL', '🐘'))
    
    # Spatialite backend
    if provider_type in ['spatialite', 'ogr']:
        if 'gpkg' in source or 'sqlite' in source or provider_type == 'spatialite':
            available.append(('spatialite', 'Spatialite', '💾'))
    
    # OGR is always available
    available.append(('ogr', 'OGR', '📁'))
    
    return available


def detect_backend_for_layer(layer, forced_backends: Dict[str, str] = None,
                              postgresql_available: bool = False) -> str:
    """
    Detect which backend to use for a layer.
    
    This is a standalone helper function.
    
    Args:
        layer: QGIS vector layer
        forced_backends: Dict of layer_id -> forced backend
        postgresql_available: Whether psycopg2 is available
    
    Returns:
        Backend type string
    """
    if not layer:
        return 'ogr'
    
    try:
        layer_id = layer.id()
        provider_type = layer.providerType()
    except (RuntimeError, AttributeError):
        return 'ogr'
    
    # Check forced backend first
    if forced_backends and layer_id in forced_backends:
        return forced_backends[layer_id]
    
    # Auto-detection
    if provider_type == 'postgres' and postgresql_available:
        return 'postgresql'
    elif provider_type == 'spatialite':
        return 'spatialite'
    else:
        return 'ogr'
