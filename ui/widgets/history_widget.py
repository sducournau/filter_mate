# -*- coding: utf-8 -*-
"""
FilterMate History Widget - ARCH-006

Widget for filter history navigation with undo/redo functionality.
Part of Phase 1 Architecture Refactoring.

Features:
- Undo/Redo buttons with state management
- Tooltips showing next/previous state info
- History count indicator
- Context menu for history operations
- Integration with HistoryManager

Author: FilterMate Team
Date: January 2025
"""

# Try PyQt5 imports, fallback to stubs for testing
try:
    from qgis.PyQt.QtWidgets import (
        QWidget, QPushButton, QHBoxLayout, QLabel,
        QMenu, QAction, QToolButton, QSizePolicy
    )
    from qgis.PyQt.QtCore import Qt, pyqtSignal
    from qgis.PyQt.QtGui import QIcon, QCursor
    PYQT_AVAILABLE = True
except ImportError:
    # Stubs for testing without QGIS
    PYQT_AVAILABLE = False

    class pyqtSignal:
        def __init__(self, *args):
            pass

        def emit(self, *args):
            pass

        def connect(self, slot):
            pass

    class QWidget:
        def __init__(self, parent=None):
            self._parent = parent
            self._layout = None
            self._enabled = True

        def setLayout(self, layout):
            self._layout = layout

        def setToolTip(self, tip):
            pass

        def setEnabled(self, enabled):
            self._enabled = enabled

        def isEnabled(self):
            return self._enabled

    class QPushButton:
        def __init__(self, text="", parent=None):
            self._text = text
            self._parent = parent
            self._enabled = True
            self._tooltip = ""
            self.clicked = pyqtSignal()

        def setText(self, text):
            self._text = text

        def text(self):
            return self._text

        def setEnabled(self, enabled):
            self._enabled = enabled

        def isEnabled(self):
            return self._enabled

        def setToolTip(self, tip):
            self._tooltip = tip

        def toolTip(self):
            return self._tooltip

        def setIcon(self, icon):
            pass

        def setFixedSize(self, w, h):
            pass

        def setStyleSheet(self, css):
            pass

    class QToolButton(QPushButton):
        def setPopupMode(self, mode):
            pass

        def setMenu(self, menu):
            pass

    class QHBoxLayout:
        def __init__(self, parent=None):
            self._widgets = []

        def addWidget(self, widget, stretch=0):
            self._widgets.append(widget)

        def addStretch(self, stretch=0):
            pass

        def setSpacing(self, spacing):
            pass

        def setContentsMargins(self, *args):
            pass

    class QLabel:
        def __init__(self, text="", parent=None):
            self._text = text

        def setText(self, text):
            self._text = text

        def text(self):
            return self._text

        def setToolTip(self, tip):
            pass

        def setStyleSheet(self, css):
            pass

    class QMenu:
        def __init__(self, parent=None):
            self._actions = []

        def addAction(self, text_or_action, slot=None):
            if isinstance(text_or_action, str):
                action = QAction(text_or_action)
                self._actions.append(action)
                return action
            self._actions.append(text_or_action)
            return text_or_action

        def addSeparator(self):
            pass

        def exec_(self, pos=None):
            pass

    class QAction:
        def __init__(self, text="", parent=None):
            self._text = text
            self._enabled = True
            self.triggered = pyqtSignal()

        def setEnabled(self, enabled):
            self._enabled = enabled

    class Qt:
        RightButton = 2
        LeftButton = 1

    class QIcon:
        @staticmethod
        def fromTheme(name, fallback=None):
            return QIcon()

        def __init__(self, path=""):
            pass

    class QCursor:
        @staticmethod
        def pos():
            return (0, 0)

    class QSizePolicy:
        Minimum = 0
        Expanding = 1
        Fixed = 2


import logging
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ...core.services.history_service import FilterHistory
logger = logging.getLogger('FilterMate.UI.HistoryWidget')


