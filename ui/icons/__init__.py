"""
FilterMate UI Icons - Compatibility Module.

Provides backwards-compatible imports for icon utilities.
The actual implementation is in ui.styles.icon_manager.

Story: COMPAT-001
Phase: 5 - Quality and Compatibility
"""

import os
import logging
from typing import Optional

from qgis.PyQt.QtGui import QIcon, QPixmap, QImage

logger = logging.getLogger(__name__)


# Import from the actual implementation
try:
    from ..styles.icon_manager import IconManager
except ImportError:
    IconManager = None  # type: ignore


# ============================================================================
# IconThemeManager - DEFINED FIRST for forward reference
# ============================================================================

class IconThemeManager:
    """
    Legacy compatibility class for icon theme management.
    
    Wraps the new IconManager for backwards compatibility.
    New code should use IconManager directly.
    """
    
    # Class-level theme storage
    _theme = 'default'
    
    def __init__(self, dockwidget=None):
        """Initialize with optional dockwidget reference."""
        self._dockwidget = dockwidget
        self._current_theme = 'default'
    
    @classmethod
    def set_theme(cls, theme: str) -> None:
        """Set the current theme (class method for legacy compatibility)."""
        cls._theme = theme
        logger.debug(f"IconThemeManager.set_theme: {theme}")
    
    @classmethod
    def get_theme(cls) -> str:
        """Get the current theme."""
        return cls._theme
    
    @classmethod
    def is_dark(cls) -> bool:
        """Check if dark mode is active (class method)."""
        return cls._theme == 'dark' or _is_dark_mode()
    
    @property
    def is_dark_mode(self) -> bool:
        """Check if dark mode is active (instance property)."""
        return IconThemeManager._theme == 'dark' or _is_dark_mode()
    
    def get_icon_for_theme(self, icon_path: str) -> QIcon:
        """Get themed icon (legacy method)."""
        return get_themed_icon(icon_path)
    
    def refresh_all_button_icons(self) -> int:
        """Refresh all icons (legacy method)."""
        if not self._dockwidget:
            return 0
        
        try:
            from qgis.PyQt.QtWidgets import QAbstractButton
            updated = 0
            
            for button in self._dockwidget.findChildren(QAbstractButton):
                icon_path = button.property('icon_path')
                if icon_path and _icon_exists(icon_path):
                    button.setIcon(get_themed_icon(icon_path))
                    updated += 1
            
            return updated
        except Exception as e:
            logger.error(f"IconThemeManager.refresh_all_button_icons failed: {e}")
            return 0


# ============================================================================
# Helper functions
# ============================================================================

def _is_qt_resource_path(path: str) -> bool:
    """Check if path is a Qt resource path (starts with :/)."""
    return path.startswith(':/') if path else False


def _icon_exists(icon_path: str) -> bool:
    """
    Check if an icon exists, supporting both filesystem and Qt resource paths.
    
    Args:
        icon_path: Path to icon (filesystem or Qt resource like :/plugins/...)
    
    Returns:
        True if icon exists and can be loaded
    """
    if not icon_path:
        return False
    
    # For Qt resource paths, try to load the pixmap to check existence
    if _is_qt_resource_path(icon_path):
        pixmap = QPixmap(icon_path)
        return not pixmap.isNull()
    
    # For filesystem paths, use os.path.exists
    return os.path.exists(icon_path)


def _is_dark_mode() -> bool:
    """Check if QGIS is using a dark theme based on palette luminance."""
    try:
        from qgis.PyQt.QtWidgets import QApplication
        from qgis.PyQt.QtGui import QPalette
        
        app = QApplication.instance()
        if app:
            palette = app.palette()
            bg_color = palette.color(QPalette.Window)
            # Consider dark if luminance is low (< 128)
            luminance = (bg_color.red() * 0.299 + 
                        bg_color.green() * 0.587 + 
                        bg_color.blue() * 0.114)
            return luminance < 128
    except Exception:
        pass
    return False


