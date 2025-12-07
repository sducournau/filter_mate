# -*- coding: utf-8 -*-
"""
UI Configuration Module for FilterMate

Provides dynamic UI sizing and spacing configuration supporting multiple display profiles.
Allows switching between 'compact' and 'normal' layouts for different screen sizes.
"""

from typing import Dict, Any, Optional
from enum import Enum


class DisplayProfile(Enum):
    """Display profile types for different screen configurations."""
    COMPACT = "compact"
    NORMAL = "normal"


class UIConfig:
    """
    Central UI configuration manager.
    
    Manages dimensions, spacing, and layout parameters for FilterMate's interface.
    Supports multiple display profiles (compact/normal) for different screen sizes.
    """
    
    # Active display profile - DEFAULT TO COMPACT for harmonized 24px dimensions
    _active_profile: DisplayProfile = DisplayProfile.COMPACT
    
    # ========================================================================
    # DISPLAY PROFILES CONFIGURATION
    # ========================================================================
    
    PROFILES: Dict[str, Dict[str, Any]] = {
        "compact": {
            "description": "Compact layout for small screens (laptops, tablets)",
            
            # Button dimensions
            "button": {
                "height": 32,
                "icon_size": 18,
                "padding": {"top": 4, "right": 8, "bottom": 4, "left": 8},
                "border_radius": 6,
                "min_width": 80
            },
            
            # Action buttons (filter, export, etc.)
            "action_button": {
                "height": 36,
                "icon_size": 22,
                "padding": {"top": 6, "right": 10, "bottom": 6, "left": 10},
                "border_radius": 8,
                "min_width": 100
            },
            
            # Tool buttons (identify, zoom, etc.)
            "tool_button": {
                "height": 28,
                "icon_size": 20,
                "padding": {"top": 2, "right": 2, "bottom": 2, "left": 2},
                "border_radius": 3
            },
            
            # Frame and container dimensions
            "frame": {
                "min_height": 35,
                "max_height": 100,
                "padding": 2,
                "border_width": 1
            },
            
            # Action frame (top buttons area)
            "action_frame": {
                "min_height": 35,
                "max_height": 35,
                "padding": 2
            },
            
            # Splitter dimensions
            "splitter": {
                "handle_width": 3,
                "margin": 2
            },
            
            # ComboBox dimensions
            "combobox": {
                "height": 24,
                "padding": {"top": 3, "right": 6, "bottom": 3, "left": 6},
                "item_height": 24,
                "icon_size": 16
            },
            
            # SpinBox and input fields
            "input": {
                "height": 24,
                "padding": {"top": 3, "right": 6, "bottom": 3, "left": 6},
                "border_radius": 4
            },
            
            # Layout dimensions (NEW)
            "layout": {
                "spacing_main": 2,       # Ultra compact pour conteneur principal
                "spacing_section": 2,    # Entre sections (exploring, filtering, etc.) - réduit pour backend
                "spacing_content": 2,    # Dans les contenus (keys, values)
                "spacing_buttons": 3,    # Entre boutons
                "spacing_frame": 3,      # Spacing interne des frames (exploring, filtering)
                "margins_main": 2,       # Marges minimales pour conteneur
                "margins_section": 2,    # Marges pour sections - réduit
                "margins_content": 2,    # Marges pour contenus
                "margins_frame": {"left": 3, "top": 4, "right": 3, "bottom": 4}  # Marges des frames groupbox - réduites
            },
            
            # Frame exploring dimensions (NEW)
            "frame_exploring": {
                "min_height": 200,
                "base_height": 250
            },
            
            # Frame filtering dimensions (NEW)
            "frame_filtering": {
                "min_height": 250
            },
            
            # Widget keys dimensions (NEW)
            "widget_keys": {
                "min_width": 40,
                "max_width": 56,
                "base_width": 56
            },
            
            # GroupBox dimensions (NEW)
            "groupbox": {
                "min_height": 100,
                "padding": 3
            },
            
            # Spacer dimensions (NEW) - Compact mode
            "spacer": {
                "default_size": 3,      # Default for compact mode - réduit
                "section_main": 4,
                "section_exploring": 3,
                "section_filtering": 3,
                "section_exporting": 3,
                "section_config": 6
            },
            
            # Labels and text
            "label": {
                "font_size": 9,
                "line_height": 14,
                "padding": 3
            },
            
            # Tree/List widgets
            "tree": {
                "item_height": 24,
                "indent": 16,
                "icon_size": 14
            },
            
            # List widget (for custom feature picker)
            "list": {
                "min_height": 150,  # Minimum height to display 5-6 items
                "item_height": 24,
                "icon_size": 14
            },
            
            # Tab widget
            "tab": {
                "height": 28,
                "padding": {"top": 4, "right": 10, "bottom": 4, "left": 10},
                "font_size": 9
            },
            
            # Spacing and margins
            "spacing": {
                "small": 3,
                "medium": 6,
                "large": 10,
                "extra_large": 15
            },
            
            "margins": {
                "tight": {"top": 3, "right": 3, "bottom": 3, "left": 3},
                "normal": {"top": 6, "right": 6, "bottom": 6, "left": 6},
                "loose": {"top": 10, "right": 10, "bottom": 10, "left": 10}
            },
            
            # Scrollbar dimensions
            "scrollbar": {
                "width": 8,
                "handle_min_height": 20
            },
            
            # Dockwidget dimensions
            "dockwidget": {
                "min_width": 280,
                "preferred_width": 350
            }
        },
        
        "normal": {
            "description": "Standard layout for normal screens (desktops, large laptops)",
            
            # Button dimensions
            "button": {
                "height": 40,
                "icon_size": 20,
                "padding": {"top": 8, "right": 12, "bottom": 8, "left": 12},
                "border_radius": 10,
                "min_width": 100
            },
            
            # Action buttons (filter, export, etc.)
            "action_button": {
                "height": 48,
                "icon_size": 25,
                "padding": {"top": 10, "right": 15, "bottom": 10, "left": 15},
                "border_radius": 10,
                "min_width": 120
            },
            
            # Tool buttons (identify, zoom, etc.)
            "tool_button": {
                "height": 36,
                "icon_size": 24,
                "padding": {"top": 4, "right": 6, "bottom": 4, "left": 6},
                "border_radius": 6
            },
            
            # Frame and container dimensions
            "frame": {
                "min_height": 80,
                "max_height": 200,
                "padding": 8,
                "border_width": 1
            },
            
            # Action frame (top buttons area)
            "action_frame": {
                "min_height": 75,
                "max_height": 75,
                "padding": 8
            },
            
            # Splitter dimensions
            "splitter": {
                "handle_width": 5,
                "margin": 3
            },
            
            # ComboBox dimensions
            "combobox": {
                "height": 36,
                "padding": {"top": 6, "right": 10, "bottom": 6, "left": 10},
                "item_height": 32,
                "icon_size": 20
            },
            
            # SpinBox and input fields
            "input": {
                "height": 36,
                "padding": {"top": 6, "right": 10, "bottom": 6, "left": 10},
                "border_radius": 6
            },
            
            # Layout dimensions (NEW)
            "layout": {
                "spacing_main": 6,       # Confortable pour conteneur principal
                "spacing_section": 6,    # Entre sections (exploring, filtering, etc.) - cohérent ×3
                "spacing_content": 6,    # Dans les contenus (keys, values)
                "spacing_buttons": 8,    # Entre boutons
                "spacing_frame": 8,      # Spacing interne des frames (exploring, filtering)
                "margins_main": 4,       # Marges confortables pour conteneur
                "margins_section": 6,    # Marges pour sections
                "margins_content": 4,    # Marges pour contenus
                "margins_frame": {"left": 8, "top": 10, "right": 8, "bottom": 10}  # Marges des frames groupbox
            },
            
            # Frame exploring dimensions (NEW)
            "frame_exploring": {
                "min_height": 250,
                "base_height": 300
            },
            
            # Frame filtering dimensions (NEW)
            "frame_filtering": {
                "min_height": 300
            },
            
            # Widget keys dimensions (NEW)
            "widget_keys": {
                "min_width": 55,
                "max_width": 110,
                "base_width": 110
            },
            
            # GroupBox dimensions (NEW)
            "groupbox": {
                "min_height": 50,
                "padding": 6
            },
            
            # Spacer dimensions (NEW) - Normal mode
            "spacer": {
                "default_size": 8,      # Default for normal mode
                "section_main": 10,
                "section_exploring": 8,
                "section_filtering": 6,
                "section_exporting": 6,
                "section_config": 12
            },
            
            # Labels and text
            "label": {
                "font_size": 10,
                "line_height": 16,
                "padding": 4
            },
            
            # Tree/List widgets
            "tree": {
                "item_height": 28,
                "indent": 20,
                "icon_size": 16
            },
            
            # List widget (for custom feature picker)
            "list": {
                "min_height": 200,  # Larger minimum for normal profile
                "item_height": 28,
                "icon_size": 16
            },
            
            # Tab widget
            "tab": {
                "height": 36,
                "padding": {"top": 8, "right": 15, "bottom": 8, "left": 15},
                "font_size": 10
            },
            
            # Spacing and margins
            "spacing": {
                "small": 5,
                "medium": 10,
                "large": 15,
                "extra_large": 20
            },
            
            "margins": {
                "tight": {"top": 5, "right": 5, "bottom": 5, "left": 5},
                "normal": {"top": 10, "right": 10, "bottom": 10, "left": 10},
                "loose": {"top": 15, "right": 15, "bottom": 15, "left": 15}
            },
            
            # Scrollbar dimensions
            "scrollbar": {
                "width": 12,
                "handle_min_height": 30
            },
            
            # Dockwidget dimensions
            "dockwidget": {
                "min_width": 350,
                "preferred_width": 450
            }
        }
    }
    
    # ========================================================================
    # METHODS
    # ========================================================================
    
    @classmethod
    def set_profile(cls, profile: DisplayProfile) -> None:
        """
        Set active display profile.
        
        Args:
            profile: DisplayProfile enum value (COMPACT or NORMAL)
        """
        cls._active_profile = profile
        print(f"FilterMate UIConfig: Switched to '{profile.value}' profile")
    
    @classmethod
    def get_profile(cls) -> DisplayProfile:
        """Get current active display profile."""
        return cls._active_profile
    
    @classmethod
    def get_profile_name(cls) -> str:
        """Get current active profile name as string."""
        return cls._active_profile.value
    
    @classmethod
    def get_config(cls, component: str, key: Optional[str] = None) -> Any:
        """
        Get configuration value for current profile.
        
        Args:
            component: Component name (e.g., 'button', 'spacing', 'margins')
            key: Optional specific key within component (e.g., 'height', 'small')
        
        Returns:
            Configuration value (dict or primitive)
        
        Example:
            >>> UIConfig.get_config('button', 'height')
            40  # Returns 40 for normal, 32 for compact
            
            >>> UIConfig.get_config('spacing')
            {'small': 5, 'medium': 10, ...}
        """
        profile_name = cls.get_profile_name()
        profile_config = cls.PROFILES.get(profile_name, cls.PROFILES["normal"])
        
        if component not in profile_config:
            print(f"FilterMate UIConfig Warning: Component '{component}' not found in profile '{profile_name}'")
            return None
        
        component_config = profile_config[component]
        
        if key is None:
            return component_config
        
        if key not in component_config:
            print(f"FilterMate UIConfig Warning: Key '{key}' not found in component '{component}'")
            return None
        
        return component_config[key]
    
    @classmethod
    def get_button_height(cls, button_type: str = "button") -> int:
        """
        Get button height for current profile.
        
        Args:
            button_type: 'button', 'action_button', or 'tool_button'
        
        Returns:
            Height in pixels
        """
        return cls.get_config(button_type, "height") or 40
    
    @classmethod
    def get_icon_size(cls, button_type: str = "button") -> int:
        """
        Get icon size for current profile.
        
        Args:
            button_type: 'button', 'action_button', or 'tool_button'
        
        Returns:
            Icon size in pixels
        """
        return cls.get_config(button_type, "icon_size") or 20
    
    @classmethod
    def get_spacing(cls, size: str = "medium") -> int:
        """
        Get spacing value for current profile.
        
        Args:
            size: 'small', 'medium', 'large', or 'extra_large'
        
        Returns:
            Spacing in pixels
        """
        spacing_config = cls.get_config("spacing")
        return spacing_config.get(size, 10) if spacing_config else 10
    
    @classmethod
    def get_margins(cls, size: str = "normal") -> Dict[str, int]:
        """
        Get margins for current profile.
        
        Args:
            size: 'tight', 'normal', or 'loose'
        
        Returns:
            Dict with 'top', 'right', 'bottom', 'left' keys
        """
        margins_config = cls.get_config("margins")
        default_margins = {"top": 10, "right": 10, "bottom": 10, "left": 10}
        return margins_config.get(size, default_margins) if margins_config else default_margins
    
    @classmethod
    def get_padding_dict(cls, component: str) -> Dict[str, int]:
        """
        Get padding as dictionary for current profile.
        
        Args:
            component: Component name (e.g., 'button', 'input')
        
        Returns:
            Dict with 'top', 'right', 'bottom', 'left' keys
        """
        return cls.get_config(component, "padding") or {"top": 5, "right": 5, "bottom": 5, "left": 5}
    
    @classmethod
    def get_padding_string(cls, component: str) -> str:
        """
        Get padding as CSS string for current profile.
        
        Args:
            component: Component name (e.g., 'button', 'input')
        
        Returns:
            CSS padding string (e.g., "10px 15px 10px 15px")
        """
        padding = cls.get_padding_dict(component)
        return f"{padding['top']}px {padding['right']}px {padding['bottom']}px {padding['left']}px"
    
    @classmethod
    def format_margins(cls, size: str = "normal") -> str:
        """
        Get margins as CSS string for use in setContentsMargins().
        
        Args:
            size: 'tight', 'normal', or 'loose'
        
        Returns:
            Comma-separated string (e.g., "10, 10, 10, 10")
        """
        margins = cls.get_margins(size)
        return f"{margins['left']}, {margins['top']}, {margins['right']}, {margins['bottom']}"
    
    @classmethod
    def apply_button_style(cls, button, button_type: str = "button") -> str:
        """
        Generate complete button stylesheet for current profile.
        
        Args:
            button: QPushButton instance (not used, kept for compatibility)
            button_type: 'button', 'action_button', or 'tool_button'
        
        Returns:
            QSS stylesheet string
        """
        config = cls.get_config(button_type)
        if not config:
            return ""
        
        padding = cls.get_padding_string(button_type)
        
        return f"""
            QPushButton {{
                min-height: {config['height']}px;
                max-height: {config['height']}px;
                padding: {padding};
                border-radius: {config['border_radius']}px;
                min-width: {config.get('min_width', 80)}px;
            }}
        """
    
    @classmethod
    def apply_input_style(cls, widget) -> str:
        """
        Generate complete input field stylesheet for current profile.
        
        Args:
            widget: QLineEdit, QSpinBox, or similar widget (not used, kept for compatibility)
        
        Returns:
            QSS stylesheet string
        """
        config = cls.get_config("input")
        if not config:
            return ""
        
        padding = cls.get_padding_string("input")
        
        return f"""
            QLineEdit, QSpinBox, QDoubleSpinBox {{
                min-height: {config['height']}px;
                max-height: {config['height']}px;
                padding: {padding};
                border-radius: {config['border_radius']}px;
            }}
        """
    
    @classmethod
    def apply_combobox_style(cls, widget) -> str:
        """
        Generate complete combobox stylesheet for current profile.
        
        Args:
            widget: QComboBox instance (not used, kept for compatibility)
        
        Returns:
            QSS stylesheet string
        """
        config = cls.get_config("combobox")
        if not config:
            return ""
        
        padding = cls.get_padding_string("combobox")
        
        return f"""
            QComboBox {{
                min-height: {config['height']}px;
                max-height: {config['height']}px;
                padding: {padding};
            }}
            QComboBox::item {{
                min-height: {config['item_height']}px;
            }}
        """
    
    @classmethod
    def get_all_dimensions(cls) -> Dict[str, Any]:
        """
        Get all configuration dimensions for current profile.
        
        Returns:
            Complete profile configuration dictionary
        """
        profile_name = cls.get_profile_name()
        return cls.PROFILES.get(profile_name, cls.PROFILES["normal"])
    
    @classmethod
    def detect_optimal_profile(cls) -> DisplayProfile:
        """
        Detect optimal UI profile based on screen resolution.
        
        Analyzes the primary screen resolution to determine if compact
        or normal profile should be used.
        
        Returns:
            DisplayProfile: COMPACT for small screens, NORMAL for large screens
        
        Resolution thresholds:
            - Width < 1920px OR Height < 1080px → COMPACT
            - Width ≥ 1920px AND Height ≥ 1080px → NORMAL
        """
        try:
            from qgis.core import QgsApplication
            
            # Get primary screen
            app = QgsApplication.instance()
            if app:
                screen = app.primaryScreen()
                if screen:
                    size = screen.size()
                    width = size.width()
                    height = size.height()
                    
                    print(f"FilterMate UIConfig: Screen resolution detected: {width}x{height}")
                    
                    # Determine profile based on resolution
                    # Use compact for laptops and small screens
                    if width < 1920 or height < 1080:
                        print(f"FilterMate UIConfig: Small screen detected → COMPACT profile")
                        return DisplayProfile.COMPACT
                    else:
                        print(f"FilterMate UIConfig: Large screen detected → NORMAL profile")
                        return DisplayProfile.NORMAL
        except Exception as e:
            print(f"FilterMate UIConfig: Could not detect screen resolution: {e}")
        
        # Fallback to NORMAL if detection fails
        return DisplayProfile.NORMAL
    
    @classmethod
    def load_from_config(cls, config_dict: Dict[str, Any], auto_detect: bool = True) -> None:
        """
        Load UI configuration from config.json with optional auto-detection.
        
        Args:
            config_dict: Configuration dictionary from config.json
            auto_detect: If True and UI_PROFILE is "auto", detect optimal profile
        """
        try:
            # Check if UI_PROFILE is defined in config
            ui_profile_config = config_dict.get("APP", {}).get("DOCKWIDGET", {}).get("UI_PROFILE", "auto")
            
            # Extract value if UI_PROFILE is a dict with 'value' key, otherwise use as-is
            if isinstance(ui_profile_config, dict) and "value" in ui_profile_config:
                ui_profile = ui_profile_config["value"]
            else:
                ui_profile = ui_profile_config
            
            # Handle auto-detection
            if ui_profile == "auto" and auto_detect:
                print("FilterMate UIConfig: Auto-detection enabled")
                detected_profile = cls.detect_optimal_profile()
                cls.set_profile(detected_profile)
                print(f"FilterMate UIConfig: Auto-selected profile '{detected_profile.value}'")
            elif ui_profile == "compact":
                cls.set_profile(DisplayProfile.COMPACT)
                print(f"FilterMate UIConfig: Loaded profile 'compact' from config")
            elif ui_profile == "normal":
                cls.set_profile(DisplayProfile.NORMAL)
                print(f"FilterMate UIConfig: Loaded profile 'normal' from config")
            else:
                # Unknown value, default to normal
                cls.set_profile(DisplayProfile.NORMAL)
                print(f"FilterMate UIConfig: Unknown profile '{ui_profile}', using 'normal'")
            
        except Exception as e:
            print(f"FilterMate UIConfig Warning: Could not load profile from config: {e}")
            cls.set_profile(DisplayProfile.NORMAL)


# Convenience function for quick access
def get_ui_config() -> UIConfig:
    """
    Get UIConfig singleton instance.
    
    Returns:
        UIConfig class (acts as singleton)
    """
    return UIConfig
