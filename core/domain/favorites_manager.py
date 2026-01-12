# -*- coding: utf-8 -*-
"""
FilterMate Favorites Manager - Standalone Implementation

Manages filter favorites with SQLite persistence.
Part of EPIC-1 v4.0 architecture cleanup.

Author: FilterMate Team
Date: January 2026
"""

import logging
import json
import uuid
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict, field

logger = logging.getLogger('FilterMate.FavoritesManager')


@dataclass
class FilterFavorite:
    """Filter favorite data class."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    expression: str = ""
    layer_name: Optional[str] = None
    layer_id: Optional[str] = None
    layer_provider: Optional[str] = None
    description: str = ""
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    use_count: int = 0
    last_used_at: Optional[str] = None
    remote_layers: Optional[Dict] = None
    spatial_config: Optional[Dict] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FilterFavorite':
        """Create from dictionary."""
        # Ensure tags is a list
        if 'tags' in data and isinstance(data['tags'], str):
            data['tags'] = json.loads(data['tags']) if data['tags'] else []
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class FavoritesManager:
    """
    Manages filter favorites with SQLite persistence.
    
    Features:
    - CRUD operations for favorites
    - SQLite database storage
    - Usage tracking and statistics
    - Search and filtering
    - Per-project organization
    """
    
    def __init__(self, db_path: Optional[str] = None, project_uuid: Optional[str] = None):
        """
        Initialize FavoritesManager.
        
        Args:
            db_path: Path to SQLite database
            project_uuid: Project UUID for favorites isolation
        """
        self._db_path = db_path
        self._project_uuid = project_uuid
        self._favorites: Dict[str, FilterFavorite] = {}
        self._initialized = False
        
        if db_path and project_uuid:
            self._initialize_database()
            self._load_favorites()
    
    def set_database(self, db_path: str, project_uuid: str) -> None:
        """
        Set database path and project UUID.
        
        Args:
            db_path: Path to SQLite database
            project_uuid: Project UUID
        """
        self._db_path = db_path
        self._project_uuid = project_uuid
        self._initialize_database()
        self._load_favorites()
    
    def _initialize_database(self) -> None:
        """Initialize database schema if needed."""
        if not self._db_path:
            return
        
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            # Check if table exists and get its columns
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='fm_favorites'")
            table_exists = cursor.fetchone() is not None
            
            if table_exists:
                # Check existing columns
                cursor.execute("PRAGMA table_info(fm_favorites)")
                existing_columns = {row[1] for row in cursor.fetchall()}
                
                # Add missing columns to existing table (migration)
                required_columns = {
                    'layer_id': 'TEXT',
                    'layer_provider': 'TEXT',
                    'description': 'TEXT',
                    'tags': 'TEXT',
                    'created_at': 'TEXT',
                    'updated_at': 'TEXT',
                    'use_count': 'INTEGER DEFAULT 0',
                    'last_used_at': 'TEXT',
                    'remote_layers': 'TEXT',
                    'spatial_config': 'TEXT'
                }
                
                for col_name, col_type in required_columns.items():
                    if col_name not in existing_columns:
                        logger.info(f"Adding missing column '{col_name}' to fm_favorites table")
                        cursor.execute(f"ALTER TABLE fm_favorites ADD COLUMN {col_name} {col_type}")
                
                conn.commit()
                logger.debug("fm_favorites table migrated to new schema")
            else:
                # Create new table with full schema
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS fm_favorites (
                        id TEXT PRIMARY KEY,
                        project_uuid TEXT NOT NULL,
                        name TEXT NOT NULL,
                        expression TEXT NOT NULL,
                        layer_name TEXT,
                        layer_id TEXT,
                        layer_provider TEXT,
                        description TEXT,
                        tags TEXT,
                        created_at TEXT,
                        updated_at TEXT,
                        use_count INTEGER DEFAULT 0,
                        last_used_at TEXT,
                        remote_layers TEXT,
                        spatial_config TEXT
                    )
                """)
                
                # Create index on project_uuid
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_favorites_project 
                    ON fm_favorites(project_uuid)
                """)
                
                conn.commit()
                logger.debug("fm_favorites table created with full schema")
            
            conn.close()
            
            self._initialized = True
            logger.debug(f"FavoritesManager: Database initialized at {self._db_path}")
            
        except Exception as e:
            logger.error(f"Failed to initialize favorites database: {e}")
            self._initialized = False
    
    def _load_favorites(self) -> None:
        """Load favorites from database."""
        if not self._initialized or not self._project_uuid:
            return
        
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            # Get available columns dynamically
            cursor.execute("PRAGMA table_info(fm_favorites)")
            available_columns = {row[1] for row in cursor.fetchall()}
            
            # Build SELECT query with only available columns
            columns_to_select = []
            column_map = {
                'id': 'id',
                'name': 'name', 
                'expression': 'expression',
                'layer_name': 'layer_name',
                'layer_id': 'layer_id',
                'layer_provider': 'layer_provider',
                'description': 'description',
                'tags': 'tags',
                'created_at': 'created_at',
                'updated_at': 'updated_at',
                'use_count': 'use_count',
                'last_used_at': 'last_used_at',
                'remote_layers': 'remote_layers',
                'spatial_config': 'spatial_config'
            }
            
            for col in column_map.keys():
                if col in available_columns:
                    columns_to_select.append(col)
            
            select_clause = ', '.join(columns_to_select)
            
            cursor.execute(f"""
                SELECT {select_clause}
                FROM fm_favorites
                WHERE project_uuid = ?
            """, (self._project_uuid,))
            
            self._favorites.clear()
            
            for row in cursor.fetchall():
                # Build data dict with defaults for missing columns
                data = {
                    'id': row['id'] if 'id' in available_columns else None,
                    'name': row['name'] if 'name' in available_columns else 'Unnamed',
                    'expression': row['expression'] if 'expression' in available_columns else '',
                    'layer_name': row['layer_name'] if 'layer_name' in available_columns else None,
                    'layer_id': row['layer_id'] if 'layer_id' in available_columns else None,
                    'layer_provider': row['layer_provider'] if 'layer_provider' in available_columns else None,
                    'description': row['description'] if 'description' in available_columns else '',
                    'tags': json.loads(row['tags']) if 'tags' in available_columns and row['tags'] else [],
                    'created_at': row['created_at'] if 'created_at' in available_columns else datetime.now().isoformat(),
                    'updated_at': row['updated_at'] if 'updated_at' in available_columns else datetime.now().isoformat(),
                    'use_count': row['use_count'] if 'use_count' in available_columns else 0,
                    'last_used_at': row['last_used_at'] if 'last_used_at' in available_columns else None,
                    'remote_layers': json.loads(row['remote_layers']) if 'remote_layers' in available_columns and row['remote_layers'] else None,
                    'spatial_config': json.loads(row['spatial_config']) if 'spatial_config' in available_columns and row['spatial_config'] else None,
                }
                favorite = FilterFavorite.from_dict(data)
                self._favorites[favorite.id] = favorite
            
            conn.close()
            logger.info(f"Loaded {len(self._favorites)} favorites for project {self._project_uuid}")
            
        except Exception as e:
            logger.error(f"Failed to load favorites: {e}")
    
    @property
    def count(self) -> int:
        """Get number of favorites."""
        return len(self._favorites)
    
    def get_all_favorites(self) -> List[FilterFavorite]:
        """Get all favorites."""
        return list(self._favorites.values())
    
    def get_favorite(self, favorite_id: str) -> Optional[FilterFavorite]:
        """Get favorite by ID."""
        return self._favorites.get(favorite_id)
    
    def get_by_id(self, favorite_id: str) -> Optional[FilterFavorite]:
        """Alias for get_favorite."""
        return self.get_favorite(favorite_id)
    
    def get_favorite_by_name(self, name: str) -> Optional[FilterFavorite]:
        """Get favorite by name."""
        for fav in self._favorites.values():
            if fav.name == name:
                return fav
        return None
    
    def add_favorite(self, favorite: FilterFavorite) -> bool:
        """
        Add a new favorite.
        
        Args:
            favorite: FilterFavorite instance
            
        Returns:
            bool: True if added successfully
        """
        if not self._initialized:
            logger.warning("Cannot add favorite: database not initialized")
            return False
        
        try:
            import sqlite3
            
            # Ensure favorite has an ID
            if not favorite.id:
                favorite.id = str(uuid.uuid4())
            
            favorite.created_at = datetime.now().isoformat()
            favorite.updated_at = favorite.created_at
            
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO fm_favorites (
                    id, project_uuid, name, expression, layer_name, layer_id,
                    layer_provider, description, tags, created_at, updated_at,
                    use_count, last_used_at, remote_layers, spatial_config
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                favorite.id,
                self._project_uuid,
                favorite.name,
                favorite.expression,
                favorite.layer_name,
                favorite.layer_id,
                favorite.layer_provider,
                favorite.description,
                json.dumps(favorite.tags) if favorite.tags else None,
                favorite.created_at,
                favorite.updated_at,
                favorite.use_count,
                favorite.last_used_at,
                json.dumps(favorite.remote_layers) if favorite.remote_layers else None,
                json.dumps(favorite.spatial_config) if favorite.spatial_config else None,
            ))
            
            conn.commit()
            conn.close()
            
            self._favorites[favorite.id] = favorite
            logger.info(f"Added favorite: {favorite.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add favorite: {e}")
            return False
    
    def remove_favorite(self, favorite_id: str) -> bool:
        """Remove a favorite."""
        if not self._initialized or favorite_id not in self._favorites:
            return False
        
        try:
            import sqlite3
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM fm_favorites WHERE id = ?", (favorite_id,))
            
            conn.commit()
            conn.close()
            
            del self._favorites[favorite_id]
            logger.info(f"Removed favorite: {favorite_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove favorite: {e}")
            return False
    
    def update_favorite(self, favorite_id: str, **kwargs) -> bool:
        """Update a favorite."""
        if not self._initialized or favorite_id not in self._favorites:
            return False
        
        try:
            import sqlite3
            
            favorite = self._favorites[favorite_id]
            
            # Update fields
            for key, value in kwargs.items():
                if hasattr(favorite, key):
                    setattr(favorite, key, value)
            
            favorite.updated_at = datetime.now().isoformat()
            
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE fm_favorites SET
                    name = ?, expression = ?, layer_name = ?, layer_id = ?,
                    layer_provider = ?, description = ?, tags = ?, updated_at = ?,
                    use_count = ?, last_used_at = ?, remote_layers = ?, spatial_config = ?
                WHERE id = ?
            """, (
                favorite.name,
                favorite.expression,
                favorite.layer_name,
                favorite.layer_id,
                favorite.layer_provider,
                favorite.description,
                json.dumps(favorite.tags) if favorite.tags else None,
                favorite.updated_at,
                favorite.use_count,
                favorite.last_used_at,
                json.dumps(favorite.remote_layers) if favorite.remote_layers else None,
                json.dumps(favorite.spatial_config) if favorite.spatial_config else None,
                favorite_id
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Updated favorite: {favorite.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update favorite: {e}")
            return False
    
    def increment_use_count(self, favorite_id: str) -> bool:
        """Increment use count for a favorite."""
        if favorite_id not in self._favorites:
            return False
        
        self._favorites[favorite_id].use_count += 1
        self._favorites[favorite_id].last_used_at = datetime.now().isoformat()
        
        return self.update_favorite(
            favorite_id,
            use_count=self._favorites[favorite_id].use_count,
            last_used_at=self._favorites[favorite_id].last_used_at
        )
    
    def search_favorites(self, query: str) -> List[FilterFavorite]:
        """Search favorites by name, expression, or tags."""
        query_lower = query.lower()
        results = []
        
        for fav in self._favorites.values():
            if (query_lower in fav.name.lower() or
                query_lower in fav.expression.lower() or
                any(query_lower in tag.lower() for tag in fav.tags)):
                results.append(fav)
        
        return results
    
    def get_recent_favorites(self, limit: int = 10) -> List[FilterFavorite]:
        """Get recently used favorites."""
        favorites = [f for f in self._favorites.values() if f.last_used_at]
        favorites.sort(key=lambda f: f.last_used_at or "", reverse=True)
        return favorites[:limit]
    
    def get_most_used_favorites(self, limit: int = 10) -> List[FilterFavorite]:
        """Get most frequently used favorites."""
        favorites = list(self._favorites.values())
        favorites.sort(key=lambda f: f.use_count, reverse=True)
        return favorites[:limit]
    
    def save_to_project(self) -> None:
        """Save favorites to project (no-op, already persisted)."""
        # Favorites are saved to database immediately in add/update/remove
        logger.debug("save_to_project called (favorites already persisted)")
    
    def load_from_project(self) -> None:
        """Load favorites from project."""
        self._load_favorites()
    
    def load_from_database(self) -> None:
        """Reload favorites from database."""
        self._load_favorites()
