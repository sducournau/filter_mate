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
        # print(f"Provider: {params.provider_type}")  # DEBUG REMOVED
        # print(f"Table: {params.table_name}")  # DEBUG REMOVED
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
        stored_geom_field = infos.get("layer_geometry_field")
        if not stored_geom_field or stored_geom_field in ('NULL', 'None', ''):
            try:
                from qgis.core import QgsDataSourceUri
                uri = QgsDataSourceUri(context.source_layer.source())
                geom_col = uri.geometryColumn()
                if geom_col:
                    infos["layer_geometry_field"] = geom_col
                else:
                    # Default based on provider
                    if infos.get("layer_provider_type") == PROVIDER_POSTGRES:
                        infos["layer_geometry_field"] = 'geom'
                    else:
                        infos["layer_geometry_field"] = 'geometry'
                logger.info(f"Auto-filled layer_geometry_field='{infos['layer_geometry_field']}'")
            except Exception as e:
                infos["layer_geometry_field"] = 'geom'
                logger.warning(f"Could not detect geometry column, using 'geom': {e}")
        
        # Auto-fill primary_key_name
        if "primary_key_name" not in infos or infos["primary_key_name"] is None:
            pk_indices = context.source_layer.primaryKeyAttributes()
            if pk_indices:
                infos["primary_key_name"] = context.source_layer.fields()[pk_indices[0]].name()
            else:
                # Fallback to first field
                if context.source_layer.fields():
                    infos["primary_key_name"] = context.source_layer.fields()[0].name()
                else:
                    infos["primary_key_name"] = 'id'
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
        
        # PRIORITY 2: Check PostgreSQL availability
        # CRITICAL FIX v4.0.2 (2026-01-16): PostgreSQL layers are ALWAYS filterable via QGIS native API
        # (setSubsetString works without psycopg2). The stored postgresql_connection_available
        # flag may be stale from old data - IGNORE IT and always use native backend.
        if provider_type == PROVIDER_POSTGRES:
            # Only check context.postgresql_available (module-level flag), NOT the stored value
            if not context.postgresql_available:
                logger.warning("Source layer is PostgreSQL but POSTGRESQL_AVAILABLE=False - using OGR fallback")
                return {
                    'provider_type': PROVIDER_OGR,
                    'forced_backend': False,
                    'postgresql_fallback': True
                }
            else:
                logger.debug(f"PostgreSQL backend available via QGIS native API")
        
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
