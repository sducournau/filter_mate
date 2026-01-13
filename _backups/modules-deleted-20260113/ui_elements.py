# -*- coding: utf-8 -*-
"""
DEPRECATED: Use ui.config.ui_elements instead

Shim module for backward compatibility.
This file will be removed in v5.0.

Migration guide:
    OLD: from modules.ui_elements import SPACERS, LAYOUTS
    NEW: from ui.config import SPACERS, LAYOUTS
    
Or:
    from ui.config.ui_elements import SPACERS, LAYOUTS
"""

import warnings

warnings.warn(
    "modules.ui_elements is deprecated. Use ui.config or ui.config.ui_elements instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from ui.config.ui_elements import (
    SPACERS,
    LAYOUTS,
    ALL_SPACERS,
    ALL_LAYOUTS,
    get_spacers_by_section,
    get_layouts_by_section,
    get_spacer_size,
    get_layout_spacing,
    get_section_names,
    find_element_section,
)

__all__ = [
    'SPACERS',
    'LAYOUTS',
    'ALL_SPACERS',
    'ALL_LAYOUTS',
    'get_spacers_by_section',
    'get_layouts_by_section',
    'get_spacer_size',
    'get_layout_spacing',
    'get_section_names',
    'find_element_section',
]
