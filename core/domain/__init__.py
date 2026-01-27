"""
FilterMate Core Domain Module.

Domain models and entities for filter operations.
This module contains pure Python value objects and entities
with NO QGIS dependencies.

Value Objects (immutable, equality by value):
- FilterExpression: Validated filter expression with SQL conversion
- FilterResult: Result of a filter operation
- OptimizationConfig: Backend optimization settings

Entities (identity-based):
- LayerInfo: Layer metadata without QGIS dependency

Enums:
- ProviderType: Supported data provider types
- SpatialPredicate: Spatial filter predicates
- FilterStatus: Filter operation status
- GeometryType: Geometry types
"""
from .filter_expression import (
    FilterExpression,
    ProviderType,
    SpatialPredicate,
)
from .filter_result import (
    FilterResult,
    FilterStatus,
)
from .layer_info import (
    LayerInfo,
    GeometryType,
)
from .optimization_config import (
    OptimizationConfig,
)
from .raster_errors import (
    # Enums
    ErrorSeverity,
    RasterErrorCategory,
    # Exceptions
    RasterError,
    LayerNotFoundError,
    LayerInvalidError,
    StatisticsComputationError,
    HistogramComputationError,
    TransparencyApplicationError,
    PixelIdentifyError,
    CacheError,
    MemoryError,
    # Result container
    ErrorResult,
    # Handler
    RasterErrorHandler,
    get_error_handler,
    reset_error_handler,
    # Decorators
    handle_raster_errors,
    with_error_result,
)

__all__ = [
    # Value Objects
    'FilterExpression',
    'FilterResult',
    'OptimizationConfig',
    # Entities
    'LayerInfo',
    # Enums
    'ProviderType',
    'SpatialPredicate',
    'FilterStatus',
    'GeometryType',
    # Raster Errors (EPIC-2)
    'ErrorSeverity',
    'RasterErrorCategory',
    'RasterError',
    'LayerNotFoundError',
    'LayerInvalidError',
    'StatisticsComputationError',
    'HistogramComputationError',
    'TransparencyApplicationError',
    'PixelIdentifyError',
    'CacheError',
    'MemoryError',
    'ErrorResult',
    'RasterErrorHandler',
    'get_error_handler',
    'reset_error_handler',
    'handle_raster_errors',
    'with_error_result',
]
