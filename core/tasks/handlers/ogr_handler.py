# -*- coding: utf-8 -*-
"""
OGR Backend Handler for FilterEngineTask.

Phase 4 (v6.0): Extracted from core/tasks/filter_task.py to reduce God class.
Contains all OGR-specific operations:
- Geometry preparation (memory layers)
- Spatial selection and filter building
- Reset/unfilter actions

Location: core/tasks/handlers/ogr_handler.py (Hexagonal Architecture - Application Layer)
"""

import logging
import os
from typing import Any, Optional

from ....infrastructure.logging import setup_logger
from ....config.config import ENV_VARS
from ....adapters.repositories.history_repository import HistoryRepository

# Core imports
from ...ports.backend_services import get_backend_services

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.OGRHandler',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# Backend services facade
_backend_services = get_backend_services()

# OGR executor
ogr_executor = _backend_services.get_ogr_executor()
OGR_EXECUTOR_AVAILABLE = ogr_executor is not None

# OGR filter actions
_ogr_actions = _backend_services.get_ogr_filter_actions()
if _ogr_actions:
    ogr_execute_reset = _ogr_actions.get('reset')
    ogr_execute_unfilter = _ogr_actions.get('unfilter')
else:
    ogr_execute_reset = None
    ogr_execute_unfilter = None


