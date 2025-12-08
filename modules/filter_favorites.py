"""
Filter Favorites Module

Provides functionality for saving, loading, and managing filter configuration
favorites. Favorites allow users to save frequently-used filter configurations
and apply them across different projects and layers.

Features:
- Save current filter configuration as a favorite
- Apply favorites to layers (with smart layer matching)
- Export/import favorites to/from JSON files
- Search and filter favorites
- User-level and project-level favorites
- Usage tracking and statistics

Author: FilterMate Development Team
Date: December 2025
Version: 1.0
"""

import json
import os
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import uuid
from pathlib import Path

logger = logging.getLogger('FilterMate.Favorites')


class FilterFavorite:
    """
    Represents a saved filter configuration favorite.
    
    A favorite captures the filter configuration (expression, predicates, buffer settings)
    without being tied to specific layer IDs. This allows favorites to be portable
    across projects and shared between users.
    
    Attributes:
        id (str): Unique identifier for this favorite
        name (str): User-friendly name for the favorite
        description (str): Optional detailed description
        configuration (dict): Filter configuration settings
        created_at (datetime): When the favorite was created
        modified_at (datetime): When the favorite was last modified
        metadata (dict): Additional metadata (tags, author, usage stats, etc.)
    """
    
    def __init__(
        self,
        name: str,
        configuration: Dict[str, Any],
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
        favorite_id: Optional[str] = None
    ):
        """
        Initialize a filter favorite.
        
        Args:
            name: Display name for the favorite
            configuration: Filter configuration dictionary
            description: Optional description of what this favorite does
            metadata: Optional metadata (tags, author, etc.)
            favorite_id: Optional specific ID (used when deserializing)
        """
        self.id = favorite_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.configuration = configuration
        self.created_at = datetime.now()
        self.modified_at = datetime.now()
        self.metadata = metadata or {}
        
        # Initialize usage tracking if not present
        if 'usage_count' not in self.metadata:
            self.metadata['usage_count'] = 0
        if 'last_used' not in self.metadata:
            self.metadata['last_used'] = None
    
    def record_usage(self):
        """Record that this favorite was used."""
        self.metadata['usage_count'] = self.metadata.get('usage_count', 0) + 1
        self.metadata['last_used'] = datetime.now().isoformat()
        self.modified_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize favorite to dictionary for JSON export.
        
        Returns:
            Dict representation of the favorite
        """
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'configuration': self.configuration,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FilterFavorite':
        """
        Deserialize favorite from dictionary.
        
        Args:
            data: Dict representation from to_dict()
        
        Returns:
            FilterFavorite instance
        """
        favorite = cls(
            name=data['name'],
            configuration=data['configuration'],
            description=data.get('description', ''),
            metadata=data.get('metadata', {}),
            favorite_id=data.get('id')
        )
        
        # Restore timestamps
        if 'created_at' in data:
            favorite.created_at = datetime.fromisoformat(data['created_at'])
        if 'modified_at' in data:
            favorite.modified_at = datetime.fromisoformat(data['modified_at'])
        
        return favorite
    
    def __repr__(self):
        return f"FilterFavorite(id='{self.id}', name='{self.name}')"


class FavoritesManager:
    """
    Manages filter favorites for the FilterMate plugin.
    
    Handles:
    - Loading/saving user-level favorites
    - Adding/removing/editing favorites
    - Searching and filtering favorites
    - Export/import to/from JSON files
    - Usage statistics
    
    Storage:
    - User favorites: ~/.qgis3/filtermate_favorites.json
    - Project favorites: Stored in QGIS project custom properties
    """
    
    def __init__(self, user_favorites_path: Optional[str] = None):
        """
        Initialize the favorites manager.
        
        Args:
            user_favorites_path: Path to user favorites file. If None, uses default location.
        """
        self.favorites: Dict[str, FilterFavorite] = {}
        
        # Determine user favorites path
        if user_favorites_path is None:
            from qgis.core import QgsApplication
            profile_path = QgsApplication.qgisSettingsDirPath()
            self.user_favorites_path = os.path.join(profile_path, 'filtermate_favorites.json')
        else:
            self.user_favorites_path = user_favorites_path
        
        # Load user favorites on initialization
        self.load_user_favorites()
        
        logger.info(f"FavoritesManager initialized with {len(self.favorites)} favorites")
    
    def add_favorite(self, favorite: FilterFavorite) -> bool:
        """
        Add a favorite to the manager.
        
        Args:
            favorite: FilterFavorite instance to add
        
        Returns:
            bool: True if added successfully, False if ID already exists
        """
        if favorite.id in self.favorites:
            logger.warning(f"Favorite with ID {favorite.id} already exists")
            return False
        
        self.favorites[favorite.id] = favorite
        logger.info(f"Added favorite: {favorite.name} ({favorite.id})")
        
        # Auto-save after adding
        self.save_user_favorites()
        return True
    
    def remove_favorite(self, favorite_id: str) -> bool:
        """
        Remove a favorite from the manager.
        
        Args:
            favorite_id: ID of the favorite to remove
        
        Returns:
            bool: True if removed, False if not found
        """
        if favorite_id not in self.favorites:
            logger.warning(f"Favorite {favorite_id} not found")
            return False
        
        favorite = self.favorites.pop(favorite_id)
        logger.info(f"Removed favorite: {favorite.name} ({favorite_id})")
        
        # Auto-save after removing
        self.save_user_favorites()
        return True
    
    def get_favorite(self, favorite_id: str) -> Optional[FilterFavorite]:
        """
        Get a favorite by ID.
        
        Args:
            favorite_id: ID of the favorite
        
        Returns:
            FilterFavorite instance or None if not found
        """
        return self.favorites.get(favorite_id)
    
    def get_all_favorites(self) -> List[FilterFavorite]:
        """
        Get all favorites.
        
        Returns:
            List of all FilterFavorite instances
        """
        return list(self.favorites.values())
    
    def search_favorites(
        self,
        query: str = "",
        tags: Optional[List[str]] = None,
        sort_by: str = 'name'
    ) -> List[FilterFavorite]:
        """
        Search and filter favorites.
        
        Args:
            query: Search string (matches name and description)
            tags: List of tags to filter by
            sort_by: Sort key ('name', 'created_at', 'usage_count', 'last_used')
        
        Returns:
            List of matching FilterFavorite instances
        """
        results = list(self.favorites.values())
        
        # Filter by query
        if query:
            query_lower = query.lower()
            results = [
                f for f in results
                if query_lower in f.name.lower() or query_lower in f.description.lower()
            ]
        
        # Filter by tags
        if tags:
            results = [
                f for f in results
                if any(tag in f.metadata.get('tags', []) for tag in tags)
            ]
        
        # Sort
        if sort_by == 'name':
            results.sort(key=lambda f: f.name.lower())
        elif sort_by == 'created_at':
            results.sort(key=lambda f: f.created_at, reverse=True)
        elif sort_by == 'usage_count':
            results.sort(key=lambda f: f.metadata.get('usage_count', 0), reverse=True)
        elif sort_by == 'last_used':
            results.sort(
                key=lambda f: datetime.fromisoformat(f.metadata['last_used'])
                if f.metadata.get('last_used') else datetime.min,
                reverse=True
            )
        
        return results
    
    def update_favorite(
        self,
        favorite_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        configuration: Optional[Dict] = None,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Update an existing favorite.
        
        Args:
            favorite_id: ID of favorite to update
            name: New name (optional)
            description: New description (optional)
            configuration: New configuration (optional)
            metadata: New metadata (optional)
        
        Returns:
            bool: True if updated, False if not found
        """
        favorite = self.get_favorite(favorite_id)
        if not favorite:
            logger.warning(f"Favorite {favorite_id} not found for update")
            return False
        
        # Update fields
        if name is not None:
            favorite.name = name
        if description is not None:
            favorite.description = description
        if configuration is not None:
            favorite.configuration = configuration
        if metadata is not None:
            favorite.metadata.update(metadata)
        
        favorite.modified_at = datetime.now()
        
        logger.info(f"Updated favorite: {favorite.name} ({favorite_id})")
        
        # Auto-save after updating
        self.save_user_favorites()
        return True
    
    def export_to_file(
        self,
        favorite_ids: Optional[List[str]],
        filepath: str,
        include_metadata: bool = True
    ) -> bool:
        """
        Export favorites to a JSON file.
        
        Args:
            favorite_ids: List of favorite IDs to export. If None, exports all.
            filepath: Path to export file
            include_metadata: Whether to include usage metadata
        
        Returns:
            bool: True if export successful
        """
        try:
            # Get favorites to export
            if favorite_ids is None:
                favorites_to_export = list(self.favorites.values())
            else:
                favorites_to_export = [
                    self.favorites[fid] for fid in favorite_ids if fid in self.favorites
                ]
            
            # Prepare export data
            export_data = {
                'filtermate_favorites_version': '1.0',
                'exported_at': datetime.now().isoformat(),
                'favorites_count': len(favorites_to_export),
                'favorites': []
            }
            
            # Serialize favorites
            for favorite in favorites_to_export:
                fav_dict = favorite.to_dict()
                
                # Optionally remove usage metadata for cleaner exports
                if not include_metadata:
                    fav_dict['metadata'] = {
                        k: v for k, v in fav_dict['metadata'].items()
                        if k not in ['usage_count', 'last_used']
                    }
                
                export_data['favorites'].append(fav_dict)
            
            # Write to file
            Path(filepath).parent.mkdir(parents=True, exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Exported {len(favorites_to_export)} favorites to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export favorites to {filepath}: {e}")
            return False
    
    def import_from_file(
        self,
        filepath: str,
        overwrite_existing: bool = False,
        merge_metadata: bool = True
    ) -> int:
        """
        Import favorites from a JSON file.
        
        Args:
            filepath: Path to import file
            overwrite_existing: If True, overwrites favorites with same ID
            merge_metadata: If True, merges metadata for existing favorites
        
        Returns:
            int: Number of favorites imported
        """
        try:
            # Read file
            with open(filepath, 'r', encoding='utf-8') as f:
                import_data = json.load(f)
            
            # Validate format
            if 'favorites' not in import_data:
                logger.error(f"Invalid favorites file format: {filepath}")
                return 0
            
            imported_count = 0
            
            # Import each favorite
            for fav_dict in import_data['favorites']:
                favorite = FilterFavorite.from_dict(fav_dict)
                
                # Check if already exists
                if favorite.id in self.favorites:
                    if overwrite_existing:
                        # Replace existing
                        self.favorites[favorite.id] = favorite
                        imported_count += 1
                        logger.debug(f"Overwrote existing favorite: {favorite.name}")
                    elif merge_metadata:
                        # Merge metadata (preserve usage stats)
                        existing = self.favorites[favorite.id]
                        existing.configuration = favorite.configuration
                        existing.name = favorite.name
                        existing.description = favorite.description
                        existing.modified_at = datetime.now()
                        # Preserve usage_count and last_used from existing
                        imported_count += 1
                        logger.debug(f"Merged favorite: {favorite.name}")
                    else:
                        logger.debug(f"Skipped existing favorite: {favorite.name}")
                else:
                    # Add new favorite
                    self.favorites[favorite.id] = favorite
                    imported_count += 1
            
            logger.info(f"Imported {imported_count} favorites from {filepath}")
            
            # Auto-save after importing
            if imported_count > 0:
                self.save_user_favorites()
            
            return imported_count
            
        except Exception as e:
            logger.error(f"Failed to import favorites from {filepath}: {e}")
            return 0
    
    def load_user_favorites(self) -> bool:
        """
        Load favorites from user favorites file.
        
        Returns:
            bool: True if loaded successfully
        """
        if not os.path.exists(self.user_favorites_path):
            logger.info(f"User favorites file not found: {self.user_favorites_path}")
            return False
        
        try:
            with open(self.user_favorites_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Load favorites
            for fav_dict in data.get('favorites', []):
                favorite = FilterFavorite.from_dict(fav_dict)
                self.favorites[favorite.id] = favorite
            
            logger.info(f"Loaded {len(self.favorites)} user favorites from {self.user_favorites_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load user favorites: {e}")
            return False
    
    def save_user_favorites(self) -> bool:
        """
        Save favorites to user favorites file.
        
        Returns:
            bool: True if saved successfully
        """
        try:
            # Prepare data
            data = {
                'filtermate_favorites_version': '1.0',
                'saved_at': datetime.now().isoformat(),
                'favorites_count': len(self.favorites),
                'favorites': [f.to_dict() for f in self.favorites.values()]
            }
            
            # Ensure directory exists
            Path(self.user_favorites_path).parent.mkdir(parents=True, exist_ok=True)
            
            # Write to file
            with open(self.user_favorites_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.debug(f"Saved {len(self.favorites)} user favorites to {self.user_favorites_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save user favorites: {e}")
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get usage statistics for all favorites.
        
        Returns:
            Dict with statistics (total count, most used, recent, etc.)
        """
        favorites_list = list(self.favorites.values())
        
        # Most used
        most_used = sorted(
            favorites_list,
            key=lambda f: f.metadata.get('usage_count', 0),
            reverse=True
        )[:5]
        
        # Recently used
        recently_used = sorted(
            favorites_list,
            key=lambda f: datetime.fromisoformat(f.metadata['last_used'])
            if f.metadata.get('last_used') else datetime.min,
            reverse=True
        )[:5]
        
        # Recently created
        recently_created = sorted(
            favorites_list,
            key=lambda f: f.created_at,
            reverse=True
        )[:5]
        
        return {
            'total_count': len(self.favorites),
            'total_usage_count': sum(f.metadata.get('usage_count', 0) for f in favorites_list),
            'most_used': [{'id': f.id, 'name': f.name, 'usage_count': f.metadata.get('usage_count', 0)} for f in most_used],
            'recently_used': [{'id': f.id, 'name': f.name, 'last_used': f.metadata.get('last_used')} for f in recently_used],
            'recently_created': [{'id': f.id, 'name': f.name, 'created_at': f.created_at.isoformat()} for f in recently_created]
        }


# Convenience functions for capturing and applying filter configurations

def capture_filter_configuration(project_layers: Dict, current_layer_id: str) -> Dict[str, Any]:
    """
    Extract current filter configuration from layer properties.
    
    This creates a portable configuration that can be saved as a favorite
    and applied to other layers.
    
    Args:
        project_layers: PROJECT_LAYERS dictionary from FilterMate
        current_layer_id: ID of the current layer
    
    Returns:
        Dict with filter configuration
    """
    if current_layer_id not in project_layers:
        return {}
    
    props = project_layers[current_layer_id]
    filtering = props.get('filtering', {})
    infos = props.get('infos', {})
    
    config = {
        # Expression
        'expression': filtering.get('filter_expression', ''),
        
        # Geometric predicates
        'geometric_predicates': filtering.get('geometric_predicates', []),
        
        # Buffer settings
        'buffer_distance': filtering.get('buffer_value', 0),
        'buffer_type': filtering.get('buffer_type', 'flat'),
        'buffer_expression': filtering.get('buffer_value_expression', ''),
        
        # Combine operators
        'source_layer_combine_operator': filtering.get('source_layer_combine_operator', 'AND'),
        'other_layers_combine_operator': filtering.get('other_layers_combine_operator', 'AND'),
        
        # Associated layers (abstracted by geometry type for portability)
        'associated_layers_by_type': {},
        
        # Source layer info (for context)
        'source_layer_geometry_type': infos.get('layer_geometry_type', 'Unknown'),
        'source_layer_provider_type': infos.get('layer_provider_type', 'unknown')
    }
    
    # Abstract associated layers by geometry type
    layers_to_filter = filtering.get('layers_to_filter', [])
    for layer_id in layers_to_filter:
        if layer_id in project_layers:
            geom_type = project_layers[layer_id]['infos'].get('layer_geometry_type', 'Unknown')
            layer_name = project_layers[layer_id]['infos'].get('layer_name', '')
            
            if geom_type not in config['associated_layers_by_type']:
                config['associated_layers_by_type'][geom_type] = []
            
            config['associated_layers_by_type'][geom_type].append(layer_name)
    
    return config


def apply_filter_configuration(
    config: Dict[str, Any],
    project_layers: Dict,
    target_layer_id: str,
    strict_matching: bool = False
) -> bool:
    """
    Apply a filter configuration to a target layer.
    
    Args:
        config: Filter configuration dictionary (from favorite)
        project_layers: PROJECT_LAYERS dictionary from FilterMate
        target_layer_id: ID of layer to apply configuration to
        strict_matching: If True, requires exact layer name matches
    
    Returns:
        bool: True if applied successfully
    """
    if target_layer_id not in project_layers:
        logger.warning(f"Target layer {target_layer_id} not found in project layers")
        return False
    
    try:
        # Apply expression
        project_layers[target_layer_id]['filtering']['filter_expression'] = config.get('expression', '')
        
        # Apply predicates
        project_layers[target_layer_id]['filtering']['geometric_predicates'] = config.get('geometric_predicates', [])
        
        # Apply buffer settings
        project_layers[target_layer_id]['filtering']['buffer_value'] = config.get('buffer_distance', 0)
        project_layers[target_layer_id]['filtering']['buffer_type'] = config.get('buffer_type', 'flat')
        project_layers[target_layer_id]['filtering']['buffer_value_expression'] = config.get('buffer_expression', '')
        
        # Apply combine operators
        project_layers[target_layer_id]['filtering']['source_layer_combine_operator'] = config.get('source_layer_combine_operator', 'AND')
        project_layers[target_layer_id]['filtering']['other_layers_combine_operator'] = config.get('other_layers_combine_operator', 'AND')
        
        # Map associated layers
        layers_to_filter = []
        associated_by_type = config.get('associated_layers_by_type', {})
        
        for geom_type, layer_names in associated_by_type.items():
            # Find matching layers in current project
            for layer_id, layer_props in project_layers.items():
                if layer_id == target_layer_id:
                    continue  # Skip self
                
                layer_geom_type = layer_props['infos'].get('layer_geometry_type', '')
                layer_name = layer_props['infos'].get('layer_name', '')
                
                if layer_geom_type == geom_type:
                    if strict_matching:
                        # Exact name match required
                        if layer_name in layer_names:
                            layers_to_filter.append(layer_id)
                    else:
                        # Fuzzy matching (contains or similar)
                        if any(ln.lower() in layer_name.lower() or layer_name.lower() in ln.lower() for ln in layer_names):
                            layers_to_filter.append(layer_id)
        
        project_layers[target_layer_id]['filtering']['layers_to_filter'] = layers_to_filter
        project_layers[target_layer_id]['filtering']['has_layers_to_filter'] = len(layers_to_filter) > 0
        
        logger.info(f"Applied filter configuration to layer {target_layer_id}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to apply filter configuration: {e}")
        return False
