"""
FilterMate Adapters Module.

Implementation of ports for external systems (QGIS, databases, etc.).
Follows hexagonal architecture pattern.

Submodules:
    - backends: Multi-backend filter implementations
    - qgis: QGIS-specific adapters
    - repositories: Data persistence adapters
    - app_bridge: Bridge for legacy FilterMateApp integration
    
For backward compatibility imports, see adapters.compat module.
"""

# Re-export key components for convenience
from .backends import BackendFactory, BackendSelector, create_backend_factory

# Application bridge for legacy integration
from .app_bridge import (
    initialize_services,
    cleanup_services,
    is_initialized,
    get_filter_service,
    get_history_service,
    get_expression_service,
    get_backend_factory,
    get_auto_optimizer_service,
    layer_info_from_qgis_layer,
    execute_filter_legacy,
    validate_expression,
    parse_expression,
    push_history_entry,
    undo_filter,
    redo_filter,
    can_undo,
    can_redo,
)

__all__ = [
    # Backend factory
    'BackendFactory',
    'BackendSelector',
    'create_backend_factory',
    
    # Application bridge
    'initialize_services',
    'cleanup_services',
    'is_initialized',
    'get_filter_service',
    'get_history_service',
    'get_expression_service',
    'get_backend_factory',
    'get_auto_optimizer_service',
    'layer_info_from_qgis_layer',
    'execute_filter_legacy',
    'validate_expression',
    'parse_expression',
    'push_history_entry',
    'undo_filter',
    'redo_filter',
    'can_undo',
    'can_redo',
    
    # Task parameter building (v3.0)
    'TaskParameterBuilder',
    'TaskParameters',
    'FilteringConfig',
    'LayerInfo',
    'TaskType',
]

# Task parameter builder for MIG-024
try:
    from .task_builder import (
        TaskParameterBuilder,
        TaskParameters,
        FilteringConfig,
        LayerInfo,
        TaskType,
    )
except ImportError:
    # Fallback if not yet available
    TaskParameterBuilder = None
    TaskParameters = None
    FilteringConfig = None
    LayerInfo = None
    TaskType = None
