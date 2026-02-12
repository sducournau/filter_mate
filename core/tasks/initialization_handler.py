"""
Task Initialization Handler

Handles all initialization logic for FilterEngineTask parameters:
- Source layer discovery and validation
- CRS configuration for metric calculations
- Filtering parameter extraction
- Source subset and buffer configuration
- Geometric predicate initialization

Extracted from FilterEngineTask as part of the C1 God Object decomposition (Phase 3).

Location: core/tasks/initialization_handler.py (Hexagonal Architecture - Application Layer)

Thread Safety:
    These methods run during task setup in run(), before heavy processing begins.
    They access QGIS layer objects for metadata only (not for rendering).
"""

import logging
import os
from qgis.core import QgsGeometry

from ...infrastructure.logging import setup_logger
from ...config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.Init',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# CRS utilities (migrated to core/geometry)
from ..geometry.crs_utils import (
    is_geographic_crs,
    is_metric_crs,
    get_optimal_metric_crs,
    get_layer_crs_info
)


class InitializationHandler:
    """Handles task initialization and parameter extraction.

    This class encapsulates all initialization operations previously embedded
    in FilterEngineTask. It receives dependencies explicitly via method
    parameters rather than accessing task state directly.

    All methods return result objects or tuples rather than modifying task
    state directly, so the caller (FilterEngineTask) can apply results
    to its own attributes.

    Example:
        >>> handler = InitializationHandler()
        >>> result = handler.initialize_source_layer(task_parameters, project)
        >>> if result.success:
        ...     task.source_layer = result.source_layer
    """

    def __init__(self):
        """Initialize InitializationHandler."""
        pass

    def initialize_source_layer(self, task_parameters, project):
        """Initialize source layer and basic layer count.

        Args:
            task_parameters: Dict with task configuration.
            project: QgsProject instance.

        Returns:
            dict: Result with keys:
                - success (bool): True if source layer found
                - source_layer (QgsVectorLayer or None): The resolved layer
                - source_crs: Layer CRS
                - source_layer_crs_authid (str): CRS authid
                - feature_count_limit (int or None): Optional feature count limit
                - exception (Exception or None): Error if failed
        """
        result = {
            'success': False,
            'source_layer': None,
            'source_crs': None,
            'source_layer_crs_authid': None,
            'feature_count_limit': None,
            'exception': None,
        }

        # Validate required keys in task_parameters["infos"]
        if "infos" not in task_parameters:
            result['exception'] = KeyError("task_parameters missing 'infos' dictionary")
            logger.error("task_parameters missing 'infos' dictionary")
            return result

        infos = task_parameters["infos"]

        # First, we need layer_id to find the layer (cannot be auto-filled)
        if "layer_id" not in infos or infos["layer_id"] is None:
            error_msg = "task_parameters['infos'] missing required key: ['layer_id']"
            result['exception'] = KeyError(error_msg)
            logger.error(error_msg)
            return result

        # Try to find the layer by ID first (more reliable than name)
        layer_id = infos["layer_id"]
        layer_obj = project.mapLayer(layer_id)

        # Fallback: try by name if available
        if layer_obj is None and infos.get("layer_name"):
            layers = [
                layer for layer in project.mapLayersByName(infos["layer_name"])
                if layer.id() == layer_id
            ]
            if layers:
                layer_obj = layers[0]

        if layer_obj is None:
            error_msg = f"Layer with id '{layer_id}' not found in project"
            result['exception'] = KeyError(error_msg)
            logger.error(error_msg)
            return result

        # Auto-fill missing required keys from the QGIS layer object
        if "layer_name" not in infos or infos["layer_name"] is None:
            infos["layer_name"] = layer_obj.name()
            logger.info(f"Auto-filled layer_name='{infos['layer_name']}' for source layer")

        if "layer_crs_authid" not in infos or infos["layer_crs_authid"] is None:
            infos["layer_crs_authid"] = layer_obj.sourceCrs().authid()
            logger.info(f"Auto-filled layer_crs_authid='{infos['layer_crs_authid']}' for source layer")

        result['success'] = True
        result['source_layer'] = layer_obj
        result['source_crs'] = layer_obj.sourceCrs()
        result['source_layer_crs_authid'] = infos["layer_crs_authid"]

        # Extract feature count limit if provided
        task_options = task_parameters.get("task", {}).get("options", {})
        if "LAYERS" in task_options and "FEATURE_COUNT_LIMIT" in task_options["LAYERS"]:
            limit = task_options["LAYERS"]["FEATURE_COUNT_LIMIT"]
            if isinstance(limit, int) and limit > 0:
                result['feature_count_limit'] = limit

        return result

    def configure_metric_crs(self, source_crs, source_layer, project, source_layer_crs_authid):
        """Configure CRS for metric calculations, reprojecting if necessary.

        IMPROVED v2.5.7: Uses crs_utils module for better CRS detection and
        optimal metric CRS selection (including UTM zones).

        Args:
            source_crs: QgsCoordinateReferenceSystem of the source layer.
            source_layer: QgsVectorLayer (needed for extent).
            project: QgsProject instance.
            source_layer_crs_authid: Current CRS authid string.

        Returns:
            dict: Result with keys:
                - has_to_reproject (bool): Whether reprojection is needed
                - crs_authid (str): Updated CRS authid (possibly changed to metric)
        """
        result = {
            'has_to_reproject': False,
            'crs_authid': source_layer_crs_authid,
        }

        # CRS handling via crs_utils
        is_non_metric = is_geographic_crs(source_crs) or not is_metric_crs(source_crs)

        if is_non_metric:
            result['has_to_reproject'] = True

            # Get optimal metric CRS using layer extent for better accuracy
            layer_extent = source_layer.extent() if source_layer else None
            extent_geom = QgsGeometry.fromRect(layer_extent) if layer_extent else None
            metric_crs = get_optimal_metric_crs(
                geometry=extent_geom,
                source_crs=source_crs,
            )
            result['crs_authid'] = metric_crs.authid()

            # Log CRS conversion info
            crs_info = get_layer_crs_info(source_layer)
            logger.info(
                f"Source layer CRS: {crs_info.get('authid', 'unknown')} "
                f"(units: {crs_info.get('units', 'unknown')}, "
                f"geographic: {crs_info.get('is_geographic', False)})"
            )
            logger.info(
                f"Source layer will be reprojected to {result['crs_authid']} "
                "for metric calculations"
            )
        else:
            logger.info(f"Source layer CRS is already metric: {source_layer_crs_authid}")

        return result

    def initialize_source_filtering_parameters(self, task_parameters, source_layer,
                                                 postgresql_available, sanitize_subset_fn):
        """Extract and initialize all parameters needed for source layer filtering.

        EPIC-1 Phase 14.4: Delegates to core.services.filter_parameter_builder.

        Args:
            task_parameters: Dict with task configuration.
            source_layer: QgsVectorLayer being filtered.
            postgresql_available: Whether PostgreSQL is available.
            sanitize_subset_fn: Callback to sanitize subset strings.

        Returns:
            dict: Result with all filter parameters as keys:
                - provider_type, layer_name, layer_id, table_name, schema
                - geometry_field, primary_key_name, forced_backend, postgresql_fallback
                - has_combine_operator, source_layer_combine_operator
                - other_layers_combine_operator, old_subset, field_names
        """
        from ..services.filter_parameter_builder import build_filter_parameters
        from ...infrastructure.utils import detect_layer_provider_type

        # Delegate to FilterParameterBuilder service
        params = build_filter_parameters(
            task_parameters=task_parameters,
            source_layer=source_layer,
            postgresql_available=postgresql_available,
            detect_provider_fn=detect_layer_provider_type,
            sanitize_subset_fn=sanitize_subset_fn
        )

        result = {
            'provider_type': params.provider_type,
            'layer_name': params.layer_name,
            'layer_id': params.layer_id,
            'table_name': params.table_name,
            'schema': params.schema,
            'geometry_field': params.geometry_field,
            'primary_key_name': params.primary_key_name,
            'forced_backend': params.forced_backend,
            'postgresql_fallback': params.postgresql_fallback,
            'has_combine_operator': params.has_combine_operator,
            'source_layer_combine_operator': params.source_layer_combine_operator,
            'other_layers_combine_operator': params.other_layers_combine_operator,
            'old_subset': params.old_subset,
            'field_names': params.field_names,
        }

        logger.debug(
            f"Filtering layer: {result['layer_name']} "
            f"(table: {result['table_name']}, Provider: {result['provider_type']})"
        )

        return result

    def initialize_source_subset_and_buffer(self, task_parameters, expression, old_subset,
                                             is_field_expression):
        """Initialize source subset expression and buffer parameters.

        PHASE 14.5: Migrated to SourceSubsetBufferBuilder service.

        Args:
            task_parameters: Dict with task configuration.
            expression: Current filter expression.
            old_subset: Previous subset string.
            is_field_expression: Whether expression is a field expression.

        Returns:
            dict: Result with keys:
                - source_new_subset, use_centroids_source_layer, use_centroids_distant_layers
                - approved_optimizations, auto_apply_optimizations
                - has_buffer, buffer_value, buffer_expression
                - buffer_type, buffer_segments
        """
        from ..services.source_subset_buffer_builder import build_source_subset_buffer_config

        config = build_source_subset_buffer_config(
            task_parameters=task_parameters,
            expression=expression,
            old_subset=old_subset,
            is_field_expression=is_field_expression
        )

        result = {
            'source_new_subset': config.source_new_subset,
            'use_centroids_source_layer': config.use_centroids_source_layer,
            'use_centroids_distant_layers': config.use_centroids_distant_layers,
            'approved_optimizations': config.approved_optimizations,
            'auto_apply_optimizations': config.auto_apply_optimizations,
            'has_buffer': config.has_buffer,
            'buffer_value': config.buffer_value if config.has_buffer else 0,
            'buffer_expression': config.buffer_expression if config.has_buffer else None,
            'buffer_type': config.buffer_type,
            'buffer_segments': config.buffer_segments,
        }

        return result

    def initialize_current_predicates(self, task_parameters, predicates_map,
                                       expression_builder=None, filter_orchestrator=None):
        """Initialize current_predicates from task parameters EARLY in the filtering process.

        FIX 2026-01-16: This method MUST be called at the start of execute_filtering(),
        BEFORE execute_source_layer_filtering(). Previously, predicates were only
        initialized in STEP 2/2 (distant layers), but ExpressionBuilder and
        FilterOrchestrator are lazy-initialized during STEP 1/2 and need predicates.

        Args:
            task_parameters: Dict with task configuration.
            predicates_map: Dict mapping user-friendly names to SQL function names.
            expression_builder: Optional ExpressionBuilder to propagate predicates to.
            filter_orchestrator: Optional FilterOrchestrator to propagate predicates to.

        Returns:
            dict: Result with keys:
                - current_predicates (dict): SQL name -> SQL name mapping
                - numeric_predicates (dict): QGIS code -> SQL name mapping
        """
        # Get geometric predicates from filtering parameters
        filtering_params = task_parameters.get("filtering", {})
        geom_predicates = filtering_params.get("geometric_predicates", [])

        from qgis.core import QgsMessageLog, Qgis as QgisLevel

        logger.info("=" * 70)
        logger.info("FILTERING PARAMETERS RECEIVED:")
        logger.info(f"   has_geometric_predicates: {filtering_params.get('has_geometric_predicates', 'NOT SET')}")
        logger.info(f"   geometric_predicates: {geom_predicates}")
        logger.info(f"   has_layers_to_filter: {filtering_params.get('has_layers_to_filter', 'NOT SET')}")
        logger.info(f"   layers_to_filter count: {len(filtering_params.get('layers_to_filter', []))}")
        logger.info("=" * 70)

        result = {
            'current_predicates': {},
            'numeric_predicates': {},
        }

        if not geom_predicates:
            logger.warning("No geometric predicates in task_parameters - distant layers will NOT be filtered!")
            QgsMessageLog.logMessage(
                "No geometric predicates configured - check 'Intersect' checkbox in Filtering panel",
                "FilterMate", QgisLevel.Warning
            )
            return result

        logger.info("EARLY PREDICATE INITIALIZATION")
        logger.info(f"   Input geometric_predicates: {geom_predicates}")
        QgsMessageLog.logMessage(
            f"Predicates: {geom_predicates}",
            "FilterMate", QgisLevel.Info
        )

        # Mapping SQL function -> QGIS predicate code (for OGR/processing)
        sql_to_qgis_code = {
            'ST_Intersects': 0,
            'ST_Contains': 1,
            'ST_Disjoint': 2,
            'ST_Equals': 3,
            'ST_Touches': 4,
            'ST_Overlaps': 5,
            'ST_Within': 6,
            'ST_Crosses': 7,
            'ST_Covers': 1,     # maps to Contains
            'ST_CoveredBy': 6,  # maps to Within
        }

        current_predicates = {}
        numeric_predicates = {}

        for key in geom_predicates:
            if key in predicates_map:
                func_name = predicates_map[key]
                # Store SQL name (for PostgreSQL/Spatialite)
                current_predicates[func_name] = func_name

                # Store numeric code separately for OGR/processing
                qgis_code = sql_to_qgis_code.get(func_name)
                if qgis_code is not None:
                    numeric_predicates[qgis_code] = func_name
                    logger.debug(f"   Mapped: {key} -> {func_name} -> QGIS code {qgis_code}")
                else:
                    logger.warning(f"   No QGIS code for: {key} -> {func_name}")
            else:
                logger.warning(f"   Unknown predicate key: {key}")

        result['current_predicates'] = current_predicates
        result['numeric_predicates'] = numeric_predicates

        # Log final state
        logger.info(f"   current_predicates (SQL): {current_predicates}")
        logger.info(f"   numeric_predicates (OGR): {numeric_predicates}")
        logger.info("   v2.10.0: Predicates now stored separately to prevent duplicate EXISTS")
        logger.info("=" * 70)

        # FIX 2026-01-16: Propagate predicates to EXISTING instances
        if expression_builder is not None:
            expression_builder.current_predicates = current_predicates
            logger.debug("Propagated predicates to existing ExpressionBuilder")

        if filter_orchestrator is not None:
            filter_orchestrator.current_predicates = current_predicates
            logger.debug("Propagated predicates to existing FilterOrchestrator")

        return result
