"""
Repository Port Interfaces.

Abstract interfaces for data access repositories.
Implements the Repository pattern from DDD.

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.
"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, TypeVar, Generic
from datetime import datetime


# Type variable for generic repository
T = TypeVar('T')
ID = TypeVar('ID')


class RepositoryPort(ABC, Generic[T, ID]):
    """
    Generic repository interface.
    
    Base interface for all repositories following the Repository pattern.
    Concrete repositories provide data access without exposing
    storage details to the domain layer.
    """
    
    @abstractmethod
    def get_by_id(self, entity_id: ID) -> Optional[T]:
        """
        Get entity by ID.
        
        Args:
            entity_id: Unique entity identifier
            
        Returns:
            Entity if found, None otherwise
        """
    
    @abstractmethod
    def get_all(self) -> List[T]:
        """
        Get all entities.
        
        Returns:
            List of all entities
        """
    
    @abstractmethod
    def save(self, entity: T) -> ID:
        """
        Save entity (create or update).
        
        Args:
            entity: Entity to save
            
        Returns:
            Entity ID
        """
    
    @abstractmethod
    def delete(self, entity_id: ID) -> bool:
        """
        Delete entity by ID.
        
        Args:
            entity_id: Entity ID to delete
            
        Returns:
            True if entity was deleted
        """
    
    @abstractmethod
    def exists(self, entity_id: ID) -> bool:
        """
        Check if entity exists.
        
        Args:
            entity_id: Entity ID to check
            
        Returns:
            True if entity exists
        """


class LayerRepositoryPort(ABC):
    """
    Interface for QGIS layer access.
    
    Provides abstraction over QgsProject and QgsVectorLayer
    to allow the core domain to work with layers without
    direct QGIS dependencies.
    """

    @abstractmethod
    def get_layer_info(self, layer_id: str) -> Optional['LayerInfo']:
        """
        Get layer information by ID.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            LayerInfo if layer exists, None otherwise
        """

    @abstractmethod
    def get_all_vector_layers(self) -> List['LayerInfo']:
        """
        Get all vector layers in project.
        
        Returns:
            List of LayerInfo for all vector layers
        """

    @abstractmethod
    def get_layers_by_provider(
        self, 
        provider_type: 'ProviderType'
    ) -> List['LayerInfo']:
        """
        Get layers filtered by provider type.
        
        Args:
            provider_type: Provider type to filter by
            
        Returns:
            List of LayerInfo matching the provider type
        """

    @abstractmethod
    def apply_filter(self, layer_id: str, subset_string: str) -> bool:
        """
        Apply subset string filter to layer.
        
        Args:
            layer_id: QGIS layer ID
            subset_string: SQL WHERE clause
            
        Returns:
            True if filter was applied successfully
        """

    @abstractmethod
    def clear_filter(self, layer_id: str) -> bool:
        """
        Clear filter from layer.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            True if filter was cleared successfully
        """

    @abstractmethod
    def refresh_layer(self, layer_id: str) -> bool:
        """
        Refresh layer display.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            True if layer was refreshed successfully
        """

    @abstractmethod
    def get_feature_count(self, layer_id: str) -> int:
        """
        Get feature count for layer.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            Number of features, -1 if unknown
        """

    @abstractmethod
    def get_current_filter(self, layer_id: str) -> Optional[str]:
        """
        Get current subset string filter.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            Current filter string, None if no filter
        """

    def get_filterable_layers(self) -> List['LayerInfo']:
        """
        Get layers that can be filtered.
        
        Returns:
            List of layers that support subset filtering
        """
        # Default implementation - all vector layers
        return self.get_all_vector_layers()


class FavoritesRepositoryPort(ABC):
    """
    Interface for favorites persistence.
    
    Handles saving and loading of favorite filter configurations.
    """

    @abstractmethod
    def get_all(self) -> List[Dict[str, Any]]:
        """
        Get all saved favorites.
        
        Returns:
            List of favorite dictionaries
        """

    @abstractmethod
    def get_by_id(self, favorite_id: str) -> Optional[Dict[str, Any]]:
        """
        Get favorite by ID.
        
        Args:
            favorite_id: Unique favorite identifier
            
        Returns:
            Favorite dictionary if found, None otherwise
        """

    @abstractmethod
    def save(self, favorite: Dict[str, Any]) -> str:
        """
        Save a favorite.
        
        Args:
            favorite: Favorite data dictionary
            
        Returns:
            Generated or existing ID
        """

    @abstractmethod
    def delete(self, favorite_id: str) -> bool:
        """
        Delete a favorite by ID.
        
        Args:
            favorite_id: Favorite ID to delete
            
        Returns:
            True if favorite was deleted
        """

    @abstractmethod
    def update(self, favorite_id: str, data: Dict[str, Any]) -> bool:
        """
        Update an existing favorite.
        
        Args:
            favorite_id: Favorite ID to update
            data: New data dictionary
            
        Returns:
            True if favorite was updated
        """

    def get_by_layer(self, layer_id: str) -> List[Dict[str, Any]]:
        """
        Get favorites for a specific layer.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            List of favorites for the layer
        """
        all_favorites = self.get_all()
        return [f for f in all_favorites if f.get('layer_id') == layer_id]

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get favorite by name.
        
        Args:
            name: Favorite name
            
        Returns:
            Favorite if found, None otherwise
        """
        all_favorites = self.get_all()
        for f in all_favorites:
            if f.get('name') == name:
                return f
        return None


