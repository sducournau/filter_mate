"""
Core Optimization Package

Query optimization strategies for FilterMate filter operations.
Provides optimizers for multi-step expressions across different backends.

This is part of the Hexagonal Architecture - Core Layer (Application Services).

Exported Symbols:
    - OptimizationType: Enum of optimization types applied
    - MaterializedViewInfo: PostgreSQL MV reference information
    - FidListInfo: Spatialite/OGR FID list information
    - RangeInfo: Consecutive FID range information
    - OptimizationResult: Result with optimization metadata
    - CombinedQueryOptimizer: Main optimizer class
    - get_combined_query_optimizer: Singleton factory function
    - optimize_combined_filter: Convenience function
    - AutoBackendSelector: Automatic backend selection (v4.1 Phase 2)
    - BackendRecommendation: Backend recommendation dataclass (v4.1 Phase 2)
    - BackendType: Enum of backend types (v4.1 Phase 2)
    - get_auto_backend_selector: Singleton factory for AutoBackendSelector (v4.1 Phase 2)
    - MultiStepFilterOptimizer: Complex filter decomposition (v4.1 Phase 2)
    - FilterStep: Single filter step dataclass (v4.1 Phase 2)
    - get_multi_step_optimizer: Singleton factory for MultiStepFilterOptimizer (v4.1 Phase 2)

Architecture:
    core/optimization/ → Application layer (query optimization logic)
    infrastructure/ → External adapters (cache, logging, database)
    adapters/ → Anti-corruption layer (legacy compatibility)

Performance Benefits:
    - PostgreSQL MV reuse: 10-50× faster
    - Spatialite/OGR FID optimization: 2-5× faster
    - Expression caching: Avoid redundant parsing
    - Auto backend selection: Choose optimal backend automatically (v4.1)
    - Multi-step filtering: 2-8× faster for complex filters (v4.1)

Migration History:
    - v3.0: Created core/optimization/ package (EPIC-1)
    - v3.0: Migrated from modules/tasks/combined_query_optimizer.py
    - v4.1.0-beta.2: Added AutoBackendSelector (Phase 2)
    - v4.1.0-beta.2: Added MultiStepFilterOptimizer (Phase 2)
"""

from .combined_query_optimizer import (
    OptimizationType,
    MaterializedViewInfo,
    FidListInfo,
    ExistsClauseInfo,
    SpatialPredicateInfo,
    SourceMVInfo,
    OptimizationResult,
    CombinedQueryOptimizer,
    get_combined_query_optimizer,
    optimize_combined_filter,
    detect_backend_type,
    optimize_for_backend
)

from .auto_backend_selector import (
    AutoBackendSelector,
    BackendRecommendation,
    BackendType,
    get_auto_backend_selector
)

from .multi_step_filter import (
    MultiStepFilterOptimizer,
    FilterStep,
    get_multi_step_optimizer
)

# Auto Optimizer (v4.1.0 migrated from before_migration)
from .auto_optimizer import (
    AUTO_OPTIMIZER_AVAILABLE,
    AutoOptimizer,
    LayerAnalyzer,
    LayerAnalysis,
    LayerLocationType,
    OptimizationRecommendation,
    OptimizationPlan,
    get_auto_optimizer,
    get_auto_optimization_config,
    analyze_layer,
)

# Raster Performance (EPIC-2 US-12)
from .raster_performance import (
    PerformanceThresholds,
    DEFAULT_THRESHOLDS,
    SamplingStrategy,
    SamplingConfig,
    RasterSampler,
    ProgressInfo,
    ProgressTracker,
    ComputationThrottle,
    MemoryEstimate,
    estimate_memory,
    batch_iterator,
    chunked_range,
)

__all__ = [
    # Combined Query Optimizer (v3.0+)
    'OptimizationType',
    'MaterializedViewInfo',
    'FidListInfo',
    'ExistsClauseInfo',
    'SpatialPredicateInfo',
    'SourceMVInfo',
    'OptimizationResult',
    'CombinedQueryOptimizer',
    'get_combined_query_optimizer',
    'optimize_combined_filter',
    'detect_backend_type',
    'optimize_for_backend',
    # Auto Backend Selector (v4.1 Phase 2)
    'AutoBackendSelector',
    'BackendRecommendation',
    'BackendType',
    'get_auto_backend_selector',
    # Multi-Step Filter Optimizer (v4.1 Phase 2)
    'MultiStepFilterOptimizer',
    'FilterStep',
    'get_multi_step_optimizer',
    # Auto Optimizer (v4.1.0 migrated from before_migration)
    'AUTO_OPTIMIZER_AVAILABLE',
    'AutoOptimizer',
    'LayerAnalyzer',
    'LayerAnalysis',
    'LayerLocationType',
    'OptimizationRecommendation',
    'OptimizationPlan',
    'get_auto_optimizer',
    'get_auto_optimization_config',
    'analyze_layer',
    # Raster Performance (EPIC-2 US-12)
    'PerformanceThresholds',
    'DEFAULT_THRESHOLDS',
    'SamplingStrategy',
    'SamplingConfig',
    'RasterSampler',
    'ProgressInfo',
    'ProgressTracker',
    'ComputationThrottle',
    'MemoryEstimate',
    'estimate_memory',
    'batch_iterator',
    'chunked_range',
]
