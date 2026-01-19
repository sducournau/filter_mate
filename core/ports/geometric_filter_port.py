# -*- coding: utf-8 -*-
"""
Geometric Filter Port Interface.

v4.1.0: Migrated from before_migration/modules/backends/base_backend.py

This interface defines the legacy API for geometric filtering backends:
- build_expression(): Generate SQL/expression for spatial filter
- apply_filter(): Apply the filter to a QGIS layer

This is maintained for backward compatibility with FilterEngineTask and
legacy code while the new BackendPort.execute() interface is adopted.

Architecture Note:
==================
- BackendPort: New hexagonal interface (execute() method)
- GeometricFilterPort: Legacy interface (build_expression + apply_filter)
- LegacyAdapter: Bridge between the two interfaces

Author: FilterMate Team
Date: January 2026
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
import logging

logger = logging.getLogger('FilterMate.Ports.GeometricFilter')


class GeometricFilterPort(ABC):
    """
    Abstract interface for geometric filtering backends (legacy API).
    
    Each backend is responsible for:
    1. Building filter expressions appropriate for its data source
    2. Applying filters to layers
    3. Verifying compatibility with specific layer types
    
    This interface is used by:
    - FilterEngineTask (core/tasks/filter_task.py)
    - LegacyAdapter (adapters/backends/legacy_adapter.py)
    
    Implementations:
    - PostgreSQLExpressionBuilder (PostGIS SQL)
    - SpatialiteExpressionBuilder (Spatialite SQL)
    - OGRExpressionBuilder (QGIS Processing)
    - MemoryExpressionBuilder (In-memory)
    """
    
    def __init__(self, task_params: Dict[str, Any]):
        """
        Initialize the backend with task parameters.
        
        Args:
            task_params: Dictionary containing all task configuration parameters
                - source_layer_id: Source layer ID
                - target_layer_ids: Target layer IDs
                - predicates: Spatial predicates to apply
                - buffer_value: Buffer distance
                - use_centroids: Use centroid optimization
                - etc.
        """
        self.task_params = task_params
        self._logger = logger
    
    @abstractmethod
    def build_expression(
        self, 
        layer_props: Dict[str, Any], 
        predicates: Dict[str, bool],
        source_geom: Optional[str] = None,
        buffer_value: Optional[float] = None,
        buffer_expression: Optional[str] = None,
        source_filter: Optional[str] = None,
        use_centroids: bool = False,
        **kwargs
    ) -> str:
        """
        Build a filter expression for this backend.
        
        Args:
            layer_props: Layer properties dictionary containing:
                - layer_name: Display name
                - layer_table_name: Actual table name (for DB layers)
                - layer_schema: Schema name (PostgreSQL)
                - layer_geometry_field: Geometry column name
                - layer_srid: Spatial reference ID
                - primary_key_name: Primary key column
                - layer: QgsVectorLayer instance
                
            predicates: Dictionary of spatial predicates to apply:
                - intersects: bool
                - contains: bool
                - within: bool
                - touches: bool
                - overlaps: bool
                - crosses: bool
                - disjoint: bool
                
            source_geom: Source geometry for spatial filtering
                - For simple mode: WKT string
                - For EXISTS mode: Table reference expression
                
            buffer_value: Buffer distance value (optional)
            
            buffer_expression: Expression for dynamic buffer (optional)
                - Attribute-based: e.g., "buffer_distance" (column name)
                
            source_filter: Source layer filter expression (optional)
                - Used in EXISTS subqueries for complex filters
                
            use_centroids: If True, use centroids for distant layers
                - Improves performance for complex polygons
                
            **kwargs: Additional backend-specific parameters:
                - source_wkt: WKT string for simple mode
                - source_srid: SRID for the source WKT
                - source_feature_count: Number of source features
        
        Returns:
            Filter expression as a string suitable for this backend:
            - PostgreSQL: PostGIS SQL expression
            - Spatialite: Spatialite SQL expression
            - OGR: FID list or QGIS expression (fallback)
        
        Example (PostgreSQL):
            >>> expr = backend.build_expression(
            ...     layer_props={'layer_schema': 'public', 'layer_table_name': 'buildings'},
            ...     predicates={'intersects': True},
            ...     source_wkt='POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))',
            ...     source_srid=4326
            ... )
            >>> print(expr)
            'ST_Intersects("geom", ST_GeomFromText('POLYGON((...))', 4326))'
        """
        raise NotImplementedError("Subclasses must implement build_expression()")
    
    @abstractmethod
    def apply_filter(
        self, 
        layer: 'QgsVectorLayer', 
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply the filter expression to the layer.
        
        Args:
            layer: QGIS vector layer to filter
            
            expression: Filter expression to apply
                - Result from build_expression()
                - Or FID-based expression like "fid IN (1,2,3)"
                
            old_subset: Existing subset string (optional)
                - Current filter on the layer
                - Will be combined with new expression if combine_operator set
                
            combine_operator: Operator to combine with existing filter
                - 'AND': Intersect filters (more restrictive)
                - 'OR': Union filters (less restrictive)
                - None: Replace existing filter
        
        Returns:
            True if filter was applied successfully, False otherwise
        
        Example:
            >>> success = backend.apply_filter(
            ...     layer=my_layer,
            ...     expression="population > 10000",
            ...     old_subset="country = 'France'",
            ...     combine_operator='AND'
            ... )
            >>> # Result: "country = 'France' AND population > 10000"
        """
        raise NotImplementedError("Subclasses must implement apply_filter()")
    
    @abstractmethod
    def supports_layer(self, layer: 'QgsVectorLayer') -> bool:
        """
        Check if this backend supports the given layer.
        
        Args:
            layer: QGIS vector layer to check
        
        Returns:
            True if this backend can handle the layer, False otherwise
        
        Example:
            >>> pg_backend.supports_layer(postgresql_layer)
            True
            >>> pg_backend.supports_layer(shapefile_layer)
            False
        """
        raise NotImplementedError("Subclasses must implement supports_layer()")
    
    def get_backend_name(self) -> str:
        """
        Get the human-readable name of this backend.
        
        Returns:
            Backend name as string (e.g., 'PostgreSQL', 'Spatialite', 'OGR')
        """
        return self.__class__.__name__
    
    # =========================================================================
    # Logging Helpers
    # =========================================================================
    
    def log_info(self, message: str) -> None:
        """Log info message with backend prefix."""
        self._logger.info(f"[{self.get_backend_name()}] {message}")
    
    def log_warning(self, message: str) -> None:
        """Log warning message with backend prefix."""
        self._logger.warning(f"[{self.get_backend_name()}] {message}")
    
    def log_error(self, message: str) -> None:
        """Log error message with backend prefix."""
        self._logger.error(f"[{self.get_backend_name()}] {message}")
    
    def log_debug(self, message: str) -> None:
        """Log debug message with backend prefix."""
        self._logger.debug(f"[{self.get_backend_name()}] {message}")
    
    # =========================================================================
    # Buffer Configuration Helpers (v2.8.6)
    # =========================================================================
    
    def _get_buffer_endcap_style(self) -> str:
        """
        Get the buffer endcap style from task_params.
        
        Supports PostGIS/Spatialite ST_Buffer 'endcap' parameter:
        - 'round' (default): Rounded ends
        - 'flat': Flat/square ends perpendicular to line
        - 'square': Square ends extending beyond line
        
        Returns:
            Endcap style string for ST_Buffer
        """
        return self.task_params.get('buffer_endcap_style', 'round')
    
    def _get_buffer_join_style(self) -> str:
        """
        Get the buffer join style from task_params.
        
        Supports PostGIS/Spatialite ST_Buffer 'join' parameter:
        - 'round' (default): Rounded corners
        - 'mitre': Sharp corners (may extend beyond buffer distance)
        - 'bevel': Flattened corners
        
        Returns:
            Join style string for ST_Buffer
        """
        return self.task_params.get('buffer_join_style', 'round')
    
    def _get_buffer_mitre_limit(self) -> float:
        """
        Get the buffer mitre limit from task_params.
        
        Controls maximum extension of mitre joins.
        Default: 5.0 (PostGIS default)
        
        Returns:
            Mitre limit as float
        """
        return self.task_params.get('buffer_mitre_limit', 5.0)


# =============================================================================
# Type hints for QGIS objects (avoid import at module level)
# =============================================================================

# These are for documentation only - actual types come from qgis.core
try:
    from qgis.core import QgsVectorLayer
except ImportError:
    # Allow module to be imported without QGIS for testing
    QgsVectorLayer = 'QgsVectorLayer'


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'GeometricFilterPort',
]
