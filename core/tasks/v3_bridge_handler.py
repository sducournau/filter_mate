"""
V3 TaskBridge Handler for FilterEngineTask

Centralizes V3 TaskBridge delegation methods (Strangler Fig pattern) that
attempt to use the new v3 architecture before falling back to legacy code.

Methods in this handler:
- try_v3_attribute_filter: Attempt v3 attribute filtering
- try_v3_spatial_filter: Attempt v3 spatial filtering
- try_v3_multi_step_filter: Attempt v3 multi-step filtering
- try_v3_export: Attempt v3 streaming export

Extracted from FilterEngineTask as part of Pass 3 god-class decomposition.

Location: core/tasks/v3_bridge_handler.py (Hexagonal Architecture - Application Layer)

Thread Safety:
    These methods access task state (self.task.xxx) and QGIS layers.
    They should only be called from within QgsTask.run() context where
    appropriate thread safety measures are already in place.
"""

import logging
import os

from ...infrastructure.logging import setup_logger
from ...config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.V3Bridge',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# Lazy load backend services for BridgeStatus
from ..ports.backend_services import get_backend_services
_backend_services = get_backend_services()
get_task_bridge, BridgeStatus = _backend_services.get_task_bridge()


class V3BridgeHandler:
    """Handles V3 TaskBridge delegation for the Strangler Fig migration pattern.

    This class encapsulates all v3 bridge methods previously embedded in
    FilterEngineTask. Each method attempts to use the v3 architecture and
    returns None to signal fallback to legacy code.

    Attributes:
        task: Reference to the parent FilterEngineTask for state access.

    Example:
        >>> handler = V3BridgeHandler(task)
        >>> result = handler.try_v3_attribute_filter(expression, features)
        >>> if result is None:
        ...     # Fallback to legacy code
    """

    def __init__(self, task):
        """Initialize V3BridgeHandler.

        Args:
            task: FilterEngineTask instance providing access to task state
                  (_task_bridge, _get_attribute_executor, _get_spatial_executor, etc.)
        """
        self.task = task

    def try_v3_attribute_filter(self, task_expression, task_features):
        """Try v3 TaskBridge attribute filter.

        Phase E13: Delegates to AttributeFilterExecutor.

        Args:
            task_expression: Filter expression string.
            task_features: Feature list for filtering.

        Returns:
            True/False if v3 handled it, None to signal fallback to legacy.
        """
        executor = self.task._get_attribute_executor()

        result = executor.try_v3_attribute_filter(
            task_expression=task_expression,
            task_features=task_features,
            task_bridge=self.task._task_bridge,
            source_layer=self.task.source_layer,
            primary_key_name=self.task.primary_key_name,
            task_parameters=self.task.task_parameters
        )

        # Update task state from executor result
        if result is True and hasattr(executor, '_last_expression'):
            self.task.expression = executor._last_expression

        return result

    def try_v3_spatial_filter(self, layer, layer_props, predicates):
        """Try v3 TaskBridge spatial filter.

        Phase E13: Delegates to SpatialFilterExecutor.

        Args:
            layer: Target QgsVectorLayer.
            layer_props: Layer properties dict.
            predicates: List of spatial predicates.

        Returns:
            True/False if v3 handled it, None to signal fallback to legacy.
        """
        executor = self.task._get_spatial_executor()

        result = executor.try_v3_spatial_filter(
            layer=layer,
            layer_props=layer_props,
            predicates=predicates,
            task_bridge=self.task._task_bridge,
            source_layer=self.task.source_layer,
            task_parameters=self.task.task_parameters,
            combine_operator=self.task._get_combine_operator() or 'AND'
        )

        return result

    def try_v3_multi_step_filter(self, layers_dict, progress_callback=None):
        """Try v3 TaskBridge multi-step filter.

        Args:
            layers_dict: Dict mapping provider types to layer lists.
            progress_callback: Optional callback(step_num, total_steps, step_name).

        Returns:
            True if v3 handled it, None to signal fallback to legacy.
        """
        if not self.task._task_bridge:
            return None

        # Check if TaskBridge supports multi-step
        if not self.task._task_bridge.supports_multi_step():
            logger.debug("TaskBridge: multi-step not supported - using legacy code")
            return None

        # CRITICAL v4.1.1 (2026-01-17): Disable V3 for PostgreSQL spatial filtering
        # The V3 PostgreSQLBackend does not generate proper EXISTS subqueries.
        # It sends raw SQL placeholders like "SPATIAL_FILTER(intersects)" which fail.
        # Use legacy PostgreSQLGeometricFilter which properly generates EXISTS clauses.
        if 'postgresql' in layers_dict and len(layers_dict.get('postgresql', [])) > 0:
            logger.debug("TaskBridge: PostgreSQL spatial filtering - using legacy code (V3 not ready)")
            return None

        # CRITICAL v4.1.2 (2026-01-19): Disable V3 for OGR spatial filtering
        # Same issue as PostgreSQL: V3 sends "SPATIAL_FILTER(intersects)" placeholder
        # which is not a valid QGIS expression function, causing:
        # "La fonction SPATIAL_FILTER est inconnue" error
        # Use legacy OGRExpressionBuilder.apply_filter() which uses QGIS processing
        if 'ogr' in layers_dict and len(layers_dict.get('ogr', [])) > 0:
            logger.debug("TaskBridge: OGR spatial filtering - using legacy code (V3 not ready)")
            return None

        # Skip multi-step for complex scenarios
        # Check for buffers which require special handling (both positive and negative)
        # Handle negative buffers (erosion) as well as positive buffers
        buffer_value = self.task.task_parameters.get("task", {}).get("buffer_value", 0)
        if buffer_value and buffer_value != 0:
            buffer_type = "expansion" if buffer_value > 0 else "erosion"
            logger.debug(f"TaskBridge: buffer active ({buffer_value}m {buffer_type}) - using legacy multi-step code")
            return None

        # Count total layers
        total_layers = sum(len(layer_list) for layer_list in layers_dict.values())
        if total_layers == 0:
            return True  # Nothing to filter

        try:
            logger.info("=" * 70)
            logger.info("V3 TASKBRIDGE: Attempting multi-step filter")
            logger.info("=" * 70)
            logger.info(f"   Total distant layers: {total_layers}")

            # Build step configurations for each layer
            steps = []
            for provider_type, layer_list in layers_dict.items():
                for layer, layer_props in layer_list:
                    # Get predicates from layer_props or default to intersects
                    predicates = layer_props.get('predicates', ['intersects'])

                    # Build spatial expression from predicates
                    # Format: SPATIAL_FILTER(predicate1, predicate2, ...)
                    predicate_str = ', '.join(predicates) if predicates else 'intersects'
                    spatial_expression = f"SPATIAL_FILTER({predicate_str})"

                    step_config = {
                        'expression': spatial_expression,  # Required by TaskBridge
                        'target_layer_ids': [layer.id()],
                        'predicates': predicates,
                        'step_name': f"Filter {layer.name()}",
                        'use_previous_result': False  # Each layer filtered independently
                    }
                    steps.append(step_config)
                    logger.debug(f"   Step for {layer.name()}: predicates={predicates}, expression={spatial_expression}")

            # FIX 2026-01-16: Log source geometry diagnostic
            logger.info("=" * 70)
            logger.info("MULTI-STEP SOURCE GEOMETRY DIAGNOSTIC")
            logger.debug(f"   Source layer: {self.task.source_layer.name()} (provider: {self.task.param_source_provider_type})")
            logger.info(f"   Source feature count: {self.task.source_layer.featureCount()}")
            logger.info(f"   Source CRS: {self.task.source_layer.crs().authid() if self.task.source_layer.crs() else 'UNKNOWN'}")
            logger.info(f"   Target layers: {len(steps)}")
            for idx, (provider_type, layer_list) in enumerate(layers_dict.items(), 1):
                for layer, layer_props in layer_list:
                    logger.info(f"   {idx}. {layer.name()}:")
                    logger.info(f"      - Provider: {layer.providerType()}")
                    logger.info(f"      - CRS: {layer.crs().authid() if layer.crs() else 'UNKNOWN'}")
                    logger.info(f"      - Geometry column: {layer_props.get('layer_geometry_field', 'UNKNOWN')}")
                    logger.info(f"      - Primary key: {layer_props.get('layer_key_column_name', 'UNKNOWN')}")
            logger.info("=" * 70)

            # Define progress callback adapter
            def bridge_progress(step_num, total_steps, step_name):
                if progress_callback:
                    progress_callback(step_num, total_steps, step_name)
                self.task.setDescription(f"V3 Multi-step: {step_name}")
                self.task.setProgress(int((step_num / total_steps) * 100))

            # Execute via TaskBridge
            bridge_result = self.task._task_bridge.execute_multi_step_filter(
                source_layer=self.task.source_layer,
                steps=steps,
                progress_callback=bridge_progress
            )

            if bridge_result.status == BridgeStatus.SUCCESS and bridge_result.success:
                logger.info("=" * 70)
                logger.info("V3 TaskBridge MULTI-STEP SUCCESS")
                logger.info(f"   Backend used: {bridge_result.backend_used}")
                logger.info(f"   Final feature count: {bridge_result.feature_count}")
                logger.debug(f"   Total execution time: {bridge_result.execution_time_ms:.1f}ms")
                logger.info("=" * 70)

                # Store metrics
                if 'actual_backends' not in self.task.task_parameters:
                    self.task.task_parameters['actual_backends'] = {}
                self.task.task_parameters['actual_backends']['_multi_step'] = f"v3_{bridge_result.backend_used}"

                return True

            elif bridge_result.status == BridgeStatus.FALLBACK:
                logger.info("V3 TaskBridge MULTI-STEP: FALLBACK requested")
                logger.info(f"   Reason: {bridge_result.error_message}")
                return None

            else:
                logger.debug(f"TaskBridge multi-step: status={bridge_result.status}, falling back")
                return None

        except Exception as e:  # catch-all safety net: v3 bridge failure falls back to legacy
            logger.warning(f"TaskBridge multi-step delegation failed: {e}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            return None

    def try_v3_export(self, layer, output_path, format_type, progress_callback=None):
        """Try v3 TaskBridge streaming export.

        Args:
            layer: Source QgsVectorLayer.
            output_path: Output file path.
            format_type: Export format type string.
            progress_callback: Optional progress callback.

        Returns:
            True if v3 handled it, None to signal fallback to legacy.
        """
        if not self.task._task_bridge:
            return None

        # Check if TaskBridge supports export
        if not self.task._task_bridge.supports_export():
            logger.debug("TaskBridge: export not supported - using legacy code")
            return None

        try:
            logger.info("=" * 60)
            logger.info("V3 TASKBRIDGE: Attempting streaming export")
            logger.info("=" * 60)
            logger.info(f"   Layer: '{layer.name()}'")
            logger.info(f"   Format: {format_type}")
            logger.info(f"   Output: {output_path}")

            # Define cancel check
            def cancel_check():
                return self.task.isCanceled()

            bridge_result = self.task._task_bridge.execute_export(
                source_layer=layer,
                output_path=output_path,
                format=format_type,
                progress_callback=progress_callback,
                cancel_check=cancel_check
            )

            if bridge_result.status == BridgeStatus.SUCCESS and bridge_result.success:
                logger.info("V3 TaskBridge EXPORT SUCCESS")
                logger.info(f"   Features exported: {bridge_result.feature_count}")
                logger.debug(f"   Execution time: {bridge_result.execution_time_ms:.1f}ms")

                # Store in task_parameters for metrics
                if 'actual_backends' not in self.task.task_parameters:
                    self.task.task_parameters['actual_backends'] = {}
                self.task.task_parameters['actual_backends'][f'export_{layer.id()}'] = 'v3_streaming'

                return True

            elif bridge_result.status == BridgeStatus.FALLBACK:
                logger.info("V3 TaskBridge EXPORT: FALLBACK requested")
                logger.info(f"   Reason: {bridge_result.error_message}")
                return None

            else:
                logger.debug(f"TaskBridge export: status={bridge_result.status}")
                return None

        except Exception as e:  # catch-all safety net: v3 bridge failure falls back to legacy
            logger.warning(f"TaskBridge export delegation failed: {e}")
            return None
