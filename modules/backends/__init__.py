# -*- coding: utf-8 -*-
"""
FilterMate Backend Architecture (LEGACY)

.. deprecated:: 3.0.0
    This package is deprecated and will be removed in a future version.
    
    NEW CODE SHOULD USE THE HEXAGONAL ARCHITECTURE:
    
    - For backends: ``adapters.backends``
    - For factory: ``adapters.backends.BackendFactory``
    - For optimizer: ``core.services.auto_optimizer.AutoOptimizer``
    - For filter optimizer: ``adapters.qgis.filter_optimizer.QgisFilterOptimizer``
    
    Example of new imports::
    
        from adapters.backends import BackendFactory, create_backend_factory
        from adapters.backends.memory.backend import MemoryBackend
        from core.services.auto_optimizer import AutoOptimizer

This package contains the legacy backend implementations for different data providers:
- PostgreSQL (optimized for performance with large datasets)
- Spatialite (good performance for small to medium datasets)
- OGR (fallback for various file formats)
- Memory (optimized for QGIS memory layers)

Each backend implements the GeometricFilterBackend interface.

v2.4.0 Optimization Modules:
- MVRegistry: Automatic cleanup of PostgreSQL materialized views
- WKTCache: LRU cache for WKT geometries in Spatialite
- SpatialIndexManager: Automatic spatial index creation for OGR layers

v2.5.8: Memory Backend
- Dedicated backend for QGIS memory layers
- Uses QgsSpatialIndex for O(log n) spatial queries
- Accurate feature counting with iteration fallback

v2.5.10: Multi-Step Filter Optimizer
- Adaptive multi-step filtering for large datasets
- Attribute-first strategy for selective attribute filters
- Selectivity estimation for optimal strategy selection
"""

from .base_backend import GeometricFilterBackend
from .postgresql_backend import PostgreSQLGeometricFilter
from .spatialite_backend import SpatialiteGeometricFilter
from .ogr_backend import OGRGeometricFilter
from .memory_backend import MemoryGeometricFilter
from .factory import BackendFactory

# v2.4.0 Optimization modules
try:
    from .mv_registry import MVRegistry, get_mv_registry
except ImportError:
    MVRegistry = None
    get_mv_registry = None

try:
    from .wkt_cache import WKTCache, get_wkt_cache
except ImportError:
    WKTCache = None
    get_wkt_cache = None

try:
    from .spatial_index_manager import SpatialIndexManager, get_spatial_index_manager
except ImportError:
    SpatialIndexManager = None
    get_spatial_index_manager = None

# v2.5.10: Multi-Step Filter Optimizer
try:
    from .multi_step_optimizer import (
        MultiStepFilterOptimizer,
        MultiStepPlanBuilder,
        BackendFilterStrategy,
        AttributePreFilter,
        ChunkedProcessor,
        BackendSelectivityEstimator,
        SpatialiteOptimizer,
        OGROptimizer,
        MemoryOptimizer
    )
except ImportError:
    MultiStepFilterOptimizer = None
    MultiStepPlanBuilder = None
    BackendFilterStrategy = None
    AttributePreFilter = None
    ChunkedProcessor = None
    BackendSelectivityEstimator = None
    SpatialiteOptimizer = None
    OGROptimizer = None
    MemoryOptimizer = None

# v2.7.0: Auto-Optimizer for intelligent heuristics
try:
    from .auto_optimizer import (
        AutoOptimizer,
        LayerAnalyzer,
        OptimizationPlan,
        OptimizationType,
        LayerLocationType,
        OptimizationRecommendation,
        LayerAnalysis,
        recommend_optimizations,
        get_auto_optimizer,
        # v2.8.0: Enhanced optimizer
        EnhancedAutoOptimizer,
        get_enhanced_optimizer,
        get_optimization_statistics,
        clear_optimization_cache,
        ENHANCED_OPTIMIZER_AVAILABLE,
    )
    from .factory import (
        get_optimization_plan,
        should_use_centroids,
        analyze_layer_for_optimization,
        AUTO_OPTIMIZER_AVAILABLE
    )
