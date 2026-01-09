"""
Icon Manager for FilterMate.

Centralized icon management with theme support.
Migrated from modules/icon_utils.py (IconThemeManager class).

Story: MIG-067
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, Dict, Set
import logging
import os

from qgis.PyQt.QtGui import QIcon, QPixmap, QImage
from qgis.PyQt.QtWidgets import QPushButton, QToolButton, QAbstractButton

from .base_styler import StylerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class IconManager(StylerBase):
    """
    Centralized icon management with theme support.
    
    Provides:
    - Theme-aware icon loading (dark/light variants)
    - Icon inversion for dark mode
    - Icon caching for performance
    - Button icon management
    
    Migrated methods from modules/icon_utils.py:
    - get_icon_for_theme() -> get_icon()
    - apply_icon_to_button() -> set_button_icon()
    - invert_pixmap() -> _invert_pixmap()
    - refresh_all_button_icons() -> refresh_all_icons()
    
    Example:
        manager = IconManager(dockwidget)
        manager.setup()
        
        # Get themed icon
        icon = manager.get_icon('filter.png')
        
        # Apply to button
        manager.set_button_icon(button, 'filter.png')
    """
    
    # Icons that have _black/_white variants
    VARIANT_ICONS: Dict[str, tuple] = {
        'auto_layer': ('auto_layer_black.png', 'auto_layer_white.png'),
        'folder': ('folder_black.png', 'folder_white.png'),
        'map': ('map_black.png', 'map_white.png'),
        'pointing': ('pointing_black.png', 'pointing_white.png'),
        'projection': ('projection_black.png', 'projection_white.png'),
        'styles': ('styles_black.png', 'styles_white.png'),
        'select': ('select_black.png', 'selection_white.png'),
    }
    
    # Icons that should ALWAYS be inverted in dark mode
    FORCE_INVERT_ICONS: Set[str] = {
        'layers.png', 'datatype.png', 'zip.png', 'filter.png',
        'undo.png', 'redo.png', 'unfilter.png', 'reset.png',
        'export.png', 'identify_alt.png', 'zoom.png', 'track.png',
        'link.png', 'save_properties.png', 'add_multi.png',
        'geo_predicates.png', 'buffer_value.png', 'buffer_type.png',
        'filter_multi.png', 'save.png', 'parameters.png',
    }
    
    # Icons that should NOT be inverted
    EXCLUDE_FROM_INVERSION: Set[str] = {
        'logo.png', 'icon.png',
    }
    
    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the IconManager.
        
        Args:
            dockwidget: The main FilterMate dockwidget instance
        """
        super().__init__(dockwidget)
        self._current_theme: str = 'default'
        self._icon_cache: Dict[str, QIcon] = {}
        self._icons_dir: Optional[str] = None
    
    @property
    def is_dark_mode(self) -> bool:
        """Check if current theme is dark mode."""
        return self._current_theme == 'dark'
    
    def setup(self) -> None:
        """
        Initialize icon paths and cache.
        
        Determines icon directory and current theme.
        """
        # Determine icons directory
        plugin_dir = self.get_plugin_dir()
        if plugin_dir:
            self._icons_dir = os.path.join(plugin_dir, 'icons')
        
        # Sync with ThemeManager if available
        self._sync_with_theme_manager()
        
        self._initialized = True
        logger.info(f"IconManager initialized with theme: {self._current_theme}")
    
    def apply(self) -> None:
        """
        Apply icons to all widgets for current theme.
        
        Refreshes all registered button icons.
        """
        if not self._initialized:
            return
        
        self.refresh_all_icons()
        logger.debug(f"Applied icons for theme '{self._current_theme}'")
    
    def get_icon(self, icon_name: str, force_invert: bool = False) -> QIcon:
        """
        Get themed icon by name.
        
        For dark mode:
        - First checks for _white variant
        - Falls back to inverting the icon
        
        Args:
            icon_name: Icon filename (e.g., 'filter.png')
            force_invert: Force inversion even if variant exists
        
        Returns:
            QIcon appropriate for current theme
        """
        # Build full path
        icon_path = self._resolve_icon_path(icon_name)
        if not icon_path or not os.path.exists(icon_path):
            logger.warning(f"Icon not found: {icon_name}")
            return QIcon()
        
        # Check exclusions
        if icon_name in self.EXCLUDE_FROM_INVERSION:
            return QIcon(icon_path)
        
        # For light themes, return original
        if not self.is_dark_mode:
            return QIcon(icon_path)
        
        # Dark mode: check cache
        cache_key = f"{icon_name}_{self._current_theme}"
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        
        # Check if should force-invert
        should_force_invert = icon_name in self.FORCE_INVERT_ICONS
        
        # Try white variant
        if not force_invert and not should_force_invert:
            white_path = self._get_white_variant_path(icon_path)
            if white_path and os.path.exists(white_path):
                icon = QIcon(white_path)
                self._icon_cache[cache_key] = icon
                logger.debug(f"Using white variant for '{icon_name}'")
                return icon
        
        # Invert the icon
        original_pixmap = QPixmap(icon_path)
        if original_pixmap.isNull():
            return QIcon(icon_path)
        
        inverted_pixmap = self._invert_pixmap(original_pixmap)
        icon = QIcon(inverted_pixmap)
        
        # Cache result
        self._icon_cache[cache_key] = icon
        logger.debug(f"Inverted icon '{icon_name}'")
        
        return icon
    
    def set_button_icon(self, button: QAbstractButton, icon_name: str) -> None:
        """
        Set themed icon on a button.
        
        Also stores the icon name as a property for later refresh.
        
        Args:
            button: QPushButton or QToolButton
            icon_name: Icon filename
        """
        icon = self.get_icon(icon_name)
        if not icon.isNull():
            button.setIcon(icon)
            button.setProperty('icon_name', icon_name)
    
    def refresh_all_icons(self) -> int:
        """
        Refresh all button icons in dockwidget for current theme.
        
        Returns:
            Number of buttons updated
        """
        updated = 0
        
        # Find all buttons
        buttons = self.dockwidget.findChildren(QAbstractButton)
        
        for button in buttons:
            icon_name = button.property('icon_name')
            if icon_name:
                icon = self.get_icon(icon_name)
                if not icon.isNull():
                    button.setIcon(icon)
                    updated += 1
        
        logger.info(f"Refreshed {updated} button icons for theme '{self._current_theme}'")
        return updated
    
    def on_theme_changed(self, theme: str) -> None:
        """
        Update all icons for new theme.
        
        Args:
            theme: New theme name
        """
        if theme != self._current_theme:
            self._current_theme = theme
            self.clear_cache()
            self.apply()
    
    def clear_cache(self) -> None:
        """Clear icon cache."""
        self._icon_cache.clear()
        logger.debug("Icon cache cleared")
    
    def _resolve_icon_path(self, icon_name: str) -> Optional[str]:
        """
        Resolve icon name to full path.
        
        Args:
            icon_name: Icon filename or relative path
        
        Returns:
            Full path to icon or None
        """
        # If already a full path
        if os.path.isabs(icon_name):
            return icon_name
        
        # Try icons directory
        if self._icons_dir:
            path = os.path.join(self._icons_dir, icon_name)
            if os.path.exists(path):
                return path
        
        # Try plugin directory
        plugin_dir = self.get_plugin_dir()
        if plugin_dir:
            for subdir in ['icons', 'resources/icons', '']:
                path = os.path.join(plugin_dir, subdir, icon_name) if subdir else os.path.join(plugin_dir, icon_name)
                if os.path.exists(path):
                    return path
        
        return None
    
    def _get_white_variant_path(self, icon_path: str) -> Optional[str]:
        """
        Get path to _white variant of an icon.
        
        Args:
            icon_path: Original icon path
        
        Returns:
            Path to white variant or None
        """
        directory = os.path.dirname(icon_path)
        filename = os.path.basename(icon_path)
        name, ext = os.path.splitext(filename)
        
        # Check if _black variant
        if name.endswith('_black'):
            white_name = name.replace('_black', '_white') + ext
            return os.path.join(directory, white_name)
        
        # Check known variants
        for base_name, (black_file, white_file) in self.VARIANT_ICONS.items():
            if filename == black_file:
                return os.path.join(directory, white_file)
        
        # Try adding _white suffix
        white_path = os.path.join(directory, f"{name}_white{ext}")
        if os.path.exists(white_path):
            return white_path
        
        return None
    
    def _invert_pixmap(self, pixmap: QPixmap) -> QPixmap:
        """
        Invert colors of a QPixmap for dark mode.
        
        Preserves alpha channel while inverting RGB.
        
        Args:
            pixmap: Original QPixmap
        
        Returns:
            Inverted QPixmap
        """
        if pixmap.isNull():
            return pixmap
        
        image = pixmap.toImage()
        image.invertPixels(QImage.InvertRgb)
        
        return QPixmap.fromImage(image)
    
    def _sync_with_theme_manager(self) -> None:
        """Sync theme from ThemeManager if available."""
        try:
            # Try to get theme from dockwidget's theme manager
            if hasattr(self.dockwidget, 'theme_manager'):
                tm = self.dockwidget.theme_manager
                if hasattr(tm, 'current_theme'):
                    self._current_theme = tm.current_theme
                    return
            
            # Try legacy StyleLoader
            from ui.styles import StyleLoader
            self._current_theme = StyleLoader.get_current_theme()
        except Exception:
            # Default theme
            self._current_theme = 'default'
    
    def teardown(self) -> None:
        """Clean up resources."""
        self.clear_cache()
        super().teardown()
