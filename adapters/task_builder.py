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
    from qgis.core import QgsVectorLayer, QgsProject

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

        # Buffer segments: only use spinbox value if buffer_type button is checked and spinbox is valid
        if (hasattr(dw, 'pushButton_checkable_filtering_buffer_type') and
            dw.pushButton_checkable_filtering_buffer_type.isChecked() and
            hasattr(dw, 'mQgsSpinBox_filtering_buffer_segments') and
                dw.mQgsSpinBox_filtering_buffer_segments.value() >= 1):
            config.buffer_segments = dw.mQgsSpinBox_filtering_buffer_segments.value()
        else:
            config.buffer_segments = 5  # Default value

        if hasattr(dw, 'comboBox_filtering_buffer_type'):
            config.buffer_type = dw.comboBox_filtering_buffer_type.currentText()

        # Geometric predicates
        if hasattr(dw, 'pushButton_checkable_filtering_geometric_predicates'):
            config.has_geometric_predicates = (
                dw.pushButton_checkable_filtering_geometric_predicates.isChecked()
            )

        # FIX: Use comboBox_filtering_geometric_predicates (QgsCheckableComboBox) with checkedItems()
        if hasattr(dw, 'comboBox_filtering_geometric_predicates'):
            config.geometric_predicates = dw.comboBox_filtering_geometric_predicates.checkedItems()

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
        logger.debug("=== build_common_task_params DIAGNOSTIC ===")
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

    def sync_ui_to_project_layers(self, current_layer: 'QgsVectorLayer') -> Dict[str, Any]:
        """
        Synchronize UI widget values to PROJECT_LAYERS for the current layer.

        CRITICAL: UI widgets may have values that haven't propagated to PROJECT_LAYERS
        via signals. This method reads current widget values and updates PROJECT_LAYERS
        to ensure task parameters are consistent with what the user sees.

        Extracted from FilterMateApp.get_task_parameters() (SYNC blocks).

        Args:
            current_layer: The source layer being filtered

        Returns:
            Updated task_parameters for the layer, or None if layer invalid
        """
        if current_layer is None or not current_layer.isValid():
            logger.warning("sync_ui_to_project_layers: Invalid current layer")
            return None

        layer_id = current_layer.id()
        if layer_id not in self._project_layers:
            logger.warning(f"sync_ui_to_project_layers: Layer {layer_id} not in PROJECT_LAYERS")
            return None

        task_parameters = self._project_layers[layer_id]
        dw = self._dockwidget

        if dw is None:
            return task_parameters

        # Ensure filtering section exists
        if "filtering" not in task_parameters:
            task_parameters["filtering"] = {}

        # SYNC has_buffer_value (CRITICAL - must be synced for buffer to work!)
        if hasattr(dw, 'pushButton_checkable_filtering_buffer_value'):
            current_val = dw.pushButton_checkable_filtering_buffer_value.isChecked()
            stored_val = task_parameters["filtering"].get("has_buffer_value", False)
            # FIX 2026-01-21: ALWAYS log this critical value
            logger.info(f"📌 has_buffer_value: button.isChecked()={current_val}, stored={stored_val}")
            if current_val != stored_val:
                logger.info(f"SYNC has_buffer_value: {stored_val} → {current_val}")
                task_parameters["filtering"]["has_buffer_value"] = current_val
                self._project_layers[layer_id]["filtering"]["has_buffer_value"] = current_val

        # SYNC buffer_value_property (property override active state)
        if hasattr(dw, 'mPropertyOverrideButton_filtering_buffer_value_property'):
            current_val = dw.mPropertyOverrideButton_filtering_buffer_value_property.isActive()
            stored_val = task_parameters["filtering"].get("buffer_value_property", False)
            if current_val != stored_val:
                logger.info(f"SYNC buffer_value_property: {stored_val} → {current_val}")
                task_parameters["filtering"]["buffer_value_property"] = current_val
                self._project_layers[layer_id]["filtering"]["buffer_value_property"] = current_val

            # Also sync buffer_value_expression if property is active
            if current_val:
                from qgis.core import QgsProperty
                qgs_prop = dw.mPropertyOverrideButton_filtering_buffer_value_property.toProperty()
                if qgs_prop.propertyType() == QgsProperty.ExpressionBasedProperty:
                    expr = qgs_prop.asExpression()
                    stored_expr = task_parameters["filtering"].get("buffer_value_expression", "")
                    if expr != stored_expr:
                        logger.info(f"SYNC buffer_value_expression: '{stored_expr}' → '{expr}'")
                        task_parameters["filtering"]["buffer_value_expression"] = expr
                        self._project_layers[layer_id]["filtering"]["buffer_value_expression"] = expr

        # SYNC buffer_value
        if hasattr(dw, 'mQgsDoubleSpinBox_filtering_buffer_value'):
            current_val = self._clean_buffer_value(dw.mQgsDoubleSpinBox_filtering_buffer_value.value())
            stored_val = task_parameters["filtering"].get("buffer_value", 0.0)
            if current_val != stored_val:
                logger.info(f"SYNC buffer_value: {stored_val} → {current_val}")
                task_parameters["filtering"]["buffer_value"] = current_val
                self._project_layers[layer_id]["filtering"]["buffer_value"] = current_val

        # SYNC buffer_segments (only if buffer_type button is checked and spinbox is valid)
        buffer_type_checked = (
            hasattr(dw, 'pushButton_checkable_filtering_buffer_type') and
            dw.pushButton_checkable_filtering_buffer_type.isChecked()
        )
        if buffer_type_checked and hasattr(dw, 'mQgsSpinBox_filtering_buffer_segments'):
            spinbox_val = dw.mQgsSpinBox_filtering_buffer_segments.value()
            if spinbox_val >= 1:
                current_val = spinbox_val
            else:
                current_val = 5  # Default value
        else:
            current_val = 5  # Default value when not checked
        stored_val = task_parameters["filtering"].get("buffer_segments", 5)
        if current_val != stored_val:
            logger.info(f"SYNC buffer_segments: {stored_val} → {current_val}")
            task_parameters["filtering"]["buffer_segments"] = current_val
            self._project_layers[layer_id]["filtering"]["buffer_segments"] = current_val

        # SYNC buffer_type
        if hasattr(dw, 'comboBox_filtering_buffer_type'):
            current_val = dw.comboBox_filtering_buffer_type.currentText()
            stored_val = task_parameters["filtering"].get("buffer_type", "Round")
            if current_val != stored_val:
                logger.info(f"SYNC buffer_type: {stored_val} → {current_val}")
                task_parameters["filtering"]["buffer_type"] = current_val
                self._project_layers[layer_id]["filtering"]["buffer_type"] = current_val

        # SYNC use_centroids_source_layer
        if hasattr(dw, 'checkBox_filtering_use_centroids_source_layer'):
            current_val = dw.checkBox_filtering_use_centroids_source_layer.isChecked()
            stored_val = task_parameters["filtering"].get("use_centroids_source_layer", False)
            if current_val != stored_val:
                logger.info(f"SYNC use_centroids_source_layer: {stored_val} → {current_val}")
                task_parameters["filtering"]["use_centroids_source_layer"] = current_val
                self._project_layers[layer_id]["filtering"]["use_centroids_source_layer"] = current_val

        # SYNC use_centroids_distant_layers
        if hasattr(dw, 'checkBox_filtering_use_centroids_distant_layers'):
            current_val = dw.checkBox_filtering_use_centroids_distant_layers.isChecked()
            stored_val = task_parameters["filtering"].get("use_centroids_distant_layers", False)
            if current_val != stored_val:
                logger.info(f"SYNC use_centroids_distant_layers: {stored_val} → {current_val}")
                task_parameters["filtering"]["use_centroids_distant_layers"] = current_val
                self._project_layers[layer_id]["filtering"]["use_centroids_distant_layers"] = current_val

        # SYNC has_geometric_predicates
        if hasattr(dw, 'pushButton_checkable_filtering_geometric_predicates'):
            current_val = dw.pushButton_checkable_filtering_geometric_predicates.isChecked()
            stored_val = task_parameters["filtering"].get("has_geometric_predicates", False)
            # FIX 2026-01-16: ALWAYS log this critical value
            logger.info(f"📌 has_geometric_predicates: button.isChecked()={current_val}, stored={stored_val}")
            if current_val != stored_val:
                logger.info(f"SYNC has_geometric_predicates: {stored_val} → {current_val}")
                task_parameters["filtering"]["has_geometric_predicates"] = current_val
                self._project_layers[layer_id]["filtering"]["has_geometric_predicates"] = current_val

        # SYNC geometric_predicates list
        # FIX: Use comboBox_filtering_geometric_predicates (QgsCheckableComboBox) with checkedItems()
        if hasattr(dw, 'comboBox_filtering_geometric_predicates'):
            current_val = dw.comboBox_filtering_geometric_predicates.checkedItems()
            stored_val = task_parameters["filtering"].get("geometric_predicates", [])
            # FIX 2026-01-16: ALWAYS log this critical value
            logger.info(f"📌 geometric_predicates: comboBox.checkedItems()={current_val}, stored={stored_val}")
            if set(current_val) != set(stored_val):
                logger.info(f"SYNC geometric_predicates: {len(stored_val)} → {len(current_val)} items")
                task_parameters["filtering"]["geometric_predicates"] = current_val
                self._project_layers[layer_id]["filtering"]["geometric_predicates"] = current_val

        # SYNC has_layers_to_filter
        if hasattr(dw, 'pushButton_checkable_filtering_layers_to_filter'):
            current_val = dw.pushButton_checkable_filtering_layers_to_filter.isChecked()
            stored_val = task_parameters["filtering"].get("has_layers_to_filter", False)
            # FIX 2026-01-16: ALWAYS log this critical value
            logger.info(f"📌 has_layers_to_filter: button.isChecked()={current_val}, stored={stored_val}")
            if current_val != stored_val:
                logger.info(f"SYNC has_layers_to_filter: {stored_val} → {current_val}")
                task_parameters["filtering"]["has_layers_to_filter"] = current_val
                self._project_layers[layer_id]["filtering"]["has_layers_to_filter"] = current_val

        # SYNC layers_to_filter list
        if hasattr(dw, 'get_layers_to_filter'):
            current_val = dw.get_layers_to_filter()
            stored_val = task_parameters["filtering"].get("layers_to_filter", [])
            # FIX 2026-01-16: ALWAYS log this critical value
            logger.info(f"📌 layers_to_filter: get_layers_to_filter()={len(current_val)} layers, stored={len(stored_val)} layers")
            if set(current_val) != set(stored_val):
                logger.info(f"SYNC layers_to_filter: {len(stored_val)} → {len(current_val)} layers")
                task_parameters["filtering"]["layers_to_filter"] = current_val
                self._project_layers[layer_id]["filtering"]["layers_to_filter"] = current_val

        # Update is_already_subset flag
        if current_layer.subsetString() != '':
            self._project_layers[layer_id]["infos"]["is_already_subset"] = True
        else:
            self._project_layers[layer_id]["infos"]["is_already_subset"] = False

        # FIX 2026-01-16: DIAGNOSTIC - Log ALL filtering params before returning
        from qgis.core import QgsMessageLog, Qgis
        filtering = task_parameters.get("filtering", {})
        QgsMessageLog.logMessage(
            "=== sync_ui_to_project_layers FINAL STATE ===\n"
            f"  has_geometric_predicates: {filtering.get('has_geometric_predicates', False)}\n"
            f"  geometric_predicates: {filtering.get('geometric_predicates', [])}\n"
            f"  has_layers_to_filter: {filtering.get('has_layers_to_filter', False)}\n"
            f"  layers_to_filter: {len(filtering.get('layers_to_filter', []))} layers\n"
            f"  has_buffer_value: {filtering.get('has_buffer_value', False)}\n"
            f"  buffer_value: {filtering.get('buffer_value', 0.0)}\n"
            f"  buffer_value_property: {filtering.get('buffer_value_property', False)}\n"
            f"  buffer_value_expression: '{filtering.get('buffer_value_expression', '')}'\n"
            f"  use_centroids_source: {filtering.get('use_centroids_source_layer', False)}\n"
            f"  use_centroids_distant: {filtering.get('use_centroids_distant_layers', False)}",
            "FilterMate", Qgis.Info
        )

        return task_parameters

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

    def log_filtering_diagnostic(
        self,
        current_layer: 'QgsVectorLayer',
        layers_to_filter: List[Dict],
        context: str = "get_task_parameters"
    ) -> None:
        """
        Log detailed filtering diagnostic information.

        v4.7: Extracted from FilterMateApp.get_task_parameters() for God Class reduction.

        Args:
            current_layer: Source layer for filtering
            layers_to_filter: List of validated layer info dictionaries
            context: Context string for log message
        """
        layer_id = current_layer.id()
        if layer_id not in self._project_layers:
            logger.warning(f"Layer {layer_id} not in PROJECT_LAYERS for diagnostic")
            return

        filtering_props = self._project_layers[layer_id].get("filtering", {})

        logger.info("=" * 60)
        logger.info(f"🔍 GEOMETRIC FILTERING DIAGNOSTIC - {context}")
        logger.info("=" * 60)
        logger.info(f"  Source layer: {current_layer.name()}")
        logger.info(f"  has_geometric_predicates: {filtering_props.get('has_geometric_predicates', 'NOT SET')}")
        logger.info(f"  geometric_predicates: {filtering_props.get('geometric_predicates', [])}")
        logger.info(f"  has_layers_to_filter: {filtering_props.get('has_layers_to_filter', 'NOT SET')}")
        logger.info(f"  layers_to_filter (from filtering): {filtering_props.get('layers_to_filter', [])}")
        logger.info(f"  layers_to_filter (validated): {len(layers_to_filter)} layers")
        for i, layer_info in enumerate(layers_to_filter[:5]):
            logger.info(f"    {i + 1}. {layer_info.get('layer_name', 'unknown')}")
        if len(layers_to_filter) > 5:
            logger.info(f"    ... and {len(layers_to_filter) - 5} more")
        logger.info("=" * 60)

    def build_export_params(
        self,
        project_layers: Dict,
        project: 'QgsProject'
    ) -> Dict[str, Any]:
        """
        Build parameters for export task.

        v4.7: Extracted from FilterMateApp.get_task_parameters() for God Class reduction.

        IMPORTANT: Export is INDEPENDENT from "exploring" and QGIS selection.
        ===================================================================

        This method builds export parameters from:
        - LAYERS_TO_EXPORT: layers selected via checkboxes in EXPORTING tab

        Export does NOT use:
        - current_layer from exploring tab
        - selectedFeatures() or QGIS selection
        - Any data from filtering/exploring process

        The actual export (via QgsVectorFileWriter) will:
        - Respect layer's subsetString (exports filtered features if filter active)
        - Export all features if no filter is active

        Args:
            project_layers: PROJECT_LAYERS dictionary
            project: QgsProject instance

        Returns:
            Export task parameters dictionary with layers_to_export
        """
        from qgis.core import QgsVectorLayer

        layers_to_export = []
        dw = self._dockwidget

        if not dw or not hasattr(dw, 'project_props'):
            logger.warning("Cannot build export params: dockwidget or project_props missing")
            return {}

        export_layer_ids = dw.project_props.get("EXPORTING", {}).get("LAYERS_TO_EXPORT", [])

        for layer_key in export_layer_ids:
            if layer_key in project_layers:
                layers_to_export.append(project_layers[layer_key]["infos"])
            else:
                # Handle layers not in PROJECT_LAYERS but still in QGIS project
                layer = project.mapLayer(layer_key)
                if layer and isinstance(layer, QgsVectorLayer) and layer.isValid():
                    from ..infrastructure.utils.layer_utils import detect_layer_provider_type

                    geom_type_map = {
                        0: 'GeometryType.Point',
                        1: 'GeometryType.Line',
                        2: 'GeometryType.Polygon',
                        3: 'GeometryType.Unknown',
                        4: 'GeometryType.Null'
                    }
                    geom_type_str = geom_type_map.get(layer.geometryType(), 'GeometryType.Unknown')

                    # Use QgsDataSourceUri for reliable geometry column detection
                    try:
                        from qgis.core import QgsDataSourceUri
                        uri = QgsDataSourceUri(layer.source())
                        geom_field = uri.geometryColumn() or "geometry"
                    except (AttributeError, RuntimeError, KeyError):
                        geom_field = "geometry"  # Fallback default

                    layer_info = {
                        "layer_id": layer.id(),
                        "layer_name": layer.name(),
                        "layer_crs_authid": layer.crs().authid(),
                        "layer_geometry_type": geom_type_str,
                        "layer_provider_type": detect_layer_provider_type(layer),
                        "layer_table_name": layer.name(),
                        "layer_schema": "",
                        "layer_geometry_field": geom_field
                    }
                    layers_to_export.append(layer_info)
                    logger.info(f"Export: Added layer '{layer.name()}' not in PROJECT_LAYERS")

        task_params = dict(dw.project_props)
        task_params["layers"] = layers_to_export
        return {"task": task_params}

    def get_and_validate_features(
        self,
        task_name: str
    ) -> tuple:
        """
        Get and validate source features for filtering task.

        v4.7: Extracted from FilterMateApp.get_task_parameters() for God Class reduction.
        v4.0.9: Export task doesn't require selection - exports all features (with subset if active).

        Args:
            task_name: Type of task ('filter', 'unfilter', 'reset', 'export')

        Returns:
            tuple: (features, expression) or ([], "") for unfilter/reset/export

        Raises:
            ValueError: If single_selection mode has no features (for 'filter' task only)
        """
        from qgis.core import QgsMessageLog, Qgis
        from qgis.utils import iface

        dw = self._dockwidget

        # Reset, unfilter, and export don't need features validation
        if task_name in ('unfilter', 'reset', 'export'):
            logger.info(f"get_and_validate_features: task_name='{task_name}' - no features needed")
            return [], ""

        # Get features for filter operation
        logger.info("get_and_validate_features: Calling get_current_features()...")
        features, expression = dw.get_current_features()
        logger.info(f"get_and_validate_features: Returned {len(features)} features, expression='{expression}'")

        # CRITICAL CHECK: Warn if no features and no expression
        if len(features) == 0 and not expression:
            logger.warning("⚠️ NO FEATURES and NO EXPRESSION!")
            logger.warning(f"   current_exploring_groupbox: {dw.current_exploring_groupbox}")

            QgsMessageLog.logMessage(
                f"⚠️ CRITICAL: No source features selected! Groupbox: {dw.current_exploring_groupbox}",
                "FilterMate", Qgis.Warning
            )

            # ABORT in single_selection mode (FILTER ONLY)
            if dw.current_exploring_groupbox == "single_selection":
                QgsMessageLog.logMessage(
                    "   Aborting filter - single_selection mode requires a selected feature!",
                    "FilterMate", Qgis.Warning
                )
                iface.messageBar().pushWarning(
                    "FilterMate",
                    "Aucune entité sélectionnée! Le widget de sélection a perdu la feature. Re-sélectionnez une entité."
                )
                logger.warning("⚠️ ABORTING filter task - single_selection mode with no selection!")
                raise ValueError("No features in single_selection mode")
            else:
                QgsMessageLog.logMessage(
                    "   The filter will use ALL features from source layer!",
                    "FilterMate", Qgis.Warning
                )

        return features, expression

    def determine_skip_source_filter(
        self,
        task_name: str,
        task_parameters: Dict,
        expression: str
    ) -> bool:
        """
        Determine if source layer filter should be skipped.

        v4.7: Extracted from FilterMateApp.get_task_parameters() for God Class reduction.

        FIX 2026-01-21: For custom_selection:
        - Skip if expression is empty (no filter expression)
        - Skip if expression is a SIMPLE FIELD (e.g., "drop_ID") without comparison operators
        - DO NOT skip if expression contains comparison operators (=, >, <, etc.)
        - DO NOT skip if we have features from a valid filter expression

        Args:
            task_name: Type of task ('filter', 'unfilter', 'reset')
            task_parameters: Task parameters dict with task section
            expression: Original expression from get_current_features()

        Returns:
            bool: True if source filter should be skipped
        """
        # Only applies to filter operation
        if task_name != 'filter':
            return False

        dw = self._dockwidget
        current_groupbox = dw.current_exploring_groupbox

        # Single_selection and multiple_selection ALWAYS filter source layer
        # Only custom_selection might skip source filter
        if current_groupbox != "custom_selection":
            return False

        # FIX 2026-01-21: Check if expression is a SIMPLE FIELD (no comparison operators)
        # A simple field like "drop_ID" or "name" should NOT filter the source layer
        # because it's just a display field, not a filter condition
        if expression and expression.strip():
            expr_upper = expression.upper().strip()
            # Check for comparison operators - if present, it's a filter expression
            comparison_operators = ['=', '>', '<', '!', ' IN ', ' LIKE ', ' AND ', ' OR ', ' IS ', ' NOT ', ' BETWEEN ']
            has_comparison = any(op in expr_upper for op in comparison_operators)

            if not has_comparison:
                # Expression has no comparison operators - it's a simple field name
                logger.info(
                    f"FilterMate: Custom selection with simple field '{expression}' (no operators) - "
                    "will NOT filter source layer (skip_source_filter=True)"
                )
                return True

        # FIX 2026-01-21: Check if we have FEATURES - features take priority
        # If custom_selection returned features from a filter expression, use them
        features = task_parameters.get("task", {}).get("features", [])
        if features and len(features) > 0:
            logger.info(
                f"FilterMate: Custom selection has {len(features)} features from filter expression - "
                "will use them for source layer filtering"
            )
            return False  # DO filter source layer using these features

        # No features and no valid expression - skip source filter
        validated_expr = task_parameters.get("task", {}).get("expression", "")
        if not validated_expr or not validated_expr.strip():
            logger.info(
                "FilterMate: Custom selection with empty expression and no features - "
                "will use ALL features from source layer"
            )
            return True

        return False

    def validate_current_layer_for_task(
        self,
        current_layer: 'QgsVectorLayer',
        project_layers: Dict
    ) -> Optional[str]:
        """
        Validate that current layer is ready for task execution.

        v4.7: Extracted from FilterMateApp.get_task_parameters() for God Class reduction.

        Args:
            current_layer: Current layer to validate
            project_layers: PROJECT_LAYERS dictionary

        Returns:
            str: Error message if validation fails, None if OK
        """
        from ..infrastructure.utils.validation_utils import is_layer_source_available
        from qgis.utils import iface

        # Check layer validity and source availability
        if not is_layer_source_available(current_layer):
            logger.warning(
                f"FilterMate: Layer '{current_layer.name() if current_layer else 'Unknown'}' "
                "is invalid or source missing."
            )
            iface.messageBar().pushWarning(
                "FilterMate",
                "La couche sélectionnée est invalide ou sa source est introuvable. Opération annulée."
            )
            return "invalid_layer"

        # Check if layer is in PROJECT_LAYERS
        if current_layer.id() not in project_layers.keys():
            logger.warning(
                f"FilterMate: Layer '{current_layer.name()}' (id: {current_layer.id()}) "
                "not found in PROJECT_LAYERS. The layer may not have been processed yet."
            )
            iface.messageBar().pushWarning(
                "FilterMate",
                f"La couche '{current_layer.name()}' n'est pas encore initialisée. "
                "Essayez de sélectionner une autre couche puis revenez à celle-ci."
            )
            return "layer_not_initialized"

        return None  # Validation OK
