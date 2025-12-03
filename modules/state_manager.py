"""
State Management for FilterMate Plugin.

This module provides centralized state management for layer properties and
project configuration, reducing tight coupling with the global PROJECT_LAYERS dictionary.

Classes:
    LayerStateManager: Manages layer-specific state and properties
    ProjectStateManager: Manages project-level configuration and state

Author: FilterMate Development Team
License: GPL-3.0
"""

from typing import Dict, List, Optional, Any, Tuple
from qgis.core import QgsVectorLayer
import logging

logger = logging.getLogger(__name__)


class LayerStateManager:
    """
    Manages state and properties for individual layers.
    
    Provides a clean interface for accessing and modifying layer properties
    without directly manipulating the global PROJECT_LAYERS dictionary.
    
    Attributes:
        _layers: Internal dictionary storing layer properties
    
    Examples:
        >>> manager = LayerStateManager()
        >>> manager.add_layer(layer_id, layer_properties)
        >>> props = manager.get_layer_properties(layer_id)
        >>> manager.update_layer_property(layer_id, "exploring", "single_selection_expression", "id")
    """
    
    def __init__(self):
        """Initialize the layer state manager with empty state."""
        self._layers: Dict[str, Dict] = {}
    
    def add_layer(self, layer_id: str, layer_properties: Dict) -> bool:
        """
        Add a new layer to state management.
        
        Args:
            layer_id: Unique layer identifier
            layer_properties: Complete layer properties dictionary
        
        Returns:
            True if layer was added, False if layer already exists
        
        Notes:
            - Creates a deep copy of properties to prevent external modifications
            - Validates required property structure
        """
        if layer_id in self._layers:
            logger.warning(f"Layer {layer_id} already exists in state")
            return False
        
        # Validate basic structure
        if not self._validate_layer_structure(layer_properties):
            logger.error(f"Invalid layer properties structure for {layer_id}")
            return False
        
        self._layers[layer_id] = dict(layer_properties)
        logger.debug(f"Added layer {layer_id} to state")
        return True
    
    def remove_layer(self, layer_id: str) -> bool:
        """
        Remove a layer from state management.
        
        Args:
            layer_id: Layer identifier to remove
        
        Returns:
            True if layer was removed, False if layer not found
        """
        if layer_id not in self._layers:
            logger.warning(f"Layer {layer_id} not found in state")
            return False
        
        del self._layers[layer_id]
        logger.debug(f"Removed layer {layer_id} from state")
        return True
    
    def has_layer(self, layer_id: str) -> bool:
        """
        Check if a layer exists in state.
        
        Args:
            layer_id: Layer identifier
        
        Returns:
            True if layer exists, False otherwise
        """
        return layer_id in self._layers
    
    def get_layer_properties(self, layer_id: str) -> Optional[Dict]:
        """
        Get complete properties for a layer.
        
        Args:
            layer_id: Layer identifier
        
        Returns:
            Layer properties dictionary or None if not found
        """
        return self._layers.get(layer_id)
    
    def get_layer_property(
        self,
        layer_id: str,
        group: str,
        key: str,
        default: Any = None
    ) -> Any:
        """
        Get a specific property value for a layer.
        
        Args:
            layer_id: Layer identifier
            group: Property group ('infos', 'exploring', 'filtering')
            key: Property key within group
            default: Default value if property not found
        
        Returns:
            Property value or default if not found
        
        Examples:
            >>> value = manager.get_layer_property(
            ...     layer_id, "infos", "layer_name", "Unknown"
            ... )
        """
        if layer_id not in self._layers:
            return default
        
        layer_props = self._layers[layer_id]
        if group not in layer_props:
            return default
        
        return layer_props[group].get(key, default)
    
    def update_layer_property(
        self,
        layer_id: str,
        group: str,
        key: str,
        value: Any
    ) -> bool:
        """
        Update a specific property value for a layer.
        
        Args:
            layer_id: Layer identifier
            group: Property group ('infos', 'exploring', 'filtering')
            key: Property key within group
            value: New value to set
        
        Returns:
            True if property was updated, False if layer not found
        
        Examples:
            >>> manager.update_layer_property(
            ...     layer_id, "exploring", "is_tracking", True
            ... )
        """
        if layer_id not in self._layers:
            logger.warning(f"Cannot update property: layer {layer_id} not found")
            return False
        
        if group not in self._layers[layer_id]:
            self._layers[layer_id][group] = {}
        
        self._layers[layer_id][group][key] = value
        logger.debug(f"Updated {layer_id}.{group}.{key} = {value}")
        return True
    
    def update_layer_properties_batch(
        self,
        layer_id: str,
        updates: List[Tuple[str, str, Any]]
    ) -> int:
        """
        Update multiple properties in a single operation.
        
        Args:
            layer_id: Layer identifier
            updates: List of (group, key, value) tuples
        
        Returns:
            Number of properties successfully updated
        
        Examples:
            >>> updates = [
            ...     ("exploring", "is_tracking", True),
            ...     ("exploring", "is_linking", False),
            ...     ("filtering", "has_buffer_value", True)
            ... ]
            >>> count = manager.update_layer_properties_batch(layer_id, updates)
        """
        if layer_id not in self._layers:
            return 0
        
        count = 0
        for group, key, value in updates:
            if self.update_layer_property(layer_id, group, key, value):
                count += 1
        
        return count
    
    def get_all_layer_ids(self) -> List[str]:
        """
        Get list of all layer IDs in state.
        
        Returns:
            List of layer identifiers
        """
        return list(self._layers.keys())
    
    def get_layers_by_provider(self, provider_type: str) -> List[str]:
        """
        Get layer IDs filtered by provider type.
        
        Args:
            provider_type: Provider type ('postgresql', 'spatialite', 'ogr')
        
        Returns:
            List of layer IDs matching the provider type
        """
        matching = []
        for layer_id, props in self._layers.items():
            if props.get('infos', {}).get('layer_provider_type') == provider_type:
                matching.append(layer_id)
        return matching
    
    def get_layers_by_geometry_type(self, geometry_type: str) -> List[str]:
        """
        Get layer IDs filtered by geometry type.
        
        Args:
            geometry_type: Geometry type ('Point', 'LineString', 'Polygon', etc.)
        
        Returns:
            List of layer IDs matching the geometry type
        """
        matching = []
        for layer_id, props in self._layers.items():
            layer_geom = props.get('infos', {}).get('layer_geometry_type', '')
            if geometry_type.lower() in layer_geom.lower():
                matching.append(layer_id)
        return matching
    
    def clear(self):
        """Remove all layers from state."""
        self._layers.clear()
        logger.debug("Cleared all layers from state")
    
    def export_state(self) -> Dict:
        """
        Export complete state as dictionary.
        
        Returns:
            Dictionary containing all layer properties
        
        Notes:
            - Used for serialization/persistence
            - Can be used to restore state with import_state()
        """
        return dict(self._layers)
    
    def import_state(self, state: Dict):
        """
        Import state from dictionary.
        
        Args:
            state: Dictionary containing layer properties
        
        Notes:
            - Replaces current state completely
            - Validates each layer structure before importing
        """
        self._layers.clear()
        for layer_id, props in state.items():
            if self._validate_layer_structure(props):
                self._layers[layer_id] = dict(props)
            else:
                logger.warning(f"Skipped importing invalid layer {layer_id}")
    
    def _validate_layer_structure(self, layer_props: Dict) -> bool:
        """
        Validate that layer properties have required structure.
        
        Args:
            layer_props: Layer properties dictionary
        
        Returns:
            True if structure is valid, False otherwise
        """
        required_groups = ['infos', 'exploring', 'filtering']
        
        for group in required_groups:
            if group not in layer_props:
                logger.error(f"Missing required group: {group}")
                return False
            
            if not isinstance(layer_props[group], dict):
                logger.error(f"Group {group} must be a dictionary")
                return False
        
        return True


