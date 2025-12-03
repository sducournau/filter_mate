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
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        print(f"Warning: Could not create log file {log_file}: {e}")
    
    # Console handler for development (only WARNING and above)
    console_handler = logging.StreamHandler()
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
