# -*- coding: utf-8 -*-
"""
UI Widget Utilities for FilterMate

Provides helper functions to apply dynamic styles and dimensions to Qt widgets
based on the current UI profile (compact/normal).
"""

import logging
from typing import Optional
from PyQt5.QtWidgets import (
    QPushButton, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox,
    QLabel, QFrame, QWidget, QLayout, QSplitter
)
from PyQt5.QtCore import QSize, Qt

logger = logging.getLogger(__name__)

try:
    from .ui_config import UIConfig, DisplayProfile
    UI_CONFIG_AVAILABLE = True
except ImportError:
    UI_CONFIG_AVAILABLE = False
    DisplayProfile = None


def apply_button_dimensions(button: QPushButton, button_type: str = "button") -> None:
    """
    Apply dynamic dimensions to a QPushButton based on current UI profile.
    
    Args:
        button: QPushButton instance to configure
        button_type: 'button', 'action_button', or 'tool_button'
    """
    if not UI_CONFIG_AVAILABLE:
        return
    
    try:
        height = UIConfig.get_button_height(button_type)
        icon_size = UIConfig.get_icon_size(button_type)
        
        button.setMinimumHeight(height)
        button.setMaximumHeight(height)
        button.setIconSize(QSize(icon_size, icon_size))
        
    except Exception as e:
        logger.warning(f"Error applying button dimensions: {e}")


def apply_input_dimensions(widget: QWidget) -> None:
    """
    Apply dynamic dimensions to input widgets (QLineEdit, QSpinBox, etc.).
    
    Args:
        widget: Input widget to configure
    """
    if not UI_CONFIG_AVAILABLE:
        return
    
    try:
        height = UIConfig.get_config("input", "height")
        if height:
            widget.setMinimumHeight(height)
            widget.setMaximumHeight(height)
            
    except Exception as e:
        logger.warning(f"Error applying input dimensions: {e}")


def apply_combobox_dimensions(combobox: QComboBox) -> None:
    """
    Apply dynamic dimensions to a QComboBox.
    
    Args:
        combobox: QComboBox instance to configure
    """
    if not UI_CONFIG_AVAILABLE:
        return
    
    try:
        height = UIConfig.get_config("combobox", "height")
        icon_size = UIConfig.get_config("combobox", "icon_size")
        
        if height:
            combobox.setMinimumHeight(height)
            combobox.setMaximumHeight(height)
        
        if icon_size:
            combobox.setIconSize(QSize(icon_size, icon_size))
            
    except Exception as e:
        logger.warning(f"Error applying combobox dimensions: {e}")


def apply_frame_dimensions(frame: QFrame, frame_type: str = "frame") -> None:
    """
    Apply dynamic dimensions to a QFrame.
    
    Args:
        frame: QFrame instance to configure
        frame_type: 'frame' or 'action_frame'
    """
    if not UI_CONFIG_AVAILABLE:
        return
    
    try:
        min_height = UIConfig.get_config(frame_type, "min_height")
        max_height = UIConfig.get_config(frame_type, "max_height")
        
        if min_height:
            frame.setMinimumHeight(min_height)
        if max_height:
            frame.setMaximumHeight(max_height)
            
    except Exception as e:
        logger.warning(f"Error applying frame dimensions: {e}")


def apply_layout_spacing(layout: QLayout, size: str = "medium") -> None:
    """
    Apply dynamic spacing to a QLayout.
    
    Args:
        layout: QLayout instance to configure
        size: 'small', 'medium', 'large', or 'extra_large'
    """
    if not UI_CONFIG_AVAILABLE:
        return
    
    try:
        spacing = UIConfig.get_spacing(size)
        layout.setSpacing(spacing)
            
    except Exception as e:
        logger.warning(f"Error applying layout spacing: {e}")


def apply_layout_margins(layout: QLayout, size: str = "normal") -> None:
    """
    Apply dynamic margins to a QLayout.
    
    Args:
        layout: QLayout instance to configure
        size: 'tight', 'normal', or 'loose'
    """
    if not UI_CONFIG_AVAILABLE:
        return
    
    try:
        margins = UIConfig.get_margins(size)
        layout.setContentsMargins(
            margins['left'],
            margins['top'],
            margins['right'],
            margins['bottom']
        )
            
    except Exception as e:
        logger.warning(f"Error applying layout margins: {e}")


