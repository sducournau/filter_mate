"""
UI Widgets for Filter History

Provides custom widgets for visualizing and interacting with filter history:
- HistoryDropdown: Dropdown showing recent filter states
- HistoryNavigationWidget: Undo/redo buttons with state indicators
- HistoryListWidget: Full history panel with details

Author: FilterMate Development Team
Date: December 2025
Version: 1.0
"""

import logging
from datetime import datetime
from typing import Optional, List

from qgis.PyQt.QtCore import Qt, pyqtSignal, QSize
from qgis.PyQt.QtWidgets import (
    QComboBox,
    QWidget,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QToolButton,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QFrame
)
from qgis.PyQt.QtGui import QIcon

logger = logging.getLogger('FilterMate.HistoryWidgets')


class HistoryDropdown(QComboBox):
    """
    Dropdown widget showing recent filter history states.
    
    Displays the last N filter states with timestamps and descriptions,
    allowing users to jump directly to any previous state.
    
    Signals:
        stateSelected(int): Emitted when user selects a state (index in history)
    """
    
    stateSelected = pyqtSignal(int)
    
    def __init__(self, parent=None, max_items: int = 10):
        """
        Initialize history dropdown.
        
        Args:
            parent: Parent widget
            max_items: Maximum number of items to display
        """
        super().__init__(parent)
        
        self.max_items = max_items
        self._current_layer_id = None
        self._history_manager = None
        self._updating = False
        
        # Configure dropdown
        self.setToolTip("Jump to a previous filter state")
        self.setMinimumWidth(200)
        self.setMaximumWidth(400)
        
        # Connect signal
        self.currentIndexChanged.connect(self._on_selection_changed)
        
        # Initial state
        self.addItem("No history available")
        self.setEnabled(False)
        
        logger.debug("HistoryDropdown initialized")
    
    def set_history_manager(self, history_manager):
        """
        Set the history manager to use.
        
        Args:
            history_manager: HistoryManager instance
        """
        self._history_manager = history_manager
        logger.debug("History manager set")
    
    def set_current_layer(self, layer_id: str):
        """
        Set the current layer to display history for.
        
        Args:
            layer_id: ID of the layer
        """
        self._current_layer_id = layer_id
        self.update_history()
    
    def update_history(self):
        """Update dropdown with current history states."""
        if not self._history_manager or not self._current_layer_id:
            self.clear()
            self.addItem("No history available")
            self.setEnabled(False)
            return
        
        # Get history for current layer
        history = self._history_manager.get_history(self._current_layer_id)
        if not history or len(history._states) == 0:
            self.clear()
            self.addItem("No history available")
            self.setEnabled(False)
            return
        
        # Block signals during update
        self._updating = True
        self.blockSignals(True)
        
        try:
            self.clear()
            
            # Add states (most recent first)
            states = history._states[-self.max_items:]  # Get last N states
            states.reverse()  # Reverse to show newest first
            
            for i, state in enumerate(states):
                # Calculate actual index in history
                actual_index = len(history._states) - 1 - i
                
                # Format display text
                timestamp_str = state.timestamp.strftime('%H:%M:%S')
                description = state.description[:50]  # Truncate long descriptions
                if len(state.description) > 50:
                    description += "..."
                
                feature_count_str = f"({state.feature_count:,} features)"
                display_text = f"{timestamp_str} - {description} {feature_count_str}"
                
                # Add item with actual index as user data
                self.addItem(display_text, actual_index)
                
                # Highlight current state
                if actual_index == history._current_index:
                    # Bold font for current state
                    item_font = self.font()
                    item_font.setBold(True)
                    self.setItemData(i, item_font, Qt.FontRole)
            
            # Set current index
            current_position = len(history._states) - 1 - history._current_index
            if 0 <= current_position < self.count():
                self.setCurrentIndex(current_position)
            
            self.setEnabled(True)
            
        finally:
            self._updating = False
            self.blockSignals(False)
        
        logger.debug(f"Updated history dropdown: {self.count()} items")
    
    def _on_selection_changed(self, dropdown_index: int):
        """
        Handle dropdown selection change.
        
        Args:
            dropdown_index: Index in dropdown (0 = most recent)
        """
        if self._updating or dropdown_index < 0:
            return
        
        # Get actual history index from user data
        actual_index = self.itemData(dropdown_index)
        if actual_index is not None:
            logger.info(f"User selected history state: index {actual_index}")
            self.stateSelected.emit(actual_index)


