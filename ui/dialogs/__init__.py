"""
FilterMate UI Dialogs.

Modal dialog components for user interactions.
"""
from .favorites_manager import FavoritesManagerDialog  # noqa: F401
from .optimization_dialog import OptimizationDialog, OptimizationSettings, RecommendationDialog  # noqa: F401
from .postgres_info_dialog import PostgresInfoDialog  # noqa: F401
from .config_editor_widget import (  # noqa: F401
    ConfigEditorWidget,
    SimpleConfigDialog,
    TabbedConfigDialog,
    ColorPickerWidget
)

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
]
