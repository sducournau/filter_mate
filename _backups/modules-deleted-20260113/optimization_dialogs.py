"""
Shim module for optimization dialogs.

DEPRECATED: This module is a compatibility shim. 
Use ui.dialogs.optimization_dialog directly.

This shim provides backward compatibility for imports from:
  from .modules.optimization_dialogs import OptimizationRecommendationDialog
  from .modules.optimization_dialogs import OptimizationSettingsDialog

Redirects to:
  from ui.dialogs.optimization_dialog import RecommendationDialog as OptimizationRecommendationDialog
  from ui.dialogs.optimization_dialog import OptimizationDialog as OptimizationSettingsDialog

Migration: EPIC-1 Phase E6 - Strangler Fig Pattern
"""

import warnings
import logging

logger = logging.getLogger(__name__)

# Emit deprecation warning
warnings.warn(
    "modules.optimization_dialogs is deprecated. "
    "Use ui.dialogs.optimization_dialog instead.",
    DeprecationWarning,
    stacklevel=2
)

# Log for debugging
logger.info(
    "SHIM: modules.optimization_dialogs redirecting to ui.dialogs.optimization_dialog"
)

# Re-export from new location with old names for compatibility
try:
    from ui.dialogs.optimization_dialog import (
        RecommendationDialog as OptimizationRecommendationDialog,
        OptimizationDialog as OptimizationSettingsDialog,
        OptimizationSettings,
        OptimizationType
    )
    
    __all__ = [
        'OptimizationRecommendationDialog',
        'OptimizationSettingsDialog',
        'OptimizationSettings',
        'OptimizationType'
    ]
    
except ImportError:
    # If new module not found, try relative import
    try:
        from ..ui.dialogs.optimization_dialog import (
            RecommendationDialog as OptimizationRecommendationDialog,
            OptimizationDialog as OptimizationSettingsDialog,
            OptimizationSettings,
            OptimizationType
        )
        
        __all__ = [
            'OptimizationRecommendationDialog',
            'OptimizationSettingsDialog',
            'OptimizationSettings',
            'OptimizationType'
        ]
        
    except ImportError as e:
        logger.warning(f"Could not import optimization dialogs: {e}")
        # Define stub classes for graceful degradation
        OptimizationRecommendationDialog = None
        OptimizationSettingsDialog = None
        OptimizationSettings = None
        OptimizationType = None
        __all__ = []
