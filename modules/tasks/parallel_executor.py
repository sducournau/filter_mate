"""
DEPRECATED - ParallelFilterExecutor migration shim

This module has been migrated to infrastructure/parallel/ as part of EPIC-1.
Imports are preserved for backward compatibility but will be removed in a future version.

Migration: modules/tasks/parallel_executor.py → infrastructure/parallel/parallel_executor.py
Date: January 2026
EPIC: EPIC-1 (Suppression du dossier modules/)
Reduction: 701 lines → 37 lines (-95%)

New location:
    from infrastructure.parallel import (
        FilterResult,
        ParallelFilterExecutor,
        ParallelConfig
    )
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "modules.tasks.parallel_executor is deprecated. "
    "Use infrastructure.parallel instead. "
    "This shim will be removed in FilterMate v4.0.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from infrastructure.parallel import (
    FilterResult,
    ParallelFilterExecutor,
    ParallelConfig
)

__all__ = [
    'FilterResult',
    'ParallelFilterExecutor',
    'ParallelConfig'
]
