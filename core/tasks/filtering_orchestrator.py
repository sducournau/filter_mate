"""
Filtering Orchestrator Handler

Extracted from FilterEngineTask (Phase 3 C1 - US-C1.3.2, February 2026).

Contains the high-level orchestration logic for filtering, unfiltering,
and resetting operations. This is the coordination layer that calls into
other handlers (InitializationHandler, SourceGeometryPreparer, etc.)
and manages progress tracking.

Methods extracted:
    - execute_filtering(): Main 2-step filtering workflow (source + distant layers)
    - execute_unfiltering(): Clear all filters from source and distant layers
    - execute_reseting(): Reset all layers to saved/original subset state
    - manage_distant_layers_geometric_filtering(): Orchestrate geometric filtering
    - _filter_all_layers_with_progress(): Dispatch to parallel or sequential mode
    - _filter_all_layers_parallel(): Parallel layer filtering with ThreadPoolExecutor
    - _filter_all_layers_sequential(): Sequential layer filtering (original behavior)
    - _log_filtering_summary(): Log summary of filtering results

Architecture:
    - Stateless handler: receives all data via method parameters
    - Thread safety: no QgsVectorLayer stored as attributes
    - Follows same pattern as CleanupHandler, ExportHandler, etc.

Location: core/tasks/filtering_orchestrator.py (Application Layer)
"""

import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple

from qgis.core import QgsVectorLayer

from ...infrastructure.logging import setup_logger
from ...infrastructure.constants import PROVIDER_POSTGRES
from ...infrastructure.utils import is_layer_valid
from ...infrastructure.parallel import ParallelFilterExecutor, ParallelConfig
from ...config.config import ENV_VARS

# Setup logger with rotation
logger = setup_logger(
    'FilterMate.Tasks.FilteringOrchestrator',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)


