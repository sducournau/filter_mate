"""
Filter Service.

Main orchestration service for filter operations.

This is a PURE PYTHON module with NO QGIS dependencies,
enabling true unit testing and clear separation of concerns.
"""
from typing import List, Optional, Dict, Set
from dataclasses import dataclass, field
from datetime import datetime
import logging

from core.domain.filter_expression import FilterExpression, ProviderType
from core.domain.filter_result import FilterResult, FilterStatus
from core.domain.layer_info import LayerInfo
from core.domain.optimization_config import OptimizationConfig
from core.services.expression_service import ExpressionService

logger = logging.getLogger(__name__)


@dataclass
class FilterRequest:
    """
    Request for a filter operation.
    
    Attributes:
        expression: The filter expression to apply
        source_layer_id: ID of the source layer
        target_layer_ids: IDs of layers to filter
        use_cache: Whether to use cached results
        optimization_config: Optional optimization settings
    """
    expression: FilterExpression
    source_layer_id: str
    target_layer_ids: List[str]
    use_cache: bool = True
    optimization_config: Optional[OptimizationConfig] = None


@dataclass
class FilterResponse:
    """
    Response from a filter operation.
    
    Attributes:
        results: Dictionary mapping layer_id to FilterResult
        total_matches: Total matching features across all layers
        total_execution_time_ms: Total execution time
        from_cache: Whether all results came from cache
        timestamp: When the response was created
    """
    results: Dict[str, FilterResult]
    total_matches: int
    total_execution_time_ms: float
    from_cache: bool
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_success(self) -> bool:
        """Check if all layer filters succeeded."""
        if not self.results:
            return False
        return all(r.is_success for r in self.results.values())

    @property
    def has_error(self) -> bool:
        """Check if any layer filter failed."""
        return any(r.has_error for r in self.results.values())

    @property
    def has_partial_success(self) -> bool:
        """Check if some layers succeeded and some failed."""
        if not self.results:
            return False
        successes = sum(1 for r in self.results.values() if r.is_success)
        return 0 < successes < len(self.results)

    @property
    def all_feature_ids(self) -> Set[int]:
        """Get all matching feature IDs across all layers."""
        all_ids: Set[int] = set()
        for result in self.results.values():
            if result.is_success:
                all_ids.update(result.feature_ids)
        return all_ids

    @property
    def error_messages(self) -> List[str]:
        """Get all error messages."""
        return [
            r.error_message 
            for r in self.results.values() 
            if r.error_message
        ]

    @property
    def layer_count(self) -> int:
        """Number of layers processed."""
        return len(self.results)

    @property
    def success_count(self) -> int:
        """Number of successful layer filters."""
        return sum(1 for r in self.results.values() if r.is_success)

    @property
    def error_count(self) -> int:
        """Number of failed layer filters."""
        return sum(1 for r in self.results.values() if r.has_error)


