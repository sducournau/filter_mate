"""
Source Geometry Preparer Handler

Handles preparation of source geometries for spatial filtering across
all three backends: PostgreSQL, Spatialite, and OGR.

Each method prepares a geometry representation appropriate for its backend:
- PostgreSQL: SQL geometry expression (e.g., '"schema"."table"."geom"')
- Spatialite: WKT geometry string
- OGR: QgsVectorLayer (memory layer)

Extracted from FilterEngineTask as part of the C1 God Object decomposition (Phase 3).

Location: core/tasks/source_geometry_preparer.py (Hexagonal Architecture - Application Layer)

Thread Safety:
    These methods run in the worker thread during run(). They do NOT call
    setSubsetString or interact with the QGIS UI. PostgreSQL and Spatialite
    methods use database connections; OGR uses processing algorithms.
"""

import logging
import os
from typing import Any, Callable, Dict, List, Optional

from ...infrastructure.logging import setup_logger
from ...config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.SourceGeom',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# Lazy-load backend services
from ..ports.backend_services import get_backend_services


class SourceGeometryPreparer:
    """Handles source geometry preparation for all backends.

    This class encapsulates the three prepare_*_source_geom() methods and the
    _prepare_geometries_by_provider() orchestrator. Each method returns the
    prepared geometry rather than modifying task state directly.

    Example:
        >>> preparer = SourceGeometryPreparer()
        >>> result = preparer.prepare_postgresql_source_geom(
        ...     source_table='parcels', source_schema='public', source_geom='geom', ...
        ... )
        >>> task.postgresql_source_geom = result['geom']
    """

    def __init__(self):
        """Initialize SourceGeometryPreparer with backend services facade."""
        self._backend_services = get_backend_services()

    def prepare_postgresql_source_geom(
        self,
        source_table,
        source_schema,
        source_geom,
        buffer_value=None,
        buffer_expression=None,
        use_centroids=False,
        buffer_segments=5,
        buffer_type="Round",
        primary_key_name=None,
        session_id=None,
        mv_schema='filter_mate_temp',
        source_feature_count=None,
        source_layer=None,
    ):
        """Prepare PostgreSQL source geometry with buffer/centroid.

        Delegates to BackendServices facade.

        Args:
            source_table: Source table name.
            source_schema: Source schema name.
            source_geom: Geometry field name.
            buffer_value: Optional buffer distance.
            buffer_expression: Optional buffer expression.
            use_centroids: Whether to use centroids.
            buffer_segments: Number of buffer segments.
            buffer_type: Buffer end cap type.
            primary_key_name: Primary key field name.
            session_id: Session ID for MV name prefix.
            mv_schema: Materialized view schema.
            source_feature_count: Cached source feature count.
            source_layer: Source QgsVectorLayer (for fallback feature count).

        Returns:
            dict: Result with keys:
                - geom (str): PostgreSQL geometry expression
                - mv_name (str or None): Materialized view name if created
        """
        logger.info("=" * 60)
        logger.info("PREPARING PostgreSQL SOURCE GEOMETRY")
        logger.info("=" * 60)
        logger.info(f"   source_schema: {source_schema}")
        logger.info(f"   source_table: {source_table}")
        logger.info(f"   source_geom: {source_geom}")
        logger.info(f"   buffer_value: {buffer_value}")
        logger.info(f"   buffer_expression: {buffer_expression}")
        logger.info(f"   use_centroids: {use_centroids}")
        logger.info(f"   session_id: {session_id}")
        logger.info(f"   mv_schema: {mv_schema}")

        # Use cached feature count for consistent threshold decisions
        source_fc = source_feature_count
        if source_fc is None:
            # Fallback if not cached
            source_fc = source_layer.featureCount() if source_layer else None
            logger.warning(f"   Using fresh featureCount (not cached): {source_fc}")
        logger.info(f"   source_feature_count: {source_fc} (threshold=10000)")

        result_geom, mv_name = self._backend_services.prepare_postgresql_source_geom(
            source_table=source_table, source_schema=source_schema,
            source_geom=source_geom, buffer_value=buffer_value,
            buffer_expression=buffer_expression,
            use_centroids=use_centroids,
            buffer_segments=buffer_segments,
            buffer_type=buffer_type,
            primary_key_name=primary_key_name,
            session_id=session_id,
            mv_schema=mv_schema,
            source_feature_count=source_fc
        )

        # Log result for debugging
        logger.info(f"   postgresql_source_geom = '{str(result_geom)[:100]}...'")
        logger.info("=" * 60)

        return {
            'geom': result_geom,
            'mv_name': mv_name,
        }

    def prepare_spatialite_source_geom(
        self,
        source_layer,
        task_parameters,
        is_field_expression=None,
        expression=None,
        param_source_new_subset=None,
        param_buffer_value=None,
        has_to_reproject_source_layer=False,
        source_layer_crs_authid=None,
        source_crs=None,
        param_use_centroids_source_layer=False,
        project=None,
        geom_cache=None,
        geometry_to_wkt_fn=None,
        simplify_geometry_adaptive_fn=None,
        get_optimization_thresholds_fn=None,
    ):
        """Prepare source geometry for Spatialite filtering.

        Delegates to BackendServices facade via SpatialiteSourceContext.

        Args:
            source_layer: QgsVectorLayer being filtered.
            task_parameters: Dict with task configuration.
            is_field_expression: Whether expression is a field expression.
            expression: Current filter expression.
            param_source_new_subset: New subset string.
            param_buffer_value: Buffer distance value.
            has_to_reproject_source_layer: Whether reprojection is needed.
            source_layer_crs_authid: CRS authid string.
            source_crs: QgsCoordinateReferenceSystem.
            param_use_centroids_source_layer: Whether to use centroids.
            project: QgsProject instance.
            geom_cache: Geometry cache instance.
            geometry_to_wkt_fn: Callback for WKT conversion.
            simplify_geometry_adaptive_fn: Callback for adaptive simplification.
            get_optimization_thresholds_fn: Callback for optimization thresholds.

        Returns:
            dict: Result with keys:
                - success (bool): Whether preparation succeeded
                - wkt (str or None): WKT geometry string
                - buffer_state: Buffer state info
                - error_message (str or None): Error description if failed
        """
        SpatialiteSourceContext = self._backend_services.get_spatialite_source_context_class()
        if SpatialiteSourceContext is None:
            return {
                'success': False,
                'wkt': None,
                'buffer_state': None,
                'error_message': 'SpatialiteSourceContext not available',
            }

        context = SpatialiteSourceContext(
            source_layer=source_layer,
            task_parameters=task_parameters,
            is_field_expression=is_field_expression,
            expression=expression,
            param_source_new_subset=param_source_new_subset,
            param_buffer_value=param_buffer_value,
            has_to_reproject_source_layer=has_to_reproject_source_layer,
            source_layer_crs_authid=source_layer_crs_authid,
            source_crs=source_crs,
            param_use_centroids_source_layer=param_use_centroids_source_layer,
            PROJECT=project,
            geom_cache=geom_cache,
            geometry_to_wkt=geometry_to_wkt_fn,
            simplify_geometry_adaptive=simplify_geometry_adaptive_fn,
            get_optimization_thresholds=get_optimization_thresholds_fn,
        )

        backend_result = self._backend_services.prepare_spatialite_source_geom(context)
        if backend_result.success:
            logger.debug(f"prepare_spatialite_source_geom: WKT length = {len(backend_result.wkt) if backend_result.wkt else 0}")
            logger.info(f"Spatialite source geom prepared: {len(backend_result.wkt)} chars")
            return {
                'success': True,
                'wkt': backend_result.wkt,
                'buffer_state': backend_result.buffer_state,
                'error_message': None,
            }
        else:
            error_msg = backend_result.error_message or "Unknown error"
            logger.error(f"prepare_spatialite_source_geom failed: {error_msg}")
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"Spatialite geometry preparation FAILED: {error_msg}",
                "FilterMate", Qgis.Critical
            )
            logger.error("  -> This will cause distant layer filtering to fail!")
            logger.error("  -> Check if source layer has valid geometry")
            logger.error("  -> Check if source layer has features selected or filtered")
            return {
                'success': False,
                'wkt': None,
                'buffer_state': None,
                'error_message': error_msg,
            }

    def prepare_ogr_source_geom(
        self,
        source_layer,
        task_parameters,
        is_field_expression=None,
        expression=None,
        param_source_new_subset=None,
        has_to_reproject_source_layer=False,
        source_layer_crs_authid=None,
        param_use_centroids_source_layer=False,
        spatialite_fallback_mode=False,
        copy_filtered_layer_to_memory_fn=None,
        copy_selected_features_to_memory_fn=None,
        create_memory_layer_from_features_fn=None,
        reproject_layer_fn=None,
        convert_layer_to_centroids_fn=None,
        get_buffer_distance_parameter_fn=None,
        ogr_executor=None,
        ogr_executor_available=False,
    ):
        """Prepare OGR source geometry with reprojection/buffering.

        Delegates to ogr_executor module.

        Args:
            source_layer: QgsVectorLayer being filtered.
            task_parameters: Dict with task configuration.
            is_field_expression: Whether expression is a field expression.
            expression: Current filter expression.
            param_source_new_subset: New subset string.
            has_to_reproject_source_layer: Whether reprojection is needed.
            source_layer_crs_authid: CRS authid string.
            param_use_centroids_source_layer: Whether to use centroids.
            spatialite_fallback_mode: Whether in Spatialite fallback mode.
            copy_filtered_layer_to_memory_fn: Callback for filtered layer copy.
            copy_selected_features_to_memory_fn: Callback for selected features copy.
            create_memory_layer_from_features_fn: Callback for memory layer creation.
            reproject_layer_fn: Callback for layer reprojection.
            convert_layer_to_centroids_fn: Callback for centroid conversion.
            get_buffer_distance_parameter_fn: Callback for buffer distance.
            ogr_executor: OGR executor module.
            ogr_executor_available: Whether OGR executor is available.

        Returns:
            The prepared OGR source geometry (typically a QgsVectorLayer), or None if failed.
        """
        if not ogr_executor_available or not hasattr(ogr_executor, 'OGRSourceContext'):
            logger.error("OGR executor not available")
            return None

        context = ogr_executor.OGRSourceContext(
            source_layer=source_layer,
            task_parameters=task_parameters,
            is_field_expression=is_field_expression,
            expression=expression,
            param_source_new_subset=param_source_new_subset,
            has_to_reproject_source_layer=has_to_reproject_source_layer,
            source_layer_crs_authid=source_layer_crs_authid,
            param_use_centroids_source_layer=param_use_centroids_source_layer,
            spatialite_fallback_mode=spatialite_fallback_mode,
            buffer_distance=None,
            copy_filtered_layer_to_memory=copy_filtered_layer_to_memory_fn,
            copy_selected_features_to_memory=copy_selected_features_to_memory_fn,
            create_memory_layer_from_features=create_memory_layer_from_features_fn,
            reproject_layer=reproject_layer_fn,
            convert_layer_to_centroids=convert_layer_to_centroids_fn,
            get_buffer_distance_parameter=get_buffer_distance_parameter_fn,
        )
        result = ogr_executor.prepare_ogr_source_geom(context)
        logger.debug(f"prepare_ogr_source_geom: {result}")

        return result

    def prepare_geometries_by_provider(
        self,
        provider_list,
        task_parameters,
        source_layer,
        param_source_provider_type,
        param_buffer_expression,
        layers_dict,
        prepare_postgresql_callback,
        prepare_spatialite_callback,
        prepare_ogr_callback,
        postgresql_available,
    ):
        """Prepare source geometries for each provider type.

        Delegates to core.services.geometry_preparer.prepare_geometries_by_provider().

        Args:
            provider_list: List of unique provider types to prepare.
            task_parameters: Dict with task configuration.
            source_layer: QgsVectorLayer being filtered.
            param_source_provider_type: Source layer provider type.
            param_buffer_expression: Buffer expression if any.
            layers_dict: Dict of layers organized by provider.
            prepare_postgresql_callback: Callback for PostgreSQL geom preparation.
            prepare_spatialite_callback: Callback for Spatialite geom preparation.
            prepare_ogr_callback: Callback for OGR geom preparation.
            postgresql_available: Whether PostgreSQL is available.

        Returns:
            dict: Result with keys:
                - success (bool): Whether all required geometries prepared
                - postgresql_source_geom: PostgreSQL geometry or None
                - spatialite_source_geom: Spatialite WKT or None
                - ogr_source_geom: OGR layer or None
                - spatialite_fallback_mode (bool): Whether fallback was used
        """
        from ..services.geometry_preparer import prepare_geometries_by_provider

        result = prepare_geometries_by_provider(
            provider_list=provider_list,
            task_parameters=task_parameters,
            source_layer=source_layer,
            param_source_provider_type=param_source_provider_type,
            param_buffer_expression=param_buffer_expression,
            layers_dict=layers_dict,
            prepare_postgresql_geom_callback=prepare_postgresql_callback,
            prepare_spatialite_geom_callback=prepare_spatialite_callback,
            prepare_ogr_geom_callback=prepare_ogr_callback,
            logger=logger,
            postgresql_available=postgresql_available
        )

        return result
