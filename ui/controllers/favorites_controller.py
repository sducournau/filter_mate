"""
Favorites Controller for FilterMate.

Manages the favorites indicator and favorites operations UI.
Extracted from filter_mate_dockwidget.py (lines 1966-2897).

Story: MIG-072
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, List, Any
import logging

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QMenu, QInputDialog, QMessageBox, QFileDialog,
    QLabel
)
from qgis.PyQt.QtGui import QCursor
from qgis.core import QgsExpressionContextUtils, QgsProject

from .base_controller import BaseController

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from ...core.services.favorites_service import FavoritesService, FilterFavorite

logger = logging.getLogger(__name__)


# Indicator styles
FAVORITES_STYLES = {
    'active': {
        'background': '#f39c12',  # Gold/amber
        'hover': '#d68910',
        'color': 'white'
    },
    'empty': {
        'background': '#ecf0f1',  # Light gray
        'hover': '#d5dbdb',
        'color': '#95a5a6'
    }
}


class FavoritesController(BaseController):
    """
    Controller for favorites management.

    Handles:
    - Favorites indicator display and styling
    - Add/Remove/Apply favorites
    - Import/Export favorites
    - Favorites menu and dialogs

    Signals:
        favorite_added: Emitted when a favorite is added (favorite_name)
        favorite_applied: Emitted when a favorite is applied (favorite_name)
        favorite_removed: Emitted when a favorite is removed (favorite_name)

    Example:
        controller = FavoritesController(dockwidget)
        controller.setup()

        # React to favorites changes
        controller.favorite_added.connect(on_favorite_added)
    """

    favorite_added = pyqtSignal(str)  # favorite_name
    favorite_applied = pyqtSignal(str)  # favorite_name
    favorite_removed = pyqtSignal(str)  # favorite_name
    favorites_changed = pyqtSignal()  # generic change signal

    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the favorites controller.

        Args:
            dockwidget: Main dockwidget reference
        """
        super().__init__(dockwidget)
        self._favorites_manager: Optional['FavoritesManager'] = None
        self._indicator_label: Optional[QLabel] = None
        self._initialized: bool = False

    @property
    def favorites_manager(self) -> Optional['FavoritesManager']:
        """Get the favorites manager instance."""
        return self._favorites_manager

    @property
    def count(self) -> int:
        """Get the number of favorites."""
        if self._favorites_manager:
            return self._favorites_manager.count
        return 0

    def setup(self) -> None:
        """
        Setup favorites indicator and manager.

        Initializes the favorites manager and connects to indicator.
        """
        self._find_indicator_label()
        self._init_favorites_manager()
        
        # CRITICAL FIX 2026-01-18: Connect to favorites_changed signal from FavoritesService
        # This ensures the UI is updated when favorites are loaded from database
        if self._favorites_manager and hasattr(self._favorites_manager, 'favorites_changed'):
            self._favorites_manager.favorites_changed.connect(self._on_favorites_loaded)
            logger.debug("✓ Connected to FavoritesService.favorites_changed signal")
        
        self._initialized = True
        logger.debug("FavoritesController setup complete")

    def teardown(self) -> None:
        """Clean up resources."""
        self._favorites_manager = None
        super().teardown()

    def sync_with_dockwidget_manager(self) -> bool:
        """
        Re-synchronize with the favorites manager from dockwidget.
        
        FIX 2026-01-19: Called when the dockwidget's _favorites_manager is updated
        (e.g., after init_filterMate_db() configures it).
        
        Returns:
            bool: True if sync was successful
        """
        if not hasattr(self.dockwidget, '_favorites_manager'):
            logger.debug("sync_with_dockwidget_manager: dockwidget has no _favorites_manager")
            return False
            
        new_manager = self.dockwidget._favorites_manager
        if new_manager is None:
            logger.debug("sync_with_dockwidget_manager: dockwidget._favorites_manager is None")
            return False
            
        # Disconnect old signal if any
        if self._favorites_manager and hasattr(self._favorites_manager, 'favorites_changed'):
            try:
                self._favorites_manager.favorites_changed.disconnect(self._on_favorites_loaded)
            except (TypeError, RuntimeError):
                pass  # Signal wasn't connected
        
        # Update reference
        old_count = self.count
        self._favorites_manager = new_manager
        
        # Connect new signal
        if hasattr(self._favorites_manager, 'favorites_changed'):
            self._favorites_manager.favorites_changed.connect(self._on_favorites_loaded)
        
        # Update UI
        self.update_indicator()
        
        logger.info(f"✓ FavoritesController synced with dockwidget manager (was {old_count}, now {self.count} favorites)")
        return True

    def on_tab_activated(self) -> None:
        """Handle tab activation."""
        super().on_tab_activated()
        self.update_indicator()

    def on_tab_deactivated(self) -> None:
        """Handle tab deactivation."""
        super().on_tab_deactivated()

    # === Public API ===
    
    def _on_favorites_loaded(self) -> None:
        """
        Handler for favorites_changed signal from FavoritesService.
        Updates the indicator when favorites are loaded/added/removed.
        """
        logger.info(f"✓ Favorites changed - updating UI (count: {self.count})")
        self.update_indicator()
        self.favorites_changed.emit()  # Propagate signal

    def update_indicator(self) -> None:
        """Update the favorites indicator badge with current count."""
        if not self._indicator_label:
            return

        count = self.count

        # Update text and styling
        if count > 0:
            self._indicator_label.setText(f"★ {count}")
            tooltip = f"★ {count} Favorites saved\nClick to apply or manage"
            style = self._get_indicator_style('active')
        else:
            self._indicator_label.setText("★")
            tooltip = "★ No favorites saved\nClick to add current filter"
            style = self._get_indicator_style('empty')

        self._indicator_label.setStyleSheet(style)
        self._indicator_label.setToolTip(tooltip)
        self._indicator_label.adjustSize()

    def handle_indicator_clicked(self) -> None:
        """
        Handle click on favorites indicator.

        Shows the favorites context menu.
        """
        
        # Lazy initialization fallback - if setup() was never called, do it now
        if not self._initialized:
            self.setup()
        
        self._show_favorites_menu()

    def add_current_to_favorites(self, name: Optional[str] = None) -> bool:
        """
        Add current filter configuration to favorites.

        Args:
            name: Optional favorite name (prompts if not provided)

        Returns:
            True if favorite was added successfully
        """
        expression = self.get_current_filter_expression()
        if not expression:
            QMessageBox.warning(
                self.dockwidget,
                self.tr("No Filter"),
                self.tr("No active filter to save.")
            )
            return False

        if not name:
            name, ok = QInputDialog.getText(
                self.dockwidget,
                self.tr("Add Favorite"),
                self.tr("Favorite name:"),
                text=""
            )
            if not ok or not name:
                return False

        if not self._validate_favorite_name(name):
            return False

        # Create favorite with current filter state
        success = self._create_favorite(name, expression)
        if success:
            self.favorite_added.emit(name)
            self.favorites_changed.emit()
            self.update_indicator()
            self._show_success(self.tr("Favorite '{}' added successfully").format(name))

        return success

    def apply_favorite(self, favorite_id: str) -> bool:
        """
        Apply a saved favorite filter.

        Args:
            favorite_id: ID of the favorite to apply

        Returns:
            True if favorite was applied successfully
        """
        if not self._favorites_manager:
            return False

        favorite = self._favorites_manager.get_favorite(favorite_id)
        if not favorite:
            logger.warning(f"Favorite not found: {favorite_id}")
            return False

        # Apply the favorite expression
        success = self._apply_favorite_expression(favorite)
        if success:
            # Update use count
            self._favorites_manager.mark_favorite_used(favorite_id)
            self.favorite_applied.emit(favorite.name)
            logger.info(f"Applied favorite: {favorite.name}")

        return success

    def remove_favorite(self, favorite_id: str) -> bool:
        """
        Remove a favorite.

        Args:
            favorite_id: ID of the favorite to remove

        Returns:
            True if favorite was removed successfully
        """
        if not self._favorites_manager:
            return False

        favorite = self._favorites_manager.get_favorite(favorite_id)
        if not favorite:
            return False

        name = favorite.name
        success = self._favorites_manager.remove_favorite(favorite_id)
        if success:
            self._favorites_manager.save()
            self.favorite_removed.emit(name)
            self.favorites_changed.emit()
            self.update_indicator()
            logger.info(f"Removed favorite: {name}")

        return success

    def get_current_filter_expression(self) -> str:
        """
        Get the current filter expression.

        Tries multiple sources in order:
        1. Expression widget (if exists and has content)
        2. Current layer's subsetString (the actual applied filter)
        3. Source layer from combobox's subsetString

        Returns:
            The current filter expression, or empty string if none
        """
        try:
            # Source 1: Try expression widget
            if hasattr(self.dockwidget, 'mQgsFieldExpressionWidget_filtering_active_expression'):
                widget = self.dockwidget.mQgsFieldExpressionWidget_filtering_active_expression
                if hasattr(widget, 'expression'):
                    expr = widget.expression()
                    if expr and expr.strip():
                        return expr
                elif hasattr(widget, 'currentText'):
                    expr = widget.currentText()
                    if expr and expr.strip():
                        return expr

            # Source 2: Try current layer's subsetString
            if hasattr(self.dockwidget, 'current_layer') and self.dockwidget.current_layer:
                subset = self.dockwidget.current_layer.subsetString()
                if subset and subset.strip():
                    return subset

            # Source 3: Try filtering source layer combobox
            if hasattr(self.dockwidget, 'comboBox_filtering_current_layer'):
                layer = self.dockwidget.comboBox_filtering_current_layer.currentLayer()
                if layer:
                    subset = layer.subsetString()
                    if subset and subset.strip():
                        return subset

            return ""
        except Exception as e:
            logger.debug(f"Could not get current expression: {e}")
            return ""

    def get_all_favorites(self) -> List['FilterFavorite']:
        """
        Get all favorites.

        Returns:
            List of all favorites
        """
        if not self._favorites_manager:
            return []
        return self._favorites_manager.get_all_favorites()

    def get_recent_favorites(self, limit: int = 10) -> List['FilterFavorite']:
        """
        Get recent favorites.

        Args:
            limit: Maximum number of favorites to return

        Returns:
            List of recent favorites
        """
        if not self._favorites_manager:
            return []
        return self._favorites_manager.get_recent_favorites(limit=limit)

    def export_favorites(self, filepath: Optional[str] = None) -> bool:
        """
        Export favorites to a JSON file.

        Args:
            filepath: Path to export file (prompts if not provided)

        Returns:
            True if export was successful
        """
        if not filepath:
            filepath, _ = QFileDialog.getSaveFileName(
                self.dockwidget,
                self.tr("Export Favorites"),
                "favorites.json",
                self.tr("JSON Files (*.json)")
            )

        if not filepath or not self._favorites_manager:
            return False

        if self._favorites_manager.export_to_file(filepath):
            self._show_success(self.tr("Exported {} favorites").format(self.count))
            return True
        else:
            self._show_warning(self.tr("Failed to export favorites"))
            return False

    def import_favorites(
        self,
        filepath: Optional[str] = None,
        merge: Optional[bool] = None
    ) -> int:
        """
        Import favorites from a JSON file.

        Args:
            filepath: Path to import file (prompts if not provided)
            merge: True to merge, False to replace (prompts if not provided)

        Returns:
            Number of favorites imported
        """
        if not filepath:
            filepath, _ = QFileDialog.getOpenFileName(
                self.dockwidget,
                self.tr("Import Favorites"),
                "",
                self.tr("JSON Files (*.json)")
            )

        if not filepath or not self._favorites_manager:
            return 0

        if merge is None:
            result = QMessageBox.question(
                self.dockwidget,
                self.tr("Import Favorites"),
                self.tr("Merge with existing favorites?\n\n"
                "Yes = Add to existing\n"
                "No = Replace all existing"),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if result == QMessageBox.Cancel:
                return 0
            merge = (result == QMessageBox.Yes)

        count = self._favorites_manager.import_from_file(filepath, merge=merge)

        if count > 0:
            self._favorites_manager.save_to_project()
            self.favorites_changed.emit()
            self.update_indicator()
            self._show_success(self.tr("Imported {} favorites").format(count))
        else:
            self._show_warning(self.tr("No favorites imported"))

        return count

    def show_manager_dialog(self) -> None:
        """Show the favorites manager dialog."""
        try:
            # Check if favorites manager is available
            if not self._favorites_manager:
                self._show_warning(self.tr("Favorites manager not initialized. Please restart FilterMate."))
                return
            
            from ..dialogs import FavoritesManagerDialog
            # Note: FavoritesManagerDialog(favorites_manager, parent) - order matters!
            dialog = FavoritesManagerDialog(self._favorites_manager, self.dockwidget)
            
            # Connect the favoriteApplied signal to apply the favorite
            dialog.favoriteApplied.connect(self.apply_favorite)
            
            dialog.exec_()
            # Refresh after dialog closes
            self.favorites_changed.emit()
            self.update_indicator()
        except ImportError as e:
            logger.warning(f"FavoritesManagerDialog not available: {e}")
            self._show_warning(self.tr("Favorites manager dialog not available"))
        except Exception as e:
            logger.error(f"Error showing favorites manager: {e}")
            self._show_warning(f"Error: {e}")

    # === Private Methods ===

    def _find_indicator_label(self) -> None:
        """Find the favorites indicator label in dockwidget."""
        if hasattr(self.dockwidget, 'favorites_indicator_label'):
            self._indicator_label = self.dockwidget.favorites_indicator_label

    def _init_favorites_manager(self) -> None:
        """
        Initialize the favorites manager.
        
        FIX 2026-01-19: The controller should NOT create its own FavoritesService.
        The FavoritesService is created by FilterMateApp and should be passed via
        dockwidget._favorites_manager AFTER init_filterMate_db() configures it.
        
        If _favorites_manager is not available yet, we create a temporary empty one
        and wait for sync_with_dockwidget_manager() to be called later.
        """
        
        # PRIORITY 1: Check if already initialized on dockwidget (from FilterMateApp)
        if hasattr(self.dockwidget, '_favorites_manager') and self.dockwidget._favorites_manager:
            self._favorites_manager = self.dockwidget._favorites_manager
            return

        # PRIORITY 2: Try to read project_uuid from QGIS project variables
        # This works if init_filterMate_db() was called BEFORE dockwidget creation
        project = getattr(self.dockwidget, 'PROJECT', None) or QgsProject.instance()
        project_uuid = None
        db_path = None
        
        if project:
            scope = QgsExpressionContextUtils.projectScope(project)
            project_uuid = scope.variable('filterMate_db_project_uuid')
            
            if project_uuid:
                from ...config.config import ENV_VARS
                import os
                db_path = os.path.normpath(
                    ENV_VARS.get("PLUGIN_CONFIG_DIRECTORY", "") + os.sep + 'filterMate_db.sqlite'
                )
                if not os.path.exists(db_path):
                    db_path = None
        
        # PRIORITY 3: Create FavoritesService and configure if possible
        try:
            from ...core.services.favorites_service import FavoritesService
            self._favorites_manager = FavoritesService()
            
            # Configure with database if available
            if project_uuid and db_path:
                self._favorites_manager.set_database(db_path, str(project_uuid))
            else:
                pass  # block was empty

            # Store reference on dockwidget (may be overwritten by FilterMateApp later)
            self.dockwidget._favorites_manager = self._favorites_manager
            logger.debug(f"FavoritesManager initialized with {self.count} favorites")

        except Exception as e:
            import traceback
            logger.error(f"Failed to initialize FavoritesManager: {e}")
            self._favorites_manager = None
        

    def _restore_spatial_config(self, favorite: 'FilterFavorite') -> bool:
        """
        Restore spatial configuration from favorite to dockwidget.
        
        This ensures task_features (selected FIDs) are available when
        launchTaskEvent is called, so the filter task can rebuild
        EXISTS expressions correctly.
        
        Args:
            favorite: Favorite containing spatial_config
            
        Returns:
            True if config was restored successfully
        """
        if not favorite.spatial_config:
            logger.warning(f"Favorite '{favorite.name}' has no spatial_config to restore")
            return False
        
        try:
            from qgis.core import QgsProject
            config = favorite.spatial_config
            
            # Restore selected feature IDs (task_features)
            if 'task_feature_ids' in config and self.dockwidget.current_layer:
                feature_ids = config['task_feature_ids']
                logger.info(f"Restoring {len(feature_ids)} task_feature IDs from favorite")
                
                # Fetch actual QgsFeature objects from the source layer
                source_layer = self.dockwidget.current_layer
                features = []
                for fid in feature_ids:
                    feature = source_layer.getFeature(fid)
                    if feature and feature.isValid():
                        features.append(feature)
                    else:
                        logger.warning(f"  ⚠️ Could not fetch feature {fid} from {source_layer.name()}")
                
                if features:
                    logger.info(f"  → Loaded {len(features)} features from {len(feature_ids)} FIDs")
                    # Store in dockwidget for get_current_features() to pick up
                    self.dockwidget._restored_task_features = features
                    logger.info(f"  ✓ Stored {len(features)} features in dockwidget._restored_task_features")
                else:
                    logger.warning(f"  ⚠️ Could not load any features from {len(feature_ids)} FIDs!")
            
            # Restore predicates if present
            if 'predicates' in config:
                predicates = config['predicates']
                logger.info(f"Restoring predicates: {list(predicates.keys())}")
                # Store in dockwidget for task to pick up
                self.dockwidget._restored_predicates = predicates
            
            # Restore buffer settings if present
            if 'buffer_value' in config:
                buffer_value = config['buffer_value']
                logger.info(f"Restoring buffer_value: {buffer_value}")
                # Note: Set buffer widget value
                if hasattr(self.dockwidget, 'mQgsDoubleSpinBox_filtering_buffer_value'):
                    self.dockwidget.mQgsDoubleSpinBox_filtering_buffer_value.setValue(float(buffer_value))
                    logger.info(f"  ✓ Buffer widget set to {buffer_value}")
            
            logger.info(f"✓ Spatial config restored from favorite '{favorite.name}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to restore spatial_config: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _get_indicator_style(self, state: str) -> str:
        """Get stylesheet for indicator state."""
        style_data = FAVORITES_STYLES.get(state, FAVORITES_STYLES['empty'])
        # v4.0: Harmonized with BackendIndicatorWidget - soft "mousse" style
        return f"""
            QLabel#label_favorites_indicator {{
                color: {style_data['color']};
                font-size: 8pt;
                font-weight: 500;
                padding: 2px 8px;
                border-radius: 10px;
                border: none;
                background-color: {style_data['background']};
            }}
            QLabel#label_favorites_indicator:hover {{
                background-color: {style_data['hover']};
            }}
        """

    def _show_favorites_menu(self) -> None:
        """Show context menu with favorites options."""
        menu = QMenu(self.dockwidget)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #cccccc;
                padding: 5px;
            }
            QMenu::item {
                padding: 6px 20px;
            }
            QMenu::item:selected {
                background-color: #f39c12;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background-color: #cccccc;
                margin: 3px 10px;
            }
        """)

        # === QUICK FILTER SECTION (Favorites) ===
        favorites = self.get_all_favorites()
        
        if favorites:
            # Header for quick filter
            header = menu.addAction(self.tr("⚡ Quick Filter ({})").format(len(favorites)))
            header.setEnabled(False)
            font = header.font()
            font.setBold(True)
            header.setFont(font)

            # Show favorites directly in menu for quick access
            # Sort by use_count (most used first), then by name
            sorted_favs = sorted(favorites, key=lambda f: (-f.use_count, f.name.lower()))
            display_favs = sorted_favs[:8]
            
            for fav in display_favs:
                layers_count = fav.get_layers_count() if hasattr(fav, 'get_layers_count') else 1
                fav_text = f"★ {fav.get_display_name(30)}"
                if layers_count > 1:
                    fav_text += f" [{layers_count}]"

                action = menu.addAction(fav_text)
                action.setData(('apply', fav.id))
                # Build tooltip with expression preview
                tooltip = f"{fav.name}\n{fav.get_preview(100)}"
                if fav.use_count > 0:
                    tooltip += "\n" + self.tr("Used {} times").format(fav.use_count)
                action.setToolTip(tooltip)

            if len(favorites) > 8:
                more_action = menu.addAction(self.tr("  ➤ See all ({})...").format(len(favorites)))
                more_action.setData('__SHOW_ALL__')
                
            menu.addSeparator()

        # === ADD TO FAVORITES ===
        current_expression = self.get_current_filter_expression()
        add_action = menu.addAction(self.tr("⭐ Add current filter to favorites"))
        add_action.setData('__ADD_FAVORITE__')
        if not current_expression:
            add_action.setEnabled(False)
            add_action.setText(self.tr("⭐ Add filter (no active filter)"))

        menu.addSeparator()

        # === MANAGEMENT OPTIONS ===
        manage_action = menu.addAction(self.tr("⚙️ Manage favorites..."))
        manage_action.setData('__MANAGE__')

        export_action = menu.addAction(self.tr("📤 Export..."))
        export_action.setData('__EXPORT__')

        import_action = menu.addAction(self.tr("📥 Import..."))
        import_action.setData('__IMPORT__')
        
        # === GLOBAL FAVORITES SUBMENU ===
        menu.addSeparator()
        global_menu = menu.addMenu(self.tr("🌐 Global Favorites"))
        
        # Add current favorites as global options
        if favorites:
            copy_global_menu = global_menu.addMenu(self.tr("Copy to global..."))
            for fav in favorites[:5]:
                action = copy_global_menu.addAction(f"  {fav.name}")
                action.setData(('copy_to_global', fav.id))
            if len(favorites) > 5:
                copy_global_menu.addAction(self.tr("  ...")).setEnabled(False)
        
        # Show global favorites
        global_favorites = self._get_global_favorites()
        if global_favorites:
            global_menu.addSeparator()
            global_menu.addAction(self.tr("── Available global favorites ──")).setEnabled(False)
            for gfav in global_favorites[:5]:
                action = global_menu.addAction(f"  📌 {gfav.name}")
                action.setData(('apply_global', gfav.id))
            if len(global_favorites) > 5:
                more_action = global_menu.addAction(self.tr("  ➤ See all ({})...").format(len(global_favorites)))
                more_action.setData('__SHOW_GLOBAL__')
        else:
            global_menu.addAction(self.tr("(No global favorites)")).setEnabled(False)
        
        # === MAINTENANCE ===
        menu.addSeparator()
        maintenance_menu = menu.addMenu(self.tr("🔧 Maintenance"))
        
        backup_action = maintenance_menu.addAction(self.tr("💾 Backup to project (.qgz)"))
        backup_action.setData('__BACKUP_TO_PROJECT__')
        
        restore_action = maintenance_menu.addAction(self.tr("📂 Restore from project"))
        restore_action.setData('__RESTORE_FROM_PROJECT__')
        
        maintenance_menu.addSeparator()
        
        cleanup_action = maintenance_menu.addAction(self.tr("🧹 Clean up orphan projects"))
        cleanup_action.setData('__CLEANUP_ORPHANS__')
        
        stats_action = maintenance_menu.addAction(self.tr("📊 Database statistics"))
        stats_action.setData('__SHOW_STATS__')

        # Show menu
        selected_action = menu.exec_(QCursor.pos())

        if selected_action:
            action_data = selected_action.data()
            self._handle_menu_action(action_data)

    def _handle_menu_action(self, action_data: Any) -> None:
        """Handle favorites menu action."""
        if action_data == '__ADD_FAVORITE__':
            self.add_current_to_favorites()
        elif action_data == '__MANAGE__':
            self.show_manager_dialog()
        elif action_data == '__EXPORT__':
            self.export_favorites()
        elif action_data == '__IMPORT__':
            self.import_favorites()
        elif action_data == '__SHOW_ALL__':
            self.show_manager_dialog()
        elif action_data == '__SHOW_GLOBAL__':
            self._show_global_favorites_dialog()
        elif action_data == '__BACKUP_TO_PROJECT__':
            self._backup_to_project()
        elif action_data == '__RESTORE_FROM_PROJECT__':
            self._restore_from_project()
        elif action_data == '__CLEANUP_ORPHANS__':
            self._cleanup_orphan_projects()
        elif action_data == '__SHOW_STATS__':
            self._show_database_stats()
        elif isinstance(action_data, tuple):
            if action_data[0] == 'apply':
                self.apply_favorite(action_data[1])
            elif action_data[0] == 'apply_global':
                self._apply_global_favorite(action_data[1])
            elif action_data[0] == 'copy_to_global':
                self._copy_to_global(action_data[1])

    def _validate_favorite_name(self, name: str) -> bool:
        """Validate favorite name."""
        if not name or not name.strip():
            QMessageBox.warning(
                self.dockwidget,
                self.tr("Invalid Name"),
                self.tr("Favorite name cannot be empty.")
            )
            return False

        # Check for duplicates
        if self._favorites_manager:
            existing = self._favorites_manager.get_favorite_by_name(name)
            if existing:
                result = QMessageBox.question(
                    self.dockwidget,
                    self.tr("Duplicate Name"),
                    self.tr("A favorite named '{}' already exists.\n"
                    "Do you want to replace it?").format(name),
                    QMessageBox.Yes | QMessageBox.No
                )
                if result != QMessageBox.Yes:
                    return False
                # Remove existing
                self._favorites_manager.remove_favorite(existing.id)

        return True

    def _create_favorite(self, name: str, expression: str) -> bool:
        """
        Create a new favorite.
        
        ENHANCEMENT 2026-01-18: Capture spatial_config (task_features, predicates, etc.)
        so favorites can be properly restored with full geometric context.
        """
        if not self._favorites_manager:
            return False

        try:
            # Get layer info
            layer = self.dockwidget.current_layer
            layer_name = layer.name() if layer else None
            layer_provider = layer.providerType() if layer else None

            # Collect all filtered layers (remote layers with active filters)
            # Iterate through all vector layers to find those with filters
            remote_layers = {}
            source_layer_id = layer.id() if layer else None
            project = QgsProject.instance()
            
            for layer_id, map_layer in project.mapLayers().items():
                # Skip non-vector layers
                if not hasattr(map_layer, 'subsetString'):
                    continue
                # Skip the source layer (already captured in main expression)
                if layer_id == source_layer_id:
                    continue
                # Check if layer has an active filter
                subset = map_layer.subsetString()
                if subset and subset.strip():
                    remote_layers[map_layer.name()] = {
                        'expression': subset,
                        'feature_count': map_layer.featureCount() if map_layer.isValid() else 0,
                        'layer_id': layer_id,
                        'provider': map_layer.providerType()
                    }
            
            # ENHANCEMENT 2026-01-18: Capture spatial configuration
            spatial_config = self._capture_spatial_config()
            
            # Use FavoritesService.add_favorite() with individual parameters
            favorite_id = self._favorites_manager.add_favorite(
                name=name,
                expression=expression,
                layer_name=layer_name,
                layer_provider=layer_provider,
                remote_layers=remote_layers if remote_layers else None,
                spatial_config=spatial_config
            )
            
            if favorite_id:
                # Note: Favorite already saved to database in add_favorite()
                # save() is a no-op but we call it for consistency
                logger.debug(f"Favorite '{name}' created successfully (ID: {favorite_id})")
                self._favorites_manager.save()  # No-op, already persisted
                return True
            else:
                logger.warning(f"Failed to create favorite '{name}' - add_favorite() returned None")
            return False

        except Exception as e:
            logger.error(f"Failed to create favorite: {e}")
            return False
    
    def _capture_spatial_config(self) -> dict:
        """
        Capture current spatial configuration for favorite restoration.
        
        This ensures favorites can be restored with full geometric context,
        including selected features, predicates, buffer settings, etc.
        
        Returns:
            dict: Spatial configuration
        """
        config = {}
        
        try:
            # Capture task_features (selected feature IDs)
            features, _ = self.dockwidget.get_current_features()
            if features:
                feature_ids = [f.id() for f in features if f.isValid()]
                if feature_ids:
                    config['task_feature_ids'] = feature_ids
                    logger.info(f"Captured {len(feature_ids)} task_feature IDs for favorite")
            
            # Capture predicates from dockwidget if available
            if hasattr(self.dockwidget, 'PROJECT_LAYERS') and self.dockwidget.current_layer:
                layer_id = self.dockwidget.current_layer.id()
                if layer_id in self.dockwidget.PROJECT_LAYERS:
                    layer_data = self.dockwidget.PROJECT_LAYERS[layer_id]
                    predicates = layer_data.get('filtering', {}).get('predicates', {})
                    if predicates:
                        config['predicates'] = predicates
                        logger.info(f"Captured predicates: {list(predicates.keys())}")
            
            # Capture buffer value if set
            # Note: Read buffer value from widget
            if hasattr(self.dockwidget, 'mQgsDoubleSpinBox_filtering_buffer_value'):
                buffer_value = self.dockwidget.mQgsDoubleSpinBox_filtering_buffer_value.value()
                if buffer_value != 0.0:
                    config['buffer_value'] = buffer_value
                    logger.info(f"Captured buffer_value: {buffer_value}")
            
            logger.info(f"Spatial config captured: {list(config.keys())}")
            
        except Exception as e:
            logger.warning(f"Failed to capture spatial config: {e}")
        
        return config if config else None

    def _apply_favorite_expression(self, favorite: 'FilterFavorite') -> bool:
        """Apply a favorite's expression to the filtering widgets and execute the filter."""
        try:
            # Set expression in widget
            if hasattr(self.dockwidget, 'mQgsFieldExpressionWidget_filtering_active_expression'):
                widget = self.dockwidget.mQgsFieldExpressionWidget_filtering_active_expression
                if hasattr(widget, 'setExpression'):
                    widget.setExpression(favorite.expression)
                elif hasattr(widget, 'setCurrentText'):
                    widget.setCurrentText(favorite.expression)

            # CRITICAL FIX 2026-01-18: Do NOT apply remote layer filters directly via setSubsetString!
            # The filters contain __source alias which _clean_corrupted_subsets() will erase.
            # Instead, we restore the spatial context (task_features, predicates, etc.) from
            # favorite.spatial_config so the filter task can REBUILD the remote filters properly.
            if favorite.remote_layers:
                logger.info(f"Favorite has {len(favorite.remote_layers)} remote layers")
                logger.info(f"  → Remote layers will be re-filtered by main filter task")
                logger.info(f"  → NOT applying filters directly to avoid __source cleanup")
            
            # Restore spatial configuration (task_features, predicates, buffer, etc.)
            if favorite.spatial_config:
                logger.info(f"Restoring spatial_config from favorite '{favorite.name}'...")
                self._restore_spatial_config(favorite)
            else:
                logger.warning(f"Favorite '{favorite.name}' has no spatial_config - remote layers may not filter correctly")

            # Trigger the filter action to apply the main expression
            if hasattr(self.dockwidget, 'launchTaskEvent'):
                self.dockwidget.launchTaskEvent(False, 'filter')
                logger.info(f"Filter triggered for favorite: {favorite.name}")
            
            return True

        except Exception as e:
            logger.error(f"Failed to apply favorite: {e}")
            return False

    def _show_success(self, message: str) -> None:
        """Show success message."""
        try:
            from ...infrastructure.feedback import show_success
            show_success("FilterMate", message)
        except ImportError:
            logger.info(f"Success: {message}")

    def _show_warning(self, message: str) -> None:
        """Show warning message."""
        try:
            from ...infrastructure.feedback import show_warning
            show_warning("FilterMate", message)
        except ImportError:
            logger.warning(message)
    
    # ─────────────────────────────────────────────────────────────────
    # Global Favorites & Maintenance Methods
    # ─────────────────────────────────────────────────────────────────
    
    def _get_global_favorites(self) -> List['FilterFavorite']:
        """Get global favorites from the manager."""
        if not self._favorites_manager:
            return []
        
        if hasattr(self._favorites_manager, 'get_global_favorites'):
            return self._favorites_manager.get_global_favorites()
        
        return []
    
    def _apply_global_favorite(self, favorite_id: str) -> bool:
        """Apply a global favorite."""
        if not self._favorites_manager:
            return False
        
        # First, import the global favorite to the current project
        if hasattr(self._favorites_manager, 'import_global_to_project'):
            new_id = self._favorites_manager.import_global_to_project(favorite_id)
            if new_id:
                # Then apply the newly imported favorite
                self.update_indicator()
                return self.apply_favorite(new_id)
        
        return False
    
    def _copy_to_global(self, favorite_id: str) -> bool:
        """Copy a favorite to global favorites."""
        if not self._favorites_manager:
            return False
        
        if hasattr(self._favorites_manager, 'copy_to_global'):
            new_id = self._favorites_manager.copy_to_global(favorite_id)
            if new_id:
                self._show_success(self.tr("Favorite copied to global favorites"))
                return True
        
        self._show_warning(self.tr("Failed to copy to global"))
        return False
    
    def _show_global_favorites_dialog(self) -> None:
        """Show dialog for managing global favorites."""
        # For now, show a message - full dialog can be added later
        global_count = len(self._get_global_favorites())
        QMessageBox.information(
            self.dockwidget,
            self.tr("Global Favorites"),
            self.tr("There are {} global favorite(s) available.\n\n"
            "Global favorites are shared between all projects.").format(global_count)
        )
    
    def _backup_to_project(self) -> None:
        """Backup favorites to the QGIS project file."""
        if not self._favorites_manager:
            return
        
        if hasattr(self._favorites_manager, 'save_to_project_file'):
            from qgis.core import QgsProject
            success = self._favorites_manager.save_to_project_file(QgsProject.instance())
            if success:
                self._show_success(self.tr("Saved {} favorite(s) to project file").format(self.count))
            else:
                self._show_warning(self.tr("Backup failed"))
    
    def _restore_from_project(self) -> None:
        """Restore favorites from the QGIS project file."""
        if not self._favorites_manager:
            return
        
        if hasattr(self._favorites_manager, 'restore_from_project_file'):
            from qgis.core import QgsProject
            count = self._favorites_manager.restore_from_project_file(QgsProject.instance())
            if count > 0:
                self.update_indicator()
                self._show_success(self.tr("Restored {} favorite(s) from project file").format(count))
            else:
                self._show_warning(self.tr("No favorites to restore found in project"))
    
    def _cleanup_orphan_projects(self) -> None:
        """Clean up orphan projects from the database."""
        try:
            from ...core.services.favorites_service import FavoritesService
            from ...config.config import ENV_VARS
            import os

            db_path = os.path.normpath(
                ENV_VARS.get("PLUGIN_CONFIG_DIRECTORY", "") + os.sep + 'filterMate_db.sqlite'
            )

            service = FavoritesService()
            service.set_database(db_path)
            deleted_count, deleted_ids = service.cleanup_orphan_projects()

            if deleted_count > 0:
                self._show_success(self.tr("Cleaned up {} orphan project(s)").format(deleted_count))
            else:
                self._show_success(self.tr("No orphan projects to clean up"))

        except Exception as e:
            logger.error(f"Error cleaning up orphan projects: {e}")
            self._show_warning(self.tr("Error: {}").format(e))
    
    def _show_database_stats(self) -> None:
        """Show database statistics dialog."""
        try:
            from ...core.services.favorites_service import FavoritesService
            from ...config.config import ENV_VARS
            import os

            db_path = os.path.normpath(
                ENV_VARS.get("PLUGIN_CONFIG_DIRECTORY", "") + os.sep + 'filterMate_db.sqlite'
            )

            service = FavoritesService()
            service.set_database(db_path)
            stats = service.get_database_statistics()

            if 'error' in stats:
                self._show_warning(self.tr("Error: {}").format(stats['error']))
                return

            # Format statistics message - build translatable parts
            db_file = os.path.basename(stats.get('database_path', 'N/A'))
            db_size = stats.get('database_size_kb', 0)
            total_projects = stats.get('total_projects', 0)
            orphan_projects = stats.get('orphan_projects', 0)
            total_favorites = stats.get('total_favorites', 0)
            orphan_favorites = stats.get('orphan_favorites', 0)
            global_favorites = stats.get('global_favorites', 0)

            msg = self.tr("FilterMate Database Statistics") + "\n\n"
            msg += self.tr("File: {}").format(db_file) + "\n"
            msg += self.tr("Size: {:.1f} KB").format(db_size) + "\n\n"
            msg += self.tr("Projects: {}").format(total_projects) + "\n"
            msg += self.tr("   Orphans: {}").format(orphan_projects) + "\n\n"
            msg += self.tr("Favorites: {}").format(total_favorites) + "\n"
            msg += self.tr("   Orphans: {}").format(orphan_favorites) + "\n"
            msg += self.tr("   Global: {}").format(global_favorites) + "\n"

            # Add top projects
            top_projects = stats.get('top_projects', [])
            if top_projects:
                msg += "\n" + self.tr("Projects with most favorites:") + "\n"
                for proj in top_projects[:3]:
                    msg += f"   - {proj['name']}: {proj['favorites']}\n"

            QMessageBox.information(
                self.dockwidget,
                self.tr("FilterMate Statistics"),
                msg
            )

        except Exception as e:
            logger.error(f"Error showing database stats: {e}")
            self._show_warning(self.tr("Error: {}").format(e))
