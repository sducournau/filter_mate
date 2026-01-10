"""
Tasks Module - LEGACY SHIM

DEPRECATED: This module is a backward compatibility shim.

NEW IMPORTS (EPIC-1 v3.0):
- infrastructure.utils.task_utils for database utilities
- infrastructure.cache.query_cache for expression caching

Refactored from appTasks.py during Phase 3 (Dec 2025).

This module provides backwards-compatible imports for all task-related classes and utilities.

Extraction Status:
- task_utils.py: Migrated to infrastructure/utils/task_utils.py ✅ EPIC-1
- query_cache.py: Migrated to infrastructure/cache/query_cache.py ✅ EPIC-1
- geometry_cache.py: SourceGeometryCache class ✅ Phase 3a
- layer_management_task.py: LayersManagementEngineTask class ✅ Phase 3b
- filter_task.py: FilterEngineTask class (4165 lines) ✅ Phase 3c

Current Status: EPIC-1 Option A2 migration in progress
"""

import warnings

# Show deprecation warning
warnings.warn(
    "modules.tasks: Importing from modules.tasks is deprecated. "
    "Use 'from infrastructure.utils import ...' for task_utils functions, "
    "or 'from infrastructure.cache import ...' for query_cache.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export FilterEngineTask from new module (Phase 3c)
from .filter_task import FilterEngineTask

# Re-export LayersManagementEngineTask from new module (Phase 3b)
from .layer_management_task import LayersManagementEngineTask

# Import from infrastructure (EPIC-1 migration)
from infrastructure.utils import (
    spatialite_connect,
    safe_spatialite_connect,
    sqlite_execute_with_retry,
    ensure_db_directory_exists,
    get_best_metric_crs,
    should_reproject_layer,
    needs_metric_conversion,
    SQLITE_TIMEOUT,
    SQLITE_MAX_RETRIES,
    SQLITE_RETRY_DELAY,
    SQLITE_MAX_RETRY_TIME,
    MESSAGE_TASKS_CATEGORIES
)

from infrastructure.cache import SourceGeometryCache

__all__ = [
    # Main task classes
    'FilterEngineTask',              # From filter_task.py (Phase 3c - ✅)
    'LayersManagementEngineTask',    # From layer_management_task.py (Phase 3b - ✅)
    
    # Constants
    'MESSAGE_TASKS_CATEGORIES',      # From infrastructure.utils.task_utils (EPIC-1)
    
    # Utilities (from infrastructure.utils.task_utils - EPIC-1 - ✅)
    'spatialite_connect',
    'safe_spatialite_connect',
    'sqlite_execute_with_retry',
    'ensure_db_directory_exists',
    'get_best_metric_crs',
    'should_reproject_layer',
    'needs_metric_conversion',
    'SQLITE_TIMEOUT',
    'SQLITE_MAX_RETRIES',
    'SQLITE_RETRY_DELAY',
    'SQLITE_MAX_RETRY_TIME',
    
    # Cache (from geometry_cache.py - Phase 3a - ✅)
    'SourceGeometryCache',
    
    # Progressive filtering (v2.5.9)
    'ProgressiveFilterExecutor',
    'TwoPhaseFilter',
    'LazyResultIterator',
    'FilterStrategy',
    
    # Multi-step filtering (v2.5.10)
    'MultiStepFilterOptimizer',
    'FilterPlanBuilder',
    'SelectivityEstimator',
    
    # Expression evaluation (v2.5.10)
    'ExpressionEvaluationTask',
    'ExpressionEvaluationManager',
    'get_expression_manager',
]

# Import progressive filter components
try:
    from .progressive_filter import (
        ProgressiveFilterExecutor,
        TwoPhaseFilter,
        LazyResultIterator,
        FilterStrategy,
        LayerProperties,
        FilterResult
    )
except ImportError:
    ProgressiveFilterExecutor = None
    TwoPhaseFilter = None
    LazyResultIterator = None
    FilterStrategy = None

# Import multi-step filter components (v2.5.10)
try:
    from .multi_step_filter import (
        MultiStepFilterOptimizer,
        FilterPlanBuilder,
        SelectivityEstimator,
        LayerStatistics,
        get_optimal_filter_plan
    )
except ImportError:
    MultiStepFilterOptimizer = None
    FilterPlanBuilder = None
    SelectivityEstimator = None

# Import expression evaluation task (v2.5.10)
try:
    from .expression_evaluation_task import (
        ExpressionEvaluationTask,
        ExpressionEvaluationManager,
        get_expression_manager
    )
except ImportError:
    ExpressionEvaluationTask = None
    ExpressionEvaluationManager = None
    get_expression_manager = None

# Version info
__version__ = '2.5.10'
__phase__ = 'performance'
__status__ = 'Multi-step adaptive filtering for large datasets'