class ProjectStateManager:
    """
    Manages project-level state and configuration.
    
    Provides centralized access to project settings, datasources, and
    global configuration options.
    
    Attributes:
        _config: Project configuration dictionary
        _datasources: Project datasources dictionary
    
    Examples:
        >>> manager = ProjectStateManager()
        >>> manager.set_config("FILTER", "app_postgresql_temp_schema", "filtermate_temp")
        >>> schema = manager.get_config("FILTER", "app_postgresql_temp_schema")
    """
    
    def __init__(self):
        """Initialize project state manager with default configuration."""
        self._config: Dict = {}
        self._datasources: Dict = {}
    
    def set_config(self, group: str, key: str, value: Any):
        """
        Set a configuration value.
        
        Args:
            group: Configuration group
            key: Configuration key
            value: Configuration value
        """
        if group not in self._config:
            self._config[group] = {}
        self._config[group][key] = value
    
    def get_config(self, group: str, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.
        
        Args:
            group: Configuration group
            key: Configuration key
            default: Default value if not found
        
        Returns:
            Configuration value or default
        """
        if group not in self._config:
            return default
        return self._config[group].get(key, default)
    
    def add_datasource(self, source_type: str, source_id: str, connection: Any):
        """
        Add a datasource connection.
        
        Args:
            source_type: Type of datasource ('postgresql', 'spatialite', 'ogr')
            source_id: Unique identifier for this connection
            connection: Connection object
        """
        if source_type not in self._datasources:
            self._datasources[source_type] = {}
        self._datasources[source_type][source_id] = connection
    
    def get_datasource(self, source_type: str, source_id: str) -> Optional[Any]:
        """
        Get a datasource connection.
        
        Args:
            source_type: Type of datasource
            source_id: Connection identifier
        
        Returns:
            Connection object or None if not found
        """
        if source_type not in self._datasources:
            return None
        return self._datasources[source_type].get(source_id)
    
    def get_datasources_by_type(self, source_type: str) -> Dict:
        """
        Get all datasources of a specific type.
        
        Args:
            source_type: Type of datasource
        
        Returns:
            Dictionary of connections for that type
        """
        return self._datasources.get(source_type, {})
    
    def export_config(self) -> Dict:
        """Export configuration as dictionary."""
        return dict(self._config)
    
    def import_config(self, config: Dict):
        """Import configuration from dictionary."""
        self._config = dict(config)
