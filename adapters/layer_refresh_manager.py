"""
Layer Refresh Manager
=====================

Extracted from filter_mate_app.py (MIG-024) for God Class reduction.

Handles layer and canvas refresh operations with:
- Stabilization delays for Spatialite/OGR
- GDAL error suppression
- Performance optimization for large layers

Author: FilterMate Team
Version: 2.8.6
"""

from typing import Optional, Callable

try:
    from qgis.core import QgsVectorLayer
    from qgis.PyQt.QtCore import QTimer
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QTimer = None

try:
    from infrastructure.logging import get_logger
except ImportError:
    import logging
    def get_logger(name):
        return logging.getLogger(name)

try:
    from infrastructure.utils.gdal_error_handler import GdalErrorHandler
except ImportError:
    # Mock for testing
    class GdalErrorHandler:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

logger = get_logger(__name__)

# Default constants (can be overridden)
DEFAULT_STABILIZATION_MS = 200
DEFAULT_UPDATE_EXTENTS_THRESHOLD = 50000


class LayerRefreshManager:
    """
    Manages layer refresh operations with stabilization and optimization.
    
    Features:
    - Non-blocking stabilization delays for file-based databases
    - GDAL error suppression during refresh
    - Performance optimization for large layers
    - Configurable thresholds
    """
    
    def __init__(
        self,
        get_iface: Callable,
        stabilization_ms: int = DEFAULT_STABILIZATION_MS,
        update_extents_threshold: int = DEFAULT_UPDATE_EXTENTS_THRESHOLD
    ):
        """
        Initialize LayerRefreshManager.
        
        Args:
            get_iface: Callback to get QGIS iface instance
            stabilization_ms: Delay in ms for Spatialite/OGR stabilization
            update_extents_threshold: Feature count threshold for updateExtents
        """
        self._get_iface = get_iface
        self._stabilization_ms = stabilization_ms
        self._update_extents_threshold = update_extents_threshold
    
    def refresh_layer_and_canvas(
        self,
        layer: 'QgsVectorLayer',
        force_immediate: bool = False
    ) -> None:
        """
        Refresh layer and map canvas with stabilization for file-based databases.
        
        For Spatialite/OGR layers, adds a brief stabilization delay before refresh
        to allow SQLite connections to fully close. This prevents transient 
        "unable to open database file" errors during concurrent access.
        
        Args:
            layer: Layer to refresh
            force_immediate: Skip stabilization delay even for file-based layers
        """
        if not layer:
            return
        
        provider_type = layer.providerType() if layer else None
        needs_stabilization = (
            not force_immediate and 
            provider_type in ('spatialite', 'ogr')
        )
        
        if needs_stabilization and QGIS_AVAILABLE and QTimer:
            # Non-blocking stabilization delay
            QTimer.singleShot(self._stabilization_ms, lambda: self._do_refresh(layer))
        else:
            # Immediate refresh
            self._do_refresh(layer)
    
    def _do_refresh(self, layer: 'QgsVectorLayer') -> None:
        """
        Perform the actual layer refresh.
        
        Args:
            layer: Layer to refresh
        """
        try:
            # Use GDAL error handler to suppress transient SQLite warnings
            with GdalErrorHandler():
                # Skip updateExtents for large layers to prevent freeze
                feature_count = layer.featureCount() if layer else 0
                if 0 <= feature_count < self._update_extents_threshold:
                    layer.updateExtents()
                # else: skip expensive updateExtents for very large layers
                
                layer.triggerRepaint()
                
                # Refresh canvas
                iface = self._get_iface()
                if iface and hasattr(iface, 'mapCanvas'):
                    iface.mapCanvas().refresh()
                    
        except Exception as e:
            logger.warning(f"_do_refresh: refresh failed: {e}")
    
    def refresh_multiple_layers(
        self,
        layers: list,
        refresh_canvas: bool = True
    ) -> None:
        """
        Refresh multiple layers efficiently.
        
        Args:
            layers: List of layers to refresh
            refresh_canvas: Whether to refresh canvas after layer updates
        """
        if not layers:
            return
        
        for layer in layers:
            if layer:
                try:
                    layer.updateExtents()
                    layer.triggerRepaint()
                except Exception as e:
                    logger.warning(f"refresh_multiple_layers: failed for layer: {e}")
        
        if refresh_canvas:
            iface = self._get_iface()
            if iface and hasattr(iface, 'mapCanvas'):
                iface.mapCanvas().refreshAllLayers()
                iface.mapCanvas().refresh()
    
    def zoom_to_layer_extent(
        self,
        layer: 'QgsVectorLayer',
        use_filtered_extent: bool = True
    ) -> None:
        """
        Zoom map canvas to layer extent.
        
        Args:
            layer: Layer to zoom to
            use_filtered_extent: Whether to use filtered extent (default True)
        """
        if not layer:
            return
        
        try:
            layer.updateExtents()  # Force recalculation
            extent = layer.extent()
            
            if extent and not extent.isEmpty():
                iface = self._get_iface()
                if iface and hasattr(iface, 'mapCanvas'):
                    iface.mapCanvas().zoomToFeatureExtent(extent)
            else:
                # Just refresh if extent is empty
                iface = self._get_iface()
                if iface and hasattr(iface, 'mapCanvas'):
                    iface.mapCanvas().refresh()
                    
        except Exception as e:
            logger.warning(f"zoom_to_layer_extent: failed: {e}")


