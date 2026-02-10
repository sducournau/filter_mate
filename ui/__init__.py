"""
FilterMate UI Module.

User interface components, widgets, and controllers.

Submodules:
    - controllers: UI controllers (Filtering, Exploring, Exporting)
    - dialogs: Dialog windows
    - layout: Layout managers (MIG-060+)
    - styles: Styling utilities
    - widgets: Custom widgets
    - orchestrator: DockWidget orchestrator (MIG-087)
"""

# Layout managers (Phase 6 - MIG-060+)
from . import layout  # noqa: F401
from . import config  # noqa: F401

# Orchestrator (Phase 6 - MIG-087)
from .orchestrator import DockWidgetOrchestrator, create_orchestrator  # noqa: F401

__all__ = [
    'layout',
    'config',
    'DockWidgetOrchestrator',
    'create_orchestrator',
]
