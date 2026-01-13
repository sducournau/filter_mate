# -*- coding: utf-8 -*-
"""
Legacy Backend Adapter - MIG-011

Provides backward compatibility by wrapping legacy v2.x backends 
to implement the v3.0 BackendPort interface.

This adapter allows gradual migration:
1. Existing code continues to work via legacy imports
2. New code uses BackendPort interface
3. Both use the same underlying backend logic

Part of FilterMate Hexagonal Architecture v3.0 Migration

Usage:
    # Wrap a legacy backend for use with v3 code
    from adapters.legacy_adapter import LegacyBackendAdapter
    from adapters.backends.postgresql import PostgreSQLBackend as LegacyPgBackend
    
    legacy = LegacyPgBackend(task_params)
    adapted = LegacyBackendAdapter(legacy, ProviderType.POSTGRESQL)
    
    # Now use adapted with FilterService
    service = FilterService(backends={ProviderType.POSTGRESQL: adapted})
"""
import warnings
import time
import logging
from typing import Dict, List, Optional, Tuple, Set, Any

from ..core.ports.backend_port import (
    BackendPort,
    BackendInfo,
    BackendCapability,
)
from ..core.domain.filter_expression import FilterExpression, ProviderType
from ..core.domain.filter_result import FilterResult
from ..core.domain.layer_info import LayerInfo

logger = logging.getLogger(__name__)


