# -*- coding: utf-8 -*-
"""
Icon Utilities Module for FilterMate

Provides utilities for managing icons with dark/light theme support:
- Automatic icon inversion for dark mode
- Icon variant switching (_black/_white)
- Theme-aware icon loading
- QPixmap manipulation for color inversion

Author: FilterMate Team
Date: December 2025
"""

import os
import logging
from typing import Dict, Optional, Tuple

# Use qgis.PyQt for QGIS plugin compatibility
from qgis.PyQt.QtGui import QIcon, QPixmap, QImage, QPainter, QColor
from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtWidgets import QPushButton, QToolButton, QAbstractButton

logger = logging.getLogger(__name__)


class IconThemeManager:
    """
    Manages icon theming for dark/light mode support.
    
    Features:
    - Inverts dark icons to white for dark mode
    - Switches between _black/_white icon variants
    - Caches inverted icons for performance
    - Provides theme-aware icon loading
    """
    
    # Cache for inverted icons
    _inverted_cache: Dict[str, QIcon] = {}
    _current_theme: str = 'default'
    
    # Icons that have _black/_white variants
    VARIANT_ICONS = {
        'auto_layer': ('auto_layer_black.png', 'auto_layer_white.png'),
        'folder': ('folder_black.png', 'folder_white.png'),
        'map': ('map_black.png', 'map_white.png'),
        'pointing': ('pointing_black.png', 'pointing_white.png'),
        'projection': ('projection_black.png', 'projection_white.png'),
        'styles': ('styles_black.png', 'styles_white.png'),
        'select': ('select_black.png', 'selection_white.png'),
    }
    
    # Icons that should ALWAYS be inverted in dark mode (no variant exists)
    # These are typically dark/black icons that need inversion for visibility
    FORCE_INVERT_ICONS = {
        'layers.png',
        'datatype.png', 
        'zip.png',
        'filter.png',
        'undo.png',
        'redo.png',
        'unfilter.png',
        'reset.png',
        'export.png',
        'identify_alt.png',
        'zoom.png',
        'track.png',
        'link.png',
        'save_properties.png',
        'add_multi.png',
        'geo_predicates.png',
        'buffer_value.png',
        'buffer_type.png',
        'filter_multi.png',
        'save.png',
        'parameters.png',
    }
    
    # Icons that should NOT be inverted (already have good contrast or are colored)
    EXCLUDE_FROM_INVERSION = {
        'logo.png',
        'icon.png',
        # Add colored icons that shouldn't be inverted
    }
    
    @classmethod
    def is_dark_mode(cls) -> bool:
        """Check if current theme is dark mode."""
        return cls._current_theme == 'dark'
    
    @classmethod
    def set_theme(cls, theme: str) -> None:
        """
        Set the current theme and clear cache if theme changed.
        
        Args:
            theme: Theme name ('default', 'dark', 'light')
        """
        if theme != cls._current_theme:
            logger.info(f"IconThemeManager: Theme changed from '{cls._current_theme}' to '{theme}'")
            cls._current_theme = theme
            cls._inverted_cache.clear()
    
    @classmethod
    def get_theme(cls) -> str:
        """Get current theme name."""
        return cls._current_theme
    
    @classmethod
    def invert_pixmap(cls, pixmap: QPixmap) -> QPixmap:
        """
        Invert the colors of a QPixmap (for dark mode).
        
        Preserves alpha channel while inverting RGB values.
        This makes dark icons appear white on dark backgrounds.
        
        Args:
            pixmap: Original QPixmap
            
        Returns:
            QPixmap with inverted colors
        """
        if pixmap.isNull():
            return pixmap
        
        # Convert to QImage for pixel manipulation
        image = pixmap.toImage()
        
        # Invert colors while preserving alpha
        image.invertPixels(QImage.InvertRgb)
        
        return QPixmap.fromImage(image)
    
    @classmethod
    def get_icon_for_theme(cls, icon_path: str, force_invert: bool = False) -> QIcon:
        """
        Get an icon appropriate for the current theme.
        
        For dark mode:
        - First checks for _white variant
        - Falls back to inverting the icon
        
        Args:
            icon_path: Path to the icon file
            force_invert: Force inversion even if variant exists
            
        Returns:
            QIcon appropriate for current theme
        """
        if not os.path.exists(icon_path):
            logger.warning(f"Icon not found: {icon_path}")
            return QIcon()
        
        # Check if this icon should be excluded from processing
        icon_filename = os.path.basename(icon_path)
        if icon_filename in cls.EXCLUDE_FROM_INVERSION:
            logger.debug(f"Icon excluded from inversion: {icon_filename}")
            return QIcon(icon_path)
        
        # For light themes, return original icon
        if not cls.is_dark_mode():
            logger.debug(f"Light mode, using original icon: {icon_filename}")
            return QIcon(icon_path)
        
        # Dark mode: check cache first
        cache_key = f"{icon_path}_{cls._current_theme}"
        if cache_key in cls._inverted_cache:
            logger.debug(f"Using cached themed icon: {icon_filename}")
            return cls._inverted_cache[cache_key]
        
        # Check if this icon should be force-inverted (no variant exists)
        should_force_invert = icon_filename in cls.FORCE_INVERT_ICONS
        
        # Try to find _white variant (unless force invert is set)
        if not force_invert and not should_force_invert:
            white_variant = cls._get_white_variant_path(icon_path)
            if white_variant and os.path.exists(white_variant):
                icon = QIcon(white_variant)
                cls._inverted_cache[cache_key] = icon
                logger.info(f"Dark mode: Using white variant for '{icon_filename}' -> '{os.path.basename(white_variant)}'")
                return icon
        
        # Invert the original icon
        original_pixmap = QPixmap(icon_path)
        if original_pixmap.isNull():
            logger.warning(f"Failed to load pixmap for inversion: {icon_path}")
            return QIcon(icon_path)
            
        inverted_pixmap = cls.invert_pixmap(original_pixmap)
        icon = QIcon(inverted_pixmap)
        
        # Cache the result
        cls._inverted_cache[cache_key] = icon
        logger.info(f"Dark mode: Inverted icon '{icon_filename}' (force={force_invert or should_force_invert})")
        
        return icon
    
    @classmethod
    def _get_white_variant_path(cls, icon_path: str) -> Optional[str]:
        """
        Get the path to the _white variant of an icon.
        
        Args:
            icon_path: Original icon path
            
        Returns:
            Path to white variant if naming convention applies, None otherwise
        """
        directory = os.path.dirname(icon_path)
        filename = os.path.basename(icon_path)
        name, ext = os.path.splitext(filename)
        
        # Check if this is a _black variant
        if name.endswith('_black'):
            white_name = name.replace('_black', '_white') + ext
            return os.path.join(directory, white_name)
        
        # Check known variants
        for base_name, (black_file, white_file) in cls.VARIANT_ICONS.items():
            if filename == black_file:
                return os.path.join(directory, white_file)
        
        # Try adding _white suffix
        white_path = os.path.join(directory, f"{name}_white{ext}")
        if os.path.exists(white_path):
            return white_path
        
        return None
    
    @classmethod
    def _get_black_variant_path(cls, icon_path: str) -> Optional[str]:
        """
        Get the path to the _black variant of an icon.
        
        Args:
            icon_path: Original icon path
            
        Returns:
            Path to black variant if naming convention applies, None otherwise
        """
        directory = os.path.dirname(icon_path)
        filename = os.path.basename(icon_path)
        name, ext = os.path.splitext(filename)
        
        # Check if this is a _white variant
        if name.endswith('_white'):
            black_name = name.replace('_white', '_black') + ext
            return os.path.join(directory, black_name)
        
        # Check known variants
        for base_name, (black_file, white_file) in cls.VARIANT_ICONS.items():
            if filename == white_file:
                return os.path.join(directory, black_file)
        
        return None
    
    @classmethod
    def apply_icon_to_button(cls, button: QAbstractButton, icon_path: str) -> None:
        """
        Apply a theme-appropriate icon to a button.
        
        Args:
            button: QPushButton or QToolButton
            icon_path: Path to the icon file
        """
        icon = cls.get_icon_for_theme(icon_path)
        if not icon.isNull():
            button.setIcon(icon)
    
    @classmethod
    def refresh_all_button_icons(cls, parent_widget, icons_dir: str) -> int:
        """
        Refresh all button icons in a widget tree for current theme.
        
        Args:
            parent_widget: Parent widget to search for buttons
            icons_dir: Directory containing icons
            
        Returns:
            Number of buttons updated
        """
        updated = 0
        
        # Find all buttons with icons
        buttons = parent_widget.findChildren(QAbstractButton)
        
        for button in buttons:
            icon = button.icon()
            if icon.isNull():
                continue
            
            # Try to get the icon path from button property
            icon_path = button.property('icon_path')
            if icon_path and os.path.exists(icon_path):
                cls.apply_icon_to_button(button, icon_path)
                updated += 1
        
        logger.info(f"Refreshed {updated} button icons for theme '{cls._current_theme}'")
        return updated
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear the icon cache."""
        cls._inverted_cache.clear()
        logger.debug("Icon cache cleared")


def detect_qgis_dark_mode() -> bool:
    """
    Detect if QGIS is using a dark theme.
    
    Analyzes the QGIS palette background color luminance.
    
    Returns:
        True if QGIS is in dark mode
    """
    try:
        from qgis.core import QgsApplication
        palette = QgsApplication.instance().palette()
        bg_color = palette.color(palette.Window)
        
        # Calculate perceived luminance
        luminance = (0.299 * bg_color.red() + 
                    0.587 * bg_color.green() + 
                    0.114 * bg_color.blue())
        
        return luminance < 128
    except Exception as e:
        logger.warning(f"Could not detect QGIS theme: {e}")
        return False


def get_themed_icon(icon_path: str) -> QIcon:
    """
    Convenience function to get a theme-appropriate icon.
    
    Args:
        icon_path: Path to the icon file
        
    Returns:
        QIcon appropriate for current theme
    """
    return IconThemeManager.get_icon_for_theme(icon_path)


def set_icon_theme(theme: str) -> None:
    """
    Set the icon theme.
    
    Args:
        theme: 'dark', 'light', or 'default'
    """
    IconThemeManager.set_theme(theme)
