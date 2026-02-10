"""
FilterMate Core Services Module.

Business logic services for filtering, expression handling,
and history management.

Services:
- ExpressionService: Expression parsing, validation, and SQL conversion
- FilterService: Main filter orchestration
- HistoryService: Undo/redo history management
- BufferService: Buffer calculations and geometry simplification

All services are pure Python with no QGIS dependencies,
enabling true unit testing and clear separation of concerns.
"""
from .expression_service import (  # noqa: F401
    ExpressionService,
    ValidationResult,
    ParsedExpression,
)
from .filter_service import (  # noqa: F401
    FilterService,
    FilterRequest,
    FilterResponse,
)
from .history_service import (  # noqa: F401
    HistoryService,
    HistoryEntry,
    HistoryState,
)
from .buffer_service import (  # noqa: F401
    BufferService,
    BufferConfig,
    BufferEndCapStyle,
    BufferJoinStyle,
    SimplificationConfig,
    SimplificationResult,
    create_buffer_service,
)

# Note: BackendService is NOT exported here because:
# 1. It has QGIS dependencies (QObject, pyqtSignal) - not pure Python
# 2. It has a name collision with BackendInfo from core/ports
# Import directly: from core.services.backend_service import BackendService

# Note: FavoritesService is NOT exported here because:
# 1. It has QGIS dependencies (QObject, pyqtSignal) - not pure Python
# Import directly: from core.services.favorites_service import FavoritesService

# Note: LayerService is NOT exported here because:
# 1. It has QGIS dependencies (QObject, pyqtSignal) - not pure Python
# Import directly: from core.services.layer_service import LayerService

# Note: PostgresSessionManager is NOT exported here because:
# 1. It has QGIS dependencies (QObject, pyqtSignal) - not pure Python
# Import directly: from core.services.postgres_session_manager import PostgresSessionManager

# Note: TaskOrchestrator is NOT exported here because:
# 1. It has QGIS dependencies (QTimer, QgsApplication) - not pure Python
# Import directly: from core.services.task_orchestrator import TaskOrchestrator

# EPIC-1 Phase 14.5: SourceSubsetBufferBuilder service
# NOT exported here - has QGIS dependencies (QgsExpression)
# Import directly: from core.services.source_subset_buffer_builder import build_source_subset_buffer_config

# EPIC-1 Phase 14.6: SourceLayerFilterExecutor service
# NOT exported here - has QGIS dependencies (QgsExpression, QgsFeature)
# Import directly: from core.services.source_layer_filter_executor import execute_source_layer_filtering

# EPIC-1 Phase 14.7: TaskRunOrchestrator service
# NOT exported here - orchestration logic for run() method
# Import directly: from core.services.task_run_orchestrator import execute_task_run

# EPIC-1 Phase 14.8: CanvasRefreshService
# NOT exported here - has QGIS dependencies (iface, QgsProject)
# Import directly: from core.services.canvas_refresh_service import single_canvas_refresh

__all__ = [
    # Expression Service
    'ExpressionService',
    'ValidationResult',
    'ParsedExpression',
    # Filter Service
    'FilterService',
    'FilterRequest',
    'FilterResponse',
    # History Service
    'HistoryService',
    'HistoryEntry',
    'HistoryState',
    # Buffer Service
    'BufferService',
    'BufferConfig',
    'BufferEndCapStyle',
    'BufferJoinStyle',
    'SimplificationConfig',
    'SimplificationResult',
    'create_buffer_service',
]
