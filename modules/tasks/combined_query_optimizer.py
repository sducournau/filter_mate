"""
DEPRECATED - CombinedQueryOptimizer migration shim

This module has been migrated to core/optimization/ as part of EPIC-1.
Imports are preserved for backward compatibility but will be removed in a future version.

Migration: modules/tasks/combined_query_optimizer.py → core/optimization/combined_query_optimizer.py
Date: January 2026
EPIC: EPIC-1 (Suppression du dossier modules/)
Reduction: 1599 lines → 45 lines (-97%)

New location:
    from core.optimization import (
        CombinedQueryOptimizer,
        get_combined_query_optimizer,
        optimize_combined_filter
    )
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "modules.tasks.combined_query_optimizer is deprecated. "
    "Use core.optimization instead. "
    "This shim will be removed in FilterMate v4.0.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from core.optimization import (
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
