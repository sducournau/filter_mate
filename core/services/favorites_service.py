"""
FavoritesService - Favorites Business Logic Service.

Bridge between UI controllers and the FavoritesManager data layer.
Provides higher-level operations and event notifications.

Story: MIG-076
Phase: 6 - God Class DockWidget Migration
Pattern: Strangler Fig - Gradual extraction
"""

import logging
from typing import Dict, List, Optional, Any, Callable, TYPE_CHECKING
from dataclasses import dataclass

try:
    from qgis.PyQt.QtCore import pyqtSignal, QObject
except ImportError:
    from PyQt5.QtCore import pyqtSignal, QObject

if TYPE_CHECKING:
    from qgis.core import QgsVectorLayer

# Export FilterFavorite from domain
from ..domain.favorites_manager import FilterFavorite

logger = logging.getLogger(__name__)


@dataclass
class FavoriteApplyResult:
    """Result of applying a favorite."""
    success: bool
    favorite_id: str
    favorite_name: str
    layers_affected: int = 0
    error_message: str = ""


@dataclass
class FavoriteExportResult:
    """Result of exporting favorites."""
    success: bool
    file_path: str
    favorites_count: int = 0
    error_message: str = ""


@dataclass
class FavoriteImportResult:
    """Result of importing favorites."""
    success: bool
    file_path: str
    imported_count: int = 0
    skipped_count: int = 0
    error_message: str = ""


