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
    QgsCheckableComboBoxFeaturesListPickerWidget,
    QgsCheckableComboBoxBands
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
# Raster Tools Keys Widget
from .raster_tools_keys import RasterToolsKeysWidget

__all__ = [
    'FavoritesWidget',
    'BackendIndicatorWidget',
    'HistoryWidget',
    'ItemDelegate',
    'ListWidgetWrapper',
    'QgsCheckableComboBoxLayer',
    'QgsCheckableComboBoxFeaturesListPickerWidget',
    'QgsCheckableComboBoxBands',
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
    # Raster Tools
    'RasterToolsKeysWidget',
]
