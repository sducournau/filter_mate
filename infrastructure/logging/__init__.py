"""
FilterMate Infrastructure Logging.

Logging configuration and utilities with file rotation and safe stream handling.

This module provides centralized logging for FilterMate with:
- File rotation (10 MB max, 5 backups)
- Safe stream handling for QGIS shutdown
- Pre-configured loggers for common modules
- Automatic file logging to logs/filtermate.log

Usage:
    from ...infrastructure.logging import get_logger, setup_logger, get_app_logger  # noqa: F401
    logger = get_logger('FilterMate.MyModule')
    logger.info("Something happened")
"""

import logging  # noqa: F401
from logging.handlers import RotatingFileHandler  # noqa: F401
import os  # noqa: F401
import sys  # noqa: F401
from datetime import datetime  # noqa: F401

# Determine log file path (relative to plugin directory)
_PLUGIN_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOG_DIR = os.path.join(_PLUGIN_DIR, 'logs')
_LOG_FILE = os.path.join(_LOG_DIR, 'filtermate.log')

# Ensure logs directory exists
try:
    os.makedirs(_LOG_DIR, exist_ok=True)
except OSError:
    _LOG_FILE = None  # Disable file logging if directory can't be created


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
                maxBytes=10 * 1024 * 1024,  # 10 MB
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
            pass  # block was empty
        except (OSError, UnicodeError):
            pass


# Root logger configuration
_root_logger_configured = False
_file_handler = None  # Global file handler reference


def _ensure_root_logger_configured():
    """Ensure the root FilterMate logger has SafeStreamHandler and FileHandler configured."""
    global _root_logger_configured, _file_handler
    if _root_logger_configured:
        return

    root_logger = logging.getLogger('FilterMate')
    root_logger.setLevel(logging.DEBUG)  # Capture all levels, handlers will filter

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Console handler - WARNING and above only
    has_safe_handler = any(isinstance(h, SafeStreamHandler) for h in root_logger.handlers)
    if not has_safe_handler:
        console_handler = SafeStreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.WARNING)
        root_logger.addHandler(console_handler)

    # File handler - INFO and above (captures more detail)
    has_file_handler = any(isinstance(h, RotatingFileHandler) for h in root_logger.handlers)
    if not has_file_handler and _LOG_FILE:
        try:
            _file_handler = RotatingFileHandler(
                _LOG_FILE,
                maxBytes=10 * 1024 * 1024,  # 10 MB
                backupCount=5,
                encoding='utf-8',
                delay=True
            )
            _file_handler.setFormatter(formatter)
            _file_handler.setLevel(logging.INFO)  # INFO and above to file
            root_logger.addHandler(_file_handler)
        except (OSError, PermissionError):
            # Silently fail if file can't be created
            pass

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


def get_log_file_path():
    """Get the path to the current log file."""
    return _LOG_FILE


def flush_logs():
    """Flush all log handlers to ensure logs are written to file."""
    if _file_handler:
        try:
            _file_handler.flush()
        except (OSError, ValueError):
            pass


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
    'get_log_file_path',
    'flush_logs',
]
