# -*- coding: utf-8 -*-
"""
Spatialite Support for FilterMate.

Re-exports Spatialite-related utilities from infrastructure.utils.task_utils.

This module provides backward compatibility for imports from
infrastructure.database.spatialite_support.

Author: FilterMate Team
Date: January 2026
"""

# Re-export from task_utils
from ..utils.task_utils import (
    spatialite_connect,
    safe_spatialite_connect,
    sqlite_execute_with_retry,
    ensure_db_directory_exists,
    SQLITE_TIMEOUT,
    SQLITE_MAX_RETRIES,
    SQLITE_RETRY_DELAY,
    SQLITE_MAX_RETRY_TIME,
    MESSAGE_TASKS_CATEGORIES,
)

__all__ = [
    'spatialite_connect',
    'safe_spatialite_connect',
    'sqlite_execute_with_retry',
    'ensure_db_directory_exists',
    'SQLITE_TIMEOUT',
    'SQLITE_MAX_RETRIES',
    'SQLITE_RETRY_DELAY',
    'SQLITE_MAX_RETRY_TIME',
    'MESSAGE_TASKS_CATEGORIES',
]
