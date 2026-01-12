# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/icon_utils

Migrated to ui/styles/icon_manager.py
This file provides backward compatibility only.

Migration: EPIC-1 Phase E6 - Strangler Fig Pattern
"""
import warnings
import logging

logger = logging.getLogger(__name__)

warnings.warn(
    "modules.icon_utils is deprecated. Use ui.styles.icon_manager instead.",
    DeprecationWarning,
    stacklevel=2
)

logger.info(
    "SHIM: modules.icon_utils redirecting to ui.styles.icon_manager"
)

# Re-export IconManager as IconThemeManager for backward compatibility
try:
    from ..ui.styles.icon_manager import IconManager
    
    # Create a compatibility class that wraps IconManager
    class IconThemeManager:
        """
        Compatibility wrapper for the old IconThemeManager class.
        
        Provides static methods that delegate to IconManager.
        For full functionality, use IconManager directly.
        """
        _instance = None
        _current_theme = 'default'
        
        @classmethod
        def instance(cls):
            """Get or create singleton instance."""
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance
        
        @classmethod
        def set_theme(cls, theme: str) -> None:
            """Set the current theme."""
            cls._current_theme = theme
            logger.debug(f"IconThemeManager: theme set to {theme}")
        
        @classmethod
        def get_theme(cls) -> str:
            """Get the current theme."""
            return cls._current_theme
        
        @classmethod
        def is_dark_mode(cls) -> bool:
            """Check if dark mode is active."""
            return cls._current_theme == 'dark'
    
except ImportError as e:
    logger.warning(f"Could not import IconManager: {e}")
    
    # Stub class for compatibility
    class IconThemeManager:
        """Stub IconThemeManager when ui.styles.icon_manager is unavailable."""
        _current_theme = 'default'
        
        @classmethod
        def instance(cls):
            return cls()
        
        @classmethod
        def set_theme(cls, theme: str) -> None:
            cls._current_theme = theme
        
        @classmethod
        def get_theme(cls) -> str:
            return cls._current_theme
        
        @classmethod
        def is_dark_mode(cls) -> bool:
            return cls._current_theme == 'dark'


__all__ = ['IconThemeManager']
