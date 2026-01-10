# -*- coding: utf-8 -*-
"""
Progressive Filter Executor - LEGACY SHIM

⚠️ DEPRECATED: This module has been migrated to core/strategies/progressive_filter.py (EPIC-1)

MIGRATION GUIDE:
- OLD: from modules.tasks.progressive_filter import ProgressiveFilterExecutor
- NEW: from core.strategies import ProgressiveFilterExecutor

All functionality is now available from:
    from core.strategies import (
        ProgressiveFilterStrategy,      # Was: FilterStrategy
        ProgressiveFilterResult,        # Was: FilterResult
        LayerProperties,
        LazyResultIterator,
        TwoPhaseFilter,
        ProgressiveFilterExecutor,
        progressive_filter
    )

This shim provides backward compatibility but will be removed in v4.0.

Migration: modules/tasks/progressive_filter.py → core/strategies/progressive_filter.py
Date: January 2026
EPIC: EPIC-1 (Suppression du dossier modules/)
Reduction: 881 lines → 65 lines (-93%)
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "modules.tasks.progressive_filter is deprecated. "
    "Use 'from core.strategies import ...' instead. "
    "This shim will be removed in FilterMate v4.0.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
# Note: FilterStrategy and FilterResult are renamed to avoid conflicts
from core.strategies.progressive_filter import (
    FilterStrategy,
    FilterResult,
    LayerProperties,
    LazyResultIterator,
    TwoPhaseFilter,
    ProgressiveFilterExecutor,
    progressive_filter
)

# Also provide aliases used in core.strategies
ProgressiveFilterStrategy = FilterStrategy
ProgressiveFilterResult = FilterResult

__all__ = [
    'FilterStrategy',
    'FilterResult',
    'LayerProperties',
    'LazyResultIterator',
    'TwoPhaseFilter',
    'ProgressiveFilterExecutor',
    'progressive_filter',
    # Aliases
    'ProgressiveFilterStrategy',
    'ProgressiveFilterResult'
]
