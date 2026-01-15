# -*- coding: utf-8 -*-
"""
Compatibility layer for legacy modules.backends imports.

This module provides backward compatibility for code that imports
from the old modules.backends location. New code should use:

    from ..adapters.backends import BackendFactory
    from ..adapters.qgis.filter_optimizer import QgisFilterOptimizer
    from ..core.services.auto_optimizer import AutoOptimizer

Legacy imports (still supported but deprecated):

    from ..adapters.backends.factory import BackendFactory
    from ..core.services.auto_optimizer import AutoOptimizer, LayerAnalyzer

Part of FilterMate Hexagonal Architecture v3.0

Migration Guide (MIG-011):
    
    # Old v2.x code:
    from ..adapters.backends.postgresql import PostgreSQLBackend
    backend = PostgreSQLBackend(task_params)
    backend.apply_filter(layer, expression)
    
    # New v3.0 code with adapter (transitional):
    from ..adapters.legacy_adapter import wrap_legacy_postgresql_backend
    adapted = wrap_legacy_postgresql_backend(task_params)
    result = adapted.execute(expression, layer_info)
    
    # New v3.0 code (preferred):
    from ..adapters.backends.postgresql.backend import PostgreSQLBackend
    from ..core.services.filter_service import FilterService
    service = FilterService(backends={ProviderType.POSTGRESQL: backend})
    response = service.apply_filter(request)
"""

# Re-export from new locations for compatibility
from .backends.factory import (
    BackendFactory,
    BackendSelector,
    create_backend_factory,
)

from .backends.memory.backend import MemoryBackend
from .backends.ogr.backend import OgrBackend
from .backends.spatialite.backend import SpatialiteBackend
from .backends.postgresql.backend import PostgreSQLBackend

from ..core.services.auto_optimizer import (
    AutoOptimizer,
    OptimizationType,
    OptimizerConfig,
    LayerAnalysis,
    OptimizationRecommendation,
    OptimizationPlan,
    get_auto_optimizer,
    create_auto_optimizer,
    recommend_optimizations,
)

from .qgis.filter_optimizer import (
    QgisFilterOptimizer,
    QgisSelectivityEstimator,
    SpatialiteQueryBuilder,
    OgrSubsetBuilder,
    MemorySpatialIndex,
    get_filter_optimizer,
    create_filter_optimizer,
)

from ..core.ports.filter_optimizer import (
    FilterStrategy,
    FilterPlan,
    FilterStep,
    LayerStatistics,
    PlanBuilderConfig,
    IFilterOptimizer,
    ISelectivityEstimator,
)

# MIG-011: Legacy Backend Adapter for v2.x → v3.0 migration
from .legacy_adapter import (
    LegacyBackendAdapter,
    wrap_legacy_postgresql_backend,
    wrap_legacy_spatialite_backend,
    wrap_legacy_ogr_backend,
    create_all_legacy_adapters,
)

__all__ = [
    # Factory
    'BackendFactory',
    'BackendSelector', 
    'create_backend_factory',
    
    # Backends
    'MemoryBackend',
    'OgrBackend',
    'SpatialiteBackend',
    'PostgreSQLBackend',
    
    # AutoOptimizer
    'AutoOptimizer',
    'OptimizationType',
    'OptimizerConfig',
    'LayerAnalysis',
    'OptimizationRecommendation',
    'OptimizationPlan',
    'get_auto_optimizer',
    'create_auto_optimizer',
    'recommend_optimizations',
    
    # FilterOptimizer
    'QgisFilterOptimizer',
    'QgisSelectivityEstimator',
    'SpatialiteQueryBuilder',
    'OgrSubsetBuilder',
    'MemorySpatialIndex',
    'get_filter_optimizer',
    'create_filter_optimizer',
    
    # Ports
    'FilterStrategy',
    'FilterPlan',
    'FilterStep',
    'LayerStatistics',
    'PlanBuilderConfig',
    'IFilterOptimizer',
    'ISelectivityEstimator',
    
    # MIG-011: Legacy Adapters
    'LegacyBackendAdapter',
    'wrap_legacy_postgresql_backend',
    'wrap_legacy_spatialite_backend',
    'wrap_legacy_ogr_backend',
    'create_all_legacy_adapters',
]
