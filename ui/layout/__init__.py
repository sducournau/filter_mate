"""
FilterMate Layout Module.

Layout managers extracted from filter_mate_dockwidget.py.
Part of Phase 6 God Class refactoring (MIG-060 → MIG-089).

This module contains managers responsible for:
- Splitter configuration and behavior
- Widget dimension management
- Layout spacing and margins
- Action bar positioning

Example:
    from ui.layout import SplitterManager, DimensionsManager
    
    splitter_mgr = SplitterManager(dockwidget)
    splitter_mgr.setup()
"""

from .base_manager import LayoutManagerBase
from .splitter_manager import SplitterManager
from .dimensions_manager import DimensionsManager
from .spacing_manager import SpacingManager
from .action_bar_manager import ActionBarManager

__all__ = [
    'LayoutManagerBase',
    'SplitterManager',
    'DimensionsManager',
    'SpacingManager',
    'ActionBarManager',
]
