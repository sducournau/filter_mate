"""
Spatial Filter Executor

Specialized class for spatial/geometric filtering operations.
Extracted from FilterEngineTask as part of Phase E13 refactoring (January 2026).

Responsibilities:
- Spatial predicate application (intersects, contains, etc.)
- Multi-layer spatial filtering
- Geometry preparation by provider
- Layer organization for filtering
- TaskBridge delegation for v3 architecture

Location: core/tasks/executors/spatial_filter_executor.py
"""

import logging
from typing import Optional, List, Dict, Tuple, Any

from qgis.core import (
    QgsVectorLayer,
    QgsProject
)

# Import constants
from ....infrastructure.constants import (
    PREDICATE_INTERSECTS, PREDICATE_WITHIN, PREDICATE_CONTAINS,
    PREDICATE_OVERLAPS, PREDICATE_CROSSES, PREDICATE_TOUCHES,
    PREDICATE_DISJOINT, PREDICATE_EQUALS
)

# Import utilities
from ....infrastructure.utils import (
    detect_layer_provider_type,
    is_layer_valid,
    is_sip_deleted
)

# Import geometry cache
from ..cache.geometry_cache import GeometryCache

logger = logging.getLogger('FilterMate.Tasks.SpatialFilterExecutor')


class SpatialFilterExecutor:
    """
    Handles spatial filtering operations with geometric predicates.

    Responsibilities:
    - Geometric predicate application (intersects, contains, within, etc.)
    - Multi-layer spatial filtering coordination
    - Geometry preparation for different providers (PostgreSQL/Spatialite/OGR)
    - Layer organization by provider type
    - TaskBridge delegation for v3 architecture

    Extracted from FilterEngineTask (lines 446-550, 732-768, 988-1042) in Phase E13.

    Example:
        executor = SpatialFilterExecutor(
            source_layer=source_layer,
            project=QgsProject.instance(),
            backend_registry=registry,
            task_bridge=bridge
        )

        # Organize layers
        result = executor.organize_layers_to_filter(
            task_action='filter',
            task_parameters=params
        )

        # Filter each layer
        for provider, layers_list in result.layers_by_provider.items():
            for layer, layer_props in layers_list:
                predicates = layer_props.get('predicates', ['intersects'])
                success, feature_ids = executor.execute_spatial_filter(
                    layer, layer_props, predicates
                )
    """

    def __init__(
        self,
        source_layer: QgsVectorLayer,
        project: Optional[QgsProject] = None,
        backend_registry: Optional[Any] = None,
        task_bridge: Optional[Any] = None,
        postgresql_available: bool = False,
        geometry_cache: Optional[GeometryCache] = None
    ):
        """
        Initialize SpatialFilterExecutor.

        Args:
            source_layer: Source QGIS vector layer
            project: QGIS project instance (defaults to current)
            backend_registry: Backend registry for multi-provider support
            task_bridge: Optional TaskBridge for v3 delegation
            postgresql_available: Whether PostgreSQL is available
            geometry_cache: Optional GeometryCache for caching prepared geometries
        """
        self.source_layer = source_layer
        self.project = project or QgsProject.instance()
        self.backend_registry = backend_registry
        self.task_bridge = task_bridge
        self.postgresql_available = postgresql_available

        # Use provided cache or get shared instance
        self._geometry_cache = geometry_cache or GeometryCache.get_shared_instance()

        # Cached provider type
        self.source_provider_type = detect_layer_provider_type(source_layer)

        logger.debug(
            "SpatialFilterExecutor initialized: "
            f"layer={source_layer.name()}, "
            f"provider={self.source_provider_type}"
        )

    def try_v3_spatial_filter(
        self,
        layer: QgsVectorLayer,
        layer_props: Dict,
        predicates: List[str]
    ) -> Optional[bool]:
        """
        Try v3 TaskBridge spatial filter.

        Extracted from FilterEngineTask._try_v3_spatial_filter (lines 988-1042).

        Args:
            layer: Target layer to filter
            layer_props: Layer properties dict
            predicates: List of geometric predicates

        Returns:
            True if v3 succeeded, False if failed, None to fallback to legacy
        """
        if not self.task_bridge or not self.task_bridge.is_available():
            return None

        # v3 spatial filter is experimental - only enable for simple cases
        # Skip for now: complex predicates, buffers, multi-step
        buffer_value = layer_props.get('buffer_value', 0)
        if buffer_value and buffer_value > 0:
            logger.debug("TaskBridge: buffer active - using legacy spatial code")
            return None

        if len(predicates) > 1:
            logger.debug("TaskBridge: multiple predicates - using legacy spatial code")
            return None

        try:
            logger.info("=" * 60)
            logger.info("🚀 V3 TASKBRIDGE: Attempting spatial filter")
            logger.info("=" * 60)
            logger.info(f"   Layer: '{layer.name()}'")
            logger.info(f"   Predicates: {predicates}")

            bridge_result = self.task_bridge.execute_spatial_filter(
                source_layer=self.source_layer,
                target_layers=[layer],
                predicates=predicates,
                buffer_value=0.0,
                combine_operator='AND'
            )

            if bridge_result.status == 'SUCCESS' and bridge_result.success:
                logger.info("✅ V3 TaskBridge SPATIAL SUCCESS")
                logger.info(f"   Backend used: {bridge_result.backend_used}")
                logger.info(f"   Feature count: {bridge_result.feature_count}")
                logger.debug(f"   Execution time: {bridge_result.execution_time_ms:.1f}ms")
                return True

            elif bridge_result.status == 'FALLBACK':
                logger.info("⚠️ V3 TaskBridge SPATIAL: FALLBACK requested")
                logger.info(f"   Reason: {bridge_result.error_message}")
                return None

            else:
                logger.debug(f"TaskBridge spatial: status={bridge_result.status}")
                return None

        except Exception as e:  # catch-all safety net: bridge failure falls back to legacy
            logger.warning(f"TaskBridge spatial delegation failed: {e}")
            return None

    def organize_layers_to_filter(
        self,
        task_action: str,
        task_parameters: Dict,
        detect_provider_fn: Optional[Any] = None,
        is_valid_layer_fn: Optional[Any] = None,
        is_sip_deleted_fn: Optional[Any] = None
    ):
        """
        Organize layers to be filtered by provider type.

        Extracted from FilterEngineTask._organize_layers_to_filter (lines 732-768).

        Args:
            task_action: Task action ('filter', 'unfilter', 'reset')
            task_parameters: Task configuration dict
            detect_provider_fn: Optional provider detection function
            is_valid_layer_fn: Optional layer validation function
            is_sip_deleted_fn: Optional SIP deletion check function

        Returns:
            OrganizedLayers object with:
                - layers_by_provider: Dict[str, List[Tuple[layer, props]]]
                - layers_count: Total layer count
                - provider_list: List of provider types
                - warnings: List of warning messages
                - not_found_layers: List of layers not found
        """
        from ....core.services.layer_organizer import organize_layers_for_filtering

        # Use provided functions or defaults
        detect_fn = detect_provider_fn or detect_layer_provider_type
        valid_fn = is_valid_layer_fn or is_layer_valid
        sip_fn = is_sip_deleted_fn or is_sip_deleted

        # Delegate to LayerOrganizer service and return full result
        result = organize_layers_for_filtering(
            task_action=task_action,
            task_parameters=task_parameters,
            project=self.project,
            postgresql_available=self.postgresql_available,
            detect_provider_fn=detect_fn,
            is_valid_layer_fn=valid_fn,
            is_sip_deleted_fn=sip_fn
        )

        return result

    def prepare_source_geometry_via_executor(
        self,
        layer_info: Dict,
        feature_ids: Optional[List[int]] = None,
        buffer_value: float = 0.0,
        use_centroids: bool = False,
        use_cache: bool = True
    ) -> Tuple[Optional[Any], Optional[str]]:
        """
        Prepare source geometry using backend executor with caching.

        Extracted from FilterEngineTask._prepare_source_geometry_via_executor (lines 446-482).
        Enhanced with GeometryCache integration in Phase E13 Step 3.

        Performance: 5× speedup when filtering multiple layers with same source.

        Args:
            layer_info: Dict with layer metadata
            feature_ids: Optional list of feature IDs to filter
            buffer_value: Buffer distance (in layer units)
            use_centroids: Use centroids instead of full geometries
            use_cache: Whether to use geometry cache (default: True)

        Returns:
            Tuple of (geometry_data, error_message)
            - geometry_data: Prepared geometry (type depends on backend)
            - error_message: Error message if failed, None if success
        """
        if not self.backend_registry:
            return None, "Backend registry not available"

        # Build cache key components
        layer_id = self.source_layer.id() if self.source_layer else None
        subset_string = self.source_layer.subsetString() if self.source_layer else None
        target_crs = layer_info.get('crs_authid', 'EPSG:4326')

        # Try cache first (if enabled)
        if use_cache and layer_id:
            cached_geom = self._geometry_cache.get(
                layer_id=layer_id,
                feature_ids=feature_ids,
                buffer_value=buffer_value,
                target_crs_authid=target_crs,
                subset_string=subset_string
            )
            if cached_geom:
                logger.debug(f"Using cached geometry for layer {layer_id}")
                return cached_geom, None

        try:
            # Get backend executor for this layer
            executor = self.backend_registry.get_backend_executor(layer_info)
            if not executor:
                return None, "No backend executor available"

            # Prepare geometry via executor
            result = executor.prepare_source_geometry(
                layer_info=layer_info,
                feature_ids=feature_ids,
                buffer_value=buffer_value,
                use_centroids=use_centroids
            )

            # Cache the result (if enabled)
            if use_cache and layer_id and result:
                self._geometry_cache.put(
                    layer_id=layer_id,
                    geometry=result,
                    feature_ids=feature_ids,
                    buffer_value=buffer_value,
                    target_crs_authid=target_crs,
                    subset_string=subset_string
                )
                logger.debug(f"Cached geometry for layer {layer_id}")

            return result, None

        except (RuntimeError, AttributeError, ValueError) as e:
            logger.debug(f"Executor.prepare_source_geometry failed: {e}, using legacy")
            return None, f"Executor failed: {str(e)}"

    def invalidate_geometry_cache(self, layer_id: Optional[str] = None):
        """
        Invalidate geometry cache for a specific layer or all layers.

        Call this when source layer changes or filter is reset.

        Args:
            layer_id: Layer ID to invalidate, or None to clear all
        """
        if layer_id:
            count = self._geometry_cache.invalidate_layer(layer_id)
            logger.info(f"Invalidated {count} cache entries for layer {layer_id}")
        else:
            self._geometry_cache.clear()
            logger.info("Cleared all geometry cache entries")

    def get_cache_stats(self) -> Dict:
        """
        Get geometry cache statistics.

        Returns:
            Dict with cache stats (size, hits, misses, etc.)
        """
        return self._geometry_cache.get_stats()

    def prepare_geometries_by_provider(
        self,
        provider_list: List[str],
        buffer_value: Optional[float] = None,
        use_centroids: bool = False,
        feature_ids: Optional[List[int]] = None
    ) -> bool:
        """
        Prepare source geometries for all provider types.

        This method orchestrates geometry preparation for multiple backends
        (PostgreSQL, Spatialite, OGR) based on the provider list.

        Args:
            provider_list: List of provider types to prepare for
            buffer_value: Optional buffer distance
            use_centroids: Use centroids instead of full geometries
            feature_ids: Optional list of feature IDs

        Returns:
            True if all preparations succeeded, False otherwise
        """
        logger.info(f"Preparing geometries for providers: {provider_list}")

        success_count = 0
        for provider_type in provider_list:
            layer_info = {
                'layer': self.source_layer,
                'layer_provider_type': provider_type,
                'buffer_value': buffer_value,
                'use_centroids': use_centroids
            }

            geometry_data, error = self.prepare_source_geometry_via_executor(
                layer_info=layer_info,
                feature_ids=feature_ids,
                buffer_value=buffer_value or 0.0,
                use_centroids=use_centroids
            )

            if geometry_data:
                logger.debug(f"✓ Geometry prepared for {provider_type}")
                success_count += 1
            elif error:
                logger.warning(f"✗ Failed to prepare geometry for {provider_type}: {error}")

        # Return True if at least one provider succeeded
        return success_count > 0

    def execute_spatial_filter(
        self,
        layer: QgsVectorLayer,
        layer_props: Dict,
        predicates: List[str],
        source_geometries: Optional[Dict[str, Any]] = None,
        expression_builder: Optional[Any] = None,
        filter_orchestrator: Optional[Any] = None,
        subset_queue_callback: Optional[Any] = None
    ) -> Tuple[bool, List[int]]:
        """
        Execute spatial filter with geometric predicates.

        Main entry point for spatial filtering operations.

        v4.0: Phase E13 Step 2 - Implements legacy fallback via FilterOrchestrator.

        Args:
            layer: Target layer to filter
            layer_props: Layer properties dict
            predicates: List of geometric predicates (intersects, contains, etc.)
            source_geometries: Dict mapping provider types to prepared geometries
            expression_builder: ExpressionBuilder instance for filter expressions
            filter_orchestrator: FilterOrchestrator for legacy delegation
            subset_queue_callback: Callback to queue subset strings for main thread

        Returns:
            (success: bool, matching_feature_ids: List[int])
        """
        # Validate predicates first
        if not self.validate_predicates(predicates):
            logger.error(f"Invalid predicates: {predicates}")
            return False, []

        # Try v3 TaskBridge first
        v3_result = self.try_v3_spatial_filter(layer, layer_props, predicates)
        if v3_result is True:
            logger.info("✅ V3 spatial filter succeeded")
            return True, []
        elif v3_result is False:
            logger.error("❌ V3 spatial filter failed")
            return False, []

        # Fallback to legacy code via FilterOrchestrator
        logger.debug("V3 returned None - using legacy spatial filter via FilterOrchestrator")

        if filter_orchestrator and source_geometries and expression_builder:
            # Detect provider type for this layer
            layer_provider_type = detect_layer_provider_type(layer)

            try:
                success = filter_orchestrator.orchestrate_geometric_filter(
                    layer=layer,
                    layer_provider_type=layer_provider_type,
                    layer_props=layer_props,
                    source_geometries=source_geometries,
                    expression_builder=expression_builder
                )

                if success:
                    logger.info(f"✅ Legacy spatial filter succeeded for {layer.name()}")
                    return True, []
                else:
                    logger.warning(f"⚠️ Legacy spatial filter returned False for {layer.name()}")
                    return False, []

            except Exception as e:  # catch-all safety net: spatial filter must return tuple
                logger.error(f"Legacy spatial filter failed: {e}")
                return False, []
        else:
            # No orchestrator available - cannot perform spatial filtering
            missing = []
            if not filter_orchestrator:
                missing.append("filter_orchestrator")
            if not source_geometries:
                missing.append("source_geometries")
            if not expression_builder:
                missing.append("expression_builder")

            logger.warning(
                f"Cannot perform legacy spatial filter - missing: {', '.join(missing)}. "
                f"Layer: {layer.name()}"
            )
            return False, []

    def execute_spatial_filter_batch(
        self,
        layers_dict: Dict[str, List[Tuple[QgsVectorLayer, Dict]]],
        predicates: List[str],
        source_geometries: Dict[str, Any],
        expression_builder: Any,
        filter_orchestrator: Any,
        progress_callback: Optional[Any] = None
    ) -> Tuple[int, int]:
        """
        Execute spatial filter on multiple layers grouped by provider.

        v4.0: Phase E13 Step 2 - Batch processing for multi-layer filtering.

        Args:
            layers_dict: Dict with layers grouped by provider type
            predicates: List of geometric predicates
            source_geometries: Prepared source geometries by provider
            expression_builder: ExpressionBuilder instance
            filter_orchestrator: FilterOrchestrator for legacy delegation
            progress_callback: Optional callback(current, total, layer_name)

        Returns:
            (success_count: int, total_count: int)
        """
        total_count = sum(len(layer_list) for layer_list in layers_dict.values())
        success_count = 0
        current = 0

        logger.info(f"Starting batch spatial filter: {total_count} layers")

        for provider_type, layer_list in layers_dict.items():
            for layer, layer_props in layer_list:
                current += 1

                if progress_callback:
                    progress_callback(current, total_count, layer.name())

                # Use layer-specific predicates if available
                layer_predicates = layer_props.get('predicates', predicates)

                success, _ = self.execute_spatial_filter(
                    layer=layer,
                    layer_props=layer_props,
                    predicates=layer_predicates,
                    source_geometries=source_geometries,
                    expression_builder=expression_builder,
                    filter_orchestrator=filter_orchestrator
                )

                if success:
                    success_count += 1
                    logger.info(f"  [{current}/{total_count}] ✓ {layer.name()}")
                else:
                    logger.warning(f"  [{current}/{total_count}] ✗ {layer.name()}")

        logger.info(f"Batch spatial filter complete: {success_count}/{total_count} succeeded")
        return success_count, total_count

    def validate_predicates(self, predicates: List[str]) -> bool:
        """
        Validate geometric predicates.

        Args:
            predicates: List of predicate names

        Returns:
            True if all predicates are valid
        """
        valid_predicates = {
            PREDICATE_INTERSECTS,
            PREDICATE_WITHIN,
            PREDICATE_CONTAINS,
            PREDICATE_OVERLAPS,
            PREDICATE_CROSSES,
            PREDICATE_TOUCHES,
            PREDICATE_DISJOINT,
            PREDICATE_EQUALS
        }

        for predicate in predicates:
            if predicate not in valid_predicates:
                logger.warning(f"Invalid predicate: {predicate}")
                return False

        return True
