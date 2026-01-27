"""
FilterMate UI Controllers.

Controller classes managing UI state and user interactions.
Implements MVC pattern for the dockwidget tabs.
"""
from .base_controller import BaseController
from .registry import TabIndex, ControllerRegistry
from .mixins import LayerSelectionMixin
from .exploring_controller import ExploringController
from .filtering_controller import (
    FilteringController,
    FilterConfiguration,
    FilterResult,
    PredicateType,
    BufferType
)
from .exporting_controller import (
    ExportingController,
    ExportConfiguration,
    ExportResult,
    ExportFormat,
    ExportMode
)
from .config_controller import ConfigController
from .backend_controller import BackendController
from .favorites_controller import FavoritesController
from .layer_sync_controller import LayerSyncController
from .property_controller import PropertyController, PropertyType, PropertyChange
from .integration import ControllerIntegration
from .raster_exploring_controller import RasterExploringController

__all__ = [
    'BaseController',
    'TabIndex',
    'ControllerRegistry',
    'LayerSelectionMixin',
    'ExploringController',
    'FilteringController',
    'FilterConfiguration',
    'FilterResult',
    'PredicateType',
    'BufferType',
    'ExportingController',
    'ExportConfiguration',
    'ExportResult',
    'ExportFormat',
    'ExportMode',
    'ConfigController',
    'BackendController',
    'FavoritesController',
    'LayerSyncController',
    'PropertyController',
    'PropertyType',
    'PropertyChange',
    'ControllerIntegration',
    'RasterExploringController',
]
