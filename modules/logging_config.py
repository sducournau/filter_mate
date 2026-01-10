"""
FilterMate Modules Logging Configuration.

Compatibility shim that re-exports logging utilities from infrastructure.logging.
This module exists for backward compatibility with code that imports from modules.logging_config.

Usage:
    from modules.logging_config import setup_logger, safe_log
    
    logger = setup_logger('FilterMate.MyModule', 'path/to/log.log')
    safe_log(logger, logging.ERROR, "Error message", exc_info=True)
"""

# Re-export from infrastructure.logging for backward compatibility
from infrastructure.logging import (
    SafeStreamHandler,
    setup_logger,
    get_logger,
    set_log_level,
    safe_log,
    get_app_logger,
    get_tasks_logger,
    get_utils_logger,
    get_ui_logger,
)

__all__ = [
    'SafeStreamHandler',
    'setup_logger',
    'get_logger',
    'set_log_level',
    'safe_log',
    'get_app_logger',
    'get_tasks_logger',
    'get_utils_logger',
    'get_ui_logger',
]
