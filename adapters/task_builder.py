# -*- coding: utf-8 -*-
"""
Task Parameter Builder for FilterMate v3.0

Provides a clean interface for building task parameters,
abstracting the complexity of synchronizing UI widgets with PROJECT_LAYERS.

This module is part of the Strangler Fig migration:
- New code should use TaskParameterBuilder
- Legacy code continues using FilterMateApp.get_task_parameters()
- Eventually, get_task_parameters() will delegate to this module

Author: FilterMate Team
Date: January 2026
"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, List, Dict, Any
from enum import Enum
import logging

if TYPE_CHECKING:
    from qgis.core import QgsVectorLayer

logger = logging.getLogger('FilterMate.TaskBuilder')


class TaskType(Enum):
    """Types of tasks that can be executed."""
    FILTER = "filter"
    UNFILTER = "unfilter"
    RESET = "reset"
    EXPORT = "export"
    ADD_LAYERS = "add_layers"
    REMOVE_LAYERS = "remove_layers"


@dataclass
class FilteringConfig:
    """
    Configuration for filtering operation.
    
    Extracted from UI widgets and PROJECT_LAYERS.
    """
    buffer_value: float = 0.0
    buffer_segments: int = 5
    buffer_type: str = "Round"
    has_geometric_predicates: bool = False
    geometric_predicates: List[str] = field(default_factory=list)
    has_layers_to_filter: bool = False
    layers_to_filter: List[str] = field(default_factory=list)
    use_centroids_source_layer: bool = False
    use_centroids_distant_layers: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for task parameters."""
        return {
            "buffer_value": self.buffer_value,
            "buffer_segments": self.buffer_segments,
            "buffer_type": self.buffer_type,
            "has_geometric_predicates": self.has_geometric_predicates,
            "geometric_predicates": self.geometric_predicates,
            "has_layers_to_filter": self.has_layers_to_filter,
            "layers_to_filter": self.layers_to_filter,
            "use_centroids_source_layer": self.use_centroids_source_layer,
            "use_centroids_distant_layers": self.use_centroids_distant_layers,
        }