class HistoryWidget(QWidget):
    """
    Widget for filter history navigation.

    Provides undo/redo buttons with state management, tooltips showing
    next/previous state information, and a context menu for history operations.

    Signals:
        undoRequested: Emitted when undo is requested
        redoRequested: Emitted when redo is requested
        historyCleared: Emitted when history is cleared
        historyBrowseRequested: Emitted when full history browser is requested

    Usage:
        history_widget = HistoryWidget(history_manager)
        history_widget.undoRequested.connect(on_undo)
        history_widget.redoRequested.connect(on_redo)
        history_widget.update_for_layer(layer_id)
    """

    # Signals
    if PYQT_AVAILABLE:
        undoRequested = pyqtSignal()
        redoRequested = pyqtSignal()
        historyCleared = pyqtSignal()
        historyBrowseRequested = pyqtSignal()
    else:
        undoRequested = pyqtSignal()
        redoRequested = pyqtSignal()
        historyCleared = pyqtSignal()
        historyBrowseRequested = pyqtSignal()

    def __init__(self, history_manager=None, parent=None):
        """
        Initialize the history widget.

        Args:
            history_manager: HistoryManager instance for accessing layer histories
            parent: Parent widget
        """
        super().__init__(parent)
        self._history_manager = history_manager
        self._current_layer_id = None
        self._undo_btn = None
        self._redo_btn = None
        self._history_label = None
        self._parent = parent
        self._setup_ui()
        logger.debug("HistoryWidget initialized")

    def _tr(self, text: str) -> str:
        """Translate text using parent's tr() if available."""
        if self._parent and hasattr(self._parent, 'tr'):
            return self._parent.tr(text)
        return text

    def _setup_ui(self):
        """Set up the widget UI components."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Undo button
        self._undo_btn = QPushButton("↶")
        self._undo_btn.setToolTip(self._tr("Undo last filter (Ctrl+Z)"))
        self._undo_btn.setFixedSize(28, 28)
        self._undo_btn.setEnabled(False)
        if PYQT_AVAILABLE:
            self._undo_btn.clicked.connect(self._on_undo_clicked)
        layout.addWidget(self._undo_btn)

        # Redo button
        self._redo_btn = QPushButton("↷")
        self._redo_btn.setToolTip(self._tr("Redo filter (Ctrl+Y)"))
        self._redo_btn.setFixedSize(28, 28)
        self._redo_btn.setEnabled(False)
        if PYQT_AVAILABLE:
            self._redo_btn.clicked.connect(self._on_redo_clicked)
        layout.addWidget(self._redo_btn)

        # History count label (optional)
        self._history_label = QLabel("")
        self._history_label.setToolTip(self._tr("Filter history position"))
        self._history_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(self._history_label)

        layout.addStretch()
        self.setLayout(layout)

        # Apply styling
        self._apply_styling()

    def _apply_styling(self):
        """Apply consistent styling to buttons."""
        button_style = """
            QPushButton {
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #e0e0e0;
                border-color: #999;
            }
            QPushButton:pressed {
                background-color: #d0d0d0;
            }
            QPushButton:disabled {
                background-color: #f8f8f8;
                color: #ccc;
                border-color: #ddd;
            }
        """
        self._undo_btn.setStyleSheet(button_style)
        self._redo_btn.setStyleSheet(button_style)

    def set_history_manager(self, history_manager):
        """
        Set or update the history manager.

        Args:
            history_manager: HistoryManager instance
        """
        self._history_manager = history_manager
        self.update_button_states()

    def update_for_layer(self, layer_id: str):
        """
        Update the widget for a specific layer.

        Args:
            layer_id: The layer ID to show history for
        """
        self._current_layer_id = layer_id
        self.update_button_states()

    def update_button_states(self):
        """Update undo/redo button enabled states based on history."""
        can_undo = False
        can_redo = False
        position_text = ""
        undo_tooltip = "Undo last filter (Ctrl+Z)"
        redo_tooltip = "Redo filter (Ctrl+Y)"

        if self._history_manager and self._current_layer_id:
            history = self._get_current_history()
            if history:
                can_undo = history.can_undo()
                can_redo = history.can_redo()

                # Update position text
                current_pos = history._current_index + 1
                total = len(history._states)
                if total > 0:
                    position_text = f"{current_pos}/{total}"

                # Update tooltips with state descriptions
                if can_undo:
                    prev_state = history.peek_undo()
                    if prev_state:
                        desc = prev_state.description[:40] + "..." if len(prev_state.description) > 40 else prev_state.description
                        undo_tooltip = f"Undo: {desc} (Ctrl+Z)"

                if can_redo:
                    next_state = history.peek_redo()
                    if next_state:
                        desc = next_state.description[:40] + "..." if len(next_state.description) > 40 else next_state.description
                        redo_tooltip = f"Redo: {desc} (Ctrl+Y)"

        self._undo_btn.setEnabled(can_undo)
        self._redo_btn.setEnabled(can_redo)
        self._undo_btn.setToolTip(undo_tooltip)
        self._redo_btn.setToolTip(redo_tooltip)
        self._history_label.setText(position_text)

        logger.debug(f"History buttons updated: undo={can_undo}, redo={can_redo}, pos={position_text}")

    def _get_current_history(self) -> Optional['FilterHistory']:
        """Get the FilterHistory for the current layer."""
        if not self._history_manager or not self._current_layer_id:
            return None

        # HistoryManager.get_history(layer_id) returns FilterHistory
        return self._history_manager.get_history(self._current_layer_id)

    def _on_undo_clicked(self):
        """Handle undo button click."""
        logger.info("Undo requested from HistoryWidget")
        if PYQT_AVAILABLE:
            self.undoRequested.emit()
        else:
            self.undoRequested.emit()

    def _on_redo_clicked(self):
        """Handle redo button click."""
        logger.info("Redo requested from HistoryWidget")
        if PYQT_AVAILABLE:
            self.redoRequested.emit()
        else:
            self.redoRequested.emit()

    def show_context_menu(self, global_pos=None):
        """
        Show context menu with history operations.

        Args:
            global_pos: Position to show menu (defaults to cursor position)
        """
        menu = QMenu(self)

        # Undo action
        undo_action = menu.addAction("↶ Undo")
        undo_action.setEnabled(self._undo_btn.isEnabled())
        if PYQT_AVAILABLE:
            undo_action.triggered.connect(self._on_undo_clicked)

        # Redo action
        redo_action = menu.addAction("↷ Redo")
        redo_action.setEnabled(self._redo_btn.isEnabled())
        if PYQT_AVAILABLE:
            redo_action.triggered.connect(self._on_redo_clicked)

        menu.addSeparator()

        # Clear history action
        clear_action = menu.addAction("🗑 Clear History")
        history = self._get_current_history()
        clear_action.setEnabled(history is not None and len(history._states) > 0)
        if PYQT_AVAILABLE:
            clear_action.triggered.connect(self._on_clear_history)

        menu.addSeparator()

        # Browse history action (for future expansion)
        browse_action = menu.addAction("📋 Browse History...")
        browse_action.setEnabled(history is not None and len(history._states) > 0)
        if PYQT_AVAILABLE:
            browse_action.triggered.connect(self._on_browse_history)

        # Show menu
        if global_pos is None and PYQT_AVAILABLE:
            global_pos = QCursor.pos()
        menu.exec_(global_pos)

    def _on_clear_history(self):
        """Handle clear history request."""
        logger.info("History clear requested from HistoryWidget")

        if self._history_manager and self._current_layer_id:
            history = self._get_current_history()
            if history:
                history.clear()
                self.update_button_states()

        if PYQT_AVAILABLE:
            self.historyCleared.emit()
        else:
            self.historyCleared.emit()

    def _on_browse_history(self):
        """Handle browse history request."""
        logger.info("History browse requested from HistoryWidget")
        if PYQT_AVAILABLE:
            self.historyBrowseRequested.emit()
        else:
            self.historyBrowseRequested.emit()

    def get_history_info(self) -> dict:
        """
        Get information about current history state.

        Returns:
            dict with keys: can_undo, can_redo, position, total, states
        """
        info = {
            'can_undo': False,
            'can_redo': False,
            'position': 0,
            'total': 0,
            'states': []
        }

        history = self._get_current_history()
        if history:
            info['can_undo'] = history.can_undo()
            info['can_redo'] = history.can_redo()
            info['position'] = history._current_index + 1
            info['total'] = len(history._states)
            info['states'] = [
                {
                    'description': s.description,
                    'timestamp': s.timestamp.isoformat(),
                    'feature_count': s.feature_count
                }
                for s in history._states
            ]

        return info


# Helper functions for external use

def create_history_widget(history_manager=None, parent=None) -> HistoryWidget:
    """
    Create a HistoryWidget instance.

    Args:
        history_manager: HistoryManager instance
        parent: Parent widget

    Returns:
        HistoryWidget instance
    """
    return HistoryWidget(history_manager, parent)
