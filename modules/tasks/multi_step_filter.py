# -*- coding: utf-8 -*-
"""
Multi-Step Filter Optimizer - LEGACY SHIM

⚠️ DEPRECATED: This module has been migrated to core/strategies/multi_step_filter.py (EPIC-1)

MIGRATION GUIDE:
- OLD: from modules.tasks.multi_step_filter import MultiStepFilterOptimizer
- NEW: from core.strategies import MultiStepFilterOptimizer

All functionality is now available from:
    from core.strategies import (
        FilterStepType,
        MultiStepFilterStrategy,        # Was: FilterStrategy
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

This shim provides backward compatibility but will be removed in v4.0.

Migration: modules/tasks/multi_step_filter.py → core/strategies/multi_step_filter.py
Date: January 2026
EPIC: EPIC-1 (Suppression du dossier modules/)
Reduction: 1051 lines → 70 lines (-93%)
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "modules.tasks.multi_step_filter is deprecated. "
    "Use 'from core.strategies import ...' instead. "
    "This shim will be removed in FilterMate v4.0.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from ...core.strategies.multi_step_filter import (
    FilterStepType,
    FilterStrategy,
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

# Also provide alias used in core.strategies
MultiStepFilterStrategy = FilterStrategy

__all__ = [
    'FilterStepType',
    'FilterStrategy',
    'FilterStepResult',
    'FilterPlanResult',
    'FilterStep',
    'LayerStatistics',
    'SelectivityEstimator',
    'FilterPlanBuilder',
    'MultiStepFilterExecutor',
    'MultiStepFilterOptimizer',
    'get_optimal_filter_plan',
    # Alias
    'MultiStepFilterStrategy'
]
