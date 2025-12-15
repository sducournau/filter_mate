# -*- coding: utf-8 -*-
"""
UI Styles Module for FilterMate

Handles loading and applying QSS stylesheets to the FilterMate dockwidget.
Supports multiple themes and dynamic color replacement.
Integrates with UIConfig for dynamic sizing based on display profiles.
"""

import os
import logging
from typing import Dict, Optional
from PyQt5.QtCore import QFile, QTextStream, QIODevice
from PyQt5.QtWidgets import QWidget
from qgis.core import QgsApplication

logger = logging.getLogger(__name__)

# Import UIConfig for dynamic sizing
try:
    from .ui_config import UIConfig, DisplayProfile
    UI_CONFIG_AVAILABLE = True
except ImportError:
    UI_CONFIG_AVAILABLE = False
    logger.warning("UIConfig not available, using default dimensions")


class StyleLoader:
    """
    Stylesheet loader with theme support.
    
    Manages loading QSS stylesheets from the resources/styles directory
    and applies them to widgets with dynamic color replacement.
    """
    
    _current_theme = 'default'
    _styles_cache: Dict[str, str] = {}
    
    # Default color schemes (matching config.json COLORS structure)
    COLOR_SCHEMES = {
        'default': {
            'color_bg_0': '#EFEFEF',      # BACKGROUND[0] - Frame background (darker for separation)
            'color_1': '#FFFFFF',         # BACKGROUND[1] - Widget background (pure white)
            'color_2': '#D0D0D0',         # BACKGROUND[2] - Borders/selected (clear contrast)
            'color_bg_3': '#2196F3',      # BACKGROUND[3] - Accent color
            'color_3': '#4A4A4A',         # FONT[1] - Text color (WCAG AA compliant)
            'color_font_0': '#1A1A1A',    # FONT[0] - Primary text (near-black, WCAG AA)
            'color_font_1': '#4A4A4A',    # FONT[1] - Secondary text (distinct from primary)
            'color_font_2': '#888888',    # FONT[2] - Disabled text (clearly muted)
            'color_accent': '#1565C0',    # Accent primary (darker blue, better contrast)
            'color_accent_hover': '#1E88E5',     # Accent hover (lighter for feedback)
            'color_accent_pressed': '#0D47A1',   # Accent pressed (very dark blue)
            'color_accent_light_bg': '#E3F2FD', # Accent light background
            'color_accent_dark': '#01579B',     # Accent dark border
            'icon_filter': 'none'               # No icon inversion for light theme
        },
        'dark': {
            'color_bg_0': '#1E1E1E',    # Dark frame background (harmonisé avec JsonView)
            'color_1': '#252526',       # Widget background (VS Code dark style)
            'color_2': '#37373D',       # Selected items (plus visible)
            'color_bg_3': '#0E639C',    # Splitter hover (bleu plus sombre)
            'color_3': '#CCCCCC',       # Light text (légèrement plus doux)
            'color_font_0': '#D4D4D4',  # Primary text (plus confortable pour les yeux)
            'color_font_1': '#9D9D9D',  # Secondary text (plus de contraste avec primary)
            'color_font_2': '#6A6A6A',  # Disabled text (plus foncé pour bien différencier)
            'color_accent': '#007ACC',  # Bleu VS Code (parfait)
            'color_accent_hover': '#1177BB',    # Hover plus subtil
            'color_accent_pressed': '#005A9E',  # Pressed reste sombre
            'color_accent_light_bg': '#264F78', # Background accentué plus visible (harmonisé)
            'color_accent_dark': '#FFFFFF',     # Text sur fond accentué (blanc pour contraste)
            'icon_filter': 'invert(100%)'       # Invert icons to white for dark theme
        },
        'light': {
            'color_bg_0': '#FFFFFF',    # Pure white frame background (maximum brightness)
            'color_1': '#F8F8F8',       # Widget background (subtle contrast)
            'color_2': '#CCCCCC',       # Borders (clearly visible)
            'color_bg_3': '#2196F3',    # Splitter hover
            'color_3': '#333333',       # Dark text (excellent readability)
            'color_font_0': '#000000',  # Primary text (pure black, maximum contrast)
            'color_font_1': '#333333',  # Secondary text (very dark gray)
            'color_font_2': '#999999',  # Disabled text (medium gray)
            'color_accent': '#1976D2',  # Accent primary (Material Blue)
            'color_accent_hover': '#2196F3',    # Accent hover (lighter blue)
            'color_accent_pressed': '#0D47A1',  # Accent pressed (dark blue)
            'color_accent_light_bg': '#E3F2FD', # Accent light background
            'color_accent_dark': '#0D47A1',     # Accent dark border
            'icon_filter': 'none'               # No icon inversion for light theme
        }
    }
    
    @classmethod
    def _load_raw_stylesheet(cls, theme: str = 'default') -> str:
        """
        Load raw QSS stylesheet from file without applying any colors.
        
        This is a private method used internally to get the stylesheet template
        before color replacement.
        
        Args:
            theme: Theme name ('default', 'dark', 'light')
        
        Returns:
            str: Raw stylesheet content with placeholders intact, or empty string on error
        """
        # Determine file path
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        style_file = os.path.join(plugin_dir, 'resources', 'styles', f'{theme}.qss')
        
        # Fallback to default if theme file doesn't exist
        if not os.path.exists(style_file):
            style_file = os.path.join(plugin_dir, 'resources', 'styles', 'default.qss')
        
        if not os.path.exists(style_file):
            logger.error(f"Stylesheet not found: {style_file}")
            return ""
        
        try:
            # Read stylesheet file using standard Python open()
            # (more reliable than QFile, especially in test environment)
            with open(style_file, 'r', encoding='utf-8') as f:
                stylesheet = f.read()
            return stylesheet
                
        except Exception as e:
            logger.error(f"Error loading stylesheet: {e}")
            return ""
    
    @classmethod
    def load_stylesheet(cls, theme: str = 'default') -> str:
        """
        Load QSS stylesheet from file with COLOR_SCHEMES colors applied.
        
        Args:
            theme: Theme name ('default', 'dark', 'light')
        
        Returns:
            str: Stylesheet content with COLOR_SCHEMES colors applied, or empty string on error
        """
        # Check cache first
        if theme in cls._styles_cache:
            return cls._styles_cache[theme]
        
        # Get raw stylesheet
        stylesheet = cls._load_raw_stylesheet(theme)
        
        if not stylesheet:
            return ""
        
        try:
            # Apply color scheme from COLOR_SCHEMES
            colors = cls.COLOR_SCHEMES.get(theme, cls.COLOR_SCHEMES['default'])
            for color_key, color_value in colors.items():
                stylesheet = stylesheet.replace(f'{{{color_key}}}', color_value)
            
            # Cache the result
            cls._styles_cache[theme] = stylesheet
            
            return stylesheet
                
        except Exception as e:
            logger.error(f"Error applying color scheme: {e}")
            return ""
    
    @classmethod
    def load_stylesheet_from_config(cls, config_data: dict, theme: str = None) -> str:
        """
        Load stylesheet with colors from config.json.
        
        Also loads UI profile from config and applies dynamic dimensions.
        
        Args:
            config_data: Configuration dictionary from config.json
            theme: Theme name (None = use ACTIVE_THEME from config)
        
        Returns:
            str: Stylesheet with config colors applied
        """
        # Load UI profile if UIConfig is available
        if UI_CONFIG_AVAILABLE:
            try:
                UIConfig.load_from_config(config_data)
            except Exception as e:
                logger.warning(f"Could not load UI profile: {e}")
        
        # Get raw stylesheet template (without color replacements)
        stylesheet = cls._load_raw_stylesheet('default')  # Always use default.qss file
        
        if not stylesheet:
            return ""
        
        # Extract colors from config using helpers
        try:
            from .config_helpers import (
                get_active_theme, get_theme_colors,
                get_background_colors, get_font_colors, get_accent_colors
            )
            
            # Determine active theme
            active_theme = theme if theme else get_active_theme(config_data)
            
            # Get colors for theme
            bg = get_background_colors(config_data) if not theme else get_theme_colors(config_data, active_theme).get("background", get_background_colors(config_data))
            font = get_font_colors(config_data) if not theme else get_theme_colors(config_data, active_theme).get("font", get_font_colors(config_data))
            accent = get_accent_colors(config_data) if not theme else get_theme_colors(config_data, active_theme).get("accent", get_accent_colors(config_data))
            
            # Map config colors to stylesheet placeholders
            color_map = {
                '{color_bg_0}': bg[0],      # Frame background
                '{color_1}': bg[1],         # Widget background
                '{color_2}': bg[2],         # Selected items
                '{color_bg_3}': bg[3],      # Accent/hover color
                '{color_3}': font[1],       # Secondary text color
                '{color_font_0}': font[0],  # Primary text color
                '{color_font_1}': font[1],  # Secondary text color
                '{color_font_2}': font[2],  # Disabled text color
                '{color_accent}': accent.get('PRIMARY', bg[3]),
                '{color_accent_hover}': accent.get('HOVER', bg[3]),
                '{color_accent_pressed}': accent.get('PRESSED', bg[3]),
                '{color_accent_light_bg}': accent.get('LIGHT_BG', bg[2]),
                '{color_accent_dark}': accent.get('DARK', bg[3])
            }
            
            # Apply color replacements
            for placeholder, color_value in color_map.items():
                stylesheet = stylesheet.replace(placeholder, color_value)
            
            # Apply dynamic dimensions from UIConfig if available
            if UI_CONFIG_AVAILABLE:
                stylesheet = cls._apply_dynamic_dimensions(stylesheet)
            
            return stylesheet
            
        except (KeyError, IndexError) as e:
            logger.warning(f"Error reading config colors: {e}")
            # Fallback to default theme colors using load_stylesheet
            return cls.load_stylesheet('default')
    
    @classmethod
    def set_theme_from_config(cls, widget, config_data: dict, theme: str = None):
        """
        Apply theme to widget using config.json colors.
        
        Supports automatic QGIS theme synchronization when ACTIVE_THEME='auto'.
        
        Args:
            widget: Qt widget to apply stylesheet to
            config_data: Configuration dictionary
            theme: Theme name (None = use ACTIVE_THEME from config, 'auto' = detect from QGIS)
        """
        # Auto-detect theme from config if not specified
        if theme is None:
            theme = cls.get_active_theme_from_config(config_data)
        elif theme == 'auto':
            theme = cls.detect_qgis_theme()
        
        stylesheet = cls.load_stylesheet_from_config(config_data, theme)
        if stylesheet:
            widget.setStyleSheet(stylesheet)
            cls._current_theme = theme
            logger.info(f"Applied theme '{theme}' from config")
    
    @classmethod
    def set_theme(cls, widget, theme: str = 'default'):
        """
        Apply theme to widget.
        
        Args:
            widget: Qt widget to apply stylesheet to
            theme: Theme name
        """
        stylesheet = cls.load_stylesheet(theme)
        if stylesheet:
            widget.setStyleSheet(stylesheet)
            cls._current_theme = theme
    
    @classmethod
    def get_current_theme(cls) -> str:
        """Get current theme name"""
        return cls._current_theme
    
    @classmethod
    def get_available_themes(cls, config_data: dict = None) -> list:
        """
        Get list of available themes.
        
        Args:
            config_data: Configuration dictionary (None = use COLOR_SCHEMES)
        
        Returns:
            list: List of available theme names
        """
        if config_data:
            try:
                from .config_helpers import get_config_value
                # Try new structure
                themes = get_config_value(config_data, "app", "themes")
                if themes:
                    return list(themes.keys())
                # Try old structure
                themes = get_config_value(config_data, "APP", "DOCKWIDGET", "COLORS", "THEMES")
                if themes:
                    return list(themes.keys())
            except (KeyError, TypeError):
                pass
        
        # Fallback to built-in themes
        return list(cls.COLOR_SCHEMES.keys())
    
    @classmethod
    def detect_qgis_theme(cls) -> str:
        """
        Detect current QGIS theme and return appropriate plugin theme.
        
        Analyzes QGIS palette to determine if dark or light theme is active.
        
        Returns:
            str: 'dark' if QGIS uses dark theme, 'default' for light theme
        """
        try:
            palette = QgsApplication.instance().palette()
            # Check background color brightness
            bg_color = palette.color(palette.Window)
            # Calculate luminance (perceived brightness)
            # Formula: (0.299*R + 0.587*G + 0.114*B)
            luminance = (0.299 * bg_color.red() + 
                        0.587 * bg_color.green() + 
                        0.114 * bg_color.blue())
            
            # If luminance < 128, it's a dark theme
            if luminance < 128:
                logger.info(f"Detected QGIS dark theme (luminance: {luminance:.0f})")
                return 'dark'
            else:
                logger.info(f"Detected QGIS light theme (luminance: {luminance:.0f})")
                return 'default'
        except Exception as e:
            logger.warning(f"Could not detect QGIS theme: {e}. Using default.")
            return 'default'
    
    @classmethod
    def get_active_theme_from_config(cls, config_data: dict) -> str:
        """
        Get active theme name from config.json.
        
        Supports special value 'auto' to sync with QGIS theme automatically.
        
        Args:
            config_data: Configuration dictionary
        
        Returns:
            str: Active theme name or 'default'
        """
        try:
            from .config_helpers import get_active_theme as get_active_theme_helper
            active_theme = get_active_theme_helper(config_data)
            
            # Auto-detect from QGIS if set to 'auto'
            if active_theme == "auto":
                return cls.detect_qgis_theme()
            
            return active_theme
        except (KeyError, TypeError):
            return "default"
    
    @classmethod
    def clear_cache(cls):
        """Clear stylesheet cache"""
        cls._styles_cache.clear()
    
    @classmethod
    def _apply_dynamic_dimensions(cls, stylesheet: str) -> str:
        """
        Apply dynamic dimensions from UIConfig to stylesheet.
        
        Replaces dimension placeholders with values from current UI profile.
        
        Args:
            stylesheet: Base stylesheet content
        
        Returns:
            str: Stylesheet with dynamic dimensions applied
        """
        if not UI_CONFIG_AVAILABLE:
            return stylesheet
        
        try:
            # Get current profile config
            profile = UIConfig.get_all_dimensions()
            
            # Define dimension replacements
            # Format: {placeholder: (component, key)}
            dimension_map = {
                # Buttons
                '{button_height}': ('button', 'height'),
                '{button_icon_size}': ('button', 'icon_size'),
                '{button_border_radius}': ('button', 'border_radius'),
                '{action_button_height}': ('action_button', 'height'),
                '{action_button_icon_size}': ('action_button', 'icon_size'),
                '{tool_button_height}': ('tool_button', 'height'),
                '{tool_button_icon_size}': ('tool_button', 'icon_size'),
                
                # Inputs
                '{input_height}': ('input', 'height'),
                '{input_border_radius}': ('input', 'border_radius'),
                
                # ComboBox
                '{combobox_height}': ('combobox', 'height'),
                '{combobox_item_height}': ('combobox', 'item_height'),
                
                # Frames
                '{frame_min_height}': ('frame', 'min_height'),
                '{frame_padding}': ('frame', 'padding'),
                '{action_frame_height}': ('action_frame', 'min_height'),
                
                # Splitter
                '{splitter_width}': ('splitter', 'handle_width'),
                
                # Scrollbar
                '{scrollbar_width}': ('scrollbar', 'width'),
                
                # Spacing
                '{spacing_small}': ('spacing', 'small'),
                '{spacing_medium}': ('spacing', 'medium'),
                '{spacing_large}': ('spacing', 'large'),
                
                # Labels
                '{label_font_size}': ('label', 'font_size'),
                
                # Tree
                '{tree_item_height}': ('tree', 'item_height'),
                '{tree_icon_size}': ('tree', 'icon_size'),
                
                # Tabs
                '{tab_height}': ('tab', 'height'),
                '{tab_font_size}': ('tab', 'font_size')
            }
            
            # Apply replacements
            for placeholder, (component, key) in dimension_map.items():
                value = UIConfig.get_config(component, key)
                if value is not None:
                    # Convert to string with 'px' suffix if numeric
                    if isinstance(value, (int, float)):
                        value_str = f"{int(value)}px"
                    else:
                        value_str = str(value)
                    
                    stylesheet = stylesheet.replace(placeholder, value_str)
            
            # Apply padding strings (special format)
            button_padding = UIConfig.get_padding_string('button')
            stylesheet = stylesheet.replace('{button_padding}', button_padding)
            
            action_padding = UIConfig.get_padding_string('action_button')
            stylesheet = stylesheet.replace('{action_button_padding}', action_padding)
            
            input_padding = UIConfig.get_padding_string('input')
            stylesheet = stylesheet.replace('{input_padding}', input_padding)
            
            combobox_padding = UIConfig.get_padding_string('combobox')
            stylesheet = stylesheet.replace('{combobox_padding}', combobox_padding)
            
            return stylesheet
            
        except Exception as e:
            logger.error(f"Error applying dynamic dimensions: {e}")
            return stylesheet
    
    @classmethod
    def reload_theme(cls, widget, theme: Optional[str] = None):
        """
        Reload and reapply theme.
        
        Args:
            widget: Widget to update
            theme: Theme to apply (None = current theme)
        """
        cls.clear_cache()
        theme_to_apply = theme or cls._current_theme
        cls.set_theme(widget, theme_to_apply)
