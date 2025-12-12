# -*- coding: utf-8 -*-
"""
Example: Dynamic Spacer Configuration

Demonstrates how to use the harmonized UI element names 
to apply dynamic dimensions in compact/normal modes.
"""

from PyQt5.QtWidgets import QSpacerItem, QWidget, QSizePolicy
from typing import Optional

try:
    from modules.ui_elements import (
        SPACERS, get_spacers_by_section, get_spacer_size
    )
    from modules.ui_config import UIConfig, DisplayProfile
except ImportError:
    # Fallback for testing
    SPACERS = {}


def apply_spacer_dimensions(widget: QWidget, compact_mode: bool = True) -> int:
    """
    Apply dynamic dimensions to all spacers in the widget based on display mode.
    
    Args:
        widget: Root widget containing the spacers
        compact_mode: True for compact mode, False for normal mode
    
    Returns:
        Number of spacers configured
    """
    count = 0
    
    # Iterate through all sections
    for section, spacer_names in SPACERS.items():
        for spacer_name in spacer_names:
            # Find the spacer widget
            spacer = widget.findChild(QSpacerItem, spacer_name)
            if spacer:
                # Get recommended size for this section and mode
                size = get_spacer_size(spacer_name, compact_mode)
                
                # Apply size based on orientation
                if "vertical" in spacer_name.lower():
                    spacer.changeSize(
                        spacer.sizeHint().width(),
                        size,
                        QSizePolicy.Minimum,
                        QSizePolicy.Expanding
                    )
                else:  # horizontal
                    spacer.changeSize(
                        size,
                        spacer.sizeHint().height(),
                        QSizePolicy.Expanding,
                        QSizePolicy.Minimum
                    )
                
                count += 1
    
    return count


def apply_section_spacer_dimensions(
    widget: QWidget, 
    section: str, 
    compact_mode: bool = True,
    custom_size: Optional[int] = None
) -> int:
    """
    Apply dimensions to spacers in a specific section only.
    
    Args:
        widget: Root widget containing the spacers
        section: Section name (e.g., 'exploring', 'filtering_keys')
        compact_mode: True for compact mode, False for normal mode
        custom_size: Override size (if None, uses default for section)
    
    Returns:
        Number of spacers configured
    """
    count = 0
    spacer_names = get_spacers_by_section(section)
    
    for spacer_name in spacer_names:
        spacer = widget.findChild(QSpacerItem, spacer_name)
        if spacer:
            # Use custom size or get recommended size
            if custom_size is not None:
                size = custom_size
            else:
                size = get_spacer_size(spacer_name, compact_mode)
            
            # Apply size
            if "vertical" in spacer_name.lower():
                spacer.changeSize(
                    spacer.sizeHint().width(),
                    size,
                    QSizePolicy.Minimum,
                    QSizePolicy.Expanding
                )
            else:
                spacer.changeSize(
                    size,
                    spacer.sizeHint().height(),
                    QSizePolicy.Expanding,
                    QSizePolicy.Minimum
                )
            
            count += 1
    
    return count


def toggle_display_mode(widget: QWidget, set_compact: bool) -> None:
    """
    Toggle between compact and normal display modes.
    
    Args:
        widget: Root widget containing UI elements
        set_compact: True to switch to compact, False for normal
    """
    # Update UIConfig profile
    try:
        profile = DisplayProfile.COMPACT if set_compact else DisplayProfile.NORMAL
        UIConfig.set_profile(profile)
    except (ImportError, AttributeError):
        pass
    
    # Apply spacer dimensions
    count = apply_spacer_dimensions(widget, compact_mode=set_compact)
    
    # Trigger layout update
    widget.update()
    widget.adjustSize()


# =============================================================================
# USAGE EXAMPLE IN FilterMate
# =============================================================================

