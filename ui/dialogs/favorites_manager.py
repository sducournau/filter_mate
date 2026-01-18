"""
FilterMate FavoritesManagerDialog.

Dialog for managing filter favorites with list, edit, delete, and search capabilities.
Extracted from filter_mate_dockwidget.py for better modularity.
"""
from typing import Optional
import logging

try:
    from qgis.PyQt.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
        QPushButton, QLabel, QLineEdit, QTextEdit, QMessageBox, QFormLayout,
        QDialogButtonBox, QSplitter, QTreeWidget, QTreeWidgetItem, QHeaderView,
        QTabWidget, QWidget
    )
    from qgis.PyQt.QtCore import Qt, pyqtSignal
    HAS_QGIS = True
except ImportError:
    HAS_QGIS = False
    # Stub classes for type hints when QGIS not available
    QDialog = object
    QWidget = object
    QVBoxLayout = object
    QHBoxLayout = object
    QListWidget = object
    QListWidgetItem = object
    QPushButton = object
    QLabel = object
    QLineEdit = object
    QTextEdit = object
    QMessageBox = None
    QFormLayout = object
    QDialogButtonBox = object
    QSplitter = object
    QTreeWidget = object
    QTreeWidgetItem = object
    QHeaderView = None
    QTabWidget = object
    Qt = None
    pyqtSignal = lambda *args: None

logger = logging.getLogger(__name__)


