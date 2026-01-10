# -*- coding: utf-8 -*-
"""
Query Complexity Estimator - LEGACY SHIM

⚠️ DEPRECATED: This module has been migrated to infrastructure/utils/complexity_estimator.py (EPIC-1)

MIGRATION GUIDE:
- OLD: from modules.tasks.query_complexity_estimator import QueryComplexityEstimator
- NEW: from infrastructure.utils import QueryComplexityEstimator

All functionality is now available from:
    from infrastructure.utils import (
        QueryComplexity,
        ComplexityBreakdown,
        OperationCosts,
        QueryComplexityEstimator,
        get_complexity_estimator,
        estimate_query_complexity
    )

This shim provides backward compatibility but will be removed in v3.1.
"""

import warnings

warnings.warn(
    "modules.tasks.query_complexity_estimator is deprecated. "
    "Use 'from infrastructure.utils import QueryComplexityEstimator' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from infrastructure
from infrastructure.utils import (
    QueryComplexity,
    ComplexityBreakdown,
    OperationCosts,
    QueryComplexityEstimator,
    get_complexity_estimator,
    estimate_query_complexity
)

__all__ = [
    'QueryComplexity',
    'ComplexityBreakdown',
    'OperationCosts',
    'QueryComplexityEstimator',
    'get_complexity_estimator',
    'estimate_query_complexity'
]
