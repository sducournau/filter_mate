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

Architecture:
    core/optimization/ → Application layer (query optimization logic)
    infrastructure/ → External adapters (cache, logging, database)
    adapters/ → Anti-corruption layer (legacy compatibility)

Performance Benefits:
    - PostgreSQL MV reuse: 10-50× faster
    - Spatialite/OGR FID optimization: 2-5× faster
    - Expression caching: Avoid redundant parsing

Migration History:
    - v3.0: Created core/optimization/ package (EPIC-1)
    - v3.0: Migrated from modules/tasks/combined_query_optimizer.py
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

__all__ = [
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
    'optimize_for_backend'
]