def apply_splitter_dimensions(splitter: QSplitter) -> None:
    """
    Apply dynamic handle width to a QSplitter.
    
    Args:
        splitter: QSplitter instance to configure
    """
    if not UI_CONFIG_AVAILABLE:
        return
    
    try:
        handle_width = UIConfig.get_config("splitter", "handle_width")
        if handle_width:
            splitter.setHandleWidth(handle_width)
            
    except Exception as e:
        logger.warning(f"Error applying splitter dimensions: {e}")


def apply_label_dimensions(label: QLabel) -> None:
    """
    Apply dynamic font size to a QLabel.
    
    Args:
        label: QLabel instance to configure
    """
    if not UI_CONFIG_AVAILABLE:
        return
    
    try:
        font_size = UIConfig.get_config("label", "font_size")
        if font_size:
            font = label.font()
            font.setPointSize(font_size)
            label.setFont(font)
            
    except Exception as e:
        logger.warning(f"Error applying label dimensions: {e}")


def configure_action_buttons(widget: QWidget, button_names: list) -> None:
    """
    Configure multiple action buttons with dynamic dimensions.
    
    Convenience function to apply action_button dimensions to multiple buttons at once.
    
    Args:
        widget: Parent widget containing the buttons
        button_names: List of button object names (e.g., ['btn_filter', 'btn_export'])
    """
    if not UI_CONFIG_AVAILABLE:
        return
    
    for button_name in button_names:
        button = widget.findChild(QPushButton, button_name)
        if button:
            apply_button_dimensions(button, "action_button")


def configure_tool_buttons(widget: QWidget, button_names: list) -> None:
    """
    Configure multiple tool buttons with dynamic dimensions.
    
    Convenience function to apply tool_button dimensions to multiple buttons at once.
    
    Args:
        widget: Parent widget containing the buttons
        button_names: List of button object names
    """
    if not UI_CONFIG_AVAILABLE:
        return
    
    for button_name in button_names:
        button = widget.findChild(QPushButton, button_name)
        if button:
            apply_button_dimensions(button, "tool_button")


def get_profile_info() -> dict:
    """
    Get information about current UI profile.
    
    Returns:
        dict: Profile information including name and key dimensions
    """
    if not UI_CONFIG_AVAILABLE:
        return {"available": False}
    
    try:
        profile_name = UIConfig.get_profile_name()
        dimensions = UIConfig.get_all_dimensions()
        
        return {
            "available": True,
            "profile": profile_name,
            "description": dimensions.get("description", ""),
            "button_height": UIConfig.get_button_height(),
            "icon_size": UIConfig.get_icon_size(),
            "spacing_medium": UIConfig.get_spacing("medium")
        }
    except Exception as e:
        print(f"FilterMate: Error getting profile info: {e}")
        return {"available": False, "error": str(e)}


def switch_profile(profile_name: str) -> bool:
    """
    Switch to a different UI profile.
    
    Args:
        profile_name: 'compact' or 'normal'
    
    Returns:
        bool: True if successful
    """
    if not UI_CONFIG_AVAILABLE:
        return False
    
    try:
        if profile_name.lower() == "compact":
            UIConfig.set_profile(DisplayProfile.COMPACT)
            return True
        elif profile_name.lower() == "normal":
            UIConfig.set_profile(DisplayProfile.NORMAL)
            return True
        else:
            print(f"FilterMate: Unknown profile '{profile_name}'")
            return False
            
    except Exception as e:
        print(f"FilterMate: Error switching profile: {e}")
        return False


def apply_widget_dimensions(widget: QWidget, widget_type: str = "auto") -> None:
    """
    Automatically apply appropriate dimensions based on widget type.
    
    Args:
        widget: Widget to configure
        widget_type: Type hint ('auto', 'button', 'input', 'combobox', 'frame', 'label')
                     If 'auto', will auto-detect type
    """
    if not UI_CONFIG_AVAILABLE:
        return
    
    # Auto-detect type if needed
    if widget_type == "auto":
        if isinstance(widget, QPushButton):
            widget_type = "button"
        elif isinstance(widget, (QLineEdit, QSpinBox, QDoubleSpinBox)):
            widget_type = "input"
        elif isinstance(widget, QComboBox):
            widget_type = "combobox"
        elif isinstance(widget, QFrame):
            widget_type = "frame"
        elif isinstance(widget, QLabel):
            widget_type = "label"
        else:
            return
    
    # Apply appropriate dimensions
    if widget_type == "button":
        apply_button_dimensions(widget)
    elif widget_type == "input":
        apply_input_dimensions(widget)
    elif widget_type == "combobox":
        apply_combobox_dimensions(widget)
    elif widget_type == "frame":
        apply_frame_dimensions(widget)
    elif widget_type == "label":
        apply_label_dimensions(widget)


