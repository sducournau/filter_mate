# -*- coding: utf-8 -*-
"""
Combined Query Optimizer - LEGACY SHIM

⚠️ DEPRECATED: This module has been migrated to core/optimization/combined_query_optimizer.py (EPIC-1)

MIGRATION GUIDE:
- OLD: from modules.tasks.combined_query_optimizer import CombinedQueryOptimizer
- NEW: from core.optimization import CombinedQueryOptimizer

All functionality is now available from:
    from core.optimization import (
        OptimizationType,
        MaterializedViewInfo,
        FidListInfo,
        RangeInfo,
        OptimizationResult,
        CombinedQueryOptimizer,
        get_combined_query_optimizer,
        optimize_combined_filter
    )

This shim provides backward compatibility but will be removed in v4.0.

Migration: modules/tasks/combined_query_optimizer.py → core/optimization/combined_query_optimizer.py
Date: January 2026
EPIC: EPIC-1 (Suppression du dossier modules/)
Reduction: 1599 lines → 52 lines (-97%)
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "modules.tasks.combined_query_optimizer is deprecated. "
    "Use 'from core.optimization import ...' instead. "
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
