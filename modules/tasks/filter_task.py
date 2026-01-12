# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/tasks/filter_task.py

This module has been migrated to core/tasks/filter_task.py
This shim provides backward compatibility for imports from modules.tasks.filter_task

Migration:
    OLD: from modules.tasks.filter_task import FilterEngineTask
    NEW: from core.tasks.filter_task import FilterEngineTask

Date: January 2026
EPIC: EPIC-1 (Suppression du dossier modules/)
"""
import warnings

warnings.warn(
    "modules.tasks.filter_task is deprecated. Use core.tasks.filter_task instead. "
    "This shim will be removed in FilterMate v5.0.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from ...core.tasks.filter_task import FilterEngineTask

__all__ = ['FilterEngineTask']
