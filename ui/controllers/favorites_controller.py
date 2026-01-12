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
    from core.services.favorites_service import FavoritesService, FilterFavorite

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
        self._initialized = True
        logger.debug("FavoritesController setup complete")

    def teardown(self) -> None:
        """Clean up resources."""
        self._favorites_manager = None
        super().teardown()

    def on_tab_activated(self) -> None:
        """Handle tab activation."""
        super().on_tab_activated()
        self.update_indicator()

    def on_tab_deactivated(self) -> None:
        """Handle tab deactivation."""
        super().on_tab_deactivated()

    # === Public API ===

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
                "No Filter",
                "No active filter to save."
            )
            return False

        if not name:
            name, ok = QInputDialog.getText(
                self.dockwidget,
                "Add Favorite",
                "Favorite name:",
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
            self._show_success(f"Favorite '{name}' added successfully")

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

        favorite = self._favorites_manager.get_by_id(favorite_id)
        if not favorite:
            logger.warning(f"Favorite not found: {favorite_id}")
            return False

        # Apply the favorite expression
        success = self._apply_favorite_expression(favorite)
        if success:
            # Update use count
            self._favorites_manager.increment_use_count(favorite_id)
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

        favorite = self._favorites_manager.get_by_id(favorite_id)
        if not favorite:
            return False

        name = favorite.name
        success = self._favorites_manager.remove(favorite_id)
        if success:
            self._favorites_manager.save_to_project()
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
                "Export Favorites",
                "favorites.json",
                "JSON Files (*.json)"
            )

        if not filepath or not self._favorites_manager:
            return False

        if self._favorites_manager.export_to_file(filepath):
            self._show_success(f"Exported {self.count} favorites")
            return True
        else:
            self._show_warning("Failed to export favorites")
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
                "Import Favorites",
                "",
                "JSON Files (*.json)"
            )

        if not filepath or not self._favorites_manager:
            return 0

        if merge is None:
            result = QMessageBox.question(
                self.dockwidget,
                "Import Favorites",
                "Merge with existing favorites?\n\n"
                "Yes = Add to existing\n"
                "No = Replace all existing",
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
            self._show_success(f"Imported {count} favorites")
        else:
            self._show_warning("No favorites imported")

        return count

    def show_manager_dialog(self) -> None:
        """Show the favorites manager dialog."""
        # Try to use new FavoritesManagerDialog if available
        try:
            from ui.dialogs import FavoritesManagerDialog
            dialog = FavoritesManagerDialog(self.dockwidget, self._favorites_manager)
            dialog.exec_()
            # Refresh after dialog closes
            self.favorites_changed.emit()
            self.update_indicator()
        except ImportError:
            # Fallback to dockwidget method
            if hasattr(self.dockwidget, '_show_favorites_manager_dialog'):
                self.dockwidget._show_favorites_manager_dialog()

    # === Private Methods ===

    def _find_indicator_label(self) -> None:
        """Find the favorites indicator label in dockwidget."""
        if hasattr(self.dockwidget, 'favorites_indicator_label'):
            self._indicator_label = self.dockwidget.favorites_indicator_label

    def _init_favorites_manager(self) -> None:
        """Initialize the favorites manager."""
        # Check if already initialized on dockwidget
        if hasattr(self.dockwidget, '_favorites_manager') and self.dockwidget._favorites_manager:
            self._favorites_manager = self.dockwidget._favorites_manager
            return

        # Create new manager
        try:
            from core.services.favorites_service import FavoritesService
            self._favorites_manager = FavoritesService()

            # Try to connect to database
            project = getattr(self.dockwidget, 'PROJECT', None) or QgsProject.instance()
            if project:
                scope = QgsExpressionContextUtils.projectScope(project)
                project_uuid = scope.variable('filterMate_db_project_uuid')
                if project_uuid:
                    from config.config import ENV_VARS
                    import os
                    db_path = os.path.normpath(
                        ENV_VARS.get("PLUGIN_CONFIG_DIRECTORY", "") + os.sep + 'filterMate_db.sqlite'
                    )
                    if os.path.exists(db_path):
                        self._favorites_manager.set_database(db_path, str(project_uuid))

            self._favorites_manager.load_from_project()

            # Store reference on dockwidget
            self.dockwidget._favorites_manager = self._favorites_manager
            logger.debug(f"FavoritesManager initialized with {self.count} favorites")

        except Exception as e:
            logger.error(f"Failed to initialize FavoritesManager: {e}")
            self._favorites_manager = None

    def _get_indicator_style(self, state: str) -> str:
        """Get stylesheet for indicator state."""
        style_data = FAVORITES_STYLES.get(state, FAVORITES_STYLES['empty'])
        return f"""
            QLabel#label_favorites_indicator {{
                color: {style_data['color']};
                font-size: 9pt;
                font-weight: 600;
                padding: 3px 10px;
                border-radius: 12px;
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
                padding: 5px 20px;
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

        # === ADD TO FAVORITES ===
        current_expression = self.get_current_filter_expression()
        add_action = menu.addAction("⭐ Add Current Filter to Favorites")
        add_action.setData('__ADD_FAVORITE__')
        if not current_expression:
            add_action.setEnabled(False)
            add_action.setText("⭐ Add Current Filter (no filter active)")

        menu.addSeparator()

        # === FAVORITES LIST ===
        favorites = self.get_all_favorites()

        if favorites:
            header = menu.addAction(f"📋 Saved Favorites ({len(favorites)})")
            header.setEnabled(False)

            recent_favs = self.get_recent_favorites(limit=10)
            for fav in recent_favs:
                layers_count = fav.get_layers_count() if hasattr(fav, 'get_layers_count') else 1
                fav_text = f"  ★ {fav.get_display_name(25)}"
                if layers_count > 1:
                    fav_text += f" [{layers_count}]"
                if fav.use_count > 0:
                    fav_text += f" ({fav.use_count}×)"

                action = menu.addAction(fav_text)
                action.setData(('apply', fav.id))
                action.setToolTip(fav.get_preview(80))

            if len(favorites) > 10:
                more_action = menu.addAction(f"  ... {len(favorites) - 10} more favorites")
                more_action.setData('__SHOW_ALL__')
        else:
            no_favs = menu.addAction("(No favorites saved)")
            no_favs.setEnabled(False)

        menu.addSeparator()

        # === MANAGEMENT OPTIONS ===
        manage_action = menu.addAction("⚙️ Manage Favorites...")
        manage_action.setData('__MANAGE__')

        export_action = menu.addAction("📤 Export Favorites...")
        export_action.setData('__EXPORT__')

        import_action = menu.addAction("📥 Import Favorites...")
        import_action.setData('__IMPORT__')

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
        elif isinstance(action_data, tuple) and action_data[0] == 'apply':
            self.apply_favorite(action_data[1])

    def _validate_favorite_name(self, name: str) -> bool:
        """Validate favorite name."""
        if not name or not name.strip():
            QMessageBox.warning(
                self.dockwidget,
                "Invalid Name",
                "Favorite name cannot be empty."
            )
            return False

        # Check for duplicates
        if self._favorites_manager:
            existing = self._favorites_manager.get_by_name(name)
            if existing:
                result = QMessageBox.question(
                    self.dockwidget,
                    "Duplicate Name",
                    f"A favorite named '{name}' already exists.\n"
                    "Do you want to replace it?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if result != QMessageBox.Yes:
                    return False
                # Remove existing
                self._favorites_manager.remove(existing.id)

        return True

    def _create_favorite(self, name: str, expression: str) -> bool:
        """Create a new favorite."""
        if not self._favorites_manager:
            return False

        try:
            from core.domain.favorites_manager import FilterFavorite

            # Get layer info
            layer = self.dockwidget.current_layer
            layer_name = layer.name() if layer else None
            layer_id = layer.id() if layer else None

            # Create favorite
            favorite = FilterFavorite(
                name=name,
                expression=expression,
                layer_name=layer_name,
                layer_id=layer_id
            )

            # Get remote layers if multi-layer filtering is active
            if hasattr(self.dockwidget, 'listWidget_filtering_remote_layers'):
                remote_layers = {}
                widget = self.dockwidget.listWidget_filtering_remote_layers
                for i in range(widget.count()):
                    item = widget.item(i)
                    if item and item.checkState() == Qt.Checked:
                        remote_layer_id = item.data(Qt.UserRole)
                        remote_layer = QgsProject.instance().mapLayer(remote_layer_id)
                        if remote_layer:
                            remote_layers[remote_layer.name()] = remote_layer_id
                favorite.remote_layers = remote_layers

            self._favorites_manager.add_favorite(favorite)
            self._favorites_manager.save_to_project()
            return True

        except Exception as e:
            logger.error(f"Failed to create favorite: {e}")
            return False

    def _apply_favorite_expression(self, favorite: 'FilterFavorite') -> bool:
        """Apply a favorite's expression to the filtering widgets."""
        try:
            # Set expression in widget
            if hasattr(self.dockwidget, 'mQgsFieldExpressionWidget_filtering_active_expression'):
                widget = self.dockwidget.mQgsFieldExpressionWidget_filtering_active_expression
                if hasattr(widget, 'setExpression'):
                    widget.setExpression(favorite.expression)
                elif hasattr(widget, 'setCurrentText'):
                    widget.setCurrentText(favorite.expression)

            # Handle remote layers if applicable
            if favorite.remote_layers and hasattr(self.dockwidget, 'listWidget_filtering_remote_layers'):
                widget = self.dockwidget.listWidget_filtering_remote_layers
                for i in range(widget.count()):
                    item = widget.item(i)
                    if item:
                        layer_id = item.data(Qt.UserRole)
                        if layer_id in favorite.remote_layers.values():
                            item.setCheckState(Qt.Checked)
                        else:
                            item.setCheckState(Qt.Unchecked)

            return True

        except Exception as e:
            logger.error(f"Failed to apply favorite: {e}")
            return False

    def _show_success(self, message: str) -> None:
        """Show success message."""
        try:
            from infrastructure.feedback import show_success
            show_success("FilterMate", message)
        except ImportError:
            logger.info(f"Success: {message}")

    def _show_warning(self, message: str) -> None:
        """Show warning message."""
        try:
            from infrastructure.feedback import show_warning
            show_warning("FilterMate", message)
        except ImportError:
            logger.warning(message)
