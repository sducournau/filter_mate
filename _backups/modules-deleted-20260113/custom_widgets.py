"""
DEPRECATED: modules.custom_widgets

This module is deprecated and will be removed in v5.0.
Use ui.widgets.custom_widgets instead.

Migration:
    # Old (deprecated):
    from modules.custom_widgets import QgsCheckableComboBoxLayer
    
    # New:
    from ui.widgets.custom_widgets import QgsCheckableComboBoxLayer
"""
import warnings

warnings.warn(
    "modules.custom_widgets is deprecated. Use ui.widgets.custom_widgets instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility
from ui.widgets.custom_widgets import QgsCheckableComboBoxLayer

__all__ = ['QgsCheckableComboBoxLayer']
