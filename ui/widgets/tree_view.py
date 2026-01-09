# -*- coding: utf-8 -*-
"""
FilterMate - Tree View Widgets
Provides JsonModel for JSON tree visualization.
"""

# Import from local json_view shim (no direct modules/ dependency)
from ui.widgets.json_view import JsonModel, JsonSortFilterProxyModel, is_available

__all__ = ['JsonModel', 'JsonSortFilterProxyModel', 'is_available']
