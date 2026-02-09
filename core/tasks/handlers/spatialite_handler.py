# -*- coding: utf-8 -*-
"""
Spatialite Backend Handler for FilterEngineTask.

Phase 4 (v6.0): Extracted from core/tasks/filter_task.py to reduce God class.
Contains all Spatialite-specific operations:
- Connection management
- Geometry preparation
- Query building and subset management
- Filter/reset/unfilter actions

Location: core/tasks/handlers/spatialite_handler.py (Hexagonal Architecture - Application Layer)
"""

import logging
import os
import sqlite3
from typing import Any, Optional

from ....infrastructure.logging import setup_logger
from ....config.config import ENV_VARS
from ....infrastructure.utils import (
    spatialite_connect,
    ensure_db_directory_exists,
)
from ....adapters.repositories.history_repository import HistoryRepository

# Core imports
from ...ports.backend_services import get_backend_services

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.SpatialiteHandler',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)

# Backend services facade
_backend_services = get_backend_services()

# Spatialite executor
sl_executor = _backend_services.get_spatialite_executor()
SL_EXECUTOR_AVAILABLE = sl_executor is not None


class SpatialiteHandler:
    """Handler for Spatialite-specific operations in FilterEngineTask.

    Phase 4 (v6.0): Extracted 10 methods from FilterEngineTask.
    Access task state via self.task.* (e.g., self.task.source_layer, self.task.session_id).
    """

    def __init__(self, task):
        """Initialize with reference to the parent FilterEngineTask.

        Args:
            task: FilterEngineTask instance
        """
        self.task = task

    # ── Connection ──────────────────────────────────────────────────────

    def safe_connect(self):
        """
        Get a Spatialite connection for the current task.

        Ensures the database directory exists before connecting.

        Returns:
            sqlite3.Connection: Spatialite database connection
        """
        ensure_db_directory_exists(self.task.db_file_path)
        return spatialite_connect(self.task.db_file_path)

    # ── Expression Conversion ───────────────────────────────────────────

    def qgis_expression_to_spatialite(self, expression):
        """Convert a QGIS expression to Spatialite-compatible SQL.

        Args:
            expression: QGIS expression string to convert.

        Returns:
            Spatialite-compatible SQL expression, or original if empty.
        """
        if not expression:
            return expression
        geom_col = getattr(self.task, 'param_source_geom', None) or 'geometry'
        from ...services.expression_service import ExpressionService
        from ...domain.filter_expression import ProviderType
        return ExpressionService().to_sql(expression, ProviderType.SPATIALITE, geom_col)

    # ── Geometry Preparation ────────────────────────────────────────────

    def prepare_source_geom(self):
        """Prepare source geometry for Spatialite filtering. Delegated to BackendServices facade.

        Returns:
            str: WKT geometry string, or None if preparation failed
        """
        SpatialiteSourceContext = _backend_services.get_spatialite_source_context_class()
        if SpatialiteSourceContext is None:
            raise ImportError("SpatialiteSourceContext not available")

        context = SpatialiteSourceContext(
            source_layer=self.task.source_layer,
            task_parameters=self.task.task_parameters,
            is_field_expression=getattr(self.task, 'is_field_expression', None),
            expression=getattr(self.task, 'expression', None),
            param_source_new_subset=getattr(self.task, 'param_source_new_subset', None),
            param_buffer_value=getattr(self.task, 'param_buffer_value', None),
            has_to_reproject_source_layer=getattr(self.task, 'has_to_reproject_source_layer', False),
            source_layer_crs_authid=getattr(self.task, 'source_layer_crs_authid', None),
            source_crs=getattr(self.task, 'source_crs', None),
            param_use_centroids_source_layer=getattr(self.task, 'param_use_centroids_source_layer', False),
            PROJECT=getattr(self.task, 'PROJECT', None),
            geom_cache=getattr(self.task, 'geom_cache', None),
            geometry_to_wkt=self.task._geometry_to_wkt,
            simplify_geometry_adaptive=self.task._simplify_geometry_adaptive,
            get_optimization_thresholds=self.task._get_optimization_thresholds,
        )

        result = _backend_services.prepare_spatialite_source_geom(context)
        if result.success:
            self.task.spatialite_source_geom = result.wkt
            if hasattr(self.task, 'task_parameters') and self.task.task_parameters:
                if 'infos' not in self.task.task_parameters:
                    self.task.task_parameters['infos'] = {}
                self.task.task_parameters['infos']['source_geom_wkt'] = result.wkt
                self.task.task_parameters['infos']['buffer_state'] = result.buffer_state
            logger.debug(f"prepare_spatialite_source_geom: WKT length = {len(result.wkt) if result.wkt else 0}")
            logger.info(f"Spatialite source geom prepared: {len(result.wkt)} chars")
            return result.wkt
        else:
            error_msg = result.error_message or "Unknown error"
            logger.error(f"prepare_spatialite_source_geom failed: {error_msg}")
            from qgis.core import QgsMessageLog, Qgis
            QgsMessageLog.logMessage(
                f"Spatialite geometry preparation FAILED: {error_msg}",
                "FilterMate", Qgis.Critical
            )
            logger.error(f"  This will cause distant layer filtering to fail!")
            logger.error(f"  Check if source layer has valid geometry")
            logger.error(f"  Check if source layer has features selected or filtered")
            self.task.spatialite_source_geom = None
            return None

    # ── Query Building & Subset Management ──────────────────────────────

    def get_datasource(self, layer):
        """
        Get Spatialite datasource information from layer.

        Args:
            layer: QGIS vector layer

        Returns:
            tuple: (db_path, table_name, layer_srid, is_native_spatialite)
        """
        from ....infrastructure.utils import get_spatialite_datasource_from_layer

        db_path, table_name = get_spatialite_datasource_from_layer(layer)
        layer_srid = layer.crs().postgisSrid()

        is_native_spatialite = db_path is not None

        if not is_native_spatialite:
            db_path = self.task.db_file_path
            logger.info("Non-Spatialite layer detected, will use QGIS subset string")

        return db_path, table_name, layer_srid, is_native_spatialite

    def build_query(self, sql_subset_string, table_name, geom_key_name,
                    primary_key_name, custom):
        """Build Spatialite query for simple or complex (buffered) subsets. Delegated to sl_executor."""
        if SL_EXECUTOR_AVAILABLE:
            return sl_executor.build_spatialite_query(
                sql_subset_string=sql_subset_string,
                table_name=table_name,
                geom_key_name=geom_key_name,
                primary_key_name=primary_key_name,
                custom=custom,
                buffer_expression=getattr(self.task, 'param_buffer_expression', None),
                buffer_value=getattr(self.task, 'param_buffer_value', None),
                buffer_segments=getattr(self.task, 'param_buffer_segments', 5),
                task_parameters=getattr(self.task, 'task_parameters', None)
            )
        return sql_subset_string

    def apply_subset(self, layer, name, primary_key_name, sql_subset_string,
                     cur, conn, current_seq_order):
        """
        Apply subset string to layer and update history.

        Args:
            layer: QGIS vector layer
            name: Temp table name
            primary_key_name: Primary key field name
            sql_subset_string: Original SQL subset string for history
            cur: Spatialite cursor for history
            conn: Spatialite connection for history
            current_seq_order: Sequence order for history

        Returns:
            bool: True if successful
        """
        return _backend_services.apply_spatialite_subset(
            layer=layer,
            name=name,
            primary_key_name=primary_key_name,
            sql_subset_string=sql_subset_string,
            cur=cur,
            conn=conn,
            current_seq_order=current_seq_order,
            session_id=self.task.session_id,
            project_uuid=self.task.project_uuid,
            source_layer_id=self.task.source_layer.id() if self.task.source_layer else None,
            queue_subset_func=self.task._queue_subset_string
        )

    def manage_subset(self, layer, sql_subset_string, primary_key_name, geom_key_name,
                      name, custom=False, cur=None, conn=None, current_seq_order=0):
        """
        Handle Spatialite temporary tables for filtering.

        Args:
            layer: QGIS vector layer
            sql_subset_string: SQL query for subset
            primary_key_name: Primary key field name
            geom_key_name: Geometry field name
            name: Unique name for temp table
            custom: Whether custom buffer expression is used
            cur: Spatialite cursor for history
            conn: Spatialite connection for history
            current_seq_order: Sequence order for history

        Returns:
            bool: True if successful
        """
        return _backend_services.manage_spatialite_subset(
            layer=layer,
            sql_subset_string=sql_subset_string,
            primary_key_name=primary_key_name,
            geom_key_name=geom_key_name,
            name=name,
            custom=custom,
            cur=cur,
            conn=conn,
            current_seq_order=current_seq_order,
            session_id=self.task.session_id,
            project_uuid=self.task.project_uuid,
            source_layer_id=self.task.source_layer.id() if self.task.source_layer else None,
            queue_subset_func=self.task._queue_subset_string,
            get_spatialite_datasource_func=self.get_datasource,
            task_parameters=self.task.task_parameters
        )

    def get_last_subset_info(self, cur, layer):
        """
        Get the last subset information for a layer from history.

        Args:
            cur: Database cursor
            layer: QgsVectorLayer

        Returns:
            tuple: (last_subset_id, last_seq_order, layer_name, name)
        """
        return _backend_services.get_last_subset_info(cur, layer, self.task.project_uuid)

    # ── Reset / Unfilter Actions ────────────────────────────────────────

    def reset_action(self, layer, name, cur, conn):
        """
        Execute reset action using Spatialite backend.

        Args:
            layer: QgsVectorLayer to reset
            name: Layer identifier
            cur: Database cursor
            conn: Database connection

        Returns:
            bool: True if successful
        """
        logger.info("Reset - Spatialite backend - dropping temp table")

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

        # Drop temp table using session-prefixed name
        session_name = self.task._get_session_prefixed_name(name)
        try:
            temp_conn = sqlite3.connect(self.task.db_file_path)
            temp_cur = temp_conn.cursor()
            temp_cur.execute(f"DROP TABLE IF EXISTS fm_temp_{session_name}")
            temp_cur.execute(f"DROP TABLE IF EXISTS mv_{session_name}")
            temp_conn.commit()
            temp_cur.close()
            temp_conn.close()
        except Exception as e:
            logger.error(f"Error dropping Spatialite temp table: {e}")

        self.task._queue_subset_string(layer, '')
        return True

    def unfilter_action(self, layer, primary_key_name, geom_key_name, name, custom, cur, conn, last_subset_id):
        """Unfilter implementation for Spatialite backend."""
        history_repo = HistoryRepository(conn, cur)
        try:
            if last_subset_id:
                history_repo.delete_entry(self.task.project_uuid, layer.id(), last_subset_id)
            last_entry = history_repo.get_last_entry(self.task.project_uuid, layer.id())
        finally:
            history_repo.close()

        if last_entry:
            sql_subset_string = last_entry.subset_string

            if not sql_subset_string or not sql_subset_string.strip():
                logger.warning(
                    f"Unfilter: Previous subset string from history is empty for {layer.name()}. "
                    f"Clearing layer filter."
                )
                self.task._queue_subset_string(layer, '')
                return True

            logger.info("Unfilter - Spatialite backend - recreating previous subset")
            success = self.manage_subset(
                layer, sql_subset_string, primary_key_name, geom_key_name,
                name, custom=False, cur=None, conn=None, current_seq_order=0
            )
            if not success:
                self.task._queue_subset_string(layer, '')
        else:
            self.task._queue_subset_string(layer, '')

        return True