except ImportError:
    AutoOptimizer = None
    LayerAnalyzer = None
    OptimizationPlan = None
    OptimizationType = None
    LayerLocationType = None
    OptimizationRecommendation = None
    LayerAnalysis = None
    recommend_optimizations = None
    get_auto_optimizer = None
    get_optimization_plan = None
    should_use_centroids = None
    analyze_layer_for_optimization = None
    AUTO_OPTIMIZER_AVAILABLE = False
    # v2.8.0
    EnhancedAutoOptimizer = None
    get_enhanced_optimizer = None
    get_optimization_statistics = None
    clear_optimization_cache = None
    ENHANCED_OPTIMIZER_AVAILABLE = False

# v2.8.0: Optimizer metrics and parallel processing
try:
    from .optimizer_metrics import (
        OptimizationMetricsCollector,
        get_metrics_collector,
        LRUCache,
        QueryPatternDetector,
        AdaptiveThresholdManager,
        SelectivityHistogram,
        OptimizationSession,
    )
    METRICS_AVAILABLE = True
except ImportError:
    OptimizationMetricsCollector = None
    get_metrics_collector = None
    LRUCache = None
    QueryPatternDetector = None
    AdaptiveThresholdManager = None
    SelectivityHistogram = None
    OptimizationSession = None
    METRICS_AVAILABLE = False

try:
    from .parallel_processor import (
        ParallelChunkProcessor,
        get_parallel_processor,
        should_use_parallel_processing,
        PARALLEL_AVAILABLE,
        ParallelProcessingStats,
    )
except ImportError:
    ParallelChunkProcessor = None
    get_parallel_processor = None
    should_use_parallel_processing = None
    PARALLEL_AVAILABLE = False
    ParallelProcessingStats = None

__all__ = [
    # Core backends
    'GeometricFilterBackend',
    'PostgreSQLGeometricFilter',
    'SpatialiteGeometricFilter',
    'OGRGeometricFilter',
    'MemoryGeometricFilter',
    'BackendFactory',
    # v2.4.0 Optimization modules
    'MVRegistry',
    'get_mv_registry',
    'WKTCache',
    'get_wkt_cache',
    'SpatialIndexManager',
    'get_spatial_index_manager',
    # v2.5.10 Multi-Step Optimizer
    'MultiStepFilterOptimizer',
    'MultiStepPlanBuilder',
    'BackendFilterStrategy',
    'AttributePreFilter',
    'ChunkedProcessor',
    'BackendSelectivityEstimator',
    'SpatialiteOptimizer',
    'OGROptimizer',
    'MemoryOptimizer',
    # v2.7.0 Auto-Optimizer
    'AutoOptimizer',
    'LayerAnalyzer',
    'OptimizationPlan',
    'OptimizationType',
    'LayerLocationType',
    'OptimizationRecommendation',
    'LayerAnalysis',
    'recommend_optimizations',
    'get_auto_optimizer',
    'get_optimization_plan',
    'should_use_centroids',
    'analyze_layer_for_optimization',
    'AUTO_OPTIMIZER_AVAILABLE',
    # v2.8.0 Enhanced Optimizer
    'EnhancedAutoOptimizer',
    'get_enhanced_optimizer',
    'get_optimization_statistics',
    'clear_optimization_cache',
    'ENHANCED_OPTIMIZER_AVAILABLE',
    # v2.8.0 Metrics
    'OptimizationMetricsCollector',
    'get_metrics_collector',
    'LRUCache',
    'QueryPatternDetector',
    'AdaptiveThresholdManager',
    'SelectivityHistogram',
    'OptimizationSession',
    'METRICS_AVAILABLE',
    # v2.8.0 Parallel Processing
    'ParallelChunkProcessor',
    'get_parallel_processor',
    'should_use_parallel_processing',
    'PARALLEL_AVAILABLE',
    'ParallelProcessingStats',
]
