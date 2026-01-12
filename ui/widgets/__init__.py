"""
FilterMate UI Widgets.

Reusable widget components extracted from the main dockwidget.
"""
from .favorites_widget import FavoritesWidget
from .backend_indicator import BackendIndicatorWidget
from .history_widget import HistoryWidget
from .custom_widgets import QgsCheckableComboBoxLayer

__all__ = [
    'FavoritesWidget',
    'BackendIndicatorWidget',
    'HistoryWidget',
    'QgsCheckableComboBoxLayer',
]
