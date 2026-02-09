"""
FilterMate UI Configuration.

UI configuration utilities (display profiles, spacers, dimensions, etc.).

This module provides centralized UI configuration for FilterMate,
including responsive sizing, spacing, and theme settings.
"""

from typing import Any, Dict, Optional
from enum import Enum


class DisplayProfile(Enum):
    """Display profile enumeration for responsive UI sizing."""
    NORMAL = "normal"
    COMPACT = "compact"
    EXPANDED = "expanded"
    HIDPI = "hidpi"  # For backward compatibility with before_migration


class UIConfig:
    """
    Centralized UI configuration manager.
    
    Provides static methods to get/set UI configuration values
    for responsive sizing, spacing, and layout management.
    """
    
    # Current active profile - Use Enum for proper comparisons
    # v4.0.1 FIX #3: Restored COMPACT as default (NORMAL was causing -12% usable space on laptops)
    # AppInitializer._initialize_ui_profile() will upgrade to NORMAL for large screens (≥2560x1440)
    _active_profile: DisplayProfile = DisplayProfile.COMPACT
    
    # Default configuration values by profile
    # MIGRATED FROM before_migration/modules/ui_config.py - Full configuration restored
    _PROFILE_CONFIGS: Dict[str, Dict[str, Any]] = {
        DisplayProfile.NORMAL.value: {
            'dockwidget': {
                'min_width': 380,
                'min_height': 600,
                'preferred_width': 480,
                'preferred_height': 850,
                'max_width': 600,
                'responsive_breakpoints': {
                    'small': {'width': 350, 'height': 500},
                    'medium': {'width': 450, 'height': 700},
                    'large': {'width': 550, 'height': 900},
                },
            },
            'splitter': {
                'handle_width': 8,
                'handle_margin': 50,
                'collapsible': False,
                'opaque_resize': True,
                'exploring_stretch': 1,
                'toolset_stretch': 1,
                'min_exploring_height': 180,
                'min_toolset_height': 300,
                'initial_exploring_ratio': 0.50,
                'initial_toolset_ratio': 0.50,
            },
            'frame_exploring': {
                'min_height': 180,
                'base_height': 260,
                'max_height': 700,
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Minimum',
                'preferred_height': 280,
                'stretch_factor': 2,
            },
            'frame_toolset': {
                'min_height': 300,
                'max_height': 16777215,
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Expanding',
                'preferred_height': 550,
                'stretch_factor': 5,
            },
            'frame_filtering': {
                'min_height': 260,
                'preferred_height': 400,
            },
            'widget_keys': {
                'min_width': 56,
                'max_width': 72,
                'base_width': 64,
                'padding': 10,
                'border_radius': 8,
            },
            'groupbox': {
                'min_width': 250,  # Prevent overlap when splitter is resized
                'content_margins': {'top': 6, 'right': 8, 'bottom': 6, 'left': 8},
            },
            'combobox': {
                'height': 20,
                'min_height': 20,
                'max_height': 20,
                'padding': {'top': 2, 'right': 8, 'bottom': 2, 'left': 8},
                'item_height': 20,
                'icon_size': 16,
            },
            'input': {
                'height': 20,
                'min_height': 20,
                'max_height': 20,
                'padding': {'top': 2, 'right': 8, 'bottom': 2, 'left': 8},
                'border_radius': 4,
            },
            'button': {
                'height': 52,
                'min_width': 140,
                'icon_size': 28,
                'padding': {'top': 10, 'right': 16, 'bottom': 10, 'left': 16},
                'border_radius': 10,
            },
            'action_button': {
                'height': 36,
                'min_width': 36,
                'icon_size': 24,
                'padding': {'top': 5, 'right': 8, 'bottom': 5, 'left': 8},
                'border_radius': 6,
            },
            'tool_button': {
                'height': 38,
                'min_width': 38,
                'icon_size': 26,
                'padding': {'top': 3, 'right': 3, 'bottom': 3, 'left': 3},
                'border_radius': 5,
            },
            'key_button': {
                'width': 36,
                'height': 32,
                'min_size': 30,
                'max_size': 36,
                'icon_size': 18,
                'spacing': 4,
            },
            'header': {
                'height': 36,
                'min_height': 32,
                'padding': {'top': 8, 'right': 12, 'bottom': 8, 'left': 12},
                'title_font_size': 13,
                'indicator_font_size': 10,
            },
            'layout': {
                'spacing_main': 2,
                'spacing_section': 3,
                'spacing_content': 3,
                'spacing_buttons': 4,
                'spacing_frame': 4,
                'margins_main': 4,
                'margins_section': 4,
                'margins_content': 4,
                'margins_frame': {'left': 4, 'top': 4, 'right': 4, 'bottom': 6},
                'margins_actions': {'left': 4, 'top': 4, 'right': 4, 'bottom': 6},
            },
            'groupbox': {
                'min_height': 40,
                'padding': 4,
                'title_padding': 4,
                'border_radius': 6,
            },
            'spacer': {
                'default_size': 4,
                'section_main': 6,
                'section_exploring': 4,
                'section_filtering': 4,
                'section_exporting': 4,
                'section_config': 8,
                'after_actions': 8,
            },
            'label': {
                'font_size': 15,
                'line_height': 24,
                'padding': 8,
            },
            'tree': {
                'item_height': 40,
                'indent': 28,
                'icon_size': 21,
            },
            'list': {
                'min_height': 225,
                'item_height': 36,
                'icon_size': 21,
            },
            'tab': {
                'height': 42,
                'padding': {'top': 6, 'right': 15, 'bottom': 6, 'left': 15},
                'font_size': 14,
            },
            'scrollbar': {
                'width': 6,
                'handle_min_height': 20,
            },
            'spacing': {
                'small': 6,
                'medium': 12,
                'large': 20,
                'extra_large': 30,
            },
            'margins': {
                'tight': {'top': 6, 'right': 6, 'bottom': 6, 'left': 6},
                'normal': {'top': 12, 'right': 12, 'bottom': 12, 'left': 12},
                'loose': {'top': 20, 'right': 20, 'bottom': 20, 'left': 20},
            },
            'icon_scaling': {
                'small': 24,
                'medium': 28,
                'large': 32,
            },
            'action_frame': {
                'min_height': 64,
                'max_height': 80,
                'padding': 4,
            },
        },
        DisplayProfile.COMPACT.value: {
            'dockwidget': {
                'min_width': 280,
                'min_height': 320,
                'preferred_width': 350,
                'preferred_height': 550,
                'max_width': 450,
            },
            'splitter': {
                'handle_width': 4,
                'handle_margin': 30,
                'collapsible': True,
                'opaque_resize': True,
                'exploring_stretch': 1,
                'toolset_stretch': 1,
                'min_exploring_height': 80,
                'min_toolset_height': 150,
                'initial_exploring_ratio': 0.35,
                'initial_toolset_ratio': 0.65,
            },
            'frame_exploring': {
                'min_height': 150,
                'base_height': 220,
                'max_height': 600,
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Minimum',
                'preferred_height': 220,
            },
            'frame_toolset': {
                'min_height': 250,
                'max_height': 16777215,
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Expanding',
                'preferred_height': 400,
            },
            'frame_filtering': {
                'min_height': 180,
                'preferred_height': 280,
            },
            'widget_keys': {
                'min_width': 32,
                'max_width': 38,
                'base_width': 34,
                'padding': 1,
                'border_radius': 5,
            },            'groupbox': {
                'min_width': 200,  # Prevent overlap when splitter is resized (compact mode)
                'content_margins': {'top': 4, 'right': 6, 'bottom': 4, 'left': 6},
            },            'combobox': {
                'height': 20,
                'min_height': 20,
                'max_height': 20,
                'padding': {'top': 5, 'right': 9, 'bottom': 5, 'left': 9},
                'item_height': 36,
                'icon_size': 24,
            },
            'input': {
                'height': 20,
                'min_height': 20,
                'max_height': 20,
                'padding': {'top': 2, 'right': 8, 'bottom': 2, 'left': 8},
                'border_radius': 4,
            },
            'button': {
                'height': 42,
                'min_width': 110,
                'icon_size': 24,
                'padding': {'top': 8, 'right': 14, 'bottom': 8, 'left': 14},
                'border_radius': 8,
            },
            'action_button': {
                'height': 34,
                'min_width': 34,
                'icon_size': 22,
                'padding': {'top': 6, 'right': 8, 'bottom': 6, 'left': 8},
                'border_radius': 6,
            },
            'tool_button': {
                'height': 36,
                'min_width': 36,
                'icon_size': 24,
                'padding': {'top': 4, 'right': 4, 'bottom': 4, 'left': 4},
                'border_radius': 5,
            },
            'key_button': {
                'width': 34,
                'height': 30,
                'min_size': 28,
                'max_size': 34,
                'icon_size': 18,
                'spacing': 1,
            },
            'header': {
                'height': 28,
                'min_height': 24,
                'padding': {'top': 4, 'right': 8, 'bottom': 4, 'left': 8},
                'title_font_size': 11,
                'indicator_font_size': 8,
            },
            'layout': {
                'spacing_main': 4,
                'spacing_section': 4,
                'spacing_content': 4,
                'spacing_buttons': 4,
                'spacing_frame': 6,
                'margins_main': 4,
                'margins_section': 4,
                'margins_content': 4,
                'margins_frame': {'left': 4, 'top': 4, 'right': 4, 'bottom': 6},
                'margins_actions': {'left': 4, 'top': 4, 'right': 4, 'bottom': 6},
            },
            'groupbox': {
                'min_height': 60,
                'padding': 4,
                'title_padding': 4,
                'border_radius': 5,
            },
            'spacer': {
                'default_size': 4,
                'section_main': 6,
                'section_exploring': 3,
                'section_filtering': 4,
                'section_exporting': 4,
                'section_config': 8,
                'after_actions': 8,
            },
            'label': {
                'font_size': 14,
                'line_height': 21,
                'padding': 6,
            },
            'tree': {
                'item_height': 36,
                'indent': 24,
                'icon_size': 21,
            },
            'list': {
                'min_height': 225,
                'item_height': 36,
                'icon_size': 21,
            },
            'tab': {
                'height': 42,
                'padding': {'top': 6, 'right': 15, 'bottom': 6, 'left': 15},
                'font_size': 14,
            },
            'scrollbar': {
                'width': 4,
                'handle_min_height': 20,
            },
            'spacing': {
                'small': 6,
                'medium': 12,
                'large': 20,
                'extra_large': 30,
            },
            'margins': {
                'tight': {'top': 6, 'right': 6, 'bottom': 6, 'left': 6},
                'normal': {'top': 12, 'right': 12, 'bottom': 12, 'left': 12},
                'loose': {'top': 20, 'right': 20, 'bottom': 20, 'left': 20},
            },
            'action_frame': {
                'min_height': 56,
                'max_height': 70,
                'padding': 3,
            },
        },
        DisplayProfile.EXPANDED.value: {
            'dockwidget': {
                'min_width': 400,
                'min_height': 550,
                'preferred_width': 520,
                'preferred_height': 900,
                'max_width': 700,
            },
            'splitter': {
                'handle_width': 10,
                'handle_margin': 60,
                'collapsible': False,
                'opaque_resize': True,
                'exploring_stretch': 2,
                'toolset_stretch': 3,
                'min_exploring_height': 220,
                'min_toolset_height': 400,
                'initial_exploring_ratio': 0.45,
                'initial_toolset_ratio': 0.55,
            },
            'frame_exploring': {
                'min_height': 220,
                'base_height': 320,
                'max_height': 600,
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Minimum',
                'preferred_height': 350,
                'stretch_factor': 3,
            },
            'frame_toolset': {
                'min_height': 400,
                'max_height': 16777215,
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Expanding',
                'preferred_height': 650,
                'stretch_factor': 5,
            },
            'frame_filtering': {
                'min_height': 320,
                'preferred_height': 480,
            },
            'widget_keys': {
                'min_width': 72,
                'max_width': 88,
                'base_width': 80,
                'padding': 14,
                'border_radius': 10,
            },
            'combobox': {
                'height': 48,
                'min_height': 44,
                'max_height': 52,
                'padding': {'top': 8, 'right': 16, 'bottom': 8, 'left': 16},
                'item_height': 48,
                'icon_size': 30,
            },
            'input': {
                'height': 48,
                'min_height': 44,
                'max_height': 52,
                'padding': {'top': 10, 'right': 16, 'bottom': 10, 'left': 16},
                'border_radius': 10,
            },
            'button': {
                'height': 60,
                'min_width': 160,
                'icon_size': 32,
                'padding': {'top': 12, 'right': 20, 'bottom': 12, 'left': 20},
                'border_radius': 12,
            },
            'action_button': {
                'height': 44,
                'min_width': 44,
                'icon_size': 28,
                'padding': {'top': 6, 'right': 10, 'bottom': 6, 'left': 10},
                'border_radius': 8,
            },
            'tool_button': {
                'height': 46,
                'min_width': 46,
                'icon_size': 30,
                'padding': {'top': 4, 'right': 4, 'bottom': 4, 'left': 4},
                'border_radius': 6,
            },
            'key_button': {
                'width': 44,
                'height': 40,
                'min_size': 36,
                'max_size': 44,
                'icon_size': 22,
                'spacing': 2,
            },
            'header': {
                'height': 44,
                'min_height': 40,
                'padding': {'top': 10, 'right': 16, 'bottom': 10, 'left': 16},
                'title_font_size': 15,
                'indicator_font_size': 12,
            },
            'layout': {
                'spacing_main': 3,
                'spacing_section': 4,
                'spacing_content': 4,
                'spacing_buttons': 5,
                'spacing_frame': 5,
                'margins_main': 5,
                'margins_section': 5,
                'margins_content': 5,
                'margins_frame': {'left': 5, 'top': 5, 'right': 5, 'bottom': 7},
                'margins_actions': {'left': 5, 'top': 5, 'right': 5, 'bottom': 7},
            },
            'groupbox': {
                'min_height': 50,
                'padding': 5,
                'title_padding': 5,
                'border_radius': 8,
            },
            'spacer': {
                'default_size': 5,
                'section_main': 7,
                'section_exploring': 5,
                'section_filtering': 5,
                'section_exporting': 5,
                'section_config': 10,
                'after_actions': 10,
            },
            'label': {
                'font_size': 17,
                'line_height': 28,
                'padding': 10,
            },
            'tree': {
                'item_height': 48,
                'indent': 32,
                'icon_size': 24,
            },
            'list': {
                'min_height': 280,
                'item_height': 44,
                'icon_size': 24,
            },
            'tab': {
                'height': 50,
                'padding': {'top': 8, 'right': 18, 'bottom': 8, 'left': 18},
                'font_size': 16,
            },
            'scrollbar': {
                'width': 8,
                'handle_min_height': 24,
            },
            'spacing': {
                'small': 8,
                'medium': 16,
                'large': 24,
                'extra_large': 36,
            },
            'margins': {
                'tight': {'top': 8, 'right': 8, 'bottom': 8, 'left': 8},
                'normal': {'top': 16, 'right': 16, 'bottom': 16, 'left': 16},
                'loose': {'top': 24, 'right': 24, 'bottom': 24, 'left': 24},
            },
            'icon_scaling': {
                'small': 28,
                'medium': 32,
                'large': 40,
            },
            'action_frame': {
                'min_height': 80,
                'max_height': 96,
                'padding': 5,
            },
        },
        # HIDPI profile for high DPI displays (4K, Retina)
        DisplayProfile.HIDPI.value: {
            'dockwidget': {
                'min_width': 480,
                'min_height': 700,
                'preferred_width': 600,
                'preferred_height': 1000,
                'max_width': 800,
            },
            'splitter': {
                'handle_width': 12,
                'handle_margin': 80,
                'collapsible': False,
                'opaque_resize': True,
                'exploring_stretch': 2,
                'toolset_stretch': 3,
                'min_exploring_height': 280,
                'min_toolset_height': 500,
                'initial_exploring_ratio': 0.45,
                'initial_toolset_ratio': 0.55,
            },
            'frame_exploring': {
                'min_height': 280,
                'base_height': 400,
                'max_height': 700,
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Minimum',
                'preferred_height': 420,
                'stretch_factor': 3,
            },
            'frame_toolset': {
                'min_height': 500,
                'max_height': 16777215,
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Expanding',
                'preferred_height': 800,
                'stretch_factor': 5,
            },
            'frame_filtering': {
                'min_height': 400,
                'preferred_height': 600,
            },
            'widget_keys': {
                'min_width': 88,
                'max_width': 104,
                'base_width': 96,
                'padding': 18,
                'border_radius': 12,
            },
            'combobox': {
                'height': 20,
                'min_height': 20,
                'max_height': 20,
                'padding': {'top': 2, 'right': 8, 'bottom': 2, 'left': 8},
                'item_height': 20,
                'icon_size': 16,
            },
            'input': {
                'height': 56,
                'min_height': 52,
                'max_height': 60,
                'padding': {'top': 12, 'right': 20, 'bottom': 12, 'left': 20},
                'border_radius': 12,
            },
            'button': {
                'height': 72,
                'min_width': 180,
                'icon_size': 40,
                'padding': {'top': 14, 'right': 24, 'bottom': 14, 'left': 24},
                'border_radius': 14,
            },
            'action_button': {
                'height': 52,
                'min_width': 52,
                'icon_size': 32,
                'padding': {'top': 8, 'right': 12, 'bottom': 8, 'left': 12},
                'border_radius': 10,
            },
            'tool_button': {
                'height': 54,
                'min_width': 54,
                'icon_size': 36,
                'padding': {'top': 5, 'right': 5, 'bottom': 5, 'left': 5},
                'border_radius': 8,
            },
            'key_button': {
                'width': 52,
                'height': 48,
                'min_size': 44,
                'max_size': 52,
                'icon_size': 28,
                'spacing': 2,
            },
            'header': {
                'height': 52,
                'min_height': 48,
                'padding': {'top': 12, 'right': 20, 'bottom': 12, 'left': 20},
                'title_font_size': 17,
                'indicator_font_size': 14,
            },
            'layout': {
                'spacing_main': 4,
                'spacing_section': 5,
                'spacing_content': 5,
                'spacing_buttons': 6,
                'spacing_frame': 6,
                'margins_main': 6,
                'margins_section': 6,
                'margins_content': 6,
                'margins_frame': {'left': 6, 'top': 6, 'right': 6, 'bottom': 8},
                'margins_actions': {'left': 6, 'top': 6, 'right': 6, 'bottom': 8},
            },
            'groupbox': {
                'min_height': 60,
                'padding': 6,
                'title_padding': 6,
                'border_radius': 10,
            },
            'spacer': {
                'default_size': 6,
                'section_main': 8,
                'section_exploring': 6,
                'section_filtering': 6,
                'section_exporting': 6,
                'section_config': 12,
                'after_actions': 12,
            },
            'label': {
                'font_size': 20,
                'line_height': 32,
                'padding': 12,
            },
            'tree': {
                'item_height': 56,
                'indent': 40,
                'icon_size': 28,
            },
            'list': {
                'min_height': 350,
                'item_height': 52,
                'icon_size': 28,
            },
            'tab': {
                'height': 58,
                'padding': {'top': 10, 'right': 22, 'bottom': 10, 'left': 22},
                'font_size': 18,
            },
            'scrollbar': {
                'width': 10,
                'handle_min_height': 28,
            },
            'spacing': {
                'small': 10,
                'medium': 20,
                'large': 30,
                'extra_large': 44,
            },
            'margins': {
                'tight': {'top': 10, 'right': 10, 'bottom': 10, 'left': 10},
                'normal': {'top': 20, 'right': 20, 'bottom': 20, 'left': 20},
                'loose': {'top': 30, 'right': 30, 'bottom': 30, 'left': 30},
            },
            'icon_scaling': {
                'small': 32,
                'medium': 40,
                'large': 48,
            },
            'action_frame': {
                'min_height': 96,
                'max_height': 116,
                'padding': 6,
            },
        },
    }
    
    @classmethod
    def set_profile(cls, profile) -> None:
        """
        Set the active display profile.
        
        Args:
            profile: DisplayProfile enum value or string name (NORMAL, COMPACT, EXPANDED)
        """
        if isinstance(profile, DisplayProfile):
            cls._active_profile = profile
        elif isinstance(profile, str):
            profile_lower = profile.lower()
            for p in DisplayProfile:
                if p.value == profile_lower:
                    cls._active_profile = p
                    return
            cls._active_profile = DisplayProfile.NORMAL
        else:
            cls._active_profile = DisplayProfile.NORMAL
    
    @classmethod
    def get_profile(cls) -> DisplayProfile:
        """
        Get the current active display profile as Enum.
        
        Returns:
            DisplayProfile: Active profile enum
        """
        return cls._active_profile
    
    @classmethod
    def get_active_profile(cls) -> DisplayProfile:
        """
        Get the current active profile.
        
        Returns:
            DisplayProfile: Active profile enum
        """
        return cls._active_profile
    
    @classmethod
    def get_profile_name(cls) -> str:
        """
        Get the human-readable name of the current active profile.
        
        Returns:
            str: Active profile name (e.g., 'normal', 'compact', 'expanded')
        """
        if isinstance(cls._active_profile, DisplayProfile):
            return cls._active_profile.value
        return str(cls._active_profile)
    
    @classmethod
    def get_config(cls, *keys) -> Any:
        """
        Get configuration value for the active profile.
        
        Args:
            *keys: Nested keys to access (e.g., 'splitter', 'handle_width')
                   Can also be used as (component, key) for backward compatibility
        
        Returns:
            Configuration value or None if not found
        """
        # Get profile value string for dict lookup
        profile_name = cls._active_profile.value if isinstance(cls._active_profile, DisplayProfile) else cls._active_profile
        profile_config = cls._PROFILE_CONFIGS.get(profile_name, {})
        
        if not keys:
            return profile_config
        
        # Navigate through nested keys
        value = profile_config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return None
        
        return value
    
    @classmethod
    def get_button_height(cls, button_type: str = "button") -> int:
        """
        Get button height for current profile.
        
        Args:
            button_type: 'button', 'action_button', 'tool_button', or 'key_button'
        
        Returns:
            Height in pixels
        """
        config = cls.get_config(button_type)
        if config and isinstance(config, dict):
            return config.get('height', 28)
        return 28
    
    @classmethod
    def get_icon_size(cls, button_type: str = "button") -> int:
        """
        Get icon size for current profile.
        
        Args:
            button_type: 'button', 'action_button', 'tool_button', or 'key_button'
        
        Returns:
            Icon size in pixels
        """
        config = cls.get_config(button_type)
        if config and isinstance(config, dict):
            return config.get('icon_size', 18)
        # Fallback based on button type
        fallbacks = {'action_button': 20, 'tool_button': 22, 'key_button': 16, 'button': 18}
        return fallbacks.get(button_type, 18)
    
    @classmethod
    def get_padding_string(cls, component: str) -> str:
        """
        Get CSS padding string for a component.
        
        Args:
            component: Component name ('button', 'action_button', etc.)
        
        Returns:
            str: CSS padding value (e.g., '4px 8px')
        """
        # Default paddings
        paddings = {
            'button': '4px 8px',
            'action_button': '4px 12px',
            'key_button': '2px 4px',
            'combobox': '4px 8px',
            'frame': '6px',
        }
        return paddings.get(component, '4px')
    
    @classmethod
    def detect_profile_from_screen(cls) -> str:
        """
        Auto-detect best profile based on screen resolution.
        
        Returns:
            str: Recommended profile name
        """
        try:
            from qgis.PyQt.QtWidgets import QApplication
            screen = QApplication.primaryScreen()
            if screen:
                geometry = screen.geometry()
                height = geometry.height()
                
                if height < 800:
                    return DisplayProfile.COMPACT
                elif height > 1200:
                    return DisplayProfile.EXPANDED
                else:
                    return DisplayProfile.NORMAL
        except Exception:
            pass
        
        return DisplayProfile.NORMAL


# Import ui_elements for centralized spacer/layout references
from .ui_elements import (
    SPACERS,
    LAYOUTS,
    ALL_SPACERS,
    ALL_LAYOUTS,
    get_spacers_by_section,
    get_layouts_by_section,
    get_spacer_size,
    get_layout_spacing,
    get_section_names,
    find_element_section,
)

__all__ = [
    'UIConfig',
    'DisplayProfile',
    # UI Elements
    'SPACERS',
    'LAYOUTS',
    'ALL_SPACERS',
    'ALL_LAYOUTS',
    'get_spacers_by_section',
    'get_layouts_by_section',
    'get_spacer_size',
    'get_layout_spacing',
    'get_section_names',
    'find_element_section',
]
