"""
FilterMate UI Widgets.

Reusable widget components extracted from the main dockwidget.
"""
from .favorites_widget import FavoritesWidget
from .backend_indicator import BackendIndicatorWidget
from .history_widget import HistoryWidget
from .custom_widgets import (
    ItemDelegate,
    ListWidgetWrapper,
    QgsCheckableComboBoxLayer,
    QgsCheckableComboBoxFeaturesListPickerWidget
)
# Note QToolBox Architecture
from .toolbox import (
    BaseToolBox,
    ExploringToolBox,
    VectorExploringPage,
    RasterExploringPage,
    ToolsetToolBox,
    FilteringPage,
    ExportingPage,
    ConfigurationPage,
    ToolBoxIntegrationBridge,
    DualToolBoxContainer
)

__all__ = [
    'FavoritesWidget',
    'BackendIndicatorWidget',
    'HistoryWidget',
    'ItemDelegate',
    'ListWidgetWrapper',
    'QgsCheckableComboBoxLayer',
    'QgsCheckableComboBoxFeaturesListPickerWidget',
    # Note QToolBox
    'BaseToolBox',
    'ExploringToolBox',
    'VectorExploringPage',
    'RasterExploringPage',
    'ToolsetToolBox',
    'FilteringPage',
    'ExportingPage',
    'ConfigurationPage',
    'ToolBoxIntegrationBridge',
    'DualToolBoxContainer',
]