@dataclass
class LayerInfo:
    """
    Information about a layer for task execution.
    """
    layer_id: str
    layer_name: str
    provider_type: str
    crs_authid: str
    geometry_type: str
    is_subset: bool = False
    table_name: str = ""
    schema: str = ""
    geometry_field: str = "geometry"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for task parameters."""
        return {
            "layer_id": self.layer_id,
            "layer_name": self.layer_name,
            "layer_provider_type": self.provider_type,
            "layer_crs_authid": self.crs_authid,
            "layer_geometry_type": self.geometry_type,
            "layer_table_name": self.table_name,
            "layer_schema": self.schema,
            "layer_geometry_field": self.geometry_field,
            "is_already_subset": self.is_subset,
        }


@dataclass
class TaskParameters:
    """
    Complete parameters for a task execution.
    
    This is the output of TaskParameterBuilder.
    """
    task_type: TaskType
    source_layer_info: Optional[LayerInfo] = None
    target_layers: List[LayerInfo] = field(default_factory=list)
    filtering_config: Optional[FilteringConfig] = None
    features: List[int] = field(default_factory=list)
    expression: str = ""
    forced_backends: Dict[str, str] = field(default_factory=dict)
    skip_source_filter: bool = False
    session_id: str = ""
    
    def to_legacy_format(self, project_layers: Dict, config_data: Dict, 
                         project: Any, plugin_dir: str) -> Dict[str, Any]:
        """
        Convert to legacy task_parameters format.
        
        This allows TaskParameters to be used with existing FilterEngineTask.
        
        Args:
            project_layers: PROJECT_LAYERS dictionary
            config_data: CONFIG_DATA dictionary
            project: QgsProject instance
            plugin_dir: Plugin directory path
            
        Returns:
            Dictionary in legacy format
        """
        if not self.source_layer_info:
            return {}
        
        # Get base parameters from PROJECT_LAYERS
        layer_id = self.source_layer_info.layer_id
        base_params = project_layers.get(layer_id, {}).copy()
        
        # Add standard fields
        base_params["plugin_dir"] = plugin_dir
        base_params["config_data"] = config_data
        base_params["project"] = project
        base_params["project_layers"] = project_layers
        
        # Build task section
        task_section = {
            "layers": [t.to_dict() for t in self.target_layers],
            "expression": self.expression,
            "skip_source_filter": self.skip_source_filter,
        }
        
        if self.features:
            task_section["features"] = self.features
        
        base_params["task"] = task_section
        
        # Add filtering config
        if self.filtering_config:
            base_params["filtering"] = self.filtering_config.to_dict()
        
        # Add forced backends at root level
        if self.forced_backends:
            base_params["forced_backends"] = self.forced_backends
        
        return base_params


class TaskParameterBuilder:
    """
    Builder for constructing TaskParameters from UI state.
    
    This provides a clean interface for controllers to build task parameters
    without directly accessing the complex PROJECT_LAYERS structure.
    
    Example:
        builder = TaskParameterBuilder(dockwidget, project_layers)
        params = builder.build_filter_params(source_layer, target_layers)
    """
    
    def __init__(
        self,
        dockwidget: Any,
        project_layers: Dict[str, Dict],
        config_data: Optional[Dict] = None
    ):
        """
        Initialize the builder.
        
        Args:
            dockwidget: FilterMateDockWidget instance
            project_layers: PROJECT_LAYERS dictionary
            config_data: Optional CONFIG_DATA dictionary
        """
        self._dockwidget = dockwidget
        self._project_layers = project_layers
        self._config_data = config_data or {}
    
    def build_filtering_config(self) -> FilteringConfig:
        """
        Build FilteringConfig from current UI state.
        
        Reads widget values directly to ensure synchronization.
        
        Returns:
            FilteringConfig with current values
        """
        dw = self._dockwidget
        config = FilteringConfig()
        
        # Buffer configuration
        if hasattr(dw, 'mQgsDoubleSpinBox_filtering_buffer_value'):
            config.buffer_value = self._clean_buffer_value(
                dw.mQgsDoubleSpinBox_filtering_buffer_value.value()
            )
        
        if hasattr(dw, 'mQgsSpinBox_filtering_buffer_segments'):
            config.buffer_segments = dw.mQgsSpinBox_filtering_buffer_segments.value()
        
        if hasattr(dw, 'comboBox_filtering_buffer_type'):
            config.buffer_type = dw.comboBox_filtering_buffer_type.currentText()
        
        # Geometric predicates
        if hasattr(dw, 'pushButton_checkable_filtering_geometric_predicates'):
            config.has_geometric_predicates = (
                dw.pushButton_checkable_filtering_geometric_predicates.isChecked()
            )
        
        if hasattr(dw, 'listWidget_filtering_geometric_predicate'):
            selected_items = dw.listWidget_filtering_geometric_predicate.selectedItems()
            config.geometric_predicates = [item.text() for item in selected_items]
        
        # Layers to filter
        if hasattr(dw, 'pushButton_checkable_filtering_layers_to_filter'):
            config.has_layers_to_filter = (
                dw.pushButton_checkable_filtering_layers_to_filter.isChecked()
            )
        
        if hasattr(dw, 'get_layers_to_filter'):
            config.layers_to_filter = dw.get_layers_to_filter()
        
        # Centroids optimization
        if hasattr(dw, 'checkBox_filtering_use_centroids_source_layer'):
            config.use_centroids_source_layer = (
                dw.checkBox_filtering_use_centroids_source_layer.isChecked()
            )
        
        if hasattr(dw, 'checkBox_filtering_use_centroids_distant_layers'):
            config.use_centroids_distant_layers = (
                dw.checkBox_filtering_use_centroids_distant_layers.isChecked()
            )
        
        return config
    
    def build_layer_info(self, layer: 'QgsVectorLayer') -> Optional[LayerInfo]:
        """
        Build LayerInfo from a QGIS layer.
        
        Args:
            layer: QgsVectorLayer instance
            
        Returns:
            LayerInfo or None if layer invalid
        """
        if layer is None or not layer.isValid():
            return None
        
        # Get from PROJECT_LAYERS if available
        layer_id = layer.id()
        stored = self._project_layers.get(layer_id, {}).get("infos", {})
        
        # Map geometry type
        geom_type_map = {
            0: 'GeometryType.Point',
            1: 'GeometryType.Line',
            2: 'GeometryType.Polygon',
            3: 'GeometryType.Unknown',
            4: 'GeometryType.Null'
        }
        
        return LayerInfo(
            layer_id=layer_id,
            layer_name=layer.name(),
            provider_type=stored.get("layer_provider_type", self._detect_provider(layer)),
            crs_authid=layer.crs().authid(),
            geometry_type=geom_type_map.get(layer.geometryType(), 'GeometryType.Unknown'),
            is_subset=bool(layer.subsetString()),
            table_name=stored.get("layer_table_name", layer.name()),
            schema=stored.get("layer_schema", ""),
            geometry_field=stored.get("layer_geometry_field", "geometry"),
        )
    
    def build_filter_params(
        self,
        source_layer: 'QgsVectorLayer',
        target_layers: List['QgsVectorLayer'],
        features: Optional[List[int]] = None,
        expression: str = ""
    ) -> Optional[TaskParameters]:
        """
        Build complete TaskParameters for a filter operation.
        
        Args:
            source_layer: Source layer for filtering
            target_layers: Target layers to filter
            features: Feature IDs (if any)
            expression: Filter expression
            
        Returns:
            TaskParameters or None if invalid
        """
        source_info = self.build_layer_info(source_layer)
        if not source_info:
            logger.warning("TaskParameterBuilder: Invalid source layer")
            return None
        
        target_infos = []
        for layer in target_layers:
            info = self.build_layer_info(layer)
            if info:
                target_infos.append(info)
        
        if not target_infos:
            logger.warning("TaskParameterBuilder: No valid target layers")
            return None
        
        filtering_config = self.build_filtering_config()
        
        # Get forced backends from dockwidget
        forced_backends = {}
        if hasattr(self._dockwidget, 'forced_backends'):
            forced_backends = self._dockwidget.forced_backends
        
        return TaskParameters(
            task_type=TaskType.FILTER,
            source_layer_info=source_info,
            target_layers=target_infos,
            filtering_config=filtering_config,
            features=features or [],
            expression=expression,
            forced_backends=forced_backends,
        )
    
    def _detect_provider(self, layer: 'QgsVectorLayer') -> str:
        """Detect provider type from layer."""
        provider = layer.providerType()
        if provider == 'postgres':
            return 'postgresql'
        elif provider == 'spatialite':
            return 'spatialite'
        elif provider == 'ogr':
            return 'ogr'
        return 'unknown'
    
    def _clean_buffer_value(self, value: float) -> float:
        """
        Clean buffer value from float precision errors.
        
        Example: 0.9999999999999999 → 1.0
        """
        # Round to 6 decimal places to clean precision errors
        rounded = round(value, 6)
        # If very close to an integer, return the integer
        if abs(rounded - round(rounded)) < 0.0000001:
            return float(round(rounded))
        return rounded
    
    def build_common_task_params(
        self, 
        features: List,
        expression: str,
        layers_to_filter: List[Dict],
        include_history: bool = False,
        session_id: str = "",
        db_file_path: str = "",
        project_uuid: str = "",
        history_manager: Any = None
    ) -> Dict[str, Any]:
        """
        Build common task parameters for filter/unfilter/reset operations.
        
        Extracted from FilterMateApp._build_common_task_params().
        
        Args:
            features: Selected features for filtering
            expression: Filter expression
            layers_to_filter: List of layer info dicts to apply filter to
            include_history: Whether to include history_manager (for unfilter)
            session_id: Session ID for multi-client isolation
            db_file_path: Database file path
            project_uuid: Project UUID
            history_manager: Optional history manager instance
            
        Returns:
            Common task parameters dictionary
        """
        # Log incoming features at DEBUG level
        feat_count = len(features) if features else 0
        logger.debug(f"build_common_task_params: {feat_count} features received, expression='{expression}'")
        
        # Deduplicate features by ID to prevent processing same feature twice
        deduplicated_features = []
        seen_ids = set()
        if features:
            for feat in features:
                if hasattr(feat, 'id'):
                    feat_id = feat.id()
                    if feat_id not in seen_ids:
                        seen_ids.add(feat_id)
                        deduplicated_features.append(feat)
                    else:
                        logger.debug(f"  Removing duplicate feature id={feat_id}")
                else:
                    # Non-QgsFeature item, keep as is
                    deduplicated_features.append(feat)
        
        if len(deduplicated_features) != feat_count:
            # Log at WARNING only if significant deduplication (>10% difference)
            if feat_count - len(deduplicated_features) > max(1, feat_count * 0.1):
                logger.warning(f"  ⚠️ Deduplicated features: {feat_count} → {len(deduplicated_features)}")
            else:
                logger.debug(f"  Deduplicated features: {feat_count} → {len(deduplicated_features)}")
            features = deduplicated_features
        
        # Log feature diagnostics
        logger.debug(f"=== build_common_task_params DIAGNOSTIC ===")
        logger.debug(f"  features count: {len(features) if features else 0}")
        if features and logger.isEnabledFor(logging.DEBUG):
            for idx, feat in enumerate(features[:3]):
                if hasattr(feat, 'id') and hasattr(feat, 'geometry'):
                    feat_id = feat.id()
                    if feat.hasGeometry():
                        bbox = feat.geometry().boundingBox()
                        logger.debug(f"  feature[{idx}]: id={feat_id}, bbox=({bbox.xMinimum():.1f},{bbox.yMinimum():.1f})-({bbox.xMaximum():.1f},{bbox.yMaximum():.1f})")
                    else:
                        logger.debug(f"  feature[{idx}]: id={feat_id}, NO GEOMETRY")
                else:
                    logger.debug(f"  feature[{idx}]: type={type(feat).__name__}")
            if len(features) > 3:
                logger.debug(f"  ... and {len(features) - 3} more features")
        logger.debug(f"  expression: '{expression}'")
        logger.debug(f"  layers_to_filter count: {len(layers_to_filter)}")
        
        # Validate that expression is a boolean filter expression, not a display expression
        validated_expression = expression
        if expression:
            # Check if expression contains comparison operators (required for boolean filter)
            comparison_operators = ['=', '>', '<', '!=', '<>', ' IN ', ' LIKE ', ' ILIKE ', 
                                   ' IS NULL', ' IS NOT NULL', ' BETWEEN ', ' NOT ', '~']
            has_comparison = any(op in expression.upper() for op in comparison_operators)
            
            if not has_comparison:
                # Expression doesn't contain comparison operators - likely a display expression
                logger.debug(f"build_common_task_params: Rejecting display expression '{expression}' - no comparison operators")
                validated_expression = ''
        
        # Store feature IDs (FIDs) for thread-safe recovery
        # QgsFeature objects can become invalid when accessed from background threads
        # FIDs allow us to refetch features from the source layer if validation fails
        feature_fids = []
        if features:
            for f in features:
                try:
                    if hasattr(f, 'id') and callable(f.id):
                        fid = f.id()
                        if fid is not None and fid >= 0:  # Valid FID
                            feature_fids.append(fid)
                except Exception as e:
                    logger.warning(f"build_common_task_params: Could not get FID from feature: {e}")
        
        # Log FIDs for diagnostic
        logger.info(f"build_common_task_params: Extracted {len(feature_fids)} FIDs from {len(features) if features else 0} features")
        if feature_fids:
            logger.info(f"  FIDs: {feature_fids[:10]}{'...' if len(feature_fids) > 10 else ''}")
        
        params = {
            "features": features,
            "feature_fids": feature_fids,  # Thread-safe FIDs for recovery
            "expression": validated_expression,
            "options": self._dockwidget.project_props.get("OPTIONS", {}) if self._dockwidget else {},
            "layers": layers_to_filter,
            "db_file_path": db_file_path,
            "project_uuid": project_uuid,
            "session_id": session_id  # For multi-client materialized view isolation
        }
        
        if include_history and history_manager:
            params["history_manager"] = history_manager
        
        # Add forced backends information from dockwidget
        if self._dockwidget and hasattr(self._dockwidget, 'forced_backends'):
            params["forced_backends"] = self._dockwidget.forced_backends
        
        return params
    
    def build_layer_management_params(
        self,
        layers: List,
        reset_flag: bool,
        project_layers: Dict,
        config_data: Dict,
        db_file_path: str = "",
        project_uuid: str = "",
        session_id: str = ""
    ) -> Dict[str, Any]:
        """
        Build parameters for layer management tasks (add/remove layers).
        
        Extracted from FilterMateApp._build_layer_management_params().
        
        Args:
            layers: List of layers to manage
            reset_flag: Whether to reset all layer variables
            project_layers: PROJECT_LAYERS dictionary
            config_data: CONFIG_DATA dictionary
            db_file_path: Database file path
            project_uuid: Project UUID
            session_id: Session ID for multi-client isolation
            
        Returns:
            Layer management task parameters dictionary
        """
        return {
            "task": {
                "layers": layers,
                "project_layers": project_layers,
                "reset_all_layers_variables_flag": reset_flag,
                "config_data": config_data,
                "db_file_path": db_file_path,
                "project_uuid": project_uuid,
                "session_id": session_id  # For multi-client materialized view isolation
            }
        }
