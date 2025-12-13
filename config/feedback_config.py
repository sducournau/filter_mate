"""
FilterMate Feedback Configuration

Controls the verbosity level of user feedback messages to reduce notification fatigue.
Users can choose between minimal, normal, and verbose feedback modes.

Usage:
    from config.feedback_config import should_show_message, get_feedback_level
    
    if should_show_message('filter_count'):
        iface.messageBar().pushInfo("FilterMate", message)
"""

from enum import Enum
from typing import Dict, Any


class FeedbackLevel(Enum):
    """Feedback verbosity levels"""
    MINIMAL = "minimal"  # Only critical errors and important successes
    NORMAL = "normal"    # Balanced (default)
    VERBOSE = "verbose"  # Show all messages (debug mode)


# Current feedback level (can be configured via UI or config.json)
_current_level = FeedbackLevel.NORMAL


# Message category definitions
MESSAGE_CATEGORIES = {
    # Operation results
    'filter_count': {
        'description': 'Show feature count after filtering',
        'minimal': False,
        'normal': True,
        'verbose': True
    },
    'undo_redo': {
        'description': 'Show undo/redo confirmation messages',
        'minimal': False,
        'normal': False,  # UI feedback is sufficient
        'verbose': True
    },
    'export_success': {
        'description': 'Show export completion messages',
        'minimal': True,
        'normal': True,
        'verbose': True
    },
    
    # Backend information
    'backend_info': {
        'description': 'Show which backend is being used',
        'minimal': False,
        'normal': False,  # Show once at startup only
        'verbose': True
    },
    'backend_startup': {
        'description': 'Show backend info at plugin startup',
        'minimal': False,
        'normal': True,
        'verbose': True
    },
    
    # Configuration changes
    'config_changes': {
        'description': 'Show UI configuration change confirmations',
        'minimal': False,
        'normal': False,  # Changes visible in UI
        'verbose': True
    },
    
    # Performance warnings
    'performance_warning': {
        'description': 'Warn about large datasets without PostgreSQL',
        'minimal': True,  # Always show performance warnings
        'normal': True,
        'verbose': True
    },
    
    # Progress messages
    'progress_info': {
        'description': 'Show progress during long operations',
        'minimal': False,
        'normal': True,
        'verbose': True
    },
    
    # History status
    'history_status': {
        'description': 'Show "no more history" warnings',
        'minimal': False,
        'normal': False,  # Buttons already disabled
        'verbose': True
    },
    
    # Errors (always show)
    'error_critical': {
        'description': 'Critical errors (connection, corruption)',
        'minimal': True,
        'normal': True,
        'verbose': True
    },
    'error_warning': {
        'description': 'Non-critical warnings',
        'minimal': False,
        'normal': True,
        'verbose': True
    }
}


def get_feedback_level() -> FeedbackLevel:
    """
    Get current feedback verbosity level.
    
    Returns:
        FeedbackLevel: Current level (MINIMAL, NORMAL, or VERBOSE)
    """
    return _current_level


def set_feedback_level(level: FeedbackLevel):
    """
    Set feedback verbosity level.
    
    Args:
        level (FeedbackLevel): New feedback level
    """
    global _current_level
    _current_level = level


def set_feedback_level_from_string(level_str: str):
    """
    Set feedback level from string value.
    
    Args:
        level_str (str): Level name ('minimal', 'normal', 'verbose')
    
    Raises:
        ValueError: If level_str is not a valid level
    """
    try:
        level = FeedbackLevel(level_str.lower())
        set_feedback_level(level)
    except ValueError:
        raise ValueError(f"Invalid feedback level: {level_str}. Must be one of: minimal, normal, verbose")


def should_show_message(category: str) -> bool:
    """
    Check if a message should be shown based on current feedback level.
    
    Args:
        category (str): Message category (e.g., 'filter_count', 'undo_redo')
    
    Returns:
        bool: True if message should be shown, False otherwise
    
    Example:
        >>> if should_show_message('filter_count'):
        ...     iface.messageBar().pushInfo("FilterMate", "1,234 features visible")
    """
    if category not in MESSAGE_CATEGORIES:
        # Unknown categories default to showing in normal/verbose
        return _current_level in (FeedbackLevel.NORMAL, FeedbackLevel.VERBOSE)
    
    category_config = MESSAGE_CATEGORIES[category]
    level_key = _current_level.value
    
    return category_config.get(level_key, True)


def get_feedback_config_summary() -> Dict[str, Any]:
    """
    Get summary of current feedback configuration.
    
    Returns:
        dict: Configuration summary with level and enabled categories
    """
    current_level_str = _current_level.value
    
    enabled_categories = []
    disabled_categories = []
    
    for category, config in MESSAGE_CATEGORIES.items():
        if config.get(current_level_str, False):
            enabled_categories.append(category)
        else:
            disabled_categories.append(category)
    
    return {
        'level': current_level_str,
        'enabled_categories': enabled_categories,
        'disabled_categories': disabled_categories,
        'total_categories': len(MESSAGE_CATEGORIES)
    }


# Convenience constants for common checks
SHOW_FILTER_COUNTS = lambda: should_show_message('filter_count')
SHOW_UNDO_REDO = lambda: should_show_message('undo_redo')
SHOW_BACKEND_INFO = lambda: should_show_message('backend_info')
SHOW_CONFIG_CHANGES = lambda: should_show_message('config_changes')
SHOW_HISTORY_STATUS = lambda: should_show_message('history_status')
