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

from .base_styler import StylerBase
from .theme_manager import ThemeManager
from .icon_manager import IconManager
from .button_styler import ButtonStyler
from .style_loader import StyleLoader
from .theme_watcher import QGISThemeWatcher

__all__ = [
    'StylerBase',
    'ThemeManager',
    'IconManager',
    'ButtonStyler',
    'StyleLoader',
    'QGISThemeWatcher',
]
