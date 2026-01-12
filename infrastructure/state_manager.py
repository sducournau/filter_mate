# -*- coding: utf-8 -*-
"""
State Management for FilterMate Plugin.

This module provides centralized state management for layer properties and
project configuration, reducing tight coupling with the global PROJECT_LAYERS dictionary.

Migrated from before_migration/modules/state_manager.py for v4.0 hexagonal architecture.

Classes:
    LayerStateManager: Manages layer-specific state and properties
    ProjectStateManager: Manages project-level configuration and state
"""

from typing import Dict, List, Optional, Any, Tuple
import logging
import copy

try:
    from qgis.core import QgsVectorLayer
except ImportError:
    QgsVectorLayer = None

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
        """
        if layer_id in self._layers:
            logger.warning(f"Layer {layer_id} already exists in state")
            return False
        
        if not self._validate_layer_structure(layer_properties):
            logger.error(f"Invalid layer properties structure for {layer_id}")
            return False
        
        self._layers[layer_id] = copy.deepcopy(layer_properties)
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
            value: New property value
        
        Returns:
            True if property was updated, False if layer/group not found
        """
        if layer_id not in self._layers:
            logger.warning(f"Cannot update property - layer {layer_id} not found")
            return False
        
        layer_props = self._layers[layer_id]
        if group not in layer_props:
            layer_props[group] = {}
        
        layer_props[group][key] = value
        logger.debug(f"Updated {layer_id}.{group}.{key} = {value}")
        return True
    
    def get_all_layer_ids(self) -> List[str]:
        """
        Get list of all managed layer IDs.
        
        Returns:
            List of layer ID strings
        """
        return list(self._layers.keys())
    
    def clear(self) -> None:
        """Clear all layer state."""
        self._layers.clear()
        logger.debug("Cleared all layer state")
    
    def _validate_layer_structure(self, layer_properties: Dict) -> bool:
        """
        Validate that layer properties have expected structure.
        
        Args:
            layer_properties: Properties dictionary to validate
            
        Returns:
            True if structure is valid
        """
        if not isinstance(layer_properties, dict):
            return False
        
        # Minimal validation - allow flexible structure
        return True
    
    def get_layer_count(self) -> int:
        """Get count of managed layers."""
        return len(self._layers)
    
    def update_layer_properties(self, layer_id: str, properties: Dict) -> bool:
        """
        Replace all properties for a layer.
        
        Args:
            layer_id: Layer identifier
            properties: New properties dictionary
            
        Returns:
            True if successful
        """
        if layer_id not in self._layers:
            return self.add_layer(layer_id, properties)
        
        self._layers[layer_id] = copy.deepcopy(properties)
        return True


class ProjectStateManager:
    """
    Manages project-level configuration and state.
    
    Centralizes access to project-wide settings, data source connections,
    and global plugin state.
    
    Attributes:
        _config: Project configuration dictionary
        _layer_manager: Associated LayerStateManager
    """
    
    def __init__(self, layer_manager: Optional[LayerStateManager] = None):
        """
        Initialize project state manager.
        
        Args:
            layer_manager: Optional LayerStateManager to associate
        """
        self._config: Dict[str, Any] = {}
        self._layer_manager = layer_manager or LayerStateManager()
        self._data_sources: Dict[str, Any] = {}
        self._current_layer_id: Optional[str] = None
    
    @property
    def layer_manager(self) -> LayerStateManager:
        """Get associated layer manager."""
        return self._layer_manager
    
    def set_current_layer(self, layer_id: str) -> None:
        """
        Set the current active layer ID.
        
        Args:
            layer_id: Layer identifier
        """
        self._current_layer_id = layer_id
        logger.debug(f"Current layer set to: {layer_id}")
    
    def get_current_layer_id(self) -> Optional[str]:
        """Get current active layer ID."""
        return self._current_layer_id
    
    def get_current_layer_properties(self) -> Optional[Dict]:
        """Get properties of current active layer."""
        if self._current_layer_id:
            return self._layer_manager.get_layer_properties(self._current_layer_id)
        return None
    
    def set_config(self, key: str, value: Any) -> None:
        """
        Set a project configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config[key] = value
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        Get a project configuration value.
        
        Args:
            key: Configuration key
            default: Default value if not found
            
        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)
    
    def register_data_source(self, source_id: str, connection: Any) -> None:
        """
        Register a data source connection.
        
        Args:
            source_id: Unique source identifier
            connection: Connection object
        """
        self._data_sources[source_id] = connection
        logger.debug(f"Registered data source: {source_id}")
    
    def get_data_source(self, source_id: str) -> Optional[Any]:
        """
        Get a registered data source connection.
        
        Args:
            source_id: Source identifier
            
        Returns:
            Connection object or None
        """
        return self._data_sources.get(source_id)
    
    def unregister_data_source(self, source_id: str) -> bool:
        """
        Unregister a data source connection.
        
        Args:
            source_id: Source identifier
            
        Returns:
            True if source was unregistered
        """
        if source_id in self._data_sources:
            del self._data_sources[source_id]
            logger.debug(f"Unregistered data source: {source_id}")
            return True
        return False
    
    def clear(self) -> None:
        """Clear all project state."""
        self._config.clear()
        self._data_sources.clear()
        self._layer_manager.clear()
        self._current_layer_id = None
        logger.debug("Cleared all project state")
    
    def get_state_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current project state.
        
        Returns:
            Dictionary with state summary
        """
        return {
            'layer_count': self._layer_manager.get_layer_count(),
            'current_layer_id': self._current_layer_id,
            'data_source_count': len(self._data_sources),
            'config_keys': list(self._config.keys()),
        }


# Singleton instances for global access
_layer_state_manager: Optional[LayerStateManager] = None
_project_state_manager: Optional[ProjectStateManager] = None


def get_layer_state_manager() -> LayerStateManager:
    """
    Get the singleton LayerStateManager instance.
    
    Returns:
        LayerStateManager singleton
    """
    global _layer_state_manager
    if _layer_state_manager is None:
        _layer_state_manager = LayerStateManager()
    return _layer_state_manager


def get_project_state_manager() -> ProjectStateManager:
    """
    Get the singleton ProjectStateManager instance.
    
    Returns:
        ProjectStateManager singleton
    """
    global _project_state_manager
    if _project_state_manager is None:
        _project_state_manager = ProjectStateManager(get_layer_state_manager())
    return _project_state_manager


def reset_state_managers() -> None:
    """Reset all state managers (useful for testing)."""
    global _layer_state_manager, _project_state_manager
    if _project_state_manager:
        _project_state_manager.clear()
    if _layer_state_manager:
        _layer_state_manager.clear()
    _layer_state_manager = None
    _project_state_manager = None


__all__ = [
    'LayerStateManager',
    'ProjectStateManager',
    'get_layer_state_manager',
    'get_project_state_manager',
    'reset_state_managers',
]
