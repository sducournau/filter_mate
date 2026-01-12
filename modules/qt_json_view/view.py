# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy shim for qt_json_view.view

Migrated to ui/widgets/json_view/
"""
import warnings
warnings.warn("modules.qt_json_view is deprecated. Use ui.widgets.json_view instead.", DeprecationWarning)

from ...ui.widgets.json_view.view import JsonView

__all__ = ['JsonView']