class LegacyBackendAdapter(BackendPort):
    """
    Adapter that wraps a legacy v2.x backend to implement BackendPort.
    
    This adapter:
    - Translates v3 domain objects to v2 parameters
    - Translates v2 results back to v3 FilterResult
    - Adds deprecation warnings to encourage migration
    - Preserves all v2 functionality
    
    The adapter pattern allows us to:
    1. Use existing tested backend code
    2. Gradually migrate to pure v3 implementations
    3. Maintain backward compatibility
    
    Attributes:
        _legacy: The wrapped legacy backend instance
        _provider_type: Provider type this backend handles
        _deprecation_warned: Whether deprecation warning has been shown
        _stats: Execution statistics
    """
    
    # Class-level flag to show deprecation warning only once
    _deprecation_warned_classes: Set[str] = set()
    
    def __init__(
        self,
        legacy_backend: 'GeometricFilterBackend',
        provider_type: ProviderType,
        emit_deprecation_warning: bool = True
    ):
        """
        Initialize the adapter with a legacy backend.
        
        Args:
            legacy_backend: Instance of a v2.x GeometricFilterBackend
            provider_type: ProviderType this backend handles
            emit_deprecation_warning: Whether to emit deprecation warnings
        """
        self._legacy = legacy_backend
        self._provider_type = provider_type
        
        # Emit deprecation warning once per class
        class_name = type(legacy_backend).__name__
        if emit_deprecation_warning and class_name not in self._deprecation_warned_classes:
            warnings.warn(
                f"LegacyBackendAdapter wrapping {class_name} is deprecated. "
                f"Migrate to native v3 backends (adapters/backends/{provider_type.value}/). "
                f"This compatibility layer will be removed in FilterMate v4.0.",
                DeprecationWarning,
                stacklevel=2
            )
            self._deprecation_warned_classes.add(class_name)
            logger.info(f"Legacy adapter created for {class_name}")
        
        # Statistics
        self._stats = {
            'total_executions': 0,
            'total_time_ms': 0.0,
            'errors': 0,
            'cache_hits': 0,
        }
    
    def execute(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo,
        target_layer_infos: Optional[List[LayerInfo]] = None
    ) -> FilterResult:
        """
        Execute filter by delegating to legacy backend.
        
        Translates v3 domain objects to v2 format, executes, then
        translates results back.
        """
        start_time = time.time()
        self._stats['total_executions'] += 1
        
        try:
            # Convert v3 expression to v2 format
            legacy_params = self._expression_to_legacy_params(expression, layer_info)
            
            # Get QGIS layer from layer_info
            qgis_layer = self._get_qgis_layer(layer_info)
            if qgis_layer is None:
                return FilterResult.error(
                    layer_id=layer_info.layer_id,
                    expression_raw=expression.raw,
                    error_message=f"Could not get QGIS layer: {layer_info.layer_id}",
                    backend_name=self.name
                )
            
            # Build expression using legacy backend
            legacy_expression = self._legacy.build_expression(
                layer_props=legacy_params.get('layer_props', {}),
                predicates=legacy_params.get('predicates', {}),
                source_geom=legacy_params.get('source_geom'),
                buffer_value=expression.buffer_value,
                **legacy_params.get('extra_kwargs', {})
            )
            
            # Apply filter using legacy backend
            success = self._legacy.apply_filter(
                layer=qgis_layer,
                expression=legacy_expression,
                old_subset=legacy_params.get('old_subset'),
                combine_operator=legacy_params.get('combine_operator', 'AND')
            )
            
            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000
            self._stats['total_time_ms'] += execution_time_ms
            
            if success:
                # Get matching feature IDs
                feature_ids = self._get_filtered_feature_ids(qgis_layer)
                
                return FilterResult.success(
                    layer_id=layer_info.layer_id,
                    expression_raw=expression.raw,
                    feature_ids=feature_ids,
                    count=len(feature_ids),
                    execution_time_ms=execution_time_ms,
                    backend_name=self.name
                )
            else:
                self._stats['errors'] += 1
                return FilterResult.error(
                    layer_id=layer_info.layer_id,
                    expression_raw=expression.raw,
                    error_message="Legacy backend apply_filter returned False",
                    backend_name=self.name
                )
                
        except Exception as e:
            self._stats['errors'] += 1
            execution_time_ms = (time.time() - start_time) * 1000
            self._stats['total_time_ms'] += execution_time_ms
            
            logger.exception(f"Legacy backend execution failed: {e}")
            return FilterResult.error(
                layer_id=layer_info.layer_id,
                expression_raw=expression.raw,
                error_message=str(e),
                backend_name=self.name
            )
    
    def supports_layer(self, layer_info: LayerInfo) -> bool:
        """Check if legacy backend supports this layer."""
        qgis_layer = self._get_qgis_layer(layer_info)
        if qgis_layer is None:
            return False
        
        try:
            return self._legacy.supports_layer(qgis_layer)
        except Exception as e:
            logger.warning(f"Legacy supports_layer check failed: {e}")
            return False
    
    def get_info(self) -> BackendInfo:
        """Get backend info from legacy backend."""
        legacy_name = type(self._legacy).__name__
        
        # Map legacy backend class names to capabilities
        capabilities = BackendCapability.SPATIAL_FILTER  # All backends support this
        
        if 'postgresql' in legacy_name.lower():
            capabilities |= (
                BackendCapability.MATERIALIZED_VIEW |
                BackendCapability.SPATIAL_INDEX |
                BackendCapability.PARALLEL_EXECUTION |
                BackendCapability.COMPLEX_EXPRESSIONS |
                BackendCapability.BUFFER_OPERATIONS |
                BackendCapability.TRANSACTIONS
            )
            priority = 100
        elif 'spatialite' in legacy_name.lower():
            capabilities |= (
                BackendCapability.SPATIAL_INDEX |
                BackendCapability.COMPLEX_EXPRESSIONS |
                BackendCapability.BUFFER_OPERATIONS
            )
            priority = 75
        elif 'ogr' in legacy_name.lower():
            capabilities |= BackendCapability.BUFFER_OPERATIONS
            priority = 50
        else:
            priority = 25
        
        return BackendInfo(
            name=f"Legacy_{legacy_name}",
            version="2.x (adapted)",
            capabilities=capabilities,
            priority=priority,
            description=f"Adapted legacy backend: {legacy_name}"
        )
    
    def cleanup(self) -> None:
        """Clean up legacy backend resources."""
        if hasattr(self._legacy, 'cleanup'):
            try:
                self._legacy.cleanup()
            except Exception as e:
                logger.warning(f"Legacy cleanup failed: {e}")
        
        if hasattr(self._legacy, 'close'):
            try:
                self._legacy.close()
            except Exception as e:
                logger.warning(f"Legacy close failed: {e}")
    
    def estimate_execution_time(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo
    ) -> float:
        """
        Estimate execution time based on historical data.
        
        Legacy backends don't have this method, so we estimate
        based on layer feature count and our statistics.
        """
        if self._stats['total_executions'] == 0:
            # Default estimates by backend type
            feature_count = layer_info.feature_count or 10000
            if 'postgresql' in self.name.lower():
                return feature_count * 0.001  # ~1ms per 1000 features
            elif 'spatialite' in self.name.lower():
                return feature_count * 0.002  # ~2ms per 1000 features
            else:
                return feature_count * 0.005  # ~5ms per 1000 features
        
        # Use average from actual executions
        return self._stats['total_time_ms'] / self._stats['total_executions']
    
    def validate_expression(
        self,
        expression: FilterExpression
    ) -> Tuple[bool, Optional[str]]:
        """Validate expression using legacy backend if available."""
        if hasattr(self._legacy, 'validate_expression'):
            try:
                return self._legacy.validate_expression(expression.raw)
            except Exception as e:
                return False, str(e)
        
        # Default: assume valid if no validation method
        return True, None
    
    def get_statistics(self) -> Dict:
        """Get adapter execution statistics."""
        avg_time = (
            self._stats['total_time_ms'] / self._stats['total_executions']
            if self._stats['total_executions'] > 0 else 0.0
        )
        return {
            **self._stats,
            'average_time_ms': avg_time,
            'error_rate': (
                self._stats['errors'] / self._stats['total_executions']
                if self._stats['total_executions'] > 0 else 0.0
            ),
            'legacy_class': type(self._legacy).__name__,
        }
    
    def reset_statistics(self) -> None:
        """Reset adapter statistics."""
        self._stats = {
            'total_executions': 0,
            'total_time_ms': 0.0,
            'errors': 0,
            'cache_hits': 0,
        }
    
    # =========================================================================
    # Private helper methods
    # =========================================================================
    
    def _expression_to_legacy_params(
        self,
        expression: FilterExpression,
        layer_info: LayerInfo
    ) -> Dict[str, Any]:
        """
        Convert v3 FilterExpression to v2 backend parameters.
        
        This is the main translation layer between v3 domain objects
        and v2 dictionary-based parameters.
        """
        # Build layer_props dict as expected by legacy backends
        layer_props = {
            'name': layer_info.name,
            'id': layer_info.layer_id,
            'provider_type': layer_info.provider_type.value,
            'geometry_type': layer_info.geometry_type,
            'crs': layer_info.crs_auth_id,
            'feature_count': layer_info.feature_count or 0,
        }
        
        # Build predicates dict from expression
        predicates = {}
        if expression.spatial_predicates:
            for pred in expression.spatial_predicates:
                predicates[pred.value] = True
        else:
            # Default to intersects
            predicates['intersects'] = True
        
        # Extract source geometry if available
        source_geom = None
        if hasattr(expression, 'source_geometry_wkt') and expression.source_geometry_wkt:
            source_geom = expression.source_geometry_wkt
        
        return {
            'layer_props': layer_props,
            'predicates': predicates,
            'source_geom': source_geom,
            'old_subset': None,  # Could be extracted from layer_info
            'combine_operator': 'AND',
            'extra_kwargs': {
                'source_srid': layer_info.crs_auth_id,
            }
        }
    
    def _get_qgis_layer(self, layer_info: LayerInfo) -> Optional['QgsVectorLayer']:
        """Get QGIS layer from layer info."""
        try:
            from qgis.core import QgsProject
            return QgsProject.instance().mapLayer(layer_info.layer_id)
        except Exception as e:
            logger.warning(f"Could not get QGIS layer: {e}")
            return None
    
    def _get_filtered_feature_ids(
        self,
        layer: 'QgsVectorLayer'
    ) -> Set[int]:
        """Get IDs of features matching the current filter."""
        try:
            from qgis.core import QgsFeatureRequest
            request = QgsFeatureRequest()
            request.setFlags(QgsFeatureRequest.NoGeometry)
            request.setSubsetOfAttributes([])
            
            return {f.id() for f in layer.getFeatures(request)}
        except Exception as e:
            logger.warning(f"Could not get feature IDs: {e}")
            return set()
    
    @property
    def legacy_backend(self) -> 'GeometricFilterBackend':
        """Access the wrapped legacy backend directly."""
        return self._legacy
    
    def __repr__(self) -> str:
        return (
            f"<LegacyBackendAdapter "
            f"wrapping={type(self._legacy).__name__} "
            f"provider={self._provider_type.value}>"
        )


