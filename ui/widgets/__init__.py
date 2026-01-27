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
# EPIC-2: Raster Integration widgets
from .raster_groupbox import RasterExploringGroupBox
from .raster_stats_panel import RasterStatsPanel, StatCard, BandStatsRow
from .histogram_widget import HistogramWidget, HistogramCanvas
from .pixel_identify_widget import (
    PixelIdentifyWidget,
    PixelValueCard,
    RasterIdentifyMapTool,
)

__all__ = [
    'FavoritesWidget',
    'BackendIndicatorWidget',
    'HistoryWidget',
    'ItemDelegate',
    'ListWidgetWrapper',
    'QgsCheckableComboBoxLayer',
    'QgsCheckableComboBoxFeaturesListPickerWidget',
    # EPIC-2: Raster widgets
    'RasterExploringGroupBox',
    'RasterStatsPanel',
    'StatCard',
    'BandStatsRow',
    'HistogramWidget',
    'HistogramCanvas',
    'PixelIdentifyWidget',
    'PixelValueCard',
    'RasterIdentifyMapTool',
]
