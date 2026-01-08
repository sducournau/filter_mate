# -*- coding: utf-8 -*-
"""
FilterMate QGIS Tasks module.

Phase 4 Task Refactoring - ARCH-046/047

Provides focused, single-responsibility task classes
for async operations in QGIS.

Task Categories:
- BaseTask: Abstract base for all tasks
- FilterTask: Layer filtering operations
- SpatialTask: Spatial filter operations
- ExportTask: Data export operations
- LayerTask: Layer management operations
- MultiStepTask: Multi-step progressive filtering
- ProgressHandler: Centralized progress reporting

Migration from modules/appTasks.py:
    OLD: from modules.appTasks import FilterEngineTask
    NEW: from adapters.qgis.tasks import FilterTask
"""

from .base_task import (
    BaseFilterMateTask,
    TaskResult,
    TaskStatus,
)

from .filter_task import (
    FilterTask,
    ClearFilterTask,
)

from .spatial_task import (
    SpatialFilterTask,
    BufferFilterTask,
)

from .export_task import (
    ExportTask,
    BatchExportTask,
)

from .layer_task import (
    GatherLayerInfoTask,
    ValidateExpressionsTask,
    CreateSpatialIndexTask,
)

from .multi_step_task import (
    MultiStepFilterTask,
)

from .progress_handler import (
    ProgressHandler,
    ProgressAggregator,
    ProgressEvent,
    ProgressPhase,
)

__all__ = [
    # Base
    'BaseFilterMateTask',
    'TaskResult',
    'TaskStatus',
    # Filter
    'FilterTask',
    'ClearFilterTask',
    # Spatial
    'SpatialFilterTask',
    'BufferFilterTask',
    # Export
    'ExportTask',
    'BatchExportTask',
    # Layer
    'GatherLayerInfoTask',
    'ValidateExpressionsTask',
    'CreateSpatialIndexTask',
    # Multi-step (MIG-023)
    'MultiStepFilterTask',
    # Progress (MIG-023)
    'ProgressHandler',
    'ProgressAggregator',
    'ProgressEvent',
    'ProgressPhase',
]
