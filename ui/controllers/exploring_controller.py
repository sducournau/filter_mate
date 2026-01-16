"""
FilterMate Exploring Controller.

Controller for the Exploring tab, managing layer selection, field selection,
feature listing, and spatial navigation (flash, zoom, identify).
"""
from typing import Optional, List, Dict, Any, Tuple
import logging

try:
    from qgis.core import (
        QgsVectorLayer,
        QgsProject,
        QgsFeature,
        QgsFeatureRequest,
        QgsRectangle,
        QgsExpression
    )
    from qgis.PyQt.QtCore import pyqtSignal, QObject
    from qgis.PyQt.QtGui import QColor
    from qgis.utils import iface
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    pyqtSignal = None
    QObject = object
    QColor = None

from .base_controller import BaseController
from .mixins.layer_selection_mixin import LayerSelectionMixin
from ...adapters.layer_validator import LayerValidator
from ...adapters.layer_validator import is_valid_layer

logger = logging.getLogger(__name__)


class ExploringController(BaseController, LayerSelectionMixin):
    """
    Controller for the Exploring tab.

    Manages:
    - Layer selection and field selection
    - Feature list population with caching
    - Spatial navigation (flash, zoom, identify)
    - Multiple feature selection

    The exploring tab allows users to browse layer data and
    navigate to specific features on the map.
    """

    def __init__(
        self,
        dockwidget,
        filter_service=None,
        signal_manager=None,
        features_cache=None
    ):
        """
        Initialize the ExploringController.

        Args:
            dockwidget: Parent dockwidget for UI access
            filter_service: Filter service for business logic
            signal_manager: Centralized signal manager
            features_cache: Optional pre-configured features cache
        """
        super().__init__(dockwidget, filter_service, signal_manager)
        
        # State
        self._current_layer: Optional[QgsVectorLayer] = None
        self._current_field: Optional[str] = None
        self._selected_features: List[str] = []
        self._current_groupbox_mode: str = "single_selection"  # v3.1 STORY-2.3
        
        # Cache for feature values - use dockwidget's cache to avoid desync
        # FIX 2026-01-15: Unified cache - always use dw._exploring_cache
        # The controller does NOT maintain its own cache to prevent regression bugs
        self._features_cache = features_cache  # Optional override for testing only

    # === BaseController Implementation ===

    def setup(self) -> None:
        """Initialize exploring tab widgets and signals."""
        logger.debug("Setting up ExploringController")
        self._setup_layer_combo()
        self._setup_field_combo()
        self._setup_features_list()
        self._setup_action_buttons()
        self._connect_signals()
        logger.debug("ExploringController setup complete")

    def teardown(self) -> None:
        """Clean up exploring controller."""
        logger.debug("Tearing down ExploringController")
        self._disconnect_all_signals()
        if self._features_cache:
            self._features_cache.clear()
        self._current_layer = None
        self._current_field = None
        self._selected_features.clear()
        logger.debug("ExploringController teardown complete")

    def on_tab_activated(self) -> None:
        """Called when exploring tab becomes active."""
        super().on_tab_activated()
        self._refresh_layer_combo()

    def on_tab_deactivated(self) -> None:
        """Called when switching away from exploring tab."""
        super().on_tab_deactivated()

    # === LayerSelectionMixin Implementation ===

    def get_current_layer(self) -> Optional[QgsVectorLayer]:
        """Get currently selected layer."""
        return self._current_layer

    # === Layer Selection ===

    def _setup_layer_combo(self) -> None:
        """Configure the layer selection combo box."""
        # Get layer combo from dockwidget
        combo = self._get_layer_combo()
        if combo is None:
            logger.warning("Layer combo box not found in dockwidget")
            return
        
        # Configure to show only vector layers
        try:
            from qgis.gui import QgsMapLayerProxyModel
            combo.setFilters(QgsMapLayerProxyModel.VectorLayer)
        except (ImportError, AttributeError):
            pass

    def _get_layer_combo(self):
        """Get the layer combo box widget from dockwidget."""
        # Try different attribute names that might exist in dockwidget
        for attr in [
            'mMapLayerComboBox_for_exploring',
            'exploring_layer_combo',
            'layerComboBox'
        ]:
            if hasattr(self.dockwidget, attr):
                return getattr(self.dockwidget, attr)
        return None

    def _refresh_layer_combo(self) -> None:
        """Refresh the layer combo box."""
        combo = self._get_layer_combo()
        if combo and hasattr(combo, 'setCurrentLayer'):
            # Refresh by triggering a change event
            current = combo.currentLayer()
            if current != self._current_layer:
                self._on_layer_changed(current)

    def set_layer(self, layer: Optional[QgsVectorLayer]) -> None:
        """
        Set the current layer programmatically.

        Args:
            layer: Layer to set as current
            
        FIX 2026-01-15 v7: Invalidate previous layer cache when switching layers.
        This prevents stale data from being used when switching back to a layer.
        """
        if not self.is_layer_valid(layer):
            layer = None
        
        # FIX 2026-01-15 v7: Invalidate cache for OLD layer when switching
        # This ensures fresh data is loaded when returning to this layer
        old_layer = self._current_layer
        if old_layer and old_layer != layer:
            dw = getattr(self, '_dockwidget', None) or getattr(self, 'dockwidget', None)
            if dw and hasattr(dw, '_exploring_cache'):
                try:
                    dw._exploring_cache.invalidate_layer(old_layer.id())
                    logger.debug(f"set_layer: Invalidated cache for old layer {old_layer.name()}")
                except Exception as e:
                    logger.debug(f"set_layer: Could not invalidate old layer cache: {e}")
        
        self._current_layer = layer
        self._current_field = None
        
        if layer:
            self._populate_field_combo(layer)
        else:
            self._clear_field_combo()
            self._clear_features_list()

    def _on_layer_changed(self, layer: Optional[QgsVectorLayer]) -> None:
        """
        Handle layer selection change.

        Args:
            layer: Newly selected layer
        """
        logger.debug(f"Layer changed: {layer.name() if layer else 'None'}")
        self.set_layer(layer)

    # === Field Selection ===

    def _setup_field_combo(self) -> None:
        """Configure the field selection combo box."""
        combo = self._get_field_combo()
        if combo is None:
            logger.warning("Field combo box not found in dockwidget")
            return

    def _get_field_combo(self):
        """Get the field combo box widget from dockwidget."""
        for attr in [
            'mFieldComboBox_for_exploring',
            'exploring_field_combo',
            'fieldComboBox'
        ]:
            if hasattr(self.dockwidget, attr):
                return getattr(self.dockwidget, attr)
        return None

    def _populate_field_combo(self, layer: QgsVectorLayer) -> None:
        """
        Populate field combo with layer fields.

        Args:
            layer: Layer to get fields from
        """
        combo = self._get_field_combo()
        if combo is None:
            return
        
        if hasattr(combo, 'setLayer'):
            combo.setLayer(layer)
        else:
            # Manual population
            if hasattr(combo, 'clear'):
                combo.clear()
            fields = self.get_layer_fields(layer)
            for field in fields:
                if hasattr(combo, 'addItem'):
                    combo.addItem(field['name'])

    def _clear_field_combo(self) -> None:
        """Clear the field combo box."""
        combo = self._get_field_combo()
        if combo and hasattr(combo, 'clear'):
            combo.clear()

    def set_field(self, field_name: str) -> None:
        """
        Set the current field programmatically.

        Args:
            field_name: Name of the field to select
        """
        self._current_field = field_name
        self._populate_features_list()

    def _on_field_changed(self, field_name: str) -> None:
        """
        Handle field selection change.

        Args:
            field_name: Newly selected field name
        """
        logger.debug(f"Field changed: {field_name}")
        self.set_field(field_name)

    def get_current_field(self) -> Optional[str]:
        """Get currently selected field name."""
        return self._current_field

    # === Features List ===

    def _setup_features_list(self) -> None:
        """Configure the features list widget."""
        pass  # Widget setup done in dockwidget

    def _populate_features_list(self) -> None:
        """
        Populate features list with unique values.

        Uses cache for performance on repeated access.
        """
        if not self._current_layer or not self._current_field:
            self._clear_features_list()
            return

        layer_id = self._current_layer.id()
        field = self._current_field

        # Check cache first
        if self._features_cache:
            cached = self._features_cache.get(layer_id, field)
            if cached:
                logger.debug(f"Using cached values for {layer_id}:{field}")
                self._update_features_widget(cached)
                return

        # Fetch unique values
        values = self._get_unique_values()
        
        # Cache the values
        if self._features_cache and values:
            self._features_cache.set(layer_id, field, values)

        self._update_features_widget(values)

    def _get_unique_values(self) -> List[str]:
        """
        Get unique values for current field.

        Returns:
            List of unique values as strings
        """
        if not self._current_layer or not self._current_field:
            return []

        try:
            field_index = self._current_layer.fields().indexFromName(self._current_field)
            if field_index < 0:
                return []

            unique_values = self._current_layer.uniqueValues(field_index)
            
            # Convert to sorted string list
            return sorted([str(v) for v in unique_values if v is not None])
        except Exception as e:
            logger.error(f"Error getting unique values: {e}")
            return []

    def _update_features_widget(self, values: List[str]) -> None:
        """
        Update the features list widget with values.

        Args:
            values: List of feature values to display
        """
        # Implementation depends on dockwidget structure
        # This would update the checkable combo or list widget

    def _clear_features_list(self) -> None:
        """Clear the features list widget."""
        self._selected_features.clear()

    # === Spatial Navigation ===

    def _setup_action_buttons(self) -> None:
        """Configure flash/zoom/identify action buttons."""
        pass  # Button setup done in dockwidget

    def flash_feature(self, feature_id: int, duration_ms: int = 500) -> bool:
        """
        Flash a feature on the map.

        Args:
            feature_id: ID of the feature to flash
            duration_ms: Flash duration in milliseconds

        Returns:
            True if successful, False otherwise
        """
        if not QGIS_AVAILABLE or not self._current_layer:
            return False

        try:
            feature = self._get_feature_by_id(feature_id)
            if feature and feature.hasGeometry():
                canvas = iface.mapCanvas()
                canvas.flashGeometries(
                    [feature.geometry()],
                    self._current_layer.crs(),
                    flashes=3,
                    duration=duration_ms
                )
                return True
        except Exception as e:
            logger.error(f"Error flashing feature {feature_id}: {e}")
        
        return False

    def flash_features(
        self, 
        feature_ids: List[int], 
        start_color: Optional[Tuple[int, int, int, int]] = None,
        end_color: Optional[Tuple[int, int, int, int]] = None,
        flashes: int = 6, 
        duration_ms: int = 400
    ) -> bool:
        """
        Flash multiple features on the map canvas.
        
        v3.1 Vague 2: Delegated from dockwidget exploring_identify_clicked.
        
        Args:
            feature_ids: List of feature IDs to flash
            start_color: RGBA tuple for start color (default: red)
            end_color: RGBA tuple for end color (default: orange fade)
            flashes: Number of flash pulses
            duration_ms: Total duration in milliseconds
            
        Returns:
            True if successful, False otherwise
        """
        if not QGIS_AVAILABLE or not self._current_layer:
            return False
        
        if not feature_ids:
            return False
            
        try:
            # Default colors matching legacy implementation
            if start_color is None:
                start_color = (235, 49, 42, 255)
            if end_color is None:
                end_color = (237, 97, 62, 25)
            
            canvas = iface.mapCanvas()
            canvas.flashFeatureIds(
                self._current_layer,
                feature_ids,
                startColor=QColor(*start_color),
                endColor=QColor(*end_color),
                flashes=flashes,
                duration=duration_ms
            )
            return True
        except Exception as e:
            logger.error(f"Error flashing {len(feature_ids)} features: {e}")
            return False

    def zoom_to_feature(self, feature_id: int, scale_factor: float = 1.5) -> bool:
        """
        Zoom map to a feature.

        Args:
            feature_id: ID of the feature to zoom to
            scale_factor: Factor to scale the extent (> 1 adds padding)

        Returns:
            True if successful, False otherwise
        """
        if not QGIS_AVAILABLE or not self._current_layer:
            return False

        try:
            feature = self._get_feature_by_id(feature_id)
            if feature and feature.hasGeometry():
                canvas = iface.mapCanvas()
                extent = feature.geometry().boundingBox()
                
                # Add padding
                extent.scale(scale_factor)
                
                # Transform to canvas CRS if needed
                if self._current_layer.crs() != canvas.mapSettings().destinationCrs():
                    transform = QgsCoordinateTransform(
                        self._current_layer.crs(),
                        canvas.mapSettings().destinationCrs(),
                        QgsProject.instance()
                    )
                    extent = transform.transformBoundingBox(extent)
                
                canvas.setExtent(extent)
                canvas.refresh()
                return True
        except Exception as e:
            logger.error(f"Error zooming to feature {feature_id}: {e}")
        
        return False

    def zoom_to_features(self, features: list, scale_factor: float = 1.1) -> bool:
        """
        Zoom map to a list of features.

        Args:
            features: List of QgsFeature objects to zoom to
            scale_factor: Factor to scale the extent (> 1 adds padding)

        Returns:
            True if successful, False otherwise
        """
        if not QGIS_AVAILABLE or not features:
            return False

        try:
            # Calculate combined extent
            combined_extent = QgsRectangle()
            for feature in features:
                if feature and feature.hasGeometry():
                    if combined_extent.isNull():
                        combined_extent = feature.geometry().boundingBox()
                    else:
                        combined_extent.combineExtentWith(feature.geometry().boundingBox())

            if combined_extent.isNull():
                return False

            canvas = iface.mapCanvas()
            
            # Add padding
            combined_extent.scale(scale_factor)
            
            # Transform to canvas CRS if needed
            if self._current_layer and self._current_layer.crs() != canvas.mapSettings().destinationCrs():
                transform = QgsCoordinateTransform(
                    self._current_layer.crs(),
                    canvas.mapSettings().destinationCrs(),
                    QgsProject.instance()
                )
                combined_extent = transform.transformBoundingBox(combined_extent)
            
            canvas.setExtent(combined_extent)
            canvas.refresh()
            return True
        except Exception as e:
            logger.error(f"Error zooming to features: {e}")
        
        return False

    def identify_feature(self, feature_id: int) -> bool:
        """
        Show identify results for a feature.

        Args:
            feature_id: ID of the feature to identify

        Returns:
            True if successful, False otherwise
        """
        if not QGIS_AVAILABLE or not self._current_layer:
            return False

        try:
            feature = self._get_feature_by_id(feature_id)
            if feature:
                # Open identify dialog or show attributes
                iface.openFeatureForm(self._current_layer, feature)
                return True
        except Exception as e:
            logger.error(f"Error identifying feature {feature_id}: {e}")
        
        return False

    def zoom_to_selected(self) -> bool:
        """
        Zoom to all selected features.

        Returns:
            True if successful, False otherwise
        """
        if not QGIS_AVAILABLE or not self._current_layer:
            return False

        try:
            selected_ids = self._current_layer.selectedFeatureIds()
            if not selected_ids:
                return False

            # Calculate combined extent
            combined_extent = QgsRectangle()
            for fid in selected_ids:
                feature = self._get_feature_by_id(fid)
                if feature and feature.hasGeometry():
                    if combined_extent.isNull():
                        combined_extent = feature.geometry().boundingBox()
                    else:
                        combined_extent.combineExtentWith(feature.geometry().boundingBox())

            if not combined_extent.isNull():
                canvas = iface.mapCanvas()
                combined_extent.scale(1.5)
                canvas.setExtent(combined_extent)
                canvas.refresh()
                return True
        except Exception as e:
            logger.error(f"Error zooming to selected: {e}")
        
        return False

    def _get_feature_by_id(self, feature_id: int) -> Optional[QgsFeature]:
        """
        Get feature by ID.

        Args:
            feature_id: Feature ID

        Returns:
            Feature if found, None otherwise
        """
        if not self._current_layer:
            return None

        try:
            request = QgsFeatureRequest().setFilterFid(feature_id)
            for feature in self._current_layer.getFeatures(request):
                return feature
        except Exception as e:
            logger.error(f"Error getting feature {feature_id}: {e}")
        
        return None

    # === Multiple Selection ===

    def get_selected_features(self) -> List[str]:
        """
        Get list of selected feature values.

        Returns:
            List of selected feature values
        """
        return list(self._selected_features)

    def set_selected_features(self, values: List[str]) -> None:
        """
        Set selected features programmatically.

        Args:
            values: List of feature values to select
        """
        self._selected_features = list(values)

    def on_selection_changed(self, selected_values: List[str]) -> None:
        """
        Handle feature selection change.

        Args:
            selected_values: List of newly selected values
        """
        self._selected_features = list(selected_values)
        logger.debug(f"Selection changed: {len(selected_values)} features selected")

    def clear_selection(self) -> None:
        """
        Clear the current selection.
        
        v3.1 Phase 6 (STORY-2.3): Also clears QGIS layer selection.
        """
        self._selected_features.clear()
        
        # v3.1: Also clear QGIS layer selection
        if self._current_layer and self.is_layer_valid(self._current_layer):
            try:
                self._current_layer.removeSelection()
                logger.debug("ExploringController: Cleared layer selection")
            except Exception as e:
                logger.warning(f"ExploringController: Failed to clear layer selection: {e}")

    # === Groupbox Mode Management (v3.1 STORY-2.3) ===

    def get_groupbox_mode(self) -> str:
        """
        Get current exploring groupbox mode.
        
        Returns:
            Current mode: 'single_selection', 'multiple_selection', or 'custom_selection'
        """
        return self._current_groupbox_mode

    def set_groupbox_mode(self, mode: str) -> bool:
        """
        Set current exploring groupbox mode.
        
        This method tracks the groupbox state in the controller for better 
        separation of concerns. The UI still handles the actual widget states.
        
        Args:
            mode: 'single_selection', 'multiple_selection', or 'custom_selection'
        
        Returns:
            True if mode was set, False if invalid mode
        """
        valid_modes = ('single_selection', 'multiple_selection', 'custom_selection')
        if mode not in valid_modes:
            logger.warning(f"ExploringController: Invalid groupbox mode '{mode}'")
            return False
        
        old_mode = self._current_groupbox_mode
        if old_mode != mode:
            # Invalidate cache for old mode when switching
            if self._features_cache and self._current_layer:
                layer_id = self._current_layer.id()
                self._features_cache.invalidate(layer_id, old_mode)
                logger.debug(f"ExploringController: Groupbox mode changed {old_mode} -> {mode}, cache invalidated")
            
            self._current_groupbox_mode = mode
        
        return True

    def configure_groupbox(self, mode: str, layer: 'QgsVectorLayer' = None, 
                           layer_props: Dict[str, Any] = None) -> bool:
        """
        Configure exploring groupbox for the specified mode.
        
        v4.0 Sprint 5: Full migration from dockwidget._configure_*_groupbox methods.
        
        This method handles:
        - Setting the current groupbox mode
        - Configuring widgets for the mode
        - Setting layer on expression widgets
        - Managing signal connections
        
        Args:
            mode: 'single_selection', 'multiple_selection', or 'custom_selection'
            layer: Optional layer to configure widgets for
            layer_props: Optional layer properties dict
        
        Returns:
            True if configuration succeeded, False otherwise
        """
        if not self.set_groupbox_mode(mode):
            return False
        
        target_layer = layer or self._current_layer
        if not target_layer:
            logger.debug(f"ExploringController.configure_groupbox: No layer for mode {mode}")
            return False
        
        try:
            dw = self._dockwidget
            if not dw or not hasattr(dw, 'widgets') or not dw.widgets:
                return False
            
            exploring_widgets = dw.widgets.get("EXPLORING", {})
            if not exploring_widgets:
                return False
            
            # Map mode to widget keys
            mode_config = {
                'single_selection': {
                    'features_widget': 'SINGLE_SELECTION_FEATURES',
                    'expression_widget': 'SINGLE_SELECTION_EXPRESSION',
                    'expression_key': 'single_selection_expression'
                },
                'multiple_selection': {
                    'features_widget': 'MULTIPLE_SELECTION_FEATURES',
                    'expression_widget': 'MULTIPLE_SELECTION_EXPRESSION',
                    'expression_key': 'multiple_selection_expression'
                },
                'custom_selection': {
                    'features_widget': None,
                    'expression_widget': 'CUSTOM_SELECTION_EXPRESSION',
                    'expression_key': 'custom_selection_expression'
                }
            }
            
            config = mode_config.get(mode)
            if not config:
                return False
            
            # Configure expression widget
            expr_key = config['expression_widget']
            if expr_key and expr_key in exploring_widgets:
                expr_widget = exploring_widgets[expr_key].get("WIDGET")
                if expr_widget:
                    expr_widget.setEnabled(True)
                    try:
                        expr_widget.setLayer(target_layer)
                        # FIX 2026-01-16: Set default field after setLayer to avoid empty combobox
                        # Get saved expression from layer_props or fallback to first field
                        expr_prop_key = config['expression_key']
                        saved_expr = ""
                        if layer_props:
                            saved_expr = layer_props.get("exploring", {}).get(expr_prop_key, "")
                        if not saved_expr:
                            # Fallback: use first field of layer
                            fields = target_layer.fields()
                            if fields.count() > 0:
                                saved_expr = fields[0].name()
                        if saved_expr:
                            # Use setField for simple field names, setExpression for complex expressions
                            from qgis.core import QgsExpression
                            if QgsExpression(saved_expr).isField():
                                expr_widget.setField(saved_expr)
                            else:
                                expr_widget.setExpression(saved_expr)
                            logger.debug(f"Set {expr_key} widget field to '{saved_expr}'")
                    except (AttributeError, RuntimeError) as e:
                        logger.warning(f"Could not set layer on {expr_key}: {e}")
            
            # Configure features widget (single/multiple selection only)
            feat_key = config['features_widget']
            if feat_key and feat_key in exploring_widgets:
                feat_widget = exploring_widgets[feat_key].get("WIDGET")
                if feat_widget:
                    feat_widget.setEnabled(True)
                    try:
                        if mode == 'single_selection':
                            feat_widget.setLayer(target_layer)
                            if layer_props:
                                expr = layer_props.get("exploring", {}).get(config['expression_key'], "")
                                if expr:
                                    feat_widget.setDisplayExpression(expr)
                            feat_widget.setAllowNull(True)
                        elif mode == 'multiple_selection' and layer_props:
                            feat_widget.setLayer(target_layer, layer_props)
                    except (AttributeError, RuntimeError) as e:
                        logger.warning(f"Could not configure {feat_key}: {e}")
            
            logger.debug(f"ExploringController: Configured groupbox for mode '{mode}'")
            return True
            
        except Exception as e:
            logger.error(f"ExploringController.configure_groupbox error: {e}")
            return False

    # === Signal Connections ===

    def _connect_signals(self) -> None:
        """Connect all controller signals."""
        # Layer combo change
        layer_combo = self._get_layer_combo()
        if layer_combo:
            self._connect_signal(
                layer_combo, 'layerChanged',
                self._on_layer_changed,
                'exploring'
            )

        # Field combo change
        field_combo = self._get_field_combo()
        if field_combo:
            self._connect_signal(
                field_combo, 'fieldChanged',
                self._on_field_changed,
                'exploring'
            )

    # === Selection Tool Activation ===

    def activate_selection_tool(self, layer: QgsVectorLayer = None) -> bool:
        """
        Activate QGIS rectangle selection tool on canvas.
        
        Args:
            layer: Optional layer to set as active. If None, uses current layer.
        
        Returns:
            True if tool activated successfully, False otherwise
        """
        if not QGIS_AVAILABLE:
            return False
        
        target_layer = layer or self._current_layer
        
        try:
            # Activate QGIS selection tool on canvas
            iface.actionSelectRectangle().trigger()
            logger.debug("ExploringController: Selection tool activated on canvas")
            
            # Set active layer in LayerTreeView
            if target_layer:
                iface.setActiveLayer(target_layer)
                logger.debug(f"ExploringController: Active layer set to {target_layer.name()}")
            
            return True
        except Exception as e:
            logger.warning(f"ExploringController: Failed to activate selection tool: {e}")
            return False

    def select_layer_features(self, feature_ids: List[int] = None, layer: QgsVectorLayer = None) -> bool:
        """
        Select features on a layer using QGIS selection.
        
        Args:
            feature_ids: List of feature IDs to select. If None, clears selection.
            layer: Optional layer to use. If None, uses current layer.
        
        Returns:
            True if selection succeeded, False otherwise
        """
        target_layer = layer or self._current_layer
        if not target_layer:
            logger.debug("ExploringController: No layer available for selection")
            return False
        
        try:
            # Clear existing selection first
            target_layer.removeSelection()
            
            # Select new features
            if feature_ids and len(feature_ids) > 0:
                target_layer.select(feature_ids)
                logger.debug(f"ExploringController: Selected {len(feature_ids)} features on {target_layer.name()}")
            
            return True
        except Exception as e:
            logger.warning(f"ExploringController: Failed to select features: {e}")
            return False

    # === Layer Expression Management ===
    
    def reset_layer_expressions(self, layer_props: Dict[str, Any]) -> None:
        """
        Reset exploring expressions to primary_key_name when switching layers.
        
        v4.0 Sprint 1: Migrated from dockwidget._reset_layer_expressions.
        
        Prevents KeyError when field names from previous layer don't exist in new layer.
        
        Args:
            layer_props: Layer properties dict with infos and exploring sections
        """
        current_layer = getattr(self.dockwidget, 'current_layer', None)
        if not current_layer:
            logger.warning("reset_layer_expressions: No current layer")
            return
        
        primary_key = layer_props.get("infos", {}).get("primary_key_name", "")
        try:
            layer_fields = [field.name() for field in current_layer.fields()]
        except Exception as e:
            logger.warning(f"reset_layer_expressions: Cannot get fields: {e}")
            return
        
        logger.debug(
            f"reset_layer_expressions: layer='{current_layer.name()}', "
            f"primary_key='{primary_key}'"
        )
        
        # Ensure primary_key is valid, fallback to first field
        fallback_field = primary_key
        if primary_key and primary_key not in layer_fields:
            if layer_fields:
                fallback_field = layer_fields[0]
                logger.warning(
                    f"Primary key '{primary_key}' not found, "
                    f"using fallback '{fallback_field}'"
                )
            else:
                logger.error(f"Layer '{current_layer.name()}' has no fields")
                return
        
        exploring = layer_props.get("exploring", {})
        
        # Reset single_selection_expression
        single_expr = exploring.get("single_selection_expression", "")
        if not self._is_valid_field_expression(single_expr, layer_fields):
            logger.info(f"Resetting single_selection_expression to '{fallback_field}'")
            exploring["single_selection_expression"] = fallback_field
        
        # Reset multiple_selection_expression
        multiple_expr = exploring.get("multiple_selection_expression", "")
        if not self._is_valid_field_expression(multiple_expr, layer_fields):
            logger.info(f"Resetting multiple_selection_expression to '{fallback_field}'")
            exploring["multiple_selection_expression"] = fallback_field
        
        # Reset custom_selection_expression if it's an invalid field
        custom_expr = exploring.get("custom_selection_expression", "")
        if custom_expr:
            try:
                from qgis.core import QgsExpression
                qgs_expr = QgsExpression(custom_expr)
                if qgs_expr.isField() and not self._is_valid_field_expression(custom_expr, layer_fields):
                    logger.info(f"Resetting custom_selection_expression to '{fallback_field}'")
                    exploring["custom_selection_expression"] = fallback_field
            except Exception:
                pass
        elif not custom_expr:
            exploring["custom_selection_expression"] = fallback_field
    
    def _is_valid_field_expression(self, expr: str, fields: List[str]) -> bool:
        """
        Check if expression is a valid field name for a layer.
        
        Args:
            expr: Field expression to check
            fields: List of valid field names
            
        Returns:
            True if expression is a valid field
        """
        if not expr:
            return False
        # Normalize by removing quotes
        normalized = expr.strip().strip('"')
        return normalized in fields or expr in fields

    # === Cache Management ===

    def clear_cache(self) -> None:
        """Clear the features cache."""
        if self._features_cache:
            self._features_cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        if self._features_cache:
            return self._features_cache.get_stats()
        return {}

    # === Zoom & Navigation ===

    def _compute_zoom_extent_for_mode(self):
        """
        Compute the appropriate zoom extent based on the current exploring mode.
        
        For single selection: zoom to the selected feature's bounding box
        For multiple selection: zoom to the combined extent of selected features
        For custom selection: zoom to the combined extent of features matching the expression
        
        Returns:
            QgsRectangle: The computed extent, or None if no features found
        """
        if not self._dockwidget.widgets_initialized or self._dockwidget.current_layer is None:
            return None
            
        try:
            from qgis.core import QgsRectangle, QgsExpression, QgsFeatureRequest
            
            extent = QgsRectangle()
            features_found = 0
            
            if self._dockwidget.current_exploring_groupbox == "single_selection":
                # Single selection: get the feature from the picker widget
                feature_picker = self._dockwidget.widgets.get("EXPLORING", {}).get("SINGLE_SELECTION_FEATURES", {}).get("WIDGET")
                if feature_picker:
                    feature = feature_picker.feature()
                    if feature and feature.isValid():
                        # Reload feature to ensure geometry is available
                        try:
                            reloaded = self._dockwidget.current_layer.getFeature(feature.id())
                            if reloaded.isValid() and reloaded.hasGeometry() and not reloaded.geometry().isEmpty():
                                extent = reloaded.geometry().boundingBox()
                                features_found = 1
                                logger.debug(f"_compute_zoom_extent_for_mode: Single feature extent computed")
                        except Exception as e:
                            logger.warning(f"_compute_zoom_extent_for_mode: Error reloading single feature: {e}")
                            
            elif self._dockwidget.current_exploring_groupbox == "multiple_selection":
                # Multiple selection: get checked items and compute combined extent
                combo = self._dockwidget.widgets.get("EXPLORING", {}).get("MULTIPLE_SELECTION_FEATURES", {}).get("WIDGET")
                if combo:
                    checked_items = combo.checkedItems()
                    if checked_items:
                        # PERFORMANCE FIX v2.6.5: Limit number of items to process
                        MAX_ITEMS_FOR_EXTENT = 500  # Beyond this, use layer extent
                        if len(checked_items) > MAX_ITEMS_FOR_EXTENT:
                            logger.debug(f"_compute_zoom_extent_for_mode: Too many items ({len(checked_items)}), using layer extent")
                            return self._dockwidget.get_filtered_layer_extent(self._dockwidget.current_layer)
                        
                        # Try to get features by their IDs
                        layer_props = self._dockwidget.PROJECT_LAYERS.get(self._dockwidget.current_layer.id(), {})
                        pk_name = layer_props.get("infos", {}).get("primary_key_name")
                        pk_is_numeric = layer_props.get("infos", {}).get("primary_key_is_numeric", True)
                        
                        for item in checked_items:
                            try:
                                # item format: (display_value, pk_value, ...)
                                if isinstance(item, (list, tuple)) and len(item) > 1:
                                    pk_value = item[1]
                                    # Build expression to fetch this feature
                                    if pk_name:
                                        if pk_is_numeric:
                                            expr = f'"{pk_name}" = {pk_value}'
                                        else:
                                            expr = f'"{pk_name}" = \'{pk_value}\''
                                        qgs_expr = QgsExpression(expr)
                                        if qgs_expr.isValid():
                                            for feat in self._dockwidget.current_layer.getFeatures(QgsFeatureRequest(qgs_expr)):
                                                if feat.hasGeometry() and not feat.geometry().isEmpty():
                                                    if extent.isEmpty():
                                                        extent = feat.geometry().boundingBox()
                                                    else:
                                                        extent.combineExtentWith(feat.geometry().boundingBox())
                                                    features_found += 1
                                                    break  # Only one feature per pk_value
                            except Exception as e:
                                logger.debug(f"_compute_zoom_extent_for_mode: Error processing multiple item: {e}")
                                
            elif self._dockwidget.current_exploring_groupbox == "custom_selection":
                # Custom selection: get expression and fetch matching features
                expr_widget = self._dockwidget.widgets.get("EXPLORING", {}).get("CUSTOM_SELECTION_EXPRESSION", {}).get("WIDGET")
                if expr_widget:
                    expression = expr_widget.expression()
                    if expression:
                        qgs_expr = QgsExpression(expression)
                        # Only process if it's a filter expression (not just a field name)
                        if qgs_expr.isValid() and not qgs_expr.isField():
                            try:
                                request = QgsFeatureRequest(qgs_expr)
                                # PERFORMANCE FIX: Limit features processed for extent calculation
                                MAX_EXTENT_FEATURES = 5000  # Enough for good extent, prevents freeze
                                for feat in self._dockwidget.current_layer.getFeatures(request):
                                    if feat.hasGeometry() and not feat.geometry().isEmpty():
                                        if extent.isEmpty():
                                            extent = feat.geometry().boundingBox()
                                        else:
                                            extent.combineExtentWith(feat.geometry().boundingBox())
                                        features_found += 1
                                        # Safety limit to prevent UI freeze
                                        if features_found >= MAX_EXTENT_FEATURES:
                                            logger.debug(f"_compute_zoom_extent_for_mode: Stopped at {MAX_EXTENT_FEATURES} features for extent")
                                            break
                            except Exception as e:
                                logger.warning(f"_compute_zoom_extent_for_mode: Error fetching custom features: {e}")
            
            if features_found > 0 and not extent.isEmpty():
                # Add small padding (10% of extent size, minimum 10 units)
                width_padding = max(extent.width() * 0.1, 10)
                height_padding = max(extent.height() * 0.1, 10)
                extent.grow(max(width_padding, height_padding))
                logger.debug(f"_compute_zoom_extent_for_mode: Computed extent from {features_found} features for mode '{self._dockwidget.current_exploring_groupbox}'")
                return extent
            else:
                # Fallback to filtered layer extent
                logger.debug(f"_compute_zoom_extent_for_mode: No features found for mode '{self._dockwidget.current_exploring_groupbox}', using filtered layer extent")
                return self._dockwidget.get_filtered_layer_extent(self._dockwidget.current_layer)
                
        except Exception as e:
            logger.warning(f"_compute_zoom_extent_for_mode error: {e}")
            return self._dockwidget.get_filtered_layer_extent(self._dockwidget.current_layer)

    def zooming_to_features(self, features, expression=None):
        """
        Zoom to provided features on the map canvas.
        
        Migrated from dockwidget - v4.0 Sprint 2 (controller architecture).
        """
        if not self._dockwidget.widgets_initialized or self._dockwidget.current_layer is None:
            return

        # v3.0.14: CRITICAL - Use centralized deletion check with full protection
        if self._dockwidget._is_layer_truly_deleted(self._dockwidget.current_layer):
            logger.debug("zooming_to_features: current_layer C++ object truly deleted")
            self._dockwidget.current_layer = None
            return

        # Import required QGIS modules
        from qgis.core import (
            QgsGeometry, QgsCoordinateTransform, 
            QgsCoordinateReferenceSystem, QgsProject,
            QgsExpression, QgsFeatureRequest
        )
        from ...infrastructure.utils import CRS_UTILS_AVAILABLE, DEFAULT_METRIC_CRS
        if CRS_UTILS_AVAILABLE:
            from ...core.geometry.crs_utils import is_geographic_crs, get_optimal_metric_crs

        # DIAGNOSTIC: Log incoming features
        logger.info(f"🔍 zooming_to_features DIAGNOSTIC:")
        logger.info(f"   features count: {len(features) if features else 0}")
        logger.info(f"   expression: '{expression}'")
        if features and len(features) > 0:
            for i, f in enumerate(features[:3]):
                has_geom = f.hasGeometry() if hasattr(f, 'hasGeometry') else 'N/A'
                fid = f.id() if hasattr(f, 'id') else 'N/A'
                logger.info(f"   feature[{i}]: id={fid}, hasGeometry={has_geom}")
                if has_geom and f.hasGeometry():
                    geom = f.geometry()
                    logger.info(f"      geometry: type={geom.type()}, isEmpty={geom.isEmpty()}")
        
        # IMPROVED: If features list is empty but we have an expression, try to fetch features
        if (not features or not isinstance(features, list) or len(features) == 0) and expression:
            logger.debug(f"zooming_to_features: Empty features list, trying to fetch from expression: {expression}")
            try:
                qgs_expr = QgsExpression(expression)
                if qgs_expr.isValid():
                    request = QgsFeatureRequest(qgs_expr)
                    # PERFORMANCE FIX: Limit features fetched for zoom
                    request.setLimit(5000)  # Enough for zoom extent calculation
                    features = list(self._dockwidget.current_layer.getFeatures(request))
                    logger.debug(f"zooming_to_features: Fetched {len(features)} features from expression")
            except Exception as e:
                logger.warning(f"zooming_to_features: Failed to fetch features from expression: {e}")
        
        # Safety check: ensure features is a list
        if not features or not isinstance(features, list) or len(features) == 0:
            # IMPROVED: Zoom to extent based on current exploring mode
            logger.debug("zooming_to_features: No features provided, computing extent based on mode")
            extent = self._compute_zoom_extent_for_mode()
            if extent and not extent.isEmpty():
                self._dockwidget.iface.mapCanvas().zoomToFeatureExtent(extent)
            else:
                logger.debug("zooming_to_features: Empty extent, using canvas refresh")
                self._dockwidget.iface.mapCanvas().refresh() 
            return

        # CRITICAL FIX: For features without geometry, try to reload from layer
        features_with_geometry = []
        for feature in features:
            if feature.hasGeometry() and not feature.geometry().isEmpty():
                features_with_geometry.append(feature)
            else:
                # Try to reload feature with geometry from layer
                try:
                    reloaded = self._dockwidget.current_layer.getFeature(feature.id())
                    if reloaded.isValid() and reloaded.hasGeometry() and not reloaded.geometry().isEmpty():
                        features_with_geometry.append(reloaded)
                        logger.debug(f"Reloaded feature {feature.id()} with geometry for zoom")
                    else:
                        logger.warning(f"Could not reload feature {feature.id()} with valid geometry")
                except Exception as e:
                    logger.warning(f"Error reloading feature {feature.id()}: {e}")

        logger.info(f"   features_with_geometry count: {len(features_with_geometry)}")

        if len(features_with_geometry) == 0:
            # IMPROVED: Zoom to extent based on current exploring mode
            logger.debug("zooming_to_features: No features have geometry, computing extent based on mode")
            extent = self._compute_zoom_extent_for_mode()
            if extent and not extent.isEmpty():
                self._dockwidget.iface.mapCanvas().zoomToFeatureExtent(extent)
            return

        if len(features_with_geometry) == 1:
            feature = features_with_geometry[0]
            # CRITICAL: Create a copy to avoid modifying the original geometry
            geom = QgsGeometry(feature.geometry())
            
            # Get CRS information
            layer_crs = self._dockwidget.current_layer.crs()
            canvas_crs = self._dockwidget.iface.mapCanvas().mapSettings().destinationCrs()
            
            # IMPROVED v2.5.7: Use crs_utils for better CRS detection
            if CRS_UTILS_AVAILABLE:
                is_geographic = is_geographic_crs(layer_crs)
            else:
                is_geographic = layer_crs.isGeographic()
            
            # CRITICAL: For geographic coordinates, switch to a metric CRS for buffer calculations
            # This ensures accurate buffer distances in meters instead of imprecise degrees
            if is_geographic:
                # IMPROVED v2.5.7: Use optimal metric CRS (UTM or Web Mercator)
                if CRS_UTILS_AVAILABLE:
                    metric_crs_authid = get_optimal_metric_crs(
                        project=QgsProject.instance(),
                        source_crs=layer_crs,
                        extent=geom.boundingBox(),
                        prefer_utm=True
                    )
                    work_crs = QgsCoordinateReferenceSystem(metric_crs_authid)
                    logger.debug(f"FilterMate: Using optimal metric CRS {metric_crs_authid} for zoom buffer")
                else:
                    # Fallback to Web Mercator
                    work_crs = QgsCoordinateReferenceSystem(DEFAULT_METRIC_CRS)
                    logger.debug(f"FilterMate: Using Web Mercator ({DEFAULT_METRIC_CRS}) for zoom buffer")
                
                to_metric = QgsCoordinateTransform(layer_crs, work_crs, QgsProject.instance())
                geom.transform(to_metric)
            else:
                # Already in projected coordinates, use layer CRS
                work_crs = layer_crs
            
            if str(feature.geometry().type()) == 'GeometryType.Point':
                # Points need a buffer since they have no bounding box
                buffer_distance = 50  # 50 meters for all points
                box = geom.buffer(buffer_distance, 5).boundingBox()
            else:
                # IMPROVED: For polygons/lines, zoom to the actual feature bounding box
                # with a small percentage-based padding for better visibility
                box = geom.boundingBox()
                if not box.isEmpty():
                    # Add 10% padding based on feature size (minimum 5 meters)
                    width_padding = max(box.width() * 0.1, 5)
                    height_padding = max(box.height() * 0.1, 5)
                    box.grow(max(width_padding, height_padding))
                else:
                    # Fallback for empty bounding box
                    box.grow(10)
            
            # Transform box to canvas CRS if needed
            if work_crs != canvas_crs:
                transform = QgsCoordinateTransform(work_crs, canvas_crs, QgsProject.instance())
                box = transform.transformBoundingBox(box)

            self._dockwidget.iface.mapCanvas().zoomToFeatureExtent(box)
        else:
            self._dockwidget.iface.mapCanvas().zoomToFeatureIds(self._dockwidget.current_layer, [feature.id() for feature in features_with_geometry])

        self._dockwidget.iface.mapCanvas().refresh()

    def get_current_features(self, use_cache: bool = True):
        """
        Get the currently selected features based on the active exploring groupbox.
        
        v3.1 Sprint 6: Migrated from dockwidget to controller.
        
        This method retrieves features from the appropriate widget (single selection,
        multiple selection, or custom expression) and caches them for subsequent
        operations like flash, zoom, and identify.
        
        Args:
            use_cache: If True, return cached features if available (default: True).
                       Set to False to force refresh from widgets.
        
        Returns:
            tuple: (features, expression) where features is a list of QgsFeature
                   and expression is the QGIS expression string used for selection.
        """
        dw = self._dockwidget
        
        if not dw.widgets_initialized or dw.current_layer is None:
            logger.debug("get_current_features: widgets not initialized or no current layer")
            return [], ''
        
        # Use centralized deletion check
        if dw._is_layer_truly_deleted(dw.current_layer):
            logger.debug("get_current_features: current_layer C++ object truly deleted")
            dw.current_layer = None
            return [], ''
        
        layer_id = dw.current_layer.id()
        groupbox_type = dw.current_exploring_groupbox
        
        # CACHE CHECK
        if use_cache and hasattr(dw, '_exploring_cache') and groupbox_type:
            cached = dw._exploring_cache.get(layer_id, groupbox_type)
            if cached:
                # Validate cache for custom_selection
                if groupbox_type == "custom_selection":
                    current_expr = dw.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].expression()
                    cached_expr = cached.get('expression', '')
                    if current_expr != cached_expr:
                        logger.debug(f"get_current_features: CACHE STALE for custom_selection")
                        dw._exploring_cache.invalidate(layer_id, groupbox_type)
                    else:
                        logger.debug(f"get_current_features: CACHE HIT for {layer_id[:8]}.../{groupbox_type}")
                        return cached['features'], cached['expression'] or ''
                else:
                    logger.debug(f"get_current_features: CACHE HIT for {layer_id[:8]}.../{groupbox_type}")
                    return cached['features'], cached['expression'] or ''
        
        features = []
        expression = ''
        
        logger.debug(f"get_current_features: groupbox='{groupbox_type}', layer='{dw.current_layer.name()}', use_cache={use_cache}")
        
        if groupbox_type == "single_selection":
            features, expression = self._get_single_selection_features()
            logger.debug(f"  → single_selection returned {len(features)} features")
        elif groupbox_type == "multiple_selection":
            features, expression = self._get_multiple_selection_features()
        elif groupbox_type == "custom_selection":
            features, expression = self._get_custom_selection_features()
        else:
            logger.warning(f"get_current_features: Unknown groupbox '{groupbox_type}'")
        
        # Cache update
        if features and hasattr(dw, '_exploring_cache') and groupbox_type:
            dw._exploring_cache.put(layer_id, groupbox_type, features, expression)
            logger.debug(f"get_current_features: Cached {len(features)} features")
        
        return features, expression
    
    def _get_single_selection_features(self):
        """
        Handle single selection feature retrieval with recovery logic.
        
        FIX 2026-01-15 v8: ALWAYS use widget feature picker as primary source.
        User requirement: "si pas de selection QGIS, et single selection alors 
        feature active est la feature active du feature picker single selection 
        (meme si pushButton_checkable_exploring_selecting est unchecked)"
        
        Strategy order:
        1. ALWAYS try widget.feature() first (primary source)
        2. If widget feature invalid, try saved FID recovery
        3. Only if still invalid AND groupbox != single_selection, try QGIS canvas
        4. Return empty only if no feature available
        
        CRITICAL: Always reload feature from layer to ensure geometry is present.
        QgsFeaturePickerWidget.feature() often returns features without geometry.
        """
        dw = self._dockwidget
        widget = dw.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
        input_feature = widget.feature()
        
        logger.debug(f"_get_single_selection_features: widget.feature() = {input_feature}")
        logger.debug(f"  widget.layer() = {widget.layer().name() if widget.layer() else 'None'}")
        logger.debug(f"  current_exploring_groupbox = {dw.current_exploring_groupbox}")
        
        # FIX v8: For single_selection mode, widget feature picker is THE source
        # Don't fall back to QGIS canvas - the picker IS the source
        is_single_selection_mode = (dw.current_exploring_groupbox == "single_selection")
        
        # Check if feature is valid
        if input_feature is None or (hasattr(input_feature, 'isValid') and not input_feature.isValid()):
            logger.debug(f"  Feature is None or invalid, trying recovery...")
            
            # Strategy 1: Try recovery from saved FID (always try this first)
            if (hasattr(dw, '_last_single_selection_fid') 
                and dw._last_single_selection_fid is not None
                and dw.current_layer.id() == getattr(dw, '_last_single_selection_layer_id', None)):
                try:
                    recovered = dw.current_layer.getFeature(dw._last_single_selection_fid)
                    if recovered.isValid() and recovered.hasGeometry():
                        logger.info(f"SINGLE_SELECTION: Recovered feature id={dw._last_single_selection_fid}")
                        input_feature = recovered
                except Exception as e:
                    logger.warning(f"SINGLE_SELECTION: Recovery from saved FID failed: {e}")
            
            # Strategy 2: Try QGIS canvas selection ONLY if NOT in single_selection mode
            # FIX v8: In single_selection mode, the feature picker IS the source of truth
            if (input_feature is None or not input_feature.isValid()) and not is_single_selection_mode:
                qgis_selected = dw.current_layer.selectedFeatures()
                if len(qgis_selected) == 1:
                    input_feature = qgis_selected[0]
                    dw._last_single_selection_fid = input_feature.id()
                    dw._last_single_selection_layer_id = dw.current_layer.id()
                    logger.info(f"SINGLE_SELECTION: Using QGIS selection feature id={input_feature.id()}")
                elif len(qgis_selected) > 1:
                    # Multiple selected - use multiple selection mode
                    features, expression = self.get_exploring_features(qgis_selected, True)
                    dw._last_multiple_selection_fids = [f.id() for f in qgis_selected]
                    dw._last_multiple_selection_layer_id = dw.current_layer.id()
                    return features, expression
            
            # FIX v8: If still no feature and in single_selection mode, return empty
            # This is intentional - user needs to select a feature in the picker
            if input_feature is None or not input_feature.isValid():
                logger.debug(f"SINGLE_SELECTION: No feature available (single_mode={is_single_selection_mode})")
                return [], ''
        
        # CRITICAL FIX v6: Always reload feature from layer to ensure geometry
        if input_feature and input_feature.isValid():
            try:
                fid = input_feature.id()
                reloaded = dw.current_layer.getFeature(fid)
                if reloaded.isValid() and reloaded.hasGeometry():
                    logger.info(f"SINGLE_SELECTION: Reloaded feature id={fid} with geometry")
                    # Save FID for future recovery
                    dw._last_single_selection_fid = fid
                    dw._last_single_selection_layer_id = dw.current_layer.id()
                    return [reloaded], ""
                else:
                    # FIX 2026-01-16: Feature has no geometry - construct ID-based expression directly
                    logger.warning(f"SINGLE_SELECTION: Reloaded feature {fid} has no geometry - using ID expression")
                    dw._last_single_selection_fid = fid
                    dw._last_single_selection_layer_id = dw.current_layer.id()
                    
                    # Get layer properties to find primary key
                    layer_props = dw.PROJECT_LAYERS.get(dw.current_layer.id(), {})
                    pk_name = layer_props.get("infos", {}).get("primary_key_name")
                    
                    if pk_name:
                        # Try to get primary key value from feature
                        try:
                            pk_value = reloaded.attribute(pk_name)
                            # Quote string values
                            if isinstance(pk_value, str):
                                expression = f'"{pk_name}" = \'{pk_value}\''
                            else:
                                expression = f'"{pk_name}" = {pk_value}'
                            logger.info(f"SINGLE_SELECTION: Using PK expression: {expression}")
                            return [reloaded], expression
                        except Exception as e:
                            logger.warning(f"Could not get PK value: {e}")
                    
                    # Fallback to $id
                    expression = f'$id = {fid}'
                    logger.info(f"SINGLE_SELECTION: Using $id fallback: {expression}")
                    return [reloaded], expression
            except Exception as e:
                logger.warning(f"SINGLE_SELECTION: Could not reload feature: {e}")
        
        # FIX 2026-01-15 v7: If we reach here, input_feature is invalid - return empty
        # This aligns with before_migration behavior that returned [], '' on invalid input
        if input_feature is None or not input_feature.isValid():
            logger.warning(f"SINGLE_SELECTION: No valid feature available - returning empty")
            return [], ''
        
        logger.info(f"SINGLE_SELECTION valid feature: id={input_feature.id() if input_feature else 'None'}")
        return self.get_exploring_features(input_feature, True)
    
    def _get_multiple_selection_features(self):
        """
        Handle multiple selection feature retrieval with recovery logic.
        
        FIX 2026-01-15 v7: Aligned with before_migration behavior:
        - Returns [], '' if no items found after all recovery attempts
        - Saves FIDs for future recovery
        """
        dw = self._dockwidget
        widget = dw.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"]
        input_items = widget.checkedItems()
        
        logger.debug(f"MULTIPLE_SELECTION: widget.checkedItems() = {len(input_items) if input_items else 0}")
        
        # Try recovery if no items
        if not input_items or len(input_items) == 0:
            if (hasattr(dw, '_last_multiple_selection_fids') 
                and dw._last_multiple_selection_fids
                and dw.current_layer.id() == getattr(dw, '_last_multiple_selection_layer_id', None)):
                try:
                    input_items = [[str(fid), fid, None, None] for fid in dw._last_multiple_selection_fids]
                    logger.info(f"MULTIPLE_SELECTION: Recovered {len(input_items)} items from saved FIDs")
                except Exception as e:
                    logger.warning(f"MULTIPLE_SELECTION: Recovery failed: {e}")
                    input_items = []
        
        # Try QGIS canvas selection as fallback
        if not input_items or len(input_items) == 0:
            qgis_selected = dw.current_layer.selectedFeatures()
            if len(qgis_selected) > 0:
                logger.info(f"MULTIPLE_SELECTION: Using {len(qgis_selected)} features from QGIS canvas")
                features, expression = self.get_exploring_features(qgis_selected, True)
                dw._last_multiple_selection_fids = [f.id() for f in qgis_selected]
                dw._last_multiple_selection_layer_id = dw.current_layer.id()
                return features, expression
            else:
                # FIX 2026-01-15 v7: Return empty if no items after all recovery attempts
                logger.debug("MULTIPLE_SELECTION: No items selected anywhere - returning empty")
                return [], ''
        
        # Save FIDs for future recovery (from before_migration pattern)
        if input_items and len(input_items) > 0:
            try:
                checked_fids = [item[1] for item in input_items if len(item) > 1]
                if checked_fids:
                    dw._last_multiple_selection_fids = checked_fids
                    dw._last_multiple_selection_layer_id = dw.current_layer.id()
            except (IndexError, TypeError):
                pass
        
        logger.debug(f"MULTIPLE_SELECTION: {len(input_items) if input_items else 0} checked items")
        return self.get_exploring_features(input_items, True)
    
    def _get_custom_selection_features(self):
        """Handle custom expression feature retrieval."""
        dw = self._dockwidget
        from qgis.core import QgsExpression
        
        expression = dw.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].expression()
        logger.info(f"CUSTOM_SELECTION expression: '{expression}'")
        
        if not expression or not expression.strip():
            logger.warning("CUSTOM_SELECTION: Empty expression!")
            return [], ''
        
        # Validate expression
        qgs_expr = QgsExpression(expression)
        if qgs_expr.hasParserError():
            logger.warning(f"CUSTOM_SELECTION: Expression parse error: {qgs_expr.parserErrorString()}")
        
        # Save expression to layer_props
        if dw.current_layer.id() in dw.PROJECT_LAYERS:
            dw.PROJECT_LAYERS[dw.current_layer.id()]["exploring"]["custom_selection_expression"] = expression
        
        # Process expression
        features, expression = dw.exploring_custom_selection()
        logger.info(f"CUSTOM_SELECTION: {len(features)} features")
        
        return features, expression

    def get_exploring_features(self, input, identify_by_primary_key_name=False, custom_expression=None):
        """
        Get features based on input (QgsFeature, list, or expression).
        
        Migrated from dockwidget - v4.0 Sprint 2 (controller architecture).
        """
        if not self._dockwidget.widgets_initialized or self._dockwidget.current_layer is None:
            return [], None

        # v3.0.14: CRITICAL - Use centralized deletion check with full protection
        if self._dockwidget._is_layer_truly_deleted(self._dockwidget.current_layer):
            logger.debug("get_exploring_features: current_layer C++ object truly deleted")
            self._dockwidget.current_layer = None
            return [], None

        if self._dockwidget.current_layer is None:
            return [], None
        
        # Guard: Handle invalid input types (e.g., False from currentSelectedFeatures())
        if input is False or input is None:
            logger.debug("get_exploring_features: Input is False or None, returning empty")
            return [], None
        
        # STABILITY FIX: Verify layer exists in PROJECT_LAYERS before access
        if self._dockwidget.current_layer.id() not in self._dockwidget.PROJECT_LAYERS:
            logger.warning(f"get_exploring_features: Layer {self._dockwidget.current_layer.name()} not in PROJECT_LAYERS")
            return [], None
        
        from qgis.core import QgsFeature, QgsExpression, QgsFeatureRequest
        
        layer_props = self._dockwidget.PROJECT_LAYERS[self._dockwidget.current_layer.id()]
        features = []
        expression = None

        if isinstance(input, QgsFeature):
            # Check if input feature is valid
            if not input.isValid():
                logger.debug("get_exploring_features: Input feature is invalid, returning empty")
                return [], None
            
            # DIAGNOSTIC: Log input feature state
            logger.debug(f"get_exploring_features: input feature id={input.id()}, hasGeometry={input.hasGeometry()}")
                
            if identify_by_primary_key_name is True:
                # CRITICAL FIX: Check if primary_key_name exists in layer properties
                pk_name = layer_props["infos"].get("primary_key_name")
                
                if pk_name is None:
                    # Primary key not detected - use universal $id fallback
                    logger.debug(f"No primary_key_name in layer properties, using $id fallback")
                    provider_type = layer_props["infos"].get("layer_provider_type", "")
                    feature_id = input.id()
                    
                    # UNIVERSAL FALLBACK: Use $id which works for all providers
                    # $id is QGIS internal feature ID, works regardless of provider
                    expression = f'$id = {feature_id}'
                    logger.debug(f"Using universal $id fallback expression: {expression}")
                    
                    # For OGR layers, also try "fid" field as alternative
                    if provider_type == 'ogr':
                        # Check if fid field exists
                        fid_idx = self._dockwidget.current_layer.fields().indexFromName('fid')
                        if fid_idx >= 0:
                            expression = f'"fid" = {feature_id}'
                            logger.debug(f"OGR layer: using fid field expression: {expression}")
                    
                    # Always reload feature to ensure geometry is available
                    try:
                        reloaded_feature = self._dockwidget.current_layer.getFeature(input.id())
                        if reloaded_feature.isValid() and reloaded_feature.hasGeometry():
                            features = [reloaded_feature]
                            logger.debug(f"Reloaded feature {input.id()} with geometry")
                        else:
                            features = [input]
                            logger.warning(f"Could not reload feature {input.id()} with geometry")
                    except Exception as e:
                        logger.debug(f"Could not reload feature: {e}")
                        features = [input]
                    return features, expression
                
                # Try to get the primary key value using multiple methods
                pk_value = None
                try:
                    # First try with attribute() method
                    pk_value = input.attribute(pk_name)
                except (KeyError, IndexError):
                    try:
                        # Fallback to field index
                        fields = input.fields()
                        idx = fields.indexFromName(pk_name)
                        if idx >= 0:
                            pk_value = input.attributes()[idx]
                    except (AttributeError, IndexError, KeyError) as e:
                        logger.warning(f"Could not get primary key value for feature: {type(e).__name__}: {e}")
                        logger.debug(f"pk_name: {pk_name}, feature fields: {[f.name() for f in input.fields()]}")
                
                if pk_value is not None:
                    pk_is_numeric = layer_props["infos"].get("primary_key_is_numeric", False)
                    provider_type = layer_props["infos"].get("layer_provider_type", "")
                    
                    # CRITICAL FIX: Field names must be quoted for QgsExpression to work
                    # This applies to ALL providers (PostgreSQL, OGR, Spatialite)
                    # UUID FIX v4.0: Convert pk_value to string explicitly for non-numeric types
                    # Note: filter_task.py handles qualified names for PostgreSQL subsetString separately
                    if pk_is_numeric is True: 
                        expression = f'"{pk_name}" = {pk_value}'
                    else:
                        # Convert to string and escape single quotes for UUID, text, etc.
                        pk_value_str = str(pk_value).replace("'", "''")
                        expression = f'"{pk_name}" = \'{pk_value_str}\''
                    logger.debug(f"Generated expression for {provider_type}: {expression}")
                    
                    # CRITICAL: Also reload feature to ensure geometry is available for zoom
                    try:
                        reloaded_feature = self._dockwidget.current_layer.getFeature(input.id())
                        if reloaded_feature.isValid() and reloaded_feature.hasGeometry():
                            features = [reloaded_feature]
                            logger.debug(f"Reloaded feature {input.id()} with geometry")
                        else:
                            features = [input]
                    except Exception as e:
                        logger.debug(f"Could not reload feature: {e}")
                        features = [input]
                else:
                    # UNIVERSAL FALLBACK: If we can't get the primary key value, use $id
                    provider_type = layer_props["infos"].get("layer_provider_type", "")
                    feature_id = input.id()
                    
                    # Use $id as universal fallback - works for all providers
                    expression = f'$id = {feature_id}'
                    logger.debug(f"pk_value not found, using universal $id fallback: {expression}")
                    
                    # For OGR layers, also try "fid" field as alternative
                    if provider_type == 'ogr':
                        fid_idx = self._dockwidget.current_layer.fields().indexFromName('fid')
                        if fid_idx >= 0:
                            expression = f'"fid" = {feature_id}'
                            logger.debug(f"OGR layer fallback: using fid field expression: {expression}")
                    
                    # Reload feature from layer by ID for geometry
                    try:
                        reloaded_feature = self._dockwidget.current_layer.getFeature(input.id())
                        if reloaded_feature.isValid() and reloaded_feature.hasGeometry():
                            features = [reloaded_feature]
                        else:
                            features = [input]
                    except (RuntimeError, KeyError, AttributeError) as e:
                        features = [input]
                        logger.debug(f"Error reloading feature: {e}")
                    logger.debug(f"Could not access primary key '{pk_name}' in feature. "
                                f"Available fields: {[f.name() for f in input.fields()]}. Using $id fallback.")
            else:
                # CRITICAL: Reload feature from layer to ensure geometry is loaded
                # QgsFeaturePickerWidget.featureChanged may emit features without geometry
                try:
                    reloaded_feature = self._dockwidget.current_layer.getFeature(input.id())
                    if reloaded_feature.isValid() and reloaded_feature.hasGeometry():
                        features = [reloaded_feature]
                        logger.debug(f"Reloaded feature {input.id()} with geometry for tracking")
                    else:
                        features = [input]
                except Exception as e:
                    logger.debug(f"Could not reload feature {input.id()}: {e}")
                    features = [input]

        elif isinstance(input, list):
            if len(input) == 0 and custom_expression is None:
                return features, expression
            
            if identify_by_primary_key_name is True:
                # FALLBACK FIX: Safely get primary key with fallback to feature ID ($id)
                pk_name = layer_props["infos"].get("primary_key_name")
                pk_is_numeric = layer_props["infos"].get("primary_key_is_numeric", True)
                provider_type = layer_props["infos"].get("layer_provider_type", "")
                
                if pk_name is None:
                    # FALLBACK: Use feature IDs directly when no primary key is available
                    # input format from CustomCheckableFeatureComboBox: [(display_value, pk_value, ...), ...]
                    # When pk_name is None, feat[1] may be the feature id
                    logger.debug(f"No primary_key_name available for list input, using $id fallback")
                    try:
                        # Try to extract feature IDs from input
                        # Format depends on how the list was built
                        feature_ids = []
                        for feat in input:
                            if isinstance(feat, (list, tuple)) and len(feat) > 1:
                                # Assume feat[1] contains an ID-like value
                                feature_ids.append(str(feat[1]))
                            elif isinstance(feat, QgsFeature):
                                feature_ids.append(str(feat.id()))
                        
                        if feature_ids:
                            expression = f'$id IN ({", ".join(feature_ids)})'
                            logger.debug(f"Generated $id fallback expression: {expression}")
                    except Exception as e:
                        logger.warning(f"Could not generate fallback expression for list: {e}")
                        # Return features directly without expression if we can't build one
                        for feat in input:
                            if isinstance(feat, QgsFeature):
                                features.append(feat)
                        return features, None
                else:
                    # CRITICAL FIX: Field names must be quoted for QgsExpression to work
                    # This applies to ALL providers (PostgreSQL, OGR, Spatialite)
                    # FIX 2026-01-15 v7: Handle both tuple format and QgsFeature format
                    try:
                        input_ids = []
                        for feat in input:
                            if isinstance(feat, QgsFeature):
                                # QgsFeature - get primary key value
                                try:
                                    pk_value = feat.attribute(pk_name)
                                    if pk_value is not None:
                                        input_ids.append(str(pk_value))
                                except:
                                    input_ids.append(str(feat.id()))
                            elif isinstance(feat, (list, tuple)) and len(feat) > 1:
                                # Tuple format: (display, pk_value, ...)
                                input_ids.append(str(feat[1]))
                        
                        if not input_ids:
                            logger.warning("get_exploring_features: No valid IDs extracted from input list")
                            return [], None
                            
                        # UUID FIX v4.0: Ensure proper string conversion and quote escaping
                        if pk_is_numeric:
                            expression = f'"{pk_name}" IN ({", ".join(input_ids)})'
                        else:
                            # Escape single quotes in UUID/text values
                            escaped_ids = [id_val.replace("'", "''") for id_val in input_ids]
                            quoted_ids = "', '".join(escaped_ids)
                            expression = f'"{pk_name}" IN (\'{quoted_ids}\')'
                        logger.debug(f"Generated list expression for {provider_type}: {expression}")
                    except Exception as e:
                        logger.warning(f"get_exploring_features: Error building list expression: {e}")
                        # Fallback: return features directly if they are QgsFeature objects
                        for feat in input:
                            if isinstance(feat, QgsFeature):
                                features.append(feat)
                        return features, None
            
        if custom_expression is not None:
                expression = custom_expression

        if expression and QgsExpression(expression).isValid():
            # Synchronous evaluation for layers
            # PERFORMANCE FIX: Add limit to prevent UI freeze on unexpected large result sets
            MAX_SYNC_FEATURES = 10000  # Limit synchronous iteration
            features_iterator = self._dockwidget.current_layer.getFeatures(QgsFeatureRequest(QgsExpression(expression)))
            done_looping = False
            feature_count_iter = 0
            
            while not done_looping:
                try:
                    feature = next(features_iterator)
                    features.append(feature)
                    feature_count_iter += 1
                    # Safety limit to prevent UI freeze
                    if feature_count_iter >= MAX_SYNC_FEATURES:
                        logger.warning(f"get_exploring_features: Stopped at {MAX_SYNC_FEATURES} features to prevent UI freeze")
                        done_looping = True
                except StopIteration:
                    done_looping = True
        else:
            expression = None

        return features, expression

    def exploring_features_changed(self, input=[], identify_by_primary_key_name=False, custom_expression=None, preserve_filter_if_empty=False):
        """
        Handle feature selection changes in exploration widgets.
        
        NOTE: This function no longer automatically applies or clears layer filters.
        Filters are only applied via pushbutton actions (Filter, Unfilter, Reset).
        This function only handles feature selection, tracking (zoom), and expression storage.
        
        Args:
            input: Features or feature list to process
            identify_by_primary_key_name: Use primary key for identification
            custom_expression: Custom filter expression
            preserve_filter_if_empty: DEPRECATED - no longer needed since filters aren't auto-applied
        """
        if self._dockwidget.widgets_initialized is True and self._dockwidget.current_layer is not None and isinstance(self._dockwidget.current_layer, QgsVectorLayer):
            
            # CACHE INVALIDATION: Selection is changing, invalidate cache for current groupbox
            # This ensures that subsequent flash/zoom operations use fresh data
            if hasattr(self._dockwidget, '_exploring_cache') and self._dockwidget.current_exploring_groupbox:
                layer_id = self._dockwidget.current_layer.id()
                self._dockwidget._exploring_cache.invalidate(layer_id, self._dockwidget.current_exploring_groupbox)
                logger.debug(f"exploring_features_changed: Invalidated cache for {layer_id[:8]}.../{self._dockwidget.current_exploring_groupbox}")
            
            # v2.9.20: Save FID for single_selection mode to allow recovery after layer refresh
            # This is critical because QgsFeaturePickerWidget can lose its selection after
            # layer operations (filter/unfilter), causing FALLBACK MODE to use all features
            if self._dockwidget.current_exploring_groupbox == "single_selection" and isinstance(input, QgsFeature):
                if input.isValid() and input.id() is not None:
                    self._dockwidget._last_single_selection_fid = input.id()
                    self._dockwidget._last_single_selection_layer_id = self._dockwidget.current_layer.id()
                    logger.debug(f"exploring_features_changed: Saved single_selection FID={input.id()} for layer {self._dockwidget.current_layer.name()}")
            
            # v2.9.29: Save FIDs for multiple_selection mode to allow recovery after layer refresh
            # This is critical for multi-step additive filtering where the widget is refreshed
            # after the first filter, causing checked items to be lost.
            elif self._dockwidget.current_exploring_groupbox == "multiple_selection" and isinstance(input, list):
                if len(input) > 0:
                    # Input is list of [[display, pk, ...], ...] from updatingCheckedItemList signal
                    try:
                        # Extract PK values (index 1) from input items
                        checked_fids = [item[1] for item in input if len(item) > 1]
                        if checked_fids:
                            self._dockwidget._last_multiple_selection_fids = checked_fids
                            self._dockwidget._last_multiple_selection_layer_id = self._dockwidget.current_layer.id()
                            logger.debug(f"exploring_features_changed: Saved {len(checked_fids)} multiple_selection FIDs for layer {self._dockwidget.current_layer.name()}")
                    except (IndexError, TypeError) as e:
                        logger.debug(f"exploring_features_changed: Could not extract FIDs from input: {e}")
            
            # Update buffer validation when source features/layer changes
            try:
                self._dockwidget._update_buffer_validation()
            except Exception as e:
                logger.debug(f"Could not update buffer validation: {e}")
            
            # v3.0.14: CRITICAL - Use centralized deletion check with full protection
            if self._dockwidget._is_layer_truly_deleted(self._dockwidget.current_layer):
                logger.debug("exploring_features_changed: current_layer C++ object truly deleted")
                self._dockwidget.current_layer = None
                return []

            # Guard: Check if current_layer is in PROJECT_LAYERS
            if self._dockwidget.current_layer.id() not in self._dockwidget.PROJECT_LAYERS:
                logger.warning(f"exploring_features_changed: Layer {self._dockwidget.current_layer.name()} not in PROJECT_LAYERS")
                return []
            
            layer_props = self._dockwidget.PROJECT_LAYERS[self._dockwidget.current_layer.id()]
            features, expression = self.get_exploring_features(input, identify_by_primary_key_name, custom_expression)
            
            # PERFORMANCE (v2.5.10): Handle async evaluation for large layers with custom expressions
            # When get_exploring_features returns empty features but valid expression for large layers,
            # it means we should use async evaluation to prevent UI freeze
            if (len(features) == 0 and expression is not None 
                and custom_expression is not None
                and self._dockwidget.should_use_async_expression(custom_expression)):
                
                logger.info(f"exploring_features_changed: Using async evaluation for large layer")
                
                # Define callback to continue processing after async evaluation
                def _on_async_complete(async_features, async_expression, layer_id):
                    """Process features after async evaluation completes."""
                    if layer_id != self._dockwidget.current_layer.id():
                        logger.debug("Async evaluation completed for different layer, ignoring")
                        return
                    
                    # v3.1 Sprint 8: Use controller method instead of dockwidget
                    self.handle_exploring_features_result(
                        async_features, 
                        async_expression, 
                        layer_props,
                        identify_by_primary_key_name
                    )
                
                def _on_async_error(error_msg, layer_id):
                    """Handle async evaluation errors."""
                    show_warning(
                        self._dockwidget.tr("Expression Evaluation"),
                        self._dockwidget.tr(f"Error evaluating expression: {error_msg}")
                    )
                
                # Start async evaluation
                self._dockwidget.get_exploring_features_async(
                    expression=expression,
                    on_complete=_on_async_complete,
                    on_error=_on_async_error
                )
                
                # Store expression even though features aren't loaded yet
                if expression:
                    layer_props["filtering"]["current_filter_expression"] = expression
                
                return []  # Features will be processed in callback
     
            # Normal synchronous flow for smaller layers or non-custom expressions
            # Process results directly
            return self.handle_exploring_features_result(
                features, expression, layer_props, identify_by_primary_key_name
            )
        
        return []
    
    def handle_exploring_features_result(
        self,
        features,
        expression,
        layer_props,
        identify_by_primary_key_name=False
    ):
        """
        Handle the result of get_exploring_features (sync or async).
        
        v3.1 Sprint 8: Migrated from dockwidget._handle_exploring_features_result.
        FIX 2026-01-15 v5: Added auto-switch groupbox based on feature count.
        
        This method processes the features and expression returned by get_exploring_features,
        handling selection, tracking, and expression storage.
        
        Args:
            features: List of QgsFeature objects
            expression: Filter expression string
            layer_props: Layer properties dict from PROJECT_LAYERS
            identify_by_primary_key_name: Whether primary key was used
            
        Returns:
            List of features processed
        """
        dw = self._dockwidget
        
        if not dw.widgets_initialized or dw.current_layer is None:
            return []
        
        # FIX 2026-01-15 v5: Auto-switch groupbox based on feature count when is_selecting is active
        # This ensures the correct groupbox is shown when user selects from widgets
        feature_count = len(features)
        current_groupbox = dw.current_exploring_groupbox
        is_selecting_from_button = dw.pushButton_checkable_exploring_selecting.isChecked() if hasattr(dw, 'pushButton_checkable_exploring_selecting') else False
        
        if is_selecting_from_button and not getattr(dw, '_syncing_from_qgis', False):
            # Auto-switch only if not syncing from QGIS (to prevent infinite loops)
            if feature_count == 1 and current_groupbox == "multiple_selection":
                logger.info(f"handle_exploring_features_result: Auto-switching to single_selection (1 feature from widget)")
                try:
                    dw._force_exploring_groupbox_exclusive("single_selection")
                    dw._configure_single_selection_groupbox()
                except Exception as e:
                    logger.warning(f"Auto-switch to single_selection failed: {e}")
            elif feature_count > 1 and current_groupbox == "single_selection":
                logger.info(f"handle_exploring_features_result: Auto-switching to multiple_selection ({feature_count} features from widget)")
                try:
                    dw._force_exploring_groupbox_exclusive("multiple_selection")
                    dw._configure_multiple_selection_groupbox()
                except Exception as e:
                    logger.warning(f"Auto-switch to multiple_selection failed: {e}")
        
        # Link widgets if is_linking is enabled
        if layer_props.get("exploring", {}).get("is_linking", False):
            single_widget = dw.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
            multiple_widget = dw.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"]
            
            single_widget.blockSignals(True)
            multiple_widget.blockSignals(True)
            
            try:
                self.exploring_link_widgets()
            finally:
                single_widget.blockSignals(False)
                multiple_widget.blockSignals(False)
        
        # Store expression for filter task
        if expression is not None and expression != '':
            layer_props["filtering"]["current_filter_expression"] = expression
            logger.debug(f"handle_exploring_features_result: Stored expression: {expression[:60]}...")
        
        if len(features) == 0:
            logger.debug("handle_exploring_features_result: No features to process")
            # Clear selection if is_selecting is active
            if layer_props.get("exploring", {}).get("is_selecting", False):
                if not getattr(dw, '_syncing_from_qgis', False):
                    dw.current_layer.removeSelection()
            return []
        
        # Sync QGIS selection when is_selecting is active
        # FIX v4: Trust BUTTON state over PROJECT_LAYERS to handle desync
        is_selecting_from_props = layer_props.get("exploring", {}).get("is_selecting", False)
        is_selecting = is_selecting_from_props or is_selecting_from_button
        
        if is_selecting:
            if not getattr(dw, '_syncing_from_qgis', False):
                dw.current_layer.removeSelection()
                dw.current_layer.select([f.id() for f in features])
                logger.debug(f"handle_exploring_features_result: Synced QGIS selection ({len(features)} features)")
        
        # FIX v4: Zoom if is_tracking is active - trust BUTTON state over PROJECT_LAYERS
        is_tracking_from_props = layer_props.get("exploring", {}).get("is_tracking", False)
        is_tracking_from_button = dw.pushButton_checkable_exploring_tracking.isChecked() if hasattr(dw, 'pushButton_checkable_exploring_tracking') else False
        is_tracking = is_tracking_from_props or is_tracking_from_button
        
        if is_tracking:
            logger.info(f"handle_exploring_features_result: TRACKING {len(features)} features (props={is_tracking_from_props}, btn={is_tracking_from_button})")
            self.zooming_to_features(features)
        
        # Update button states
        dw._update_exploring_buttons_state()
        
        return features

    def exploring_link_widgets(self, expression=None, change_source=None):
        """
        Link single and multiple selection widgets based on IS_LINKING state.

        Args:
            expression: Optional filter expression to apply to single selection widget
            change_source: Optional source of the change ("single_selection", "multiple_selection")
                          Used for bidirectional display expression synchronization
        """
        if self._dockwidget.widgets_initialized and self._dockwidget.current_layer is not None:

            # CRITICAL: Verify layer exists in PROJECT_LAYERS before access
            if self._dockwidget.current_layer.id() not in self._dockwidget.PROJECT_LAYERS:
                logger.debug(f"exploring_link_widgets: Layer {self._dockwidget.current_layer.name()} not in PROJECT_LAYERS")
                return

            layer_props = self._dockwidget.PROJECT_LAYERS[self._dockwidget.current_layer.id()]
            custom_filter = None

            # Ensure is_linking property exists (backward compatibility)
            if "is_linking" not in layer_props["exploring"]:
                layer_props["exploring"]["is_linking"] = False

            # Helper function to set filter expression only if it changed
            def _safe_set_single_filter(new_filter):
                """Set filter expression on single selection widget only if changed."""
                single_widget = self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
                current_filter = single_widget.filterExpression() if hasattr(single_widget, 'filterExpression') else ''
                new_filter = new_filter or ''
                current_filter = current_filter or ''
                if new_filter.strip() != current_filter.strip():
                    logger.debug(f"exploring_link_widgets: Updating single selection filter: '{current_filter[:30]}' -> '{new_filter[:30]}'")
                    single_widget.setFilterExpression(new_filter)
                    return True
                return False

            if layer_props["exploring"]["is_linking"]:
                if QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isValid():
                    if not QgsExpression(layer_props["exploring"]["custom_selection_expression"]).isField():
                        custom_filter = layer_props["exploring"]["custom_selection_expression"]
                        self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setFilterExpression(custom_filter, layer_props)
                
                if expression is not None:
                    _safe_set_single_filter(expression)
                elif self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures() is not False:
                    features, expression = self.get_exploring_features(self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentSelectedFeatures(), True)
                    if len(features) > 0 and expression is not None:
                        _safe_set_single_filter(expression)
                elif self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentVisibleFeatures() is not False:
                    features, expression = self.get_exploring_features(self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].currentVisibleFeatures(), True)
                    if len(features) > 0 and expression is not None:
                        _safe_set_single_filter(expression)
                elif custom_filter is not None:
                    _safe_set_single_filter(custom_filter)

                # BIDIRECTIONAL DISPLAY EXPRESSION SYNCHRONIZATION
                multiple_display_expression = layer_props["exploring"]["multiple_selection_expression"]
                if QgsExpression(multiple_display_expression).isField():
                    multiple_display_expression = multiple_display_expression.replace('"','')

                single_display_expression = layer_props["exploring"]["single_selection_expression"]
                if QgsExpression(single_display_expression).isField():
                    single_display_expression = single_display_expression.replace('"','')

                # PROTECTION: Avoid infinite sync loops
                if change_source and change_source == self._dockwidget._last_expression_change_source:
                    logger.debug(f"exploring_link_widgets: Bidirectional sync from {change_source}")
                    self._dockwidget._last_expression_change_source = None

                    if change_source == "single_selection":
                        if single_display_expression != multiple_display_expression:
                            if QgsExpression(single_display_expression).isValid():
                                logger.info(f"🔗 SYNC: single -> multiple | '{single_display_expression}'")
                                self._dockwidget.PROJECT_LAYERS[self._dockwidget.current_layer.id()]["exploring"]["multiple_selection_expression"] = single_display_expression
                                self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression(single_display_expression)
                                self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(single_display_expression)

                    elif change_source == "multiple_selection":
                        if multiple_display_expression != single_display_expression:
                            if QgsExpression(multiple_display_expression).isValid():
                                logger.info(f"🔗 SYNC: multiple -> single | '{multiple_display_expression}'")
                                self._dockwidget.PROJECT_LAYERS[self._dockwidget.current_layer.id()]["exploring"]["single_selection_expression"] = multiple_display_expression
                                self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression(multiple_display_expression)
                                self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(multiple_display_expression)

                # LEGACY BEHAVIOR: Keep existing primary key swap logic as fallback
                elif QgsExpression(single_display_expression).isValid() and single_display_expression == layer_props["infos"]["primary_key_name"]:
                    if QgsExpression(multiple_display_expression).isValid() and multiple_display_expression != layer_props["infos"]["primary_key_name"]:
                        logger.debug(f"exploring_link_widgets: Swapping single (PK) -> multiple (descriptive)")
                        self._dockwidget.PROJECT_LAYERS[self._dockwidget.current_layer.id()]["exploring"]["single_selection_expression"] = multiple_display_expression
                        self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression(multiple_display_expression)
                        self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(multiple_display_expression)

                elif QgsExpression(multiple_display_expression).isValid() and multiple_display_expression == layer_props["infos"]["primary_key_name"]:
                    if QgsExpression(single_display_expression).isValid() and single_display_expression != layer_props["infos"]["primary_key_name"]:
                        logger.debug(f"exploring_link_widgets: Swapping multiple (PK) -> single (descriptive)")
                        self._dockwidget.PROJECT_LAYERS[self._dockwidget.current_layer.id()]["exploring"]["multiple_selection_expression"] = single_display_expression
                        self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"].setExpression(single_display_expression)
                        self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(single_display_expression)
            else:
                # When is_linking is False, only clear filter expressions if not already empty
                single_widget = self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
                multiple_widget = self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"]
                
                current_single_filter = single_widget.filterExpression() if hasattr(single_widget, 'filterExpression') else ''
                if current_single_filter and current_single_filter.strip() != '':
                    logger.debug(f"exploring_link_widgets: is_linking=False, clearing single selection filter")
                    single_widget.setFilterExpression('')
                
                if self._dockwidget.current_layer is not None and hasattr(multiple_widget, 'list_widgets') and self._dockwidget.current_layer.id() in multiple_widget.list_widgets:
                    current_multiple_filter = multiple_widget.list_widgets[self._dockwidget.current_layer.id()].getFilterExpression()
                    if current_multiple_filter and current_multiple_filter.strip() != '':
                        logger.debug(f"exploring_link_widgets: is_linking=False, clearing multiple selection filter")
                        multiple_widget.setFilterExpression('', layer_props)

    def exploring_source_params_changed(self, expression=None, groupbox_override=None, change_source=None):
        """
        Handle changes to source parameters for exploring features.

        Args:
            expression: Optional expression to use
            groupbox_override: Optional groupbox to target instead of current_exploring_groupbox
            change_source: Optional source of the change for bidirectional sync
        """
        if self._dockwidget.widgets_initialized is True and self._dockwidget.current_layer is not None:

            logger.debug(f"exploring_source_params_changed called with expression={expression}, groupbox_override={groupbox_override}, change_source={change_source}")

            if self._dockwidget.current_layer.id() not in self._dockwidget.PROJECT_LAYERS:
                logger.warning(f"exploring_source_params_changed: layer {self._dockwidget.current_layer.name()} not in PROJECT_LAYERS")
                return

            layer_props = self._dockwidget.PROJECT_LAYERS[self._dockwidget.current_layer.id()]
            target_groupbox = groupbox_override if groupbox_override is not None else self._dockwidget.current_exploring_groupbox
            logger.debug(f"target_groupbox={target_groupbox}")

            if target_groupbox == "single_selection":
                expression_widget = self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"]
                expression = expression_widget.expression()
                logger.debug(f"single_selection expression from widget: {expression}")
                
                if expression is not None and expression.strip() != '' and QgsExpression(expression).isValid():
                    current_expression = layer_props["exploring"]["single_selection_expression"]
                    if current_expression == expression:
                        logger.debug("single_selection: Expression unchanged, skipping setDisplayExpression")
                    else:
                        # v4.0 UUID FIX: Save user-selected field for this layer (persisted to SQLite)
                        self._dockwidget.PROJECT_LAYERS[self._dockwidget.current_layer.id()]["exploring"]["single_selection_expression"] = expression
                        
                        # Persist to SQLite if this is a user-initiated change (not auto-init)
                        if change_source and 'field' in change_source.lower():
                            logger.debug(f"Persisting single_selection field '{expression}' to SQLite for layer {self._dockwidget.current_layer.name()}")
                            from ...infrastructure.utils import is_layer_valid
                            if is_layer_valid(self._dockwidget.current_layer):
                                self._dockwidget.settingLayerVariable.emit(
                                    self._dockwidget.current_layer,
                                    [("exploring", "single_selection_expression")]
                                )
                        
                        try:
                            picker_widget = self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
                            # FIX 2026-01-15 v4: Save current feature to restore after rebuild
                            current_feature = picker_widget.feature()
                            current_fid = current_feature.id() if (current_feature and current_feature.isValid()) else None
                            
                            # Set display expression
                            picker_widget.setDisplayExpression(expression)
                            # CRITICAL: For QgsFeaturePickerWidget, must call setLayer() to force rebuild
                            picker_widget.setLayer(self._dockwidget.current_layer)
                            
                            # Restore feature if possible
                            if current_fid is not None:
                                try:
                                    picker_widget.setFeature(current_fid)
                                except:
                                    pass
                            
                            picker_widget.update()
                            logger.debug("single_selection: Updated display expression with layer rebuild")
                        except Exception as e:
                            logger.warning(f"single_selection: Could not force widget refresh: {e}")
                        
                        self.exploring_link_widgets(change_source=change_source)
                        self._dockwidget.invalidate_expression_cache(self._dockwidget.current_layer.id())
                elif expression is not None and expression.strip() != '':
                    logger.debug(f"single_selection: Expression '{expression}' is not valid, skipping update")

            elif target_groupbox == "multiple_selection":
                expression_widget = self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"]
                expression = expression_widget.expression()
                
                if expression is not None and expression.strip() != '' and QgsExpression(expression).isValid():
                    current_expression = layer_props["exploring"]["multiple_selection_expression"]
                    if current_expression == expression:
                        logger.debug("multiple_selection: Expression unchanged, skipping setDisplayExpression")
                    else:
                        # v4.0 UUID FIX: Save user-selected field for this layer (persisted to SQLite)
                        self._dockwidget.PROJECT_LAYERS[self._dockwidget.current_layer.id()]["exploring"]["multiple_selection_expression"] = expression
                        
                        # Persist to SQLite if this is a user-initiated change (not auto-init)
                        if change_source and 'field' in change_source.lower():
                            logger.debug(f"Persisting multiple_selection field '{expression}' to SQLite for layer {self._dockwidget.current_layer.name()}")
                            from ...infrastructure.utils import is_layer_valid
                            if is_layer_valid(self._dockwidget.current_layer):
                                self._dockwidget.settingLayerVariable.emit(
                                    self._dockwidget.current_layer,
                                    [("exploring", "multiple_selection_expression")]
                                )
                        logger.debug(f"Calling setDisplayExpression with: {expression}")
                        
                        try:
                            picker_widget = self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"]
                            
                            # FIX 2026-01-15 v4: Save checked items before rebuild
                            saved_checked_fids = None
                            layer_id = self._dockwidget.current_layer.id()
                            if hasattr(picker_widget, 'list_widgets') and layer_id in picker_widget.list_widgets:
                                try:
                                    saved_checked_fids = picker_widget.list_widgets[layer_id].getSelectedFeaturesList()
                                except:
                                    pass
                            
                            picker_widget.setDisplayExpression(expression)
                            # FIX v4: Call setLayer with layer_props to force full rebuild
                            picker_widget.setLayer(self._dockwidget.current_layer, layer_props, skip_task=True)
                            
                            # Restore checked items
                            if saved_checked_fids and hasattr(picker_widget, 'list_widgets') and layer_id in picker_widget.list_widgets:
                                try:
                                    picker_widget.list_widgets[layer_id].setSelectedFeaturesList(saved_checked_fids)
                                except:
                                    pass
                            
                            picker_widget.update()
                            logger.debug("multiple_selection: Updated display expression with layer rebuild")
                        except Exception as e:
                            logger.warning(f"multiple_selection: Could not force widget refresh: {e}")
                        
                        self.exploring_link_widgets(change_source=change_source)
                        self._dockwidget.invalidate_expression_cache(self._dockwidget.current_layer.id())
                elif expression is not None and expression.strip() != '':
                    logger.debug(f"multiple_selection: Expression '{expression}' is not valid, skipping update")

            elif target_groupbox == "custom_selection":
                expression = self._dockwidget.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"].expression()
                if expression is not None:
                    current_expression = layer_props["exploring"]["custom_selection_expression"]
                    if current_expression != expression:
                        self._dockwidget.PROJECT_LAYERS[self._dockwidget.current_layer.id()]["exploring"]["custom_selection_expression"] = expression
                        self._dockwidget.invalidate_expression_cache(self._dockwidget.current_layer.id())
                        
                        if hasattr(self._dockwidget, '_exploring_cache'):
                            self._dockwidget._exploring_cache.invalidate(self._dockwidget.current_layer.id(), "custom_selection")
                            logger.debug(f"custom_selection: Invalidated exploring cache")
                        
                        logger.debug("custom_selection: Expression stored, skipping immediate feature evaluation")
                        self._dockwidget._update_buffer_validation()
                        self._dockwidget._update_exploring_buttons_state()
                        return

            self._dockwidget.get_current_features()
            self._dockwidget._update_buffer_validation()

    def _reload_exploration_widgets(self, layer, layer_props):
        """
        Force reload of ALL exploration widgets with new layer data.
        
        Args:
            layer: The validated layer to use for widget updates
            layer_props: Layer properties dictionary
        """
        logger.info(f"=== ExploringController._reload_exploration_widgets ENTRY === layer: {layer.name() if layer else 'None'}, widgets_initialized: {self._dockwidget.widgets_initialized}")
        if not self._dockwidget.widgets_initialized:
            logger.warning("_reload_exploration_widgets: widgets not initialized, skipping")
            return
        
        logger.info(f"=== _reload_exploration_widgets called for layer: {layer.name() if layer else 'None'} ===")
        
        from qgis.core import QgsExpression
        from ...infrastructure.utils import get_best_display_field, is_layer_valid
        
        try:
            # Disconnect feature picker signals before updating widgets
            # NOTE 2026-01-15: Do NOT disconnect EXPRESSION signals here - they are managed
            # by _setup_expression_widget_direct_connections() which handles idempotent reconnection
            self._dockwidget.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'disconnect')
            self._dockwidget.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'disconnect')
            # REMOVED: Expression widget signals - managed separately (FIX-005)
            # self._dockwidget.manageSignal(["EXPLORING","SINGLE_SELECTION_EXPRESSION"], 'disconnect')
            # self._dockwidget.manageSignal(["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"], 'disconnect')
            # self._dockwidget.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'disconnect')
            
            # v4.0 SMART FIELD SELECTION: Upgrade primary-key-only expressions to better fields
            # Priority: 1) User's custom field (if set), 2) Best available field, 3) Primary key
            expressions_updated = False
            single_expr = layer_props["exploring"]["single_selection_expression"]
            multiple_expr = layer_props["exploring"]["multiple_selection_expression"]
            custom_expr = layer_props["exploring"]["custom_selection_expression"]
            
            # Get primary key to detect default (unset) expressions
            primary_key = layer_props.get("infos", {}).get("primary_key_name", "")
            logger.debug(f"Layer '{layer.name()}' expressions: single={single_expr}, multiple={multiple_expr}, custom={custom_expr}, pk={primary_key}")
            
            # Check if expressions are just the primary key (default from layer_management_task)
            # If so, try to upgrade to a better descriptive field
            should_upgrade_single = (single_expr == primary_key or not single_expr)
            should_upgrade_multiple = (multiple_expr == primary_key or not multiple_expr)
            should_upgrade_custom = (custom_expr == primary_key or not custom_expr)
            
            if should_upgrade_single or should_upgrade_multiple or should_upgrade_custom:
                # Get best available field (name, label, etc.)
                best_field = get_best_display_field(layer)
                logger.debug(f"Best field detected for layer '{layer.name()}': '{best_field}'")
                
                # FIX v4.0 + v4.1 Simon 2026-01-16: Comboboxes CANNOT be empty - must ALWAYS have a value
                # Garantir qu'il y a toujours un champ par défaut, même si get_best_display_field retourne vide
                if not best_field:
                    fields = layer.fields()
                    # Essayer de trouver le premier champ non-PK
                    best_field = None
                    for field in fields:
                        if field.name() != primary_key:
                            best_field = field.name()
                            break
                    
                    # Si tous les champs sont PK ou aucun champ, utiliser le premier champ ou PK
                    if not best_field:
                        if fields.count() > 0:
                            best_field = fields[0].name()
                        elif primary_key:
                            best_field = primary_key
                        else:
                            best_field = "$id"  # Fallback absolu
                    
                    logger.info(f"Forced fallback field '{best_field}' for layer '{layer.name()}' (get_best_display_field returned empty)")
                
                # TOUJOURS mettre à jour les expressions, même si best_field == primary_key
                # Ceci garantit que les combobox ne soient JAMAIS vides
                if best_field:
                    if should_upgrade_single:
                        layer_props["exploring"]["single_selection_expression"] = best_field
                        self._dockwidget.PROJECT_LAYERS[layer.id()]["exploring"]["single_selection_expression"] = best_field
                        expressions_updated = True
                        logger.info(f"✨ Set single_selection to '{best_field}' for layer '{layer.name()}'")
                    if should_upgrade_multiple:
                        layer_props["exploring"]["multiple_selection_expression"] = best_field
                        self._dockwidget.PROJECT_LAYERS[layer.id()]["exploring"]["multiple_selection_expression"] = best_field
                        expressions_updated = True
                        logger.info(f"✨ Set multiple_selection to '{best_field}' for layer '{layer.name()}'")
                    if should_upgrade_custom:
                        layer_props["exploring"]["custom_selection_expression"] = best_field
                        self._dockwidget.PROJECT_LAYERS[layer.id()]["exploring"]["custom_selection_expression"] = best_field
                        expressions_updated = True
                        logger.info(f"✨ Set custom_selection to '{best_field}' for layer '{layer.name()}'")
                    
                    # Persist upgraded field to SQLite for future sessions
                    if expressions_updated:
                        logger.debug(f"Persisting field '{best_field}' to SQLite for layer {layer.name()}")
                        if is_valid_layer(layer):
                            properties_to_save = []
                            if should_upgrade_single:
                                properties_to_save.append(("exploring", "single_selection_expression"))
                            if should_upgrade_multiple:
                                properties_to_save.append(("exploring", "multiple_selection_expression"))
                            if should_upgrade_custom:
                                properties_to_save.append(("exploring", "custom_selection_expression"))
                            self._dockwidget.settingLayerVariable.emit(layer, properties_to_save)
                        else:
                            logger.debug(f"_reload_exploration_widgets: layer became invalid, skipping signal emit")
                else:
                    logger.error(f"CRITICAL: No field could be determined for layer '{layer.name()}' - comboboxes may be empty!")
            else:
                # Expressions already customized (not equal to primary key)
                logger.debug(f"Using user-customized expressions for layer '{layer.name()}': single={single_expr}, multiple={multiple_expr}")
            
            # Update expressions after potential auto-initialization
            single_expr = layer_props["exploring"]["single_selection_expression"]
            multiple_expr = layer_props["exploring"]["multiple_selection_expression"]
            custom_expr = layer_props["exploring"]["custom_selection_expression"]
            
            # FIX v4.1 Simon 2026-01-16: GARANTIR que les expressions ne sont JAMAIS vides
            # Fallback absolu si une expression est vide (dernier rempart avant les widgets)
            if not single_expr:
                fields = layer.fields()
                if fields.count() > 0:
                    single_expr = fields[0].name()
                    layer_props["exploring"]["single_selection_expression"] = single_expr
                    self._dockwidget.PROJECT_LAYERS[layer.id()]["exploring"]["single_selection_expression"] = single_expr
                    logger.warning(f"Emergency fallback: Set single_selection to first field '{single_expr}'")
                else:
                    single_expr = "$id"
                    logger.error(f"CRITICAL: Layer '{layer.name()}' has no fields, using $id")
            
            if not multiple_expr:
                fields = layer.fields()
                if fields.count() > 0:
                    multiple_expr = fields[0].name()
                    layer_props["exploring"]["multiple_selection_expression"] = multiple_expr
                    self._dockwidget.PROJECT_LAYERS[layer.id()]["exploring"]["multiple_selection_expression"] = multiple_expr
                    logger.warning(f"Emergency fallback: Set multiple_selection to first field '{multiple_expr}'")
                else:
                    multiple_expr = "$id"
                    logger.error(f"CRITICAL: Layer '{layer.name()}' has no fields, using $id")
            
            if not custom_expr:
                fields = layer.fields()
                if fields.count() > 0:
                    custom_expr = fields[0].name()
                    layer_props["exploring"]["custom_selection_expression"] = custom_expr
                    self._dockwidget.PROJECT_LAYERS[layer.id()]["exploring"]["custom_selection_expression"] = custom_expr
                    logger.warning(f"Emergency fallback: Set custom_selection to first field '{custom_expr}'")
                else:
                    custom_expr = "$id"
                    logger.error(f"CRITICAL: Layer '{layer.name()}' has no fields, using $id")
            
            logger.info(f"FINAL expressions for layer '{layer.name()}': single={single_expr}, multiple={multiple_expr}, custom={custom_expr}")
            
            # Single selection widget
            if "SINGLE_SELECTION_FEATURES" in self._dockwidget.widgets.get("EXPLORING", {}):
                saved_fid = None
                saved_layer_id = None
                picker_widget = self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
                
                current_feature = picker_widget.feature() if picker_widget else None
                if current_feature and current_feature.isValid() and current_feature.id() is not None:
                    saved_fid = current_feature.id()
                    if picker_widget.layer():
                        saved_layer_id = picker_widget.layer().id()
                    logger.debug(f"_reload_exploration_widgets: Saved current feature FID={saved_fid} from widget")
                elif hasattr(self._dockwidget, '_last_single_selection_fid') and self._dockwidget._last_single_selection_fid is not None:
                    saved_fid = self._dockwidget._last_single_selection_fid
                    saved_layer_id = getattr(self._dockwidget, '_last_single_selection_layer_id', None)
                    logger.debug(f"_reload_exploration_widgets: Using saved _last_single_selection_fid={saved_fid}")
                
                picker_widget = self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
                picker_widget.setLayer(None)
                picker_widget.setLayer(layer)
                picker_widget.setDisplayExpression(single_expr)
                picker_widget.setFetchGeometry(True)
                picker_widget.setShowBrowserButtons(True)
                picker_widget.setAllowNull(True)
                # FIX 2026-01-15: Force visual refresh to display features
                picker_widget.update()
                picker_widget.repaint()
                
                if saved_fid is not None and layer is not None:
                    if saved_layer_id is None or saved_layer_id == layer.id():
                        logger.info(f"_reload_exploration_widgets: Restoring feature FID={saved_fid} after widget refresh")
                        try:
                            self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"].setFeature(saved_fid)
                            self._dockwidget._last_single_selection_fid = saved_fid
                            self._dockwidget._last_single_selection_layer_id = layer.id()
                        except Exception as e:
                            logger.warning(f"_reload_exploration_widgets: Failed to restore feature FID={saved_fid}: {e}")
                    else:
                        logger.debug(f"_reload_exploration_widgets: Layer changed, not restoring FID")
            
            # Multiple selection widget
            if "MULTIPLE_SELECTION_FEATURES" in self._dockwidget.widgets.get("EXPLORING", {}):
                saved_checked_fids = []
                saved_multi_layer_id = None
                multi_widget = self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"]
                
                if multi_widget and hasattr(multi_widget, 'checkedItems'):
                    try:
                        checked_items = multi_widget.checkedItems()
                        if checked_items:
                            saved_checked_fids = [item[1] for item in checked_items if len(item) > 1]
                            if multi_widget.layer:
                                saved_multi_layer_id = multi_widget.layer.id()
                            logger.info(f"_reload_exploration_widgets: Saved {len(saved_checked_fids)} checked items FIDs")
                    except Exception as e:
                        logger.debug(f"_reload_exploration_widgets: Could not save checked items: {e}")
                
                if not saved_checked_fids:
                    if hasattr(self._dockwidget, '_last_multiple_selection_fids') and self._dockwidget._last_multiple_selection_fids:
                        saved_checked_fids = self._dockwidget._last_multiple_selection_fids
                        saved_multi_layer_id = getattr(self._dockwidget, '_last_multiple_selection_layer_id', None)
                        logger.info(f"_reload_exploration_widgets: Using backup fids: {len(saved_checked_fids)}")
                
                self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setLayer(layer, layer_props, skip_task=True)
                self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_FEATURES"]["WIDGET"].setDisplayExpression(multiple_expr)
                
                if saved_checked_fids and layer is not None:
                    if saved_multi_layer_id is None or saved_multi_layer_id == layer.id():
                        logger.info(f"_reload_exploration_widgets: Restoring {len(saved_checked_fids)} checked items")
                        try:
                            if hasattr(multi_widget, 'list_widgets') and layer.id() in multi_widget.list_widgets:
                                list_widget_wrapper = multi_widget.list_widgets[layer.id()]
                                restored_selection = [[str(fid), fid, True] for fid in saved_checked_fids]
                                list_widget_wrapper.setSelectedFeaturesList(restored_selection)
                                logger.info(f"_reload_exploration_widgets: Restored {len(saved_checked_fids)} checked items")
                            
                            self._dockwidget._last_multiple_selection_fids = saved_checked_fids
                            self._dockwidget._last_multiple_selection_layer_id = layer.id()
                        except Exception as e:
                            logger.warning(f"_reload_exploration_widgets: Failed to restore checked items: {e}")
            
            # Field expression widgets
            # FIX 2026-01-15 + 2026-01-16: Use setField() for simple field names to properly select in combobox
            # Use setExpression() only for complex expressions. This fixes empty combobox issue.
            # FIX v4.1 Simon: Never pass empty string to setField() - always use first field as fallback
            if "SINGLE_SELECTION_EXPRESSION" in self._dockwidget.widgets.get("EXPLORING", {}):
                logger.info(f"Setting SINGLE_SELECTION_EXPRESSION widget: layer={layer.name()}, expression='{single_expr}'")
                widget = self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_EXPRESSION"]["WIDGET"]
                widget.setLayer(layer)
                # Use setField for simple field names, setExpression for complex expressions
                if single_expr and not QgsExpression(single_expr).isField():
                    widget.setExpression(single_expr)
                else:
                    # Ne JAMAIS passer une chaîne vide à setField - la sécurité ci-dessus garantit que single_expr n'est jamais vide
                    widget.setField(single_expr)
                logger.info(f"Widget expression after set: '{widget.expression()}'")
            
            if "MULTIPLE_SELECTION_EXPRESSION" in self._dockwidget.widgets.get("EXPLORING", {}):
                logger.info(f"Setting MULTIPLE_SELECTION_EXPRESSION widget: layer={layer.name()}, expression='{multiple_expr}'")
                widget = self._dockwidget.widgets["EXPLORING"]["MULTIPLE_SELECTION_EXPRESSION"]["WIDGET"]
                widget.setLayer(layer)
                # Use setField for simple field names, setExpression for complex expressions
                if multiple_expr and not QgsExpression(multiple_expr).isField():
                    widget.setExpression(multiple_expr)
                else:
                    # Ne JAMAIS passer une chaîne vide à setField
                    widget.setField(multiple_expr)
                logger.info(f"Widget expression after set: '{widget.expression()}'")
            
            if "CUSTOM_SELECTION_EXPRESSION" in self._dockwidget.widgets.get("EXPLORING", {}):
                logger.info(f"Setting CUSTOM_SELECTION_EXPRESSION widget: layer={layer.name()}, expression='{custom_expr}'")
                widget = self._dockwidget.widgets["EXPLORING"]["CUSTOM_SELECTION_EXPRESSION"]["WIDGET"]
                widget.setLayer(layer)
                # Use setField for simple field names, setExpression for complex expressions
                if custom_expr and not QgsExpression(custom_expr).isField():
                    widget.setExpression(custom_expr)
                else:
                    # Ne JAMAIS passer une chaîne vide à setField
                    widget.setField(custom_expr)
                logger.info(f"Widget expression after set: '{widget.expression()}'")

            
            # Reconnect signals
            self._dockwidget.manageSignal(["EXPLORING","SINGLE_SELECTION_FEATURES"], 'connect', 'featureChanged')
            self._dockwidget.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'updatingCheckedItemList')
            self._dockwidget.manageSignal(["EXPLORING","MULTIPLE_SELECTION_FEATURES"], 'connect', 'filteringCheckedItemList')
            # FIX 2026-01-14: MUST reconnect fieldChanged signals after widget layer update
            # These signals are CRITICAL for expression widget synchronization when layer changes
            self._dockwidget.manageSignal(["EXPLORING","SINGLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
            self._dockwidget.manageSignal(["EXPLORING","MULTIPLE_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
            self._dockwidget.manageSignal(["EXPLORING","CUSTOM_SELECTION_EXPRESSION"], 'connect', 'fieldChanged')
            
            # FIX 2026-01-15: manageSignal doesn't work for IDENTIFY/ZOOM/RESET - connect them directly
            # Reconnect after widget layer updates to ensure they remain functional
            for btn_name, btn_widget, handler in [
                ("IDENTIFY", self._dockwidget.pushButton_exploring_identify, self._dockwidget.exploring_identify_clicked),
                ("ZOOM", self._dockwidget.pushButton_exploring_zoom, self._dockwidget.exploring_zoom_clicked),
                ("RESET", self._dockwidget.pushButton_exploring_reset_layer_properties, lambda: self._dockwidget.resetLayerVariableEvent())
            ]:
                try:
                    btn_widget.clicked.disconnect(handler)
                except TypeError:
                    pass  # Not connected
                btn_widget.clicked.connect(handler)
                logger.debug(f"✓ Reconnected {btn_name} button")
            
            # DEBUG logging
            picker_widget = self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
            logger.debug(f"_reload_exploration_widgets complete:")
            logger.debug(f"  layer: {layer.name() if layer else 'None'}")
            logger.debug(f"  single_expr: {single_expr}")
            logger.debug(f"  picker layer: {picker_widget.layer().name() if picker_widget.layer() else 'None'}")
            logger.info(f"✓ Exploration widgets reloaded for layer {layer.name()}")
            
            # FIX 2026-01-15 (FIX-003b): CRITICAL - Ensure layer signals reconnected after reload
            # Widgets reload breaks selectionChanged connection - self-heal it
            if hasattr(self._dockwidget, '_ensure_layer_signals_connected'):
                self._dockwidget._ensure_layer_signals_connected(layer)
            else:
                logger.warning("_ensure_layer_signals_connected not available - signal may be lost!")
            
            # FIX 2026-01-15 (FIX-004): CRITICAL - Reconnect expression widget signals after reload
            # fieldChanged signals are lost during widget reload - reconnect them
            if hasattr(self._dockwidget, '_setup_expression_widget_direct_connections'):
                self._dockwidget._setup_expression_widget_direct_connections()
                logger.info("✓ Reconnected expression widget fieldChanged signals")
            else:
                logger.warning("_setup_expression_widget_direct_connections not available!")
                
        except (AttributeError, KeyError, RuntimeError) as e:
            error_type = type(e).__name__
            error_details = str(e)
            logger.warning(f"Error in _reload_exploration_widgets: {error_type}: {error_details}")
            logger.debug(f"Layer: {layer.name() if layer else 'None'}, widgets_initialized: {self._dockwidget.widgets_initialized}")
            
            if isinstance(e, KeyError):
                logger.debug(f"Missing key: {error_details}")

    # === Layer Selection Synchronization (v3.1 Sprint 7) ===
    
    def handle_layer_selection_changed(self, selected, deselected, clear_and_select) -> bool:
        """
        Handle QGIS layer selection change event.
        
        v3.1 Sprint 7: Migrated from dockwidget.on_layer_selection_changed.
        Synchronizes QGIS selection with FilterMate widgets when is_selecting is active.
        If is_tracking is active, zooms to selected features.
        
        FIX 2026-01-15 v5: Ensure selectionChanged signal stays connected for IS_TRACKING.
        
        Args:
            selected: List of added feature IDs
            deselected: List of removed feature IDs
            clear_and_select: Boolean indicating if selection was cleared
            
        Returns:
            True if handled successfully, False otherwise
        """
        # FIX v10: DEBUG - Entry point confirmation
        logger.info(f"🎯 ExploringController.handle_layer_selection_changed ENTERED: selected={len(selected)}, deselected={len(deselected)}")
        
        try:
            # FIX v5: Self-healing - ensure signal stays connected
            if self._dockwidget.current_layer and not self._dockwidget.current_layer_selection_connection:
                try:
                    self._dockwidget.current_layer.selectionChanged.connect(self._dockwidget.on_layer_selection_changed)
                    self._dockwidget.current_layer_selection_connection = True
                    logger.info("handle_layer_selection_changed: Re-connected selectionChanged (self-healing)")
                except (TypeError, RuntimeError):
                    pass
            # Check recursion prevention flag
            if getattr(self._dockwidget, '_syncing_from_qgis', False):
                logger.debug("handle_layer_selection_changed: Skipping (sync in progress)")
                return True
            
            # Block during filtering operations
            if getattr(self._dockwidget, '_filtering_in_progress', False):
                logger.debug("handle_layer_selection_changed: Skipping (filtering in progress)")
                return True
            
            if not self._dockwidget.widgets_initialized or not self._dockwidget.current_layer:
                return False
            
            layer_props = self._dockwidget.PROJECT_LAYERS.get(self._dockwidget.current_layer.id())
            if not layer_props:
                logger.error(f"handle_layer_selection_changed: No layer_props for layer!")
                return False
            
            is_selecting = layer_props.get("exploring", {}).get("is_selecting", False)
            is_tracking = layer_props.get("exploring", {}).get("is_tracking", False)
            
            # Check button states vs stored state (CRITICAL for debugging desync)
            btn_selecting = self._dockwidget.pushButton_checkable_exploring_selecting
            btn_tracking = self._dockwidget.pushButton_checkable_exploring_tracking
            selecting_button_checked = btn_selecting.isChecked()
            tracking_button_checked = btn_tracking.isChecked()
            
            # DIAGNOSTIC LOGGING v4
            logger.info("=" * 60)
            logger.info("handle_layer_selection_changed TRIGGERED")
            logger.info(f"  Layer: {self._dockwidget.current_layer.name()}")
            logger.info(f"  Selected IDs: {len(selected)}, Deselected: {len(deselected)}")
            logger.info(f"  is_selecting (PROJECT_LAYERS): {is_selecting}, Button: {selecting_button_checked}")
            logger.info(f"  is_tracking (PROJECT_LAYERS): {is_tracking}, Button: {tracking_button_checked}")
            logger.info(f"  Current groupbox: {self._dockwidget.current_exploring_groupbox}")
            
            # FIX v4: Detect and CORRECT mismatch for is_selecting
            if selecting_button_checked != is_selecting:
                logger.warning(f"  ⚠️ IS_SELECTING mismatch! Button={selecting_button_checked} PROJECT_LAYERS={is_selecting}")
                layer_id = self._dockwidget.current_layer.id()
                if layer_id in self._dockwidget.PROJECT_LAYERS:
                    self._dockwidget.PROJECT_LAYERS[layer_id]["exploring"]["is_selecting"] = selecting_button_checked
                    is_selecting = selecting_button_checked
                    logger.info(f"  ✅ Corrected is_selecting to {is_selecting}")
            
            # FIX v4: Detect and CORRECT mismatch for is_tracking  
            if tracking_button_checked != is_tracking:
                logger.warning(f"  ⚠️ IS_TRACKING mismatch! Button={tracking_button_checked} PROJECT_LAYERS={is_tracking}")
                layer_id = self._dockwidget.current_layer.id()
                if layer_id in self._dockwidget.PROJECT_LAYERS:
                    self._dockwidget.PROJECT_LAYERS[layer_id]["exploring"]["is_tracking"] = tracking_button_checked
                    is_tracking = tracking_button_checked
                    logger.info(f"  ✅ Corrected is_tracking to {is_tracking}")
            
            logger.info("=" * 60)
            
            # FIX v4: Sync widgets if BUTTON is checked (trust button state over PROJECT_LAYERS)
            should_sync = selecting_button_checked or is_selecting
            
            if should_sync:
                logger.info(f"📍 Syncing widgets (button={selecting_button_checked}, stored={is_selecting})")
                self._sync_widgets_from_qgis_selection()
            else:
                logger.debug(f"Skipping sync: button={selecting_button_checked}, stored={is_selecting}")
            
            # FIX v4: Zoom to selection when is_tracking is active (trust BUTTON state)
            # This ensures tracking works even when PROJECT_LAYERS is desynchronized
            if is_tracking or tracking_button_checked:
                selected_ids = self._dockwidget.current_layer.selectedFeatureIds()
                if len(selected_ids) > 0:
                    from qgis.core import QgsFeatureRequest
                    request = QgsFeatureRequest().setFilterFids(selected_ids)
                    features = list(self._dockwidget.current_layer.getFeatures(request))
                    logger.info(f"Tracking: zooming to {len(features)} features")
                    self.zooming_to_features(features)
            
            return True
            
        except Exception as e:
            logger.warning(f"Error in handle_layer_selection_changed: {type(e).__name__}: {e}")
            return False
    
    def _sync_widgets_from_qgis_selection(self) -> None:
        """
        Synchronize single and multiple selection widgets with QGIS selection.
        
        v3.1 Sprint 7: Migrated from dockwidget._sync_widgets_from_qgis_selection.
        Auto-switches groupbox based on selection count.
        """
        try:
            logger.info("🔄 _sync_widgets_from_qgis_selection CALLED")
            
            if not self._dockwidget.current_layer or not self._dockwidget.widgets_initialized:
                logger.warning("  ⚠️ Aborting: layer or widgets not initialized")
                return
            
            selected_features = self._dockwidget.current_layer.selectedFeatures()
            selected_count = len(selected_features)
            logger.info(f"  📊 Selected features count: {selected_count}")
            
            layer_props = self._dockwidget.PROJECT_LAYERS.get(self._dockwidget.current_layer.id())
            if not layer_props:
                logger.warning("  ⚠️ Aborting: No layer_props found")
                return
            
            current_groupbox = self._dockwidget.current_exploring_groupbox
            logger.info(f"  📦 Current groupbox: {current_groupbox}")
            
            # Auto-switch groupbox based on selection count
            if selected_count == 1 and current_groupbox == "multiple_selection":
                logger.info("  🔀 Auto-switching to single_selection groupbox (1 feature)")
                self._dockwidget._syncing_from_qgis = True
                try:
                    self._dockwidget._force_exploring_groupbox_exclusive("single_selection")
                    self._dockwidget._configure_single_selection_groupbox()
                    logger.info("  ✅ Switched to single_selection")
                finally:
                    self._dockwidget._syncing_from_qgis = False
                    
            elif selected_count > 1 and current_groupbox == "single_selection":
                logger.info(f"  🔀 Auto-switching to multiple_selection groupbox ({selected_count} features)")
                self._dockwidget._syncing_from_qgis = True
                try:
                    self._dockwidget._force_exploring_groupbox_exclusive("multiple_selection")
                    self._dockwidget._configure_multiple_selection_groupbox()
                    logger.info("  ✅ Switched to multiple_selection")
                finally:
                    self._dockwidget._syncing_from_qgis = False
            else:
                logger.info(f"  ℹ️ No groupbox switch needed (count={selected_count}, current={current_groupbox})")
            
            # Sync both widgets
            logger.info("  🔧 Syncing single selection widget...")
            self._sync_single_selection_from_qgis(selected_features, selected_count)
            logger.info("  🔧 Syncing multiple selection widget...")
            self._sync_multiple_selection_from_qgis(selected_features, selected_count)
            
            logger.info("  ✅ _sync_widgets_from_qgis_selection COMPLETED")
            
        except Exception as e:
            logger.warning(f"Error in _sync_widgets_from_qgis_selection: {type(e).__name__}: {e}")
    
    def _sync_single_selection_from_qgis(self, selected_features, selected_count) -> None:
        """
        Sync single selection widget with QGIS selection.
        
        v3.1 Sprint 7: Migrated from dockwidget._sync_single_selection_from_qgis.
        FIX 2026-01-15 v6: Also save FID for recovery and update button states.
        """
        try:
            if selected_count < 1:
                return
            
            feature = selected_features[0]
            feature_id = feature.id()
            
            feature_picker = self._dockwidget.widgets["EXPLORING"]["SINGLE_SELECTION_FEATURES"]["WIDGET"]
            current_feature = feature_picker.feature()
            
            # Skip if already showing this feature
            if current_feature and current_feature.isValid() and current_feature.id() == feature_id:
                logger.debug(f"_sync_single: Already showing feature {feature_id}")
                return
            
            logger.info(f"Syncing single selection to feature ID {feature_id}")
            
            self._dockwidget._syncing_from_qgis = True
            try:
                feature_picker.setFeature(feature_id)
                
                # FIX 2026-01-15 v6: Save FID for recovery
                self._dockwidget._last_single_selection_fid = feature_id
                self._dockwidget._last_single_selection_layer_id = self._dockwidget.current_layer.id()
                
                # FIX 2026-01-15: Force visual refresh
                feature_picker.update()
                feature_picker.repaint()
                
                # FIX 2026-01-15 v6: Update button states after sync
                self._dockwidget._update_exploring_buttons_state()
                
                logger.info(f"  ✓ Single selection synced to feature {feature_id}")
            finally:
                self._dockwidget._syncing_from_qgis = False
                
        except Exception as e:
            logger.warning(f"Error in _sync_single_selection_from_qgis: {type(e).__name__}: {e}")
    
    def _sync_multiple_selection_from_qgis(self, selected_features, selected_count) -> None:
        """
        Sync multiple selection widget with QGIS selection.
        
        FIX 2026-01-15 v4: Implement fallback when UILayoutController unavailable.
        """
        # Try delegation first
        if hasattr(self._dockwidget, '_controller_integration'):
            ci = self._dockwidget._controller_integration
            if ci and ci.delegate_sync_multiple_selection_from_qgis():
                return
        
        # FIX v4: Implement fallback synchronization
        # FIX v6: Also update button states after sync
        logger.info(f"_sync_multiple_selection_from_qgis: Syncing {selected_count} features to widget")
        try:
            if selected_count == 0:
                return
            
            # Get the multiple selection widget
            multi_widget = self._dockwidget.widgets.get("EXPLORING", {}).get("MULTIPLE_SELECTION_FEATURES", {}).get("WIDGET")
            if not multi_widget:
                logger.warning("_sync_multiple_selection_from_qgis: Multiple selection widget not found")
                return
            
            # Build the selection list from selected features
            feature_ids = [f.id() for f in selected_features if f and f.isValid()]
            if not feature_ids:
                return
            
            # Store FIDs for recovery
            self._dockwidget._last_multiple_selection_fids = feature_ids
            self._dockwidget._last_multiple_selection_layer_id = self._dockwidget.current_layer.id()
            
            # Update the widget's checked items
            self._dockwidget._syncing_from_qgis = True
            try:
                if hasattr(multi_widget, 'setCheckedFeatureIds'):
                    multi_widget.setCheckedFeatureIds(feature_ids)
                    logger.info(f"  ✓ Synced {len(feature_ids)} features to multiple selection widget")
                elif hasattr(multi_widget, 'list_widgets') and self._dockwidget.current_layer.id() in multi_widget.list_widgets:
                    # Alternative: use list_widgets
                    list_widget = multi_widget.list_widgets[self._dockwidget.current_layer.id()]
                    if hasattr(list_widget, 'setSelectedFeaturesList'):
                        selection_data = [[str(fid), fid, True] for fid in feature_ids]
                        list_widget.setSelectedFeaturesList(selection_data)
                        logger.info(f"  ✓ Synced {len(feature_ids)} features via list_widget")
                
                # FIX 2026-01-15 v6: Update button states after sync
                self._dockwidget._update_exploring_buttons_state()
            finally:
                self._dockwidget._syncing_from_qgis = False
                
        except Exception as e:
            logger.warning(f"_sync_multiple_selection_from_qgis error: {type(e).__name__}: {e}")

    # === Utility ===

    def __repr__(self) -> str:
        """String representation for debugging."""
        layer_name = self._current_layer.name() if self._current_layer else 'None'
        return (
            f"<ExploringController "
            f"layer={layer_name} "
            f"field={self._current_field} "
            f"selected={len(self._selected_features)}>"
        )