class HistoryNavigationWidget(QWidget):
    """
    Widget with undo/redo buttons and state indicator.
    
    Provides intuitive controls for navigating filter history with
    visual feedback about available operations.
    
    Signals:
        undoRequested(): Emitted when undo button clicked
        redoRequested(): Emitted when redo button clicked
    """
    
    undoRequested = pyqtSignal()
    redoRequested = pyqtSignal()
    
    def __init__(self, parent=None, icon_path: str = ""):
        """
        Initialize history navigation widget.
        
        Args:
            parent: Parent widget
            icon_path: Path to icons directory
        """
        super().__init__(parent)
        
        self._icon_path = icon_path
        self._current_layer_id = None
        self._history_manager = None
        
        # Setup UI
        self._setup_ui()
        
        logger.debug("HistoryNavigationWidget initialized")
    
    def _setup_ui(self):
        """Setup the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Undo button
        self.undo_button = QToolButton(self)
        self.undo_button.setText("◀")  # Left arrow
        self.undo_button.setToolTip("Undo last filter (Ctrl+Z)")
        self.undo_button.setEnabled(False)
        self.undo_button.clicked.connect(self.undoRequested.emit)
        
        # Try to load icon if available
        if self._icon_path:
            undo_icon_path = f"{self._icon_path}/undo.svg"
            try:
                undo_icon = QIcon(undo_icon_path)
                if not undo_icon.isNull():
                    self.undo_button.setIcon(undo_icon)
                    self.undo_button.setText("")
            except:
                pass
        
        # State indicator label
        self.state_label = QLabel("No history")
        self.state_label.setAlignment(Qt.AlignCenter)
        self.state_label.setMinimumWidth(80)
        self.state_label.setToolTip("Current position in filter history")
        
        # Redo button
        self.redo_button = QToolButton(self)
        self.redo_button.setText("▶")  # Right arrow
        self.redo_button.setToolTip("Redo last undone filter (Ctrl+Y)")
        self.redo_button.setEnabled(False)
        self.redo_button.clicked.connect(self.redoRequested.emit)
        
        # Try to load icon if available
        if self._icon_path:
            redo_icon_path = f"{self._icon_path}/redo.svg"
            try:
                redo_icon = QIcon(redo_icon_path)
                if not redo_icon.isNull():
                    self.redo_button.setIcon(redo_icon)
                    self.redo_button.setText("")
            except:
                pass
        
        # Add to layout
        layout.addWidget(self.undo_button)
        layout.addWidget(self.state_label)
        layout.addWidget(self.redo_button)
        
        # Set consistent sizes
        button_size = 24
        self.undo_button.setFixedSize(button_size, button_size)
        self.redo_button.setFixedSize(button_size, button_size)
    
    def set_history_manager(self, history_manager):
        """
        Set the history manager to use.
        
        Args:
            history_manager: HistoryManager instance
        """
        self._history_manager = history_manager
        logger.debug("History manager set")
    
    def set_current_layer(self, layer_id: str):
        """
        Set the current layer to display history for.
        
        Args:
            layer_id: ID of the layer
        """
        self._current_layer_id = layer_id
        self.update_state()
    
    def update_state(self):
        """Update button states and label based on current history."""
        if not self._history_manager or not self._current_layer_id:
            self.undo_button.setEnabled(False)
            self.redo_button.setEnabled(False)
            self.state_label.setText("No history")
            return
        
        # Get history for current layer
        history = self._history_manager.get_history(self._current_layer_id)
        if not history:
            self.undo_button.setEnabled(False)
            self.redo_button.setEnabled(False)
            self.state_label.setText("No history")
            return
        
        # Update buttons
        self.undo_button.setEnabled(history.can_undo())
        self.redo_button.setEnabled(history.can_redo())
        
        # Update label
        if len(history._states) == 0:
            self.state_label.setText("No history")
        else:
            current_pos = history._current_index + 1
            total_states = len(history._states)
            self.state_label.setText(f"{current_pos}/{total_states}")
        
        logger.debug(f"Updated navigation state: undo={history.can_undo()}, redo={history.can_redo()}")


class HistoryListWidget(QWidget):
    """
    Full history list widget with detailed information.
    
    Displays all filter states in a list with timestamps, descriptions,
    feature counts, and metadata. Useful for a dedicated history panel.
    
    Signals:
        stateSelected(int): Emitted when user selects a state
    """
    
    stateSelected = pyqtSignal(int)
    
    def __init__(self, parent=None):
        """
        Initialize history list widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        
        self._current_layer_id = None
        self._history_manager = None
        
        # Setup UI
        self._setup_ui()
        
        logger.debug("HistoryListWidget initialized")
    
    def _setup_ui(self):
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header label
        header = QLabel("Filter History")
        header.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(header)
        
        # List widget
        self.list_widget = QListWidget(self)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)
        
        # Info label
        self.info_label = QLabel("No history available")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setStyleSheet("color: gray; padding: 10px;")
        layout.addWidget(self.info_label)
    
    def set_history_manager(self, history_manager):
        """
        Set the history manager to use.
        
        Args:
            history_manager: HistoryManager instance
        """
        self._history_manager = history_manager
        logger.debug("History manager set")
    
    def set_current_layer(self, layer_id: str):
        """
        Set the current layer to display history for.
        
        Args:
            layer_id: ID of the layer
        """
        self._current_layer_id = layer_id
        self.update_history()
    
    def update_history(self):
        """Update list with current history states."""
        self.list_widget.clear()
        
        if not self._history_manager or not self._current_layer_id:
            self.info_label.setText("No history available")
            self.info_label.setVisible(True)
            self.list_widget.setVisible(False)
            return
        
        # Get history for current layer
        history = self._history_manager.get_history(self._current_layer_id)
        if not history or len(history._states) == 0:
            self.info_label.setText("No history available")
            self.info_label.setVisible(True)
            self.list_widget.setVisible(False)
            return
        
        # Show list, hide info
        self.info_label.setVisible(False)
        self.list_widget.setVisible(True)
        
        # Add all states (most recent first)
        states = list(history._states)
        states.reverse()
        
        for i, state in enumerate(states):
            # Calculate actual index
            actual_index = len(history._states) - 1 - i
            
            # Format display text
            timestamp_str = state.timestamp.strftime('%Y-%m-%d %H:%M:%S')
            feature_count_str = f"{state.feature_count:,} features"
            
            # Main text
            main_text = f"{state.description}\n"
            main_text += f"  {timestamp_str} • {feature_count_str}"
            
            # Add metadata if available
            if state.metadata:
                backend = state.metadata.get('backend', '')
                operation = state.metadata.get('operation', '')
                if backend or operation:
                    main_text += f" • {operation} ({backend})"
            
            # Create item
            item = QListWidgetItem(main_text)
            item.setData(Qt.UserRole, actual_index)
            
            # Highlight current state
            if actual_index == history._current_index:
                item_font = item.font()
                item_font.setBold(True)
                item.setFont(item_font)
                item.setToolTip("Current state")
            else:
                item.setToolTip("Double-click to jump to this state")
            
            self.list_widget.addItem(item)
        
        logger.debug(f"Updated history list: {self.list_widget.count()} items")
    
    def _on_item_double_clicked(self, item: QListWidgetItem):
        """
        Handle item double-click.
        
        Args:
            item: The clicked item
        """
        actual_index = item.data(Qt.UserRole)
        if actual_index is not None:
            logger.info(f"User selected history state via list: index {actual_index}")
            self.stateSelected.emit(actual_index)


