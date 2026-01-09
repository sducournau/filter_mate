# -*- coding: utf-8 -*-
"""
Task Bridge for FilterMate v3.0

Bridges the legacy FilterEngineTask with the new hexagonal architecture backends.
This module enables gradual migration using the Strangler Fig pattern.

The TaskBridge:
- Provides backend operations via BackendPort interface
- Translates legacy parameters to new domain objects
- Handles fallback to legacy code when needed
- Tracks metrics for migration validation

Usage in modules/tasks/filter_task.py:
    from adapters.task_bridge import TaskBridge, get_task_bridge
    
    class FilterEngineTask(QgsTask):
        def __init__(self, ...):
            # Get bridge if available
            self._task_bridge = get_task_bridge()
        
        def execute_geometric_filtering(self, ...):
            # Try new backend first
            if self._task_bridge and self._task_bridge.is_available():
                result = self._task_bridge.execute_spatial_filter(...)
                if result.success:
                    return result.to_legacy_format()
            
            # Fallback to legacy code
            return self._legacy_execute_geometric_filtering(...)

Part of FilterMate Hexagonal Architecture v3.0 (MIG-023, MIG-024)
Author: FilterMate Team
Date: January 2026
"""

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, List, Dict, Any, Tuple
from enum import Enum

if TYPE_CHECKING:
    from qgis.core import QgsVectorLayer, QgsGeometry

logger = logging.getLogger('FilterMate.TaskBridge')


# ============================================================================
# Result Types
# ============================================================================

class BridgeStatus(Enum):
    """Status of bridge operation."""
    SUCCESS = "success"
    FALLBACK = "fallback"  # New backend failed, use legacy
    NOT_AVAILABLE = "not_available"  # Bridge not initialized
    ERROR = "error"


@dataclass
class BridgeResult:
    """
    Result of a bridged operation.
    
    Provides both success/failure status and the data needed
    to continue with either new or legacy code path.
    """
    status: BridgeStatus
    success: bool = False
    feature_ids: List[int] = field(default_factory=list)
    feature_count: int = 0
    expression: str = ""
    execution_time_ms: float = 0.0
    backend_used: str = ""
    error_message: str = ""
    
    def to_legacy_format(self) -> Dict[str, Any]:
        """Convert to format expected by legacy code."""
        return {
            'success': self.success,
            'feature_ids': self.feature_ids,
            'feature_count': self.feature_count,
            'expression': self.expression,
            'execution_time_ms': self.execution_time_ms,
            'backend': self.backend_used,
            'error': self.error_message,
        }
    
    @classmethod
    def not_available(cls) -> 'BridgeResult':
        """Create a 'not available' result."""
        return cls(status=BridgeStatus.NOT_AVAILABLE)
    
    @classmethod
    def fallback(cls, reason: str = "") -> 'BridgeResult':
        """Create a 'fallback' result indicating legacy code should be used."""
        return cls(status=BridgeStatus.FALLBACK, error_message=reason)


# ============================================================================
# TaskBridge Class
# ============================================================================

