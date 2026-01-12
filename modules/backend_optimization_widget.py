"""
Shim module for backend optimization widget.

DEPRECATED: This module is a compatibility shim. 
Use ui.dialogs.optimization_dialog directly.

This shim provides backward compatibility for imports from:
  from .modules.backend_optimization_widget import BackendOptimizationDialog

Redirects to:
  from ui.dialogs.optimization_dialog import OptimizationDialog as BackendOptimizationDialog

The BackendOptimizationDialog is the same as OptimizationDialog as it now
includes backend-specific tabs for PostgreSQL, Spatialite, and OGR settings.

Migration: EPIC-1 Phase E6 - Strangler Fig Pattern
"""

import warnings
import logging

logger = logging.getLogger(__name__)

# Emit deprecation warning
warnings.warn(
    "modules.backend_optimization_widget is deprecated. "
    "Use ui.dialogs.optimization_dialog instead.",
    DeprecationWarning,
    stacklevel=2
)

# Log for debugging
logger.info(
    "SHIM: modules.backend_optimization_widget redirecting to ui.dialogs.optimization_dialog"
)

# Re-export from new location with old name for compatibility
try:
    from ui.dialogs.optimization_dialog import (
        OptimizationDialog as BackendOptimizationDialog
    )
    
    __all__ = ['BackendOptimizationDialog']
    
except ImportError:
    # If new module not found, try relative import
    try:
        from ..ui.dialogs.optimization_dialog import (
            OptimizationDialog as BackendOptimizationDialog
        )
        
        __all__ = ['BackendOptimizationDialog']
        
    except ImportError as e:
        logger.warning(f"Could not import BackendOptimizationDialog: {e}")
        # Define stub for graceful degradation
        BackendOptimizationDialog = None
        __all__ = []
