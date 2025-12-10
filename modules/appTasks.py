"""
DEPRECATED: appTasks.py - Backwards Compatibility Shim

This file now only provides backwards-compatible imports.
All actual implementations have been extracted to modules/tasks/ during Phase 3 refactoring.

MIGRATION PATH:
    OLD: from modules.appTasks import FilterEngineTask, LayersManagementEngineTask
    NEW: from modules.tasks import FilterEngineTask, LayersManagementEngineTask

Extraction History:
- Phase 3a (10 Dec 2025): Extracted utilities and cache to task_utils.py, geometry_cache.py
- Phase 3b (10 Dec 2025): Extracted LayersManagementEngineTask to layer_management_task.py  
- Phase 3c (10 Dec 2025): Extracted FilterEngineTask to filter_task.py

All code now lives in modules/tasks/*.py.
This file will be removed in a future version.
"""

import warnings

# Show deprecation warning on first import
warnings.warn(
    "Importing from modules.appTasks is deprecated. "
    "Use 'from modules.tasks import FilterEngineTask, LayersManagementEngineTask' instead. "
    "appTasks.py will be removed in v3.0.0",
    DeprecationWarning,
    stacklevel=2
)

# Re-export everything from modules.tasks for backwards compatibility
from .tasks import (
    FilterEngineTask,
    LayersManagementEngineTask,
    SourceGeometryCache,
    spatialite_connect,
    sqlite_execute_with_retry,
    get_best_metric_crs,
    should_reproject_layer,
    SQLITE_TIMEOUT,
    SQLITE_MAX_RETRIES,
    SQLITE_RETRY_DELAY,
    MESSAGE_TASKS_CATEGORIES
)

__all__ = [
    'FilterEngineTask',
    'LayersManagementEngineTask',
    'SourceGeometryCache',
    'spatialite_connect',
    'sqlite_execute_with_retry',
    'get_best_metric_crs',
    'should_reproject_layer',
    'SQLITE_TIMEOUT',
    'SQLITE_MAX_RETRIES',
    'SQLITE_RETRY_DELAY',
    'MESSAGE_TASKS_CATEGORIES',
]
