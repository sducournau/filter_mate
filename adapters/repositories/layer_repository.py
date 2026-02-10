# -*- coding: utf-8 -*-
"""
QGIS Layer Repository.

Provides access to QGIS layers for the domain layer.
This adapter bridges QGIS-specific code to the core ports.
"""
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Check if QGIS is available
try:
    from qgis.core import QgsProject, QgsVectorLayer
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsProject = None
    QgsVectorLayer = None


class QGISLayerRepository:
    """
    Repository for accessing QGIS layers.

    Provides a clean interface for the domain layer to access
    QGIS layers without direct QGIS dependencies.
    """

    def __init__(self):
        """Initialize the repository."""
        self._cache: Dict[str, Any] = {}

    def get_layer(self, layer_id: str) -> Optional[Any]:
        """
        Get a layer by ID.

        Args:
            layer_id: QGIS layer ID

        Returns:
            QgsVectorLayer or None
        """
        if not QGIS_AVAILABLE:
            return None

        try:
            project = QgsProject.instance()
            layer = project.mapLayer(layer_id)
            if isinstance(layer, QgsVectorLayer):
                return layer
        except Exception as e:
            logger.warning(f"Failed to get layer {layer_id}: {e}")

        return None

    def get_layer_by_name(self, name: str) -> Optional[Any]:
        """
        Get a layer by name.

        Args:
            name: Layer name

        Returns:
            QgsVectorLayer or None (first match)
        """
        if not QGIS_AVAILABLE:
            return None

        try:
            project = QgsProject.instance()
            layers = project.mapLayersByName(name)
            for layer in layers:
                if isinstance(layer, QgsVectorLayer):
                    return layer
        except Exception as e:
            logger.warning(f"Failed to get layer by name {name}: {e}")

        return None

    def get_all_vector_layers(self) -> List[Any]:
        """
        Get all vector layers in the project.

        Returns:
            List of QgsVectorLayer
        """
        if not QGIS_AVAILABLE:
            return []

        try:
            project = QgsProject.instance()
            return [
                layer for layer in project.mapLayers().values()
                if isinstance(layer, QgsVectorLayer)
            ]
        except Exception as e:
            logger.warning(f"Failed to get vector layers: {e}")
            return []

    def layer_exists(self, layer_id: str) -> bool:
        """Check if a layer exists."""
        return self.get_layer(layer_id) is not None

    def get_layer_info(self, layer_id: str) -> Optional[Any]:
        """
        Get layer information by ID.

        Args:
            layer_id: QGIS layer ID

        Returns:
            LayerInfo if layer exists, None otherwise
        """
        layer = self.get_layer(layer_id)
        if layer is None:
            return None

        try:
            from ..app_bridge import layer_info_from_qgis_layer
            return layer_info_from_qgis_layer(layer)
        except Exception as e:
            logger.warning(f"Failed to get layer info for {layer_id}: {e}")
            return None

    def get_layers_by_provider(self, provider_type: Any) -> List[Any]:
        """
        Get layers filtered by provider type.

        Args:
            provider_type: Provider type to filter by

        Returns:
            List of LayerInfo matching the provider type
        """
        if not QGIS_AVAILABLE:
            return []

        try:
            from ..app_bridge import layer_info_from_qgis_layer

            layers = self.get_all_vector_layers()
            result = []
            for layer in layers:
                layer_info = layer_info_from_qgis_layer(layer)
                if layer_info.provider_type == provider_type:
                    result.append(layer_info)
            return result
        except Exception as e:
            logger.warning(f"Failed to get layers by provider: {e}")
            return []

    def clear_cache(self) -> None:
        """Clear the internal cache."""
        self._cache.clear()
