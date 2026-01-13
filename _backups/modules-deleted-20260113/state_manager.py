# -*- coding: utf-8 -*-
"""
DEPRECATED: Use infrastructure.state_manager instead

Shim module for backward compatibility.
This file will be removed in v5.0.

Migration guide:
    OLD: from modules.state_manager import LayerStateManager, ProjectStateManager
    NEW: from infrastructure.state_manager import LayerStateManager, ProjectStateManager
    
Or use shorthand:
    from infrastructure import LayerStateManager, ProjectStateManager
"""

import warnings

warnings.warn(
    "modules.state_manager is deprecated. Use infrastructure.state_manager instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from infrastructure.state_manager import (
    LayerStateManager,
    ProjectStateManager,
    get_layer_state_manager,
    get_project_state_manager,
    reset_state_managers,
)

__all__ = [
    'LayerStateManager',
    'ProjectStateManager',
    'get_layer_state_manager',
    'get_project_state_manager',
    'reset_state_managers',
]
