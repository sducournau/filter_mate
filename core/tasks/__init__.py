"""
Core Tasks Package

Domain-specific task implementations for QGIS operations.
These tasks implement business logic using QGIS API and domain models.

This is part of the Hexagonal Architecture - Application Layer (core/).

Exported Symbols:
    - ExpressionEvaluationSignals: QObject for thread-safe signals
    - ExpressionEvaluationTask: QgsTask for async expression evaluation
    - ExpressionEvaluationManager: Singleton manager for expression tasks
    - get_expression_manager: Factory function for manager singleton

Architecture:
    core/tasks/ → Application layer (business logic with QGIS)
    infrastructure/ → External adapters (database, cache, logging)
    adapters/ → Anti-corruption layer (legacy compatibility)
    ui/ → User interface layer

Migration History:
    - v3.0: Created core/tasks/ package for domain-specific tasks
    - v3.0: Migrated expression_evaluation_task.py from modules/tasks/ (EPIC-1)
"""

from .expression_evaluation_task import (
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