# =============================================================================
# Factory functions for common legacy backend wrapping
# =============================================================================

def wrap_legacy_postgresql_backend(task_params: Dict) -> LegacyBackendAdapter:
    """
    Create an adapted PostgreSQL backend from legacy code.
    
    Args:
        task_params: Task parameters for legacy backend
        
    Returns:
        LegacyBackendAdapter wrapping PostgreSQLBackend
    """
    try:
        from .backends.postgresql import PostgreSQLBackend
        legacy = PostgreSQLBackend(task_params)
        return LegacyBackendAdapter(legacy, ProviderType.POSTGRESQL)
    except ImportError as e:
        logger.error(f"Could not import PostgreSQL backend: {e}")
        raise


def wrap_legacy_spatialite_backend(task_params: Dict) -> LegacyBackendAdapter:
    """
    Create an adapted Spatialite backend from legacy code.
    
    Args:
        task_params: Task parameters for legacy backend
        
    Returns:
        LegacyBackendAdapter wrapping SpatialiteBackend
    """
    try:
        from .backends.spatialite import SpatialiteBackend
        legacy = SpatialiteBackend(task_params)
        return LegacyBackendAdapter(legacy, ProviderType.SPATIALITE)
    except ImportError as e:
        logger.error(f"Could not import Spatialite backend: {e}")
        raise