class FavoritesManagerDialog(QDialog if HAS_QGIS else object):
    """
    Dialog for managing filter favorites.
    
    Features:
    - List all favorites with search/filter
    - Edit favorite name, description, tags, and expression
    - Delete favorites
    - Apply favorites directly
    - View remote layer details
    
    Signals:
        favoriteApplied: Emitted when a favorite is applied (favorite_id)
        favoriteDeleted: Emitted when a favorite is deleted (favorite_id)
        favoriteUpdated: Emitted when a favorite is updated (favorite_id)
        favoritesChanged: Emitted when favorites list changes
    """
    
    if HAS_QGIS:
        favoriteApplied = pyqtSignal(str)
        favoriteDeleted = pyqtSignal(str)
        favoriteUpdated = pyqtSignal(str)
        favoritesChanged = pyqtSignal()
    
    def __init__(self, favorites_manager, parent=None):
        """
        Initialize FavoritesManagerDialog.
        
        Args:
            favorites_manager: FavoritesManager instance
            parent: Parent widget
        """
        if HAS_QGIS:
            super().__init__(parent)
        
        self._favorites_manager = favorites_manager
        self._current_fav_id = None
        self._all_favorites = []
        
        if HAS_QGIS:
            self._setup_ui()
    
    def _setup_ui(self):
        """Build the dialog UI."""
        self.setWindowTitle("FilterMate - Favorites Manager")
        self.setMinimumSize(550, 400)
        self.resize(650, 480)
        self.setModal(True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        
        # Header with count (handle None favorites_manager)
        fav_count = self._favorites_manager.count if self._favorites_manager else 0
        self._header_label = QLabel(
            f"<b>Saved Favorites ({fav_count})</b>"
        )
        self._header_label.setStyleSheet("font-size: 11pt; margin-bottom: 5px;")
        layout.addWidget(self._header_label)
        
        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍")
        search_label.setStyleSheet("font-size: 12pt;")
        search_layout.addWidget(search_label)
        
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText(
            "Search by name, expression, tags, or description..."
        )
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.setStyleSheet("padding: 4px 8px; border-radius: 4px;")
        self._search_edit.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self._search_edit)
        layout.addLayout(search_layout)
        
        # Main content with splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel: List of favorites
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        # Right panel: Details with tabs
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions (30% list, 70% details)
        splitter.setSizes([200, 450])
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)
        
        # Buttons
        button_layout = self._create_buttons()
        layout.addLayout(button_layout)
        
        # Initial population (handle None favorites_manager)
        if self._favorites_manager:
            self._all_favorites = self._favorites_manager.get_all_favorites()
        else:
            self._all_favorites = []
        self._populate_list(self._all_favorites)
        
        # Select first item
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)
    
    def _create_left_panel(self) -> QWidget:
        """Create the left panel with favorites list."""
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)
        
        self._list_widget = QListWidget()
        self._list_widget.setMinimumWidth(180)
        self._list_widget.setMaximumWidth(250)
        self._list_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self._list_widget.currentItemChanged.connect(self._on_selection_changed)
        
        left_layout.addWidget(self._list_widget)
        return left_panel
    
    def _create_right_panel(self) -> QWidget:
        """Create the right panel with details tabs."""
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        
        self._tab_widget = QTabWidget()
        
        # Tab 1: General Info
        general_tab = self._create_general_tab()
        self._tab_widget.addTab(general_tab, "📋 General")
        
        # Tab 2: Expression
        expr_tab = self._create_expression_tab()
        self._tab_widget.addTab(expr_tab, "🔍 Expression")
        
        # Tab 3: Remote Layers
        remote_tab = self._create_remote_tab()
        self._tab_widget.addTab(remote_tab, "🗂️ Remote Layers")
        
        right_layout.addWidget(self._tab_widget)
        return right_panel
    
    def _create_general_tab(self) -> QWidget:
        """Create the General Info tab."""
        general_tab = QWidget()
        general_layout = QFormLayout(general_tab)
        general_layout.setContentsMargins(8, 8, 8, 8)
        general_layout.setSpacing(6)
        general_layout.setRowWrapPolicy(QFormLayout.DontWrapRows)
        
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Favorite name")
        general_layout.addRow("Name:", self._name_edit)
        
        self._description_edit = QTextEdit()
        self._description_edit.setMaximumHeight(60)
        self._description_edit.setPlaceholderText("Description (auto-generated, editable)")
        general_layout.addRow("Description:", self._description_edit)
        
        self._tags_edit = QLineEdit()
        self._tags_edit.setPlaceholderText(
            "Enter tags separated by commas (e.g., urban, population, 2024)"
        )
        self._tags_edit.setToolTip(
            "Tags help organize and search favorites.\nSeparate multiple tags with commas."
        )
        general_layout.addRow("Tags:", self._tags_edit)
        
        self._layer_label = QLabel("-")
        self._layer_label.setStyleSheet("color: #555;")
        self._layer_label.setWordWrap(True)
        general_layout.addRow("Source Layer:", self._layer_label)
        
        self._provider_label = QLabel("-")
        self._provider_label.setStyleSheet("color: #777;")
        general_layout.addRow("Provider:", self._provider_label)
        
        # Stats row
        stats_layout = QHBoxLayout()
        stats_layout.setContentsMargins(0, 0, 0, 0)
        self._use_count_label = QLabel("-")
        self._created_label = QLabel("-")
        self._created_label.setStyleSheet("color: #777; font-size: 9pt;")
        stats_layout.addWidget(QLabel("Used:"))
        stats_layout.addWidget(self._use_count_label)
        stats_layout.addStretch()
        stats_layout.addWidget(QLabel("Created:"))
        stats_layout.addWidget(self._created_label)
        general_layout.addRow(stats_layout)
        
        return general_tab
    
    def _create_expression_tab(self) -> QWidget:
        """Create the Expression tab."""
        expr_tab = QWidget()
        expr_layout = QVBoxLayout(expr_tab)
        expr_layout.setContentsMargins(8, 8, 8, 8)
        expr_layout.setSpacing(4)
        
        source_expr_label = QLabel("<b>Source Layer Expression:</b>")
        expr_layout.addWidget(source_expr_label)
        
        self._expression_edit = QTextEdit()
        self._expression_edit.setPlaceholderText("Filter expression for source layer")
        self._expression_edit.setStyleSheet(
            "font-family: monospace; font-size: 10pt;"
        )
        expr_layout.addWidget(self._expression_edit)
        
        return expr_tab
    
    def _create_remote_tab(self) -> QWidget:
        """Create the Remote Layers tab."""
        remote_tab = QWidget()
        remote_layout = QVBoxLayout(remote_tab)
        remote_layout.setContentsMargins(8, 8, 8, 8)
        remote_layout.setSpacing(4)
        
        remote_header = QLabel("<b>Filtered Remote Layers:</b>")
        remote_layout.addWidget(remote_header)
        
        self._remote_tree = QTreeWidget()
        self._remote_tree.setHeaderLabels(["Layer", "Features", "Expression"])
        self._remote_tree.setColumnCount(3)
        self._remote_tree.header().setStretchLastSection(True)
        self._remote_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._remote_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._remote_tree.setAlternatingRowColors(True)
        remote_layout.addWidget(self._remote_tree)
        
        self._no_remote_label = QLabel("<i>No remote layers in this favorite</i>")
        self._no_remote_label.setStyleSheet("color: #888; padding: 10px;")
        self._no_remote_label.setAlignment(Qt.AlignCenter)
        remote_layout.addWidget(self._no_remote_label)
        
        return remote_tab
    
    def _create_buttons(self) -> QHBoxLayout:
        """Create the button row."""
        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 8, 0, 0)
        
        self._apply_btn = QPushButton("▶ Apply")
        self._apply_btn.setEnabled(False)
        self._apply_btn.setStyleSheet(
            "background-color: #27ae60; color: white; "
            "font-weight: bold; padding: 6px 12px;"
        )
        self._apply_btn.clicked.connect(self._on_apply)
        
        self._save_btn = QPushButton("💾 Save Changes")
        self._save_btn.setEnabled(False)
        self._save_btn.setStyleSheet("padding: 6px 12px;")
        self._save_btn.clicked.connect(self._on_save)
        
        self._delete_btn = QPushButton("🗑️ Delete")
        self._delete_btn.setEnabled(False)
        self._delete_btn.setStyleSheet(
            "background-color: #e74c3c; color: white; padding: 6px 12px;"
        )
        self._delete_btn.clicked.connect(self._on_delete)
        
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("padding: 6px 12px;")
        close_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self._apply_btn)
        button_layout.addWidget(self._save_btn)
        button_layout.addStretch()
        button_layout.addWidget(self._delete_btn)
        button_layout.addWidget(close_btn)
        
        return button_layout
    
    def _populate_list(self, favorites_to_show: list):
        """Populate list widget with given favorites."""
        self._list_widget.clear()
        
        for fav in favorites_to_show:
            layers_count = fav.get_layers_count() if hasattr(fav, 'get_layers_count') else 1
            item_text = f"★ {fav.name}"
            if layers_count > 1:
                item_text += f" [{layers_count}]"
            if fav.tags:
                item_text += " 🏷️"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, fav.id)
            
            tooltip = f"Layer: {fav.layer_name}\nUsed: {fav.use_count} times"
            if fav.tags:
                tooltip += f"\nTags: {', '.join(fav.tags)}"
            if fav.description:
                tooltip += f"\n\n{fav.description}"
            item.setToolTip(tooltip)
            
            self._list_widget.addItem(item)
    
    def _on_search_changed(self, text: str):
        """Filter favorites based on search text."""
        if not self._favorites_manager:
            return
        if not text.strip():
            self._populate_list(self._all_favorites)
            self._header_label.setText(
                f"<b>Saved Favorites ({self._favorites_manager.count})</b>"
            )
        else:
            filtered = self._favorites_manager.search_favorites(text)
            self._populate_list(filtered)
            self._header_label.setText(
                f"<b>Favorites ({len(filtered)}/{self._favorites_manager.count})</b>"
            )
    
    def _on_selection_changed(self):
        """Handle selection change in list."""
        item = self._list_widget.currentItem()
        if not item or not self._favorites_manager:
            return
        
        fav_id = item.data(Qt.UserRole)
        fav = self._favorites_manager.get_favorite(fav_id)
        
        if not fav:
            return
        
        self._current_fav_id = fav_id
        
        # Update General tab
        self._name_edit.setText(fav.name)
        self._description_edit.setText(fav.description or "")
        self._tags_edit.setText(", ".join(fav.tags) if fav.tags else "")
        self._layer_label.setText(fav.layer_name or "-")
        self._provider_label.setText(fav.layer_provider or "-")
        self._use_count_label.setText(f"{fav.use_count} times")
        self._created_label.setText(fav.created_at[:16] if fav.created_at else "-")
        
        # Update Expression tab
        self._expression_edit.setText(fav.expression)
        
        # Update Remote Layers tab
        self._remote_tree.clear()
        if fav.remote_layers and len(fav.remote_layers) > 0:
            self._no_remote_label.hide()
            self._remote_tree.show()
            
            for layer_name, layer_data in fav.remote_layers.items():
                expr = layer_data.get('expression', '')
                feature_count = layer_data.get('feature_count', '?')
                tree_item = QTreeWidgetItem([
                    layer_name,
                    str(feature_count),
                    expr[:80] + "..." if len(expr) > 80 else expr
                ])
                tree_item.setToolTip(2, expr)
                self._remote_tree.addTopLevelItem(tree_item)
            
            self._tab_widget.setTabText(
                2, f"🗂️ Remote Layers ({len(fav.remote_layers)})"
            )
        else:
            self._remote_tree.hide()
            self._no_remote_label.show()
            self._tab_widget.setTabText(2, "🗂️ Remote Layers")
        
        # Enable buttons
        self._apply_btn.setEnabled(True)
        self._save_btn.setEnabled(True)
        self._delete_btn.setEnabled(True)
    
    def _on_apply(self):
        """Apply selected favorite."""
        if self._current_fav_id:
            self.favoriteApplied.emit(self._current_fav_id)
            self.accept()
    
    def _on_save(self):
        """Save changes to selected favorite."""
        if not self._current_fav_id or not self._favorites_manager:
            return
        
        new_name = self._name_edit.text().strip()
        new_expr = self._expression_edit.toPlainText().strip()
        new_desc = self._description_edit.toPlainText().strip()
        new_tags = [
            tag.strip() for tag in self._tags_edit.text().split(',')
            if tag.strip()
        ]
        
        if new_name:
            self._favorites_manager.update_favorite(
                self._current_fav_id,
                name=new_name,
                expression=new_expr,
                description=new_desc,
                tags=new_tags
            )
            self._favorites_manager.save_to_project()
            
            # Update list item
            item = self._list_widget.currentItem()
            if item:
                fav = self._favorites_manager.get_favorite(self._current_fav_id)
                layers_count = (
                    fav.get_layers_count() 
                    if fav and hasattr(fav, 'get_layers_count') 
                    else 1
                )
                item_text = f"★ {new_name}"
                if layers_count > 1:
                    item_text += f" [{layers_count}]"
                if new_tags:
                    item_text += " 🏷️"
                item.setText(item_text)
            
            self.favoriteUpdated.emit(self._current_fav_id)
            logger.info(f"Favorite updated: {new_name}")
    
    def _on_delete(self):
        """Delete selected favorite."""
        if not self._current_fav_id or not self._favorites_manager:
            return
        
        fav = self._favorites_manager.get_favorite(self._current_fav_id)
        if not fav:
            return
        
        reply = QMessageBox.question(
            self,
            "Delete Favorite",
            f"Delete favorite '{fav.name}'?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        deleted_id = self._current_fav_id
        self._favorites_manager.remove_favorite(self._current_fav_id)
        self._list_widget.takeItem(self._list_widget.currentRow())
        
        fav_count = self._favorites_manager.count if self._favorites_manager else 0
        self._header_label.setText(
            f"<b>Saved Favorites ({fav_count})</b>"
        )
        
        # Clear all fields
        self._clear_details()
        
        self._current_fav_id = None
        self._apply_btn.setEnabled(False)
        self._save_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)
        
        # Save changes
        self._favorites_manager.save_to_project()
        
        # Auto-select next item
        if self._list_widget.count() > 0:
            self._list_widget.setCurrentRow(0)
        
        self.favoriteDeleted.emit(deleted_id)
        self.favoritesChanged.emit()
    
    def _clear_details(self):
        """Clear all detail fields."""
        # Tab 1: General
        self._name_edit.clear()
        self._description_edit.clear()
        self._tags_edit.clear()
        self._layer_label.setText("-")
        self._provider_label.setText("-")
        self._use_count_label.setText("-")
        self._created_label.setText("-")
        
        # Tab 2: Expression
        self._expression_edit.clear()
        
        # Tab 3: Remote Layers
        self._remote_tree.clear()
        self._no_remote_label.show()
        self._remote_tree.hide()
        self._tab_widget.setTabText(2, "🗂️ Remote Layers")
    
    def refresh(self):
        """Refresh the favorites list."""
        if not self._favorites_manager:
            self._all_favorites = []
            self._populate_list(self._all_favorites)
            self._header_label.setText("<b>Saved Favorites (0)</b>")
            return
        self._all_favorites = self._favorites_manager.get_all_favorites()
        self._populate_list(self._all_favorites)
        self._header_label.setText(
            f"<b>Saved Favorites ({self._favorites_manager.count})</b>"
        )
    
    @staticmethod
    def show_dialog(favorites_manager, parent=None) -> Optional[str]:
        """
        Show the dialog and return the applied favorite ID if any.
        
        Args:
            favorites_manager: FavoritesManager instance
            parent: Parent widget
        
        Returns:
            Applied favorite ID or None
        """
        if not favorites_manager or favorites_manager.count == 0:
            if HAS_QGIS:
                QMessageBox.information(
                    parent,
                    "Favorites Manager",
                    "No favorites saved yet.\n\n"
                    "Click the ★ indicator and select 'Add current filter to favorites' "
                    "to save your first favorite."
                )
            return None
        
        dialog = FavoritesManagerDialog(favorites_manager, parent)
        applied_id = [None]
        
        def on_applied(fav_id):
            applied_id[0] = fav_id
        
        dialog.favoriteApplied.connect(on_applied)
        dialog.exec_()
        
        return applied_id[0]
