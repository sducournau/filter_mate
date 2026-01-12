"""
DEPRECATED - LayersManagementEngineTask migration shim

This module has been migrated to core/tasks/ as part of EPIC-1.
Imports are preserved for backward compatibility but will be removed in v4.0.

Migration: modules/tasks/layer_management_task.py → core/tasks/layer_management_task.py
Date: January 2026
EPIC: EPIC-1 (Suppression du dossier modules/)
Reduction: 1818 lines → 30 lines (-98%)

New location:
    from core.tasks import LayersManagementEngineTask
"""

import warnings

warnings.warn(
    "modules.tasks.layer_management_task is deprecated. "
    "Use core.tasks.layer_management_task instead. "
    "This shim will be removed in FilterMate v4.0.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from ...core.tasks.layer_management_task import LayersManagementEngineTask

__all__ = ['LayersManagementEngineTask']