class TaskBridge:
    """
    Bridge between legacy FilterEngineTask and new v3 backends.
    
    This class wraps the new BackendPort implementations and provides
    a simple interface for the legacy task code to use them.
    
    The bridge tracks metrics to validate that the new backends
    produce equivalent results to the legacy code.
    
    Example:
        bridge = TaskBridge()
        if bridge.is_available():
            result = bridge.execute_spatial_filter(
                source_layer=layer,
                target_layers=[...],
                predicates=['intersects'],
                buffer_value=0.0
            )
            if result.success:
                # Use new backend result
                ...
            else:
                # Fallback to legacy
                ...
    """
    
    def __init__(self, auto_initialize: bool = True):
        """
        Initialize the task bridge.
        
        Args:
            auto_initialize: Whether to auto-initialize services
        """
        self._initialized = False
        self._backend_factory = None
        self._metrics = {
            'operations': 0,
            'successes': 0,
            'fallbacks': 0,
            'errors': 0,
            'total_time_ms': 0.0,
            # Per-operation type metrics for migration validation
            'by_type': {
                'attribute': {'count': 0, 'success': 0, 'time_ms': 0.0},
                'spatial': {'count': 0, 'success': 0, 'time_ms': 0.0},
                'multi_step': {'count': 0, 'success': 0, 'time_ms': 0.0},
                'export': {'count': 0, 'success': 0, 'time_ms': 0.0},
            }
        }
        
        if auto_initialize:
            self._try_initialize()
    
    def _try_initialize(self) -> bool:
        """Try to initialize the bridge with v3 services."""
        try:
            from .app_bridge import (
                is_initialized as services_initialized,
                initialize_services,
                get_backend_factory,
            )
            
            if not services_initialized():
                # Try to initialize services
                initialize_services()
            
            self._backend_factory = get_backend_factory()
            self._initialized = True
            logger.info("TaskBridge initialized with v3 backends")
            return True
            
        except ImportError as e:
            logger.debug(f"TaskBridge: v3 services not available: {e}")
            return False
        except Exception as e:
            logger.warning(f"TaskBridge: Failed to initialize: {e}")
            return False
    
    def is_available(self) -> bool:
        """Check if the bridge is available for use."""
        return self._initialized and self._backend_factory is not None
    
    @property
    def metrics(self) -> Dict[str, Any]:
        """Get bridge usage metrics."""
        return self._metrics.copy()
    
    def reset_metrics(self) -> None:
        """Reset usage metrics."""
        self._metrics = {
            'operations': 0,
            'successes': 0,
            'fallbacks': 0,
            'errors': 0,
            'total_time_ms': 0.0,
            'by_type': {
                'attribute': {'count': 0, 'success': 0, 'time_ms': 0.0},
                'spatial': {'count': 0, 'success': 0, 'time_ms': 0.0},
                'multi_step': {'count': 0, 'success': 0, 'time_ms': 0.0},
                'export': {'count': 0, 'success': 0, 'time_ms': 0.0},
            }
        }
    
    def _update_type_metrics(self, op_type: str, success: bool, time_ms: float) -> None:
        """Update metrics for a specific operation type."""
        if op_type in self._metrics['by_type']:
            self._metrics['by_type'][op_type]['count'] += 1
            self._metrics['by_type'][op_type]['time_ms'] += time_ms
            if success:
                self._metrics['by_type'][op_type]['success'] += 1
    
    def get_metrics_report(self) -> str:
        """
        Generate a formatted metrics report for migration validation.
        
        Returns:
            str: Multi-line formatted report
        """
        m = self._metrics
        lines = [
            "=" * 60,
            "📊 TASKBRIDGE V3 MIGRATION METRICS",
            "=" * 60,
            f"Total Operations: {m['operations']}",
            f"  ✅ Successes: {m['successes']} ({self._pct(m['successes'], m['operations'])})",
            f"  ⚠️ Fallbacks: {m['fallbacks']} ({self._pct(m['fallbacks'], m['operations'])})",
            f"  ❌ Errors: {m['errors']} ({self._pct(m['errors'], m['operations'])})",
            f"Total V3 Time: {m['total_time_ms']:.1f}ms",
            "",
            "By Operation Type:",
        ]
        
        for op_type, stats in m['by_type'].items():
            if stats['count'] > 0:
                avg_time = stats['time_ms'] / stats['count'] if stats['count'] > 0 else 0
                success_rate = self._pct(stats['success'], stats['count'])
                lines.append(
                    f"  {op_type}: {stats['count']} ops, {success_rate} success, "
                    f"avg {avg_time:.1f}ms"
                )
        
        lines.append("=" * 60)
        return "\n".join(lines)
    
    def _pct(self, part: int, total: int) -> str:
        """Calculate percentage string."""
        if total == 0:
            return "0%"
        return f"{(part / total) * 100:.1f}%"
    
    # ========================================================================
    # Spatial Filtering Operations
    # ========================================================================
    
    def execute_spatial_filter(
        self,
        source_layer: 'QgsVectorLayer',
        target_layers: List['QgsVectorLayer'],
        predicates: List[str],
        buffer_value: float = 0.0,
        buffer_segments: int = 16,
        source_geometry: Optional['QgsGeometry'] = None,
        combine_operator: str = 'AND'
    ) -> BridgeResult:
        """
        Execute spatial filter using v3 backends.
        
        Args:
            source_layer: Source layer for filter
            target_layers: Target layers to filter
            predicates: List of spatial predicates (e.g., ['intersects'])
            buffer_value: Buffer distance
            buffer_segments: Buffer segments
            source_geometry: Pre-computed source geometry (optional)
            combine_operator: How to combine with existing filter
            
        Returns:
            BridgeResult with operation status and data
        """
        if not self.is_available():
            return BridgeResult.not_available()
        
        self._metrics['operations'] += 1
        start_time = time.time()
        
        try:
            from .app_bridge import layer_info_from_qgis_layer
            
            # Convert source layer to LayerInfo
            source_info = layer_info_from_qgis_layer(source_layer)
            
            # Get appropriate backend
            backend = self._backend_factory.get_backend(source_info)
            
            # Build filter expression
            filter_expr = self._build_spatial_expression(
                predicates=predicates,
                buffer_value=buffer_value,
                provider_type=source_info.provider_type
            )
            
            # Execute for each target layer
            all_feature_ids = []
            for target_layer in target_layers:
                target_info = layer_info_from_qgis_layer(target_layer)
                
                result = backend.execute(
                    expression=filter_expr,
                    layer_info=target_info,
                    target_layer_infos=[source_info]
                )
                
                if result.is_success:
                    all_feature_ids.extend(result.feature_ids)
            
            elapsed_ms = (time.time() - start_time) * 1000
            self._metrics['successes'] += 1
            self._metrics['total_time_ms'] += elapsed_ms
            self._update_type_metrics('spatial', True, elapsed_ms)
            
            return BridgeResult(
                status=BridgeStatus.SUCCESS,
                success=True,
                feature_ids=list(set(all_feature_ids)),
                feature_count=len(set(all_feature_ids)),
                expression=filter_expr.sql if hasattr(filter_expr, 'sql') else str(filter_expr),
                execution_time_ms=elapsed_ms,
                backend_used=backend.get_info().name if hasattr(backend, 'get_info') else 'unknown'
            )
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self._metrics['errors'] += 1
            self._metrics['total_time_ms'] += elapsed_ms
            self._update_type_metrics('spatial', False, elapsed_ms)
            
            logger.warning(f"TaskBridge.execute_spatial_filter failed: {e}")
            return BridgeResult.fallback(str(e))
    
    def execute_attribute_filter(
        self,
        layer: 'QgsVectorLayer',
        expression: str,
        combine_with_existing: bool = True
    ) -> BridgeResult:
        """
        Execute attribute filter using v3 backends.
        
        Args:
            layer: Layer to filter
            expression: QGIS expression string
            combine_with_existing: Whether to combine with existing filter
            
        Returns:
            BridgeResult with operation status and data
        """
        if not self.is_available():
            return BridgeResult.not_available()
        
        self._metrics['operations'] += 1
        start_time = time.time()
        
        try:
            from .app_bridge import layer_info_from_qgis_layer
            from ..core.domain.filter_expression import FilterExpression
            
            layer_info = layer_info_from_qgis_layer(layer)
            backend = self._backend_factory.get_backend(layer_info)
            
            filter_expr = FilterExpression.create(
                raw=expression,
                provider=layer_info.provider_type,
                source_layer_id=layer.id()
            )
            
            result = backend.execute(filter_expr, layer_info)
            
            elapsed_ms = (time.time() - start_time) * 1000
            self._metrics['successes'] += 1
            self._metrics['total_time_ms'] += elapsed_ms
            self._update_type_metrics('attribute', result.is_success, elapsed_ms)
            
            return BridgeResult(
                status=BridgeStatus.SUCCESS,
                success=result.is_success,
                feature_ids=list(result.feature_ids),
                feature_count=result.count,
                expression=expression,
                execution_time_ms=elapsed_ms,
                backend_used=backend.get_info().name if hasattr(backend, 'get_info') else 'unknown',
                error_message=result.error_message if not result.is_success else ""
            )
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self._metrics['errors'] += 1
            self._metrics['total_time_ms'] += elapsed_ms
            self._update_type_metrics('attribute', False, elapsed_ms)
            
            logger.warning(f"TaskBridge.execute_attribute_filter failed: {e}")
            return BridgeResult.fallback(str(e))
    
    def _build_spatial_expression(
        self,
        predicates: List[str],
        buffer_value: float,
        provider_type: 'ProviderType'
    ) -> 'FilterExpression':
        """Build spatial filter expression from predicates."""
        from ..core.domain.filter_expression import FilterExpression, SpatialPredicate
        
        # Convert string predicates to enum
        spatial_predicates = []
        for p in predicates:
            try:
                spatial_predicates.append(SpatialPredicate(p.lower()))
            except ValueError:
                logger.warning(f"Unknown predicate: {p}")
        
        return FilterExpression.create_spatial(
            predicates=spatial_predicates,
            buffer_value=buffer_value,
            provider=provider_type
        )
    
    # ========================================================================
    # Expression Conversion
    # ========================================================================
    
    def convert_expression_to_backend(
        self,
        expression: str,
        layer: 'QgsVectorLayer'
    ) -> Tuple[str, str]:
        """
        Convert QGIS expression to backend-specific SQL.
        
        Args:
            expression: QGIS expression string
            layer: Target layer
            
        Returns:
            Tuple of (converted_expression, backend_type)
        """
        if not self.is_available():
            return (expression, 'qgis')
        
        try:
            from .app_bridge import layer_info_from_qgis_layer
            from ..core.domain.filter_expression import FilterExpression
            
            layer_info = layer_info_from_qgis_layer(layer)
            
            filter_expr = FilterExpression.create(
                raw=expression,
                provider=layer_info.provider_type,
                source_layer_id=layer.id()
            )
            
            return (filter_expr.sql, layer_info.provider_type.value)
            
        except Exception as e:
            logger.debug(f"Expression conversion failed: {e}")
            return (expression, 'qgis')
    
    # ========================================================================
    # Multi-Step Filtering
    # ========================================================================
    
    def execute_multi_step_filter(
        self,
        source_layer: 'QgsVectorLayer',
        steps: List[Dict[str, Any]],
        progress_callback: Optional[callable] = None
    ) -> BridgeResult:
        """
        Execute multi-step filter using v3 FilterService.
        
        Multi-step filtering chains multiple filter operations where
        the output of one step can be used as input to the next.
        
        Args:
            source_layer: Source layer for filtering
            steps: List of step configurations, each containing:
                - expression: Filter expression
                - target_layer_ids: List of target layer IDs
                - predicates: Optional spatial predicates
                - use_previous_result: Whether to use previous step's output
            progress_callback: Optional callback(step, total, name)
            
        Returns:
            BridgeResult with multi-step status and data
        """
        if not self.is_available():
            return BridgeResult.not_available()
        
        self._metrics['operations'] += 1
        start_time = time.time()
        
        try:
            from .app_bridge import get_filter_service, layer_info_from_qgis_layer
            from ..core.services.filter_service import MultiStepRequest, FilterStep
            from ..core.domain.filter_expression import FilterExpression
            
            filter_service = get_filter_service()
            source_info = layer_info_from_qgis_layer(source_layer)
            
            # Convert step configs to FilterStep objects
            filter_steps = []
            for step_config in steps:
                expr_raw = step_config.get('expression', '')
                target_ids = step_config.get('target_layer_ids', [])
                use_prev = step_config.get('use_previous_result', False)
                step_name = step_config.get('name', '')
                
                filter_expr = FilterExpression.create(
                    raw=expr_raw,
                    provider=source_info.provider_type,
                    source_layer_id=source_layer.id()
                )
                
                filter_steps.append(FilterStep(
                    expression=filter_expr,
                    target_layer_ids=target_ids,
                    use_previous_result=use_prev,
                    step_name=step_name
                ))
            
            # Create and execute multi-step request
            request = MultiStepRequest(
                steps=filter_steps,
                source_layer_id=source_layer.id(),
                progress_callback=progress_callback,
                stop_on_empty=True
            )
            
            response = filter_service.apply_multi_step_filter(request)
            
            elapsed_ms = (time.time() - start_time) * 1000
            success = not response.stopped_early or response.stop_reason == ""
            self._metrics['successes'] += 1
            self._metrics['total_time_ms'] += elapsed_ms
            self._update_type_metrics('multi_step', success, elapsed_ms)
            
            return BridgeResult(
                status=BridgeStatus.SUCCESS,
                success=success,
                feature_ids=list(response.final_feature_ids),
                feature_count=len(response.final_feature_ids),
                expression=f"multi-step ({response.completed_steps} steps)",
                execution_time_ms=elapsed_ms,
                backend_used='multi_step_v3',
                error_message=response.stop_reason if response.stopped_early else ""
            )
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self._metrics['errors'] += 1
            self._metrics['total_time_ms'] += elapsed_ms
            self._update_type_metrics('multi_step', False, elapsed_ms)
            
            logger.warning(f"TaskBridge.execute_multi_step_filter failed: {e}")
            return BridgeResult.fallback(str(e))
    
    def supports_multi_step(self) -> bool:
        """Check if multi-step filtering is available."""
        if not self.is_available():
            return False
        
        try:
            return True
        except ImportError:
            return False
    
    # ========================================================================
    # Export Operations
    # ========================================================================
    
    def execute_export(
        self,
        source_layer: 'QgsVectorLayer',
        output_path: str,
        format: str = 'gpkg',
        field_mapping: Optional[Dict[str, str]] = None,
        progress_callback: Optional[callable] = None,
        cancel_check: Optional[callable] = None
    ) -> BridgeResult:
        """
        Execute layer export using streaming exporter.
        
        This provides the Strangler Fig pattern for export operations,
        using the optimized StreamingExporter for large datasets.
        
        Args:
            source_layer: QGIS layer to export
            output_path: Path for output file
            format: Output format ('gpkg', 'shp', 'geojson', etc.)
            field_mapping: Optional field name mapping
            progress_callback: Callback for progress updates
            cancel_check: Callback to check for cancellation
            
        Returns:
            BridgeResult with export status and metrics
        """
        if not self.is_available():
            return BridgeResult.not_available()
        
        start_time = time.time()
        self._metrics['operations'] += 1
        
        try:
            # Import streaming exporter
            from .qgis.tasks import StreamingExporter
            
            logger.info("=" * 60)
            logger.info("🚀 V3 TASKBRIDGE: Executing streaming export")
            logger.info("=" * 60)
            logger.info(f"   Layer: '{source_layer.name()}'")
            logger.info(f"   Format: {format}")
            logger.info(f"   Output: {output_path}")
            
            # Create streaming exporter with default config
            exporter = StreamingExporter()
            
            # Execute export
            result = exporter.export_layer_streaming(
                source_layer=source_layer,
                output_path=output_path,
                format=format,
                field_mapping=field_mapping,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            success = result.get('success', False)
            
            self._metrics['total_time_ms'] += elapsed_ms
            self._update_type_metrics('export', success, elapsed_ms)
            
            if success:
                self._metrics['successes'] += 1
                logger.info(f"✅ V3 TaskBridge EXPORT SUCCESS")
                logger.info(f"   Features exported: {result.get('features_exported', 0)}")
                logger.info(f"   File size: {result.get('bytes_written', 0)} bytes")
                logger.info(f"   Execution time: {elapsed_ms:.1f}ms")
                
                return BridgeResult(
                    status=BridgeStatus.SUCCESS,
                    success=True,
                    feature_count=result.get('features_exported', 0),
                    expression=f"export to {format}",
                    execution_time_ms=elapsed_ms,
                    backend_used='streaming_exporter'
                )
            else:
                self._metrics['errors'] += 1
                error_msg = result.get('error', 'Unknown export error')
                logger.warning(f"⚠️ V3 TaskBridge EXPORT FAILED: {error_msg}")
                
                return BridgeResult(
                    status=BridgeStatus.FALLBACK,
                    success=False,
                    error_message=error_msg,
                    execution_time_ms=elapsed_ms
                )
                
        except ImportError as e:
            elapsed_ms = (time.time() - start_time) * 1000
            logger.debug(f"StreamingExporter not available: {e}")
            return BridgeResult.fallback(f"StreamingExporter not available: {e}")
            
        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            self._metrics['errors'] += 1
            self._metrics['total_time_ms'] += elapsed_ms
            self._update_type_metrics('export', False, elapsed_ms)
            
            logger.warning(f"TaskBridge.execute_export failed: {e}")
            return BridgeResult.fallback(str(e))
    
    def supports_export(self) -> bool:
        """Check if streaming export is available."""
        if not self.is_available():
            return False
        
        try:
            return True
        except ImportError:
            return False
    
    # ========================================================================
    # Backend Selection
    # ========================================================================
    
    def get_backend_for_layer(
        self,
        layer: 'QgsVectorLayer'
    ) -> Optional[str]:
        """
        Get the backend type that would be used for a layer.
        
        Args:
            layer: QGIS layer
            
        Returns:
            Backend type name or None
        """
        if not self.is_available():
            return None
        
        try:
            from .app_bridge import layer_info_from_qgis_layer
            
            layer_info = layer_info_from_qgis_layer(layer)
            backend = self._backend_factory.get_backend(layer_info)
            
            if hasattr(backend, 'get_info'):
                return backend.get_info().name
            return layer_info.provider_type.value
            
        except Exception:
            return None


# ============================================================================
# Singleton Access
# ============================================================================

_task_bridge: Optional[TaskBridge] = None


def get_task_bridge(auto_init: bool = True) -> Optional[TaskBridge]:
    """
    Get the global TaskBridge instance.
    
    Args:
        auto_init: If True, auto-initialize services on creation.
                   Set False for testing without QGIS.
    
    Returns:
        TaskBridge instance or None if not available
    """
    global _task_bridge
    
    if _task_bridge is None:
        _task_bridge = TaskBridge(auto_initialize=auto_init)
    
    # If auto_init is False, return bridge even if not fully initialized
    if not auto_init:
        return _task_bridge
    
    return _task_bridge if _task_bridge.is_available() else None


def reset_task_bridge() -> None:
    """Reset the global TaskBridge instance."""
    global _task_bridge
    _task_bridge = None


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    'TaskBridge',
    'BridgeResult',
    'BridgeStatus',
    'get_task_bridge',
    'reset_task_bridge',
]
