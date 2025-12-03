# -*- coding: utf-8 -*-
"""
Backend Factory for FilterMate

Factory pattern implementation for selecting the appropriate backend
based on layer provider type.
"""

from typing import Dict
from qgis.core import QgsVectorLayer
from .base_backend import GeometricFilterBackend
from .postgresql_backend import PostgreSQLGeometricFilter, POSTGRESQL_AVAILABLE
from .spatialite_backend import SpatialiteGeometricFilter
from .ogr_backend import OGRGeometricFilter
from ..logging_config import get_tasks_logger
from ..constants import PROVIDER_POSTGRES, PROVIDER_SPATIALITE, PROVIDER_OGR

logger = get_tasks_logger()


class BackendFactory:
    """
    Factory for creating appropriate backend instances.
    
    The factory selects the best backend based on:
    1. Layer provider type (postgres, spatialite, ogr)
    2. Availability of required libraries (psycopg2 for PostgreSQL)
    3. Fallback to OGR for unknown providers
    """
    
    @staticmethod
    def get_backend(
        layer_provider_type: str,
        layer: QgsVectorLayer,
        task_params: Dict
    ) -> GeometricFilterBackend:
        """
        Get the appropriate backend for the given layer.
        
        Args:
            layer_provider_type: Provider type string ('postgresql', 'spatialite', 'ogr')
            layer: QgsVectorLayer instance
            task_params: Task parameters dictionary
        
        Returns:
            GeometricFilterBackend: Appropriate backend instance
        """
        logger.debug(f"Selecting backend for provider type: {layer_provider_type}")
        
        # Try PostgreSQL backend first if available
        if layer_provider_type == PROVIDER_POSTGRES and POSTGRESQL_AVAILABLE:
            backend = PostgreSQLGeometricFilter(task_params)
            if backend.supports_layer(layer):
                logger.info(f"Using PostgreSQL backend for {layer.name()}")
                return backend
        
        # Try Spatialite backend
        if layer_provider_type == PROVIDER_SPATIALITE:
            backend = SpatialiteGeometricFilter(task_params)
            if backend.supports_layer(layer):
                logger.info(f"Using Spatialite backend for {layer.name()}")
                return backend
        
        # Fallback to OGR backend (supports everything)
        logger.info(f"Using OGR backend (fallback) for {layer.name()}")
        return OGRGeometricFilter(task_params)
    
    @staticmethod
    def get_backend_for_provider(
        provider_type: str,
        task_params: Dict
    ) -> GeometricFilterBackend:
        """
        Get backend instance for a provider type without checking layer.
        
        Args:
            provider_type: Provider type string
            task_params: Task parameters
        
        Returns:
            Backend instance
        """
        if provider_type == PROVIDER_POSTGRES and POSTGRESQL_AVAILABLE:
            return PostgreSQLGeometricFilter(task_params)
        elif provider_type == PROVIDER_SPATIALITE:
            return SpatialiteGeometricFilter(task_params)
        else:
            return OGRGeometricFilter(task_params)
