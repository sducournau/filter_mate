"""
UILayoutController - Interface Layout Management.

Handles UI layout operations including widget alignment, spacing,
action bar positioning, and groupbox configuration.

Story: v4.0 Sprint 4
Phase: 6 - God Class DockWidget Migration
Pattern: Strangler Fig - Gradual extraction from filter_mate_dockwidget.py
"""

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

try:
    from qgis.PyQt.QtCore import Qt, QSize
    from qgis.PyQt.QtWidgets import (
        QWidget, QHBoxLayout, QVBoxLayout, QLayout, QFrame,
        QSizePolicy, QPushButton
    )
except ImportError:
    from PyQt5.QtCore import Qt, QSize
    from PyQt5.QtWidgets import (
        QWidget, QHBoxLayout, QVBoxLayout, QLayout, QFrame,
        QSizePolicy, QPushButton
    )

from .base_controller import BaseController

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class UILayoutController(BaseController):
    """
    Controller for UI layout management.
    
    Handles:
    - Multiple selection sync from QGIS
    - Key layout alignment
    - Action bar wrapper creation
    - Checkable pushbutton harmonization
    - Layout spacing management
    - Widget dimension configuration
    
    v4.0 Sprint 4: New controller for UI layout operations.
    
    Example:
        controller = UILayoutController(dockwidget)
        controller.setup()
        controller.sync_multiple_selection_from_qgis()
    """
    
    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the UI layout controller.
        
        Args:
            dockwidget: Main dockwidget reference
        """
        super().__init__(dockwidget)
        
        # Layout configuration
        self._default_spacing = 6
        self._compact_spacing = 4
        self._default_margin = 9
        self._compact_margin = 6
    
    def setup(self) -> None:
        """Initialize the controller."""
        self._is_initialized = True
        logger.debug("UILayoutController setup complete")
    
    def teardown(self) -> None:
        """Cleanup controller resources."""
        self._is_initialized = False
        logger.debug("UILayoutController teardown complete")
    
    def on_tab_activated(self) -> None:
        """Handle tab activation."""
        pass  # Layout controller is passive
    
    # =========================================================================
    # Sprint 4: Layout Management Methods
    # =========================================================================
    
    def sync_multiple_selection_from_qgis(self) -> bool:
        """
        Synchronize multiple selection from QGIS layer selection.
        
        Migrated from filter_mate_dockwidget._sync_multiple_selection_from_qgis.
        
        v4.0 Sprint 4: Full migration from dockwidget.
        FIX 2026-01-14: Complete rewrite to match before_migration implementation.
        
        When QGIS layer selection changes, update the FilterMate multiple
        selection widget to reflect the same selection (CHECK/UNCHECK items).
        
        Returns:
            True if sync completed, False otherwise
        """
        dw = self.dockwidget
        
        # Guard: widgets must be initialized
        if not getattr(dw, 'widgets_initialized', False):
            return False
        
        # Guard: must have current layer
        current_layer = getattr(dw, 'current_layer', None)
        if current_layer is None:
            return False
        
        # Get the multiple selection widget
        widgets = getattr(dw, 'widgets', {})
        multi_widget = widgets.get("EXPLORING", {}).get(
            "MULTIPLE_SELECTION_FEATURES", {}
        ).get("WIDGET")
        
        if multi_widget is None:
            logger.warning("sync_multiple_selection_from_qgis: widget not found")
            return False
        
        # FIX 2026-01-14: Use list_widgets API like before_migration
        if not hasattr(multi_widget, 'list_widgets'):
            logger.debug("sync_multiple_selection_from_qgis: No list_widgets attribute")
            return False
        
        layer_id = current_layer.id()
        if layer_id not in multi_widget.list_widgets:
            logger.debug(f"sync_multiple_selection_from_qgis: Layer {layer_id} not in list_widgets")
            return False
        
        list_widget = multi_widget.list_widgets[layer_id]
        
        # Get layer properties to find primary key field
        project_layers = getattr(dw, 'PROJECT_LAYERS', {})
        layer_props = project_layers.get(layer_id, {})
        pk_field_name = layer_props.get("infos", {}).get("primary_key_name", None)
        
        if not pk_field_name:
            logger.warning("sync_multiple_selection_from_qgis: No primary_key_name found")
            return False
        
        # Get widget's identifier field for comparison
        widget_identifier_field = list_widget.getIdentifierFieldName() if hasattr(list_widget, 'getIdentifierFieldName') else None
        effective_pk_field = widget_identifier_field if widget_identifier_field else pk_field_name
        
        # Get selected features from QGIS
        selected_features = current_layer.selectedFeatures()
        
        # Extract PRIMARY KEY VALUES (not feature IDs!) from selected features
        selected_pk_values = set()
        for f in selected_features:
            try:
                pk_value = f[effective_pk_field]
                selected_pk_values.add(str(pk_value) if pk_value is not None else pk_value)
            except (KeyError, IndexError) as e:
                logger.debug(f"Could not get field '{effective_pk_field}' from feature: {e}")
                selected_pk_values.add(str(f.id()))
        
        logger.debug(f"sync_multiple_selection_from_qgis: {len(selected_pk_values)} pk values to sync")
        
        # Set sync flag to prevent infinite recursion
        dw._syncing_from_qgis = True
        
        try:
            checked_count = 0
            unchecked_count = 0
            
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                item_pk_value = item.data(3)  # data(3) = PRIMARY KEY value
                item_pk_str = str(item_pk_value) if item_pk_value is not None else item_pk_value
                
                if item_pk_str in selected_pk_values:
                    # CHECK features selected in QGIS
                    if item.checkState() != Qt.Checked:
                        item.setCheckState(Qt.Checked)
                        checked_count += 1
                else:
                    # UNCHECK features not selected in QGIS
                    if item.checkState() != Qt.Unchecked:
                        item.setCheckState(Qt.Unchecked)
                        unchecked_count += 1
            
            logger.debug(f"sync_multiple_selection_from_qgis: checked={checked_count}, unchecked={unchecked_count}")
            
            # Force visual refresh
            multi_widget.update()
            multi_widget.repaint()
            
            return True
            
        except Exception as e:
            logger.warning(f"sync_multiple_selection_from_qgis error: {e}")
            return False
        finally:
            dw._syncing_from_qgis = False
    
    def align_key_layouts(self) -> bool:
        """
        Align key layouts for consistent spacing.
        
        Migrated from filter_mate_dockwidget._align_key_layouts.
        
        v4.0 Sprint 4: Full migration from dockwidget.
        
        Ensures that key layouts (filtering, exploring, exporting)
        have consistent alignment and spacing.
        
        Returns:
            True if alignment completed, False otherwise
        """
        dw = self.dockwidget
        
        # Guard: widgets must be initialized
        if not getattr(dw, 'widgets_initialized', False):
            return False
        
        # Key layout groups to align
        layout_groups = [
            ('FILTERING', ['SOURCE_LAYER', 'LAYERS_TO_FILTER', 'PREDICATES']),
            ('EXPLORING', ['SINGLE_SELECTION', 'MULTIPLE_SELECTION', 'CUSTOM_SELECTION']),
            ('EXPORTING', ['LAYERS', 'PROJECTION', 'OUTPUT'])
        ]
        
        widgets = getattr(dw, 'widgets', {})
        
        for group_name, widget_names in layout_groups:
            if group_name not in widgets:
                continue
            
            group_widgets = widgets[group_name]
            
            # Find maximum label width
            max_label_width = 0
            
            for widget_name in widget_names:
                if widget_name not in group_widgets:
                    continue
                
                widget_info = group_widgets[widget_name]
                label = widget_info.get('LABEL')
                
                if label and hasattr(label, 'sizeHint'):
                    label_width = label.sizeHint().width()
                    max_label_width = max(max_label_width, label_width)
            
            # Apply maximum width to all labels
            if max_label_width > 0:
                for widget_name in widget_names:
                    if widget_name not in group_widgets:
                        continue
                    
                    widget_info = group_widgets[widget_name]
                    label = widget_info.get('LABEL')
                    
                    if label and hasattr(label, 'setMinimumWidth'):
                        label.setMinimumWidth(max_label_width)
        
        logger.debug("align_key_layouts: alignment complete")
        return True
    
    def create_horizontal_wrapper_for_side_action_bar(
        self,
        main_widget: QWidget,
        action_bar_widget: QWidget,
        position: str = 'right'
    ) -> Optional[QWidget]:
        """
        Create horizontal wrapper for side action bar.
        
        Migrated from filter_mate_dockwidget._create_horizontal_wrapper_for_side_action_bar.
        
        v4.0 Sprint 4: Full migration from dockwidget.
        
        Creates a horizontal layout with main widget and action bar
        positioned on the side (left or right).
        
        Args:
            main_widget: The main widget (content area)
            action_bar_widget: The action bar widget
            position: 'left' or 'right' for action bar position
            
        Returns:
            QWidget with horizontal layout, or None if failed
        """
        try:
            # Create container widget
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            
            # Add widgets based on position
            if position == 'left':
                layout.addWidget(action_bar_widget)
                layout.addWidget(main_widget)
            else:  # right (default)
                layout.addWidget(main_widget)
                layout.addWidget(action_bar_widget)
            
            # Configure stretch
            layout.setStretch(0, 0 if position == 'left' else 1)
            layout.setStretch(1, 1 if position == 'left' else 0)
            
            logger.debug(f"create_horizontal_wrapper: created with position={position}")
            return container
            
        except Exception as e:
            logger.warning(f"create_horizontal_wrapper failed: {e}")
            return None
    
    def harmonize_checkable_pushbuttons(self) -> bool:
        """
        Harmonize checkable pushbutton appearance.
        
        Migrated from filter_mate_dockwidget._harmonize_checkable_pushbuttons.
        
        v4.0 Sprint 4: Full migration from dockwidget.
        
        Ensures all checkable pushbuttons have consistent styling
        for checked/unchecked states.
        
        Returns:
            True if harmonization completed, False otherwise
        """
        dw = self.dockwidget
        
        # Guard: widgets must be initialized
        if not getattr(dw, 'widgets_initialized', False):
            return False
        
        widgets = getattr(dw, 'widgets', {})
        
        # Find all checkable pushbuttons
        checkable_buttons = []
        
        for group_name, group_widgets in widgets.items():
            if not isinstance(group_widgets, dict):
                continue
            
            for widget_name, widget_info in group_widgets.items():
                if not isinstance(widget_info, dict):
                    continue
                
                widget_type = widget_info.get('TYPE')
                widget = widget_info.get('WIDGET')
                
                if widget_type == 'PushButton' and widget:
                    if hasattr(widget, 'isCheckable') and widget.isCheckable():
                        checkable_buttons.append(widget)
        
        # Apply harmonized styling
        for button in checkable_buttons:
            try:
                # Ensure button has proper size policy
                button.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
                
                # Set minimum height for consistency
                if hasattr(button, 'setMinimumHeight'):
                    button.setMinimumHeight(24)
                
            except Exception as e:
                logger.debug(f"Error harmonizing button: {e}")
        
        logger.debug(f"harmonize_checkable_pushbuttons: harmonized {len(checkable_buttons)} buttons")
        return True
    
    def apply_layout_spacing(
        self,
        layout: QLayout,
        spacing: int = None,
        margins: int = None
    ) -> bool:
        """
        Apply spacing and margins to a layout.
        
        v4.0 Sprint 4: Helper method for consistent spacing.
        
        Args:
            layout: The layout to configure
            spacing: Spacing value (uses default if None)
            margins: Margins value (uses default if None)
            
        Returns:
            True if applied, False otherwise
        """
        if layout is None:
            return False
        
        try:
            # Apply spacing
            if spacing is not None:
                layout.setSpacing(spacing)
            else:
                layout.setSpacing(self._default_spacing)
            
            # Apply margins
            margin_value = margins if margins is not None else self._default_margin
            layout.setContentsMargins(margin_value, margin_value, margin_value, margin_value)
            
            return True
            
        except Exception as e:
            logger.warning(f"apply_layout_spacing failed: {e}")
            return False
    
    def apply_compact_layout(self, layout: QLayout) -> bool:
        """
        Apply compact spacing to a layout.
        
        v4.0 Sprint 4: Helper for compact mode.
        
        Args:
            layout: The layout to configure
            
        Returns:
            True if applied, False otherwise
        """
        return self.apply_layout_spacing(
            layout,
            spacing=self._compact_spacing,
            margins=self._compact_margin
        )
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def get_widget_dimensions(self, widget: QWidget) -> Dict[str, int]:
        """
        Get widget dimensions.
        
        Args:
            widget: The widget to measure
            
        Returns:
            dict with 'width' and 'height' keys
        """
        if widget is None:
            return {'width': 0, 'height': 0}
        
        size = widget.size()
        return {
            'width': size.width(),
            'height': size.height()
        }
    
    def set_widget_fixed_size(
        self,
        widget: QWidget,
        width: int = None,
        height: int = None
    ) -> bool:
        """
        Set widget fixed size.
        
        Args:
            widget: The widget to configure
            width: Fixed width (None to skip)
            height: Fixed height (None to skip)
            
        Returns:
            True if applied, False otherwise
        """
        if widget is None:
            return False
        
        try:
            if width is not None and height is not None:
                widget.setFixedSize(QSize(width, height))
            elif width is not None:
                widget.setFixedWidth(width)
            elif height is not None:
                widget.setFixedHeight(height)
            
            return True
            
        except Exception as e:
            logger.warning(f"set_widget_fixed_size failed: {e}")
            return False
