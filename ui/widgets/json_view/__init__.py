"""
FilterMate UI Widgets - JSON View.

This module provides JSON tree viewing capabilities for QGIS.
Migrated from modules/qt_json_view/ for FilterMate v4.0.

v4.0.7: Added SearchableJsonView with integrated search bar.

Usage:
    from ui.widgets.json_view import JsonModel, JsonView
    from ui.widgets.json_view import SearchableJsonView  # With search bar
"""

# Local imports from migrated qt_json_view files
from .model import JsonModel, JsonSortFilterProxyModel
from .view import JsonView
from .searchable_view import SearchableJsonView  # v4.0.7: New searchable view
from .datatypes import (
    DataType, NoneType, StrType, IntType, FloatType, BoolType,
    ListType, DictType, UrlType, FilepathType, RangeType, ChoicesType,
)
from .delegate import JsonDelegate
from .themes import (
    Theme, get_current_theme, set_theme, get_available_themes,
    get_theme_display_names,
)

_AVAILABLE = True


def is_available() -> bool:
    """Check if JSON view module is available."""
    return _AVAILABLE


__all__ = [
    'is_available',
    'JsonModel',
    'JsonSortFilterProxyModel',
    'JsonView',
    'JsonDelegate',
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
    'Theme',
    'get_current_theme',
    'set_theme',
    'get_available_themes',
    'get_theme_display_names',
]
