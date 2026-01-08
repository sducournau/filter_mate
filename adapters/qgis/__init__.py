"""
FilterMate QGIS Adapters.

QGIS-specific implementations for tasks, signals, and layer management.

Submodules:
    - filter_optimizer: Multi-step filter optimization for QGIS layers
    - tasks: Async task implementations
    - signals: QGIS signal handlers
"""

from .filter_optimizer import (
    QgisFilterOptimizer,
    QgisSelectivityEstimator,
    SpatialiteQueryBuilder,
    OgrSubsetBuilder,
    MemorySpatialIndex,
    get_filter_optimizer,
    create_filter_optimizer,
)

__all__ = [
    'QgisFilterOptimizer',
    'QgisSelectivityEstimator',
    'SpatialiteQueryBuilder',
    'OgrSubsetBuilder',
    'MemorySpatialIndex',
    'get_filter_optimizer',
    'create_filter_optimizer',
]
