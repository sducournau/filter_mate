# -*- coding: utf-8 -*-
"""
LayerOrganizer Service

EPIC-1 Phase 14.3: Extracted from FilterTask._organize_layers_to_filter()

This service organizes layers to be filtered by provider type, handling:
- Provider type detection and validation
- PostgreSQL availability fallback to OGR
- Layer resolution by name and ID
- SIP deletion detection
- Grouping layers by provider type

Author: FilterMate Team
Created: January 2026 (EPIC-1 Phase 14.3)
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field

logger = logging.getLogger('FilterMate.Core.Services.LayerOrganizer')


# =============================================================================
# Constants
# =============================================================================

PROVIDER_POSTGRES = 'postgresql'
PROVIDER_SPATIALITE = 'spatialite'
PROVIDER_OGR = 'ogr'

# Keys to remove from layer props to avoid stale data between executions
STALE_RUNTIME_KEYS = ['_effective_provider_type', '_postgresql_fallback', '_forced_backend']


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class OrganizedLayers:
    """Result of layer organization."""
    layers_by_provider: Dict[str, List[Tuple[Any, Dict]]] = field(default_factory=dict)
    layers_count: int = 0
    provider_list: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    not_found_layers: List[str] = field(default_factory=list)


@dataclass
class LayerOrganizationContext:
    """Context for layer organization."""
    task_action: str
    task_parameters: Dict[str, Any]
    project: Any  # QgsProject
    postgresql_available: bool = True
    forced_backends: Dict[str, str] = field(default_factory=dict)
    detect_provider_fn: Optional[Callable] = None
    is_valid_layer_fn: Optional[Callable] = None
    is_sip_deleted_fn: Optional[Callable] = None


# =============================================================================
# LayerOrganizer Service
# =============================================================================

class LayerOrganizer:
    """
    Service for organizing layers by provider type.
    
    This service extracts the layer organization logic from FilterTask,
    making it testable and reusable.
    
    Example:
        organizer = LayerOrganizer()
        result = organizer.organize(context)
        for provider, layers in result.layers_by_provider.items():
            print(f"{provider}: {len(layers)} layers")
    """
    
    def __init__(self, log_to_qgis: bool = True):
        """
        Initialize LayerOrganizer.
        
        Args:
            log_to_qgis: Whether to log messages to QGIS message panel
        """
        self._log_to_qgis = log_to_qgis
        self._qgs_message_log = None
        self._qgis_level = None
        
        if log_to_qgis:
            try:
                from qgis.core import QgsMessageLog, Qgis
                self._qgs_message_log = QgsMessageLog
                self._qgis_level = Qgis
            except ImportError:
                self._log_to_qgis = False
    
    def organize(self, context: LayerOrganizationContext) -> OrganizedLayers:
        """
        Organize layers by provider type.
        
        Args:
            context: Organization context with task parameters and project
            
        Returns:
            OrganizedLayers with layers grouped by provider
        """
        result = OrganizedLayers()
        
        logger.info(f"🔍 LayerOrganizer.organize() called for action: {context.task_action}")
        
        # Get layer parameters
        filtering_params = context.task_parameters.get("filtering", {})
        task_params = context.task_parameters.get("task", {})
        
        has_layers_to_filter = filtering_params.get("has_layers_to_filter", False)
        layers_list = task_params.get("layers", [])
        has_layers_in_params = len(layers_list) > 0
        
        logger.info(f"  has_layers_to_filter: {has_layers_to_filter}")
        logger.info(f"  task['layers'] count: {len(layers_list)}")
        
        # Early exit for filter action with no layers
        if context.task_action == 'filter' and not has_layers_in_params:
            logger.info("  ℹ️ No layers in task params - skipping organization")
            return result
        
        # Get forced backends
        forced_backends = context.task_parameters.get('forced_backends', {}) or context.forced_backends
        
        # Process each layer
        for layer_props_original in layers_list:
            layer_result = self._process_single_layer(
                layer_props_original,
                context,
                forced_backends,
                result
            )
            
            if layer_result:
                provider_type, layer, layer_props = layer_result
                
                # Add to result
                if provider_type not in result.layers_by_provider:
                    result.layers_by_provider[provider_type] = []
                
                result.layers_by_provider[provider_type].append([layer, layer_props])
                result.layers_count += 1
                logger.info(f"    ✓ Added to filter list (total: {result.layers_count})")
        
        # Build provider list
        result.provider_list = list(result.layers_by_provider.keys())
        
        # Log summary
        self._log_summary(result, len(layers_list))
        
        return result
    
    def _process_single_layer(
        self,
        layer_props_original: Dict[str, Any],
        context: LayerOrganizationContext,
        forced_backends: Dict[str, str],
        result: OrganizedLayers
    ) -> Optional[Tuple[str, Any, Dict]]:
        """
        Process a single layer for organization.
        
        Returns:
            Tuple of (provider_type, layer, layer_props) or None if layer not found
        """
        # Create copy to avoid modifying original
        layer_props = layer_props_original.copy()
        
        # Remove stale runtime keys
        for stale_key in STALE_RUNTIME_KEYS:
            layer_props.pop(stale_key, None)
        
        provider_type = layer_props.get("layer_provider_type", "unknown")
        layer_name = layer_props.get("layer_name", "unknown")
        layer_id = layer_props.get("layer_id", "unknown")
        
        self._log_qgis(f"📂 Organizing layer: {layer_name} ({provider_type})", "Info")
        logger.debug(f"  📋 Layer '{layer_name}' initial provider_type='{provider_type}'")
        
        # Determine effective provider type
        provider_type = self._determine_effective_provider(
            layer_props,
            provider_type,
            layer_name,
            layer_id,
            context,
            forced_backends
        )
        
        logger.info(f"  Processing layer: {layer_name} ({provider_type}), id={layer_id}")
        
        # Resolve layer from project
        layer = self._resolve_layer(layer_props, layer_name, layer_id, context, result)
        
        if layer is None:
            result.not_found_layers.append(layer_name)
            return None
        
        # FIX v4.0.3 (2026-01-16): Add layer instance to layer_props for auto-detection of geometry column
        # The backend needs access to the QgsVectorLayer to detect the actual geometry column name
        # when the stored value is invalid (e.g., "NULL")
        layer_props["layer"] = layer
        
        # FIX v4.0.3 (2026-01-16): Auto-detect geometry column if stored value is invalid
        stored_geom_field = layer_props.get("layer_geometry_field")
        if not stored_geom_field or stored_geom_field in ('NULL', 'None', '', None):
            try:
                # Try to get geometry column from QGIS layer
                detected_geom = layer.dataProvider().geometryColumn()
                if detected_geom:
                    layer_props["layer_geometry_field"] = detected_geom
                    logger.info(f"  ✓ Auto-detected geometry column for {layer_name}: '{detected_geom}'")
                else:
                    # Try from URI
                    from qgis.core import QgsDataSourceUri
                    uri = QgsDataSourceUri(layer.source())
                    detected_geom = uri.geometryColumn()
                    if detected_geom:
                        layer_props["layer_geometry_field"] = detected_geom
                        logger.info(f"  ✓ Auto-detected geometry column from URI for {layer_name}: '{detected_geom}'")
                    else:
                        # Final fallback
                        layer_props["layer_geometry_field"] = 'geom'
                        logger.warning(f"  ⚠️ Using fallback geometry column 'geom' for {layer_name}")
            except Exception as e:
                layer_props["layer_geometry_field"] = 'geom'
                logger.warning(f"  ⚠️ Could not auto-detect geometry column for {layer_name}: {e}, using 'geom'")
        
        return provider_type, layer, layer_props
    
    def _determine_effective_provider(
        self,
        layer_props: Dict[str, Any],
        provider_type: str,
        layer_name: str,
        layer_id: str,
        context: LayerOrganizationContext,
        forced_backends: Dict[str, str]
    ) -> str:
        """Determine the effective provider type for a layer."""
        
        # PRIORITY 1: Check if backend is forced by user
        forced_backend = forced_backends.get(layer_id)
        if forced_backend:
            logger.info(f"  🔒 Using FORCED backend '{forced_backend}' for layer '{layer_name}'")
            layer_props["_effective_provider_type"] = forced_backend
            layer_props["_forced_backend"] = True
            return forced_backend
        
        # PRIORITY 2: Check PostgreSQL availability
        # CRITICAL FIX v4.0.2 (2026-01-16): PostgreSQL layers are ALWAYS filterable via QGIS native API
        # (setSubsetString works without psycopg2). The stored postgresql_connection_available
        # flag may be stale from old data - IGNORE IT and always use native backend.
        # psycopg2 is only needed for ADVANCED features (materialized views, indexes).
        if provider_type == PROVIDER_POSTGRES:
            # FIX 2026-01-16: Log diagnostic
            logger.info(f"  🔍 PostgreSQL layer check: '{layer_name}'")
            logger.info(f"     - context.postgresql_available = {context.postgresql_available}")
            
            # Only check context.postgresql_available (module-level flag), NOT the stored value
            if not context.postgresql_available:
                logger.warning(f"  ⚠️ PostgreSQL layer '{layer_name}' - CONVERTED TO OGR (postgresql_available=False)")
                logger.warning(f"     → This will prevent PostgreSQL geometry from being prepared!")
                layer_props["_effective_provider_type"] = PROVIDER_OGR
                layer_props["_postgresql_fallback"] = True
                return PROVIDER_OGR
            else:
                # Force postgresql_connection_available to True for runtime consistency
                layer_props["postgresql_connection_available"] = True
                logger.info(f"  ✓ PostgreSQL layer '{layer_name}': using native backend (QGIS API)")
                logger.debug(f"  PostgreSQL layer '{layer_name}': using native backend (QGIS API)")
        
        # PRIORITY 3: Detect provider from actual layer
        if context.detect_provider_fn and context.is_valid_layer_fn:
            layer_by_id = context.project.mapLayer(layer_id)
            if layer_by_id and context.is_valid_layer_fn(layer_by_id):
                detected_provider = context.detect_provider_fn(layer_by_id)
                if detected_provider != provider_type and detected_provider != 'unknown':
                    logger.warning(
                        f"  ⚠️ Provider type mismatch for '{layer_name}': "
                        f"stored='{provider_type}', detected='{detected_provider}'"
                    )
                    layer_props["layer_provider_type"] = detected_provider
                    return detected_provider
        
        return provider_type
    
    def _resolve_layer(
        self,
        layer_props: Dict[str, Any],
        layer_name: str,
        layer_id: str,
        context: LayerOrganizationContext,
        result: OrganizedLayers
    ) -> Optional[Any]:
        """Resolve layer from project by name or ID."""
        
        is_valid = context.is_valid_layer_fn or (lambda x: True)
        is_sip_deleted = context.is_sip_deleted_fn or (lambda x: False)
        
        # Try to find by name first
        layers_by_name = context.project.mapLayersByName(layer_name)
        logger.debug(f"    Found {len(layers_by_name)} layers by name '{layer_name}'")
        
        for layer in layers_by_name:
            if is_sip_deleted(layer):
                logger.debug(f"    Skipping sip-deleted layer")
                continue
            if layer.id() == layer_id:
                if is_valid(layer):
                    return layer
                else:
                    logger.warning(f"    Layer '{layer_name}' found but is_valid_layer=False!")
                    self._log_qgis(f"⚠️ Layer invalid: {layer_name}", "Warning")
        
        # Fallback: try by ID only
        logger.debug(f"    Layer not found by name, trying by ID...")
        layer_by_id = context.project.mapLayer(layer_id)
        
        if layer_by_id:
            if is_valid(layer_by_id):
                try:
                    logger.info(f"    Found layer by ID (name: '{layer_by_id.name()}')")
                    layer_props["layer_name"] = layer_by_id.name()
                    return layer_by_id
                except RuntimeError:
                    logger.warning(f"    Layer {layer_id} became invalid during access")
            else:
                logger.warning(f"    Layer found by ID but is_valid_layer=False!")
                self._log_qgis(f"⚠️ Layer invalid (by ID): {layer_name}", "Warning")
        else:
            logger.warning(f"    Layer not found by ID: {layer_id[:16]}...")
        
        # Layer not found
        logger.warning(f"    ⚠️ Layer not found in project: {layer_name}")
        self._log_qgis(f"⚠️ Layer not found: {layer_name} (id: {layer_id[:16]}...)", "Warning")
        
        # Log available layer IDs for debugging
        all_layer_ids = list(context.project.mapLayers().keys())
        logger.debug(f"    Available layer IDs: {all_layer_ids[:10]}{'...' if len(all_layer_ids) > 10 else ''}")
        
        return None
    
    def _log_summary(self, result: OrganizedLayers, input_count: int) -> None:
        """Log organization summary."""
        organized_count = result.layers_count
        
        logger.info(f"  📊 Final organized layers count: {organized_count}, providers: {result.provider_list}")
        
        if organized_count < input_count:
            self._log_qgis(
                f"⚠️ Only {organized_count}/{input_count} distant layers found!",
                "Warning"
            )
            result.warnings.append(f"Only {organized_count}/{input_count} layers found")
        else:
            self._log_qgis(
                f"✓ {organized_count} distant layers organized for filtering",
                "Info"
            )
        
        if result.layers_count > 0:
            layer_summary = [
                (layer.name(), provider) 
                for provider, layers_list in result.layers_by_provider.items() 
                for layer, props in layers_list
            ]
            logger.info(f"  ✓ Layers organized: {layer_summary}")
    
    def _log_qgis(self, message: str, level: str = "Info") -> None:
        """Log message to QGIS message panel if available."""
        if self._log_to_qgis and self._qgs_message_log:
            qgis_level = getattr(self._qgis_level, level, self._qgis_level.Info)
            self._qgs_message_log.logMessage(message, "FilterMate", qgis_level)


# =============================================================================
# Factory Function
# =============================================================================

def create_layer_organizer(log_to_qgis: bool = True) -> LayerOrganizer:
    """
    Factory function to create a LayerOrganizer.
    
    Args:
        log_to_qgis: Whether to log to QGIS message panel
        
    Returns:
        LayerOrganizer instance
    """
    return LayerOrganizer(log_to_qgis=log_to_qgis)


# =============================================================================
# Convenience Function for Direct Use
# =============================================================================

def organize_layers_for_filtering(
    task_action: str,
    task_parameters: Dict[str, Any],
    project: Any,
    postgresql_available: bool = True,
    detect_provider_fn: Optional[Callable] = None,
    is_valid_layer_fn: Optional[Callable] = None,
    is_sip_deleted_fn: Optional[Callable] = None
) -> OrganizedLayers:
    """
    Organize layers for filtering.
    
    Convenience function that creates a LayerOrganizer and runs organization.
    
    Args:
        task_action: Action being performed ('filter', 'unfilter', 'reset')
        task_parameters: Task parameters dict
        project: QgsProject instance
        postgresql_available: Whether PostgreSQL/psycopg2 is available
        detect_provider_fn: Function to detect provider type from layer
        is_valid_layer_fn: Function to check if layer is valid
        is_sip_deleted_fn: Function to check if layer is SIP-deleted
        
    Returns:
        OrganizedLayers result
    """
    context = LayerOrganizationContext(
        task_action=task_action,
        task_parameters=task_parameters,
        project=project,
        postgresql_available=postgresql_available,
        detect_provider_fn=detect_provider_fn,
        is_valid_layer_fn=is_valid_layer_fn,
        is_sip_deleted_fn=is_sip_deleted_fn
    )
    
    organizer = create_layer_organizer(log_to_qgis=True)
    return organizer.organize(context)
