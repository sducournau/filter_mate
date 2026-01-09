"""
FilterMate FavoritesWidget.

Widget for favorites indicator and quick access menu.
Extracted from filter_mate_dockwidget.py for better modularity.
"""
from typing import Optional, Callable, List
import logging

try:
    from qgis.PyQt.QtWidgets import (
        QLabel, QMenu, QInputDialog, QDialog, QVBoxLayout,
        QFormLayout, QDialogButtonBox, QTextEdit, QLineEdit,
        QWidget
    )
    from qgis.PyQt.QtCore import pyqtSignal, Qt
    from qgis.PyQt.QtGui import QCursor
    from qgis.core import QgsProject, QgsExpressionContextUtils
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False
    QLabel = object
    pyqtSignal = lambda *args: None

logger = logging.getLogger(__name__)


class FavoritesWidget(QLabel if HAS_QGIS else object):
    """
    Widget for favorites indicator and quick access.
    
    Displays a badge showing favorites count and provides a context menu
    for quick access to saved filter favorites.
    
    Signals:
        favoriteAdded: Emitted when a favorite is added (favorite_id)
        favoriteApplied: Emitted when a favorite is applied (favorite_id)
        favoritesExported: Emitted when favorites are exported (file_path)
        favoritesImported: Emitted when favorites are imported (file_path)
        managerRequested: Emitted when user wants to open manager dialog
    """
    
    if HAS_QGIS:
        favoriteAdded = pyqtSignal(str)
        favoriteApplied = pyqtSignal(str)
        favoritesExported = pyqtSignal(str)
        favoritesImported = pyqtSignal(str)
        managerRequested = pyqtSignal()
    
    def __init__(
        self,
        favorites_manager,
        get_current_expression_func: Optional[Callable] = None,
        get_current_layer_func: Optional[Callable] = None,
        parent=None
    ):
        """
        Initialize FavoritesWidget.
        
        Args:
            favorites_manager: FavoritesManager instance for data access
            get_current_expression_func: Callback to get current filter expression
            get_current_layer_func: Callback to get current layer
            parent: Parent widget
        """
        if HAS_QGIS:
            super().__init__(parent)
        
        self._favorites_manager = favorites_manager
        self._get_expression = get_current_expression_func
        self._get_layer = get_current_layer_func
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Set up the favorites indicator UI."""
        if not HAS_QGIS:
            return
        
        self.setObjectName("label_favorites_indicator")
        self.setCursor(Qt.PointingHandCursor)
        
        # Initial update
        self.update_indicator()
    
    def mousePressEvent(self, event):
        """Handle click to show favorites menu."""
        if not HAS_QGIS:
            return
        
        self._show_favorites_menu()
    
    def _show_favorites_menu(self):
        """Show the favorites context menu."""
        if not HAS_QGIS:
            return
        
        menu = QMenu(self)
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
        add_action = menu.addAction("⭐ Add Current Filter to Favorites")
        add_action.setData('__ADD_FAVORITE__')
        
        # Check if there's an expression to save
        current_expression = ""
        if self._get_expression:
            current_expression = self._get_expression()
        
        if not current_expression:
            add_action.setEnabled(False)
            add_action.setText("⭐ Add Current Filter (no filter active)")
        
        menu.addSeparator()
        
        # === FAVORITES LIST ===
        favorites = []
        if self._favorites_manager:
            favorites = self._favorites_manager.get_all_favorites()
        
        if favorites:
            # Add header
            header = menu.addAction(f"📋 Saved Favorites ({len(favorites)})")
            header.setEnabled(False)
            
            # Show recent/most used first (up to 10)
            recent_favs = self._favorites_manager.get_recent_favorites(limit=10)
            for fav in recent_favs:
                layers_count = fav.get_layers_count() if hasattr(fav, 'get_layers_count') else 1
                fav_text = f"  ★ {fav.get_display_name(25)}"
                if layers_count > 1:
                    fav_text += f" [{layers_count}]"
                if fav.use_count > 0:
                    fav_text += f" ({fav.use_count}×)"
                action = menu.addAction(fav_text)
                action.setData(('apply', fav.id))
                
                # Build tooltip
                tooltip = fav.get_preview(80)
                if fav.remote_layers:
                    tooltip += f"\n\nLayers ({layers_count}):\n• {fav.layer_name or 'Source'}"
                    for remote_name in list(fav.remote_layers.keys())[:5]:
                        tooltip += f"\n• {remote_name}"
                    if len(fav.remote_layers) > 5:
                        tooltip += f"\n... and {len(fav.remote_layers) - 5} more"
                action.setToolTip(tooltip)
            
            # Show "More..." if there are more favorites
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
        
        # Show menu and handle selection
        selected_action = menu.exec_(QCursor.pos())
        
        if selected_action:
            self._handle_menu_action(selected_action.data())
    
    def _handle_menu_action(self, action_data):
        """Handle menu action selection."""
        if action_data == '__ADD_FAVORITE__':
            self.add_current_to_favorites()
        elif action_data == '__MANAGE__':
            self.managerRequested.emit()
        elif action_data == '__EXPORT__':
            self._export_favorites()
        elif action_data == '__IMPORT__':
            self._import_favorites()
        elif action_data == '__SHOW_ALL__':
            self.managerRequested.emit()
        elif isinstance(action_data, tuple) and action_data[0] == 'apply':
            self.favoriteApplied.emit(action_data[1])
    
    def add_current_to_favorites(self):
        """Add current filter configuration to favorites."""
        if not HAS_QGIS:
            return
        
        from datetime import datetime
        
        # Get expression
        expression = ""
        if self._get_expression:
            expression = self._get_expression()
        
        if not expression:
            logger.warning("No active filter to save as favorite")
            return
        
        # Get current layer info
        current_layer = None
        if self._get_layer:
            current_layer = self._get_layer()
        
        source_layer_id = None
        source_layer_name = None
        layer_provider = None
        
        if current_layer:
            source_layer_id = current_layer.id()
            source_layer_name = current_layer.name()
            layer_provider = current_layer.providerType()
        
        # Collect filtered remote layers
        remote_layers_data = {}
        project = QgsProject.instance()
        
        for layer_id, layer in project.mapLayers().items():
            if not hasattr(layer, 'subsetString'):
                continue
            if layer_id == source_layer_id:
                continue
            subset = layer.subsetString()
            if subset and subset.strip():
                remote_layers_data[layer.name()] = {
                    'expression': subset,
                    'feature_count': layer.featureCount(),
                    'layer_id': layer_id,
                    'provider': layer.providerType()
                }
        
        # Build default name
        layers_count = 1 + len(remote_layers_data)
        default_name = f"Filter ({layers_count} layers)" if layers_count > 1 else ""
        
        # Generate auto-description
        auto_description = self._generate_description(
            source_layer_name, expression, remote_layers_data
        )
        
        # Show dialog
        result = self._show_add_dialog(
            default_name, auto_description, layers_count
        )
        
        if result:
            name, description = result
            self._save_favorite(
                name=name,
                expression=expression,
                description=description,
                layer_name=source_layer_name,
                layer_provider=layer_provider,
                remote_layers=remote_layers_data
            )
    
    def _show_add_dialog(self, default_name: str, auto_description: str, 
                         layers_count: int) -> Optional[tuple]:
        """
        Show dialog to add favorite.
        
        Returns:
            Tuple of (name, description) or None if cancelled
        """
        if not HAS_QGIS:
            return None
        
        dialog = QDialog(self)
        dialog.setWindowTitle("FilterMate - Add to Favorites")
        dialog.setMinimumSize(380, 200)
        dialog.resize(420, 260)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        form_layout = QFormLayout()
        
        # Name input
        name_edit = QLineEdit()
        name_edit.setText(default_name)
        name_edit.setPlaceholderText("Enter a name for this filter")
        form_layout.addRow(
            f"Name ({layers_count} layer{'s' if layers_count > 1 else ''}):",
            name_edit
        )
        
        # Description input
        desc_edit = QTextEdit()
        desc_edit.setMaximumHeight(120)
        desc_edit.setText(auto_description)
        desc_edit.setPlaceholderText("Description (auto-generated, you can modify it)")
        form_layout.addRow("Description:", desc_edit)
        
        layout.addLayout(form_layout)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        
        if dialog.exec_() == QDialog.Accepted:
            name = name_edit.text().strip()
            description = desc_edit.toPlainText().strip()
            if name:
                return (name, description)
        
        return None
    
    def _save_favorite(self, name: str, expression: str, description: str,
                       layer_name: str = None, layer_provider: str = None,
                       remote_layers: dict = None):
        """Save a new favorite."""
        try:
            from core.services.favorites_service import FilterFavorite
        except ImportError:
            try:
                from ..core.services.favorites_service import FilterFavorite
            except ImportError:
                logger.error("Could not import FilterFavorite")
                return
        
        fav = FilterFavorite(
            name=name,
            expression=expression,
            layer_name=layer_name,
            layer_provider=layer_provider,
            remote_layers=remote_layers if remote_layers else None,
            description=description
        )
        
        self._favorites_manager.add_favorite(fav)
        self._favorites_manager.save_to_project()
        
        self.update_indicator()
        self.favoriteAdded.emit(fav.id)
        
        logger.info(f"Favorite saved: {name}")
    
    def _generate_description(self, source_layer_name: str, expression: str,
                               remote_layers: dict) -> str:
        """Generate automatic description for a favorite."""
        from datetime import datetime
        
        lines = []
        lines.append(f"Created: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        
        if source_layer_name:
            lines.append(f"Source: {source_layer_name}")
            expr_preview = expression[:100] + "..." if len(expression) > 100 else expression
            lines.append(f"Filter: {expr_preview}")
        
        if remote_layers:
            lines.append("")
            lines.append(f"Remote layers ({len(remote_layers)}):")
            for layer_name, data in list(remote_layers.items())[:5]:
                feature_count = data.get('feature_count', '?')
                lines.append(f"  • {layer_name} ({feature_count} features)")
            if len(remote_layers) > 5:
                lines.append(f"  ... and {len(remote_layers) - 5} more")
        
        return "\n".join(lines)
    
    def _export_favorites(self):
        """Export favorites to a JSON file."""
        if not HAS_QGIS:
            return
        
        from qgis.PyQt.QtWidgets import QFileDialog
        
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Export Favorites",
            "filtermate_favorites.json",
            "JSON Files (*.json)"
        )
        
        if filepath:
            if self._favorites_manager.export_to_file(filepath):
                self.favoritesExported.emit(filepath)
                logger.info(f"Exported favorites to {filepath}")
            else:
                logger.error("Failed to export favorites")
    
    def _import_favorites(self):
        """Import favorites from a JSON file."""
        if not HAS_QGIS:
            return
        
        from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox
        
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Import Favorites",
            "",
            "JSON Files (*.json)"
        )
        
        if filepath:
            result = QMessageBox.question(
                self,
                "Import Favorites",
                "Merge with existing favorites?\n\n"
                "Yes = Add to existing\n"
                "No = Replace all existing",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            
            if result == QMessageBox.Cancel:
                return
            
            merge = (result == QMessageBox.Yes)
            count = self._favorites_manager.import_from_file(filepath, merge=merge)
            
            if count > 0:
                self._favorites_manager.save_to_project()
                self.update_indicator()
                self.favoritesImported.emit(filepath)
                logger.info(f"Imported {count} favorites from {filepath}")
    
    def update_indicator(self):
        """Update the favorites indicator badge with current count."""
        if not HAS_QGIS:
            return
        
        count = 0
        if self._favorites_manager:
            count = self._favorites_manager.count
        
        if count > 0:
            self.setText(f"★ {count}")
            tooltip = f"★ {count} Favorites saved\nClick to apply or manage"
            style = """
                QLabel#label_favorites_indicator {
                    color: white;
                    font-size: 9pt;
                    font-weight: 600;
                    padding: 3px 10px;
                    border-radius: 12px;
                    border: none;
                    background-color: #f39c12;
                }
                QLabel#label_favorites_indicator:hover {
                    background-color: #d68910;
                }
            """
        else:
            self.setText("★")
            tooltip = "★ No favorites saved\nClick to add current filter"
            style = """
                QLabel#label_favorites_indicator {
                    color: #95a5a6;
                    font-size: 9pt;
                    font-weight: 600;
                    padding: 3px 10px;
                    border-radius: 12px;
                    border: none;
                    background-color: #ecf0f1;
                }
                QLabel#label_favorites_indicator:hover {
                    background-color: #d5dbdb;
                }
            """
        
        self.setStyleSheet(style)
        self.setToolTip(tooltip)
        self.adjustSize()
    
    def set_favorites_manager(self, manager):
        """Set or update the favorites manager."""
        self._favorites_manager = manager
        self.update_indicator()
    
    @property
    def favorites_count(self) -> int:
        """Get current favorites count."""
        if self._favorites_manager:
            return self._favorites_manager.count
        return 0
