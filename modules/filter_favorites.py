# -*- coding: utf-8 -*-
"""
FilterMate - Filter Favorites Management Module

This module provides classes for saving, loading, and managing filter favorites
that persist in FilterMate's SQLite database, organized by project.

Classes:
    FilterFavorite: A single saved filter configuration
    FavoritesManager: Manages collection of favorites with SQLite persistence

Author: FilterMate Team
License: GPL-3.0
"""

import json
import uuid
import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from qgis.core import QgsProject, QgsExpressionContextUtils

logger = logging.getLogger('FilterMate.Favorites')

# Project variable key for storing favorites (legacy, kept for migration)
FAVORITES_PROJECT_KEY = 'filtermate_favorites'


@dataclass
class FilterFavorite:
    """
    Represents a single saved filter configuration (favorite).
    
    Attributes:
        id: Unique identifier (UUID)
        name: User-defined name for the favorite
        expression: QGIS filter expression string
        layer_name: Optional associated layer name (for context)
        layer_provider: Optional provider type (postgresql, spatialite, ogr)
        spatial_config: Optional spatial filter configuration
        remote_layers: Dict of remote layer filters {layer_name: {expression, feature_count}}
        created_at: Creation timestamp (ISO format)
        last_used: Last usage timestamp (ISO format)
        use_count: Number of times this favorite was applied
        tags: List of user-defined tags for organization
        description: Optional description/notes
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    expression: str = ""
    layer_name: Optional[str] = None
    layer_provider: Optional[str] = None
    spatial_config: Optional[Dict[str, Any]] = None
    remote_layers: Optional[Dict[str, Dict[str, Any]]] = None  # {layer_name: {expression, feature_count, layer_id}}
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used: str = field(default_factory=lambda: datetime.now().isoformat())
    use_count: int = 0
    tags: List[str] = field(default_factory=list)
    description: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FilterFavorite':
        """Deserialize from dictionary."""
        # Handle missing fields with defaults
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            name=data.get('name', ''),
            expression=data.get('expression', ''),
            layer_name=data.get('layer_name'),
            layer_provider=data.get('layer_provider'),
            spatial_config=data.get('spatial_config'),
            remote_layers=data.get('remote_layers'),
            created_at=data.get('created_at', datetime.now().isoformat()),
            last_used=data.get('last_used', datetime.now().isoformat()),
            use_count=data.get('use_count', 0),
            tags=data.get('tags', []),
            description=data.get('description', '')
        )
    
    def get_layers_count(self) -> int:
        """Get total number of layers in this favorite (source + remote)."""
        count = 1 if self.expression else 0
        if self.remote_layers:
            count += len(self.remote_layers)
        return count
    
    def get_summary(self) -> str:
        """Get a summary string for display."""
        layers_count = self.get_layers_count()
        if layers_count <= 1:
            return f"{self.layer_name or 'Unknown layer'}"
        return f"{layers_count} layers filtered"
    
    def mark_used(self):
        """Update usage statistics when favorite is applied."""
        self.last_used = datetime.now().isoformat()
        self.use_count += 1
    
    def get_display_name(self, max_length: int = 30) -> str:
        """Get truncated display name for UI."""
        if len(self.name) <= max_length:
            return self.name
        return self.name[:max_length - 3] + "..."
    
    def get_preview(self, max_length: int = 50) -> str:
        """Get expression preview for tooltips."""
        if not self.expression:
            return "(empty expression)"
        if len(self.expression) <= max_length:
            return self.expression
        return self.expression[:max_length - 3] + "..."
    
    def __repr__(self):
        return f"FilterFavorite('{self.name}', uses={self.use_count})"


class FavoritesManager:
    """
    Manages a collection of filter favorites with SQLite database persistence.
    
    Favorites are stored in FilterMate's SQLite database, organized by project UUID.
    This allows favorites to persist across sessions and be shared within a project.
    
    Usage:
        manager = FavoritesManager(db_path="/path/to/filterMate_db.sqlite", project_uuid="...")
        manager.load_from_database()
        
        # Add a favorite
        fav = FilterFavorite(name="Large Cities", expression="population > 100000")
        manager.add_favorite(fav)
        
        # Get favorites
        all_favorites = manager.get_all_favorites()
        recent = manager.get_recent_favorites(limit=5)
        
        # Apply and track usage
        manager.mark_favorite_used(fav.id)
        
        # Save to database
        manager.save_to_project()
    """
    
    # SQL for creating favorites table
    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS fm_favorites (
        id TEXT PRIMARY KEY,
        project_uuid TEXT NOT NULL,
        name TEXT NOT NULL,
        expression TEXT,
        layer_name TEXT,
        layer_provider TEXT,
        spatial_config TEXT,
        remote_layers TEXT,
        created_at TEXT,
        last_used TEXT,
        use_count INTEGER DEFAULT 0,
        tags TEXT,
        description TEXT,
        _created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        _updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    
    CREATE_INDEX_SQL = """
    CREATE INDEX IF NOT EXISTS idx_fm_favorites_project ON fm_favorites(project_uuid);
    CREATE INDEX IF NOT EXISTS idx_fm_favorites_last_used ON fm_favorites(project_uuid, last_used DESC);
    CREATE INDEX IF NOT EXISTS idx_fm_favorites_use_count ON fm_favorites(project_uuid, use_count DESC);
    CREATE INDEX IF NOT EXISTS idx_fm_favorites_name ON fm_favorites(project_uuid, name);
    """
    
    def __init__(self, db_path: Optional[str] = None, project_uuid: Optional[str] = None, max_favorites: int = 50):
        """
        Initialize the favorites manager.
        
        Args:
            db_path: Path to FilterMate SQLite database. If None, uses legacy project variables.
            project_uuid: UUID of the current project. Required for SQLite mode.
            max_favorites: Maximum number of favorites to store (oldest removed when exceeded)
        """
        self._favorites: Dict[str, FilterFavorite] = {}
        self._max_favorites = max_favorites
        self._is_dirty = False  # Track unsaved changes
        self._db_path = db_path
        self._project_uuid = project_uuid
        self._table_initialized = False
        
        # Initialize table if using SQLite
        if self._db_path and self._project_uuid:
            self._ensure_table_exists()
        
    def set_database(self, db_path: str, project_uuid: str):
        """
        Set or update the database path and project UUID.
        
        Args:
            db_path: Path to FilterMate SQLite database
            project_uuid: UUID of the current project
        """
        self._db_path = db_path
        self._project_uuid = project_uuid
        self._table_initialized = False
        self._ensure_table_exists()
        
    def _get_connection(self) -> Optional[sqlite3.Connection]:
        """Get a SQLite connection to the database."""
        if not self._db_path:
            return None
        try:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to favorites database: {e}")
            return None
    
    def _ensure_table_exists(self):
        """Create the favorites table if it doesn't exist."""
        if self._table_initialized:
            return
        
        conn = self._get_connection()
        if not conn:
            return
        
        try:
            cursor = conn.cursor()
            cursor.execute(self.CREATE_TABLE_SQL)
            cursor.execute(self.CREATE_INDEX_SQL)
            conn.commit()
            self._table_initialized = True
            logger.debug("Favorites table initialized")
        except Exception as e:
            logger.error(f"Failed to create favorites table: {e}")
        finally:
            conn.close()
        
    @property
    def count(self) -> int:
        """Get the number of stored favorites."""
        return len(self._favorites)
    
    @property
    def is_empty(self) -> bool:
        """Check if there are no favorites."""
        return len(self._favorites) == 0
    
    @property
    def using_sqlite(self) -> bool:
        """Check if using SQLite storage."""
        return bool(self._db_path and self._project_uuid)
    
    def add_favorite(self, favorite: FilterFavorite) -> str:
        """
        Add a new favorite to the collection.
        
        Args:
            favorite: The FilterFavorite to add
            
        Returns:
            The ID of the added favorite
        """
        # Enforce max limit - remove oldest if needed
        if len(self._favorites) >= self._max_favorites:
            self._remove_oldest()
        
        self._favorites[favorite.id] = favorite
        self._is_dirty = True
        logger.info(f"Added favorite: {favorite.name} (id={favorite.id})")
        return favorite.id
    
    def remove_favorite(self, favorite_id: str) -> bool:
        """
        Remove a favorite by ID.
        
        Args:
            favorite_id: The UUID of the favorite to remove
            
        Returns:
            True if removed, False if not found
        """
        if favorite_id in self._favorites:
            name = self._favorites[favorite_id].name
            del self._favorites[favorite_id]
            self._is_dirty = True
            logger.info(f"Removed favorite: {name}")
            return True
        return False
    
    def get_favorite(self, favorite_id: str) -> Optional[FilterFavorite]:
        """Get a favorite by ID."""
        return self._favorites.get(favorite_id)
    
    def get_favorite_by_name(self, name: str) -> Optional[FilterFavorite]:
        """Get a favorite by exact name match."""
        for fav in self._favorites.values():
            if fav.name == name:
                return fav
        return None
    
    def get_all_favorites(self) -> List[FilterFavorite]:
        """Get all favorites sorted by name."""
        return sorted(self._favorites.values(), key=lambda f: f.name.lower())
    
    def get_recent_favorites(self, limit: int = 5) -> List[FilterFavorite]:
        """Get most recently used favorites."""
        sorted_favs = sorted(
            self._favorites.values(), 
            key=lambda f: f.last_used, 
            reverse=True
        )
        return sorted_favs[:limit]
    
    def get_most_used_favorites(self, limit: int = 5) -> List[FilterFavorite]:
        """Get most frequently used favorites."""
        sorted_favs = sorted(
            self._favorites.values(), 
            key=lambda f: f.use_count, 
            reverse=True
        )
        return sorted_favs[:limit]
    
    def search_favorites(self, query: str) -> List[FilterFavorite]:
        """
        Search favorites by name, expression, or tags.
        
        Args:
            query: Search string (case-insensitive)
            
        Returns:
            List of matching favorites
        """
        query_lower = query.lower()
        results = []
        
        for fav in self._favorites.values():
            # Search in name
            if query_lower in fav.name.lower():
                results.append(fav)
                continue
            # Search in expression
            if query_lower in fav.expression.lower():
                results.append(fav)
                continue
            # Search in tags
            if any(query_lower in tag.lower() for tag in fav.tags):
                results.append(fav)
                continue
            # Search in description
            if fav.description and query_lower in fav.description.lower():
                results.append(fav)
        
        return sorted(results, key=lambda f: f.name.lower())
    
    def mark_favorite_used(self, favorite_id: str) -> bool:
        """
        Update usage statistics for a favorite.
        
        Args:
            favorite_id: The UUID of the favorite
            
        Returns:
            True if found and updated
        """
        if favorite_id in self._favorites:
            self._favorites[favorite_id].mark_used()
            self._is_dirty = True
            return True
        return False
    
    def update_favorite(self, favorite_id: str, **kwargs) -> bool:
        """
        Update favorite properties.
        
        Args:
            favorite_id: The UUID of the favorite
            **kwargs: Properties to update (name, expression, tags, etc.)
            
        Returns:
            True if found and updated
        """
        if favorite_id not in self._favorites:
            return False
        
        fav = self._favorites[favorite_id]
        for key, value in kwargs.items():
            if hasattr(fav, key):
                setattr(fav, key, value)
        
        self._is_dirty = True
        return True
    
    def clear_all(self):
        """Remove all favorites."""
        self._favorites.clear()
        self._is_dirty = True
        logger.info("Cleared all favorites")
    
    def _remove_oldest(self):
        """Remove the oldest (least recently used) favorite."""
        if not self._favorites:
            return
        
        oldest = min(self._favorites.values(), key=lambda f: f.last_used)
        self.remove_favorite(oldest.id)
        logger.debug(f"Auto-removed oldest favorite: {oldest.name}")
    
    # === Database Persistence (SQLite) ===
    
    def save_to_project(self) -> bool:
        """
        Save favorites to storage (SQLite database or legacy project variables).
        
        Returns:
            True if saved successfully
        """
        if self.using_sqlite:
            return self._save_to_database()
        else:
            return self._save_to_project_variables()
    
    def _save_to_database(self) -> bool:
        """Save favorites to SQLite database."""
        conn = self._get_connection()
        if not conn:
            logger.warning("No database connection for saving favorites")
            return False
        
        try:
            cursor = conn.cursor()
            
            # Delete existing favorites for this project
            cursor.execute(
                "DELETE FROM fm_favorites WHERE project_uuid = ?",
                (self._project_uuid,)
            )
            
            # Insert all current favorites
            for fav in self._favorites.values():
                cursor.execute("""
                    INSERT INTO fm_favorites (
                        id, project_uuid, name, expression, layer_name, layer_provider,
                        spatial_config, remote_layers, created_at, last_used, use_count,
                        tags, description, _updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """, (
                    fav.id,
                    self._project_uuid,
                    fav.name,
                    fav.expression,
                    fav.layer_name,
                    fav.layer_provider,
                    json.dumps(fav.spatial_config) if fav.spatial_config else None,
                    json.dumps(fav.remote_layers) if fav.remote_layers else None,
                    fav.created_at,
                    fav.last_used,
                    fav.use_count,
                    json.dumps(fav.tags) if fav.tags else None,
                    fav.description
                ))
            
            conn.commit()
            self._is_dirty = False
            logger.info(f"Saved {len(self._favorites)} favorites to database for project {self._project_uuid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save favorites to database: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def _save_to_project_variables(self) -> bool:
        """Save favorites to QGIS project variables (legacy mode)."""
        try:
            project = QgsProject.instance()
            if not project:
                logger.warning("No project available for saving favorites")
                return False
            
            # Serialize to JSON
            data = {
                'version': '1.0',
                'favorites': [fav.to_dict() for fav in self._favorites.values()]
            }
            json_str = json.dumps(data, ensure_ascii=False)
            
            # Save as project variable
            QgsExpressionContextUtils.setProjectVariable(
                project, 
                FAVORITES_PROJECT_KEY, 
                json_str
            )
            
            self._is_dirty = False
            logger.info(f"Saved {len(self._favorites)} favorites to project variables")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save favorites to project: {e}")
            return False
    
    def load_from_project(self) -> bool:
        """
        Load favorites from storage (SQLite database or legacy project variables).
        
        Returns:
            True if loaded successfully (or no data to load)
        """
        if self.using_sqlite:
            success = self._load_from_database()
            # If no favorites in database, try migrating from project variables
            if success and len(self._favorites) == 0:
                self._migrate_from_project_variables()
            return success
        else:
            return self._load_from_project_variables()
    
    def _load_from_database(self) -> bool:
        """Load favorites from SQLite database."""
        conn = self._get_connection()
        if not conn:
            logger.debug("No database connection for loading favorites")
            return False
        
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, expression, layer_name, layer_provider,
                       spatial_config, remote_layers, created_at, last_used,
                       use_count, tags, description
                FROM fm_favorites
                WHERE project_uuid = ?
                ORDER BY last_used DESC
            """, (self._project_uuid,))
            
            self._favorites.clear()
            for row in cursor.fetchall():
                fav = FilterFavorite(
                    id=row['id'],
                    name=row['name'],
                    expression=row['expression'] or '',
                    layer_name=row['layer_name'],
                    layer_provider=row['layer_provider'],
                    spatial_config=json.loads(row['spatial_config']) if row['spatial_config'] else None,
                    remote_layers=json.loads(row['remote_layers']) if row['remote_layers'] else None,
                    created_at=row['created_at'] or datetime.now().isoformat(),
                    last_used=row['last_used'] or datetime.now().isoformat(),
                    use_count=row['use_count'] or 0,
                    tags=json.loads(row['tags']) if row['tags'] else [],
                    description=row['description'] or ''
                )
                self._favorites[fav.id] = fav
            
            self._is_dirty = False
            logger.info(f"Loaded {len(self._favorites)} favorites from database for project {self._project_uuid}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load favorites from database: {e}")
            return False
        finally:
            conn.close()
    
    def _load_from_project_variables(self) -> bool:
        """Load favorites from QGIS project variables (legacy mode)."""
        try:
            project = QgsProject.instance()
            if not project:
                logger.debug("No project available for loading favorites")
                return False
            
            # Get project variable
            scope = QgsExpressionContextUtils.projectScope(project)
            json_str = scope.variable(FAVORITES_PROJECT_KEY)
            
            if not json_str:
                logger.debug("No favorites data in project variables")
                return True  # No data is not an error
            
            # Parse JSON
            data = json.loads(json_str)
            
            # Load favorites
            self._favorites.clear()
            for fav_data in data.get('favorites', []):
                fav = FilterFavorite.from_dict(fav_data)
                self._favorites[fav.id] = fav
            
            self._is_dirty = False
            logger.info(f"Loaded {len(self._favorites)} favorites from project variables")
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid favorites JSON in project: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to load favorites from project: {e}")
            return False
    
    def _migrate_from_project_variables(self) -> bool:
        """Migrate favorites from legacy project variables to database."""
        try:
            project = QgsProject.instance()
            if not project:
                return False
            
            scope = QgsExpressionContextUtils.projectScope(project)
            json_str = scope.variable(FAVORITES_PROJECT_KEY)
            
            if not json_str:
                return False  # Nothing to migrate
            
            # Parse legacy data
            data = json.loads(json_str)
            favorites_data = data.get('favorites', [])
            
            if not favorites_data:
                return False
            
            # Load favorites from legacy format
            for fav_data in favorites_data:
                fav = FilterFavorite.from_dict(fav_data)
                self._favorites[fav.id] = fav
            
            # Save to database
            if self._save_to_database():
                # Clear legacy project variable after successful migration
                QgsExpressionContextUtils.setProjectVariable(
                    project, 
                    FAVORITES_PROJECT_KEY, 
                    ''
                )
                logger.info(f"Migrated {len(self._favorites)} favorites from project variables to database")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to migrate favorites: {e}")
            return False
            return False
    
    def export_to_file(self, filepath: str) -> bool:
        """
        Export favorites to external JSON file.
        
        Args:
            filepath: Path to output file
            
        Returns:
            True if exported successfully
        """
        try:
            data = {
                'version': '1.0',
                'exported_at': datetime.now().isoformat(),
                'favorites': [fav.to_dict() for fav in self._favorites.values()]
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Exported {len(self._favorites)} favorites to {filepath}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to export favorites: {e}")
            return False
    
    def import_from_file(self, filepath: str, merge: bool = True) -> int:
        """
        Import favorites from external JSON file.
        
        Args:
            filepath: Path to input file
            merge: If True, merge with existing; if False, replace all
            
        Returns:
            Number of favorites imported
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not merge:
                self._favorites.clear()
            
            imported = 0
            for fav_data in data.get('favorites', []):
                fav = FilterFavorite.from_dict(fav_data)
                
                # Generate new ID if merging to avoid conflicts
                if merge:
                    fav.id = str(uuid.uuid4())
                
                self._favorites[fav.id] = fav
                imported += 1
            
            self._is_dirty = True
            logger.info(f"Imported {imported} favorites from {filepath}")
            return imported
            
        except Exception as e:
            logger.error(f"Failed to import favorites: {e}")
            return 0
    
    # === Utility Methods ===
    
    def create_favorite_from_current(
        self, 
        name: str,
        expression: str,
        layer_name: Optional[str] = None,
        layer_provider: Optional[str] = None,
        spatial_config: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
        description: str = ""
    ) -> FilterFavorite:
        """
        Create a new favorite from current filter state.
        
        Convenience method that creates and adds a favorite in one step.
        
        Returns:
            The created FilterFavorite
        """
        fav = FilterFavorite(
            name=name,
            expression=expression,
            layer_name=layer_name,
            layer_provider=layer_provider,
            spatial_config=spatial_config,
            tags=tags or [],
            description=description
        )
        self.add_favorite(fav)
        return fav
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about favorites usage."""
        if not self._favorites:
            return {
                'total': 0,
                'total_uses': 0,
                'most_used': None,
                'least_used': None,
                'never_used': 0
            }
        
        all_favs = list(self._favorites.values())
        total_uses = sum(f.use_count for f in all_favs)
        never_used = sum(1 for f in all_favs if f.use_count == 0)
        
        most_used = max(all_favs, key=lambda f: f.use_count)
        least_used = min(all_favs, key=lambda f: f.use_count)
        
        return {
            'total': len(all_favs),
            'total_uses': total_uses,
            'most_used': most_used.name if most_used.use_count > 0 else None,
            'least_used': least_used.name,
            'never_used': never_used
        }
    
    def validate_favorite(self, favorite_id: str) -> tuple[bool, Optional[str]]:
        """
        Validate that a favorite can be applied (layer exists, expression valid).
        
        Args:
            favorite_id: ID of the favorite to validate
            
        Returns:
            tuple: (is_valid: bool, error_message: Optional[str])
        """
        from qgis.core import QgsProject, QgsExpression
        
        favorite = self.get_favorite(favorite_id)
        if not favorite:
            return False, f"Favorite {favorite_id} not found"
        
        # Check if layer exists in current project
        project = QgsProject.instance()
        matching_layers = project.mapLayersByName(favorite.layer_name)
        
        if not matching_layers:
            return False, f"Layer '{favorite.layer_name}' not found in current project"
        
        # If expression exists, validate it
        if favorite.expression:
            expr = QgsExpression(favorite.expression)
            if expr.hasParserError():
                return False, f"Invalid expression: {expr.parserErrorString()}"
        
        return True, None
    
    def cleanup_orphaned_favorites(self) -> tuple[int, list[str]]:
        """
        Remove favorites whose layers no longer exist in the current project.
        
        Returns:
            tuple: (removed_count: int, removed_names: list[str])
        """
        from qgis.core import QgsProject
        
        project = QgsProject.instance()
        project_layer_names = {layer.name() for layer in project.mapLayers().values()}
        
        removed_count = 0
        removed_names = []
        
        # Collect favorites to remove (avoid modifying dict during iteration)
        favorites_to_remove = []
        for fav in list(self._favorites.values()):
            if fav.layer_name and fav.layer_name not in project_layer_names:
                favorites_to_remove.append(fav)
        
        # Remove orphaned favorites
        for fav in favorites_to_remove:
            self.remove_favorite(fav.id)
            removed_count += 1
            removed_names.append(fav.name)
            logger.info(f"Removed orphaned favorite '{fav.name}' (layer '{fav.layer_name}' not found)")
        
        # Save changes if any were made
        if removed_count > 0:
            self.save_to_project()
            logger.info(f"🧹 Cleaned up {removed_count} orphaned favorite(s)")
        
        return removed_count, removed_names
    
    def validate_all_favorites(self) -> dict[str, tuple[bool, Optional[str]]]:
        """
        Validate all favorites in the manager.
        
        Returns:
            dict: {favorite_id: (is_valid, error_message)}
        """
        results = {}
        for fav_id in self._favorites.keys():
            results[fav_id] = self.validate_favorite(fav_id)
        return results
    
    def __repr__(self):
        return f"FavoritesManager({len(self._favorites)} favorites)"
