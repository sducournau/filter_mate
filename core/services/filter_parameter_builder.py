# -*- coding: utf-8 -*-
"""
FilterParameterBuilder Service

EPIC-1 Phase 14.4: Extracted from FilterTask._initialize_source_filtering_parameters()

This service initializes all parameters needed for source layer filtering, handling:
- Auto-filling missing layer metadata from source layer
- Provider type detection and PostgreSQL fallback
- Schema validation for PostgreSQL layers
- Filtering configuration extraction (combine operators, old subset)

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase 14.4)
"""

import logging
import re
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field

logger = logging.getLogger('FilterMate.Core.Services.FilterParameterBuilder')


# =============================================================================
# Constants
# =============================================================================

PROVIDER_POSTGRES = 'postgresql'
PROVIDER_SPATIALITE = 'spatialite'
PROVIDER_OGR = 'ogr'

REQUIRED_INFO_KEYS = [
    "layer_provider_type",
    "layer_name",
    "layer_id",
    "layer_geometry_field",
    "primary_key_name"
]


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class FilterParameters:
    """Result of filter parameter initialization."""
    # Basic layer info
    provider_type: str
    layer_name: str
    layer_id: str
    table_name: str
    schema: str
    geometry_field: str
    primary_key_name: str
    
    # Provider detection flags
    forced_backend: bool = False
    postgresql_fallback: bool = False
    
    # Filtering configuration
    has_combine_operator: bool = False
    source_layer_combine_operator: str = "AND"
    other_layers_combine_operator: str = "AND"
    old_subset: str = ""
    field_names: List[str] = field(default_factory=list)
    
    # Auto-filled info dict (for reference)
    infos: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParameterBuilderContext:
    """Context for parameter building."""
    task_parameters: Dict[str, Any]
    source_layer: Any  # QgsVectorLayer
    postgresql_available: bool = True
    detect_provider_fn: Optional[Callable] = None
    sanitize_subset_fn: Optional[Callable] = None


# =============================================================================
# FilterParameterBuilder Service
# =============================================================================

