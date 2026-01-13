# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/widgets

All widget classes have been moved to ui/widgets/custom_widgets.py
This file provides backward compatibility only.

Migration: from ui.widgets.custom_widgets import QgsCheckableComboBoxFeaturesListPickerWidget, QgsCheckableComboBoxLayer
"""
import warnings

warnings.warn(
    "modules.widgets is deprecated. Use ui.widgets.custom_widgets instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from ..ui.widgets.custom_widgets import (
    ItemDelegate,
    ListWidgetWrapper,
    QgsCheckableComboBoxFeaturesListPickerWidget,
    QgsCheckableComboBoxLayer
)

# Also re-export safe_iterate_features for compatibility
from ..infrastructure.utils import safe_iterate_features

__all__ = [
    'ItemDelegate',
    'ListWidgetWrapper',
    'QgsCheckableComboBoxFeaturesListPickerWidget',
    'QgsCheckableComboBoxLayer',
    'safe_iterate_features',
]
