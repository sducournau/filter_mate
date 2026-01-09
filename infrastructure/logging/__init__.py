"""
FilterMate Infrastructure Logging.

Logging configuration and utilities.

This module provides compatibility imports for the logging system,
replacing the old infrastructure.logging imports.
"""

# Re-export from legacy module for now (will be migrated later)
try:
    from infrastructure.logging import (
        get_logger,
        get_app_logger,
        setup_logger,
    )
except ImportError:
    # Fallback if modules is removed
    import logging
    
    def get_logger(name: str = "FilterMate"):
        return logging.getLogger(name)
    
    def get_app_logger():
        return logging.getLogger("FilterMate")
    
    def setup_logger(name: str = "FilterMate", level=logging.INFO):
        logger = logging.getLogger(name)
        logger.setLevel(level)
        return logger

__all__ = [
    'get_logger',
    'get_app_logger', 
    'setup_logger',
]
