"""
Core Tasks Package

Domain-specific task implementations for QGIS operations.
These tasks implement business logic using QGIS API and domain models.

This is part of the Hexagonal Architecture - Application Layer (core/).

Exported Symbols:
    - FilterEngineTask: Main filtering task (migrated from modules/tasks/)
    - ExpressionEvaluationSignals: QObject for thread-safe signals
    - ExpressionEvaluationTask: QgsTask for async expression evaluation
    - ExpressionEvaluationManager: Singleton manager for expression tasks
    - get_expression_manager: Factory function for manager singleton
    - LayersManagementEngineTask: QgsTask for layer tracking management

Architecture:
    core/tasks/ → Application layer (business logic with QGIS)
    infrastructure/ → External adapters (database, cache, logging)
    adapters/ → Anti-corruption layer (legacy compatibility)
    ui/ → User interface layer

Migration History:
    - v3.0: Created core/tasks/ package for domain-specific tasks
    - v3.0: Migrated expression_evaluation_task.py from modules/tasks/ (EPIC-1)
    - v3.0: Migrated layer_management_task.py from modules/tasks/ (EPIC-1)
    - v4.0: Migrated filter_task.py from modules/tasks/ (EPIC-1 Final)
"""

# Main filter task (EPIC-1 migration - January 2026)
from .filter_task import FilterEngineTask

from .expression_evaluation_task import (
    ExpressionEvaluationSignals,
    ExpressionEvaluationTask,
    ExpressionEvaluationManager,
    get_expression_manager
)

from .layer_management_task import LayersManagementEngineTask

# E6: Task completion handler functions
from .task_completion_handler import (
    display_warning_messages,
    should_skip_subset_application,
    apply_pending_subset_requests,
    schedule_canvas_refresh,
    cleanup_memory_layer
)

__all__ = [
    # Main filter task
    'FilterEngineTask',
    # Expression evaluation
    'ExpressionEvaluationSignals',
    'ExpressionEvaluationTask',
    'ExpressionEvaluationManager',
    'get_expression_manager',
    # Layer management
    'LayersManagementEngineTask',
    # E6: Task completion handler
    'display_warning_messages',
    'should_skip_subset_application',
    'apply_pending_subset_requests',
    'schedule_canvas_refresh',
    'cleanup_memory_layer'
]
