"""
FilterMate UI Elements.

UI element utilities (spacers, layouts, etc.).

This module provides compatibility imports for UI elements,
replacing the old ui.elements imports.
"""

# Re-export from legacy module for now (will be migrated later)
try:
    from ui.elements import (  # noqa: F401
        get_spacer_size,
        LAYOUTS,
    )
except ImportError:
    # Fallback if modules is removed
    def get_spacer_size(size_name: str = "medium"):
        sizes = {"small": 5, "medium": 10, "large": 20}
        return sizes.get(size_name, 10)

    LAYOUTS = {}

__all__ = [
    'get_spacer_size',
    'LAYOUTS',
]
