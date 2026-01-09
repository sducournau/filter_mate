"""
Dimensions Manager for FilterMate.

Handles widget dimension management based on UI profiles (compact/normal).
Extracted from filter_mate_dockwidget.py (lines 848-1041, 1334-1403).

Story: MIG-062
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, Dict, Any
import logging

from qgis.PyQt.QtCore import QSize, Qt
from qgis.PyQt.QtWidgets import (
    QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox, QGroupBox,
    QPushButton, QSizePolicy, QSpacerItem
)
from qgis.gui import (
    QgsFeaturePickerWidget, QgsFieldExpressionWidget,
    QgsProjectionSelectionWidget, QgsMapLayerComboBox,
    QgsFieldComboBox, QgsCheckableComboBox, QgsPropertyOverrideButton
)

from .base_manager import LayoutManagerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class DimensionsManager(LayoutManagerBase):
    """
    Manages widget dimensions based on active UI profile.
    
    Handles sizing for:
    - Dockwidget minimum/preferred size
    - Frame dimensions
    - Widget dimensions (buttons, inputs, etc.)
    - QGIS-specific widget dimensions
    
    Extracted methods from dockwidget:
    - apply_dynamic_dimensions() -> apply()
    - _apply_dockwidget_dimensions()
    - _apply_widget_dimensions()
    - _apply_frame_dimensions()
    - _apply_qgis_widget_dimensions()
    - _harmonize_checkable_pushbuttons()
    - _apply_layout_spacing()
    - _harmonize_spacers()
    - _align_key_layouts()
    - _adjust_row_spacing()
    
    Attributes:
        _config: Current dimension configuration from UIConfig
    
    Example:
        manager = DimensionsManager(dockwidget)
        manager.setup()
        
        # After profile change:
        manager.apply()
    """
    
    # Size policy mapping
    POLICY_MAP = {
        'Fixed': QSizePolicy.Fixed,
        'Minimum': QSizePolicy.Minimum,
        'Maximum': QSizePolicy.Maximum,
        'Preferred': QSizePolicy.Preferred,
        'Expanding': QSizePolicy.Expanding,
        'MinimumExpanding': QSizePolicy.MinimumExpanding,
        'Ignored': QSizePolicy.Ignored
    }
    
    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the DimensionsManager.
        
        Args:
            dockwidget: The main FilterMate dockwidget instance
        """
        super().__init__(dockwidget)
        self._config: Dict[str, Any] = {}
        self._ui_config = None  # Lazy-loaded UIConfig
    
    def _get_ui_config(self):
        """Lazy load UIConfig to avoid circular imports."""
        if self._ui_config is None:
            from modules.ui_config import UIConfig
            self._ui_config = UIConfig
        return self._ui_config
    
    def setup(self) -> None:
        """
        Setup initial dimensions based on active UI profile.
        
        Loads configuration from UIConfig and applies dimensions
        to all managed widgets.
        """
        self.apply()
        self._initialized = True
        logger.debug("DimensionsManager setup complete")
    
    def apply(self) -> None:
        """
        Apply dimensions based on current profile.
        
        Orchestrates the application of dimensions by calling specialized methods.
        Called when profile changes (compact/normal).
        """
        try:
            # Apply dockwidget minimum size based on profile
            self.apply_dockwidget_dimensions()
            
            # Apply dimensions in logical groups
            self.apply_widget_dimensions()
            self.apply_frame_dimensions()
            self.harmonize_checkable_pushbuttons()
            self.apply_layout_spacing()
            self.harmonize_spacers()
            self.apply_qgis_widget_dimensions()
            self.align_key_layouts()
            self.adjust_row_spacing()
            
            logger.info("DimensionsManager: Applied dynamic dimensions to all widgets")
            
        except Exception as e:
            logger.error(f"DimensionsManager: Error applying dynamic dimensions: {e}")
            import traceback
            traceback.print_exc()
    
    def apply_dockwidget_dimensions(self) -> None:
        """
        Apply minimum size to the dockwidget based on active UI profile.
        
        This ensures the dockwidget can be resized smaller in compact mode,
        allowing better screen space management.
        """
        UIConfig = self._get_ui_config()
        
        # Get dockwidget dimensions from active profile
        min_width = UIConfig.get_config('dockwidget', 'min_width')
        min_height = UIConfig.get_config('dockwidget', 'min_height')
        preferred_width = UIConfig.get_config('dockwidget', 'preferred_width')
        preferred_height = UIConfig.get_config('dockwidget', 'preferred_height')
        
        if min_width and min_height:
            self.dockwidget.setMinimumSize(QSize(min_width, min_height))
            logger.debug(f"Applied dockwidget minimum size: {min_width}x{min_height}px")
        
        # Set a reasonable preferred size (not enforced, just a hint)
        if preferred_width and preferred_height:
            # Only resize if current size is larger than preferred (don't expand small windows)
            current_size = self.dockwidget.size()
            if current_size.width() > preferred_width or current_size.height() > preferred_height:
                self.dockwidget.resize(preferred_width, preferred_height)
                logger.debug(f"Resized dockwidget to preferred size: {preferred_width}x{preferred_height}px")
    
    def apply_widget_dimensions(self) -> None:
        """
        Apply dimensions to standard Qt widgets (ComboBox, LineEdit, SpinBox, GroupBox).
        
        Reads dimensions from UIConfig and applies them to all relevant widgets
        using findChildren() for batch processing.
        """
        UIConfig = self._get_ui_config()
        
        # Get dimensions from active profile
        combobox_height = UIConfig.get_config('combobox', 'height')
        input_height = UIConfig.get_config('input', 'height')
        groupbox_min_height = UIConfig.get_config('groupbox', 'min_height')
        
        # Apply to ComboBoxes
        for combo in self.dockwidget.findChildren(QComboBox):
            combo.setMinimumHeight(combobox_height)
            combo.setMaximumHeight(combobox_height)
            combo.setSizePolicy(combo.sizePolicy().horizontalPolicy(), 
                              QSizePolicy.Fixed)
        
        # Apply to LineEdits
        for line_edit in self.dockwidget.findChildren(QLineEdit):
            line_edit.setMinimumHeight(input_height)
            line_edit.setMaximumHeight(input_height)
            line_edit.setSizePolicy(line_edit.sizePolicy().horizontalPolicy(), 
                                   QSizePolicy.Fixed)
        
        # Apply to SpinBoxes (QDoubleSpinBox and QSpinBox)
        for spinbox in self.dockwidget.findChildren(QDoubleSpinBox):
            spinbox.setMinimumHeight(input_height)
            spinbox.setMaximumHeight(input_height)
            spinbox.setSizePolicy(spinbox.sizePolicy().horizontalPolicy(), 
                                QSizePolicy.Fixed)
        
        for spinbox in self.dockwidget.findChildren(QSpinBox):
            spinbox.setMinimumHeight(input_height)
            spinbox.setMaximumHeight(input_height)
            spinbox.setSizePolicy(spinbox.sizePolicy().horizontalPolicy(), 
                                QSizePolicy.Fixed)
        
        # Apply to GroupBoxes (QgsCollapsibleGroupBox included)
        for groupbox in self.dockwidget.findChildren(QGroupBox):
            groupbox.setMinimumHeight(groupbox_min_height)
        
        logger.debug(f"Applied widget dimensions: ComboBox={combobox_height}px, Input={input_height}px")
    
    def apply_frame_dimensions(self) -> None:
        """
        Apply dimensions and size policies to frames and widget key containers.
        
        This method configures:
        - Widget key containers (sidebar buttons area)
        - Main frames (exploring, toolset)
        - Sub-frames (filtering)
        """
        UIConfig = self._get_ui_config()
        
        # Get widget_keys dimensions
        widget_keys_min_width = UIConfig.get_config('widget_keys', 'min_width')
        widget_keys_max_width = UIConfig.get_config('widget_keys', 'max_width')
        
        # Get frame exploring configuration
        exploring_config = UIConfig.get_config('frame_exploring')
        exploring_min = exploring_config.get('min_height', 120) if exploring_config else 120
        exploring_max = exploring_config.get('max_height', 350) if exploring_config else 350
        exploring_h_policy = exploring_config.get('size_policy_h', 'Preferred') if exploring_config else 'Preferred'
        exploring_v_policy = exploring_config.get('size_policy_v', 'Minimum') if exploring_config else 'Minimum'
        
        # Get frame toolset configuration
        toolset_config = UIConfig.get_config('frame_toolset')
        toolset_min = toolset_config.get('min_height', 200) if toolset_config else 200
        toolset_max = toolset_config.get('max_height', 16777215) if toolset_config else 16777215
        toolset_h_policy = toolset_config.get('size_policy_h', 'Preferred') if toolset_config else 'Preferred'
        toolset_v_policy = toolset_config.get('size_policy_v', 'Expanding') if toolset_config else 'Expanding'
        
        # Get frame filtering configuration
        filtering_config = UIConfig.get_config('frame_filtering')
        filtering_min = filtering_config.get('min_height', 180) if filtering_config else 180
        
        # Get widget_keys padding and border radius from config
        widget_keys_config = UIConfig.get_config('widget_keys')
        widget_keys_padding = widget_keys_config.get('padding', 2) if widget_keys_config else 2
        
        # Apply to widget keys containers with enhanced styling
        for widget_name in ['widget_exploring_keys', 'widget_filtering_keys', 'widget_exporting_keys']:
            if hasattr(self.dockwidget, widget_name):
                widget = getattr(self.dockwidget, widget_name)
                widget.setMinimumWidth(widget_keys_min_width)
                widget.setMaximumWidth(widget_keys_max_width)
                # Apply consistent padding via layout margins
                layout = widget.layout()
                if layout:
                    layout.setContentsMargins(widget_keys_padding, widget_keys_padding, 
                                            widget_keys_padding, widget_keys_padding)
                    layout.setSpacing(0)  # No extra spacing in container
        
        # Apply to frame_exploring with size policy
        if hasattr(self.dockwidget, 'frame_exploring'):
            self.dockwidget.frame_exploring.setMinimumHeight(exploring_min)
            self.dockwidget.frame_exploring.setMaximumHeight(exploring_max)
            h_policy = self.POLICY_MAP.get(exploring_h_policy, QSizePolicy.Preferred)
            v_policy = self.POLICY_MAP.get(exploring_v_policy, QSizePolicy.Minimum)
            self.dockwidget.frame_exploring.setSizePolicy(h_policy, v_policy)
        
        # Apply to frame_toolset with size policy
        if hasattr(self.dockwidget, 'frame_toolset'):
            self.dockwidget.frame_toolset.setMinimumHeight(toolset_min)
            self.dockwidget.frame_toolset.setMaximumHeight(toolset_max)
            h_policy = self.POLICY_MAP.get(toolset_h_policy, QSizePolicy.Preferred)
            v_policy = self.POLICY_MAP.get(toolset_v_policy, QSizePolicy.Expanding)
            self.dockwidget.frame_toolset.setSizePolicy(h_policy, v_policy)
        
        # Apply to frame_filtering (if it exists inside toolbox)
        if hasattr(self.dockwidget, 'frame_filtering'):
            self.dockwidget.frame_filtering.setMinimumHeight(filtering_min)
        
        logger.debug(f"Applied frame dimensions: exploring={exploring_min}-{exploring_max}px ({exploring_v_policy}), "
                    f"toolset={toolset_min}px+ ({toolset_v_policy}), "
                    f"widget_keys={widget_keys_min_width}-{widget_keys_max_width}px")
    
    def harmonize_checkable_pushbuttons(self) -> None:
        """
        Harmonize dimensions of all checkable pushbuttons across tabs.
        
        Applies consistent sizing to exploring, filtering, and exporting pushbuttons
        based on the active UI profile (compact/normal/hidpi) using key_button dimensions.
        """
        try:
            UIConfig = self._get_ui_config()
            from modules.ui_config import DisplayProfile
            
            # Get dynamic dimensions from key_button config
            key_button_config = UIConfig.get_config('key_button')
            
            # Profile-aware fallback values
            current_profile = UIConfig.get_profile()
            if key_button_config:
                pushbutton_min_size = key_button_config.get('min_size', 26)
                pushbutton_max_size = key_button_config.get('max_size', 32)
                pushbutton_icon_size = key_button_config.get('icon_size', 16)
                button_spacing = key_button_config.get('spacing', 2)
            else:
                # Fallback values based on profile if config not available
                if current_profile == DisplayProfile.COMPACT:
                    pushbutton_min_size = 26
                    pushbutton_max_size = 32
                    pushbutton_icon_size = 16
                    button_spacing = 2
                elif current_profile == DisplayProfile.HIDPI:
                    pushbutton_min_size = 36
                    pushbutton_max_size = 44
                    pushbutton_icon_size = 24
                    button_spacing = 6
                else:  # NORMAL
                    pushbutton_min_size = 30
                    pushbutton_max_size = 36
                    pushbutton_icon_size = 18
                    button_spacing = 4
            
            # Get all checkable pushbuttons with consistent naming pattern
            checkable_buttons = []
            
            # Exploring buttons (including non-checkable explore buttons)
            exploring_button_names = [
                'pushButton_exploring_identify',
                'pushButton_exploring_zoom',
                'pushButton_checkable_exploring_selecting',
                'pushButton_checkable_exploring_tracking',
                'pushButton_checkable_exploring_linking_widgets',
                'pushButton_exploring_reset_layer_properties'
            ]
            
            # Filtering buttons
            filtering_button_names = [
                'pushButton_checkable_filtering_auto_current_layer',
                'pushButton_checkable_filtering_layers_to_filter',
                'pushButton_checkable_filtering_current_layer_combine_operator',
                'pushButton_checkable_filtering_geometric_predicates',
                'pushButton_checkable_filtering_buffer_value',
                'pushButton_checkable_filtering_buffer_type'
            ]
            
            # Exporting buttons
            exporting_button_names = [
                'pushButton_checkable_exporting_layers',
                'pushButton_checkable_exporting_projection',
                'pushButton_checkable_exporting_styles',
                'pushButton_checkable_exporting_datatype',
                'pushButton_checkable_exporting_output_folder',
                'pushButton_checkable_exporting_zip'
            ]
            
            all_button_names = exploring_button_names + filtering_button_names + exporting_button_names
            
            # Apply consistent dimensions to all key pushbuttons
            for button_name in all_button_names:
                if hasattr(self.dockwidget, button_name):
                    button = getattr(self.dockwidget, button_name)
                    if isinstance(button, QPushButton):
                        # Set consistent square size constraints
                        button.setMinimumSize(pushbutton_min_size, pushbutton_min_size)
                        button.setMaximumSize(pushbutton_max_size, pushbutton_max_size)
                        
                        # Set consistent icon size
                        button.setIconSize(QSize(pushbutton_icon_size, pushbutton_icon_size))
                        
                        # Ensure consistent style properties
                        button.setFlat(True)
                        
                        # Set consistent size policy - Fixed for uniform sizing
                        button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                        
                        checkable_buttons.append(button_name)
            
            # Apply spacing to layout containers
            for layout_name in ['verticalLayout_exploring_content', 
                               'verticalLayout_filtering_keys',
                               'verticalLayout_exporting_keys']:
                if hasattr(self.dockwidget, layout_name):
                    layout = getattr(self.dockwidget, layout_name)
                    layout.setSpacing(button_spacing)
            
            mode_name = UIConfig.get_profile_name()
            logger.debug(f"Harmonized {len(checkable_buttons)} key pushbuttons in {mode_name} mode: "
                        f"{pushbutton_min_size}-{pushbutton_max_size}px (icon: {pushbutton_icon_size}px)")
            
        except Exception as e:
            logger.warning(f"Could not harmonize checkable pushbuttons: {e}")
            import traceback
            traceback.print_exc()
    
    def apply_layout_spacing(self) -> None:
        """
        Apply consistent spacing to layouts across all tabs.
        
        Uses harmonized spacing values from UIConfig to ensure
        uniform visual appearance across the entire UI.
        """
        try:
            UIConfig = self._get_ui_config()
            
            # Get harmonized layout spacing from config
            layout_spacing = UIConfig.get_config('layout', 'spacing_frame') or 8
            content_spacing = UIConfig.get_config('layout', 'spacing_content') or 6
            section_spacing = UIConfig.get_config('layout', 'spacing_section') or 8
            main_spacing = UIConfig.get_config('layout', 'spacing_main') or 8
            
            # Get key button spacing for harmonized key layouts
            key_button_config = UIConfig.get_config('key_button')
            button_spacing = key_button_config.get('spacing', 2) if key_button_config else 2
            
            # Apply main container spacing for better responsiveness
            if hasattr(self.dockwidget, 'verticalLayout_main_content'):
                self.dockwidget.verticalLayout_main_content.setSpacing(main_spacing)
            
            # Apply spacing to exploring layouts
            exploring_layouts = [
                'verticalLayout_exploring_single_selection',
                'verticalLayout_exploring_multiple_selection',
                'verticalLayout_exploring_custom_selection'
            ]
            for layout_name in exploring_layouts:
                if hasattr(self.dockwidget, layout_name):
                    getattr(self.dockwidget, layout_name).setSpacing(layout_spacing)
            
            # Apply spacing to filtering layouts
            if hasattr(self.dockwidget, 'verticalLayout_filtering_keys'):
                self.dockwidget.verticalLayout_filtering_keys.setSpacing(button_spacing)
            if hasattr(self.dockwidget, 'verticalLayout_filtering_values'):
                self.dockwidget.verticalLayout_filtering_values.setSpacing(content_spacing)
            
            # Apply spacing to exporting layouts
            if hasattr(self.dockwidget, 'verticalLayout_exporting_keys'):
                self.dockwidget.verticalLayout_exporting_keys.setSpacing(button_spacing)
            if hasattr(self.dockwidget, 'verticalLayout_exporting_values'):
                self.dockwidget.verticalLayout_exporting_values.setSpacing(content_spacing)
            
            # Apply spacing to exploring key layout
            if hasattr(self.dockwidget, 'verticalLayout_exploring_content'):
                self.dockwidget.verticalLayout_exploring_content.setSpacing(button_spacing)
            
            section_spacing_adjusted = UIConfig.get_config('layout', 'spacing_section') or 4
            horizontal_layouts = [
                'horizontalLayout_filtering_content',
                'horizontalLayout_exporting_content'
            ]
            for layout_name in horizontal_layouts:
                if hasattr(self.dockwidget, layout_name):
                    layout = getattr(self.dockwidget, layout_name)
                    layout.setSpacing(section_spacing_adjusted)
            
            # Apply harmonized margins to groupbox layouts
            margins_frame = UIConfig.get_config('layout', 'margins_frame')
            if margins_frame and isinstance(margins_frame, dict):
                left = margins_frame.get('left', 8)
                top = margins_frame.get('top', 8)
                right = margins_frame.get('right', 8)
                bottom = margins_frame.get('bottom', 10)
                
                # Exploring groupbox layouts
                groupbox_layouts = [
                    'gridLayout_exploring_single_content',
                    'gridLayout_exploring_multiple_content',
                    'verticalLayout_exploring_custom_container'
                ]
                
                for layout_name in groupbox_layouts:
                    if hasattr(self.dockwidget, layout_name):
                        layout = getattr(self.dockwidget, layout_name)
                        layout.setContentsMargins(left, top, right, bottom)
                
                # Apply to filtering/exporting value layouts
                value_layouts = [
                    'verticalLayout_filtering_values',
                    'verticalLayout_exporting_values'
                ]
                for layout_name in value_layouts:
                    if hasattr(self.dockwidget, layout_name):
                        layout = getattr(self.dockwidget, layout_name)
                        layout.setContentsMargins(left, top, right, bottom)
                
                logger.debug(f"Applied harmonized margins: {left}-{top}-{right}-{bottom}")
            
            # Apply action bar margins if available
            margins_actions = UIConfig.get_config('layout', 'margins_actions')
            if margins_actions and hasattr(self.dockwidget, 'frame_actions'):
                layout = self.dockwidget.frame_actions.layout()
                if layout:
                    layout.setContentsMargins(
                        margins_actions.get('left', 8),
                        margins_actions.get('top', 6),
                        margins_actions.get('right', 8),
                        margins_actions.get('bottom', 12)
                    )
            
            logger.debug(f"Applied harmonized layout spacing: {layout_spacing}px")
            
        except Exception as e:
            logger.debug(f"Could not apply layout spacing: {e}")
    
    def harmonize_spacers(self) -> None:
        """
        Harmonize vertical spacers across all key widget sections.
        
        Applies consistent spacer dimensions to exploring/filtering/exporting key widgets
        based on section-specific sizes from UI config.
        """
        try:
            UIConfig = self._get_ui_config()
            from modules.ui_config import DisplayProfile
            from modules.ui_elements import get_spacer_size
            
            # Get compact mode status from UIConfig
            is_compact = UIConfig._active_profile == DisplayProfile.COMPACT
            
            # Get dynamic spacer sizes based on active profile
            spacer_sizes = {
                'exploring': get_spacer_size('verticalSpacer_exploring_tab_top', is_compact),
                'filtering': get_spacer_size('verticalSpacer_filtering_keys_field_top', is_compact),
                'exporting': get_spacer_size('verticalSpacer_exporting_keys_field_top', is_compact)
            }
            
            spacer_width = 20  # Standard width for vertical spacers
            
            # Harmonize spacers in all three key widgets
            sections = {
                'exploring': 'widget_exploring_keys',
                'filtering': 'widget_filtering_keys',
                'exporting': 'widget_exporting_keys'
            }
            
            for section_name, widget_name in sections.items():
                # Get section-specific spacer height
                target_spacer_height = spacer_sizes.get(section_name, 4)
                
                if hasattr(self.dockwidget, widget_name):
                    widget = getattr(self.dockwidget, widget_name)
                    layout = widget.layout()
                    if layout:
                        spacer_count = 0
                        # Find the nested verticalLayout
                        for i in range(layout.count()):
                            item = layout.itemAt(i)
                            if item and hasattr(item, 'layout') and item.layout():
                                nested_layout = item.layout()
                                # Iterate through nested layout items to find spacers
                                for j in range(nested_layout.count()):
                                    nested_item = nested_layout.itemAt(j)
                                    if nested_item and isinstance(nested_item, QSpacerItem):
                                        # Set section-specific spacer dimensions
                                        nested_item.changeSize(
                                            spacer_width,
                                            target_spacer_height,
                                            nested_item.sizePolicy().horizontalPolicy(),
                                            nested_item.sizePolicy().verticalPolicy()
                                        )
                                        spacer_count += 1
                        
                        if spacer_count > 0:
                            logger.debug(f"Harmonized {spacer_count} spacers in {section_name} to {target_spacer_height}px")
            
            mode_name = 'COMPACT' if is_compact else 'NORMAL'
            logger.debug(f"Applied spacer dimensions ({mode_name} mode): {spacer_sizes}")
            
        except Exception as e:
            logger.warning(f"Could not harmonize spacers: {e}")
            import traceback
            traceback.print_exc()
    
    def apply_qgis_widget_dimensions(self) -> None:
        """
        Apply dimensions to QGIS custom widgets.
        
        Sets heights for QgsFeaturePickerWidget, QgsFieldExpressionWidget, 
        QgsProjectionSelectionWidget, and forces QgsPropertyOverrideButton to exact 22px.
        """
        try:
            UIConfig = self._get_ui_config()
            
            # Get dimensions from config
            combobox_height = UIConfig.get_config('combobox', 'height') or 24
            input_height = UIConfig.get_config('input', 'height') or 24
            
            # QgsFeaturePickerWidget
            for widget in self.dockwidget.findChildren(QgsFeaturePickerWidget):
                widget.setMinimumHeight(combobox_height)
                widget.setMaximumHeight(combobox_height)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # QgsFieldExpressionWidget
            for widget in self.dockwidget.findChildren(QgsFieldExpressionWidget):
                widget.setMinimumHeight(input_height)
                widget.setMaximumHeight(input_height)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # QgsProjectionSelectionWidget
            for widget in self.dockwidget.findChildren(QgsProjectionSelectionWidget):
                widget.setMinimumHeight(combobox_height)
                widget.setMaximumHeight(combobox_height)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # QgsMapLayerComboBox
            for widget in self.dockwidget.findChildren(QgsMapLayerComboBox):
                widget.setMinimumHeight(combobox_height)
                widget.setMaximumHeight(combobox_height)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # QgsFieldComboBox
            for widget in self.dockwidget.findChildren(QgsFieldComboBox):
                widget.setMinimumHeight(combobox_height)
                widget.setMaximumHeight(combobox_height)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # QgsCheckableComboBox (QGIS native)
            for widget in self.dockwidget.findChildren(QgsCheckableComboBox):
                widget.setMinimumHeight(combobox_height)
                widget.setMaximumHeight(combobox_height)
                widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            
            # QgsPropertyOverrideButton - FORCE to exact 22px
            for widget in self.dockwidget.findChildren(QgsPropertyOverrideButton):
                button_size = 22
                widget.setMinimumHeight(button_size)
                widget.setMaximumHeight(button_size)
                widget.setMinimumWidth(button_size)
                widget.setMaximumWidth(button_size)
                widget.setFixedSize(button_size, button_size)
                widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            
            logger.debug(f"Applied QGIS widget dimensions: ComboBox={combobox_height}px, Input={input_height}px")
            
        except Exception as e:
            logger.debug(f"Could not apply dimensions to QGIS widgets: {e}")
    
    def align_key_layouts(self) -> None:
        """
        Align key layouts (exploring/filtering/exporting) for visual consistency.
        
        Sets consistent spacing, margins, and alignment for all key widget layouts
        and their parent containers. Harmonizes vertical bars of pushbuttons.
        """
        try:
            UIConfig = self._get_ui_config()
            
            # Get key button config for harmonized spacing
            key_button_config = UIConfig.get_config('key_button')
            button_spacing = key_button_config.get('spacing', 2) if key_button_config else 2
            
            # Get widget_keys config for container margins
            widget_keys_config = UIConfig.get_config('widget_keys')
            widget_keys_padding = widget_keys_config.get('padding', 2) if widget_keys_config else 2
            
            # Apply consistent spacing and alignment to ALL key layouts
            key_layouts = [
                ('verticalLayout_exploring_content', 'exploring content'),
                ('verticalLayout_filtering_keys', 'filtering keys'),
                ('verticalLayout_exporting_keys', 'exporting keys')
            ]
            
            for layout_name, description in key_layouts:
                if hasattr(self.dockwidget, layout_name):
                    layout = getattr(self.dockwidget, layout_name)
                    layout.setSpacing(button_spacing)
                    layout.setContentsMargins(0, 0, 0, 0)
                    layout.setAlignment(Qt.AlignVCenter | Qt.AlignHCenter)
                    
                    # Center each item horizontally within the layout
                    for i in range(layout.count()):
                        item = layout.itemAt(i)
                        if item and item.widget():
                            layout.setAlignment(item.widget(), Qt.AlignHCenter)
            
            # Apply consistent styling to parent container layouts
            container_layouts = [
                ('verticalLayout_exploring_container', 'exploring'),
                ('verticalLayout_filtering_keys_container', 'filtering'),
                ('verticalLayout_exporting_keys_container', 'exporting')
            ]
            
            for layout_name, section in container_layouts:
                if hasattr(self.dockwidget, layout_name):
                    layout = getattr(self.dockwidget, layout_name)
                    layout.setContentsMargins(widget_keys_padding, widget_keys_padding, 
                                            widget_keys_padding, widget_keys_padding)
                    layout.setSpacing(0)
            
            # Apply consistent margins to parent horizontal/grid layouts
            parent_horizontal_layouts = [
                ('gridLayout_main_actions', 'exploring parent'),
                ('horizontalLayout_filtering_content', 'filtering parent'),
                ('horizontalLayout_exporting_content', 'exporting parent')
            ]
            
            for layout_name, description in parent_horizontal_layouts:
                if hasattr(self.dockwidget, layout_name):
                    layout = getattr(self.dockwidget, layout_name)
                    layout.setContentsMargins(0, 0, 0, 0)
                    layout.setSpacing(4)
            
            # Configure column stretch for gridLayout_main_actions
            if hasattr(self.dockwidget, 'gridLayout_main_actions'):
                self.dockwidget.gridLayout_main_actions.setColumnStretch(0, 0)
                self.dockwidget.gridLayout_main_actions.setColumnStretch(1, 1)
            
            # Ensure gridLayout_main_header expands properly
            if hasattr(self.dockwidget, 'gridLayout_main_header'):
                self.dockwidget.gridLayout_main_header.setColumnStretch(0, 1)
            
            # Apply consistent styling to parent widget containers
            parent_widgets = [
                ('widget_exploring_keys', 'exploring'),
                ('widget_filtering_keys', 'filtering'),
                ('widget_exporting_keys', 'exporting')
            ]
            
            for widget_name, section in parent_widgets:
                if hasattr(self.dockwidget, widget_name):
                    widget = getattr(self.dockwidget, widget_name)
                    min_width = widget_keys_config.get('min_width', 34) if widget_keys_config else 34
                    max_width = widget_keys_config.get('max_width', 40) if widget_keys_config else 40
                    widget.setMinimumWidth(min_width)
                    widget.setMaximumWidth(max_width)
                    
                    parent_layout = widget.layout()
                    if parent_layout:
                        parent_layout.setContentsMargins(widget_keys_padding, widget_keys_padding, 
                                                        widget_keys_padding, widget_keys_padding)
                        parent_layout.setAlignment(Qt.AlignCenter)
            
            # Apply consistent spacing to content layouts
            content_layouts = [
                ('verticalLayout_exploring_tabs_content', 'exploring groupboxes'),
                ('verticalLayout_filtering_values', 'filtering values'),
                ('verticalLayout_exporting_values', 'exporting values')
            ]
            
            content_spacing = 4
            for layout_name, description in content_layouts:
                if hasattr(self.dockwidget, layout_name):
                    layout = getattr(self.dockwidget, layout_name)
                    layout.setSpacing(content_spacing)
                    layout.setContentsMargins(0, 0, 0, 0)
            
            # Reduce padding on filtering and exporting main layouts
            main_page_layouts = [
                ('horizontalLayout_filtering_main', 'filtering main'),
                ('horizontalLayout_exporting_main', 'exporting main')
            ]
            
            for layout_name, description in main_page_layouts:
                if hasattr(self.dockwidget, layout_name):
                    layout = getattr(self.dockwidget, layout_name)
                    layout.setContentsMargins(2, 2, 2, 2)
                    layout.setSpacing(4)
            
            logger.debug(f"Aligned key layouts with {button_spacing}px spacing, {widget_keys_padding}px padding")
            
        except Exception as e:
            logger.warning(f"Could not align key layouts: {e}")
            import traceback
            traceback.print_exc()
    
    def adjust_row_spacing(self) -> None:
        """
        Adjust row spacing in filtering and exporting value layouts.
        
        Synchronizes spacer heights between key and value layouts for proper
        horizontal alignment of widgets across columns.
        """
        try:
            UIConfig = self._get_ui_config()
            from modules.ui_config import DisplayProfile
            from modules.ui_elements import get_spacer_size
            
            # Get compact mode status and spacer sizes
            is_compact = UIConfig._active_profile == DisplayProfile.COMPACT
            layout_spacing = UIConfig.get_config('layout', 'spacing_frame') or 4
            
            spacer_sizes = {
                'filtering': get_spacer_size('verticalSpacer_filtering_keys_field_top', is_compact),
                'exporting': get_spacer_size('verticalSpacer_exporting_keys_field_top', is_compact)
            }
            
            # Adjust spacers in filtering values layout to match keys layout
            if hasattr(self.dockwidget, 'verticalLayout_filtering_values'):
                values_layout = self.dockwidget.verticalLayout_filtering_values
                spacer_target_height = spacer_sizes.get('filtering', 4)
                
                for i in range(values_layout.count()):
                    item = values_layout.itemAt(i)
                    if item and isinstance(item, QSpacerItem):
                        item.changeSize(
                            item.sizeHint().width(),
                            spacer_target_height,
                            item.sizePolicy().horizontalPolicy(),
                            item.sizePolicy().verticalPolicy()
                        )
                
                self.dockwidget.verticalLayout_filtering_values.setSpacing(layout_spacing)
            
            # Adjust spacers in exporting values layout to match keys layout
            if hasattr(self.dockwidget, 'verticalLayout_exporting_values'):
                values_layout = self.dockwidget.verticalLayout_exporting_values
                spacer_target_height = spacer_sizes.get('exporting', 4)
                
                for i in range(values_layout.count()):
                    item = values_layout.itemAt(i)
                    if item and isinstance(item, QSpacerItem):
                        item.changeSize(
                            item.sizeHint().width(),
                            spacer_target_height,
                            item.sizePolicy().horizontalPolicy(),
                            item.sizePolicy().verticalPolicy()
                        )
                
                self.dockwidget.verticalLayout_exporting_values.setSpacing(layout_spacing)
            
            logger.debug(f"Adjusted row spacing: filtering/exporting aligned with {layout_spacing}px spacing")
            
        except Exception as e:
            logger.warning(f"Could not adjust row spacing: {e}")
            import traceback
            traceback.print_exc()
