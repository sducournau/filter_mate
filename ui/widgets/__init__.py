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
from .transparency_widget import (
    TransparencyWidget,
    OpacitySlider,
    RangeTransparencyWidget,
)
# EPIC-3: Raster-Vector Integration widgets
from .raster_statistics_gb import RasterStatisticsGroupBox, StatCell
from .raster_value_selection_gb import RasterValueSelectionGroupBox
from .raster_mask_clip_gb import RasterMaskClipGroupBox
from .raster_memory_clips_gb import (
    RasterMemoryClipsGroupBox,
    MemoryClipItem,
    MemoryClipListItem,
)
from .raster_exploring_gb_v2 import RasterExploringGroupBoxV2
from .raster_templates_gb import RasterTemplatesGroupBox, TemplateListItem
from .pixel_picker_map_tool import PixelPickerMapTool

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
    'TransparencyWidget',
    'OpacitySlider',
    'RangeTransparencyWidget',
    # EPIC-3: Raster-Vector Integration widgets
    'RasterStatisticsGroupBox',
    'StatCell',
    'RasterValueSelectionGroupBox',
    'RasterMaskClipGroupBox',
    'RasterMemoryClipsGroupBox',
    'MemoryClipItem',
    'MemoryClipListItem',
    'RasterExploringGroupBoxV2',
    'RasterTemplatesGroupBox',
    'TemplateListItem',
    'PixelPickerMapTool',
]
