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
    
    # Default color schemes
    COLOR_SCHEMES = {
        'default': {
            'color_1': '#31363b',  # Dark background
            'color_2': '#232629',  # Secondary background
            'color_3': '#eff0f1'   # Light text/accent
        },
        'dark': {
            'color_1': '#1e1e1e',  # Darker background
            'color_2': '#2d2d30',  # Secondary
            'color_3': '#3daee9'   # Blue accent
        },
        'light': {
            'color_1': '#ffffff',  # Light background
            'color_2': '#f0f0f0',  # Secondary
            'color_3': '#2196f3'   # Blue accent
        }
    }
    
    @classmethod
    def load_stylesheet(cls, theme: str = 'default') -> str:
        """
        Load QSS stylesheet from file.
        
        Args:
            theme: Theme name ('default', 'dark', 'light')
        
        Returns:
            str: Stylesheet content with colors applied, or empty string on error
        """
        # Check cache first
        if theme in cls._styles_cache:
            return cls._styles_cache[theme]
        
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
            # Read stylesheet file
            qfile = QFile(style_file)
            if qfile.open(QIODevice.ReadOnly | QIODevice.Text):
                stream = QTextStream(qfile)
                stylesheet = stream.readAll()
                qfile.close()
                
                # Apply color scheme
                colors = cls.COLOR_SCHEMES.get(theme, cls.COLOR_SCHEMES['default'])
                for color_key, color_value in colors.items():
                    stylesheet = stylesheet.replace(f'{{{color_key}}}', color_value)
                
                # Cache the result
                cls._styles_cache[theme] = stylesheet
                
                return stylesheet
            else:
                print(f"FilterMate: Could not open stylesheet: {style_file}")
                return ""
                
        except Exception as e:
            print(f"FilterMate: Error loading stylesheet: {e}")
            return ""
    
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
