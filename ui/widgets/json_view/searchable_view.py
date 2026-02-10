"""
Searchable JSON View Widget for FilterMate Configuration.

Provides a QTreeView with integrated search/filter functionality.
The search bar filters configuration items in real-time.

v4.0.7: Initial implementation based on audit recommendations.

Author: FilterMate Team
"""

from qgis.PyQt import QtGui, QtCore, QtWidgets
from .view import JsonView
from .model import JsonModel, JsonSortFilterProxyModel


class SearchableJsonView(QtWidgets.QWidget):
    """
    A widget combining JsonView with a search bar for filtering configuration items.
    
    Features:
    - Real-time search filtering
    - Highlights matching items
    - Expands tree to show matches
    - Clear search button
    - Keyboard shortcut (Ctrl+F) to focus search
    
    Example:
        model = JsonModel(data=config_data, editable_values=True)
        searchable_view = SearchableJsonView(model, plugin_dir)
        layout.addWidget(searchable_view)
        
        # Access underlying view for signals
        searchable_view.json_view.model.itemChanged.connect(on_change)
    """
    
    # Signal emitted when search text changes
    searchTextChanged = QtCore.pyqtSignal(str)
    
    def __init__(self, model, plugin_dir=None, parent=None):
        """
        Initialize searchable JSON view.
        
        Args:
            model: JsonModel instance to display
            plugin_dir: Plugin directory path for icons
            parent: Parent widget
        """
        super(SearchableJsonView, self).__init__(parent)
        self.plugin_dir = plugin_dir
        self._source_model = model
        self._setup_ui()
        self._setup_filter()
        self._connect_signals()
    
    def _setup_ui(self):
        """Setup the widget UI layout."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Search bar container
        search_container = QtWidgets.QWidget()
        search_layout = QtWidgets.QHBoxLayout(search_container)
        search_layout.setContentsMargins(2, 2, 2, 2)
        search_layout.setSpacing(4)
        
        # Search icon label
        self._search_icon = QtWidgets.QLabel("🔍")
        self._search_icon.setFixedWidth(20)
        search_layout.addWidget(self._search_icon)
        
        # Search input
        self._search_input = QtWidgets.QLineEdit()
        self._search_input.setPlaceholderText("Search configuration... (Ctrl+F)")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumHeight(26)
        search_layout.addWidget(self._search_input)
        
        # Match count label
        self._match_label = QtWidgets.QLabel("")
        self._match_label.setFixedWidth(60)
        self._match_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        search_layout.addWidget(self._match_label)
        
        layout.addWidget(search_container)
        
        # JSON Tree View
        self._json_view = JsonView(self._source_model, self.plugin_dir, self)
        layout.addWidget(self._json_view)
        
        # Apply search bar styling
        self._apply_search_styling()
    
    def _setup_filter(self):
        """Setup the filter proxy model."""
        self._proxy_model = JsonSortFilterProxyModel()
        self._proxy_model.setSourceModel(self._source_model)
        self._proxy_model.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self._proxy_model.setFilterKeyColumn(0)  # Filter on property column
        
        # Keep source model for now - filtering is optional
        # Users can toggle between filtered and unfiltered view
        self._filtering_enabled = False
    
    def _connect_signals(self):
        """Connect signal handlers."""
        self._search_input.textChanged.connect(self._on_search_changed)
        self._search_input.returnPressed.connect(self._on_search_enter)
        
        # Keyboard shortcut for search
        shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+F"), self)
        shortcut.activated.connect(self._focus_search)
        
        # Escape to clear search
        escape_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Escape"), self._search_input)
        escape_shortcut.activated.connect(self._clear_search)
    
    def _apply_search_styling(self):
        """Apply styling to the search bar based on theme."""
        try:
            from qgis.core import QgsApplication
            palette = QgsApplication.palette()
            bg_color = palette.color(QtGui.QPalette.Window)
            is_dark = bg_color.lightness() < 128
        except (ImportError, AttributeError):
            is_dark = False
        
        if is_dark:
            self._search_input.setStyleSheet("""
                QLineEdit {
                    background-color: #2D2D30;
                    border: 1px solid #3E3E42;
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: #D4D4D4;
                    font-size: 9pt;
                }
                QLineEdit:focus {
                    border: 1px solid #007ACC;
                }
                QLineEdit::placeholder {
                    color: #808080;
                }
            """)
            self._match_label.setStyleSheet("color: #808080; font-size: 8pt;")
        else:
            self._search_input.setStyleSheet("""
                QLineEdit {
                    background-color: #FFFFFF;
                    border: 1px solid #C0C0C0;
                    border-radius: 4px;
                    padding: 4px 8px;
                    color: #333333;
                    font-size: 9pt;
                }
                QLineEdit:focus {
                    border: 1px solid #0078D4;
                }
                QLineEdit::placeholder {
                    color: #999999;
                }
            """)
            self._match_label.setStyleSheet("color: #666666; font-size: 8pt;")
    
    def _on_search_changed(self, text):
        """Handle search text changes."""
        self.searchTextChanged.emit(text)
        
        if not text:
            self._match_label.setText("")
            self._clear_highlights()
            return
        
        # Find and highlight matches
        matches = self._find_matches(text)
        count = len(matches)
        
        if count == 0:
            self._match_label.setText("No match")
            self._match_label.setStyleSheet(
                self._match_label.styleSheet() + "color: #FF6B6B;"
            )
        else:
            self._match_label.setText(f"{count} found")
            self._apply_search_styling()  # Reset color
        
        # Highlight and expand to show matches
        self._highlight_matches(matches)
    
    def _on_search_enter(self):
        """Handle Enter key in search - navigate to first/next match."""
        text = self._search_input.text()
        if text:
            matches = self._find_matches(text)
            if matches:
                # Select first match
                first_match = matches[0]
                self._json_view.setCurrentIndex(first_match)
                self._json_view.scrollTo(first_match)
    
    def _focus_search(self):
        """Focus the search input."""
        self._search_input.setFocus()
        self._search_input.selectAll()
    
    def _clear_search(self):
        """Clear the search input."""
        self._search_input.clear()
        self._match_label.setText("")
        self._clear_highlights()
    
    def _find_matches(self, search_text, parent=None):
        """
        Find all items matching the search text.
        
        Args:
            search_text: Text to search for
            parent: Parent index to start from (None for root)
            
        Returns:
            List of QModelIndex for matching items
        """
        matches = []
        model = self._source_model
        search_lower = search_text.lower()
        
        if parent is None:
            parent = QtCore.QModelIndex()
        
        for row in range(model.rowCount(parent)):
            # Check key column (0)
            key_index = model.index(row, 0, parent)
            key_text = model.data(key_index, QtCore.Qt.DisplayRole)
            
            if key_text and search_lower in str(key_text).lower():
                matches.append(key_index)
            
            # Check value column (1)
            value_index = model.index(row, 1, parent)
            value_text = model.data(value_index, QtCore.Qt.DisplayRole)
            
            if value_text and search_lower in str(value_text).lower():
                if key_index not in matches:
                    matches.append(key_index)
            
            # Recurse into children
            if model.hasChildren(key_index):
                matches.extend(self._find_matches(search_text, key_index))
        
        return matches
    
    def _highlight_matches(self, matches):
        """
        Highlight matching items and expand their parents.
        
        Args:
            matches: List of QModelIndex to highlight
        """
        # First, collapse all to make expansion meaningful
        # self._json_view.collapseAll()  # Optional - can be jarring
        
        for match in matches:
            # Expand all parent nodes
            parent = match.parent()
            while parent.isValid():
                self._json_view.expand(parent)
                parent = parent.parent()
        
        # If there are matches, scroll to and select the first one
        if matches:
            self._json_view.setCurrentIndex(matches[0])
            self._json_view.scrollTo(matches[0])
    
    def _clear_highlights(self):
        """Clear all search highlights."""
        # Reset selection
        self._json_view.clearSelection()
    
    # === Public API ===
    
    @property
    def json_view(self):
        """Get the underlying JsonView widget."""
        return self._json_view
    
    @property
    def model(self):
        """Get the source JsonModel."""
        return self._source_model
    
    @model.setter
    def model(self, new_model):
        """Set a new model."""
        self._source_model = new_model
        self._json_view.setModel(new_model)
        self._json_view.model = new_model
        self._proxy_model.setSourceModel(new_model)
        self._clear_search()
    
    def setModel(self, model):
        """Qt-style setter for model."""
        self.model = model
    
    def setAnimated(self, animated):
        """Delegate to JsonView."""
        self._json_view.setAnimated(animated)
    
    def setEnabled(self, enabled):
        """Enable/disable the widget."""
        super().setEnabled(enabled)
        self._json_view.setEnabled(enabled)
        self._search_input.setEnabled(enabled)
    
    def show(self):
        """Show the widget."""
        super().show()
        self._json_view.show()
    
    def expand_all(self):
        """Expand all tree items."""
        self._json_view.expandAll()
    
    def collapse_all(self):
        """Collapse all tree items."""
        self._json_view.collapseAll()
    
    def get_search_text(self):
        """Get current search text."""
        return self._search_input.text()
    
    def set_search_text(self, text):
        """Set search text programmatically."""
        self._search_input.setText(text)