def _get_white_variant(icon_path: str) -> Optional[str]:
    """Get path to white variant of an icon."""
    if not icon_path:
        return None
    
    # Handle Qt resource paths
    if _is_qt_resource_path(icon_path):
        # Extract parts from resource path like :/plugins/filter_mate/icons/icon.png
        # Split by / and reconstruct with _white suffix
        parts = icon_path.rsplit('/', 1)
        if len(parts) == 2:
            directory, filename = parts
        else:
            return None
    else:
        directory = os.path.dirname(icon_path)
        filename = os.path.basename(icon_path)
    
    name, ext = os.path.splitext(filename)
    
    # Check if _black variant -> use _white
    if name.endswith('_black'):
        white_name = name.replace('_black', '_white') + ext
        if _is_qt_resource_path(icon_path):
            white_path = f"{directory}/{white_name}"
        else:
            white_path = os.path.join(directory, white_name)
        if _icon_exists(white_path):
            return white_path
    
    # Try adding _white suffix
    if _is_qt_resource_path(icon_path):
        white_path = f"{directory}/{name}_white{ext}"
    else:
        white_path = os.path.join(directory, f"{name}_white{ext}")
    if _icon_exists(white_path):
        return white_path
    
    return None


def _invert_pixmap(pixmap: QPixmap) -> QPixmap:
    """Invert colors of a QPixmap, preserving alpha channel."""
    if pixmap.isNull():
        return pixmap
    
    image = pixmap.toImage()
    image.invertPixels(QImage.InvertRgb)
    
    return QPixmap.fromImage(image)


# ============================================================================
# Main function: get_themed_icon
# ============================================================================

def get_themed_icon(icon_path: str, force_invert: bool = False) -> QIcon:
    """
    Get a themed icon suitable for the current QGIS theme.
    
    Supports both filesystem paths and Qt resource paths (:/plugins/...).
    
    For dark themes:
    - First checks for _white variant of the icon
    - Falls back to inverting the icon colors
    
    Args:
        icon_path: Full path to the icon file (filesystem or Qt resource path)
        force_invert: Force inversion even if variant exists
    
    Returns:
        QIcon appropriate for current theme
    """
    if not icon_path:
        logger.warning("get_themed_icon: Empty icon path")
        return QIcon()
    
    if not _icon_exists(icon_path):
        logger.warning(f"get_themed_icon: Icon not found: {icon_path}")
        return QIcon()
    
    # Check if we're in dark mode (from IconThemeManager or QGIS palette)
    is_dark = IconThemeManager._theme == 'dark' or _is_dark_mode()
    
    # For light mode, return original icon directly
    if not is_dark:
        icon = QIcon(icon_path)
        if icon.isNull():
            logger.warning(f"get_themed_icon: Failed to load icon: {icon_path}")
        return icon
    
    # Dark mode: Try white variant first (unless forced invert)
    if not force_invert:
        white_path = _get_white_variant(icon_path)
        if white_path and _icon_exists(white_path):
            icon = QIcon(white_path)
            if not icon.isNull():
                logger.debug(f"get_themed_icon: Using white variant: {white_path}")
                return icon
    
    # Dark mode: Invert the icon colors
    pixmap = QPixmap(icon_path)
    if pixmap.isNull():
        logger.warning(f"get_themed_icon: Failed to load pixmap: {icon_path}")
        return QIcon(icon_path)
    
    inverted = _invert_pixmap(pixmap)
    logger.debug(f"get_themed_icon: Inverted icon for dark mode: {icon_path}")
    return QIcon(inverted)


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'IconThemeManager',
    'get_themed_icon',
    'IconManager',
    'icon_exists',  # Public alias for _icon_exists
]


# Public alias for external use
def icon_exists(icon_path: str) -> bool:
    """
    Check if an icon exists, supporting both filesystem and Qt resource paths.
    
    This is the public API for checking icon existence.
    
    Args:
        icon_path: Path to icon (filesystem or Qt resource like :/plugins/...)
    
    Returns:
        True if icon exists and can be loaded
    """
    return _icon_exists(icon_path)
