"""
FilterMate Core Domain Module.

Domain models and entities for filter operations.
This module contains pure Python value objects and entities
with NO QGIS dependencies.

Value Objects (immutable, equality by value):
- FilterExpression: Validated filter expression with SQL conversion
- FilterResult: Result of a filter operation
- OptimizationConfig: Backend optimization settings
- VectorFilterCriteria: Filter criteria for vector layers (v5.0)
- RasterFilterCriteria: Filter criteria for raster layers (v5.0)

Entities (identity-based):
- LayerInfo: Layer metadata without QGIS dependency

Enums:
- ProviderType: Supported data provider types
- SpatialPredicate: Spatial filter predicates
- FilterStatus: Filter operation status
- GeometryType: Geometry types
- LayerType: Layer type (vector, raster) (v5.0)
- RasterPredicate: Raster value predicates (v5.0)

Type Aliases:
- UnifiedFilterCriteria: Union of vector and raster criteria (v5.0)
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
# v5.0: Unified Filter Criteria (EPIC-UNIFIED-FILTER)
from .filter_criteria import (
    LayerType,
    VectorFilterCriteria,
    RasterFilterCriteria,
    RasterPredicate,
    UnifiedFilterCriteria,
    validate_criteria,
    criteria_from_dict,
)

__all__ = [
    # Value Objects
    'FilterExpression',
    'FilterResult',
    'OptimizationConfig',
    # v5.0: Unified Filter Criteria
    'VectorFilterCriteria',
    'RasterFilterCriteria',
    'UnifiedFilterCriteria',
    'validate_criteria',
    'criteria_from_dict',
    # Entities
    'LayerInfo',
    # Enums
    'ProviderType',
    'SpatialPredicate',
    'FilterStatus',
    'GeometryType',
    'LayerType',
    'RasterPredicate',
]
