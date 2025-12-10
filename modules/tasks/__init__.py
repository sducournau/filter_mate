"""
Tasks Module

Refactored from appTasks.py during Phase 3 (Dec 2025).

This module provides backwards-compatible imports for all task-related classes and utilities.
The original appTasks.py file remains unchanged during the initial refactoring phase.

Future phases will decompose appTasks.py into:
- task_utils.py: Common utility functions (spatialite_connect, etc.) ✅ Created
- geometry_cache.py: SourceGeometryCache class ✅ Created  
- filter_task.py: FilterEngineTask class (4165 lines) ⏳ Planned
- layer_management_task.py: LayersManagementEngineTask class (1079 lines) ⏳ Planned

Current Status: Phase 3a complete - utilities and cache extracted
"""

# Re-export from original appTasks.py for backwards compatibility
from ..appTasks import (
    FilterEngineTask,
    LayersManagementEngineTask,
    MESSAGE_TASKS_CATEGORIES
)

# Import from new modules
from .task_utils import (
    spatialite_connect,
    sqlite_execute_with_retry,
    get_best_metric_crs,
    should_reproject_layer,
    SQLITE_TIMEOUT,
    SQLITE_MAX_RETRIES,
    SQLITE_RETRY_DELAY,
    MESSAGE_TASKS_CATEGORIES as MESSAGE_CATEGORIES_UTILS
)

from .geometry_cache import SourceGeometryCache

__all__ = [
    # Main task classes (from appTasks.py)
    'FilterEngineTask',
    'LayersManagementEngineTask',
    'MESSAGE_TASKS_CATEGORIES',
    
    # Utilities (from task_utils.py)
    'spatialite_connect',
    'sqlite_execute_with_retry',
    'get_best_metric_crs',
    'should_reproject_layer',
    'SQLITE_TIMEOUT',
    'SQLITE_MAX_RETRIES',
    'SQLITE_RETRY_DELAY',
    
    # Cache (from geometry_cache.py)
    'SourceGeometryCache',
]

# Version info
__version__ = '2.3.0-alpha'
__phase__ = '3a'
__status__ = 'Utilities extracted, full decomposition pending'