def wrap_legacy_ogr_backend(task_params: Dict) -> LegacyBackendAdapter:
    """
    Create an adapted OGR backend from legacy code.
    
    Args:
        task_params: Task parameters for legacy backend
        
    Returns:
        LegacyBackendAdapter wrapping OGRBackend
    """
    try:
        from .backends.ogr import OGRBackend
        legacy = OGRBackend(task_params)
        return LegacyBackendAdapter(legacy, ProviderType.OGR)
    except ImportError as e:
        logger.error(f"Could not import OGR backend: {e}")
        raise


def create_all_legacy_adapters(
    task_params: Dict
) -> Dict[ProviderType, LegacyBackendAdapter]:
    """
    Create adapted backends for all available legacy backends.
    
    Args:
        task_params: Task parameters for legacy backends
        
    Returns:
        Dict mapping ProviderType to LegacyBackendAdapter
    """
    adapters = {}
    
    # Try PostgreSQL
    try:
        from .backends.postgresql import PostgreSQLBackend
        adapters[ProviderType.POSTGRESQL] = LegacyBackendAdapter(
            PostgreSQLBackend(task_params),
            ProviderType.POSTGRESQL
        )
    except (ImportError, Exception) as e:
        logger.info(f"PostgreSQL backend not available: {e}")
    
    # Try Spatialite
    try:
        from .backends.spatialite import SpatialiteBackend
        adapters[ProviderType.SPATIALITE] = LegacyBackendAdapter(
            SpatialiteBackend(task_params),
            ProviderType.SPATIALITE
        )
    except (ImportError, Exception) as e:
        logger.info(f"Spatialite backend not available: {e}")
    
    # Try OGR
    try:
        from .backends.ogr import OGRBackend
        adapters[ProviderType.OGR] = LegacyBackendAdapter(
            OGRBackend(task_params),
            ProviderType.OGR
        )
    except (ImportError, Exception) as e:
        logger.info(f"OGR backend not available: {e}")
    
    return adapters


# Type hints for forward references
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from qgis.core import QgsVectorLayer
    from .backends.base import GeometricFilterBackend
