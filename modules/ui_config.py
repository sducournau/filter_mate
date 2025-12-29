# -*- coding: utf-8 -*-
"""
UI Configuration Module for FilterMate

Provides dynamic UI sizing and spacing configuration supporting multiple display profiles.
Allows switching between 'compact' and 'normal' layouts for different screen sizes.
"""

from typing import Dict, Any, Optional
from enum import Enum

from .logging_config import get_logger

logger = get_logger(__name__)


class DisplayProfile(Enum):
    """Display profile types for different screen configurations."""
    COMPACT = "compact"
    NORMAL = "normal"
    HIDPI = "hidpi"


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
                "height": 48,
                "icon_size": 27,
                "padding": {"top": 6, "right": 12, "bottom": 6, "left": 12},
                "border_radius": 9,
                "min_width": 120
            },
            
            # Action buttons (filter, export, etc.)
            "action_button": {
                "height": 32,
                "icon_size": 20,
                "padding": {"top": 4, "right": 6, "bottom": 4, "left": 6},
                "border_radius": 5,
                "min_width": 32
            },
            
            # Tool buttons (identify, zoom, etc.)
            "tool_button": {
                "height": 34,
                "icon_size": 22,
                "padding": {"top": 2, "right": 2, "bottom": 2, "left": 2},
                "border_radius": 4
            },
            
            # Frame and container dimensions
            "frame": {
                "min_height": 35,
                "max_height": 100,
                "padding": 2,
                "border_width": 1
            },
            
            # Action frame (top buttons area) - Compact
            "action_frame": {
                "min_height": 56,
                "max_height": 70,
                "padding": 6
            },
            
            # Splitter dimensions - Enhanced configuration
            "splitter": {
                "handle_width": 4,
                "handle_margin": 30,  # Horizontal margin for the handle bar
                "exploring_stretch": 1,  # Stretch factor for frame_exploring (equal)
                "toolset_stretch": 1,    # Stretch factor for frame_toolset (equal)
                "collapsible": False,    # Whether frames can be collapsed
                "opaque_resize": True,   # Whether to show live resize
                "initial_exploring_ratio": 0.50,  # Initial ratio for exploring (50%)
                "initial_toolset_ratio": 0.50     # Initial ratio for toolset (50%)
            },
            
            # ComboBox dimensions
            "combobox": {
                "height": 36,
                "padding": {"top": 5, "right": 9, "bottom": 5, "left": 9},
                "item_height": 36,
                "icon_size": 24
            },
            
            # SpinBox and input fields
            "input": {
                "height": 36,
                "padding": {"top": 5, "right": 9, "bottom": 5, "left": 9},
                "border_radius": 6
            },
            
            # Header bar dimensions
            "header": {
                "height": 28,
                "min_height": 24,
                "padding": {"top": 4, "right": 8, "bottom": 4, "left": 8},
                "title_font_size": 11,
                "indicator_font_size": 8
            },
            
            # Layout dimensions - Harmonized spacing
            "layout": {
                "spacing_main": 6,       # Harmonized - main container spacing
                "spacing_section": 6,    # Harmonized - between sections
                "spacing_content": 6,    # Harmonized - within content areas
                "spacing_buttons": 8,    # Harmonized - between buttons
                "spacing_frame": 8,      # Harmonized - internal frame spacing
                "margins_main": 6,       # Harmonized - main container margins
                "margins_section": 6,    # Harmonized - section margins
                "margins_content": 6,    # Harmonized - content margins
                "margins_frame": {"left": 8, "top": 8, "right": 8, "bottom": 10},  # Harmonized - frame margins with extra bottom
                "margins_actions": {"left": 8, "top": 6, "right": 8, "bottom": 12}  # Action bar margins with extra bottom
            },
            
            # Frame exploring dimensions - Enhanced with size policy
            "frame_exploring": {
                "min_height": 120,
                "base_height": 180,
                "max_height": 350,
                "size_policy_h": "Preferred",
                "size_policy_v": "Minimum",  # Can shrink but has minimum
                "preferred_height": 200
            },
            
            # Frame toolset dimensions
            "frame_toolset": {
                "min_height": 200,
                "max_height": 16777215,  # QWIDGETSIZE_MAX
                "size_policy_h": "Preferred",
                "size_policy_v": "Expanding",  # Takes remaining space
                "preferred_height": 400
            },
            
            # Frame filtering dimensions (inside toolset/toolbox)
            "frame_filtering": {
                "min_height": 180,
                "preferred_height": 300
            },
            
            # Widget keys dimensions - Compact sidebar buttons
            "widget_keys": {
                "min_width": 34,
                "max_width": 40,
                "base_width": 36,
                "padding": 2,
                "border_radius": 5
            },
            
            # Key buttons (buttons in widget_*_keys containers) - Compact for small screens
            "key_button": {
                "min_size": 26,
                "max_size": 32,
                "icon_size": 16,
                "spacing": 2
            },
            
            # GroupBox dimensions - Compact grouping
            "groupbox": {
                "min_height": 60,
                "padding": 6,
                "title_padding": 4,
                "border_radius": 4
            },
            
            # Spacer dimensions - Harmonized spacing values
            "spacer": {
                "default_size": 8,      # Harmonized base spacer
                "section_main": 10,     # Main section spacer
                "section_exploring": 6, # Exploring section spacer
                "section_filtering": 8, # Filtering section spacer
                "section_exporting": 8, # Exporting section spacer
                "section_config": 12,   # Config section spacer
                "after_actions": 12     # Extra spacing after action buttons
            },
            
            # Labels and text
            "label": {
                "font_size": 14,
                "line_height": 21,
                "padding": 6
            },
            
            # Tree/List widgets
            "tree": {
                "item_height": 36,
                "indent": 24,
                "icon_size": 21
            },
            
            # List widget (for custom feature picker)
            "list": {
                "min_height": 225,  # Ratio 1.5x - minimum height to display 5-6 items
                "item_height": 36,
                "icon_size": 21
            },
            
            # Tab widget
            "tab": {
                "height": 42,
                "padding": {"top": 6, "right": 15, "bottom": 6, "left": 15},
                "font_size": 14
            },
            
            # Spacing and margins
            "spacing": {
                "small": 6,
                "medium": 12,
                "large": 20,
                "extra_large": 30
            },
            
            "margins": {
                "tight": {"top": 6, "right": 6, "bottom": 6, "left": 6},
                "normal": {"top": 12, "right": 12, "bottom": 12, "left": 12},
                "loose": {"top": 20, "right": 20, "bottom": 20, "left": 20}
            },
            
            # Scrollbar dimensions - aligned with splitter handle_width
            "scrollbar": {
                "width": 4,
                "handle_min_height": 20
            },
            
            # Dockwidget dimensions
            "dockwidget": {
                "min_width": 280,
                "min_height": 400,
                "preferred_width": 350,
                "preferred_height": 600
            }
        },
        
        "normal": {
            "description": "Standard layout for normal screens (desktops, large laptops)",
            
            # Button dimensions - More generous for large screens
            "button": {
                "height": 52,
                "icon_size": 28,
                "padding": {"top": 10, "right": 16, "bottom": 10, "left": 16},
                "border_radius": 10,
                "min_width": 140
            },
            
            # Action buttons (filter, export, etc.) - Larger touch targets
            "action_button": {
                "height": 36,
                "icon_size": 24,
                "padding": {"top": 5, "right": 8, "bottom": 5, "left": 8},
                "border_radius": 6,
                "min_width": 36
            },
            
            # Tool buttons (identify, zoom, etc.) - Better spacing
            "tool_button": {
                "height": 38,
                "icon_size": 26,
                "padding": {"top": 3, "right": 3, "bottom": 3, "left": 3},
                "border_radius": 5
            },
            
            # Key buttons (buttons in widget_*_keys containers) - Normal size for bigger screens
            "key_button": {
                "min_size": 30,
                "max_size": 36,
                "icon_size": 18,
                "spacing": 4
            },
            
            # Frame and container dimensions - More padding
            "frame": {
                "min_height": 100,
                "max_height": 250,
                "padding": 12,
                "border_width": 1,
                "border_radius": 8
            },
            
            # Action frame (top buttons area) - Normal profile, more spacious
            "action_frame": {
                "min_height": 64,
                "max_height": 80,
                "padding": 10
            },
            
            # Splitter dimensions - Enhanced configuration for responsiveness
            "splitter": {
                "handle_width": 8,
                "handle_margin": 50,  # Horizontal margin for the handle bar
                "exploring_stretch": 1,  # Stretch factor for frame_exploring (equal)
                "toolset_stretch": 1,    # Stretch factor for frame_toolset (equal)
                "collapsible": False,    # Whether frames can be collapsed
                "opaque_resize": True,   # Whether to show live resize
                "initial_exploring_ratio": 0.50,  # Initial ratio for exploring (50%)
                "initial_toolset_ratio": 0.50,    # Initial ratio for toolset (50%)
                "min_exploring_height": 180,      # Minimum height for exploring frame
                "min_toolset_height": 300         # Minimum height for toolset frame
            },
            
            # ComboBox dimensions - Better readability
            "combobox": {
                "height": 40,
                "padding": {"top": 6, "right": 12, "bottom": 6, "left": 12},
                "item_height": 40,
                "icon_size": 26
            },
            
            # SpinBox and input fields - Larger for ease of use
            "input": {
                "height": 40,
                "padding": {"top": 8, "right": 12, "bottom": 8, "left": 12},
                "border_radius": 8
            },
            
            # Header bar dimensions
            "header": {
                "height": 36,
                "min_height": 32,
                "padding": {"top": 8, "right": 12, "bottom": 8, "left": 12},
                "title_font_size": 13,
                "indicator_font_size": 10
            },
            
            # Layout dimensions - More generous spacing for large screens
            "layout": {
                "spacing_main": 12,       # Main container spacing
                "spacing_section": 12,    # Between sections
                "spacing_content": 10,    # Within content areas
                "spacing_buttons": 12,    # Between buttons
                "spacing_frame": 14,      # Internal frame spacing
                "margins_main": 12,       # Main container margins
                "margins_section": 12,    # Section margins
                "margins_content": 10,    # Content margins
                "margins_frame": {"left": 14, "top": 12, "right": 14, "bottom": 16},  # Frame margins
                "margins_actions": {"left": 12, "top": 10, "right": 12, "bottom": 16}  # Action bar margins
            },
            
            # Frame exploring dimensions - Enhanced with responsive size policy
            "frame_exploring": {
                "min_height": 180,
                "base_height": 260,
                "max_height": 500,
                "size_policy_h": "Preferred",
                "size_policy_v": "Minimum",  # Can shrink but has minimum
                "preferred_height": 280,
                "stretch_factor": 2
            },
            
            # Frame toolset dimensions - More space for content
            "frame_toolset": {
                "min_height": 300,
                "max_height": 16777215,  # QWIDGETSIZE_MAX
                "size_policy_h": "Preferred",
                "size_policy_v": "Expanding",  # Takes remaining space
                "preferred_height": 550,
                "stretch_factor": 5
            },
            
            # Frame filtering dimensions (inside toolset/toolbox)
            "frame_filtering": {
                "min_height": 260,
                "preferred_height": 400
            },
            
            # Widget keys dimensions - Wider for large screens
            "widget_keys": {
                "min_width": 56,
                "max_width": 72,
                "base_width": 64,
                "padding": 10,
                "border_radius": 8
            },
            
            # GroupBox dimensions - More padding
            "groupbox": {
                "min_height": 60,
                "padding": 10,
                "title_padding": 8,
                "border_radius": 6
            },
            
            # Spacer dimensions - More generous for visual breathing room
            "spacer": {
                "default_size": 14,     # Base spacer
                "section_main": 16,     # Main section spacer
                "section_exploring": 12, # Exploring section spacer
                "section_filtering": 14, # Filtering section spacer
                "section_exporting": 14, # Exporting section spacer
                "section_config": 18,   # Config section spacer
                "after_actions": 18     # Extra spacing after action buttons
            },
            
            # Labels and text - Better typography
            "label": {
                "font_size": 15,
                "line_height": 24,
                "padding": 8
            },
            
            # Tree/List widgets - More comfortable item height
            "tree": {
                "item_height": 40,
                "indent": 28,
                "icon_size": 21
            },
            
            # List widget (for custom feature picker)
            "list": {
                "min_height": 225,  # Ratio 1.5x - larger minimum for normal profile
                "item_height": 36,
                "icon_size": 21
            },
            
            # Tab widget
            "tab": {
                "height": 42,
                "padding": {"top": 6, "right": 15, "bottom": 6, "left": 15},
                "font_size": 14
            },
            
            # Spacing and margins
            "spacing": {
                "small": 6,
                "medium": 12,
                "large": 20,
                "extra_large": 30
            },
            
            "margins": {
                "tight": {"top": 6, "right": 6, "bottom": 6, "left": 6},
                "normal": {"top": 12, "right": 12, "bottom": 12, "left": 12},
                "loose": {"top": 20, "right": 20, "bottom": 20, "left": 20}
            },
            
            # Scrollbar dimensions - aligned with splitter handle_width
            "scrollbar": {
                "width": 6,
                "handle_min_height": 20
            },
            
            # Dockwidget dimensions - Generous sizing for large screens
            "dockwidget": {
                "min_width": 380,
                "min_height": 600,
                "preferred_width": 480,
                "preferred_height": 850,
                "responsive_breakpoints": {
                    "small": {"width": 350, "height": 500},
                    "medium": {"width": 450, "height": 700},
                    "large": {"width": 550, "height": 900}
                }
            },
            
            # Icon size scaling for readability
            "icon_scaling": {
                "small": 24,
                "medium": 28,
                "large": 32
            }
        },
        
        "hidpi": {
            "description": "HiDPI layout for high resolution displays (4K, Retina, high DPI)",
            
            # Button dimensions - Scaled up for HiDPI screens
            "button": {
                "height": 56,
                "icon_size": 32,
                "padding": {"top": 12, "right": 18, "bottom": 12, "left": 18},
                "border_radius": 12,
                "min_width": 160
            },
            
            # Action buttons (filter, export, etc.) - Larger for HiDPI
            "action_button": {
                "height": 42,
                "icon_size": 28,
                "padding": {"top": 6, "right": 10, "bottom": 6, "left": 10},
                "border_radius": 8,
                "min_width": 42
            },
            
            # Tool buttons (identify, zoom, etc.) - HiDPI optimized
            "tool_button": {
                "height": 44,
                "icon_size": 30,
                "padding": {"top": 4, "right": 4, "bottom": 4, "left": 4},
                "border_radius": 6
            },
            
            # Key buttons (buttons in widget_*_keys containers) - HiDPI for big screens
            "key_button": {
                "min_size": 36,
                "max_size": 44,
                "icon_size": 24,
                "spacing": 6
            },
            
            # Frame and container dimensions - More padding for HiDPI
            "frame": {
                "min_height": 120,
                "max_height": 280,
                "padding": 16,
                "border_width": 2,
                "border_radius": 10
            },
            
            # Action frame (top buttons area) - HiDPI profile
            "action_frame": {
                "min_height": 72,
                "max_height": 90,
                "padding": 12
            },
            
            # Splitter dimensions - HiDPI configuration
            "splitter": {
                "handle_width": 10,
                "handle_margin": 60,
                "exploring_stretch": 1,  # Equal stretch factor
                "toolset_stretch": 1,    # Equal stretch factor
                "collapsible": False,
                "opaque_resize": True,
                "initial_exploring_ratio": 0.50,  # Equal ratio (50%)
                "initial_toolset_ratio": 0.50,    # Equal ratio (50%)
                "min_exploring_height": 200,
                "min_toolset_height": 350
            },
            
            # ComboBox dimensions - HiDPI readability
            "combobox": {
                "height": 44,
                "padding": {"top": 8, "right": 14, "bottom": 8, "left": 14},
                "item_height": 44,
                "icon_size": 28
            },
            
            # SpinBox and input fields - HiDPI for ease of use
            "input": {
                "height": 44,
                "padding": {"top": 10, "right": 14, "bottom": 10, "left": 14},
                "border_radius": 10
            },
            
            # Header bar dimensions - HiDPI
            "header": {
                "height": 40,
                "min_height": 36,
                "padding": {"top": 10, "right": 14, "bottom": 10, "left": 14},
                "title_font_size": 14,
                "indicator_font_size": 11
            },
            
            # Layout dimensions - Generous spacing for HiDPI screens
            "layout": {
                "spacing_main": 14,
                "spacing_section": 14,
                "spacing_content": 12,
                "spacing_buttons": 14,
                "spacing_frame": 16,
                "margins_main": 14,
                "margins_section": 14,
                "margins_content": 12,
                "margins_frame": {"left": 16, "top": 14, "right": 16, "bottom": 18},
                "margins_actions": {"left": 14, "top": 12, "right": 14, "bottom": 18}
            },
            
            # Frame exploring dimensions - HiDPI with responsive size policy
            "frame_exploring": {
                "min_height": 200,
                "base_height": 300,
                "max_height": 550,
                "size_policy_h": "Preferred",
                "size_policy_v": "Minimum",
                "preferred_height": 320,
                "stretch_factor": 2
            },
            
            # Frame toolset dimensions - HiDPI more space for content
            "frame_toolset": {
                "min_height": 350,
                "max_height": 16777215,
                "size_policy_h": "Preferred",
                "size_policy_v": "Expanding",
                "preferred_height": 600,
                "stretch_factor": 5
            },
            
            # Frame filtering dimensions (inside toolset/toolbox)
            "frame_filtering": {
                "min_height": 300,
                "preferred_height": 450
            },
            
            # Widget keys dimensions - HiDPI for large screens (reduced for compact icons)
            "widget_keys": {
                "min_width": 50,
                "max_width": 60,
                "base_width": 54,
                "padding": 4,
                "border_radius": 8
            },
            
            # GroupBox dimensions - HiDPI more padding
            "groupbox": {
                "min_height": 70,
                "padding": 12,
                "title_padding": 10,
                "border_radius": 8
            },
            
            # Spacer dimensions - HiDPI generous for visual breathing room
            "spacer": {
                "default_size": 16,
                "section_main": 18,
                "section_exploring": 14,
                "section_filtering": 16,
                "section_exporting": 16,
                "section_config": 20,
                "after_actions": 20
            },
            
            # Labels and text - HiDPI better typography
            "label": {
                "font_size": 16,
                "line_height": 26,
                "padding": 10
            },
            
            # Tree/List widgets - HiDPI more comfortable item height
            "tree": {
                "item_height": 44,
                "indent": 32,
                "icon_size": 24
            },
            
            # List widget (for custom feature picker)
            "list": {
                "min_height": 260,
                "item_height": 40,
                "icon_size": 24
            },
            
            # Tab widget - HiDPI
            "tab": {
                "height": 48,
                "padding": {"top": 8, "right": 18, "bottom": 8, "left": 18},
                "font_size": 15
            },
            
            # Spacing and margins - HiDPI
            "spacing": {
                "small": 8,
                "medium": 14,
                "large": 24,
                "extra_large": 36
            },
            
            "margins": {
                "tight": {"top": 8, "right": 8, "bottom": 8, "left": 8},
                "normal": {"top": 14, "right": 14, "bottom": 14, "left": 14},
                "loose": {"top": 24, "right": 24, "bottom": 24, "left": 24}
            },
            
            # Scrollbar dimensions - HiDPI aligned with splitter handle_width
            "scrollbar": {
                "width": 8,
                "handle_min_height": 24
            },
            
            # Dockwidget dimensions - HiDPI generous sizing
            "dockwidget": {
                "min_width": 420,
                "min_height": 700,
                "preferred_width": 540,
                "preferred_height": 950,
                "responsive_breakpoints": {
                    "small": {"width": 400, "height": 600},
                    "medium": {"width": 500, "height": 800},
                    "large": {"width": 600, "height": 1000}
                }
            },
            
            # Icon size scaling for HiDPI readability
            "icon_scaling": {
                "small": 28,
                "medium": 32,
                "large": 40
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
        logger.debug(f"Switched to '{profile.value}' profile")
    
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
            logger.debug(f"Component '{component}' not found in profile '{profile_name}'")
            return None
        
        component_config = profile_config[component]
        
        if key is None:
            return component_config
        
        if key not in component_config:
            logger.debug(f"Key '{key}' not found in component '{component}'")
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
        Detect optimal UI profile based on screen resolution and DPI scaling.
        
        Analyzes the primary screen resolution and devicePixelRatio to determine
        the best profile for the current display configuration.
        
        Returns:
            DisplayProfile: COMPACT, NORMAL, or HIDPI based on screen characteristics
        
        Detection logic:
            1. HiDPI detection (devicePixelRatio > 1.5 OR physical resolution ≥ 3840x2160)
            2. Resolution-based detection:
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
                    # Get logical size (what the OS reports after DPI scaling)
                    logical_size = screen.size()
                    logical_width = logical_size.width()
                    logical_height = logical_size.height()
                    
                    # Get physical pixel ratio (DPI scaling factor)
                    device_pixel_ratio = screen.devicePixelRatio()
                    
                    # Calculate physical resolution (actual pixels)
                    physical_width = int(logical_width * device_pixel_ratio)
                    physical_height = int(logical_height * device_pixel_ratio)
                    
                    logger.debug(f"Screen detection: logical={logical_width}x{logical_height}, "
                                f"physical={physical_width}x{physical_height}, "
                                f"devicePixelRatio={device_pixel_ratio}")
                    
                    # HiDPI detection:
                    # - High DPI scaling (1.5x or higher) indicates HiDPI display
                    # - 4K resolution (3840x2160) or higher is HiDPI
                    # - Very high logical DPI (e.g., Retina displays)
                    is_hidpi = (
                        device_pixel_ratio >= 1.5 or
                        physical_width >= 3840 or
                        physical_height >= 2160
                    )
                    
                    if is_hidpi:
                        logger.info(f"HiDPI display detected (ratio={device_pixel_ratio}, "
                                   f"physical={physical_width}x{physical_height}) → HIDPI profile")
                        return DisplayProfile.HIDPI
                    
                    # Standard resolution detection for non-HiDPI displays
                    # Use logical resolution for profile selection
                    if logical_width < 1920 or logical_height < 1080:
                        logger.debug(f"Small screen detected ({logical_width}x{logical_height}) → COMPACT profile")
                        return DisplayProfile.COMPACT
                    else:
                        logger.debug(f"Large screen detected ({logical_width}x{logical_height}) → NORMAL profile")
                        return DisplayProfile.NORMAL
                        
        except Exception as e:
            logger.debug(f"Could not detect screen resolution: {e}")
        
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
                logger.debug("Auto-detection enabled")
                detected_profile = cls.detect_optimal_profile()
                cls.set_profile(detected_profile)
                logger.info(f"Auto-selected profile '{detected_profile.value}'")
            elif ui_profile == "compact":
                cls.set_profile(DisplayProfile.COMPACT)
                logger.debug("Loaded profile 'compact' from config")
            elif ui_profile == "normal":
                cls.set_profile(DisplayProfile.NORMAL)
                logger.debug("Loaded profile 'normal' from config")
            elif ui_profile == "hidpi":
                cls.set_profile(DisplayProfile.HIDPI)
                logger.debug("Loaded profile 'hidpi' from config")
            else:
                # Unknown value, default to auto-detection
                logger.debug(f"Unknown profile '{ui_profile}', using auto-detection")
                detected_profile = cls.detect_optimal_profile()
                cls.set_profile(detected_profile)
            
        except Exception as e:
            logger.warning(f"Could not load profile from config: {e}")
            cls.set_profile(DisplayProfile.NORMAL)


# Convenience function for quick access
def get_ui_config() -> UIConfig:
    """
    Get UIConfig singleton instance.
    
    Returns:
        UIConfig class (acts as singleton)
    """
    return UIConfig