class TaskCompletionMessenger:
    """
    Handles task completion messages for filter operations.
    
    Separated from FilterMateApp to reduce coupling and improve testability.
    """
    
    def __init__(
        self,
        show_success_callback: Callable,
        show_info_callback: Callable,
        should_show_message_callback: Optional[Callable[[str], bool]] = None
    ):
        """
        Initialize TaskCompletionMessenger.
        
        Args:
            show_success_callback: Callback to show success message with backend info
            show_info_callback: Callback to show info message
            should_show_message_callback: Optional callback to check if message should show
        """
        self._show_success = show_success_callback
        self._show_info = show_info_callback
        self._should_show = should_show_message_callback or (lambda _: True)
    
    def show_task_completion(
        self,
        task_name: str,
        layer: 'QgsVectorLayer',
        provider_type: str,
        layer_count: int,
        is_fallback: bool = False
    ) -> None:
        """
        Show success message with backend info and feature counts.
        
        Args:
            task_name: Name of completed task ('filter', 'unfilter', 'reset')
            layer: Layer with results
            provider_type: Backend provider type
            layer_count: Number of layers affected
            is_fallback: True if OGR was used as fallback
        """
        feature_count = layer.featureCount() if layer else 0
        
        # Show backend success message
        self._show_success(provider_type, task_name, layer_count, is_fallback)
        
        # Show feature count if configured
        if self._should_show('filter_count'):
            if task_name == 'filter':
                self._show_info(f"{feature_count:,} features visible in main layer")
            elif task_name == 'unfilter':
                self._show_info(f"All filters cleared - {feature_count:,} features visible in main layer")
            elif task_name == 'reset':
                self._show_info(f"{feature_count:,} features visible in main layer")
    
    def show_filter_applied(
        self,
        layer_name: str,
        feature_count: int,
        expression_preview: str
    ) -> None:
        """
        Show message when filter is applied.
        
        Args:
            layer_name: Name of filtered layer
            feature_count: Number of matching features
            expression_preview: Preview of filter expression
        """
        if self._should_show('filter_applied'):
            msg = f"Filter applied to '{layer_name}': {feature_count:,} features"
            if expression_preview:
                msg += f" ({expression_preview})"
            self._show_info(msg)
    
    def show_filter_cleared(self, layer_name: str, feature_count: int) -> None:
        """
        Show message when filter is cleared.
        
        Args:
            layer_name: Name of layer
            feature_count: Total features after clearing
        """
        if self._should_show('filter_cleared'):
            self._show_info(f"Filter cleared for '{layer_name}': {feature_count:,} features visible")
