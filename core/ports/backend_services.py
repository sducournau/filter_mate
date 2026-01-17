"""
Backend Services Port - Facade for backend adapter access.

EPIC-1 Phase E13: Encapsulates adapter imports to maintain hexagonal architecture.

This module provides a clean interface for filter_task.py to access
backend-specific functionality without direct imports from adapters/.

Usage:
    from core.ports.backend_services import BackendServices
    
    services = BackendServices.get_instance()
    pg_executor = services.get_postgresql_executor()
    sl_executor = services.get_spatialite_executor()
"""

import logging
from typing import Optional, Any, Callable, Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger('FilterMate.Ports.BackendServices')


@dataclass
class PostgreSQLAvailability:
    """PostgreSQL availability status."""
    psycopg2: Optional[Any] = None
    psycopg2_available: bool = False
    postgresql_available: bool = False


class BackendServices:
    """
    Facade for backend adapter services.
    
    Provides lazy loading of backend executors and utilities,
    maintaining separation between core and adapters layers.
    """
    
    _instance: Optional['BackendServices'] = None
    
    def __init__(self):
        self._pg_availability: Optional[PostgreSQLAvailability] = None
        self._pg_executor = None
        self._sl_executor = None
        self._ogr_executor = None
        self._task_bridge = None
        self._geometry_adapter = None
        
    @classmethod
    def get_instance(cls) -> 'BackendServices':
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton for testing."""
        cls._instance = None
    
    # ==================== PostgreSQL Services ====================
    
    def get_postgresql_availability(self) -> PostgreSQLAvailability:
        """
        Get PostgreSQL availability status.
        
        Returns:
            PostgreSQLAvailability with psycopg2 module and flags
        """
        if self._pg_availability is None:
            try:
                from ...adapters.backends.postgresql_availability import (
                    psycopg2, PSYCOPG2_AVAILABLE, POSTGRESQL_AVAILABLE
                )
                self._pg_availability = PostgreSQLAvailability(
                    psycopg2=psycopg2,
                    psycopg2_available=PSYCOPG2_AVAILABLE,
                    postgresql_available=POSTGRESQL_AVAILABLE
                )
            except ImportError:
                logger.debug("PostgreSQL availability module not found")
                self._pg_availability = PostgreSQLAvailability()
        return self._pg_availability
    
    def get_postgresql_executor(self) -> Optional[Any]:
        """
        Get PostgreSQL filter executor module.
        
        Returns:
            pg_executor module or None if unavailable
        """
        if self._pg_executor is None:
            try:
                from ...adapters.backends.postgresql import filter_executor as pg_executor
                self._pg_executor = pg_executor
            except ImportError as e:
                logger.debug(f"PostgreSQL executor not available: {e}")
        return self._pg_executor
    
    def get_postgresql_filter_actions(self) -> Optional[Dict[str, Callable]]:
        """
        Get PostgreSQL filter action functions.
        
        Returns:
            Dict with action functions or None
        """
        try:
            from ...adapters.backends.postgresql.filter_actions import (
                execute_filter_action_postgresql,
                execute_reset_action_postgresql,
                execute_unfilter_action_postgresql
            )
            return {
                'filter': execute_filter_action_postgresql,
                'reset': execute_reset_action_postgresql,
                'unfilter': execute_unfilter_action_postgresql
            }
        except ImportError as e:
            logger.debug(f"PostgreSQL filter actions not available: {e}")
            return None
    
    def get_postgresql_schema_manager(self) -> Optional[Any]:
        """
        Get PostgreSQL schema manager module.
        
        Returns:
            Schema manager module or None
        """
        try:
            from ...adapters.backends.postgresql import schema_manager
            return schema_manager
        except ImportError as e:
            logger.debug(f"PostgreSQL schema manager not available: {e}")
            return None
    
    def prepare_postgresql_source_geom(self, *args, **kwargs) -> Any:
        """
        Delegate to PostgreSQL source geometry preparation.
        
        Returns:
            Result from pg_prepare_source_geom
        """
        try:
            from ...adapters.backends.postgresql import (
                prepare_postgresql_source_geom as pg_prepare
            )
            return pg_prepare(*args, **kwargs)
        except ImportError as e:
            logger.error(f"Cannot prepare PostgreSQL source geom: {e}")
            raise
    
    # ==================== Spatialite Services ====================
    
    def get_spatialite_executor(self) -> Optional[Any]:
        """
        Get Spatialite filter executor module.
        
        Returns:
            sl_executor module or None if unavailable
        """
        if self._sl_executor is None:
            try:
                from ...adapters.backends.spatialite import filter_executor as sl_executor
                self._sl_executor = sl_executor
            except ImportError as e:
                logger.debug(f"Spatialite executor not available: {e}")
        return self._sl_executor
    
    def get_spatialite_functions(self) -> Optional[Dict[str, Callable]]:
        """
        Get Spatialite utility functions.
        
        Returns:
            Dict with utility functions or None
        """
        try:
            from ...adapters.backends.spatialite import (
                apply_spatialite_subset,
                manage_spatialite_subset,
                get_last_subset_info
            )
            return {
                'apply_subset': apply_spatialite_subset,
                'manage_subset': manage_spatialite_subset,
                'get_last_subset_info': get_last_subset_info
            }
        except ImportError as e:
            logger.debug(f"Spatialite functions not available: {e}")
            return None
    
    def get_spatialite_filter_actions(self) -> Optional[Dict[str, Callable]]:
        """
        Get Spatialite filter action functions (reset/unfilter).
        
        Phase 1 v4.1: Added Spatialite backend actions.
        
        Returns:
            Dict with action functions or None
        """
        try:
            from ...adapters.backends.spatialite.filter_actions import (
                execute_reset_action_spatialite,
                execute_unfilter_action_spatialite,
                cleanup_spatialite_session_tables
            )
            return {
                'reset': execute_reset_action_spatialite,
                'unfilter': execute_unfilter_action_spatialite,
                'cleanup': cleanup_spatialite_session_tables
            }
        except ImportError as e:
            logger.debug(f"Spatialite filter actions not available: {e}")
            return None
    
    # ==================== OGR Services ====================
    
    def get_ogr_executor(self) -> Optional[Any]:
        """
        Get OGR filter executor module.
        
        Returns:
            ogr_executor module or None if unavailable
        """
        if self._ogr_executor is None:
            try:
                from ...adapters.backends.ogr import filter_executor as ogr_executor
                self._ogr_executor = ogr_executor
            except ImportError as e:
                logger.debug(f"OGR executor not available: {e}")
        return self._ogr_executor
    
    def get_ogr_filter_actions(self) -> Optional[Dict[str, Callable]]:
        """
        Get OGR filter action functions.
        
        EPIC-1 Phase E4-S8: OGR Reset and Unfilter Actions
        
        Returns:
            Dict with action functions or None
        """
        try:
            from ...adapters.backends.ogr.filter_executor import (
                execute_reset_action_ogr,
                execute_unfilter_action_ogr,
                apply_ogr_subset,
                cleanup_ogr_temp_layers
            )
            return {
                'reset': execute_reset_action_ogr,
                'unfilter': execute_unfilter_action_ogr,
                'apply_subset': apply_ogr_subset,
                'cleanup': cleanup_ogr_temp_layers
            }
        except ImportError as e:
            logger.debug(f"OGR filter actions not available: {e}")
            return None
    
    def cleanup_ogr_temp_layers(self) -> int:
        """
        Cleanup OGR temporary layers.
        
        Returns:
            Number of layers cleaned up
        """
        try:
            from ...adapters.backends.ogr.filter_executor import cleanup_ogr_temp_layers
            return cleanup_ogr_temp_layers()
        except ImportError:
            return 0  # OGR not available
        except Exception as e:
            logger.debug(f"OGR cleanup failed: {e}")
            return 0
    
    def simplify_source_for_ogr_fallback(self, *args, **kwargs) -> Any:
        """
        Delegate to OGR geometry optimizer.
        
        Returns:
            Simplified geometry
        """
        try:
            from ...adapters.backends.ogr.geometry_optimizer import simplify_source_for_ogr_fallback
            return simplify_source_for_ogr_fallback(*args, **kwargs)
        except ImportError as e:
            logger.error(f"OGR geometry optimizer not available: {e}")
            raise
    
    # ==================== Task Bridge Services ====================
    
    def get_task_bridge(self) -> Tuple[Optional[Callable], Optional[Any]]:
        """
        Get task bridge factory and status enum.
        
        Returns:
            Tuple of (get_task_bridge function, BridgeStatus enum)
        """
        try:
            from ...adapters.task_bridge import get_task_bridge, BridgeStatus
            return get_task_bridge, BridgeStatus
        except ImportError as e:
            logger.debug(f"Task bridge not available: {e}")
            return None, None
    
    # ==================== Geometry Preparation Services ====================
    
    def get_geometry_preparation_adapter(self) -> Optional[Any]:
        """
        Get QGIS geometry preparation adapter.
        
        Returns:
            GeometryPreparationAdapter class or None
        """
        if self._geometry_adapter is None:
            try:
                from ...adapters.qgis.geometry_preparation import GeometryPreparationAdapter
                self._geometry_adapter = GeometryPreparationAdapter
            except ImportError as e:
                logger.debug(f"Geometry preparation adapter not available: {e}")
        return self._geometry_adapter
    
    # ==================== Spatialite Extended Functions ====================
    
    def apply_spatialite_subset(self, *args, **kwargs) -> Any:
        """Delegate to Spatialite apply_spatialite_subset."""
        try:
            from ...adapters.backends.spatialite import apply_spatialite_subset
            return apply_spatialite_subset(*args, **kwargs)
        except ImportError as e:
            logger.error(f"Spatialite apply_subset not available: {e}")
            raise
    
    def manage_spatialite_subset(self, *args, **kwargs) -> Any:
        """Delegate to Spatialite manage_spatialite_subset."""
        try:
            from ...adapters.backends.spatialite import manage_spatialite_subset
            return manage_spatialite_subset(*args, **kwargs)
        except ImportError as e:
            logger.error(f"Spatialite manage_subset not available: {e}")
            raise
    
    def get_last_subset_info(self, *args, **kwargs) -> Any:
        """Delegate to Spatialite get_last_subset_info."""
        try:
            from ...adapters.backends.spatialite import get_last_subset_info
            return get_last_subset_info(*args, **kwargs)
        except ImportError as e:
            logger.error(f"Spatialite get_last_subset_info not available: {e}")
            raise
    
    def get_spatialite_source_context_class(self) -> Optional[type]:
        """
        Get SpatialiteSourceContext class for building context objects.
        
        Returns:
            SpatialiteSourceContext class or None
        """
        try:
            from ...adapters.backends.spatialite import SpatialiteSourceContext
            return SpatialiteSourceContext
        except ImportError as e:
            logger.error(f"SpatialiteSourceContext not available: {e}")
            return None
    
    def prepare_spatialite_source_geom(self, *args, **kwargs) -> Any:
        """Delegate to Spatialite source geometry preparation."""
        try:
            from ...adapters.backends.spatialite import (
                prepare_spatialite_source_geom as sl_prepare
            )
            return sl_prepare(*args, **kwargs)
        except ImportError as e:
            logger.error(f"Spatialite prepare_source_geom not available: {e}")
            raise
    
    # ==================== PostgreSQL Schema Manager ====================
    
    def create_simple_materialized_view_sql(self, *args, **kwargs) -> str:
        """Delegate to PostgreSQL schema manager."""
        try:
            from ...adapters.backends.postgresql.schema_manager import create_simple_materialized_view_sql
            return create_simple_materialized_view_sql(*args, **kwargs)
        except ImportError as e:
            logger.error(f"PostgreSQL schema manager not available: {e}")
            raise
    
    def parse_case_to_where_clauses(self, *args, **kwargs) -> Any:
        """Delegate to PostgreSQL schema manager."""
        try:
            from ...adapters.backends.postgresql.schema_manager import parse_case_to_where_clauses
            return parse_case_to_where_clauses(*args, **kwargs)
        except ImportError as e:
            logger.error(f"PostgreSQL schema manager not available: {e}")
            raise
    
    def ensure_temp_schema_exists(self, *args, **kwargs) -> Any:
        """Delegate to PostgreSQL schema manager."""
        try:
            from ...adapters.backends.postgresql.schema_manager import ensure_temp_schema_exists
            return ensure_temp_schema_exists(*args, **kwargs)
        except ImportError as e:
            logger.error(f"PostgreSQL schema manager not available: {e}")
            raise
    
    def get_session_prefixed_name(self, *args, **kwargs) -> str:
        """Delegate to PostgreSQL schema manager."""
        try:
            from ...adapters.backends.postgresql.schema_manager import get_session_prefixed_name
            return get_session_prefixed_name(*args, **kwargs)
        except ImportError as e:
            logger.error(f"PostgreSQL schema manager not available: {e}")
            raise
    
    def cleanup_session_materialized_views(self, *args, **kwargs) -> Any:
        """Delegate to PostgreSQL schema manager."""
        try:
            from ...adapters.backends.postgresql.schema_manager import cleanup_session_materialized_views
            return cleanup_session_materialized_views(*args, **kwargs)
        except ImportError as e:
            logger.error(f"PostgreSQL schema manager not available: {e}")
            raise
    
    def cleanup_orphaned_materialized_views(self, *args, **kwargs) -> Any:
        """Delegate to PostgreSQL schema manager."""
        try:
            from ...adapters.backends.postgresql.schema_manager import cleanup_orphaned_materialized_views
            return cleanup_orphaned_materialized_views(*args, **kwargs)
        except ImportError as e:
            logger.error(f"PostgreSQL schema manager not available: {e}")
            raise
    
    def execute_postgresql_commands(self, *args, **kwargs) -> Any:
        """Delegate to PostgreSQL schema manager execute_commands."""
        try:
            from ...adapters.backends.postgresql.schema_manager import execute_commands
            return execute_commands(*args, **kwargs)
        except ImportError as e:
            logger.error(f"PostgreSQL schema manager not available: {e}")
            raise
    
    def ensure_table_stats(self, *args, **kwargs) -> Any:
        """Delegate to PostgreSQL schema manager."""
        try:
            from ...adapters.backends.postgresql.schema_manager import ensure_table_stats
            return ensure_table_stats(*args, **kwargs)
        except ImportError as e:
            logger.error(f"PostgreSQL schema manager not available: {e}")
            raise
    
    # ==================== Backend Factory ====================
    
    def get_backend_factory(self) -> Optional[type]:
        """
        Get BackendFactory class for creating backend instances.
        
        Returns:
            BackendFactory class or None
        """
        try:
            from ...adapters.backends.factory import BackendFactory
            return BackendFactory
        except ImportError as e:
            logger.debug(f"BackendFactory not available: {e}")
            return None
    
    def get_optimization_plan(self, *args, **kwargs) -> Any:
        """Get optimization plan from factory."""
        try:
            from ...adapters.backends.factory import get_optimization_plan
            return get_optimization_plan(*args, **kwargs)
        except ImportError as e:
            logger.error(f"get_optimization_plan not available: {e}")
            raise
    
    def is_auto_optimizer_available(self) -> bool:
        """Check if auto optimizer is available."""
        try:
            from ...adapters.backends.factory import AUTO_OPTIMIZER_AVAILABLE
            return AUTO_OPTIMIZER_AVAILABLE
        except ImportError:
            return False
    
    # ==================== Backend Classes ====================
    
    def get_postgresql_geometric_filter(self) -> Optional[type]:
        """Get PostgreSQLGeometricFilter class."""
        try:
            from ...adapters.backends.postgresql import PostgreSQLGeometricFilter
            return PostgreSQLGeometricFilter
        except ImportError as e:
            logger.debug(f"PostgreSQLGeometricFilter not available: {e}")
            return None
    
    def get_spatialite_geometric_filter(self) -> Optional[type]:
        """Get SpatialiteGeometricFilter class."""
        try:
            from ...adapters.backends.spatialite import SpatialiteGeometricFilter
            return SpatialiteGeometricFilter
        except ImportError as e:
            logger.debug(f"SpatialiteGeometricFilter not available: {e}")
            return None
    
    def get_spatialite_backend(self) -> Optional[type]:
        """Get SpatialiteBackend class (alias for SpatialiteGeometricFilter)."""
        try:
            from ...adapters.backends.spatialite import SpatialiteBackend
            return SpatialiteBackend
        except ImportError as e:
            logger.debug(f"SpatialiteBackend not available: {e}")
            return None
    
    def get_ogr_geometric_filter(self) -> Optional[type]:
        """Get OGRGeometricFilter class."""
        try:
            from ...adapters.backends.ogr import OGRGeometricFilter
            return OGRGeometricFilter
        except ImportError as e:
            logger.debug(f"OGRGeometricFilter not available: {e}")
            return None
    
    # ==================== OGR Utilities ====================
    
    def register_ogr_temp_layer(self, *args, **kwargs) -> Any:
        """Register OGR temporary layer."""
        try:
            from ...adapters.backends.ogr.filter_executor import register_temp_layer
            return register_temp_layer(*args, **kwargs)
        except ImportError as e:
            logger.error(f"OGR register_temp_layer not available: {e}")
            raise
    
    # ==================== Layer Validation ====================
    
    def is_valid_layer(self, *args, **kwargs) -> bool:
        """
        Validate layer. Delegates to infrastructure or adapter.
        
        Returns:
            bool: True if layer is valid
        """
        # Try infrastructure first (preferred location)
        try:
            from ...infrastructure.utils import is_layer_valid
            return is_layer_valid(*args, **kwargs)
        except ImportError:
            pass
        
        # Fallback to adapter
        try:
            from ...adapters.layer_validator import is_valid_layer
            return is_valid_layer(*args, **kwargs)
        except ImportError as e:
            logger.error(f"is_valid_layer not available: {e}")
            return False


# Convenience function for quick access
def get_backend_services() -> BackendServices:
    """Get BackendServices singleton instance."""
    return BackendServices.get_instance()


# Export availability check for backward compatibility
def get_postgresql_available() -> bool:
    """Check if PostgreSQL is available."""
    return get_backend_services().get_postgresql_availability().postgresql_available
