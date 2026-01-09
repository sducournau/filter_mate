"""
FilterMate QGIS Signals.

Signal management and debouncing utilities.
"""
from .signal_manager import SignalManager
from .debouncer import Debouncer
from .layer_signal_handler import LayerSignalHandler
from .migration_helper import (
    SignalMigrationHelper,
    SignalDefinition,
    SignalCategory,
    MigrationResult,
    deprecated_signal_connection,
    DOCKWIDGET_WIDGET_SIGNALS,
    get_all_signal_definitions,
    get_signals_by_category,
    get_signals_by_context,
)

__all__ = [
    'SignalManager',
    'Debouncer',
    'LayerSignalHandler',
    'SignalMigrationHelper',
    'SignalDefinition',
    'SignalCategory',
    'MigrationResult',
    'deprecated_signal_connection',
    'DOCKWIDGET_WIDGET_SIGNALS',
    'get_all_signal_definitions',
    'get_signals_by_category',
    'get_signals_by_context',
]
