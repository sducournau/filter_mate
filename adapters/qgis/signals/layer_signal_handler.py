"""
Layer Signal Handler for FilterMate.

Manages Qt signals specific to QGIS layers.
Extracted from filter_mate_dockwidget.py (lines 9702-9758, 10326-10437).

Story: MIG-085
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Dict, List, Callable, Optional, Set
import logging
import weakref

try:
    from qgis.core import QgsVectorLayer
except ImportError:
    QgsVectorLayer = None

if TYPE_CHECKING:
    from .signal_manager import SignalManager

logger = logging.getLogger(__name__)


class LayerSignalHandler:
    """
    Handler for layer-specific Qt signals.
    
    Manages the lifecycle of signal connections for vector layers:
    - Connects signals when a layer becomes current
    - Disconnects signals when layer changes or is removed
    - Tracks which layers have active connections
    
    Works with SignalManager for centralized tracking.
    
    Usage:
        handler = LayerSignalHandler(signal_manager=manager)
        handler.connect_layer_signals(layer)
        # ... layer is in use ...
        handler.disconnect_layer_signals(layer)
    """
    
    # Signals to connect for each layer
    LAYER_SIGNALS = [
        'subsetStringChanged',
        'featureAdded',
        'featureDeleted',
        'attributeValueChanged',
        'beforeEditingStarted',
        'editingStopped',
        'willBeDeleted',
    ]
    
    def __init__(
        self,
        signal_manager: Optional['SignalManager'] = None,
        on_subset_changed: Optional[Callable] = None,
        on_feature_added: Optional[Callable] = None,
        on_feature_deleted: Optional[Callable] = None,
        on_attribute_changed: Optional[Callable] = None,
        on_editing_started: Optional[Callable] = None,
        on_editing_stopped: Optional[Callable] = None,
        on_layer_deleted: Optional[Callable] = None,
    ) -> None:
        """
        Initialize the layer signal handler.
        
        Args:
            signal_manager: Central signal manager for tracking
            on_subset_changed: Handler for subsetStringChanged
            on_feature_added: Handler for featureAdded
            on_feature_deleted: Handler for featureDeleted
            on_attribute_changed: Handler for attributeValueChanged
            on_editing_started: Handler for beforeEditingStarted
            on_editing_stopped: Handler for editingStopped
            on_layer_deleted: Handler for willBeDeleted
        """
        self._signal_manager = signal_manager
        self._connected_layers: Dict[str, weakref.ref] = {}
        self._connection_ids: Dict[str, List[str]] = {}  # layer_id -> [conn_ids]
        
        # Custom handlers (can be overridden)
        self._custom_handlers = {
            'subsetStringChanged': on_subset_changed,
            'featureAdded': on_feature_added,
            'featureDeleted': on_feature_deleted,
            'attributeValueChanged': on_attribute_changed,
            'beforeEditingStarted': on_editing_started,
            'editingStopped': on_editing_stopped,
            'willBeDeleted': on_layer_deleted,
        }
        
        # Default handlers
        self._handlers = self._setup_default_handlers()
    
    def _setup_default_handlers(self) -> Dict[str, Callable]:
        """Setup default signal handlers with fallbacks."""
        handlers = {}
        
        for signal_name in self.LAYER_SIGNALS:
            custom = self._custom_handlers.get(signal_name)
            if custom:
                handlers[signal_name] = custom
            else:
                # Create default no-op handler
                handlers[signal_name] = self._create_default_handler(signal_name)
        
        return handlers
    
    def _create_default_handler(self, signal_name: str) -> Callable:
        """Create a default handler for a signal."""
        def handler(*args, **kwargs):
            logger.debug(f"Layer signal {signal_name} received")
        return handler
    
    def set_handler(self, signal_name: str, handler: Callable) -> None:
        """
        Set a custom handler for a signal.
        
        Args:
            signal_name: Name of the signal
            handler: Handler function
        """
        if signal_name in self.LAYER_SIGNALS:
            self._handlers[signal_name] = handler
            self._custom_handlers[signal_name] = handler
            logger.debug(f"Set custom handler for {signal_name}")
    
    def connect_layer_signals(self, layer) -> int:
        """
        Connect all signals for a layer.
        
        Args:
            layer: Vector layer to connect
        
        Returns:
            Number of signals connected
        """
        if not layer:
            return 0
        
        # Handle mock layers in tests
        layer_id = getattr(layer, 'id', lambda: str(id(layer)))()
        layer_name = getattr(layer, 'name', lambda: 'Unknown')()
        is_valid = getattr(layer, 'isValid', lambda: True)()
        
        if not is_valid:
            logger.warning(f"Cannot connect signals for invalid layer")
            return 0
        
        # Check if already connected
        if layer_id in self._connected_layers:
            logger.debug(f"Layer {layer_name} already connected")
            return 0
        
        connected = 0
        conn_ids = []
        
        for signal_name in self.LAYER_SIGNALS:
            signal = getattr(layer, signal_name, None)
            if signal is None:
                continue
            
            handler = self._handlers.get(signal_name)
            if handler is None:
                continue
            
            try:
                # Use signal manager if available
                if self._signal_manager:
                    full_name = f"layer_{layer_id}_{signal_name}"
                    conn_id = self._signal_manager.connect(
                        sender=layer,
                        signal_name=signal_name,
                        receiver=handler,
                        context='layer_signals'
                    )
                    conn_ids.append(conn_id)
                else:
                    # Direct connection
                    signal.connect(handler)
                
                connected += 1
                
            except Exception as e:
                logger.warning(f"Failed to connect {signal_name}: {e}")
        
        if connected > 0:
            self._connected_layers[layer_id] = weakref.ref(layer)
            self._connection_ids[layer_id] = conn_ids
            logger.debug(f"Connected {connected} signals for layer {layer_name}")
        
        return connected
    
    def disconnect_layer_signals(self, layer) -> int:
        """
        Disconnect all signals for a layer.
        
        Args:
            layer: Vector layer to disconnect
        
        Returns:
            Number of signals disconnected
        """
        if not layer:
            return 0
        
        layer_id = getattr(layer, 'id', lambda: str(id(layer)))()
        
        if layer_id not in self._connected_layers:
            return 0
        
        disconnected = 0
        
        # Use signal manager if available
        if self._signal_manager and layer_id in self._connection_ids:
            for conn_id in self._connection_ids[layer_id]:
                if self._signal_manager.disconnect(conn_id):
                    disconnected += 1
        else:
            # Direct disconnection
            for signal_name in self.LAYER_SIGNALS:
                signal = getattr(layer, signal_name, None)
                handler = self._handlers.get(signal_name)
                
                if signal and handler:
                    try:
                        signal.disconnect(handler)
                        disconnected += 1
                    except (TypeError, RuntimeError):
                        pass
        
        # Clean up tracking
        del self._connected_layers[layer_id]
        if layer_id in self._connection_ids:
            del self._connection_ids[layer_id]
        
        logger.debug(f"Disconnected {disconnected} signals from layer")
        
        return disconnected
    
    def reconnect_layer_signals(self, layer) -> None:
        """
        Force reconnect all signals for a layer.
        
        Useful when signal state is uncertain.
        
        Args:
            layer: Vector layer to reconnect
        """
        self.disconnect_layer_signals(layer)
        self.connect_layer_signals(layer)
    
    def disconnect_all(self) -> int:
        """
        Disconnect all layer signals.
        
        Returns:
            Total number of signals disconnected
        """
        total = 0
        
        for layer_id in list(self._connected_layers.keys()):
            layer_ref = self._connected_layers[layer_id]
            layer = layer_ref() if layer_ref else None
            
            if layer:
                total += self.disconnect_layer_signals(layer)
            else:
                # Layer was deleted, just clean up tracking
                if self._signal_manager and layer_id in self._connection_ids:
                    for conn_id in self._connection_ids[layer_id]:
                        self._signal_manager.disconnect(conn_id)
                del self._connected_layers[layer_id]
                if layer_id in self._connection_ids:
                    del self._connection_ids[layer_id]
        
        return total
    
    def is_layer_connected(self, layer) -> bool:
        """
        Check if a layer has connected signals.
        
        Args:
            layer: Layer to check
        
        Returns:
            True if layer has active signal connections
        """
        if not layer:
            return False
        
        layer_id = getattr(layer, 'id', lambda: str(id(layer)))()
        return layer_id in self._connected_layers
    
    def get_connected_layers(self) -> List[str]:
        """
        Get list of connected layer IDs.
        
        Returns:
            List of layer IDs with active connections
        """
        return list(self._connected_layers.keys())
    
    def get_connected_layer_count(self) -> int:
        """
        Get number of connected layers.
        
        Returns:
            Number of layers with active connections
        """
        return len(self._connected_layers)
    
    def prune_dead_layers(self) -> int:
        """
        Remove connections for deleted layers.
        
        Returns:
            Number of dead layer connections removed
        """
        pruned = 0
        
        for layer_id in list(self._connected_layers.keys()):
            layer_ref = self._connected_layers[layer_id]
            if layer_ref is None or layer_ref() is None:
                # Layer was deleted
                if self._signal_manager and layer_id in self._connection_ids:
                    for conn_id in self._connection_ids[layer_id]:
                        self._signal_manager.disconnect(conn_id)
                
                del self._connected_layers[layer_id]
                if layer_id in self._connection_ids:
                    del self._connection_ids[layer_id]
                
                pruned += 1
        
        if pruned > 0:
            logger.debug(f"Pruned {pruned} dead layer connections")
        
        return pruned
    
    def cleanup(self) -> None:
        """
        Full cleanup - disconnect all and clear state.
        """
        self.disconnect_all()
        self._connected_layers.clear()
        self._connection_ids.clear()
        logger.debug("LayerSignalHandler cleaned up")
    
    def __len__(self) -> int:
        """Return number of connected layers."""
        return len(self._connected_layers)
    
    def __repr__(self) -> str:
        """String representation."""
        return f"<LayerSignalHandler: {len(self._connected_layers)} layers>"
