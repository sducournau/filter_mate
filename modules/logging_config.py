"""
FilterMate Logging Configuration

This module provides centralized logging configuration with rotation
and appropriate formatting for the FilterMate plugin.

Usage:
    from modules.logging_config import setup_logger
    
    logger = setup_logger('FilterMate.MyModule', 'path/to/logfile.log')
    logger.info("Something happened")
    logger.warning("Something concerning happened")
    logger.error("Something bad happened")
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
        """
        Emit a record, with safe handling of None or closed streams.
        """
        try:
            if self.stream is None:
                # Stream has been closed or not initialized, skip emission
                return
            super().emit(record)
        except (AttributeError, ValueError, OSError):
            # Stream closed, invalid, or other IO error - silently ignore
            # This is acceptable for console output during shutdown
            pass


def setup_logger(name, log_file, level=logging.INFO):
    """
    Setup logger with file rotation.
    
    Args:
        name (str): Logger name (e.g., 'FilterMate.Utils')
        log_file (str): Path to log file
        level (int): Logging level (default: logging.INFO)
    
    Returns:
        logging.Logger: Configured logger instance
    
    Example:
        >>> logger = setup_logger('FilterMate.Tasks', 'logs/tasks.log')
        >>> logger.info("Task started")
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger
    
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError as e:
            print(f"Warning: Could not create log directory {log_dir}: {e}")
            # Fallback to file in current directory
            log_file = os.path.basename(log_file)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation (10 MB max, 5 backup files)
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
    except (OSError, PermissionError) as e:
        print(f"Warning: Could not create log file {log_file}: {e}")
    
    # Console handler for development (only WARNING and above)
    # Use SafeStreamHandler to prevent crashes during QGIS shutdown
    console_handler = SafeStreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)
    logger.addHandler(console_handler)
    
    return logger


def get_logger(name):
    """
    Get existing logger or create a default one.
    
    Args:
        name (str): Logger name
    
    Returns:
        logging.Logger: Logger instance
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        # Create default logger if not configured
        logger = setup_logger(name, f'filtermate_{name.split(".")[-1].lower()}.log')
    return logger


def set_log_level(logger_name, level):
    """
    Change log level for a specific logger.
    
    Args:
        logger_name (str): Name of the logger
        level (int): New logging level (logging.DEBUG, INFO, WARNING, ERROR)
    
    Example:
        >>> set_log_level('FilterMate.Tasks', logging.DEBUG)
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)


def safe_log(logger, level, message, exc_info=False):
    """
    Safely log a message, catching any exceptions that might occur.
    
    This is useful in exception handlers or during shutdown when logging
    infrastructure might be partially torn down.
    
    Args:
        logger (logging.Logger): Logger instance
        level (int): Logging level (logging.DEBUG, INFO, WARNING, ERROR, CRITICAL)
        message (str): Message to log
        exc_info (bool): Include exception information if True
    
    Example:
        >>> try:
        >>>     risky_operation()
        >>> except Exception as e:
        >>>     safe_log(logger, logging.ERROR, f"Operation failed: {e}", exc_info=True)
    """
    try:
        logger.log(level, message, exc_info=exc_info)
    except (OSError, ValueError, AttributeError) as e:
        # If logging fails completely, fall back to print
        # This ensures we don't lose critical error information
        try:
            print(f"[FilterMate] {message}")
        except (OSError, UnicodeError):
            pass  # Absolute last resort - do nothing if even print fails
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler):
            handler.setLevel(level)


# Pre-configured loggers for common modules
# Root logger is configured once to ensure all FilterMate.* loggers get SafeStreamHandler
_root_logger_configured = False


def _ensure_root_logger_configured():
    """
    Ensure the root FilterMate logger has SafeStreamHandler configured.
    
    This is called automatically by all get_*_logger() functions to ensure
    that child loggers inherit the safe console handler. This prevents
    "--- Logging error ---" messages during QGIS shutdown.
    """
    global _root_logger_configured
    if _root_logger_configured:
        return
    
    root_logger = logging.getLogger('FilterMate')
    
    # Check if a SafeStreamHandler is already attached
    has_safe_handler = any(
        isinstance(h, SafeStreamHandler) for h in root_logger.handlers
    )
    
    if not has_safe_handler:
        # Add SafeStreamHandler to root FilterMate logger
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
    """Get logger for main application"""
    _ensure_root_logger_configured()
    return get_logger('FilterMate.App')


def get_tasks_logger():
    """Get logger for task execution"""
    _ensure_root_logger_configured()
    return get_logger('FilterMate.Tasks')


def get_utils_logger():
    """Get logger for utilities"""
    _ensure_root_logger_configured()
    return get_logger('FilterMate.Utils')


def get_ui_logger():
    """Get logger for UI components"""
    _ensure_root_logger_configured()
    return get_logger('FilterMate.UI')
