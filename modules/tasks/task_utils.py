# -*- coding: utf-8 -*-
"""
Task Utilities - LEGACY SHIM

⚠️ DEPRECATED: This module has been migrated to infrastructure/utils/task_utils.py (EPIC-1)

MIGRATION GUIDE:
- OLD: from modules.tasks.task_utils import spatialite_connect
- NEW: from infrastructure.utils import spatialite_connect

All functionality is now available from:
    from infrastructure.utils import (
        spatialite_connect,
        safe_spatialite_connect,
        sqlite_execute_with_retry,
        ensure_db_directory_exists,
        get_best_metric_crs,
        should_reproject_layer,
        needs_metric_conversion
    )

This shim provides backward compatibility but will be removed in v3.1.
"""

import warnings

warnings.warn(
    "modules.tasks.task_utils is deprecated. "
    "Use 'from infrastructure.utils import ...' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from infrastructure
from infrastructure.utils import (
    spatialite_connect,
    safe_spatialite_connect,
    sqlite_execute_with_retry,
    ensure_db_directory_exists,
    get_best_metric_crs,
    should_reproject_layer,
    needs_metric_conversion,
    SQLITE_TIMEOUT,
    SQLITE_MAX_RETRIES,
    SQLITE_RETRY_DELAY,
    SQLITE_MAX_RETRY_TIME,
    MESSAGE_TASKS_CATEGORIES
)

__all__ = [
    'spatialite_connect',
    'safe_spatialite_connect',
    'sqlite_execute_with_retry',
    'ensure_db_directory_exists',
    'get_best_metric_crs',
    'should_reproject_layer',
    'needs_metric_conversion',
    'SQLITE_TIMEOUT',
    'SQLITE_MAX_RETRIES',
    'SQLITE_RETRY_DELAY',
    'SQLITE_MAX_RETRY_TIME',
    'MESSAGE_TASKS_CATEGORIES'
]
