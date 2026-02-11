# -*- coding: utf-8 -*-
"""
UI Elements Reference for FilterMate

Centralized reference for all named UI elements (spacers and layouts)
after harmonization. Useful for programmatic access and dynamic configuration.

Migrated from before_migration/modules/ui_elements.py for v4.0 hexagonal architecture.
"""

from typing import List, Dict, Optional

# =============================================================================
# SPACERS REFERENCE
# =============================================================================

# Organized by section for easy programmatic access
SPACERS: Dict[str, List[str]] = {
    "main": [
        "verticalSpacer_main_top",
        "horizontalSpacer_main_right",
    ],

    "exploring": [
        "verticalSpacer_exploring_tab_top",
        "verticalSpacer_exploring_tab_bottom",
        "verticalSpacer_exploring_single_top",
        "verticalSpacer_exploring_single_middle",
        "verticalSpacer_exploring_single_bottom",
        "verticalSpacer_exploring_multiple_top",
        "verticalSpacer_exploring_multiple_bottom",
        "verticalSpacer_exploring_custom_bottom",
    ],

    "filtering_keys": [
        "verticalSpacer_filtering_keys_field_top",
        "verticalSpacer_filtering_keys_field_middle1",
        "verticalSpacer_filtering_keys_field_middle2",
        "verticalSpacer_filtering_keys_field_middle3",
        "verticalSpacer_filtering_keys_field_bottom",
    ],

    "filtering_values": [
        "verticalSpacer_filtering_values_top",
        "verticalSpacer_filtering_values_search_top",
        "verticalSpacer_filtering_values_buttons_top",
        "verticalSpacer_filtering_values_buttons_middle",
        "verticalSpacer_filtering_values_buttons_bottom1",
        "verticalSpacer_filtering_values_buttons_bottom2",
        "horizontalSpacer_filtering_values_right",
    ],

    "exporting_keys": [
        "verticalSpacer_exporting_keys_field_top",
        "verticalSpacer_exporting_keys_field_middle1",
        "verticalSpacer_exporting_keys_field_middle2",
        "verticalSpacer_exporting_keys_field_middle3",
        "verticalSpacer_exporting_keys_field_bottom",
    ],

    "exporting_values": [
        "verticalSpacer_exporting_values_top",
        "verticalSpacer_exporting_values_crs_top",
        "verticalSpacer_exporting_values_crs_middle",
        "verticalSpacer_exporting_values_format_top",
        "verticalSpacer_exporting_values_format_middle",
        "verticalSpacer_exporting_values_destination_top",
        "verticalSpacer_exporting_values_destination_bottom",
        "horizontalSpacer_exporting_values_right",
    ],

    "config": [
        "verticalSpacer_config_bottom",
    ],
}

# Flat list of all spacers
ALL_SPACERS: List[str] = [spacer for section in SPACERS.values() for spacer in section]


# =============================================================================
# LAYOUTS REFERENCE
# =============================================================================

# Organized by section for easy programmatic access
LAYOUTS: Dict[str, List[str]] = {
    "main": [
        "verticalLayout_main_root",
        "verticalLayout_main_content",
        "gridLayout_main_header",
        "gridLayout_main_actions",
    ],

    "exploring": [
        "verticalLayout_exploring_container",
        "verticalLayout_exploring_content",
        "verticalLayout_exploring_tabs_content",
        "gridLayout_exploring_single_content",
        "verticalLayout_exploring_single_selection",
        "gridLayout_exploring_multiple_content",
        "verticalLayout_exploring_multiple_selection",
        "verticalLayout_exploring_custom_container",
        "verticalLayout_exploring_custom_selection",
    ],

    "filtering": [
        "verticalLayout_filtering_section",
        "verticalLayout_filtering_container",
        "horizontalLayout_filtering_main",
        "horizontalLayout_filtering_content",
        "verticalLayout_filtering_keys_container",
        "verticalLayout_filtering_keys",
        "verticalLayout_filtering_values",
        "horizontalLayout_filtering_values_search",
        "horizontalLayout_filtering_values_buttons",
    ],

    "exporting": [
        "verticalLayout_exporting_section",
        "horizontalLayout_exporting_main",
        "verticalLayout_exporting_keys_container",
        "verticalLayout_exporting_keys",
        "verticalLayout_exporting_values",
    ],

    "config": [
        "verticalLayout_config_section",
        "verticalLayout_configurationPanel",
    ],

    "actions": [
        "horizontalLayout_actions_container",
        "horizontalLayout_actions_bottom",
    ],
}

# Flat list of all layouts
ALL_LAYOUTS: List[str] = [layout for section in LAYOUTS.values() for layout in section]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_spacers_by_section(section: str) -> List[str]:
    """
    Get all spacers for a specific section.

    Args:
        section: Section name (e.g., 'exploring', 'filtering_keys')

    Returns:
        List of spacer names
    """
    return SPACERS.get(section, [])


def get_layouts_by_section(section: str) -> List[str]:
    """
    Get all layouts for a specific section.

    Args:
        section: Section name (e.g., 'exploring', 'filtering')

    Returns:
        List of layout names
    """
    return LAYOUTS.get(section, [])


def get_spacer_size(spacer_name: str, compact_mode: bool = True) -> int:
    """
    Get recommended size for a spacer based on mode and name.

    Args:
        spacer_name: Name of the spacer
        compact_mode: True for compact mode, False for normal mode

    Returns:
        Recommended size in pixels
    """
    # Default sizes based on mode - REDUCED for better alignment
    # Keys and values columns need matching spacer sizes
    base_size = 4 if compact_mode else 6

    # Section-specific adjustments - minimal to maintain alignment
    if "main" in spacer_name:
        return base_size + 2
    elif "config" in spacer_name:
        return base_size + 2
    elif "exploring" in spacer_name:
        return base_size
    elif "filtering" in spacer_name:
        return base_size  # Must match between keys and values
    elif "exporting" in spacer_name:
        return base_size  # Must match between keys and values

    return base_size


def get_layout_spacing(layout_name: str, compact_mode: bool = True) -> int:
    """
    Get recommended spacing for a layout based on mode and name.

    Args:
        layout_name: Name of the layout
        compact_mode: True for compact mode, False for normal mode

    Returns:
        Recommended spacing in pixels
    """
    # Default spacing based on mode
    base_spacing = 6 if compact_mode else 12

    # Layout-specific adjustments
    if "main" in layout_name:
        return base_spacing + 2
    elif "keys" in layout_name:
        return 2 if compact_mode else 4  # Tight spacing for key buttons
    elif "buttons" in layout_name:
        return base_spacing + 2
    elif "content" in layout_name:
        return base_spacing

    return base_spacing


def get_section_names() -> List[str]:
    """
    Get list of all section names.

    Returns:
        List of section name strings
    """
    spacer_sections = set(SPACERS.keys())
    layout_sections = set(LAYOUTS.keys())
    return sorted(spacer_sections.union(layout_sections))


def find_element_section(element_name: str) -> Optional[str]:
    """
    Find which section an element belongs to.

    Args:
        element_name: Name of spacer or layout

    Returns:
        Section name or None if not found
    """
    for section, spacers in SPACERS.items():
        if element_name in spacers:
            return section

    for section, layouts in LAYOUTS.items():
        if element_name in layouts:
            return section

    return None


__all__ = [
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
