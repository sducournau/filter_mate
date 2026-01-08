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
