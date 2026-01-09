"""
FilterMate UI Configuration.

UI configuration utilities (display profiles, spacers, etc.).

This module provides compatibility imports for UI configuration,
replacing the old ui.config imports.
"""

# Re-export from legacy module for now (will be migrated later)
try:
    from ui.config import (
        UIConfig,
        DisplayProfile,
    )
except ImportError:
    # Fallback if modules is removed
    class DisplayProfile:
        NORMAL = "normal"
        COMPACT = "compact"
        EXPANDED = "expanded"
    
    class UIConfig:
        display_profile = DisplayProfile.NORMAL

__all__ = [
    'UIConfig',
    'DisplayProfile',
]
