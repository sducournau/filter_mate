"""
DEPRECATED - ExpressionEvaluationTask migration shim

This module has been migrated to core/tasks/ as part of EPIC-1.
Imports are preserved for backward compatibility but will be removed in a future version.

Migration: modules/tasks/expression_evaluation_task.py → core/tasks/expression_evaluation_task.py
Date: January 2026
EPIC: EPIC-1 (Suppression du dossier modules/)
Reduction: 530 lines → 35 lines (-93%)

New location:
    from core.tasks import (
        ExpressionEvaluationSignals,
        ExpressionEvaluationTask,
        ExpressionEvaluationManager,
        get_expression_manager
    )
"""

import warnings

# Issue deprecation warning
warnings.warn(
    "modules.tasks.expression_evaluation_task is deprecated. "
    "Use core.tasks.expression_evaluation_task instead. "
    "This shim will be removed in FilterMate v4.0.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from core.tasks.expression_evaluation_task import (
    ExpressionEvaluationSignals,
    ExpressionEvaluationTask,
    ExpressionEvaluationManager,
    get_expression_manager
)

__all__ = [
    'ExpressionEvaluationSignals',
    'ExpressionEvaluationTask',
    'ExpressionEvaluationManager',
    'get_expression_manager'
]
