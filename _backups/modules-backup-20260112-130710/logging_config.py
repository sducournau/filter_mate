# -*- coding: utf-8 -*-
"""
FilterMate Modules Logging Configuration.

Compatibility shim that re-exports logging utilities from infrastructure.logging.
This module exists for backward compatibility with code that imports from modules.logging_config.

Usage:
    from modules.logging_config import setup_logger, safe_log
    
    logger = setup_logger('FilterMate.MyModule', 'path/to/log.log')
    safe_log(logger, logging.ERROR, "Error message", exc_info=True)
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# Try relative import first (when used as part of filter_mate package)
try:
    from ..infrastructure.logging import (
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
except ImportError:
    # Fallback: provide implementations directly
    class SafeStreamHandler(logging.StreamHandler):
        """StreamHandler that gracefully handles closed or None streams."""
        
        def emit(self, record):
            try:
                if self.stream is None:
                    return
                super().emit(record)
            except (AttributeError, ValueError, OSError):
                pass

    def setup_logger(name: str, log_file: str = None, level=logging.INFO):
        """Setup logger with file rotation."""
        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False
        
        if logger.handlers:
            return logger
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        if log_file:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                try:
                    os.makedirs(log_dir, exist_ok=True)
                except OSError:
                    log_file = os.path.basename(log_file)
            
            try:
                file_handler = RotatingFileHandler(
                    log_file, maxBytes=10*1024*1024, backupCount=5,
                    encoding='utf-8', delay=True
                )
                file_handler.setFormatter(formatter)
                file_handler.setLevel(level)
                logger.addHandler(file_handler)
            except (OSError, PermissionError):
                pass
        
        console_handler = SafeStreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.WARNING)
        logger.addHandler(console_handler)
        
        return logger

    def get_logger(name: str):
        """Get existing logger or create a default one."""
        logger = logging.getLogger(name)
        if not logger.handlers:
            logger = setup_logger(name)
        return logger

    def set_log_level(logger_name: str, level: int):
        """Change log level for a specific logger."""
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)

    def safe_log(logger, level: int, message: str, exc_info: bool = False):
        """Safely log a message, catching any exceptions."""
        try:
            logger.log(level, message, exc_info=exc_info)
        except (OSError, ValueError, AttributeError):
            try:
                print(f"[FilterMate] {message}")
            except (OSError, UnicodeError):
                pass

    def get_app_logger():
        return get_logger('FilterMate.App')

    def get_tasks_logger():
        return get_logger('FilterMate.Tasks')

    def get_utils_logger():
        return get_logger('FilterMate.Utils')

    def get_ui_logger():
        return get_logger('FilterMate.UI')


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
