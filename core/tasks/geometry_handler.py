"""
Geometry Handler for FilterEngineTask

Handles all geometry preparation, buffer operations, memory layer management,
and spatial utility operations. Extracted from FilterEngineTask as part of the
C1 God Object decomposition (Phase 3).

This handler manages:
- Source geometry preparation (PostgreSQL, Spatialite, OGR)
- Geometry simplification and optimization
- Buffer operations with fallback strategies
- Memory layer creation and management (copy, centroid conversion)
- Spatial index verification
- Geometry repair and WKT conversion

Location: core/tasks/geometry_handler.py (Hexagonal Architecture - Application Layer)

Thread Safety:
    All methods are designed to be called from worker threads. They operate
    on QGIS processing algorithms and memory layers which are safe to use
    in background tasks (as opposed to map layer registry operations).
"""

import logging
import os
from typing import Any, Callable, Dict, List, Optional

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsProcessing,
    QgsProcessingContext,
    QgsProcessingFeedback,
    QgsVectorLayer,
)
from qgis import processing

from ...infrastructure.logging import setup_logger
from ...config.config import ENV_VARS
from ..ports.backend_services import get_backend_services

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.Geometry',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# Lazy-load constants
from ...infrastructure.constants import (
    PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR
)


class GeometryHandler:
    """Handles geometry preparation and spatial operations for FilterEngineTask.

    Encapsulates geometry-related logic previously embedded in FilterEngineTask.
    All dependencies are received explicitly via method parameters.

    Example:
        >>> handler = GeometryHandler()
        >>> wkt = handler.geometry_to_wkt(geometry, 'EPSG:4326')
        >>> layer = handler.reproject_layer(source_layer, target_crs)
    """

    def __init__(self):
        """Initialize GeometryHandler with backend services facade."""
        self._backend_services = get_backend_services()

    # =========================================================================
    # Optimization and Configuration
    # =========================================================================

    def get_optimization_thresholds(self, task_parameters: Optional[Dict] = None) -> Dict:
        """Get optimization thresholds config.

        Args:
            task_parameters: Task configuration dict (optional)

        Returns:
            dict: Optimization thresholds
        """
        from ..optimization.config_provider import get_optimization_thresholds
        return get_optimization_thresholds(task_parameters)

    def get_simplification_config(self, task_parameters: Optional[Dict] = None) -> Dict:
        """Get geometry simplification config.

        Args:
            task_parameters: Task configuration dict (optional)

        Returns:
            dict: Simplification configuration
        """
        from ..optimization.config_provider import get_simplification_config
        return get_simplification_config(task_parameters)

    # =========================================================================
    # WKT and Precision
    # =========================================================================

    def get_wkt_precision(self, crs_authid: Optional[str] = None) -> int:
        """Get appropriate WKT precision based on CRS units.

        Args:
            crs_authid: CRS authority ID (e.g., 'EPSG:4326')

        Returns:
            int: Number of decimal places for WKT
        """
        from ..services.buffer_service import BufferService
        return BufferService().get_wkt_precision(crs_authid)

    def geometry_to_wkt(
        self,
        geometry: Any,
        crs_authid: Optional[str] = None,
    ) -> str:
        """Convert geometry to WKT with optimized precision based on CRS.

        Args:
            geometry: QgsGeometry to convert
            crs_authid: CRS authority ID for precision calculation

        Returns:
            str: WKT representation, or empty string if geometry is invalid
        """
        if geometry is None or geometry.isEmpty():
            return ""
        precision = self.get_wkt_precision(crs_authid)
        wkt = geometry.asWkt(precision)
        logger.debug(f"  WKT precision: {precision} decimals (CRS: {crs_authid})")
        return wkt

    # =========================================================================
    # Buffer Operations
    # =========================================================================

    def get_buffer_aware_tolerance(
        self,
        buffer_value: Optional[float],
        buffer_segments: int,
        buffer_type: Any,
        extent_size: float,
        is_geographic: bool = False,
    ) -> float:
        """Calculate optimal simplification tolerance.

        Args:
            buffer_value: Buffer distance value
            buffer_segments: Number of buffer segments
            buffer_type: Buffer end cap style
            extent_size: Size of the layer extent
            is_geographic: Whether the CRS is geographic

        Returns:
            float: Simplification tolerance
        """
        from ..services.buffer_service import BufferService, BufferConfig, BufferEndCapStyle
        config = BufferConfig(
            distance=buffer_value or 0,
            segments=buffer_segments,
            end_cap_style=BufferEndCapStyle(buffer_type),
        )
        return BufferService().calculate_buffer_aware_tolerance(config, extent_size, is_geographic)

    def apply_qgis_buffer(
        self,
        layer: QgsVectorLayer,
        buffer_distance: Any,
        param_buffer_type: int,
        param_buffer_segments: int,
        outputs: Dict,
    ) -> QgsVectorLayer:
        """Apply buffer using QGIS processing algorithm.

        Args:
            layer: Input layer to buffer
            buffer_distance: Buffer distance (float or QgsProperty)
            param_buffer_type: Buffer end cap type
            param_buffer_segments: Number of segments
            outputs: Task outputs dict for storing intermediate results

        Returns:
            QgsVectorLayer: Buffered layer

        Raises:
            Exception: If buffer operation fails
        """
        try:
            from ..geometry import apply_qgis_buffer, BufferConfig
            config = BufferConfig(
                buffer_type=param_buffer_type,
                buffer_segments=param_buffer_segments,
                dissolve=True,
            )
            buffered_layer = apply_qgis_buffer(
                layer, buffer_distance, config,
                self.convert_geometry_collection_to_multipolygon
            )
            outputs['alg_source_layer_params_buffer'] = {'OUTPUT': buffered_layer}
            return buffered_layer
        except ImportError as e:
            logger.error(f"core.geometry module not available: {e}")
            raise Exception(f"Buffer operation requires core.geometry module: {e}")
        except (RuntimeError, ValueError, AttributeError) as e:
            logger.error(f"Buffer operation failed: {e}")
            raise

    def apply_buffer_with_fallback(
        self,
        layer: QgsVectorLayer,
        buffer_distance: Any,
        param_buffer_type: int,
        param_buffer_segments: int,
        outputs: Dict,
        verify_spatial_index_fn: Callable,
        store_warning_fn: Callable,
    ) -> Optional[QgsVectorLayer]:
        """Apply buffer with fallback to manual method.

        Validates geometries before buffering and tries QGIS algorithm first,
        then falls back to manual buffer if the algorithm fails.

        Args:
            layer: Input layer to buffer
            buffer_distance: Buffer distance
            param_buffer_type: Buffer end cap type
            param_buffer_segments: Number of segments
            outputs: Task outputs dict
            verify_spatial_index_fn: Function to verify/create spatial index
            store_warning_fn: Function to store warning messages

        Returns:
            QgsVectorLayer or None if buffer fails completely
        """
        logger.info(f"Applying buffer: distance={buffer_distance}")

        if layer is None:
            logger.error("_apply_buffer_with_fallback: Input layer is None")
            return None

        if not layer.isValid():
            logger.error("_apply_buffer_with_fallback: Input layer is not valid")
            return None

        if layer.featureCount() == 0:
            logger.warning("_apply_buffer_with_fallback: Input layer has no features")
            return None

        result = None

        try:
            result = self.apply_qgis_buffer(
                layer, buffer_distance, param_buffer_type, param_buffer_segments, outputs
            )
            if result is None or not result.isValid() or result.featureCount() == 0:
                logger.warning("_apply_qgis_buffer returned invalid/empty result, trying manual buffer")
                raise ValueError("QGIS buffer returned invalid result")

        except (RuntimeError, ValueError, AttributeError) as e:
            logger.warning(f"QGIS buffer algorithm failed: {str(e)}, using manual buffer approach")
            try:
                result = self.create_buffered_memory_layer(
                    layer, buffer_distance, param_buffer_segments,
                    verify_spatial_index_fn, store_warning_fn
                )
                if result is None or not result.isValid() or result.featureCount() == 0:
                    logger.error("Manual buffer also returned invalid/empty result")
                    return None
            except (RuntimeError, ValueError, AttributeError) as manual_error:
                logger.error(f"Both buffer methods failed. QGIS: {str(e)}, Manual: {str(manual_error)}")
                return None

        # Apply post-buffer simplification
        if result is not None and result.isValid() and result.featureCount() > 0:
            result = self.simplify_buffer_result(result, buffer_distance, verify_spatial_index_fn)

        return result

    def simplify_buffer_result(
        self,
        layer: QgsVectorLayer,
        buffer_distance: float,
        verify_spatial_index_fn: Callable,
    ) -> QgsVectorLayer:
        """Simplify polygon(s) from buffer operations.

        Args:
            layer: Buffered layer to simplify
            buffer_distance: Original buffer distance
            verify_spatial_index_fn: Function to verify/create spatial index

        Returns:
            QgsVectorLayer: Simplified layer
        """
        from ..backends.auto_optimizer import get_auto_optimization_config
        from ..geometry import simplify_buffer_result
        config = get_auto_optimization_config()
        return simplify_buffer_result(
            layer=layer,
            buffer_distance=buffer_distance,
            auto_simplify=config.get('auto_simplify_after_buffer', True),
            tolerance=config.get('buffer_simplify_after_tolerance', 0.5),
            verify_spatial_index_fn=verify_spatial_index_fn,
        )

    # =========================================================================
    # Geometry Simplification
    # =========================================================================

    def simplify_geometry_adaptive(
        self,
        geometry: Any,
        max_wkt_length: Optional[int] = None,
        crs_authid: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_segments: int = 5,
        buffer_type: int = 0,
    ) -> Any:
        """Simplify geometry adaptively using GeometryPreparationAdapter.

        Args:
            geometry: QgsGeometry to simplify
            max_wkt_length: Maximum WKT string length
            crs_authid: CRS authority ID
            buffer_value: Buffer distance value
            buffer_segments: Number of buffer segments
            buffer_type: Buffer end cap type

        Returns:
            QgsGeometry: Simplified geometry (or original on failure)
        """
        if not geometry or geometry.isEmpty():
            return geometry

        try:
            AdapterClass = self._backend_services.get_geometry_preparation_adapter()
            if AdapterClass is None:
                logger.warning("GeometryPreparationAdapter not available, returning original geometry")
                return geometry

            result = AdapterClass().simplify_geometry_adaptive(
                geometry=geometry,
                max_wkt_length=max_wkt_length,
                crs_authid=crs_authid,
                buffer_value=buffer_value,
                buffer_segments=buffer_segments,
                buffer_type=buffer_type,
            )

            if result.success and result.geometry:
                return result.geometry
            logger.warning(f"GeometryPreparationAdapter simplify failed: {result.message}")
            return geometry
        except ImportError as e:
            logger.error(f"GeometryPreparationAdapter not available: {e}")
            return geometry
        except (RuntimeError, ValueError, AttributeError) as e:
            logger.error(f"GeometryPreparationAdapter simplify error: {e}")
            return geometry

    # =========================================================================
    # Memory Layer Operations
    # =========================================================================

    def copy_filtered_layer_to_memory(
        self,
        layer: QgsVectorLayer,
        layer_name: str = "filtered_copy",
        verify_spatial_index_fn: Optional[Callable] = None,
    ) -> QgsVectorLayer:
        """Copy filtered layer to memory layer.

        Args:
            layer: Source QgsVectorLayer
            layer_name: Name for the memory layer
            verify_spatial_index_fn: Optional function to verify/create spatial index

        Returns:
            QgsVectorLayer: Memory layer copy

        Raises:
            Exception: If copy fails
        """
        GeometryPreparationAdapter = self._backend_services.get_geometry_preparation_adapter()
        if GeometryPreparationAdapter is None:
            raise Exception("GeometryPreparationAdapter not available")
        result = GeometryPreparationAdapter().copy_filtered_to_memory(layer, layer_name)
        if result.success and result.layer:
            if verify_spatial_index_fn:
                verify_spatial_index_fn(result.layer, layer_name)
            return result.layer
        raise Exception(f"Failed to copy filtered layer: {result.error_message or 'Unknown'}")

    def copy_selected_features_to_memory(
        self,
        layer: QgsVectorLayer,
        layer_name: str = "selected_copy",
        verify_spatial_index_fn: Optional[Callable] = None,
    ) -> QgsVectorLayer:
        """Copy selected features to memory layer.

        Args:
            layer: Source QgsVectorLayer
            layer_name: Name for the memory layer
            verify_spatial_index_fn: Optional function to verify/create spatial index

        Returns:
            QgsVectorLayer: Memory layer with selected features

        Raises:
            Exception: If copy fails
        """
        GeometryPreparationAdapter = self._backend_services.get_geometry_preparation_adapter()
        if GeometryPreparationAdapter is None:
            raise Exception("GeometryPreparationAdapter not available")
        result = GeometryPreparationAdapter().copy_selected_to_memory(layer, layer_name)
        if result.success and result.layer:
            if verify_spatial_index_fn:
                verify_spatial_index_fn(result.layer, layer_name)
            return result.layer
        raise Exception(f"Failed to copy selected features: {result.error_message or 'Unknown'}")

    def create_memory_layer_from_features(
        self,
        features: List[QgsFeature],
        crs: QgsCoordinateReferenceSystem,
        layer_name: str = "from_features",
        verify_spatial_index_fn: Optional[Callable] = None,
    ) -> Optional[QgsVectorLayer]:
        """Create memory layer from QgsFeature objects.

        Args:
            features: List of QgsFeature objects
            crs: CRS for the memory layer
            layer_name: Name for the memory layer
            verify_spatial_index_fn: Optional function to verify/create spatial index

        Returns:
            QgsVectorLayer or None if creation fails
        """
        GeometryPreparationAdapter = self._backend_services.get_geometry_preparation_adapter()
        if GeometryPreparationAdapter is None:
            logger.error("GeometryPreparationAdapter not available")
            return None
        result = GeometryPreparationAdapter().create_memory_from_features(features, crs, layer_name)
        if result.success and result.layer:
            if verify_spatial_index_fn:
                verify_spatial_index_fn(result.layer, layer_name)
            return result.layer
        logger.error(f"_create_memory_layer_from_features failed: {result.error_message or 'Unknown'}")
        return None

    def convert_layer_to_centroids(self, layer: QgsVectorLayer) -> Optional[QgsVectorLayer]:
        """Convert layer geometries to centroids.

        Args:
            layer: Source QgsVectorLayer

        Returns:
            QgsVectorLayer with centroid geometries, or None on failure
        """
        GeometryPreparationAdapter = self._backend_services.get_geometry_preparation_adapter()
        if GeometryPreparationAdapter is None:
            logger.error("GeometryPreparationAdapter not available")
            return None
        result = GeometryPreparationAdapter().convert_to_centroids(layer)
        if result.success and result.layer:
            return result.layer
        logger.error(f"_convert_layer_to_centroids failed: {result.error_message or 'Unknown'}")
        return None

    # =========================================================================
    # Layer Operations
    # =========================================================================

    def reproject_layer(
        self,
        layer: QgsVectorLayer,
        target_crs: Any,
        outputs: Dict,
    ) -> QgsVectorLayer:
        """Reproject layer to target CRS without geometry validation.

        Args:
            layer: Input layer to reproject
            target_crs: Target CRS
            outputs: Task outputs dict for intermediate results

        Returns:
            QgsVectorLayer: Reprojected layer
        """
        alg_params = {
            'INPUT': layer,
            'TARGET_CRS': target_crs,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT,
        }

        context = QgsProcessingContext()
        context.setInvalidGeometryCheck(QgsFeatureRequest.GeometryNoCheck)
        feedback = QgsProcessingFeedback()

        outputs['alg_source_layer_params_reprojectlayer'] = processing.run(
            'qgis:reprojectlayer',
            alg_params,
            context=context,
            feedback=feedback,
        )
        layer = outputs['alg_source_layer_params_reprojectlayer']['OUTPUT']
        processing.run('qgis:createspatialindex', {"INPUT": layer})
        return layer

    def fix_invalid_geometries(self, layer: Any, output_key: str) -> Any:
        """Fix invalid geometries. DISABLED: Returns input layer unchanged.

        Args:
            layer: Input layer
            output_key: Output key (unused)

        Returns:
            Input layer unchanged
        """
        return layer

    def verify_and_create_spatial_index(
        self,
        layer: QgsVectorLayer,
        layer_name: Optional[str] = None,
    ) -> Any:
        """Verify/create spatial index on layer.

        Args:
            layer: QgsVectorLayer to index
            layer_name: Optional layer name for logging

        Returns:
            Result from spatial index creation
        """
        from ..geometry.spatial_index import verify_and_create_spatial_index
        return verify_and_create_spatial_index(layer, layer_name)

    # =========================================================================
    # Geometry Utility Delegates
    # =========================================================================

    def convert_geometry_collection_to_multipolygon(self, layer: Any) -> Any:
        """Convert GeometryCollection to MultiPolygon.

        Args:
            layer: Input layer with GeometryCollection features

        Returns:
            Layer with MultiPolygon geometries
        """
        from ..geometry import convert_geometry_collection_to_multipolygon
        return convert_geometry_collection_to_multipolygon(layer)

    def evaluate_buffer_distance(self, layer: QgsVectorLayer, buffer_param: Any) -> Any:
        """Evaluate buffer distance for a layer.

        Args:
            layer: QgsVectorLayer
            buffer_param: Buffer parameter (float or QgsProperty)

        Returns:
            Evaluated buffer distance
        """
        from ..geometry.buffer_processor import evaluate_buffer_distance
        return evaluate_buffer_distance(layer, buffer_param)

    def create_memory_layer_for_buffer(self, layer: QgsVectorLayer) -> QgsVectorLayer:
        """Create empty memory layer for buffered features.

        Args:
            layer: Source layer for CRS and geometry type

        Returns:
            QgsVectorLayer: Empty memory layer configured for buffered geometries
        """
        from ..geometry.buffer_processor import create_memory_layer_for_buffer
        return create_memory_layer_for_buffer(layer)

    def buffer_all_features(
        self,
        layer: QgsVectorLayer,
        buffer_dist: float,
        segments: int = 5,
    ) -> List:
        """Buffer all features from layer.

        Args:
            layer: Source layer
            buffer_dist: Buffer distance
            segments: Number of segments for buffer

        Returns:
            List of buffered geometries
        """
        from ..geometry.buffer_processor import buffer_all_features
        return buffer_all_features(layer, buffer_dist, segments)

    def dissolve_and_add_to_layer(
        self,
        geometries: List,
        buffered_layer: QgsVectorLayer,
        verify_spatial_index_fn: Callable,
    ) -> Any:
        """Dissolve geometries and add to layer.

        Args:
            geometries: List of geometries to dissolve
            buffered_layer: Target layer
            verify_spatial_index_fn: Function to verify/create spatial index

        Returns:
            Result of the operation
        """
        from ..geometry.buffer_processor import dissolve_and_add_to_layer
        return dissolve_and_add_to_layer(geometries, buffered_layer, verify_spatial_index_fn)

    def create_buffered_memory_layer(
        self,
        layer: QgsVectorLayer,
        buffer_distance: float,
        param_buffer_segments: int,
        verify_spatial_index_fn: Callable,
        store_warning_fn: Callable,
    ) -> QgsVectorLayer:
        """Create a buffered memory layer.

        Args:
            layer: Source layer
            buffer_distance: Buffer distance
            param_buffer_segments: Number of buffer segments
            verify_spatial_index_fn: Function to verify/create spatial index
            store_warning_fn: Function to store warning messages

        Returns:
            QgsVectorLayer: Buffered memory layer
        """
        from ..geometry import create_buffered_memory_layer
        return create_buffered_memory_layer(
            layer, buffer_distance, param_buffer_segments,
            verify_spatial_index_fn, store_warning_fn
        )

    def aggressive_geometry_repair(self, geom: QgsGeometry) -> QgsGeometry:
        """Perform aggressive geometry repair.

        Args:
            geom: QgsGeometry to repair

        Returns:
            QgsGeometry: Repaired geometry
        """
        from ..geometry import aggressive_geometry_repair
        return aggressive_geometry_repair(geom)

    def repair_invalid_geometries(
        self,
        layer: QgsVectorLayer,
        verify_spatial_index_fn: Callable,
    ) -> Any:
        """Validate and repair invalid geometries.

        Args:
            layer: QgsVectorLayer with potentially invalid geometries
            verify_spatial_index_fn: Function to verify/create spatial index

        Returns:
            Layer with repaired geometries
        """
        from ..geometry import repair_invalid_geometries
        return repair_invalid_geometries(
            layer=layer,
            verify_spatial_index_fn=verify_spatial_index_fn,
        )

    def get_buffer_distance_parameter(
        self,
        param_buffer_expression: Optional[str],
        param_buffer_value: Optional[float],
    ) -> Any:
        """Get buffer distance parameter from task configuration.

        Args:
            param_buffer_expression: Buffer expression string (optional)
            param_buffer_value: Buffer distance value (optional)

        Returns:
            QgsProperty or float or None
        """
        from qgis.core import QgsProperty
        if param_buffer_expression:
            return QgsProperty.fromExpression(param_buffer_expression)
        elif param_buffer_value is not None:
            return float(param_buffer_value)
        return None

    def store_warning_message(self, message: str, warning_messages: List[str]) -> None:
        """Store a warning message for display in UI thread (thread-safe).

        Args:
            message: Warning message text
            warning_messages: List to append the message to
        """
        if message and message not in warning_messages:
            warning_messages.append(message)
