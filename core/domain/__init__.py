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
from .filter_expression import (  # noqa: F401
    FilterExpression,
    ProviderType,
    SpatialPredicate,
)
from .filter_result import (  # noqa: F401
    FilterResult,
    FilterStatus,
)
from .layer_info import (  # noqa: F401
    LayerInfo,
    GeometryType,
)
from .optimization_config import (  # noqa: F401
    OptimizationConfig,
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
]
