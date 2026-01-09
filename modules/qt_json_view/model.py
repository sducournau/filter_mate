# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy shim for qt_json_view.model

Migrated to ui/widgets/json_view/
"""
import warnings
warnings.warn("modules.qt_json_view is deprecated. Use ui.widgets.json_view instead.", DeprecationWarning)

from ...ui.widgets.json_view.model import JsonModel

__all__ = ['JsonModel']