class FilterParameterBuilder:
    """
    Service for building filter parameters from task parameters and source layer.
    
    This service extracts the initialization logic from FilterTask,
    making it testable and reusable.
    
    Example:
        builder = FilterParameterBuilder()
        params = builder.build(context)
      
      
    """
    
    def build(self, context: ParameterBuilderContext) -> FilterParameters:
        """
        Build filter parameters from context.
        
        Args:
            context: Builder context with task parameters and source layer
            
        Returns:
            FilterParameters with all initialized values
        """
        infos = context.task_parameters.get("infos", {}).copy()
        
        # Step 1: Auto-fill missing metadata
        self._auto_fill_metadata(infos, context)
        
        # Step 2: Validate required keys
        self._validate_required_keys(infos)
        
        # Step 3: Determine effective provider type
        provider_info = self._determine_provider_type(infos, context)
        
        # Step 4: Validate schema for PostgreSQL
        schema = self._validate_schema(infos, context, provider_info['provider_type'])
        
        # Step 5: Extract basic parameters
        table_name = infos.get("layer_table_name") or infos["layer_name"]
        
        # Step 6: Extract filtering configuration
        filtering_config = self._extract_filtering_config(context, infos)
        
        # Build result
        return FilterParameters(
            provider_type=provider_info['provider_type'],
            layer_name=infos["layer_name"],
            layer_id=infos["layer_id"],
            table_name=table_name,
            schema=schema,
            geometry_field=infos["layer_geometry_field"],
            primary_key_name=infos["primary_key_name"],
            forced_backend=provider_info['forced_backend'],
            postgresql_fallback=provider_info['postgresql_fallback'],
            has_combine_operator=filtering_config['has_combine_operator'],
            source_layer_combine_operator=filtering_config['source_layer_combine_operator'],
            other_layers_combine_operator=filtering_config['other_layers_combine_operator'],
            old_subset=filtering_config['old_subset'],
            field_names=filtering_config['field_names'],
            infos=infos
        )
    
    def _auto_fill_metadata(
        self,
        infos: Dict[str, Any],
        context: ParameterBuilderContext
    ) -> None:
        """Auto-fill missing metadata from source layer."""
        if not context.source_layer:
            return
        
        # Auto-fill layer_name
        if "layer_name" not in infos or infos["layer_name"] is None:
            infos["layer_name"] = context.source_layer.name()
            logger.info(f"Auto-filled layer_name='{infos['layer_name']}'")
        
        # Auto-fill layer_id
        if "layer_id" not in infos or infos["layer_id"] is None:
            infos["layer_id"] = context.source_layer.id()
            logger.info(f"Auto-filled layer_id='{infos['layer_id']}'")
        
        # Auto-fill layer_provider_type
        if "layer_provider_type" not in infos or infos["layer_provider_type"] is None:
            if context.detect_provider_fn:
                detected_type = context.detect_provider_fn(context.source_layer)
                infos["layer_provider_type"] = detected_type
                logger.debug(f"Auto-filled layer_provider_type='{detected_type}'")
            else:
                infos["layer_provider_type"] = 'unknown'
        
        # Auto-fill layer_geometry_field
        # FIX v4.0.7 (2026-01-16): Use QgsDataSourceUri directly (more reliable)
        # Also check for string "NULL" which may be stored from stale config
        # FIX v4.2.15 (2026-01-22): Query geometry_columns for PostgreSQL when URI is empty
        # FIX v4.4.2 (2026-01-25): ALWAYS detect geometry column for PostgreSQL
        # Don't trust stored values like 'geom' - they may be incorrect defaults
        stored_geom_field = infos.get("layer_geometry_field")
        needs_detection = (
            not stored_geom_field or 
            stored_geom_field in ('NULL', 'None', '', 'geom', 'geometry')
        )
        if needs_detection:
            try:
                from qgis.core import QgsDataSourceUri
                uri = QgsDataSourceUri(context.source_layer.source())
                geom_col = uri.geometryColumn()
                if geom_col:
                    infos["layer_geometry_field"] = geom_col
                    logger.info(f"Detected geometry column from URI: '{geom_col}'")
                else:
                    # FIX v4.2.15: Query PostgreSQL geometry_columns catalog when URI is empty
                    if infos.get("layer_provider_type") == PROVIDER_POSTGRES:
                        pg_geom_col = self._query_postgresql_geometry_column(
                            context.source_layer,
                            uri.schema() or 'public',
                            uri.table()
                        )
                        if pg_geom_col:
                            infos["layer_geometry_field"] = pg_geom_col
                            logger.info(
                                f"Detected geometry column from PostgreSQL catalog: "
                                f"'{pg_geom_col}'"
                            )
                        else:
                            # Last resort: use stored value or hardcoded default
                            infos["layer_geometry_field"] = stored_geom_field or 'geom'
                            logger.warning(
                                "Could not detect geometry column from PostgreSQL "
                                f"catalog, using '{infos['layer_geometry_field']}'"
                            )
                    else:
                        infos["layer_geometry_field"] = stored_geom_field or 'geometry'
                logger.info(
                    f"Auto-filled layer_geometry_field='{infos['layer_geometry_field']}'"
                )
            except Exception as e:
                infos["layer_geometry_field"] = stored_geom_field or 'geom'
                logger.warning(f"Could not detect geometry column: {e}")
        
        # Auto-fill primary_key_name
        if "primary_key_name" not in infos or infos["primary_key_name"] is None:
            from infrastructure.utils.layer_utils import get_primary_key_name
            infos["primary_key_name"] = get_primary_key_name(context.source_layer) or 'id'
            logger.info(f"Auto-filled primary_key_name='{infos['primary_key_name']}'")
        
        # Auto-fill layer_schema (empty for non-PostgreSQL)
        if "layer_schema" not in infos or infos["layer_schema"] is None:
            if infos.get("layer_provider_type") == PROVIDER_POSTGRES:
                source = context.source_layer.source()
                match = re.search(r'table="([^"]+)"\.', source)
                if match:
                    infos["layer_schema"] = match.group(1)
                else:
                    infos["layer_schema"] = 'public'
            else:
                infos["layer_schema"] = ''
            logger.info(f"Auto-filled layer_schema='{infos['layer_schema']}'")
    
    def _query_postgresql_geometry_column(
        self,
        layer,
        schema: str,
        table: str
    ) -> Optional[str]:
        """
        Query PostgreSQL geometry_columns catalog to find the geometry column name.
        
        FIX v4.2.15 (2026-01-22): Added to handle cases where
        QgsDataSourceUri.geometryColumn() returns empty (e.g., for some 
        PostgreSQL views or layers with non-standard URIs).
        
        Args:
            layer: QGIS vector layer (PostgreSQL)
            schema: Schema name (e.g., 'public')
            table: Table name (e.g., 'commune')
            
        Returns:
            str: Geometry column name, or None if not found
        """
        try:
            # Import here to avoid circular imports and optional dependency
            from ...infrastructure.utils import get_datasource_connexion_from_layer
            
            conn, source_uri = get_datasource_connexion_from_layer(layer)
            if conn is None:
                logger.debug(
                    "No PostgreSQL connection for geometry column detection"
                )
                return None
            
            cursor = None
            try:
                cursor = conn.cursor()
                # Query geometry_columns view (works for tables and views)
                cursor.execute("""
                    SELECT f_geometry_column 
                    FROM geometry_columns 
                    WHERE f_table_schema = %s AND f_table_name = %s
                    LIMIT 1
                """, (schema, table))
                
                result = cursor.fetchone()
                if result and result[0]:
                    logger.debug(
                        f"Found geometry column '{result[0]}' from catalog"
                    )
                    return result[0]
                
                # Fallback: Query geography_columns for geography types
                cursor.execute("""
                    SELECT f_geography_column 
                    FROM geography_columns 
                    WHERE f_table_schema = %s AND f_table_name = %s
                    LIMIT 1
                """, (schema, table))
                
                result = cursor.fetchone()
                if result and result[0]:
                    logger.debug(
                        f"Found geography column '{result[0]}' from catalog"
                    )
                    return result[0]
                    
                logger.debug(
                    f"No geometry column found in catalog for {schema}.{table}"
                )
                return None
                
            finally:
                if cursor:
                    cursor.close()
                # Note: Don't close connection - managed by connection pool
                
        except Exception as e:
            logger.debug(f"Error querying PostgreSQL geometry column: {e}")
            return None
    
    def _validate_required_keys(self, infos: Dict[str, Any]) -> None:
        """Validate that all required keys exist."""
        missing_keys = [
            k for k in REQUIRED_INFO_KEYS 
            if k not in infos or infos[k] is None
        ]
        
        if missing_keys:
            error_msg = f"task_parameters['infos'] missing required keys: {missing_keys}"
            logger.error(error_msg)
            raise KeyError(error_msg)
    
    def _determine_provider_type(
        self,
        infos: Dict[str, Any],
        context: ParameterBuilderContext
    ) -> Dict[str, Any]:
        """
        Determine effective provider type.
        
        Returns:
            Dict with 'provider_type', 'forced_backend', 'postgresql_fallback'
        """
        provider_type = infos["layer_provider_type"]
        forced_backend = False
        postgresql_fallback = False
        
        # PRIORITY 1: Check if backend is forced
        forced_backends = context.task_parameters.get('forced_backends', {})
        source_layer_id = infos.get("layer_id")
        forced = forced_backends.get(source_layer_id) if source_layer_id else None
        
        if forced:
            logger.debug(f"🔒 Source layer: Using FORCED backend '{forced}'")
            return {
                'provider_type': forced,
                'forced_backend': True,
                'postgresql_fallback': False
            }
        
        # PRIORITY 2: PostgreSQL layers ALWAYS use PostgreSQL backend
        # FIX v4.1.4 (2026-01-21): PostgreSQL layers are ALWAYS filterable via QGIS native API
        # (setSubsetString works without psycopg2). NEVER fall back to OGR.
        # psycopg2 is only needed for advanced features (materialized views, connection pooling).
        if provider_type == PROVIDER_POSTGRES:
            if not context.postgresql_available:
                logger.info("PostgreSQL layer: using QGIS native API (psycopg2 not available for advanced features)")
            else:
                logger.debug("PostgreSQL backend: full functionality with psycopg2")
            # ALWAYS return PostgreSQL - never fallback to OGR
        
        return {
            'provider_type': provider_type,
            'forced_backend': False,
            'postgresql_fallback': False
        }
    
    def _validate_schema(
        self,
        infos: Dict[str, Any],
        context: ParameterBuilderContext,
        provider_type: str
    ) -> str:
        """Validate and return schema for PostgreSQL layers."""
        stored_schema = infos.get("layer_schema", "")
        
        if provider_type != PROVIDER_POSTGRES or not context.source_layer:
            return stored_schema
        
        try:
            from qgis.core import QgsDataSourceUri
            source_uri = QgsDataSourceUri(context.source_layer.source())
            detected_schema = source_uri.schema()
            
            if detected_schema:
                if stored_schema != detected_schema:
                    logger.info(f"Schema mismatch: stored='{stored_schema}', actual='{detected_schema}'")
                    logger.info(f"Using actual schema: '{detected_schema}'")
                return detected_schema
            elif stored_schema and stored_schema != 'NULL':
                return stored_schema
            else:
                logger.info("No schema detected, using default: 'public'")
                return 'public'
        except Exception as e:
            logger.warning(f"Could not detect schema from layer source: {e}")
            return stored_schema if stored_schema and stored_schema != 'NULL' else 'public'
    
    def _extract_filtering_config(
        self,
        context: ParameterBuilderContext,
        infos: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract filtering configuration."""
        filtering_params = context.task_parameters.get("filtering", {})
        
        # Extract combine operators
        has_combine_operator = filtering_params.get("has_combine_operator", False)
        
        source_combine_op = "AND"
        other_combine_op = "AND"
        
        if has_combine_operator:
            source_combine_op = filtering_params.get("source_layer_combine_operator", "AND") or "AND"
            other_combine_op = filtering_params.get("other_layers_combine_operator", "AND") or "AND"
        
        # Extract field names
        primary_key_name = infos["primary_key_name"]
        field_names = []
        
        if context.source_layer:
            field_names = [
                field.name() 
                for field in context.source_layer.fields()
                if field.name() != primary_key_name
            ]
        
        # Extract old subset
        old_subset = ""
        if context.source_layer and context.source_layer.subsetString():
            old_subset_raw = context.source_layer.subsetString()
            
            if context.sanitize_subset_fn:
                old_subset = context.sanitize_subset_fn(old_subset_raw)
            else:
                old_subset = old_subset_raw
            
            table_name = infos.get("layer_table_name") or infos["layer_name"]
            logger.info(f"FilterMate: Existing filter detected on {table_name}: {old_subset[:100]}...")
        
        return {
            'has_combine_operator': has_combine_operator,
            'source_layer_combine_operator': source_combine_op,
            'other_layers_combine_operator': other_combine_op,
            'old_subset': old_subset,
            'field_names': field_names
        }


# =============================================================================
# Factory Function
# =============================================================================

def create_filter_parameter_builder() -> FilterParameterBuilder:
    """
    Factory function to create a FilterParameterBuilder.
    
    Returns:
        FilterParameterBuilder instance
    """
    return FilterParameterBuilder()


# =============================================================================
# Convenience Function for Direct Use
# =============================================================================

def build_filter_parameters(
    task_parameters: Dict[str, Any],
    source_layer: Any,
    postgresql_available: bool = True,
    detect_provider_fn: Optional[Callable] = None,
    sanitize_subset_fn: Optional[Callable] = None
) -> FilterParameters:
    """
    Build filter parameters.
    
    Convenience function that creates a FilterParameterBuilder and builds parameters.
    
    Args:
        task_parameters: Task parameters dict
        source_layer: QgsVectorLayer instance
        postgresql_available: Whether PostgreSQL/psycopg2 is available
        detect_provider_fn: Function to detect provider type from layer
        sanitize_subset_fn: Function to sanitize subset strings
        
    Returns:
        FilterParameters result
    """
    context = ParameterBuilderContext(
        task_parameters=task_parameters,
        source_layer=source_layer,
        postgresql_available=postgresql_available,
        detect_provider_fn=detect_provider_fn,
        sanitize_subset_fn=sanitize_subset_fn
    )
    
    builder = create_filter_parameter_builder()
    return builder.build(context)
