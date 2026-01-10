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
        QgsRectangle
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
        
        # Cache for feature values
        self._features_cache = features_cache
        if self._features_cache is None:
            try:
                from infrastructure.cache import ExploringFeaturesCache
                self._features_cache = ExploringFeaturesCache(
                    max_layers=50,
                    max_age_seconds=300.0
                )
            except ImportError:
                self._features_cache = None
                logger.warning("ExploringFeaturesCache not available")

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
        """
        if not self.is_layer_valid(layer):
            layer = None
        
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
