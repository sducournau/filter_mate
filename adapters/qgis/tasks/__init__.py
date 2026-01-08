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
]
