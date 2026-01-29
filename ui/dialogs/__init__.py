"""
FilterMate UI Dialogs.

Modal dialog components for user interactions.
"""
from .favorites_manager import FavoritesManagerDialog
from .optimization_dialog import OptimizationDialog, OptimizationSettings, RecommendationDialog
from .postgres_info_dialog import PostgresInfoDialog
from .config_editor_widget import (
    ConfigEditorWidget,
    SimpleConfigDialog,
    TabbedConfigDialog,
    ColorPickerWidget
)
from .zonal_stats_dialog import ZonalStatsDialog

__all__ = [
    'FavoritesManagerDialog',
    'OptimizationDialog',
    'OptimizationSettings',
    'RecommendationDialog',
    'PostgresInfoDialog',
    # Config editor
    'ConfigEditorWidget',
    'SimpleConfigDialog',
    'TabbedConfigDialog',
    'ColorPickerWidget',
    # EPIC-3: Raster integration
    'ZonalStatsDialog',
]
