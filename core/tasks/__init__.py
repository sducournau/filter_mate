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
    - RasterSamplingSignals: QObject for raster sampling thread-safe signals
    - RasterSamplingTask: QgsTask for async raster value sampling

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
    - v4.1: Added raster_sampling_task.py (Phase 1 Dual Panel Raster)
"""

# Main filter task (EPIC-1 migration - January 2026)
from .filter_task import FilterEngineTask  # noqa: F401

from .expression_evaluation_task import (  # noqa: F401
    ExpressionEvaluationSignals,
    ExpressionEvaluationTask,
    ExpressionEvaluationManager,
    get_expression_manager
)

from .layer_management_task import LayersManagementEngineTask  # noqa: F401

# Phase 1: Raster sampling task (Dual Panel Raster)
from .raster_sampling_task import (  # noqa: F401
    RasterSamplingSignals,
    RasterSamplingTask,
)

# E6: Task completion handler functions
from .task_completion_handler import (  # noqa: F401
    display_warning_messages,
    should_skip_subset_application,
    apply_pending_subset_requests,
    schedule_canvas_refresh,
    cleanup_memory_layer
)

# Phase 3 C1: Extracted handlers (February 2026)
from .cleanup_handler import CleanupHandler  # noqa: F401
from .export_handler import ExportHandler  # noqa: F401
from .geometry_handler import GeometryHandler  # noqa: F401

# Phase 3 C1 Pass 2: Additional extracted handlers (February 2026)
from .initialization_handler import InitializationHandler  # noqa: F401
from .source_geometry_preparer import SourceGeometryPreparer  # noqa: F401
from .subset_management_handler import SubsetManagementHandler  # noqa: F401

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
    'cleanup_memory_layer',
    # Raster sampling (Phase 1)
    'RasterSamplingSignals',
    'RasterSamplingTask',
    # Phase 3 C1: Extracted handlers
    'CleanupHandler',
    'ExportHandler',
    'GeometryHandler',
    # Phase 3 C1 Pass 2: Additional extracted handlers
    'InitializationHandler',
    'SourceGeometryPreparer',
    'SubsetManagementHandler',
]