class ConfigRepositoryPort(ABC):
    """
    Interface for configuration persistence.
    
    Handles loading and saving of plugin configuration.
    """

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """
        Load entire configuration.
        
        Returns:
            Configuration dictionary
        """

    @abstractmethod
    def save(self, config: Dict[str, Any]) -> bool:
        """
        Save entire configuration.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            True if configuration was saved
        """

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key.
        
        Supports nested keys with dot notation: "section.subsection.key"
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """

    @abstractmethod
    def set(self, key: str, value: Any) -> bool:
        """
        Set configuration value.
        
        Supports nested keys with dot notation.
        
        Args:
            key: Configuration key
            value: Value to set
            
        Returns:
            True if value was set
        """

    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section.
        
        Args:
            section: Section name
            
        Returns:
            Section dictionary or empty dict
        """
        return self.get(section, {})

    def has_key(self, key: str) -> bool:
        """
        Check if configuration key exists.
        
        Args:
            key: Configuration key
            
        Returns:
            True if key exists
        """
        sentinel = object()
        return self.get(key, sentinel) is not sentinel


class HistoryRepositoryPort(ABC):
    """
    Interface for filter history persistence.
    
    Handles saving and loading of filter operation history
    for undo/redo functionality.
    """

    @abstractmethod
    def add_entry(
        self,
        layer_id: str,
        expression: str,
        feature_ids: List[int],
        timestamp: Optional[datetime] = None
    ) -> str:
        """
        Add history entry.
        
        Args:
            layer_id: QGIS layer ID
            expression: Filter expression used
            feature_ids: Resulting feature IDs
            timestamp: Optional timestamp (defaults to now)
            
        Returns:
            Entry ID
        """

    @abstractmethod
    def get_history(
        self, 
        layer_id: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get history entries.
        
        Args:
            layer_id: Optional layer ID filter
            limit: Maximum entries to return
            
        Returns:
            List of history entries (newest first)
        """

    @abstractmethod
    def get_entry(self, entry_id: str) -> Optional[Dict[str, Any]]:
        """
        Get specific history entry.
        
        Args:
            entry_id: Entry ID
            
        Returns:
            Entry dictionary if found
        """

    @abstractmethod
    def clear_history(self, layer_id: Optional[str] = None) -> int:
        """
        Clear history entries.
        
        Args:
            layer_id: Optional layer ID to clear (None = all)
            
        Returns:
            Number of entries cleared
        """

    @abstractmethod
    def get_undo_entry(self, layer_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the previous entry for undo.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            Previous entry or None if at beginning
        """

    @abstractmethod
    def get_redo_entry(self, layer_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the next entry for redo.
        
        Args:
            layer_id: QGIS layer ID
            
        Returns:
            Next entry or None if at end
        """


# Type hints for forward references
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..domain import LayerInfo, ProviderType