"""
In filter_mate_app.py or filter_mate_dockwidget.py:

def setup_ui_dimensions(self):
    '''Initialize UI with appropriate dimensions based on display mode.'''
    from modules.ui_elements_helpers import apply_spacer_dimensions
    
    # Detect screen size and choose mode
    screen = QApplication.primaryScreen()
    screen_height = screen.size().height()
    compact_mode = screen_height < 900  # Use compact for small screens
    
    # Apply dimensions
    count = apply_spacer_dimensions(self, compact_mode=compact_mode)
    print(f"FilterMate: Configured {count} spacers in {'compact' if compact_mode else 'normal'} mode")


def toggle_compact_mode(self):
    '''Toggle between compact and normal modes (e.g., from menu action).'''
    from modules.ui_elements_helpers import toggle_display_mode
    
    self.compact_mode = not self.compact_mode
    toggle_display_mode(self, self.compact_mode)


def configure_section_spacing(self, section: str, size: int):
    '''Configure spacing for a specific section.'''
    from modules.ui_elements_helpers import apply_section_spacer_dimensions
    
    count = apply_section_spacer_dimensions(
        self, 
        section=section, 
        compact_mode=self.compact_mode,
        custom_size=size
    )
    print(f"Updated {count} spacers in '{section}' section to {size}px")
"""

# =============================================================================
# LAYOUT SPACING CONFIGURATION
# =============================================================================

def apply_layout_spacing(widget: QWidget, compact_mode: bool = True) -> int:
    """
    Apply dynamic spacing to all layouts based on display mode.
    
    Uses the granular spacing configuration from UIConfig to apply
    different spacing values to:
    - Main container layouts (spacing_main)
    - Section layouts like exploring, filtering (spacing_section)
    - Content layouts for keys/values (spacing_content)
    - Button layouts (spacing_buttons)
    
    Args:
        widget: Root widget containing the layouts
        compact_mode: True for compact mode, False for normal mode
    
    Returns:
        Number of layouts configured
    """
    from modules.ui_elements import LAYOUTS
    from modules.ui_config import UIConfig, DisplayProfile
    
    # Set the profile to get correct config
    profile = DisplayProfile.COMPACT if compact_mode else DisplayProfile.NORMAL
    UIConfig.set_profile(profile)
    
    # Get layout configuration
    layout_config = UIConfig.get_config('layout')
    
    count = 0
    
    # Define spacing rules per layout type
    spacing_rules = {
        # Main container - tightest spacing
        'main': layout_config.get('spacing_main', 3 if compact_mode else 6),
        # Sections - moderate spacing
        'section': layout_config.get('spacing_section', 4 if compact_mode else 8),
        # Content - tight spacing
        'content': layout_config.get('spacing_content', 3 if compact_mode else 6),
        # Buttons - comfortable spacing
        'buttons': layout_config.get('spacing_buttons', 4 if compact_mode else 8),
    }
    
    margin_rules = {
        'main': layout_config.get('margins_main', 2 if compact_mode else 4),
        'section': layout_config.get('margins_section', 3 if compact_mode else 6),
        'content': layout_config.get('margins_content', 2 if compact_mode else 4),
    }
    
    for section, layout_names in LAYOUTS.items():
        # Determine spacing based on section
        if section == 'main':
            spacing = spacing_rules['main']
            margins = margin_rules['main']
        elif section in ['exploring', 'filtering', 'exporting', 'config']:
            spacing = spacing_rules['section']
            margins = margin_rules['section']
        elif 'buttons' in section or 'actions' in section:
            spacing = spacing_rules['buttons']
            margins = margin_rules['content']
        else:
            spacing = spacing_rules['content']
            margins = margin_rules['content']
        
        for layout_name in layout_names:
            # Try to find the widget that has this layout
            # Note: Layouts don't have names as widgets, we need to find parent widget
            # For now, skip - this would need widget tree traversal
            pass
    
    # Alternative: Find layouts directly by object name if they're named QLayouts
    # This is more complex and would require QGIS-specific implementation
    
    return count
