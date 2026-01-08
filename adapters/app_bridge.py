# -*- coding: utf-8 -*-
"""
Application Bridge for FilterMate v3.0

Bridges the legacy FilterMateApp with the new hexagonal architecture services.
Provides a gradual migration path from the God Class to the new architecture.

This module:
- Wraps new services for use by legacy FilterMateApp
- Provides dependency injection setup
- Handles backward compatibility

Usage in filter_mate_app.py:
    from adapters.app_bridge import (
        get_filter_service,
        get_history_service,
        get_backend_factory,
        initialize_services,
    )
    
    # Initialize once at plugin startup
    initialize_services(config)
    
    # Use services
    filter_service = get_filter_service()
    result = filter_service.apply_filter(request)

Part of FilterMate Hexagonal Architecture v3.0
Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, Dict, Any, TYPE_CHECKING

from core.domain.filter_expression import FilterExpression, ProviderType
from core.domain.filter_result import FilterResult, FilterStatus
from core.domain.layer_info import LayerInfo, GeometryType
from core.domain.optimization_config import OptimizationConfig
from core.services.filter_service import FilterService, FilterRequest, FilterResponse
from core.services.expression_service import ExpressionService
from core.services.history_service import HistoryService, HistoryEntry
from core.services.auto_optimizer import AutoOptimizer, get_auto_optimizer

from adapters.backends.factory import BackendFactory, create_backend_factory, BackendSelector

if TYPE_CHECKING:
    from qgis.core import QgsVectorLayer

logger = logging.getLogger('FilterMate.AppBridge')


# ============================================================================
# Service Singletons
# ============================================================================

_filter_service: Optional[FilterService] = None
_history_service: Optional[HistoryService] = None
_expression_service: Optional[ExpressionService] = None
_backend_factory: Optional[BackendFactory] = None
_initialized: bool = False


def initialize_services(config: Optional[Dict[str, Any]] = None) -> None:
    """
    Initialize all services with optional configuration.
    
    Should be called once at plugin startup.
    
    Args:
        config: Optional configuration dictionary
    """
    global _filter_service, _history_service, _expression_service
    global _backend_factory, _initialized
    
    if _initialized:
        logger.debug("Services already initialized")
        return
    
    config = config or {}
    
    try:
        # Initialize backend factory
        _backend_factory = create_backend_factory(config.get('backends', {}))
        
        # Initialize expression service
        _expression_service = ExpressionService()
        
        # Initialize history service
        history_config = config.get('history', {})
        _history_service = HistoryService(
            max_depth=history_config.get('max_depth', 50)
        )
        
        # Initialize filter service
        _filter_service = FilterService(
            backend_factory=_backend_factory,
            expression_service=_expression_service,
            cache=None  # Cache can be added later
        )
        
        _initialized = True
        logger.info("FilterMate services initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise


def cleanup_services() -> None:
    """
    Cleanup all services on plugin unload.
    """
    global _filter_service, _history_service, _expression_service
    global _backend_factory, _initialized
    
    try:
        if _backend_factory:
            _backend_factory.cleanup()
        
        if _history_service:
            _history_service.clear()
        
        _filter_service = None
        _history_service = None
        _expression_service = None
        _backend_factory = None
        _initialized = False
        
        logger.info("FilterMate services cleaned up")
        
    except Exception as e:
        logger.warning(f"Error during service cleanup: {e}")


def is_initialized() -> bool:
    """Check if services are initialized."""
    return _initialized


# ============================================================================
# Service Accessors
# ============================================================================

def get_filter_service() -> FilterService:
    """
    Get the filter service instance.
    
    Returns:
        FilterService instance
        
    Raises:
        RuntimeError: If services not initialized
    """
    if not _initialized or _filter_service is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _filter_service


def get_history_service() -> HistoryService:
    """
    Get the history service instance.
    
    Returns:
        HistoryService instance
        
    Raises:
        RuntimeError: If services not initialized
    """
    if not _initialized or _history_service is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _history_service


def get_expression_service() -> ExpressionService:
    """
    Get the expression service instance.
    
    Returns:
        ExpressionService instance
        
    Raises:
        RuntimeError: If services not initialized
    """
    if not _initialized or _expression_service is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _expression_service


def get_backend_factory() -> BackendFactory:
    """
    Get the backend factory instance.
    
    Returns:
        BackendFactory instance
        
    Raises:
        RuntimeError: If services not initialized
    """
    if not _initialized or _backend_factory is None:
        raise RuntimeError("Services not initialized. Call initialize_services() first.")
    return _backend_factory


def get_auto_optimizer_service() -> AutoOptimizer:
    """
    Get the auto-optimizer service.
    
    Returns:
        AutoOptimizer instance
    """
    return get_auto_optimizer()


# ============================================================================
# QGIS Layer Helpers
# ============================================================================

def layer_info_from_qgis_layer(layer: 'QgsVectorLayer') -> LayerInfo:
    """
    Create LayerInfo from a QGIS vector layer.
    
    Args:
        layer: QGIS vector layer
        
    Returns:
        LayerInfo domain object
    """
    from qgis.core import QgsWkbTypes
    
    # Determine provider type
    provider_type = ProviderType.from_qgis_provider(layer.providerType())
    
    # Determine geometry type
    wkb_type = layer.wkbType()
    geometry_type = GeometryType.from_qgis_wkb_type(wkb_type)
    
    # Get CRS
    crs = layer.crs()
    crs_auth_id = crs.authid() if crs.isValid() else ""
    
    # Check for spatial index
    has_spatial_index = _check_spatial_index(layer)
    
    # Get table info for database layers
    schema_name = ""
    table_name = ""
    if provider_type in (ProviderType.POSTGRESQL, ProviderType.SPATIALITE):
        uri = layer.dataProvider().dataSourceUri()
        schema_name, table_name = _parse_db_uri(uri, provider_type)
    
    return LayerInfo(
        layer_id=layer.id(),
        name=layer.name(),
        provider_type=provider_type,
        feature_count=layer.featureCount(),
        geometry_type=geometry_type,
        crs_auth_id=crs_auth_id,
        is_valid=layer.isValid(),
        source_path=layer.source(),
        has_spatial_index=has_spatial_index,
        schema_name=schema_name,
        table_name=table_name
    )


def _check_spatial_index(layer: 'QgsVectorLayer') -> bool:
    """Check if layer has spatial index."""
    try:
        provider = layer.dataProvider()
        if hasattr(provider, 'hasSpatialIndex'):
            return provider.hasSpatialIndex() in [1, True]
    except Exception:
        pass
    return False


def _parse_db_uri(uri: str, provider_type: ProviderType) -> tuple:
    """Parse schema and table from database URI."""
    import re
    
    schema_name = ""
    table_name = ""
    
    if provider_type == ProviderType.POSTGRESQL:
        # Parse PostgreSQL URI: table="schema"."table"
        match = re.search(r'table="([^"]+)"\."([^"]+)"', uri)
        if match:
            schema_name = match.group(1)
            table_name = match.group(2)
        else:
            # Try without schema: table="table"
            match = re.search(r'table="([^"]+)"', uri)
            if match:
                schema_name = "public"
                table_name = match.group(1)
                
    elif provider_type == ProviderType.SPATIALITE:
        # Parse Spatialite URI: table="table_name"
        match = re.search(r'table="([^"]+)"', uri)
        if match:
            table_name = match.group(1)
    
    return schema_name, table_name


# ============================================================================
# Legacy Compatibility Functions
# ============================================================================

def create_filter_expression_from_legacy(
    raw_expression: str,
    layer: 'QgsVectorLayer',
    buffer_value: float = 0.0,
    buffer_segments: int = 16
) -> FilterExpression:
    """
    Create FilterExpression from legacy filter parameters.
    
    This bridges the old FilterMateApp parameter style to the
    new domain object style.
    
    Args:
        raw_expression: Raw QGIS expression string
        layer: Source QGIS layer
        buffer_value: Buffer distance (0 for no buffer)
        buffer_segments: Number of buffer segments
        
    Returns:
        FilterExpression domain object
    """
    provider_type = ProviderType.from_qgis_provider(layer.providerType())
    
    return FilterExpression.create(
        raw=raw_expression,
        provider=provider_type,
        source_layer_id=layer.id(),
        buffer_value=buffer_value,
        buffer_segments=buffer_segments
    )


def convert_filter_result_to_legacy(result: FilterResult) -> Dict[str, Any]:
    """
    Convert FilterResult to legacy dictionary format.
    
    Args:
        result: FilterResult domain object
        
    Returns:
        Dictionary compatible with legacy code
    """
    return {
        'success': result.is_success,
        'feature_count': result.count,
        'feature_ids': list(result.feature_ids),
        'expression': result.expression_raw,
        'execution_time_ms': result.execution_time_ms,
        'backend': result.backend_name,
        'error': result.error_message,
        'is_cached': result.is_cached,
        'timestamp': result.timestamp.isoformat() if result.timestamp else None,
    }


def execute_filter_legacy(
    layer: 'QgsVectorLayer',
    expression: str,
    target_layer_ids: list,
    buffer_value: float = 0.0,
    use_optimization: bool = True
) -> Dict[str, Any]:
    """
    Execute filter using legacy-compatible interface.
    
    This is a convenience function for gradual migration from
    FilterMateApp to the new services.
    
    Args:
        layer: Source QGIS layer
        expression: Raw expression string
        target_layer_ids: List of target layer IDs
        buffer_value: Buffer distance
        use_optimization: Enable optimizations
        
    Returns:
        Legacy-format result dictionary
    """
    if not _initialized:
        initialize_services()
    
    try:
        # Create expression
        filter_expr = create_filter_expression_from_legacy(
            raw_expression=expression,
            layer=layer,
            buffer_value=buffer_value
        )
        
        # Get layer info
        layer_info = layer_info_from_qgis_layer(layer)
        
        # Create request
        request = FilterRequest(
            expression=filter_expr,
            source_layer_id=layer.id(),
            target_layer_ids=target_layer_ids,
            use_cache=use_optimization,
            optimization_config=OptimizationConfig.default() if use_optimization else OptimizationConfig.disabled()
        )
        
        # Execute
        response = _filter_service.apply_filter(request)
        
        # Convert results
        results = {}
        for layer_id, result in response.results.items():
            results[layer_id] = convert_filter_result_to_legacy(result)
        
        return {
            'success': response.is_success,
            'total_matches': response.total_matches,
            'total_time_ms': response.total_execution_time_ms,
            'from_cache': response.from_cache,
            'results': results,
            'errors': response.error_messages
        }
        
    except Exception as e:
        logger.error(f"Legacy filter execution failed: {e}")
        return {
            'success': False,
            'total_matches': 0,
            'total_time_ms': 0,
            'from_cache': False,
            'results': {},
            'errors': [str(e)]
        }


# ============================================================================
# History Bridge
# ============================================================================

def push_history_entry(
    expression: str,
    layer_ids: list,
    previous_filters: list,
    description: str = None
) -> None:
    """
    Push an entry to the history service.
    
    Args:
        expression: The filter expression applied
        layer_ids: List of affected layer IDs
        previous_filters: List of (layer_id, previous_filter) tuples
        description: Optional description
    """
    if not _initialized or _history_service is None:
        return
    
    entry = HistoryEntry.create(
        expression=expression,
        layer_ids=layer_ids,
        previous_filters=previous_filters,
        description=description
    )
    _history_service.push(entry)


def undo_filter() -> Optional[HistoryEntry]:
    """
    Undo the last filter operation.
    
    Returns:
        The undone HistoryEntry or None
    """
    if not _initialized or _history_service is None:
        return None
    return _history_service.undo()


def redo_filter() -> Optional[HistoryEntry]:
    """
    Redo a previously undone filter.
    
    Returns:
        The redone HistoryEntry or None
    """
    if not _initialized or _history_service is None:
        return None
    return _history_service.redo()


def can_undo() -> bool:
    """Check if undo is available."""
    if not _initialized or _history_service is None:
        return False
    return _history_service.can_undo


def can_redo() -> bool:
    """Check if redo is available."""
    if not _initialized or _history_service is None:
        return False
    return _history_service.can_redo


# ============================================================================
# Expression Validation Bridge
# ============================================================================

def validate_expression(expression: str) -> tuple:
    """
    Validate an expression.
    
    Args:
        expression: The expression to validate
        
    Returns:
        Tuple of (is_valid, error_message, warnings)
    """
    if not _initialized:
        initialize_services()
    
    result = _expression_service.validate(expression)
    return (result.is_valid, result.error_message, result.warnings)


def parse_expression(expression: str) -> Dict[str, Any]:
    """
    Parse an expression and return analysis.
    
    Args:
        expression: The expression to parse
        
    Returns:
        Dictionary with parsed expression info
    """
    if not _initialized:
        initialize_services()
    
    parsed = _expression_service.parse(expression)
    return {
        'original': parsed.original,
        'fields': list(parsed.fields),
        'spatial_predicates': [p.value for p in parsed.spatial_predicates],
        'is_spatial': parsed.is_spatial,
        'has_geometry_reference': parsed.has_geometry_reference,
        'has_layer_reference': parsed.has_layer_reference,
        'operators': list(parsed.operators),
        'estimated_complexity': parsed.estimated_complexity,
        'is_simple': parsed.is_simple,
        'is_complex': parsed.is_complex,
    }


# ============================================================================
# Backend Selection Bridge
# ============================================================================

def select_backend_for_layer(layer: 'QgsVectorLayer', forced_backend: str = None) -> str:
    """
    Select the best backend for a layer.
    
    Args:
        layer: QGIS vector layer
        forced_backend: Optional forced backend name
        
    Returns:
        Backend provider type name
    """
    if not _initialized:
        initialize_services()
    
    layer_info = layer_info_from_qgis_layer(layer)
    provider_type = _backend_factory.select_provider_type(layer_info, forced_backend)
    return provider_type.value


def get_available_backends() -> list:
    """
    Get list of available backends.
    
    Returns:
        List of backend provider type names
    """
    if not _initialized:
        initialize_services()
    
    return [p.value for p in _backend_factory.available_backends]


# ============================================================================
# Export public API
# ============================================================================

__all__ = [
    # Initialization
    'initialize_services',
    'cleanup_services',
    'is_initialized',
    
    # Service accessors
    'get_filter_service',
    'get_history_service',
    'get_expression_service',
    'get_backend_factory',
    'get_auto_optimizer_service',
    
    # Layer helpers
    'layer_info_from_qgis_layer',
    
    # Legacy compatibility
    'create_filter_expression_from_legacy',
    'convert_filter_result_to_legacy',
    'execute_filter_legacy',
    
    # History bridge
    'push_history_entry',
    'undo_filter',
    'redo_filter',
    'can_undo',
    'can_redo',
    
    # Expression bridge
    'validate_expression',
    'parse_expression',
    
    # Backend bridge
    'select_backend_for_layer',
    'get_available_backends',
]
