"""
FilterMate Infrastructure Logging.

Logging configuration and utilities with file rotation and safe stream handling.

This module provides centralized logging for FilterMate with:
- File rotation (10 MB max, 5 backups)
- Safe stream handling for QGIS shutdown
- Pre-configured loggers for common modules

Usage:
    from infrastructure.logging import get_logger, setup_logger, get_app_logger
    
    logger = get_logger('FilterMate.MyModule')
    logger.info("Something happened")
"""

import logging
from logging.handlers import RotatingFileHandler
import os
import sys


class SafeStreamHandler(logging.StreamHandler):
    """
    StreamHandler that gracefully handles closed or None streams.
    
    This prevents AttributeError when QGIS shuts down while tasks are still
    logging, or when the stream becomes None during handler cleanup.
    """
    
    def emit(self, record):
        """Emit a record, with safe handling of None or closed streams."""
        try:
            if self.stream is None:
                return
            super().emit(record)
        except (AttributeError, ValueError, OSError):
            pass


def setup_logger(name: str, log_file: str = None, level=logging.INFO):
    """
    Setup logger with file rotation.
    
    Args:
        name: Logger name (e.g., 'FilterMate.Utils')
        log_file: Path to log file (optional)
        level: Logging level (default: logging.INFO)
    
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False
    
    if logger.handlers:
        return logger
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler if log_file provided
    if log_file:
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except OSError:
                log_file = os.path.basename(log_file)
        
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10*1024*1024,  # 10 MB
                backupCount=5,
                encoding='utf-8',
                delay=True
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            logger.addHandler(file_handler)
        except (OSError, PermissionError):
            pass
    
    # Console handler with SafeStreamHandler
    console_handler = SafeStreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name: str):
    """
    Get existing logger or create a default one.
    
    Args:
        name: Logger name
    
    Returns:
        logging.Logger: Logger instance
    """
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
    """
    Safely log a message, catching any exceptions.
    
    Useful in exception handlers or during shutdown.
    """
    try:
        logger.log(level, message, exc_info=exc_info)
    except (OSError, ValueError, AttributeError):
        try:
            print(f"[FilterMate] {message}")
        except (OSError, UnicodeError):
            pass


# Root logger configuration
_root_logger_configured = False


def _ensure_root_logger_configured():
    """Ensure the root FilterMate logger has SafeStreamHandler configured."""
    global _root_logger_configured
    if _root_logger_configured:
        return
    
    root_logger = logging.getLogger('FilterMate')
    has_safe_handler = any(isinstance(h, SafeStreamHandler) for h in root_logger.handlers)
    
    if not has_safe_handler:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler = SafeStreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.WARNING)
        root_logger.addHandler(console_handler)
    
    _root_logger_configured = True


def get_app_logger():
    """Get logger for main application."""
    _ensure_root_logger_configured()
    return get_logger('FilterMate.App')


def get_tasks_logger():
    """Get logger for task execution."""
    _ensure_root_logger_configured()
    return get_logger('FilterMate.Tasks')


def get_utils_logger():
    """Get logger for utilities."""
    _ensure_root_logger_configured()
    return get_logger('FilterMate.Utils')


def get_ui_logger():
    """Get logger for UI components."""
    _ensure_root_logger_configured()
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
