# -*- coding: utf-8 -*-
"""
DEPRECATED: Use ui.config instead

Shim module for backward compatibility.
This file will be removed in v5.0.

Migration guide:
    OLD: from modules.ui_config import UIConfig, DisplayProfile
    NEW: from ui.config import UIConfig, DisplayProfile
"""

import warnings

warnings.warn(
    "modules.ui_config is deprecated. Use ui.config instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from ui.config import UIConfig, DisplayProfile

__all__ = ['UIConfig', 'DisplayProfile']