class FilterService:
    """
    Main filter orchestration service.

    Coordinates:
    - Backend selection based on layer type
    - Expression validation and conversion
    - Cache lookup and storage
    - Multi-layer filter execution
    - Result aggregation

    This service follows the hexagonal architecture pattern:
    - Depends on ports (interfaces) not concrete implementations
    - Pure Python with no QGIS dependencies
    - Fully testable with mocks

    Example:
        service = FilterService(
            backends={ProviderType.POSTGRESQL: pg_backend},
            cache=result_cache,
            layer_repository=layer_repo
        )
        
        expression = FilterExpression.create(
            raw="intersects($geometry, @source)",
            provider=ProviderType.POSTGRESQL,
            source_layer_id="layer_123"
        )
        
        request = FilterRequest(
            expression=expression,
            source_layer_id="layer_123",
            target_layer_ids=["layer_456", "layer_789"]
        )
        
        response = service.apply_filter(request)
        
        for layer_id, result in response.results.items():
            print(f"{layer_id}: {result.count} matches")
    """

    def __init__(
        self,
        backends: Dict[ProviderType, 'BackendPort'],
        cache: 'CachePort',
        layer_repository: 'LayerRepositoryPort',
        expression_service: Optional[ExpressionService] = None,
        default_optimization: Optional[OptimizationConfig] = None
    ):
        """
        Initialize FilterService.

        Args:
            backends: Dict of provider type to backend implementation
            cache: Cache implementation for results
            layer_repository: Repository for layer access
            expression_service: Expression parsing service (optional)
            default_optimization: Default optimization settings (optional)
        """
        self._backends = backends
        self._cache = cache
        self._layer_repository = layer_repository
        self._expression_service = expression_service or ExpressionService()
        self._default_optimization = default_optimization or OptimizationConfig.default()
        self._is_cancelled = False
        
        # Statistics
        self._stats = {
            'total_filters': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0,
            'total_time_ms': 0.0,
        }

    def apply_filter(self, request: FilterRequest) -> FilterResponse:
        """
        Apply filter to one or more layers.

        This is the main entry point for filter operations.

        Args:
            request: Filter request with expression and targets

        Returns:
            FilterResponse with results for each layer
        """
        self._is_cancelled = False
        start_time = datetime.now()
        results: Dict[str, FilterResult] = {}
        from_cache = True

        # Get optimization config
        opt_config = request.optimization_config or self._default_optimization

        # Get source layer info
        source_layer = self._layer_repository.get_layer_info(request.source_layer_id)
        if not source_layer:
            return self._error_response(
                request.target_layer_ids,
                request.expression,
                f"Source layer not found: {request.source_layer_id}"
            )

        # Validate expression
        validation = self._expression_service.validate(request.expression.raw)
        if not validation.is_valid:
            return self._error_response(
                request.target_layer_ids,
                request.expression,
                validation.error_message or "Invalid expression"
            )

        # Convert expression for source provider
        sql = self._expression_service.to_sql(
            request.expression.raw,
            source_layer.provider_type
        )
        expression = request.expression.with_sql(sql)

        # Process each target layer
        for target_layer_id in request.target_layer_ids:
            if self._is_cancelled:
                results[target_layer_id] = FilterResult.cancelled(
                    layer_id=target_layer_id,
                    expression_raw=expression.raw
                )
                continue

            result = self._filter_layer(
                expression=expression,
                source_layer=source_layer,
                target_layer_id=target_layer_id,
                use_cache=request.use_cache and opt_config.use_cache
            )
            results[target_layer_id] = result

            if not result.is_cached:
                from_cache = False

        # Calculate totals
        execution_time = (datetime.now() - start_time).total_seconds() * 1000
        total_matches = sum(r.count for r in results.values() if r.is_success)

        # Update statistics
        self._stats['total_filters'] += 1
        self._stats['total_time_ms'] += execution_time

        return FilterResponse(
            results=results,
            total_matches=total_matches,
            total_execution_time_ms=execution_time,
            from_cache=from_cache
        )

    def _filter_layer(
        self,
        expression: FilterExpression,
        source_layer: LayerInfo,
        target_layer_id: str,
        use_cache: bool
    ) -> FilterResult:
        """
        Filter a single layer.
        
        Handles cache lookup, backend selection, and execution.
        """
        # Check cache first
        if use_cache:
            cache_key = self._build_cache_key(expression, target_layer_id)
            cached = self._cache.get(cache_key)
            if cached:
                logger.debug(f"Cache hit for {target_layer_id}")
                self._stats['cache_hits'] += 1
                return cached.with_from_cache(True)
            self._stats['cache_misses'] += 1

        # Get target layer info
        target_layer = self._layer_repository.get_layer_info(target_layer_id)
        if not target_layer:
            return FilterResult.error(
                layer_id=target_layer_id,
                expression_raw=expression.raw,
                error_message=f"Target layer not found: {target_layer_id}"
            )

        # Select backend
        backend = self._select_backend(source_layer)
        if not backend:
            self._stats['errors'] += 1
            return FilterResult.error(
                layer_id=target_layer_id,
                expression_raw=expression.raw,
                error_message=f"No backend available for provider: {source_layer.provider_type.value}"
            )

        # Validate expression for this backend
        is_valid, error_msg = backend.validate_expression(expression)
        if not is_valid:
            self._stats['errors'] += 1
            return FilterResult.error(
                layer_id=target_layer_id,
                expression_raw=expression.raw,
                error_message=error_msg or "Expression not valid for backend"
            )

        # Execute filter
        try:
            result = backend.execute(
                expression=expression,
                layer_info=source_layer,
                target_layer_infos=[target_layer]
            )

            # Cache successful results
            if result.is_success and use_cache:
                cache_key = self._build_cache_key(expression, target_layer_id)
                self._cache.set(cache_key, result)

            return result

        except Exception as e:
            logger.exception(f"Filter execution failed: {e}")
            self._stats['errors'] += 1
            return FilterResult.error(
                layer_id=target_layer_id,
                expression_raw=expression.raw,
                error_message=str(e),
                backend_name=backend.name
            )

    def _select_backend(self, layer: LayerInfo) -> Optional['BackendPort']:
        """
        Select the best backend for a layer.
        
        Priority:
        1. Exact provider match
        2. Any supporting backend by priority
        """
        # Try exact match first
        backend = self._backends.get(layer.provider_type)
        if backend and backend.supports_layer(layer):
            return backend

        # Fall back to any supporting backend by priority
        supporting = [
            b for b in self._backends.values()
            if b.supports_layer(layer)
        ]
        if supporting:
            return max(supporting, key=lambda b: b.priority)

        return None

    def _build_cache_key(
        self, 
        expression: FilterExpression, 
        target_layer_id: str
    ) -> str:
        """Build cache key for expression + target combination."""
        buffer_str = str(expression.buffer_value) if expression.buffer_value else "0"
        return f"{expression.raw}|{expression.source_layer_id}|{target_layer_id}|{buffer_str}"

    def _error_response(
        self,
        target_layer_ids: List[str],
        expression: FilterExpression,
        error_message: str
    ) -> FilterResponse:
        """Build error response for all layers."""
        self._stats['errors'] += 1
        results = {
            layer_id: FilterResult.error(
                layer_id=layer_id,
                expression_raw=expression.raw,
                error_message=error_message
            )
            for layer_id in target_layer_ids
        }
        return FilterResponse(
            results=results,
            total_matches=0,
            total_execution_time_ms=0,
            from_cache=False
        )

    def cancel(self) -> None:
        """
        Cancel ongoing filter operation.
        
        Sets cancellation flag that is checked between layer processing.
        """
        self._is_cancelled = True

    @property
    def is_cancelled(self) -> bool:
        """Check if filter was cancelled."""
        return self._is_cancelled

    def clear_cache(self) -> int:
        """
        Clear filter result cache.
        
        Returns:
            Number of entries cleared
        """
        return self._cache.clear()

    def invalidate_layer_cache(self, layer_id: str) -> int:
        """
        Invalidate cache entries for a specific layer.
        
        Called when layer data changes.
        
        Args:
            layer_id: Layer ID to invalidate
            
        Returns:
            Number of entries invalidated
        """
        # This requires a specialized cache implementation
        # Default behavior is to clear all
        if hasattr(self._cache, 'invalidate_layer'):
            return self._cache.invalidate_layer(layer_id)
        return self.clear_cache()

    def get_available_backends(self) -> Dict[str, ProviderType]:
        """
        Get available backends.
        
        Returns:
            Dict mapping backend name to provider type
        """
        return {
            b.name: provider_type 
            for provider_type, b in self._backends.items()
        }

    def get_backend_for_layer(self, layer_id: str) -> Optional[str]:
        """
        Get backend name that would handle a layer.
        
        Args:
            layer_id: Layer ID
            
        Returns:
            Backend name or None if no backend available
        """
        layer = self._layer_repository.get_layer_info(layer_id)
        if not layer:
            return None
        backend = self._select_backend(layer)
        return backend.name if backend else None

    def validate_expression(self, expression: str) -> bool:
        """
        Quick validation of expression syntax.
        
        Args:
            expression: Expression string
            
        Returns:
            True if expression is syntactically valid
        """
        return self._expression_service.validate(expression).is_valid

    def get_statistics(self) -> Dict:
        """
        Get filter service statistics.
        
        Returns:
            Dictionary with execution statistics
        """
        total = self._stats['cache_hits'] + self._stats['cache_misses']
        cache_rate = (
            self._stats['cache_hits'] / total 
            if total > 0 else 0.0
        )
        
        return {
            **self._stats,
            'cache_hit_rate': cache_rate,
        }

    def reset_statistics(self) -> None:
        """Reset all statistics."""
        self._stats = {
            'total_filters': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': 0,
            'total_time_ms': 0.0,
        }


# Type hints for forward references
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.ports.backend_port import BackendPort
    from core.ports.cache_port import CachePort
    from core.ports.repository_port import LayerRepositoryPort