class CompactHistoryWidget(QWidget):
    """
    Compact history widget combining dropdown and navigation buttons.
    
    Space-efficient widget for the main FilterMate UI that combines
    the history dropdown with undo/redo buttons in a single row.
    
    Signals:
        undoRequested(): Emitted when undo requested
        redoRequested(): Emitted when redo requested
        stateSelected(int): Emitted when state selected from dropdown
    """
    
    undoRequested = pyqtSignal()
    redoRequested = pyqtSignal()
    stateSelected = pyqtSignal(int)
    
    def __init__(self, parent=None, icon_path: str = ""):
        """
        Initialize compact history widget.
        
        Args:
            parent: Parent widget
            icon_path: Path to icons directory
        """
        super().__init__(parent)
        
        self._icon_path = icon_path
        self._current_layer_id = None
        self._history_manager = None
        
        # Setup UI
        self._setup_ui()
        
        logger.debug("CompactHistoryWidget initialized")
    
    def _setup_ui(self):
        """Setup the widget UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        
        # Label
        label = QLabel("History:")
        layout.addWidget(label)
        
        # Undo button
        self.undo_button = QToolButton(self)
        self.undo_button.setText("◀")
        self.undo_button.setToolTip("Undo (Ctrl+Z)")
        self.undo_button.setEnabled(False)
        self.undo_button.setFixedSize(22, 22)
        self.undo_button.clicked.connect(self._on_undo_clicked)
        layout.addWidget(self.undo_button)
        
        # Dropdown
        self.dropdown = HistoryDropdown(self, max_items=10)
        self.dropdown.stateSelected.connect(self._on_state_selected)
        layout.addWidget(self.dropdown, stretch=1)
        
        # Redo button
        self.redo_button = QToolButton(self)
        self.redo_button.setText("▶")
        self.redo_button.setToolTip("Redo (Ctrl+Y)")
        self.redo_button.setEnabled(False)
        self.redo_button.setFixedSize(22, 22)
        self.redo_button.clicked.connect(self._on_redo_clicked)
        layout.addWidget(self.redo_button)
    
    def set_history_manager(self, history_manager):
        """Set the history manager."""
        self._history_manager = history_manager
        self.dropdown.set_history_manager(history_manager)
    
    def set_current_layer(self, layer_id: str):
        """Set the current layer."""
        self._current_layer_id = layer_id
        self.dropdown.set_current_layer(layer_id)
        self.update_buttons()
    
    def update_history(self):
        """Update all components."""
        self.dropdown.update_history()
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states."""
        if not self._history_manager or not self._current_layer_id:
            self.undo_button.setEnabled(False)
            self.redo_button.setEnabled(False)
            return
        
        history = self._history_manager.get_history(self._current_layer_id)
        if history:
            self.undo_button.setEnabled(history.can_undo())
            self.redo_button.setEnabled(history.can_redo())
        else:
            self.undo_button.setEnabled(False)
            self.redo_button.setEnabled(False)
    
    def _on_undo_clicked(self):
        """Handle undo button click."""
        self.undoRequested.emit()
        # Update after undo will be triggered by caller
    
    def _on_redo_clicked(self):
        """Handle redo button click."""
        self.redoRequested.emit()
        # Update after redo will be triggered by caller
    
    def _on_state_selected(self, index: int):
        """Handle state selection from dropdown."""
        self.stateSelected.emit(index)
