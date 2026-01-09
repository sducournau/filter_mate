"""
FilterMate UI Module.

User interface components, widgets, and controllers.

Submodules:
    - controllers: UI controllers (Filtering, Exploring, Exporting)
    - dialogs: Dialog windows
    - layout: Layout managers (MIG-060+)
    - styles: Styling utilities
    - widgets: Custom widgets
"""

# Layout managers (Phase 6 - MIG-060+)
from . import layout

__all__ = [
    'layout',
]
