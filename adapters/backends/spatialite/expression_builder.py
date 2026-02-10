# -*- coding: utf-8 -*-
"""
Spatialite Expression Builder.

v4.1.0: Migrated from before_migration/modules/backends/spatialite_backend.py

This module contains the SQL expression building logic for Spatialite spatial filters.
It implements the GeometricFilterPort interface for Spatialite backends.

Features:
- GeoPackage support with GeomFromGPB conversion
- R-tree spatial index optimization
- WKT simplification for large geometries
- Centroid optimization
- CRS transformation handling

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Dict, Optional, Any

try:
    from qgis.core import QgsVectorLayer
except ImportError:
    QgsVectorLayer = None

logger = logging.getLogger('FilterMate.Backend.Spatialite.ExpressionBuilder')

# Import the port interface
try:
    from ....core.ports.geometric_filter_port import GeometricFilterPort
except ImportError:
    from core.ports.geometric_filter_port import GeometricFilterPort

# Import safe_set_subset_string from infrastructure
try:
    from ....infrastructure.database.sql_utils import safe_set_subset_string
except ImportError:
    def safe_set_subset_string(layer, expression):
        """Fallback implementation."""
        if layer is None:
            return False
        try:
            return layer.setSubsetString(expression)
        except Exception:
            return False

# Sentinel value for OGR fallback
USE_OGR_FALLBACK = "__USE_OGR_FALLBACK__"

# Thresholds
SPATIALITE_WKT_SIMPLIFY_THRESHOLD = 100000  # 100KB - simplify WKT above this


class SpatialiteExpressionBuilder(GeometricFilterPort):
    """
    Spatialite expression builder.

    Generates Spatialite SQL expressions for spatial filtering.
    Implements the legacy GeometricFilterPort interface for backward compatibility.

    Features:
    - GeoPackage binary geometry support
    - WKT simplification for large geometries
    - R-tree index optimization via temp tables
    - Centroid optimization
    - CRS transformation

    Example:
        builder = SpatialiteExpressionBuilder(task_params)
        expr = builder.build_expression(
            layer_props={'layer_table_name': 'buildings'},
            predicates={'intersects': True},
            source_geom='POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))'
        )
    """

    # Spatialite predicate mapping
    PREDICATE_FUNCTIONS = {
        'intersects': 'Intersects',
        'contains': 'Contains',
        'within': 'Within',
        'touches': 'Touches',
        'overlaps': 'Overlaps',
        'crosses': 'Crosses',
        'disjoint': 'Disjoint',
        'equals': 'Equals',
        'covers': 'Covers',
        'coveredby': 'CoveredBy',
    }

    def __init__(self, task_params: Dict[str, Any]):
        """
        Initialize Spatialite expression builder.

        Args:
            task_params: Task configuration parameters
        """
        super().__init__(task_params)
        self._logger = logger

    def get_backend_name(self) -> str:
        """Get backend name."""
        return "Spatialite"

    def supports_layer(self, layer: 'QgsVectorLayer') -> bool:
        """
        Check if this backend supports the given layer.

        Args:
            layer: QGIS vector layer to check

        Returns:
            True if layer is Spatialite or GeoPackage
        """
        if layer is None:
            return False

        provider = layer.providerType()
        if provider == 'spatialite':
            return True

        # Check for GeoPackage via OGR
        if provider == 'ogr':
            source = layer.source().lower()
            if '.gpkg' in source or 'gpkg|' in source:
                return True

        return False

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
        Build Spatialite filter expression.

        Args:
            layer_props: Layer properties
            predicates: Spatial predicates to apply
            source_geom: Source geometry WKT
            buffer_value: Buffer distance
            buffer_expression: Dynamic buffer expression
            source_filter: Source filter (not used)
            use_centroids: Use centroid optimization
            **kwargs: Additional parameters

        Returns:
            Spatialite SQL expression or USE_OGR_FALLBACK sentinel
        """
        self.log_debug(f"Building Spatialite expression for {layer_props.get('layer_name', 'unknown')}")

        # FIX v4.2.13: Spatialite cannot evaluate dynamic buffer expressions with field references
        # Unlike PostgreSQL which can create temp tables with pre-calculated buffers,
        # Spatialite's Buffer(GeomFromText(wkt), "field_name" * 2) fails because
        # the field reference is not valid in the context of a WKT literal.
        # Solution: Fall back to OGR backend which uses QGIS native expression evaluation.
        if buffer_expression and buffer_expression.strip():
            self.log_warning(f"🔄 Dynamic buffer expression detected: {buffer_expression}")
            self.log_warning("   Spatialite cannot evaluate field references in Buffer()")
            self.log_warning("   → Falling back to OGR backend for native QGIS expression evaluation")
            return USE_OGR_FALLBACK

        # Extract layer properties
        layer_props.get("layer_table_name") or layer_props.get("layer_name")
        geom_field = self._detect_geometry_column(layer_props)
        layer = layer_props.get("layer")

        # Validate source geometry
        if not source_geom:
            self.log_error("No source geometry provided")
            return "1 = 0"

        if not isinstance(source_geom, str):
            self.log_error(f"Invalid source geometry type: {type(source_geom)}")
            return "1 = 0"

        wkt_length = len(source_geom)
        self.log_debug(f"Source WKT length: {wkt_length} chars")

        # Handle GeometryCollection (causes RTTOPO errors)
        is_geometry_collection = source_geom.strip().upper().startswith('GEOMETRYCOLLECTION')
        if is_geometry_collection:
            self.log_warning("GeometryCollection detected - returning OGR fallback")
            return USE_OGR_FALLBACK

        # Simplify large WKT
        if wkt_length >= SPATIALITE_WKT_SIMPLIFY_THRESHOLD:
            source_geom = self._simplify_wkt(source_geom)
            wkt_length = len(source_geom)
            self.log_info(f"WKT simplified to {wkt_length} chars")

        # Build geometry expression
        geom_expr = f'"{geom_field}"'

        # Detect GeoPackage and apply GPB conversion
        is_geopackage = self._is_geopackage(layer)
        if is_geopackage:
            geom_expr = f'GeomFromGPB({geom_expr})'
            self.log_info("GeoPackage detected: using GeomFromGPB()")

        # Apply centroid optimization
        if use_centroids:
            geom_expr = self._apply_centroid_transform(geom_expr, layer_props)

        # Get SRIDs
        target_srid = self._get_layer_srid(layer)
        source_srid = self._get_source_srid()

        self.log_debug(f"SRIDs: source={source_srid}, target={target_srid}")

        # Build source geometry SQL
        # FIX v4.2.11: Pass buffer_expression for dynamic buffer support
        source_geom_sql = self._build_source_geometry_sql(
            source_geom, source_srid, target_srid, buffer_value, buffer_expression
        )

        # Build predicate expressions
        predicate_expressions = []

        for predicate_name, predicate_value in predicates.items():
            if not predicate_value:
                continue

            # Get Spatialite function name
            predicate_func = self.PREDICATE_FUNCTIONS.get(
                predicate_name.lower().replace('st_', ''),
                'Intersects'
            )

            # Build expression
            expr = f"{predicate_func}({geom_expr}, {source_geom_sql})"
            predicate_expressions.append(expr)

        # Combine predicates
        if not predicate_expressions:
            self.log_warning("No predicates specified")
            return "1 = 0"

        if len(predicate_expressions) == 1:
            return predicate_expressions[0]
        else:
            return f"({' OR '.join(predicate_expressions)})"

    def apply_filter(
        self,
        layer: 'QgsVectorLayer',
        expression: str,
        old_subset: Optional[str] = None,
        combine_operator: Optional[str] = None
    ) -> bool:
        """
        Apply filter to Spatialite layer.

        Args:
            layer: Layer to filter
            expression: SQL expression
            old_subset: Existing filter
            combine_operator: Combine operator (AND/OR)

        Returns:
            True if filter applied successfully
        """
        try:
            if not expression:
                self.log_warning("Empty expression, skipping filter")
                return False

            # Check for OGR fallback sentinel
            if expression == USE_OGR_FALLBACK:
                self.log_info("OGR fallback requested")
                return False

            # Combine with existing filter if needed
            if old_subset and combine_operator:
                if self._is_geometric_filter(old_subset):
                    self.log_info("Replacing geometric filter in old_subset")
                    final_expression = expression
                else:
                    final_expression = f"({old_subset}) {combine_operator} ({expression})"
            else:
                final_expression = expression

            # Apply filter
            success = safe_set_subset_string(layer, final_expression)

            if success:
                self.log_info("✓ Filter applied successfully")
            else:
                self.log_error("✗ Failed to apply filter")

            return success

        except Exception as e:
            self.log_error(f"Error applying filter: {e}")
            return False

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    # NOTE v4.0.1: _detect_geometry_column, _apply_centroid_transform,
    # _get_layer_srid, _get_source_srid are inherited from GeometricFilterPort

    def _is_geopackage(self, layer) -> bool:
        """Check if layer is from a GeoPackage."""
        if not layer:
            return False
        source = layer.source().lower()
        return '.gpkg' in source or 'gpkg|' in source

    def _build_source_geometry_sql(
        self,
        source_wkt: str,
        source_srid: int,
        target_srid: int,
        buffer_value: Optional[float],
        buffer_expression: Optional[str] = None
    ) -> str:
        """
        Build SQL for source geometry.

        FIX v4.2.11: Added buffer_expression support for dynamic buffer.

        Args:
            source_wkt: WKT string of source geometry
            source_srid: Source SRID
            target_srid: Target SRID for transformation
            buffer_value: Static buffer value
            buffer_expression: Dynamic buffer expression (QGIS syntax)
        """
        # Escape single quotes in WKT
        escaped_wkt = source_wkt.replace("'", "''")

        # Build base geometry
        source_geom_sql = f"GeomFromText('{escaped_wkt}', {source_srid})"

        # Apply MakeValid
        source_geom_sql = f"MakeValid({source_geom_sql})"

        # Apply CRS transformation if needed
        if source_srid != target_srid:
            source_geom_sql = f"Transform({source_geom_sql}, {target_srid})"
            self.log_info(f"Applying CRS transform: {source_srid} → {target_srid}")

        # FIX v4.2.11: Support dynamic buffer expressions
        # Priority: buffer_expression (dynamic) > buffer_value (static)
        if buffer_expression and buffer_expression.strip():
            # Convert QGIS expression to Spatialite SQL
            from .filter_executor import qgis_expression_to_spatialite
            buffer_expr_sql = qgis_expression_to_spatialite(buffer_expression)

            self.log_info(f"🔧 Applying dynamic buffer expression: {buffer_expr_sql[:100]}...")
            source_geom_sql = f"Buffer({source_geom_sql}, {buffer_expr_sql})"

        # Apply static buffer
        elif buffer_value is not None and buffer_value != 0:
            source_geom_sql = f"Buffer({source_geom_sql}, {buffer_value})"
            self.log_info(f"Applying buffer: {buffer_value}")

            # Wrap negative buffers in MakeValid
            if buffer_value < 0:
                source_geom_sql = f"MakeValid({source_geom_sql})"

        return source_geom_sql

    def _simplify_wkt(self, wkt: str) -> str:
        """Simplify WKT geometry to reduce complexity."""
        try:
            from qgis.core import QgsGeometry
            geom = QgsGeometry.fromWkt(wkt)
            if geom and not geom.isEmpty():
                # Calculate tolerance based on bbox
                bbox = geom.boundingBox()
                tolerance = max(bbox.width(), bbox.height()) / 1000

                # Simplify
                simplified = geom.simplify(tolerance)
                if simplified and not simplified.isEmpty():
                    return simplified.asWkt()
        except Exception as e:
            self.log_warning(f"WKT simplification failed: {e}")

        return wkt

    def _is_geometric_filter(self, subset: str) -> bool:
        """Check if subset contains geometric filter patterns."""
        subset_upper = subset.upper()

        geometric_patterns = [
            'INTERSECTS',
            'CONTAINS',
            'WITHIN',
            'TOUCHES',
            'OVERLAPS',
            'CROSSES',
            'DISJOINT',
            'BUFFER',
            'GEOMFROMTEXT',
            'GEOMFROMGPB'
        ]

        return any(p in subset_upper for p in geometric_patterns)


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'SpatialiteExpressionBuilder',
    'USE_OGR_FALLBACK',
]
