"""
FilterMate UI Styles.

Theme and styling utilities for dark mode and custom themes.

Story: MIG-065, MIG-066, MIG-067, MIG-068, MIG-090
Phase: 6 - God Class DockWidget Migration

Classes:
    StylerBase: Abstract base class for all style managers
    ThemeManager: Centralized theme management with QGIS sync
    IconManager: Theme-aware icon management with caching
    ButtonStyler: Button styling and state management
    StyleLoader: Stylesheet loader with theme support (migrated from modules/)
    QGISThemeWatcher: QGIS theme change watcher (migrated from modules/)
"""

from .base_styler import StylerBase  # noqa: F401
from .theme_manager import ThemeManager  # noqa: F401
from .icon_manager import IconManager  # noqa: F401
from .button_styler import ButtonStyler  # noqa: F401
from .style_loader import StyleLoader  # noqa: F401
from .theme_watcher import QGISThemeWatcher  # noqa: F401

__all__ = [
    'StylerBase',
    'ThemeManager',
    'IconManager',
    'ButtonStyler',
    'StyleLoader',
    'QGISThemeWatcher',
]
