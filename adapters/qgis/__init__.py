"""
FilterMate QGIS Adapters.

QGIS-specific implementations for tasks, signals, and layer management.

Submodules:
    - filter_optimizer: Multi-step filter optimization for QGIS layers
    - geometry_preparation: Geometry preparation for spatial filtering
    - tasks: Async task implementations
    - signals: QGIS signal handlers
"""

from .filter_optimizer import (  # noqa: F401
    QgisFilterOptimizer,
    QgisSelectivityEstimator,
    SpatialiteQueryBuilder,
    OgrSubsetBuilder,
    MemorySpatialIndex,
    get_filter_optimizer,
    create_filter_optimizer,
)

from .geometry_preparation import (  # noqa: F401
    GeometryPreparationAdapter,
    GeometryPreparationConfig,
    GeometryPreparationResult,
    create_geometry_preparation_adapter,
)

from .source_feature_resolver import (  # noqa: F401
    SourceFeatureResolver,
    FeatureResolverConfig,
    FeatureResolutionResult,
    FeatureSourceMode,
    create_source_feature_resolver,
)

__all__ = [
    # Filter optimizer
    'QgisFilterOptimizer',
    'QgisSelectivityEstimator',
    'SpatialiteQueryBuilder',
    'OgrSubsetBuilder',
    'MemorySpatialIndex',
    'get_filter_optimizer',
    'create_filter_optimizer',
    # Geometry preparation
    'GeometryPreparationAdapter',
    'GeometryPreparationConfig',
    'GeometryPreparationResult',
    'create_geometry_preparation_adapter',
    # Source feature resolver
    'SourceFeatureResolver',
    'FeatureResolverConfig',
    'FeatureResolutionResult',
    'FeatureSourceMode',
    'create_source_feature_resolver',
]
