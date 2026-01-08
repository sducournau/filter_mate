"""
FilterMate Core Module.

Pure Python business logic with no QGIS dependencies.
This layer follows the Hexagonal Architecture pattern:

- domain/: Value objects, entities, and domain logic
- ports/: Abstract interfaces for external dependencies
- services/: Business logic orchestration

Usage:
    from core.domain import FilterExpression, FilterResult, LayerInfo
    from core.ports import BackendPort, CachePort
    from core.services import FilterService, ExpressionService
"""

# Re-export commonly used types for convenience
from .domain import (
    FilterExpression,
    FilterResult,
    FilterStatus,
    LayerInfo,
    GeometryType,
    ProviderType,
    SpatialPredicate,
    OptimizationConfig,
)

from .ports import (
    BackendPort,
    BackendInfo,
    BackendCapability,
    CachePort,
    CacheStats,
    LayerRepositoryPort,
)

from .services import (
    FilterService,
    FilterRequest,
    FilterResponse,
    ExpressionService,
    ValidationResult,
    HistoryService,
    HistoryEntry,
)

__all__ = [
    # Domain
    'FilterExpression',
    'FilterResult',
    'FilterStatus',
    'LayerInfo',
    'GeometryType',
    'ProviderType',
    'SpatialPredicate',
    'OptimizationConfig',
    # Ports
    'BackendPort',
    'BackendInfo',
    'BackendCapability',
    'CachePort',
    'CacheStats',
    'LayerRepositoryPort',
    # Services
    'FilterService',
    'FilterRequest',
    'FilterResponse',
    'ExpressionService',
    'ValidationResult',
    'HistoryService',
    'HistoryEntry',
]
