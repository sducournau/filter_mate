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
    # REGRESSION FIX: Default to NORMAL instead of COMPACT (was causing 26-32px buttons instead of 30-36px)
    # AppInitializer._initialize_ui_profile() will override based on screen resolution if needed
    _active_profile: DisplayProfile = DisplayProfile.NORMAL
    
    # Default configuration values by profile
    _PROFILE_CONFIGS: Dict[str, Dict[str, Any]] = {
        DisplayProfile.NORMAL.value: {
            'dockwidget': {
                'min_width': 340,
                'min_height': 400,
                'preferred_width': 380,
                'max_width': 500,
            },
            'splitter': {
                'handle_width': 6,
                'handle_margin': 40,
                'collapsible': False,
                'opaque_resize': True,
                'exploring_stretch': 2,
                'toolset_stretch': 5,
                'initial_exploring_ratio': 0.50,
                'initial_toolset_ratio': 0.50,
            },
            'frame_exploring': {
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Minimum',
            },
            'frame_toolset': {
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Expanding',
            },
            'combobox': {
                'height': 26,
                'min_height': 24,
                'max_height': 32,
            },
            'input': {
                'height': 26,
                'min_height': 24,
                'max_height': 32,
            },
            'button': {
                'height': 28,
                'min_width': 28,
                'icon_size': 18,
            },
            'action_button': {
                'height': 32,
                'min_width': 32,
                'icon_size': 20,
            },
            'tool_button': {
                'height': 34,
                'min_width': 34,
                'icon_size': 22,
            },
            'key_button': {
                'width': 32,
                'height': 28,
                'min_size': 26,
                'max_size': 32,
                'icon_size': 16,
                'spacing': 4,
            },
            'layout': {
                'spacing_frame': 8,
                'spacing_content': 6,
                'spacing_section': 8,
                'spacing_main': 8,
                'margins_frame': (6, 6, 6, 6),
                'margins_actions': (4, 4, 4, 4),
            },
            'groupbox': {
                'min_height': 60,
            },
        },
        DisplayProfile.COMPACT.value: {
            'dockwidget': {
                'min_width': 280,
                'min_height': 300,
                'preferred_width': 320,
                'max_width': 400,
            },
            'splitter': {
                'handle_width': 4,
                'handle_margin': 30,
                'collapsible': True,
                'opaque_resize': True,
                'exploring_stretch': 1,
                'toolset_stretch': 4,
                'initial_exploring_ratio': 0.40,
                'initial_toolset_ratio': 0.60,
            },
            'frame_exploring': {
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Fixed',
            },
            'frame_toolset': {
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Expanding',
            },
            'combobox': {
                'height': 24,
                'min_height': 22,
                'max_height': 28,
            },
            'input': {
                'height': 24,
                'min_height': 22,
                'max_height': 28,
            },
            'button': {
                'height': 24,
                'min_width': 24,
                'icon_size': 16,
            },
            'action_button': {
                'height': 28,
                'min_width': 28,
                'icon_size': 18,
            },
            'tool_button': {
                'height': 30,
                'min_width': 30,
                'icon_size': 20,
            },
            'key_button': {
                'width': 28,
                'height': 24,
                'min_size': 22,
                'max_size': 28,
                'icon_size': 14,
                'spacing': 2,
            },
            'layout': {
                'spacing_frame': 4,
                'spacing_content': 4,
                'spacing_section': 4,
                'spacing_main': 4,
                'margins_frame': (4, 4, 4, 4),
                'margins_actions': (2, 2, 2, 2),
            },
            'groupbox': {
                'min_height': 50,
            },
        },
        DisplayProfile.EXPANDED.value: {
            'dockwidget': {
                'min_width': 400,
                'min_height': 500,
                'preferred_width': 450,
                'max_width': 600,
            },
            'splitter': {
                'handle_width': 8,
                'handle_margin': 50,
                'collapsible': False,
                'opaque_resize': True,
                'exploring_stretch': 3,
                'toolset_stretch': 5,
                'initial_exploring_ratio': 0.55,
                'initial_toolset_ratio': 0.45,
            },
            'frame_exploring': {
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Preferred',
            },
            'frame_toolset': {
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Expanding',
            },
            'combobox': {
                'height': 30,
                'min_height': 28,
                'max_height': 36,
            },
            'input': {
                'height': 30,
                'min_height': 28,
                'max_height': 36,
            },
            'button': {
                'height': 32,
                'min_width': 32,
                'icon_size': 20,
            },
            'action_button': {
                'height': 36,
                'min_width': 36,
                'icon_size': 24,
            },
            'tool_button': {
                'height': 38,
                'min_width': 38,
                'icon_size': 26,
            },
            'key_button': {
                'width': 36,
                'height': 32,
                'min_size': 30,
                'max_size': 38,
                'icon_size': 20,
                'spacing': 6,
            },
            'layout': {
                'spacing_frame': 10,
                'spacing_content': 8,
                'spacing_section': 10,
                'spacing_main': 10,
                'margins_frame': (8, 8, 8, 8),
                'margins_actions': (6, 6, 6, 6),
            },
            'groupbox': {
                'min_height': 70,
            },
        },
        # HIDPI profile for high DPI displays
        DisplayProfile.HIDPI.value: {
            'dockwidget': {
                'min_width': 420,
                'min_height': 520,
                'preferred_width': 480,
                'max_width': 650,
            },
            'splitter': {
                'handle_width': 10,
                'handle_margin': 60,
                'collapsible': False,
                'opaque_resize': True,
                'exploring_stretch': 3,
                'toolset_stretch': 5,
                'initial_exploring_ratio': 0.50,
                'initial_toolset_ratio': 0.50,
            },
            'frame_exploring': {
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Preferred',
            },
            'frame_toolset': {
                'size_policy_h': 'Preferred',
                'size_policy_v': 'Expanding',
            },
            'combobox': {
                'height': 36,
                'min_height': 32,
                'max_height': 44,
            },
            'input': {
                'height': 36,
                'min_height': 32,
                'max_height': 44,
            },
            'button': {
                'height': 38,
                'min_width': 38,
                'icon_size': 24,
            },
            'action_button': {
                'height': 44,
                'min_width': 44,
                'icon_size': 28,
            },
            'tool_button': {
                'height': 44,
                'min_width': 44,
                'icon_size': 28,
            },
            'key_button': {
                'width': 44,
                'height': 38,
                'min_size': 36,
                'max_size': 44,
                'icon_size': 24,
                'spacing': 6,
            },
            'layout': {
                'spacing_frame': 12,
                'spacing_content': 10,
                'spacing_section': 12,
                'spacing_main': 12,
                'margins_frame': (10, 10, 10, 10),
                'margins_actions': (8, 8, 8, 8),
            },
            'groupbox': {
                'min_height': 80,
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


__all__ = [
    'UIConfig',
    'DisplayProfile',
]