def apply_dockwidget_dimensions(dockwidget: QWidget) -> None:
    """
    Apply recommended dockwidget dimensions based on current profile.
    
    Args:
        dockwidget: Dockwidget to configure
    """
    if not UI_CONFIG_AVAILABLE:
        return
    
    try:
        min_width = UIConfig.get_config("dockwidget", "min_width")
        preferred_width = UIConfig.get_config("dockwidget", "preferred_width")
        
        if min_width:
            dockwidget.setMinimumWidth(min_width)
        
        # Note: Preferred width would need to be set on the dock widget container,
        # not on the widget itself. This is more of a hint for initial sizing.
        
    except Exception as e:
        print(f"FilterMate: Error applying dockwidget dimensions: {e}")


def auto_configure_from_environment(config_data: dict = None) -> dict:
    """
    Automatically configure UI profile and theme based on environment.
    
    Detects:
    - Screen resolution → selects UI profile (compact/normal)
    - QGIS theme → selects color theme (light/dark)
    
    Args:
        config_data: Optional config dictionary to update
    
    Returns:
        dict: Configuration info with detected settings
        {
            'profile_detected': str,
            'profile_source': str,
            'theme_detected': str,
            'theme_source': str,
            'screen_resolution': str,
            'qgis_theme': str
        }
    """
    result = {
        'profile_detected': 'normal',
        'profile_source': 'default',
        'theme_detected': 'default',
        'theme_source': 'default',
        'screen_resolution': 'unknown',
        'qgis_theme': 'unknown'
    }
    
    if not UI_CONFIG_AVAILABLE:
        result['error'] = 'UIConfig not available'
        return result
    
    try:
        from qgis.core import QgsApplication
        
        # Detect screen resolution
        app = QgsApplication.instance()
        if app and app.primaryScreen():
            screen = app.primaryScreen()
            size = screen.size()
            width = size.width()
            height = size.height()
            result['screen_resolution'] = f"{width}x{height}"
            
            # Auto-detect profile from resolution
            detected_profile = UIConfig.detect_optimal_profile()
            UIConfig.set_profile(detected_profile)
            result['profile_detected'] = detected_profile.value
            result['profile_source'] = 'auto-detected from screen'
        
        # Detect QGIS theme
        try:
            from .ui_styles import StyleLoader
            detected_theme = StyleLoader.detect_qgis_theme()
            result['theme_detected'] = detected_theme
            result['theme_source'] = 'auto-detected from QGIS'
            result['qgis_theme'] = detected_theme
        except Exception as e:
            print(f"FilterMate: Could not detect QGIS theme: {e}")
        
        # Override with config if provided and not "auto"
        if config_data:
            ui_profile_config = config_data.get("APP", {}).get("DOCKWIDGET", {}).get("UI_PROFILE", "auto")
            
            # Extract value if UI_PROFILE is a dict with 'value' key, otherwise use as-is
            if isinstance(ui_profile_config, dict) and "value" in ui_profile_config:
                ui_profile = ui_profile_config["value"]
            else:
                ui_profile = ui_profile_config
                
            if ui_profile in ["compact", "normal"]:
                # User explicitly set a profile, don't auto-detect
                if ui_profile == "compact":
                    UIConfig.set_profile(DisplayProfile.COMPACT)
                else:
                    UIConfig.set_profile(DisplayProfile.NORMAL)
                result['profile_detected'] = ui_profile
                result['profile_source'] = 'config.json'
            
            # Check theme setting
            theme_setting_config = config_data.get("APP", {}).get("DOCKWIDGET", {}).get("COLORS", {}).get("ACTIVE_THEME", "auto")
            
            # Extract value if ACTIVE_THEME is a dict with 'value' key, otherwise use as-is
            if isinstance(theme_setting_config, dict) and "value" in theme_setting_config:
                theme_setting = theme_setting_config["value"]
            else:
                theme_setting = theme_setting_config
                
            if theme_setting != "auto":
                result['theme_detected'] = theme_setting
                result['theme_source'] = 'config.json'
        
        print(f"\n{'='*60}")
        print(f"FilterMate Auto-Configuration")
        print(f"{'='*60}")
        print(f"Screen Resolution: {result['screen_resolution']}")
        print(f"UI Profile: {result['profile_detected']} ({result['profile_source']})")
        print(f"QGIS Theme: {result['qgis_theme']}")
        print(f"Color Theme: {result['theme_detected']} ({result['theme_source']})")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"FilterMate: Error in auto-configuration: {e}")
        result['error'] = str(e)
    
    return result