class OGRHandler:
    """Handler for OGR-specific operations in FilterEngineTask.

    Phase 4 (v6.0): Extracted 6 methods from FilterEngineTask.
    Access task state via self.task.* (e.g., self.task.source_layer, self.task.ogr_source_geom).
    """

    def __init__(self, task):
        """Initialize with reference to the parent FilterEngineTask.

        Args:
            task: FilterEngineTask instance
        """
        self.task = task

    # ── Geometry Preparation ────────────────────────────────────────────

    def prepare_source_geom(self):
        """Prepare OGR source geometry with reprojection/buffering. Delegated to ogr_executor."""
        if not OGR_EXECUTOR_AVAILABLE or not hasattr(ogr_executor, 'OGRSourceContext'):
            logger.error("OGR executor not available")
            self.task.ogr_source_geom = None
            return None

        context = ogr_executor.OGRSourceContext(
            source_layer=self.task.source_layer,
            task_parameters=self.task.task_parameters,
            is_field_expression=getattr(self.task, 'is_field_expression', None),
            expression=getattr(self.task, 'expression', None),
            param_source_new_subset=getattr(self.task, 'param_source_new_subset', None),
            has_to_reproject_source_layer=self.task.has_to_reproject_source_layer,
            source_layer_crs_authid=self.task.source_layer_crs_authid,
            param_use_centroids_source_layer=self.task.param_use_centroids_source_layer,
            spatialite_fallback_mode=getattr(self.task, '_spatialite_fallback_mode', False),
            buffer_distance=None,
            copy_filtered_layer_to_memory=self.task._copy_filtered_layer_to_memory,
            copy_selected_features_to_memory=self.task._copy_selected_features_to_memory,
            create_memory_layer_from_features=self.task._create_memory_layer_from_features,
            reproject_layer=self.task._reproject_layer,
            convert_layer_to_centroids=self.task._convert_layer_to_centroids,
            get_buffer_distance_parameter=self.task._get_buffer_distance_parameter,
        )
        self.task.ogr_source_geom = ogr_executor.prepare_ogr_source_geom(context)
        logger.debug(f"prepare_ogr_source_geom: {self.task.ogr_source_geom}")

        return self.task.ogr_source_geom

    # ── Spatial Selection & Filter Building ─────────────────────────────

    def execute_spatial_selection(self, layer, current_layer, param_old_subset):
        """Delegates to ogr_executor.execute_ogr_spatial_selection()."""
        if not OGR_EXECUTOR_AVAILABLE:
            raise ImportError("ogr_executor module not available - cannot execute OGR spatial selection")

        if not hasattr(ogr_executor, 'OGRSpatialSelectionContext'):
            raise ImportError("ogr_executor.OGRSpatialSelectionContext not available")

        context = ogr_executor.OGRSpatialSelectionContext(
            ogr_source_geom=self.task.ogr_source_geom,
            current_predicates=self.task.current_predicates,
            has_combine_operator=self.task.has_combine_operator,
            param_other_layers_combine_operator=self.task.param_other_layers_combine_operator,
            verify_and_create_spatial_index=self.task._verify_and_create_spatial_index,
        )
        ogr_executor.execute_ogr_spatial_selection(
            layer, current_layer, param_old_subset, context
        )
        logger.debug("_execute_ogr_spatial_selection: delegated to ogr_executor")

    def build_filter_from_selection(self, current_layer, layer_props, param_distant_geom_expression):
        """Delegates to ogr_executor.build_ogr_filter_from_selection()."""
        if not OGR_EXECUTOR_AVAILABLE:
            raise ImportError("ogr_executor module not available - cannot build OGR filter from selection")

        return ogr_executor.build_ogr_filter_from_selection(
            layer=current_layer,
            layer_props=layer_props,
            distant_geom_expression=param_distant_geom_expression
        )

    def simplify_source_for_fallback(self, source_layer):
        """
        v4.7 E6-S2: Simplify complex source geometries for OGR fallback.

        Args:
            source_layer: QgsVectorLayer containing source geometry

        Returns:
            QgsVectorLayer: Simplified source layer (may be new memory layer)
        """
        return _backend_services.simplify_source_for_ogr_fallback(source_layer, logger=logger)

    # ── Reset / Unfilter Actions ────────────────────────────────────────

    def reset_action(self, layer, name, cur, conn):
        """
        Execute reset action using OGR backend.

        Args:
            layer: QgsVectorLayer to reset
            name: Layer identifier
            cur: Database cursor (for history)
            conn: Database connection (for history)

        Returns:
            bool: True if successful
        """
        logger.info("Reset - OGR backend")

        history_repo = HistoryRepository(conn, cur)
        try:
            if self.task._ps_manager:
                try:
                    self.task._ps_manager.delete_subset_history(self.task.project_uuid, layer.id())
                except Exception as e:
                    logger.warning(f"Prepared statement failed, falling back to repository: {e}")
                    history_repo.delete_for_layer(self.task.project_uuid, layer.id())
            else:
                history_repo.delete_for_layer(self.task.project_uuid, layer.id())
        finally:
            history_repo.close()

        if ogr_execute_reset:
            return ogr_execute_reset(
                layer=layer,
                queue_subset_func=self.task._queue_subset_string,
                cleanup_temp_layers=True
            )

        # Fallback: simple subset clear
        self.task._queue_subset_string(layer, '')
        return True

    def unfilter_action(self, layer, cur, conn, last_subset_id):
        """
        Unfilter implementation for OGR backend.

        Args:
            layer: QgsVectorLayer to unfilter
            cur: Database cursor (for history)
            conn: Database connection (for history)
            last_subset_id: Last subset ID to remove

        Returns:
            bool: True if successful
        """
        history_repo = HistoryRepository(conn, cur)
        try:
            if last_subset_id:
                history_repo.delete_entry(self.task.project_uuid, layer.id(), last_subset_id)
            last_entry = history_repo.get_last_entry(self.task.project_uuid, layer.id())
        finally:
            history_repo.close()

        previous_subset = None

        if last_entry:
            previous_subset = last_entry.subset_string

            if not previous_subset or not previous_subset.strip():
                logger.warning(
                    f"Unfilter OGR: Previous subset from history is empty for {layer.name()}. "
                    f"Clearing layer filter."
                )
                previous_subset = None

        if ogr_execute_unfilter:
            return ogr_execute_unfilter(
                layer=layer,
                previous_subset=previous_subset,
                queue_subset_func=self.task._queue_subset_string
            )

        # Fallback: direct subset application
        self.task._queue_subset_string(layer, previous_subset or '')
        return True