class FavoritesService(QObject):
    """
    Service for managing filter favorites.

    Provides:
    - Favorite CRUD operations with notifications
    - Apply/unapply favorites to layers
    - Import/export favorites
    - Search and organization
    - Usage tracking and statistics

    Emits:
    - favorite_added: When a new favorite is created
    - favorite_removed: When a favorite is deleted
    - favorite_updated: When a favorite is modified
    - favorite_applied: When a favorite is applied to layers
    - favorites_changed: When the favorites list changes
    - favorites_imported: When favorites are imported
    - favorites_exported: When favorites are exported
    """

    # Signals
    favorite_added = pyqtSignal(str, str)  # favorite_id, name
    favorite_removed = pyqtSignal(str)  # favorite_id
    favorite_updated = pyqtSignal(str, str)  # favorite_id, name
    favorite_applied = pyqtSignal(str, int)  # favorite_id, layers_affected
    favorites_changed = pyqtSignal()  # general notification
    favorites_imported = pyqtSignal(int, int)  # imported_count, skipped_count
    favorites_exported = pyqtSignal(int, str)  # count, file_path

    def __init__(
        self,
        favorites_manager: Optional[Any] = None,
        parent: Optional[QObject] = None
    ):
        """
        Initialize FavoritesService.

        Args:
            favorites_manager: FavoritesManager instance (or will be created)
            parent: Optional parent QObject
        """
        super().__init__(parent)

        # If no manager provided, create internal one
        if favorites_manager is None:
            try:
                from ..domain.favorites_manager import FavoritesManager
                self._favorites_manager = FavoritesManager()
                logger.debug("FavoritesService: Created internal FavoritesManager")
            except Exception as e:
                logger.warning(f"Could not create internal FavoritesManager: {e}")
                self._favorites_manager = None
        else:
            self._favorites_manager = favorites_manager

        self._is_initialized = False

        # Callbacks for applying favorites (set by controller)
        self._apply_expression_callback: Optional[Callable] = None
        self._get_current_state_callback: Optional[Callable] = None

    # ─────────────────────────────────────────────────────────────────
    # Initialization
    # ─────────────────────────────────────────────────────────────────

    @property
    def favorites_manager(self) -> Any:
        """Get the underlying FavoritesManager."""
        return self._favorites_manager

    @favorites_manager.setter
    def favorites_manager(self, manager: Any) -> None:
        """Set the FavoritesManager."""
        self._favorites_manager = manager
        self._is_initialized = manager is not None

    def initialize(
        self,
        db_path: Optional[str] = None,
        project_uuid: Optional[str] = None
    ) -> bool:
        """
        Initialize the service with database.

        Args:
            db_path: Path to FilterMate database
            project_uuid: Current project UUID

        Returns:
            bool: True if initialization succeeded
        """
        # FavoritesService is a wrapper - it requires an external manager
        # The manager should be injected via constructor or favorites_manager setter
        if self._favorites_manager is None:
            logger.warning("FavoritesService: No favorites manager provided. Use favorites_manager setter.")
            return False

        # Configure existing manager with database
        if db_path and project_uuid:
            self.set_database(db_path, project_uuid)

        self._is_initialized = True
        return True

    def set_database(self, db_path: str, project_uuid: str) -> None:
        """
        Set database path and project UUID.
        Delegates to underlying FavoritesManager.

        Args:
            db_path: Path to SQLite database
            project_uuid: Project UUID for favorites isolation
        """
        if self._favorites_manager and hasattr(self._favorites_manager, 'set_database'):
            self._favorites_manager.set_database(db_path, project_uuid)
            # CRITICAL: Emit favorites_changed to update UI after loading
            self.favorites_changed.emit()
            logger.info(f"✓ Favorites loaded from database and UI notified (count: {self.count})")
        else:
            # v5.0: Internal database storage when manager not available
            self._db_path = db_path
            self._project_uuid = project_uuid
            self._init_internal_storage()
            self.favorites_changed.emit()
            logger.info(f"FavoritesService: Internal database initialized at {db_path}")

    def _init_internal_storage(self) -> None:
        """
        Initialize internal SQLite storage for favorites when manager not available.

        v5.0: Standalone favorites storage capability.
        """
        import sqlite3
        import os

        if not hasattr(self, '_db_path') or not self._db_path:
            return

        try:
            # Ensure directory exists
            db_dir = os.path.dirname(self._db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)

            # Create database and tables
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            cursor.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    id TEXT PRIMARY KEY,
                    project_uuid TEXT,
                    name TEXT NOT NULL,
                    expression TEXT,
                    layer_name TEXT,
                    layer_provider TEXT,
                    spatial_config TEXT,
                    remote_layers TEXT,
                    tags TEXT,
                    description TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    use_count INTEGER DEFAULT 0,
                    is_global INTEGER DEFAULT 0
                )
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_project_uuid
                ON favorites(project_uuid)
            ''')

            conn.commit()
            conn.close()

            logger.info(f"Internal favorites storage initialized: {self._db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize internal storage: {e}")

    def load_from_project(self) -> None:
        """
        Load favorites from project.
        Delegates to underlying FavoritesManager.
        """
        if self._favorites_manager and hasattr(self._favorites_manager, 'load_from_project'):
            self._favorites_manager.load_from_project()
            # CRITICAL: Emit favorites_changed to update UI after loading
            self.favorites_changed.emit()
            logger.info(f"✓ Favorites reloaded from database and UI notified (count: {self.count})")
        else:
            # Note: Internal project loading without manager is not implemented.
            # FavoritesManager is required for full functionality.
            logger.debug("FavoritesService: Loading from project (stub - no manager)")

    @property
    def count(self) -> int:
        """Get the number of favorites."""
        if self._favorites_manager and hasattr(self._favorites_manager, '__len__'):
            return len(self._favorites_manager)
        elif self._favorites_manager and hasattr(self._favorites_manager, 'count'):
            return self._favorites_manager.count
        return 0

    def set_callbacks(
        self,
        apply_expression: Optional[Callable] = None,
        get_current_state: Optional[Callable] = None
    ) -> None:
        """
        Set callbacks for integration with dockwidget.

        Args:
            apply_expression: Callback to apply expression to layer
            get_current_state: Callback to get current filter state
        """
        self._apply_expression_callback = apply_expression
        self._get_current_state_callback = get_current_state

    # ─────────────────────────────────────────────────────────────────
    # CRUD Operations
    # ─────────────────────────────────────────────────────────────────

    def add_favorite(
        self,
        name: str,
        expression: str,
        layer_name: Optional[str] = None,
        layer_provider: Optional[str] = None,
        spatial_config: Optional[Dict] = None,
        remote_layers: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
        description: str = ""
    ) -> Optional[str]:
        """
        Add a new favorite.

        Args:
            name: Favorite name
            expression: Filter expression
            layer_name: Optional layer name
            layer_provider: Optional provider type
            spatial_config: Optional spatial filter config
            remote_layers: Optional remote layers config
            tags: Optional tags list
            description: Optional description

        Returns:
            str: Favorite ID if created, None on error
        """
        if not self._favorites_manager:
            logger.error("FavoritesManager not initialized")
            return None

        try:
            # FilterFavorite is imported at top of file
            favorite = FilterFavorite(
                name=name,
                expression=expression,
                layer_name=layer_name,
                layer_provider=layer_provider,
                spatial_config=spatial_config,
                remote_layers=remote_layers,
                tags=tags or [],
                description=description
            )

            success = self._favorites_manager.add_favorite(favorite)

            if success:
                self.favorite_added.emit(favorite.id, name)
                self.favorites_changed.emit()
                logger.info(f"✓ Favorite added via FavoritesService: {name} (ID: {favorite.id})")
                return favorite.id
            else:
                logger.error(f"✗ Failed to add favorite '{name}' - FavoritesManager.add_favorite() returned False")

            return None

        except Exception as e:
            logger.error(f"Error adding favorite: {e}")
            return None

    def remove_favorite(self, favorite_id: str) -> bool:
        """
        Remove a favorite.

        Args:
            favorite_id: ID of favorite to remove

        Returns:
            bool: True if removed successfully
        """
        if not self._favorites_manager:
            return False

        try:
            success = self._favorites_manager.remove_favorite(favorite_id)

            if success:
                self.favorite_removed.emit(favorite_id)
                self.favorites_changed.emit()
                logger.info(f"Removed favorite: {favorite_id}")

            return success

        except Exception as e:
            logger.error(f"Error removing favorite: {e}")
            return False

    def update_favorite(
        self,
        favorite_id: str,
        **kwargs
    ) -> bool:
        """
        Update a favorite.

        Args:
            favorite_id: ID of favorite to update
            **kwargs: Fields to update

        Returns:
            bool: True if updated successfully
        """
        if not self._favorites_manager:
            return False

        try:
            success = self._favorites_manager.update_favorite(favorite_id, **kwargs)

            if success:
                name = kwargs.get('name', favorite_id)
                self.favorite_updated.emit(favorite_id, name)
                self.favorites_changed.emit()
                logger.info(f"Updated favorite: {favorite_id}")

            return success

        except Exception as e:
            logger.error(f"Error updating favorite: {e}")
            return False

    def get_favorite(self, favorite_id: str) -> Optional[Any]:
        """
        Get a favorite by ID.

        Args:
            favorite_id: Favorite ID

        Returns:
            FilterFavorite or None
        """
        if not self._favorites_manager:
            return None

        return self._favorites_manager.get_favorite(favorite_id)

    def get_favorite_by_name(self, name: str) -> Optional[Any]:
        """
        Get a favorite by name.

        Args:
            name: Favorite name

        Returns:
            FilterFavorite or None
        """
        if not self._favorites_manager:
            return None

        return self._favorites_manager.get_favorite_by_name(name)

    # ─────────────────────────────────────────────────────────────────
    # List Operations
    # ─────────────────────────────────────────────────────────────────

    def get_all_favorites(self) -> List[Any]:
        """
        Get all favorites.

        Returns:
            List of FilterFavorite objects
        """
        if not self._favorites_manager:
            return []

        return self._favorites_manager.get_all_favorites()

    def get_recent_favorites(self, limit: int = 5) -> List[Any]:
        """
        Get recently used favorites.

        Args:
            limit: Maximum number to return

        Returns:
            List of FilterFavorite objects
        """
        if not self._favorites_manager:
            return []

        return self._favorites_manager.get_recent_favorites(limit)

    def get_most_used_favorites(self, limit: int = 5) -> List[Any]:
        """
        Get most frequently used favorites.

        Args:
            limit: Maximum number to return

        Returns:
            List of FilterFavorite objects
        """
        if not self._favorites_manager:
            return []

        return self._favorites_manager.get_most_used_favorites(limit)

    def search_favorites(self, query: str) -> List[Any]:
        """
        Search favorites by name, expression, or tags.

        Args:
            query: Search query

        Returns:
            List of matching FilterFavorite objects
        """
        if not self._favorites_manager:
            return []

        return self._favorites_manager.search_favorites(query)

    def get_favorites_count(self) -> int:
        """
        Get total number of favorites.

        Returns:
            int: Number of favorites
        """
        if not self._favorites_manager:
            return 0

        return len(self.get_all_favorites())

    # ─────────────────────────────────────────────────────────────────
    # Apply Operations
    # ─────────────────────────────────────────────────────────────────

    def apply_favorite(
        self,
        favorite_id: str,
        layer: Optional["QgsVectorLayer"] = None
    ) -> FavoriteApplyResult:
        """
        Apply a favorite's filter to the current layer.

        Args:
            favorite_id: ID of favorite to apply
            layer: Optional layer to apply to

        Returns:
            FavoriteApplyResult with status
        """
        if not self._favorites_manager:
            return FavoriteApplyResult(
                success=False,
                favorite_id=favorite_id,
                favorite_name="",
                error_message="FavoritesManager not initialized"
            )

        favorite = self._favorites_manager.get_favorite(favorite_id)

        if not favorite:
            return FavoriteApplyResult(
                success=False,
                favorite_id=favorite_id,
                favorite_name="",
                error_message=f"Favorite not found: {favorite_id}"
            )

        try:
            layers_affected = 0

            # Apply main expression
            if self._apply_expression_callback:
                success = self._apply_expression_callback(
                    favorite.expression,
                    layer
                )
                if success:
                    layers_affected += 1

            # Apply remote layers if any
            if favorite.remote_layers:
                for layer_name, config in favorite.remote_layers.items():
                    # Remote layer application is handled by controller
                    layers_affected += 1

            # Mark as used
            self._favorites_manager.increment_use_count(favorite_id)

            # Emit signal
            self.favorite_applied.emit(favorite_id, layers_affected)

            return FavoriteApplyResult(
                success=True,
                favorite_id=favorite_id,
                favorite_name=favorite.name,
                layers_affected=layers_affected
            )

        except Exception as e:
            logger.error(f"Error applying favorite: {e}")
            return FavoriteApplyResult(
                success=False,
                favorite_id=favorite_id,
                favorite_name=favorite.name,
                error_message=str(e)
            )

    def mark_favorite_used(self, favorite_id: str) -> bool:
        """
        Mark a favorite as used (update usage stats).

        Args:
            favorite_id: Favorite ID

        Returns:
            bool: True if marked successfully
        """
        if not self._favorites_manager:
            return False

        return self._favorites_manager.increment_use_count(favorite_id)

    # ─────────────────────────────────────────────────────────────────
    # Create from Current State
    # ─────────────────────────────────────────────────────────────────

    def create_from_current_state(
        self,
        name: str,
        layer: Optional["QgsVectorLayer"] = None,
        include_remote_layers: bool = True
    ) -> Optional[str]:
        """
        Create a favorite from the current filter state.

        Args:
            name: Name for the new favorite
            layer: Current layer (or None to use callback)
            include_remote_layers: Whether to include remote layer filters

        Returns:
            str: Favorite ID if created, None on error
        """
        if not self._favorites_manager:
            return None

        # Get current state via callback
        if self._get_current_state_callback:
            state = self._get_current_state_callback()

            if state:
                return self.add_favorite(
                    name=name,
                    expression=state.get('expression', ''),
                    layer_name=state.get('layer_name'),
                    layer_provider=state.get('layer_provider'),
                    spatial_config=state.get('spatial_config'),
                    remote_layers=state.get('remote_layers') if include_remote_layers else None,
                    description="Created from current state"
                )

        # Fallback: use layer directly
        if layer is not None:
            expression = layer.subsetString() if layer.subsetString() else ""
            return self.add_favorite(
                name=name,
                expression=expression,
                layer_name=layer.name(),
                layer_provider=layer.providerType()
            )

        return None

    # ─────────────────────────────────────────────────────────────────
    # Import/Export
    # ─────────────────────────────────────────────────────────────────

    def export_favorites(
        self,
        file_path: str,
        favorite_ids: Optional[List[str]] = None
    ) -> FavoriteExportResult:
        """
        Export favorites to a JSON file.

        Args:
            file_path: Path to export file
            favorite_ids: Optional list of IDs to export (None = all)

        Returns:
            FavoriteExportResult with status
        """
        if not self._favorites_manager:
            return FavoriteExportResult(
                success=False,
                file_path=file_path,
                error_message="FavoritesManager not initialized"
            )

        try:
            import json

            # Get favorites to export
            if favorite_ids:
                favorites = [
                    self._favorites_manager.get_favorite(fid)
                    for fid in favorite_ids
                ]
                favorites = [f for f in favorites if f is not None]
            else:
                favorites = self.get_all_favorites()

            # Serialize
            data = {
                "version": "1.0",
                "exported_at": self._get_timestamp(),
                "favorites": [f.to_dict() for f in favorites]
            }

            # Write file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            count = len(favorites)
            self.favorites_exported.emit(count, file_path)

            logger.info(f"Exported {count} favorites to {file_path}")

            return FavoriteExportResult(
                success=True,
                file_path=file_path,
                favorites_count=count
            )

        except Exception as e:
            logger.error(f"Error exporting favorites: {e}")
            return FavoriteExportResult(
                success=False,
                file_path=file_path,
                error_message=str(e)
            )

    def import_favorites(
        self,
        file_path: str,
        skip_duplicates: bool = True
    ) -> FavoriteImportResult:
        """
        Import favorites from a JSON file.

        Args:
            file_path: Path to import file
            skip_duplicates: Skip favorites with same name

        Returns:
            FavoriteImportResult with status
        """
        if not self._favorites_manager:
            return FavoriteImportResult(
                success=False,
                file_path=file_path,
                error_message="FavoritesManager not initialized"
            )

        try:
            import json
            # FilterFavorite is imported at top of file

            # Read file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            favorites_data = data.get('favorites', [])

            imported_count = 0
            skipped_count = 0

            for fav_data in favorites_data:
                name = fav_data.get('name', '')

                # Check for duplicates
                if skip_duplicates:
                    existing = self.get_favorite_by_name(name)
                    if existing:
                        skipped_count += 1
                        continue

                # Create new favorite with new ID
                favorite = FilterFavorite.from_dict(fav_data)
                favorite.id = None  # Will generate new ID

                if self._favorites_manager.add_favorite(favorite):
                    imported_count += 1
                else:
                    skipped_count += 1

            self.favorites_imported.emit(imported_count, skipped_count)
            self.favorites_changed.emit()

            logger.info(f"Imported {imported_count} favorites, skipped {skipped_count}")

            return FavoriteImportResult(
                success=True,
                file_path=file_path,
                imported_count=imported_count,
                skipped_count=skipped_count
            )

        except Exception as e:
            logger.error(f"Error importing favorites: {e}")
            return FavoriteImportResult(
                success=False,
                file_path=file_path,
                error_message=str(e)
            )

    # ─────────────────────────────────────────────────────────────────
    # Validation and Cleanup
    # ─────────────────────────────────────────────────────────────────

    def validate_favorite(
        self,
        favorite_id: str
    ) -> tuple[bool, Optional[str]]:
        """
        Validate a favorite (check if layers/expressions still valid).

        Args:
            favorite_id: Favorite ID

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self._favorites_manager:
            return False, "FavoritesManager not initialized"

        return self._favorites_manager.validate_favorite(favorite_id)

    def validate_all_favorites(self) -> Dict[str, tuple[bool, Optional[str]]]:
        """
        Validate all favorites.

        Returns:
            Dict mapping favorite_id to (is_valid, error_message)
        """
        if not self._favorites_manager:
            return {}

        return self._favorites_manager.validate_all_favorites()

    def cleanup_orphaned_favorites(self) -> tuple[int, List[str]]:
        """
        Remove favorites for layers that no longer exist.

        Returns:
            Tuple of (removed_count, removed_ids)
        """
        if not self._favorites_manager:
            return 0, []

        result = self._favorites_manager.cleanup_orphaned_favorites()

        if result[0] > 0:
            self.favorites_changed.emit()

        return result

    # ─────────────────────────────────────────────────────────────────
    # Statistics
    # ─────────────────────────────────────────────────────────────────

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get favorites statistics.

        Returns:
            Dict with statistics
        """
        favorites = self.get_all_favorites()

        if not favorites:
            return {
                "total_count": 0,
                "total_uses": 0,
                "most_used": None,
                "recently_used": None
            }

        total_uses = sum(f.use_count for f in favorites)
        most_used = max(favorites, key=lambda f: f.use_count) if favorites else None

        recent = self.get_recent_favorites(1)
        recently_used = recent[0] if recent else None

        return {
            "total_count": len(favorites),
            "total_uses": total_uses,
            "most_used": most_used.name if most_used else None,
            "most_used_count": most_used.use_count if most_used else 0,
            "recently_used": recently_used.name if recently_used else None
        }

    # ─────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()

    def save(self) -> bool:
        """
        Save favorites to storage.

        Returns:
            bool: True if saved successfully
        """
        if not self._favorites_manager:
            return False

        try:
            self._favorites_manager.save_to_project()
            return True
        except Exception as e:
            logger.error(f"Error saving favorites: {e}")
            return False

    def reload(self) -> bool:
        """
        Reload favorites from storage.

        Returns:
            bool: True if reloaded successfully
        """
        if not self._favorites_manager:
            return False

        try:
            self._favorites_manager.load_from_database()
            self.favorites_changed.emit()
            return True
        except Exception as e:
            logger.error(f"Error reloading favorites: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────
    # Project File (.qgz) Backup/Restore
    # ─────────────────────────────────────────────────────────────────

    def save_to_project_file(self, project: Optional[Any] = None) -> bool:
        """
        Save favorites to QGIS project file as custom property.

        This provides an additional backup in the .qgz file itself,
        ensuring favorites are bundled with the project.

        Args:
            project: QgsProject instance (uses current if None)

        Returns:
            bool: True if saved successfully
        """
        if not self._favorites_manager:
            return False

        try:
            from qgis.core import QgsProject
            import json

            if project is None:
                project = QgsProject.instance()

            favorites = self.get_all_favorites()

            if not favorites:
                # Clear any existing property
                project.removeEntry("FilterMate", "favorites_backup")
                return True

            # Serialize favorites
            data = {
                "version": "1.0",
                "backup_type": "project_file",
                "created_at": self._get_timestamp(),
                "favorites": [f.to_dict() for f in favorites]
            }

            json_data = json.dumps(data, ensure_ascii=False)

            # Store in project custom properties
            project.writeEntry("FilterMate", "favorites_backup", json_data)

            logger.info(f"✓ Saved {len(favorites)} favorites to project file")
            return True

        except Exception as e:
            logger.error(f"Error saving favorites to project file: {e}")
            return False

    def restore_from_project_file(self, project: Optional[Any] = None) -> int:
        """
        Restore favorites from QGIS project file backup.

        This is useful when the SQLite database is lost or corrupted.

        Args:
            project: QgsProject instance (uses current if None)

        Returns:
            int: Number of favorites restored
        """
        if not self._favorites_manager:
            return 0

        try:
            from qgis.core import QgsProject
            import json

            if project is None:
                project = QgsProject.instance()

            # Read from project custom properties
            json_data, success = project.readEntry("FilterMate", "favorites_backup", "")

            if not success or not json_data:
                logger.debug("No favorites backup found in project file")
                return 0

            data = json.loads(json_data)
            favorites_data = data.get('favorites', [])

            if not favorites_data:
                return 0

            # Import favorites (skip duplicates by name)
            from ..domain.favorites_manager import FilterFavorite

            imported = 0
            for fav_data in favorites_data:
                name = fav_data.get('name', '')

                # Check for existing favorite with same name
                existing = self.get_favorite_by_name(name)
                if existing:
                    continue

                # Create and add favorite
                favorite = FilterFavorite.from_dict(fav_data)
                favorite.id = None  # Generate new ID

                if self._favorites_manager.add_favorite(favorite):
                    imported += 1

            if imported > 0:
                self.favorites_changed.emit()
                logger.info(f"✓ Restored {imported} favorites from project file")

            return imported

        except Exception as e:
            logger.error(f"Error restoring favorites from project file: {e}")
            return 0

    # ─────────────────────────────────────────────────────────────────
    # Global Favorites Support
    # ─────────────────────────────────────────────────────────────────

    def get_global_favorites(self) -> List[Any]:
        """
        Get all global favorites (available in all projects).

        Returns:
            List of global FilterFavorite objects
        """
        if not self._favorites_manager:
            return []

        if hasattr(self._favorites_manager, 'get_global_favorites'):
            return self._favorites_manager.get_global_favorites()

        return []

    def get_all_with_global(self) -> List[Any]:
        """
        Get all favorites including global ones.

        Returns:
            List of FilterFavorite (project-specific + global)
        """
        if not self._favorites_manager:
            return []

        if hasattr(self._favorites_manager, 'get_all_with_global'):
            return self._favorites_manager.get_all_with_global()

        # Fallback: just return project favorites
        return self.get_all_favorites()

    def make_favorite_global(self, favorite_id: str) -> bool:
        """
        Make a favorite global (available in all projects).

        Args:
            favorite_id: ID of favorite to make global

        Returns:
            bool: True if successful
        """
        if not self._favorites_manager:
            return False

        if hasattr(self._favorites_manager, 'make_favorite_global'):
            success = self._favorites_manager.make_favorite_global(favorite_id)
            if success:
                self.favorites_changed.emit()
            return success

        return False

    def copy_to_global(self, favorite_id: str) -> Optional[str]:
        """
        Copy a favorite to global (keeps original in project).

        Args:
            favorite_id: ID of favorite to copy

        Returns:
            New favorite ID if successful, None otherwise
        """
        if not self._favorites_manager:
            return None

        if hasattr(self._favorites_manager, 'copy_to_global'):
            new_id = self._favorites_manager.copy_to_global(favorite_id)
            if new_id:
                self.favorites_changed.emit()
            return new_id

        return None

    def import_global_to_project(self, global_favorite_id: str) -> Optional[str]:
        """
        Import a global favorite to the current project.

        Args:
            global_favorite_id: ID of global favorite to import

        Returns:
            New favorite ID if successful, None otherwise
        """
        if not self._favorites_manager:
            return None

        if hasattr(self._favorites_manager, 'import_global_to_project'):
            new_id = self._favorites_manager.import_global_to_project(global_favorite_id)
            if new_id:
                self.favorites_changed.emit()
            return new_id

        return None
