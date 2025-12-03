# -*- coding: utf-8 -*-
"""
UI Styles Module for FilterMate

Handles loading and applying QSS stylesheets to the FilterMate dockwidget.
Supports multiple themes and dynamic color replacement.
"""

import os
from typing import Dict, Optional
from PyQt5.QtCore import QFile, QTextStream, QIODevice


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
            'color_bg_0': 'white',      # BACKGROUND[0] - Frame background
            'color_1': '#CCCCCC',       # BACKGROUND[1] - Widget background
            'color_2': '#F0F0F0',       # BACKGROUND[2] - Selected items
            'color_bg_3': '#757575',    # BACKGROUND[3] - Splitter hover
            'color_3': 'black'          # FONT[1] - Text color
        },
        'dark': {
            'color_bg_0': '#1e1e1e',    # Darker frame background
            'color_1': '#2d2d30',       # Widget background
            'color_2': '#3e3e42',       # Selected items
            'color_bg_3': '#007acc',    # Splitter hover
            'color_3': '#eff0f1'        # Light text
        },
        'light': {
            'color_bg_0': '#ffffff',    # Light frame background
            'color_1': '#f0f0f0',       # Widget background
            'color_2': '#e0e0e0',       # Selected items
            'color_bg_3': '#2196f3',    # Splitter hover
            'color_3': '#000000'        # Dark text
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
            print(f"FilterMate: Stylesheet not found: {style_file}")
            return ""
        
        try:
            # Read stylesheet file using standard Python open()
            # (more reliable than QFile, especially in test environment)
            with open(style_file, 'r', encoding='utf-8') as f:
                stylesheet = f.read()
            return stylesheet
                
        except Exception as e:
            print(f"FilterMate: Error loading stylesheet: {e}")
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
            print(f"FilterMate: Error applying color scheme: {e}")
            return ""
    
    @classmethod
    def load_stylesheet_from_config(cls, config_data: dict, theme: str = 'default') -> str:
        """
        Load stylesheet with colors from config.json.
        
        Args:
            config_data: Configuration dictionary from config.json
            theme: Theme name (currently only uses config colors)
        
        Returns:
            str: Stylesheet with config colors applied
        """
        # Get raw stylesheet template (without color replacements)
        stylesheet = cls._load_raw_stylesheet(theme)
        
        if not stylesheet:
            return ""
        
        # Extract colors from config
        try:
            colors = config_data["APP"]["DOCKWIDGET"]["COLORS"]
            bg = colors["BACKGROUND"]
            font = colors["FONT"]
            
            # Map config colors to stylesheet placeholders
            color_map = {
                '{color_bg_0}': bg[0],      # Frame background
                '{color_1}': bg[1],         # Widget background
                '{color_2}': bg[2],         # Selected items
                '{color_bg_3}': bg[3],      # Splitter hover
                '{color_3}': font[1]        # Text color
            }
            
            # Apply color replacements
            for placeholder, color_value in color_map.items():
                stylesheet = stylesheet.replace(placeholder, color_value)
            
            return stylesheet
            
        except (KeyError, IndexError) as e:
            print(f"FilterMate: Error reading config colors: {e}")
            # Fallback to default theme colors using load_stylesheet
            return cls.load_stylesheet(theme)
    
    @classmethod
    def set_theme_from_config(cls, widget, config_data: dict, theme: str = 'default'):
        """
        Apply theme to widget using config.json colors.
        
        Args:
            widget: Qt widget to apply stylesheet to
            config_data: Configuration dictionary
            theme: Theme name
        """
        stylesheet = cls.load_stylesheet_from_config(config_data, theme)
        if stylesheet:
            widget.setStyleSheet(stylesheet)
            cls._current_theme = theme
    
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
    def clear_cache(cls):
        """Clear stylesheet cache"""
        cls._styles_cache.clear()
    
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
