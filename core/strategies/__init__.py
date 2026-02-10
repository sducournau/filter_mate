"""
Core Strategies Package

Filter execution strategies for different backends and data sizes.
Provides progressive, multi-step, and adaptive filtering for large datasets.

This is part of the Hexagonal Architecture - Core Layer (Domain Services).

Progressive Filtering (progressive_filter):
    - Two-phase filtering (bbox pre-filter + full predicate)
    - Streaming cursor for memory-efficient iteration
    - Chunked ID retrieval to avoid massive IN clauses

Multi-Step Filtering (multi_step_filter):
    - Attribute-first strategy for selective filters
    - Bbox-then-attribute-then-full for complex expressions
    - Statistical adaptive ordering based on PostgreSQL stats

Performance Benefits:
    - 3-10x faster on complex expressions (two-phase)
    - 5-20x faster on selective attribute filters (multi-step)
    - 50-80% memory reduction (streaming)

Migration History:
    - v3.0: Created core/strategies/ package (EPIC-1)
    - v3.0: Migrated from modules/tasks/progressive_filter.py
    - v3.0: Migrated from modules/tasks/multi_step_filter.py
"""

# Progressive filter exports
from .progressive_filter import (
    FilterStrategy as ProgressiveFilterStrategy,
    FilterResult as ProgressiveFilterResult,
    LayerProperties,
    LazyResultIterator,
    TwoPhaseFilter,
    ProgressiveFilterExecutor,
    progressive_filter
)

# Multi-step filter exports
from .multi_step_filter import (
    FilterStepType,
    FilterStrategy as MultiStepFilterStrategy,
    FilterStepResult,
    FilterPlanResult,
    FilterStep,
    LayerStatistics,
    SelectivityEstimator,
    FilterPlanBuilder,
    MultiStepFilterExecutor,
    MultiStepFilterOptimizer,
    get_optimal_filter_plan
)

__all__ = [
    # Progressive filter
    'ProgressiveFilterStrategy',
    'ProgressiveFilterResult',
    'LayerProperties',
    'LazyResultIterator',
    'TwoPhaseFilter',
    'ProgressiveFilterExecutor',
    'progressive_filter',
    # Multi-step filter
    'FilterStepType',
    'MultiStepFilterStrategy',
    'FilterStepResult',
    'FilterPlanResult',
    'FilterStep',
    'LayerStatistics',
    'SelectivityEstimator',
    'FilterPlanBuilder',
    'MultiStepFilterExecutor',
    'MultiStepFilterOptimizer',
    'get_optimal_filter_plan'
]
