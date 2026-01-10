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

# v4.0 EPIC-1 Phase E1: Export module
from .export import (
    LayerExporter,
    ExportConfig,
    ExportResult,
    ExportFormat,
    StyleExporter,
    StyleFormat,
    save_layer_style,
    validate_export_parameters,
    ExportValidationResult,
)

# v4.0 EPIC-1 Phase E2: Geometry module
from .geometry import (
    apply_qgis_buffer,
    create_buffered_memory_layer,
    BufferConfig,
    aggressive_geometry_repair,
    repair_invalid_geometries,
    convert_geometry_collection_to_multipolygon,
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
    # Export (v4.0 EPIC-1 Phase E1)
    'LayerExporter',
    'ExportConfig',
    'ExportResult',
    'ExportFormat',
    'StyleExporter',
    'StyleFormat',
    'save_layer_style',
    'validate_export_parameters',
    'ExportValidationResult',
    # Geometry (v4.0 EPIC-1 Phase E2)
    'apply_qgis_buffer',
    'create_buffered_memory_layer',
    'BufferConfig',
    'aggressive_geometry_repair',
    'repair_invalid_geometries',
    'convert_geometry_collection_to_multipolygon',
]
