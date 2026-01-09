"""
FilterMate UI Dialogs.

Modal dialog components for user interactions.
"""
from .favorites_manager import FavoritesManagerDialog
from .optimization_dialog import OptimizationDialog, OptimizationSettings, RecommendationDialog
from .postgres_info_dialog import PostgresInfoDialog

__all__ = [
    'FavoritesManagerDialog',
    'OptimizationDialog',
    'OptimizationSettings',
    'RecommendationDialog',
    'PostgresInfoDialog',
]
