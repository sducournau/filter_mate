"""
FilterMate QGIS Signals.

Signal management and debouncing utilities.
"""
from .signal_manager import SignalManager  # noqa: F401
from .debouncer import Debouncer  # noqa: F401
from .layer_signal_handler import LayerSignalHandler  # noqa: F401
from .migration_helper import (  # noqa: F401
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