class FilteringOrchestrator:
    """Orchestrates filtering, unfiltering, and resetting workflows.

    Extracted from FilterEngineTask to reduce its line count and isolate
    the high-level workflow coordination logic.

    This handler is stateless: all data is passed via method parameters.
    No QgsVectorLayer or QgsTask state is stored on the instance.

    Usage:
        orchestrator = FilteringOrchestrator()
        result = orchestrator.execute_filtering(
            task_parameters=params,
            source_layer=layer,
            ...
        )
    """

    def execute_filtering(
        self,
        task_parameters: Dict[str, Any],
        source_layer: QgsVectorLayer,
        layers: Dict[str, List],
        layers_count: int,
        current_predicates: dict,
        initialize_current_predicates_callback: Callable,
        execute_source_layer_filtering_callback: Callable,
        manage_distant_layers_callback: Callable,
        is_canceled_callback: Callable,
        set_progress_callback: Callable,
    ) -> dict:
        """Execute the complete filtering workflow.

        Orchestrates filtering in two steps:
        1. Filter the source layer using attribute/expression criteria
        2. Filter distant layers using geometric predicates (intersects, within, etc.)

        The source layer filter must succeed before distant layers are processed.
        If no geometric predicates are configured, only the source layer is filtered.

        Args:
            task_parameters: Full task parameters dict.
            source_layer: The source QgsVectorLayer being filtered.
            layers: Dict of layers organized by provider type.
            layers_count: Total number of layers to filter.
            current_predicates: Dict of active geometric predicates.
            initialize_current_predicates_callback: Callable to initialize predicates.
            execute_source_layer_filtering_callback: Callable for source layer filtering.
            manage_distant_layers_callback: Callable for distant layers filtering.
            is_canceled_callback: Callable returning True if task was canceled.
            set_progress_callback: Callable(int) to report progress percentage.

        Returns:
            dict with keys:
                - success (bool): True if filtering completed successfully.
                - message (str or None): Error message if failed.
                - failed_layer_names (list): Names of layers that failed filtering.
        """
        result = {
            'success': False,
            'message': None,
            'failed_layer_names': [],
        }

        # FIX 2026-01-16: Initialize current_predicates EARLY
        # current_predicates must be populated BEFORE execute_source_layer_filtering()
        # because ExpressionBuilder and FilterOrchestrator need them during lazy init.
        # Previously, predicates were only set in STEP 2/2 (distant layers), causing
        # EMPTY predicates warnings during source layer filtering.
        initialize_current_predicates_callback()

        # STEP 1/2: Filtering SOURCE LAYER

        logger.info("=" * 60)
        logger.info("STEP 1/2: Filtering SOURCE LAYER")
        logger.info("=" * 60)

        # Determine the active selection mode
        features_list = task_parameters["task"]["features"]
        qgis_expression = task_parameters["task"]["expression"]
        skip_source_filter = task_parameters["task"].get("skip_source_filter", False)

        # DIAGNOSTIC 2026-01-28: Log features details
        logger.info(f"  features_list count: {len(features_list) if features_list else 0}")
        logger.info(f"  features_list type: {type(features_list)}")
        if features_list and len(features_list) > 0:
            logger.info(f"  features_list[0] type: {type(features_list[0])}")
            logger.info(f"  features_list[0]: {features_list[0]}")
        logger.info(f"  qgis_expression: '{qgis_expression}'")
        logger.info(f"  skip_source_filter: {skip_source_filter}")

        if len(features_list) > 0 and features_list[0] != "":
            if len(features_list) == 1:
                logger.info("Selection Mode: SINGLE SELECTION")
                logger.info("  -> 1 feature selected")
            else:
                logger.info("Selection Mode: MULTIPLE SELECTION")
                logger.info(f"  -> {len(features_list)} features selected")
        elif qgis_expression and qgis_expression.strip():
            logger.info("Selection Mode: CUSTOM EXPRESSION")
            logger.info(f"  -> Expression: '{qgis_expression}'")
        elif skip_source_filter:
            # Custom selection mode with non-filter expression (e.g., field name only)
            # -> Use all features from source layer
            logger.info("Selection Mode: ALL FEATURES (custom selection with field-only expression)")
            logger.info("  -> No source filter will be applied")
            logger.info("  -> All features from source layer will be used for geometric predicates")
        else:
            logger.error("No valid selection mode detected!")
            logger.error("  -> features_list is empty AND expression is empty")
            logger.error("  -> Please select a feature, check multiple features, or enter a filter expression")
            # Provide user-friendly message with guidance
            result['message'] = (
                "No valid selection: please select a feature, check features, "
                "or enter a filter expression in the 'Exploring' tab before filtering."
            )
            return result

        # Execute source layer filtering
        filter_result = execute_source_layer_filtering_callback()

        if is_canceled_callback():
            logger.warning("Task canceled by user")
            return result

        # VALIDATION: Check that source filter succeeded
        if not filter_result:
            logger.error("=" * 60)
            logger.error("FAILED: Source layer filtering FAILED")
            logger.error("=" * 60)
            logger.error("ABORTING: Distant layers will NOT be filtered")
            logger.error("   Reason: Source filter must succeed before filtering distant layers")
            # Set error message for user
            source_name = source_layer.name() if source_layer else 'Unknown'
            result['message'] = f"Failed to filter source layer '{source_name}'. Check Python console for details."
            return result

        # Check feature count after filtering
        source_feature_count = source_layer.featureCount()
        logger.info("=" * 60)
        logger.info("SUCCESS: Source layer filtered")
        logger.info(f"  -> {source_feature_count} feature(s) remaining")
        logger.info("=" * 60)

        if source_feature_count == 0:
            logger.warning("WARNING: Source layer has ZERO features after filter!")
            logger.warning("  -> Distant layers may return no results")
            logger.warning("  -> Consider adjusting filter criteria")

        set_progress_callback((1 / layers_count) * 100)

        # ===================================================================
        # STEP 2: FILTER DISTANT LAYERS (if geometric predicates configured)
        # ===================================================================

        # FIX 2026-01-17: Enhanced console diagnostic for distant layers filtering

        has_geom_predicates = task_parameters["filtering"]["has_geometric_predicates"]
        has_layers_to_filter = task_parameters["filtering"]["has_layers_to_filter"]
        has_layers_in_params = len(task_parameters['task'].get('layers', [])) > 0
        for prov_type, layer_list in (layers or {}).items():
            pass  # print statements removed

        # Log to QGIS message panel for visibility
        from qgis.core import QgsMessageLog, Qgis as QgisLevel

        logger.info("\nChecking if distant layers should be filtered...")
        logger.info(f"  has_geometric_predicates: {has_geom_predicates}")
        logger.info(f"  has_layers_to_filter: {has_layers_to_filter}")
        logger.info(f"  has_layers_in_params: {has_layers_in_params}")
        logger.info(f"  layers_count: {layers_count}")

        # Log layer names to QGIS message panel for visibility
        layer_names = [l.get('layer_name', 'unknown') for l in task_parameters['task'].get('layers', [])]
        QgsMessageLog.logMessage(
            f"Distant layers to filter ({len(layer_names)}): {', '.join(layer_names[:5])}{'...' if len(layer_names) > 5 else ''}",
            "FilterMate", QgisLevel.Info
        )

        logger.info(f"  task['layers'] content: {layer_names}")
        logger.info(f"  layers content: {list(layers.keys())} with {sum(len(v) for v in layers.values())} total layers")

        # Log conditions to QGIS message panel for debugging
        # This helps diagnose why distant layers may not be filtered
        if not has_geom_predicates or (not has_layers_to_filter and not has_layers_in_params) or layers_count == 0:
            missing_conditions = []
            if not has_geom_predicates:
                missing_conditions.append("has_geometric_predicates=False")
            if not has_layers_to_filter and not has_layers_in_params:
                missing_conditions.append("no layers configured")
            if layers_count == 0:
                missing_conditions.append("layers_count=0")
            QgsMessageLog.logMessage(
                f"Distant layers NOT filtered: {', '.join(missing_conditions)}",
                "FilterMate", QgisLevel.Warning
            )
            logger.warning(f"Distant layers NOT filtered: {', '.join(missing_conditions)}")

        # Process if geometric predicates enabled AND (has_layers_to_filter OR layers in params) AND layers were organized
        distant_result = filter_result  # Default to source result
        if has_geom_predicates and (has_layers_to_filter or has_layers_in_params) and layers_count > 0:
            geom_predicates_list = task_parameters["filtering"]["geometric_predicates"]
            logger.info(f"  geometric_predicates list: {geom_predicates_list}")
            logger.info(f"  geometric_predicates count: {len(geom_predicates_list)}")

            if len(geom_predicates_list) > 0:

                logger.info("")
                logger.info("=" * 60)
                logger.info("STEP 2/2: Filtering DISTANT LAYERS")
                logger.info("=" * 60)
                logger.info(f"  -> {len(task_parameters['task']['layers'])} layer(s) to filter")

                # FIX 2026-01-16: current_predicates is already initialized at start of execute_filtering()
                # Just log for confirmation
                logger.info(f"  -> Using pre-initialized predicates: {current_predicates}")

                logger.info("\nCalling manage_distant_layers_geometric_filtering()...")

                distant_result = manage_distant_layers_callback()

                if is_canceled_callback():
                    logger.warning("Task canceled during distant layers filtering")
                    result['message'] = "Filter task was canceled by user"
                    return result

                if distant_result is False:
                    logger.error("=" * 60)
                    logger.error("PARTIAL SUCCESS: Source OK, but distant layers FAILED")
                    logger.error("=" * 60)
                    logger.warning("  -> Source layer remains filtered")
                    logger.warning("  -> Check logs for distant layer errors")
                    logger.warning("  -> Common causes:")
                    logger.warning("     1. Forced Spatialite backend on non-Spatialite layers (e.g., Shapefiles)")
                    logger.warning("     2. GDAL not compiled with Spatialite extension")
                    logger.warning("     3. CRS mismatch between source and distant layers")

                    # Build informative error message with failed layer names
                    failed_names = result.get('failed_layer_names', [])
                    if failed_names:
                        if len(failed_names) <= 3:
                            layers_str = ', '.join(failed_names)
                        else:
                            layers_str = f"{', '.join(failed_names[:3])} (+{len(failed_names) - 3} others)"
                        result['message'] = f"Failed layers: {layers_str}. Try OGR backend or check Python console."
                    else:
                        result['message'] = "Source layer filtered, but some distant layers failed. Try using OGR backend for failing layers or check Python console."
                    return result

                logger.info("=" * 60)
                logger.info("COMPLETE SUCCESS: All layers filtered")
                logger.info("=" * 60)
            else:
                logger.info("  -> No geometric predicates configured")
                logger.info("  -> Only source layer filtered")
        else:
            # Log detailed reason why geometric filtering is skipped
            logger.warning("=" * 60)
            logger.warning("DISTANT LAYERS FILTERING SKIPPED - DIAGNOSTIC")
            logger.warning("=" * 60)
            if not has_geom_predicates:
                logger.warning("  has_geometric_predicates = FALSE")
                logger.warning("     -> Enable 'Geometric predicates' button in UI")
            else:
                logger.info("  has_geometric_predicates = True")

            if not has_layers_to_filter and not has_layers_in_params:
                logger.warning("  No layers to filter:")
                logger.warning(f"     - has_layers_to_filter = {has_layers_to_filter}")
                logger.warning(f"     - has_layers_in_params = {has_layers_in_params}")
                logger.warning("     -> Select layers to filter in UI")
            else:
                logger.info(f"  has_layers_to_filter = {has_layers_to_filter}")
                logger.info(f"  has_layers_in_params = {has_layers_in_params}")

            if layers_count == 0:
                logger.warning("  layers_count = 0 (no layers organized)")
                logger.warning("     -> Check if selected layers exist in project")
            else:
                logger.info(f"  layers_count = {layers_count}")

            # Log filtering parameters for debugging
            filtering_params = task_parameters.get("filtering", {})
            logger.warning("  Filtering parameters:")
            logger.warning(f"     - has_geometric_predicates: {filtering_params.get('has_geometric_predicates', 'NOT SET')}")
            logger.warning(f"     - geometric_predicates: {filtering_params.get('geometric_predicates', 'NOT SET')}")
            logger.warning(f"     - has_layers_to_filter: {filtering_params.get('has_layers_to_filter', 'NOT SET')}")
            logger.warning(f"     - layers_to_filter: {filtering_params.get('layers_to_filter', 'NOT SET')}")

            logger.warning("=" * 60)
            logger.warning("  -> Only source layer filtered")

        result['success'] = True if distant_result else False
        return result

    def execute_unfiltering(
        self,
        source_layer: QgsVectorLayer,
        layers: Dict[str, List],
        layers_count: int,
        queue_subset_string_callback: Callable,
        is_canceled_callback: Callable,
        set_progress_callback: Callable,
    ) -> bool:
        """Remove all filters from source and selected remote layers.

        Clears filters completely by setting subsetString to empty for:
        - The source/current layer
        - All selected remote layers (layers_to_filter)

        Args:
            source_layer: The source QgsVectorLayer.
            layers: Dict of layers organized by provider type.
            layers_count: Total number of layers.
            queue_subset_string_callback: Callable(layer, expression) to queue subset change.
            is_canceled_callback: Callable returning True if task was canceled.
            set_progress_callback: Callable(int) to report progress percentage.

        Returns:
            True if all filter clears were queued successfully.

        Note:
            - This is NOT the same as undo - it removes filters entirely
            - Use the undo button to restore previous filter state
            - All setSubsetString calls are queued for main thread execution
            - Progress is reported via set_progress_callback
        """
        logger.info("=" * 60)
        logger.info("FilterMate: UNFILTERING - Clearing all filters")
        logger.info("=" * 60)

        # Queue filter clear on source layer (will be applied in finished())
        queue_subset_string_callback(source_layer, '')
        logger.info(f"  -> Queued clear on source: {source_layer.name()}")

        # Queue filter clear on all selected associated layers
        # FIX 2026-01-15: Protect against division by zero when no layers selected
        i = 1
        if layers_count > 0:
            set_progress_callback((i / layers_count) * 100)

        for layer_provider_type in layers:
            logger.debug(f"  -> Processing {len(layers[layer_provider_type])} {layer_provider_type} layer(s)")
            for layer, layer_props in layers[layer_provider_type]:
                queue_subset_string_callback(layer, '')
                logger.info(f"    -> Queued clear on: {layer.name()}")
                i += 1
                if layers_count > 0:
                    set_progress_callback((i / layers_count) * 100)
                if is_canceled_callback():
                    logger.warning("FilterMate: Unfilter canceled by user")
                    return False

        logger.info("=" * 60)
        logger.info(f"FilterMate: Unfilter queued for {i} layer(s)")
        logger.info("=" * 60)

        return True

    def execute_reseting(
        self,
        source_layer: QgsVectorLayer,
        layers: Dict[str, List],
        layers_count: int,
        manage_layer_subset_strings_callback: Callable,
        is_canceled_callback: Callable,
        set_progress_callback: Callable,
    ) -> bool:
        """Reset all layers to their original/saved subset state.

        Restores the initial filter state for all configured layers by:
        - Looking up saved subset strings in the filter history database
        - Applying the original subset to each layer via manage_layer_subset_strings()

        Args:
            source_layer: The source QgsVectorLayer.
            layers: Dict of layers organized by provider type.
            layers_count: Total number of layers.
            manage_layer_subset_strings_callback: Callable(layer) to reset layer subset.
            is_canceled_callback: Callable returning True if task was canceled.
            set_progress_callback: Callable(int) to report progress percentage.

        Returns:
            True if reset completed successfully, False if canceled.

        Note:
            - Progress is reported via set_progress_callback
            - Can be canceled by user (is_canceled_callback check)
        """
        logger.info("=" * 60)
        logger.info("FilterMate: RESETTING all layers to saved state")
        logger.info("=" * 60)

        i = 1

        logger.info(f"  -> Resetting source layer: {source_layer.name()}")
        manage_layer_subset_strings_callback(source_layer)
        # FIX 2026-01-15: Protect against division by zero when no layers selected
        if layers_count > 0:
            set_progress_callback((i / layers_count) * 100)

        for layer_provider_type in layers:
            logger.debug(f"  -> Processing {len(layers[layer_provider_type])} {layer_provider_type} layer(s)")
            for layer, layer_props in layers[layer_provider_type]:
                logger.info(f"    -> Resetting: {layer.name()}")
                manage_layer_subset_strings_callback(layer)
                i += 1
                set_progress_callback((i / layers_count) * 100)
                if is_canceled_callback():
                    logger.warning("FilterMate: Reset canceled by user")
                    return False

        logger.info("=" * 60)
        logger.info(f"FilterMate: Reset completed for {i} layer(s)")
        logger.info("=" * 60)
        return True

    def manage_distant_layers_geometric_filtering(
        self,
        source_layer: QgsVectorLayer,
        layers: Dict[str, List],
        task_parameters: Dict[str, Any],
        param_buffer_expression: Optional[str],
        param_source_provider_type: str,
        provider_list: List[str],
        initialize_source_subset_and_buffer_callback: Callable,
        ensure_buffer_expression_mv_exists_callback: Callable,
        try_create_filter_chain_mv_callback: Callable,
        prepare_geometries_by_provider_callback: Callable,
        filter_all_layers_with_progress_callback: Callable,
        cached_source_feature_count_setter: Callable,
    ) -> bool:
        """Filter distant layers using source layer geometries.

        Orchestrates the geometric filtering workflow:
        1. Initialize buffer parameters and source subset
        2. Create optimized filter chain MV for PostgreSQL (if applicable)
        3. Prepare source geometries for each backend type
        4. Execute filtering on all distant layers with progress tracking

        Args:
            source_layer: The source QgsVectorLayer.
            layers: Dict of layers organized by provider type.
            task_parameters: Full task parameters dict.
            param_buffer_expression: Buffer expression or None.
            param_source_provider_type: Provider type of source layer.
            provider_list: List of provider types for geometry preparation.
            initialize_source_subset_and_buffer_callback: Callable to init buffer params.
            ensure_buffer_expression_mv_exists_callback: Callable to create buffer MV.
            try_create_filter_chain_mv_callback: Callable to create filter chain MV.
            prepare_geometries_by_provider_callback: Callable(provider_list) to prepare geometries.
            filter_all_layers_with_progress_callback: Callable to run the actual filtering.
            cached_source_feature_count_setter: Callable(count) to store cached feature count.

        Returns:
            True if all distant layers were filtered successfully.

        Note:
            - Supports buffer expressions with MV optimization for large datasets
            - Creates filter chain MV when multiple spatial filters are chained
            - Handles provider-specific geometry preparation (PostgreSQL, Spatialite, OGR)
        """
        logger.info(f"manage_distant_layers_geometric_filtering: {source_layer.name()} (features: {source_layer.featureCount()})")
        logger.info(f"  is_field_expression: N/A (handled by caller)")
        logger.info("=" * 60)

        # DIAGNOSTIC COMPLET - ARCHITECTURE FIX 2026-01-16
        logger.info("=" * 80)
        logger.info("DIAGNOSTIC manage_distant_layers_geometric_filtering")
        logger.info("=" * 80)

        # CRITICAL: Initialize source subset and buffer parameters FIRST
        # This sets param_buffer_value which is needed by prepare_*_source_geom()
        initialize_source_subset_and_buffer_callback()

        # Calculate source_feature_count ONCE and store it for consistent threshold decisions
        # This ensures _ensure_buffer_expression_mv_exists() and prepare_postgresql_source_geom()
        # use the same value (featureCount can vary if subsetString changes between calls)
        cached_feature_count = source_layer.featureCount() if source_layer else None
        cached_source_feature_count_setter(cached_feature_count)
        logger.info(f"  Cached source_feature_count: {cached_feature_count}")

        # Re-read param_buffer_expression from task after initialization
        # (it may have been set by initialize_source_subset_and_buffer_callback)
        # The caller should pass the updated value, but we use the one from task_parameters
        # as a safety measure
        current_buffer_expression = task_parameters.get('filtering', {}).get('buffer_expression', param_buffer_expression)
        if current_buffer_expression is None:
            current_buffer_expression = param_buffer_expression

        # Ensure buffer expression MV exists BEFORE prepare_geometries
        # CRITICAL - Only call MV creation if feature count exceeds threshold
        from ...adapters.backends.postgresql.filter_executor import BUFFER_EXPR_MV_THRESHOLD
        if (current_buffer_expression and
            param_source_provider_type == PROVIDER_POSTGRES and
            cached_feature_count is not None and
                cached_feature_count > BUFFER_EXPR_MV_THRESHOLD):
            logger.info(f"  Feature count ({cached_feature_count}) > threshold ({BUFFER_EXPR_MV_THRESHOLD})")
            logger.info("  -> Calling _ensure_buffer_expression_mv_exists()...")
            ensure_buffer_expression_mv_exists_callback()
        elif current_buffer_expression and param_source_provider_type == PROVIDER_POSTGRES:
            logger.info(f"  SKIP MV creation: {cached_feature_count} features <= {BUFFER_EXPR_MV_THRESHOLD} threshold")
            logger.info("  -> Buffer expression will be applied INLINE by prepare_postgresql_source_geom()")

        # Try to create optimized filter chain MV for PostgreSQL
        # When multiple spatial filters are chained (zone_pop AND demand_points etc.),
        # creating a single MV reduces N*M EXISTS queries to 1 EXISTS per distant layer
        if param_source_provider_type == PROVIDER_POSTGRES:
            try_create_filter_chain_mv_callback()

        # Build unique provider list including source layer provider AND forced backends
        # Include forced backends in provider_list
        # Without this, forced backends won't have their source geometry prepared
        full_provider_list = list(provider_list) + [param_source_provider_type]

        # Add any forced backends to ensure their geometry is prepared
        forced_backends = task_parameters.get('forced_backends', {})
        for layer_id, forced_backend in forced_backends.items():
            if forced_backend and forced_backend not in full_provider_list:
                logger.debug(f"  -> Adding forced backend '{forced_backend}' to provider_list")
                full_provider_list.append(forced_backend)

        full_provider_list = list(dict.fromkeys(full_provider_list))
        logger.info(f"  -> Provider list for geometry preparation: {full_provider_list}")

        # Prepare geometries for all provider types
        geom_prep_result = prepare_geometries_by_provider_callback(full_provider_list)

        if not geom_prep_result:
            logger.error("_prepare_geometries_by_provider failed")
            return False

        # Filter all layers with progress tracking
        logger.info("Starting _filter_all_layers_with_progress()...")
        result = filter_all_layers_with_progress_callback()
        logger.info(f"_filter_all_layers_with_progress() returned: {result}")
        return result

    def filter_all_layers_with_progress(
        self,
        layers: Dict[str, List],
        layers_count: int,
        task_parameters: Dict[str, Any],
        execute_geometric_filtering_callback: Callable,
        try_v3_multi_step_filter_callback: Callable,
        is_canceled_callback: Callable,
        set_progress_callback: Callable,
        set_description_callback: Callable,
    ) -> dict:
        """Iterate through all layers and apply filtering with progress tracking.

        Supports parallel execution when enabled in configuration.
        Updates task description to show current layer being processed.
        Progress is visible in QGIS task manager panel.

        Args:
            layers: Dict of layers organized by provider type.
            layers_count: Total number of layers.
            task_parameters: Full task parameters dict.
            execute_geometric_filtering_callback: Callable(provider_type, layer, props) for filtering.
            try_v3_multi_step_filter_callback: Callable(layers_dict) for v3 migration.
            is_canceled_callback: Callable returning True if task was canceled.
            set_progress_callback: Callable(int) to report progress percentage.
            set_description_callback: Callable(str) to update task description.

        Returns:
            dict with keys:
                - success (bool): True if all layers processed successfully.
                - message (str or None): Error message if any failures.
                - failed_layer_names (list): Names of layers that failed.
        """
        result = {
            'success': True,
            'message': None,
            'failed_layer_names': [],
        }

        # Import QgsMessageLog for visible diagnostic logs
        from qgis.core import QgsMessageLog, Qgis as QgisLevel

        # DIAGNOSTIC: Log all layers that will be filtered
        logger.info("=" * 70)
        logger.info("LAYERS TO FILTER GEOMETRICALLY")
        logger.info("=" * 70)
        total_layers = 0
        layer_names_list = []
        for provider_type in layers:
            layer_list = layers[provider_type]
            logger.debug(f"  Provider: {provider_type} -> {len(layer_list)} layer(s)")
            for idx, (layer, layer_props) in enumerate(layer_list, 1):
                logger.info(f"    {idx}. {layer.name()} (id={layer.id()[:8]}...)")
                layer_names_list.append(layer.name())
            total_layers += len(layer_list)
        logger.info(f"  TOTAL: {total_layers} layers to filter")
        logger.info("=" * 70)

        # Log to QGIS message panel for visibility
        QgsMessageLog.logMessage(
            f"Filtering {total_layers} distant layers: {', '.join(layer_names_list[:5])}{'...' if len(layer_names_list) > 5 else ''}",
            "FilterMate", QgisLevel.Info
        )

        # =================================================================
        # MIG-023: STRANGLER FIG PATTERN - Try v3 multi-step first
        # =================================================================
        v3_result = try_v3_multi_step_filter_callback(layers)

        if v3_result is True:
            logger.info("V3 multi-step completed successfully - skipping legacy code")
            return result
        elif v3_result is False:
            logger.error("V3 multi-step failed - falling back to legacy")
            # Continue with legacy code below
        else:
            logger.debug("V3 multi-step not applicable - using legacy code")
        # =================================================================

        # Check if parallel filtering is enabled
        parallel_config = task_parameters.get('config', {}).get('APP', {}).get('OPTIONS', {}).get('PARALLEL_FILTERING', {})
        parallel_enabled = parallel_config.get('enabled', {}).get('value', True)
        min_layers_for_parallel = parallel_config.get('min_layers', {}).get('value', 2)
        max_workers = parallel_config.get('max_workers', {}).get('value', 0)

        # Use parallel execution if enabled and enough layers
        if parallel_enabled and total_layers >= min_layers_for_parallel:
            par_result = self._filter_all_layers_parallel(
                layers=layers,
                layers_count=layers_count,
                max_workers=max_workers,
                execute_geometric_filtering_callback=execute_geometric_filtering_callback,
                is_canceled_callback=is_canceled_callback,
                set_progress_callback=set_progress_callback,
                set_description_callback=set_description_callback,
            )
            return par_result
        else:
            seq_result = self._filter_all_layers_sequential(
                layers=layers,
                layers_count=layers_count,
                execute_geometric_filtering_callback=execute_geometric_filtering_callback,
                is_canceled_callback=is_canceled_callback,
                set_progress_callback=set_progress_callback,
                set_description_callback=set_description_callback,
            )
            return seq_result

    def _filter_all_layers_parallel(
        self,
        layers: Dict[str, List],
        layers_count: int,
        max_workers: int,
        execute_geometric_filtering_callback: Callable,
        is_canceled_callback: Callable,
        set_progress_callback: Callable,
        set_description_callback: Callable,
    ) -> dict:
        """Filter all layers using parallel execution.

        Args:
            layers: Dict of layers organized by provider type.
            layers_count: Total number of layers.
            max_workers: Maximum number of worker threads (0 = auto).
            execute_geometric_filtering_callback: Callable for geometric filtering.
            is_canceled_callback: Callable returning True if task was canceled.
            set_progress_callback: Callable(int) to report progress percentage.
            set_description_callback: Callable(str) to update task description.

        Returns:
            dict with keys: success, message, failed_layer_names.
        """
        result = {
            'success': True,
            'message': None,
            'failed_layer_names': [],
        }

        logger.info("Using PARALLEL filtering mode")

        # Prepare flat list of (layer, layer_props) tuples with provider_type stored in layer_props
        all_layers = []
        for provider_type in layers:
            for layer, layer_props in layers[provider_type]:
                # Store provider_type in layer_props for the filter function
                layer_props_with_provider = layer_props.copy()
                layer_props_with_provider['_effective_provider_type'] = provider_type
                all_layers.append((layer, layer_props_with_provider))

        logger.debug(f"Prepared {len(all_layers)} layers for parallel filtering")

        # Create executor with config
        config = ParallelConfig(
            max_workers=max_workers if max_workers > 0 else None,
            min_layers_for_parallel=1  # Already checked threshold
        )
        executor = ParallelFilterExecutor(config.max_workers)

        # Execute parallel filtering with required task_parameters
        # Include filtering params for OGR detection (thread safety)
        task_parameters = {
            'task': None,  # Not used in parallel mode
            'filter_type': 'geometric',
            'filtering': {
                'filter_type': 'geometric'
            }
        }
        # Pass cancel_check callback to executor
        # This allows parallel workers to check if task was canceled and stop immediately
        results = executor.filter_layers_parallel(
            all_layers,
            execute_geometric_filtering_callback,
            task_parameters,
            cancel_check=is_canceled_callback
        )

        # Process results and update progress
        successful_filters = 0
        failed_filters = 0
        failed_layer_names = []

        logger.debug(f"_filter_all_layers_parallel: all_layers count={len(all_layers)}, results count={len(results)}")
        for idx, res in enumerate(results):
            logger.debug(f"  Result[{idx}]: {res.layer_name} -> success={res.success}, error={res.error_message}")

        for i, (layer_tuple, filter_result) in enumerate(zip(all_layers, results), 1):
            layer, layer_props = layer_tuple
            set_description_callback(f"Filtering layer {i}/{layers_count}: {layer.name()}")

            if filter_result.success:
                successful_filters += 1
                logger.info(f"  {layer.name()} has been filtered -> {layer.featureCount()} features")
            else:
                failed_filters += 1
                failed_layer_names.append(layer.name())
                error_msg = filter_result.error_message if hasattr(filter_result, 'error_message') else getattr(filter_result, 'error', 'Unknown error')
                logger.error(f"  {layer.name()} - errors occurred during filtering: {error_msg}")

            progress_percent = int((i / layers_count) * 100)
            set_progress_callback(progress_percent)

            if is_canceled_callback():
                logger.warning(f"Filtering canceled at layer {i}/{layers_count}")
                result['success'] = False
                return result

        # DIAGNOSTIC: Summary of filtering results
        self._log_filtering_summary(layers_count, successful_filters, failed_filters, failed_layer_names)

        # CRITICAL FIX: Return False if ANY filter failed to alert user
        if failed_filters > 0:
            result['success'] = False
            result['failed_layer_names'] = failed_layer_names
            layer_list = ', '.join(failed_layer_names[:3])
            suffix = f' (+{len(failed_layer_names) - 3} more)' if len(failed_layer_names) > 3 else ''
            result['message'] = f"{failed_filters} layer(s) failed to filter: {layer_list}{suffix}"
            logger.warning(f"{failed_filters} layer(s) failed to filter (parallel mode) - returning False")
            logger.warning(f"   Failed layers: {', '.join(failed_layer_names[:5])}{'...' if len(failed_layer_names) > 5 else ''}")

        return result

    def _filter_all_layers_sequential(
        self,
        layers: Dict[str, List],
        layers_count: int,
        execute_geometric_filtering_callback: Callable,
        is_canceled_callback: Callable,
        set_progress_callback: Callable,
        set_description_callback: Callable,
    ) -> dict:
        """Filter all layers sequentially (original behavior).

        Args:
            layers: Dict of layers organized by provider type.
            layers_count: Total number of layers.
            execute_geometric_filtering_callback: Callable(provider_type, layer, props) for filtering.
            is_canceled_callback: Callable returning True if task was canceled.
            set_progress_callback: Callable(int) to report progress percentage.
            set_description_callback: Callable(str) to update task description.

        Returns:
            dict with keys: success, message, failed_layer_names.
        """
        result = {
            'success': True,
            'message': None,
            'failed_layer_names': [],
        }

        logger.info("Using SEQUENTIAL filtering mode")

        i = 1
        successful_filters = 0
        failed_filters = 0
        failed_layer_names = []

        logger.debug(f"Processing providers: {list(layers.keys())}")
        for provider_type in layers:
            logger.debug(f"Provider '{provider_type}' has {len(layers[provider_type])} layers")

        for layer_provider_type in layers:
            for layer, layer_props in layers[layer_provider_type]:
                # Validate layer before any operations
                # This prevents crashes when layer becomes invalid during sequential filtering
                try:
                    if not is_layer_valid(layer):
                        logger.warning(f"Layer {i}/{layers_count} is invalid - skipping")
                        failed_filters += 1
                        failed_layer_names.append(f"Layer_{i} (invalid)")
                        i += 1
                        continue

                    layer_name = layer.name()
                    layer_feature_count = layer.featureCount()
                except (RuntimeError, AttributeError) as access_error:
                    logger.error(f"Layer {i}/{layers_count} access error (C++ object deleted): {access_error}")
                    failed_filters += 1
                    failed_layer_names.append(f"Layer_{i} (deleted)")
                    i += 1
                    continue

                # Update task description with current progress
                set_description_callback(f"Filtering layer {i}/{layers_count}: {layer_name}")

                logger.info("")
                logger.debug(f"FILTERING {i}/{layers_count}: {layer_name} ({layer_provider_type})")
                logger.info(f"   Features before filter: {layer_feature_count}")

                filter_result = execute_geometric_filtering_callback(layer_provider_type, layer, layer_props)

                # Log result VISIBLY for debugging
                logger.info(f"   -> execute_geometric_filtering RESULT: {filter_result}")

                if filter_result:
                    successful_filters += 1
                    try:
                        final_count = layer.featureCount()
                        logger.info(f"  {layer_name} has been filtered -> {final_count} features")
                    except (RuntimeError, AttributeError):
                        logger.info(f"  {layer_name} has been filtered (count unavailable)")
                else:
                    failed_filters += 1
                    failed_layer_names.append(layer_name)
                    logger.error(f"  {layer_name} - errors occurred during filtering")

                i += 1
                progress_percent = int((i / layers_count) * 100)
                set_progress_callback(progress_percent)

                if is_canceled_callback():
                    logger.warning(f"Filtering canceled at layer {i}/{layers_count}")
                    result['success'] = False
                    return result

        # DIAGNOSTIC: Summary of filtering results
        self._log_filtering_summary(layers_count, successful_filters, failed_filters, failed_layer_names)

        # CRITICAL FIX: Return False if ANY filter failed to alert user
        if failed_filters > 0:
            result['success'] = False
            result['failed_layer_names'] = failed_layer_names
            layer_list = ', '.join(failed_layer_names[:3])
            suffix = f' (+{len(failed_layer_names) - 3} more)' if len(failed_layer_names) > 3 else ''
            result['message'] = f"{failed_filters} layer(s) failed to filter: {layer_list}{suffix}"
            logger.warning(f"{failed_filters} layer(s) failed to filter - returning False")
            logger.warning(f"   Failed layers: {', '.join(failed_layer_names[:5])}{'...' if len(failed_layer_names) > 5 else ''}")

        return result

    def _log_filtering_summary(
        self,
        layers_count: int,
        successful_filters: int,
        failed_filters: int,
        failed_layer_names: Optional[List[str]] = None,
    ) -> None:
        """Log summary of filtering results.

        Delegates to core.optimization.logging_utils for standardized logging.

        Args:
            layers_count: Total number of layers.
            successful_filters: Number of layers filtered successfully.
            failed_filters: Number of layers that failed.
            failed_layer_names: Names of layers that failed (optional).
        """
        from ..optimization.logging_utils import log_filtering_summary
        log_filtering_summary(
            layers_count=layers_count, successful_filters=successful_filters,
            failed_filters=failed_filters, failed_layer_names=failed_layer_names, log_to_qgis=True
        )
