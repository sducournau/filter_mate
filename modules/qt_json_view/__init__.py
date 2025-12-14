"""
Qt JSON View - A Qt-based JSON viewer and editor widget for QGIS.

This module provides a tree-based JSON viewer with support for:
- Editable keys and values
- Custom data types (URLs, file paths, ranges, choices)
- Multiple color themes
- Context menu actions
- Type-specific editors

Quick Start:
    from modules.qt_json_view import view, model
    
    json_model = model.JsonModel(data)
    json_view = view.JsonView(json_model)
    json_view.set_theme('monokai')
    json_view.show()

Available themes:
    - default: Black text for all types
    - monokai: Vibrant dark theme
    - solarized_light: Warm colors on light background
    - solarized_dark: Warm colors on dark background
    - nord: Cool, arctic-inspired colors
    - dracula: Vivid colors on dark background
    - one_dark: Modern theme (Atom/VS Code style)
    - gruvbox: Warm, retro colors

For more information, see README.md and THEMES.md
"""

__version__ = '1.1.0'
__author__ = 'FilterMate Team'

# Import main components
from . import view
from . import model
from . import datatypes
from . import delegate
from . import themes

# Expose commonly used classes
from .view import JsonView
from .model import JsonModel
from .datatypes import (
    DataType,
    NoneType,
    StrType,
    IntType,
    FloatType,
    BoolType,
    ListType,
    DictType,
    UrlType,
    FilepathType,
    RangeType,
    ChoicesType,
)
from .delegate import JsonDelegate

# Expose theme functions
from .themes import (
    get_current_theme,
    set_theme,
    get_available_themes,
    get_theme_display_names,
    Theme,
)

__all__ = [
    # Modules
    'view',
    'model',
    'datatypes',
    'delegate',
    'themes',
    
    # Main classes
    'JsonView',
    'JsonModel',
    'JsonDelegate',
    
    # Data type classes
    'DataType',
    'NoneType',
    'StrType',
    'IntType',
    'FloatType',
    'BoolType',
    'ListType',
    'DictType',
    'UrlType',
    'FilepathType',
    'RangeType',
    'ChoicesType',
    
    # Theme classes and functions
    'Theme',
    'get_current_theme',
    'set_theme',
    'get_available_themes',
    'get_theme_display_names',
]
