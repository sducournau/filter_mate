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
import tempfile


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
    
    # Normalize and validate log file path
    # Handle case when ENV_VARS is empty at module load time
    log_file = os.path.normpath(log_file) if log_file else ''
    
    # If log_file starts with './' or is relative without proper base, use safe fallback
    if not log_file or log_file.startswith('.') or not os.path.isabs(log_file):
        # Use system temp directory as safe fallback
        try:
            fallback_dir = os.path.join(tempfile.gettempdir(), 'filtermate_logs')
            os.makedirs(fallback_dir, exist_ok=True)
            log_basename = os.path.basename(log_file) if log_file else 'filtermate.log'
            log_file = os.path.join(fallback_dir, log_basename)
        except OSError:
            # Ultimate fallback: no file logging, console only
            log_file = None
    else:
        # Ensure log directory exists for absolute paths
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
            except OSError as e:
                # Fallback to temp directory
                try:
                    fallback_dir = os.path.join(tempfile.gettempdir(), 'filtermate_logs')
                    os.makedirs(fallback_dir, exist_ok=True)
                    log_file = os.path.join(fallback_dir, os.path.basename(log_file))
                except OSError:
                    log_file = None
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # File handler with rotation (10 MB max, 5 backup files)
    # Only create file handler if we have a valid log file path
    if log_file:
        try:
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10*1024*1024,  # 10 MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            logger.addHandler(file_handler)
        except (OSError, PermissionError, TypeError) as e:
            # Log file creation failed - continue with console only
            pass
    
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
def get_app_logger():
    """Get logger for main application"""
    return get_logger('FilterMate.App')


def get_tasks_logger():
    """Get logger for task execution"""
    return get_logger('FilterMate.Tasks')


def get_utils_logger():
    """Get logger for utilities"""
    return get_logger('FilterMate.Utils')


def get_ui_logger():
    """Get logger for UI components"""
    return get_logger('FilterMate.UI')
