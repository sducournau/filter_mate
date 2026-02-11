"""
FilterMate Adapters Module.

Implementation of ports for external systems (QGIS, databases, etc.).
Follows hexagonal architecture pattern.

Submodules:
    - backends: Multi-backend filter implementations
    - qgis: QGIS-specific adapters
    - repositories: Data persistence adapters
    - app_bridge: Bridge for legacy FilterMateApp integration

Follows hexagonal architecture pattern.
"""

# Re-export key components for convenience
from .backends import BackendFactory, BackendSelector, create_backend_factory  # noqa: F401

# v4.0.1: Backend registry for hexagonal architecture compliance
from .backend_registry import (  # noqa: F401
    BackendRegistry,
    get_backend_registry,
    reset_backend_registry,
)

# Application bridge for legacy integration
from .app_bridge import (  # noqa: F401
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

    # Task bridge for Strangler Fig migration (v3.0 MIG-023)
    'TaskBridge',
    'BridgeResult',
    'get_task_bridge',

    # Database manager (v3.0 MIG-024)
    'DatabaseManager',
]

# Task parameter builder for MIG-024
try:
    from .task_builder import (  # noqa: F401
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

# Task bridge for MIG-023 (Strangler Fig pattern)
try:
    from .task_bridge import (  # noqa: F401
        TaskBridge,
        BridgeResult,
        get_task_bridge,
    )
except ImportError:
    # Fallback if not yet available
    TaskBridge = None
    BridgeResult = None
    get_task_bridge = None

# Database manager for MIG-024 (God Class reduction)
try:
    from .database_manager import DatabaseManager  # noqa: F401
except ImportError:
    DatabaseManager = None
