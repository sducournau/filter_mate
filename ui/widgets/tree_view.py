# -*- coding: utf-8 -*-
"""
FilterMate - Tree View Widgets
Provides JsonModel for JSON tree visualization.
"""

try:
    from modules.qt_json_view.model import JsonModel
except ImportError:
    # Fallback if module not available
    JsonModel = None

__all__ = ['JsonModel']
