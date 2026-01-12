# -*- coding: utf-8 -*-
"""
Layer Filter Builder for FilterMate v4.6

Extracts and validates layers for geometric filtering operations.
This service handles the complex logic of:
- Building validated layer lists from user selections
- Auto-filling missing layer properties
- Detecting and logging layer registration issues

Part of the God Class reduction strategy for filter_mate_app.py.

Author: FilterMate Team
Date: January 2026
"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, List, Dict, Any, Tuple
import logging

if TYPE_CHECKING:
    from qgis.core import QgsVectorLayer, QgsProject

from ...infrastructure.utils.validation_utils import is_layer_source_available
from ...infrastructure.utils.layer_utils import detect_layer_provider_type

logger = logging.getLogger('FilterMate.LayerFilterBuilder')


@dataclass
class LayerFilterConfig:
    """Configuration for layer filter building."""
    auto_fill_missing: bool = True
    log_diagnostics: bool = True


@dataclass
class LayerValidationResult:
    """Result of layer validation."""
    layer_id: str
    layer_name: str
    is_valid: bool
    layer_info: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class LayerFilterBuilder:
    """
    Builds validated lists of layers for geometric filtering.
    
    Extracted from FilterMateApp._build_layers_to_filter() for:
    - Better testability
    - Cleaner separation of concerns
    - God Class reduction
    
    Example:
        builder = LayerFilterBuilder(project_layers, project)
        validated_layers = builder.build_layers_to_filter(source_layer)
    """
    
    def __init__(
        self,
        project_layers: Dict[str, Dict],
        project: 'QgsProject',
        config: Optional[LayerFilterConfig] = None
    ):
        """
        Initialize the builder.
        
        Args:
            project_layers: PROJECT_LAYERS dictionary
            project: QgsProject instance
            config: Optional configuration
        """
        self._project_layers = project_layers
        self._project = project
        self._config = config or LayerFilterConfig()
    
    def build_layers_to_filter(
        self,
        source_layer: 'QgsVectorLayer'
    ) -> List[Dict[str, Any]]:
        """
        Build list of layers to filter with validation.
        
        AUTO-DETECTION: Validates all selected layers, auto-fills
        missing properties where possible, and logs any issues.
        
        Args:
            source_layer: Source layer for filtering
            
        Returns:
            list: List of validated layer info dictionaries
        """
        layers_to_filter = []
        
        # Verify source layer exists in PROJECT_LAYERS
        if source_layer.id() not in self._project_layers:
            logger.warning(f"build_layers_to_filter: layer {source_layer.name()} not in PROJECT_LAYERS")
            return layers_to_filter
        
        # Get user-selected layers
        raw_layers_list = self._project_layers[source_layer.id()]["filtering"].get(
            "layers_to_filter", []
        )
        
        if self._config.log_diagnostics:
            self._log_diagnostics(source_layer, raw_layers_list)
        
        # Process each selected layer
        for layer_id in raw_layers_list:
            result = self._validate_and_build_layer_info(layer_id, source_layer.id())
            
            if result.is_valid and result.layer_info:
                layers_to_filter.append(result.layer_info)
                logger.debug(f"✓ Added layer: {result.layer_name}")
            else:
                logger.warning(f"✗ Skipped layer {result.layer_name}: {result.error}")
        
        logger.info(f"Built layers_to_filter list with {len(layers_to_filter)} layers")
        return layers_to_filter
    
    def _validate_and_build_layer_info(
        self,
        layer_id: str,
        source_layer_id: str
    ) -> LayerValidationResult:
        """
        Validate a single layer and build its info dict.
        
        Args:
            layer_id: ID of layer to validate
            source_layer_id: ID of source layer (for context)
            
        Returns:
            LayerValidationResult with validation status and info
        """
        # Check if layer is in PROJECT_LAYERS
        if layer_id not in self._project_layers:
            layer_obj = self._project.mapLayer(layer_id)
            layer_name = layer_obj.name() if layer_obj else "unknown"
            return LayerValidationResult(
                layer_id=layer_id,
                layer_name=layer_name,
                is_valid=False,
                error="Not in PROJECT_LAYERS"
            )
        
        # Get layer info copy
        layer_info = self._project_layers[layer_id]["infos"].copy()
        layer_name = layer_info.get("layer_name", layer_id[:16])
        
        # Remove stale runtime keys
        for stale_key in ['_effective_provider_type', '_postgresql_fallback', '_forced_backend']:
            layer_info.pop(stale_key, None)
        
        # Get actual layer object
        layer = self._project.mapLayer(layer_id)
        if not layer:
            return LayerValidationResult(
                layer_id=layer_id,
                layer_name=layer_name,
                is_valid=False,
                error="Layer not found in project"
            )
        
        # Check layer source availability
        if not is_layer_source_available(layer):
            return LayerValidationResult(
                layer_id=layer_id,
                layer_name=layer_name,
                is_valid=False,
                error="Invalid or source missing"
            )
        
        # Validate and auto-fill required keys
        required_keys = [
            'layer_name', 'layer_id', 'layer_provider_type',
            'primary_key_name', 'layer_geometry_field', 'layer_schema'
        ]
        
        missing_keys = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
        
        if missing_keys and self._config.auto_fill_missing:
            layer_info = self._auto_fill_layer_info(layer, layer_info, missing_keys)
            
            # Re-check for still missing keys
            still_missing = [k for k in required_keys if k not in layer_info or layer_info[k] is None]
            if still_missing:
                return LayerValidationResult(
                    layer_id=layer_id,
                    layer_name=layer_name,
                    is_valid=False,
                    error=f"Missing required keys: {still_missing}"
                )
            
            # Update PROJECT_LAYERS with auto-filled values
            update_info = {k: v for k, v in layer_info.items() 
                           if k not in ['_effective_provider_type', '_postgresql_fallback', '_forced_backend']}
            self._project_layers[layer_id]["infos"].update(update_info)
        
        return LayerValidationResult(
            layer_id=layer_id,
            layer_name=layer_name,
            is_valid=True,
            layer_info=layer_info
        )
    
    def _auto_fill_layer_info(
        self,
        layer: 'QgsVectorLayer',
        layer_info: Dict[str, Any],
        missing_keys: List[str]
    ) -> Dict[str, Any]:
        """
        Auto-fill missing layer info from QGIS layer object.
        
        Args:
            layer: QgsVectorLayer object
            layer_info: Current layer info dict
            missing_keys: List of keys that need to be filled
            
        Returns:
            Updated layer_info dict
        """
        logger.debug(f"Auto-filling missing keys for {layer.name()}: {missing_keys}")
        
        # Fill basic info
        if 'layer_name' in missing_keys or layer_info.get('layer_name') is None:
            layer_info['layer_name'] = layer.name()
        
        if 'layer_id' in missing_keys or layer_info.get('layer_id') is None:
            layer_info['layer_id'] = layer.id()
        
        # Fill geometry field
        if 'layer_geometry_field' in missing_keys or layer_info.get('layer_geometry_field') is None:
            layer_info['layer_geometry_field'] = self._detect_geometry_field(layer)
        
        # Fill provider type
        if 'layer_provider_type' in missing_keys or layer_info.get('layer_provider_type') is None:
            layer_info['layer_provider_type'] = detect_layer_provider_type(layer)
        
        # Fill schema
        if 'layer_schema' in missing_keys or layer_info.get('layer_schema') is None:
            layer_info['layer_schema'] = self._detect_schema(layer, layer_info)
        
        # Fill primary key
        if 'primary_key_name' in missing_keys or layer_info.get('primary_key_name') is None:
            layer_info['primary_key_name'] = self._detect_primary_key(layer)
        
        return layer_info
    
    def _detect_geometry_field(self, layer: 'QgsVectorLayer') -> str:
        """Detect geometry field name from layer."""
        try:
            geom_col = layer.dataProvider().geometryColumn()
            if geom_col:
                return geom_col
        except Exception:
            pass
        
        # Default by provider
        provider = layer.providerType()
        if provider == 'postgres':
            return 'geom'
        elif provider == 'spatialite':
            return 'geometry'
        return 'geom'
    
    def _detect_schema(self, layer: 'QgsVectorLayer', layer_info: Dict) -> str:
        """Detect schema from layer source."""
        provider_type = layer_info.get('layer_provider_type', '')
        
        if provider_type == 'postgresql':
            try:
                from qgis.core import QgsDataSourceUri
                source_uri = QgsDataSourceUri(layer.source())
                schema = source_uri.schema()
                if schema:
                    return schema
            except Exception:
                pass
            
            # Regex fallback
            import re
            source = layer.source()
            match = re.search(r'table="([^"]+)"\.', source)
            if match:
                return match.group(1)
            return 'public'
        
        return 'NULL'
    
    def _detect_primary_key(self, layer: 'QgsVectorLayer') -> Optional[str]:
        """Detect primary key from layer."""
        # Check declared primary key
        pk_attrs = layer.primaryKeyAttributes()
        if pk_attrs:
            field = layer.fields()[pk_attrs[0]]
            return field.name()
        
        # Look for 'id' field
        for field in layer.fields():
            if 'id' in field.name().lower():
                return field.name()
        
        # First numeric field
        for field in layer.fields():
            if field.isNumeric():
                return field.name()
        
        return None
    
    def _log_diagnostics(self, source_layer: 'QgsVectorLayer', raw_layers_list: List[str]):
        """Log diagnostic information about layer selection."""
        from qgis.core import QgsVectorLayer as QVL
        
        logger.info("=== LayerFilterBuilder DIAGNOSTIC ===")
        logger.info(f"  Source layer: {source_layer.name()} (id={source_layer.id()[:8]}...)")
        logger.info(f"  User-selected layers: {len(raw_layers_list)}")
        
        # List available layers
        all_available = []
        for key in list(self._project_layers.keys()):
            if key != source_layer.id():
                layer_obj = self._project.mapLayer(key)
                if layer_obj:
                    all_available.append((layer_obj.name(), key[:8], key))
        
        logger.info(f"  Available layers in PROJECT_LAYERS: {len(all_available)}")
        for name, key_prefix, full_key in all_available[:5]:
            is_selected = full_key in raw_layers_list
            status = "✓" if is_selected else "✗"
            logger.debug(f"    {status} {name} ({key_prefix}...)")
        
        if len(all_available) > 5:
            logger.debug(f"    ... and {len(all_available) - 5} more")
        
        # Detect layers in QGIS but not in PROJECT_LAYERS
        qgis_layers = [l for l in self._project.mapLayers().values() if isinstance(l, QVL)]
        missing = [l.name() for l in qgis_layers 
                   if l.id() not in self._project_layers and l.id() != source_layer.id()]
        
        if missing:
            logger.warning(f"  ⚠️ Layers in QGIS but not in PROJECT_LAYERS: {missing[:3]}")
        
        logger.info("=== END DIAGNOSTIC ===")
