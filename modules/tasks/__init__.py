"""
Tasks Module

Refactored from appTasks.py during Phase 3 (Dec 2025).

This module provides backwards-compatible imports for all task-related classes and utilities.

Extraction Status:
- task_utils.py: Common utility functions (spatialite_connect, etc.) ✅ Phase 3a
- geometry_cache.py: SourceGeometryCache class ✅ Phase 3a
- layer_management_task.py: LayersManagementEngineTask class ✅ Phase 3b
- filter_task.py: FilterEngineTask class (4165 lines) ✅ Phase 3c

Current Status: Phase 3c complete - FilterEngineTask extracted
"""

# Re-export FilterEngineTask from new module (Phase 3c)
from .filter_task import FilterEngineTask

# Re-export LayersManagementEngineTask from new module (Phase 3b)
from .layer_management_task import LayersManagementEngineTask

# Import from new modules
from .task_utils import (
    spatialite_connect,
    sqlite_execute_with_retry,
    ensure_db_directory_exists,
    get_best_metric_crs,
    should_reproject_layer,
    SQLITE_TIMEOUT,
    SQLITE_MAX_RETRIES,
    SQLITE_RETRY_DELAY,
    SQLITE_MAX_RETRY_TIME,
    MESSAGE_TASKS_CATEGORIES
)

from .geometry_cache import SourceGeometryCache

__all__ = [
    # Main task classes
    'FilterEngineTask',              # From filter_task.py (Phase 3c - ✅)
    'LayersManagementEngineTask',    # From layer_management_task.py (Phase 3b - ✅)
    
    # Constants
    'MESSAGE_TASKS_CATEGORIES',      # From task_utils.py
    
    # Utilities (from task_utils.py - Phase 3a - ✅)
    'spatialite_connect',
    'sqlite_execute_with_retry',
    'ensure_db_directory_exists',
    'get_best_metric_crs',
    'should_reproject_layer',
    'SQLITE_TIMEOUT',
    'SQLITE_MAX_RETRIES',
    'SQLITE_RETRY_DELAY',
    'SQLITE_MAX_RETRY_TIME',
    
    # Cache (from geometry_cache.py - Phase 3a - ✅)
    'SourceGeometryCache',
]

# Version info
__version__ = '2.3.0-alpha'
__phase__ = '3c'
__status__ = 'FilterEngineTask extracted, all major tasks modularized'
