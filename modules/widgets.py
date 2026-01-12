# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/widgets

All widget classes have been moved to ui/widgets/
This file provides backward compatibility only.

Migration: from .ui.widgets import QgsCheckableComboBoxFeaturesListPickerWidget, QgsCheckableComboBoxLayer
"""
import warnings

warnings.warn(
    "modules.widgets is deprecated. Use ui.widgets instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from ..ui.widgets import (
    QgsCheckableComboBoxFeaturesListPickerWidget,
    QgsCheckableComboBoxLayer
)

__all__ = [
    'QgsCheckableComboBoxFeaturesListPickerWidget',
    'QgsCheckableComboBoxLayer',
]
