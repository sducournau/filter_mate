"""
FilterMate Core Services Module.

Business logic services for filtering, expression handling,
and history management.

Services:
- ExpressionService: Expression parsing, validation, and SQL conversion
- FilterService: Main filter orchestration
- HistoryService: Undo/redo history management

All services are pure Python with no QGIS dependencies,
enabling true unit testing and clear separation of concerns.
"""
from .expression_service import (
    ExpressionService,
    ValidationResult,
    ParsedExpression,
)
from .filter_service import (
    FilterService,
    FilterRequest,
    FilterResponse,
)
from .history_service import (
    HistoryService,
    HistoryEntry,
    HistoryState,
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
]
