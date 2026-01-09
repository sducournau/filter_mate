# -*- coding: utf-8 -*-
"""
FilterMate Modules Package (DEPRECATED)

⚠️ DEPRECATION WARNING - FilterMate v3.0 ⚠️

This package is deprecated and will be removed in FilterMate v4.0.

Migration Guide:
- modules.appUtils → infrastructure.utils + adapters.database_manager
- modules.appTasks → adapters.qgis.tasks
- modules.backends → adapters.backends
- modules.config_* → config.config

See docs/migration-v3.md for complete migration guide.

This package contains all core modules for FilterMate plugin:
- appUtils: Database connections and utility functions
- appTasks: Async task definitions (QgsTask)
- backends: Multi-backend system (PostgreSQL, Spatialite, OGR, Memory)
- tasks: Specialized task implementations
- widgets: Custom UI widgets
- config_*: Configuration management modules

v2.8.6: Package initialization for proper relative imports
v3.0.0: DEPRECATED - Use core/, adapters/, infrastructure/ instead
"""
import warnings
from typing import Any

# Version info for deprecation tracking
__deprecated__ = True
__deprecated_since__ = "3.0.0"
__removal_version__ = "4.0.0"

# Track which modules have been accessed (for reporting)
_accessed_modules = set()


def _emit_deprecation_warning(module_name: str) -> None:
    """
    Emit a deprecation warning for legacy module access.
    
    Args:
        module_name: Name of the deprecated module being accessed
    """
    # Get the mapping of old → new modules
    migration_map = {
        "appUtils": "infrastructure.utils or adapters.database_manager",
        "appTasks": "adapters.qgis.tasks",
        "backends": "adapters.backends",
        "config_helpers": "config.config",
        "config_migration": "config.config",
        "ui_styles": "ui.styles",
        "tasks": "adapters.qgis.tasks",
        "widgets": "ui.widgets",
    }
    
    alternative = migration_map.get(module_name, "core.*, adapters.*, or infrastructure.*")
    
    warnings.warn(
        f"Importing from 'modules.{module_name}' is deprecated since FilterMate v3.0. "
        f"Use '{alternative}' instead. "
        f"This module will be removed in FilterMate v4.0. "
        f"See docs/migration-v3.md for migration guide.",
        DeprecationWarning,
        stacklevel=3
    )
    
    # Track access for potential reporting
    _accessed_modules.add(module_name)


def __getattr__(name: str) -> Any:
    """
    Intercept attribute access to emit deprecation warnings.
    
    This is called when accessing modules.* attributes that don't exist
    in this __init__.py file.
    """
    # List of known legacy modules
    legacy_modules = {
        "appUtils",
        "appTasks", 
        "backends",
        "config_helpers",
        "config_migration",
        "ui_styles",
        "tasks",
        "widgets",
    }
    
    if name in legacy_modules:
        _emit_deprecation_warning(name)
        
        # Still allow the import to work for backwards compatibility
        import importlib
        return importlib.import_module(f".{name}", __package__)
    
    # For unknown attributes, raise standard AttributeError
    raise AttributeError(f"module 'modules' has no attribute '{name}'")


def get_deprecated_usage_report() -> dict:
    """
    Get a report of deprecated module usage.
    
    Returns:
        Dictionary with usage statistics for deprecation tracking.
    """
    return {
        "accessed_modules": list(_accessed_modules),
        "total_accesses": len(_accessed_modules),
        "deprecated_since": __deprecated_since__,
        "removal_version": __removal_version__,
    }


# This file is required for Python to recognize 'modules' as a package,
# enabling relative imports like 'from ..appUtils import ...'
