# -*- coding: utf-8 -*-
"""
UI Elements Reference for FilterMate

Centralized reference for all named UI elements (spacers and layouts) 
after harmonization. Useful for programmatic access and dynamic configuration.
"""

# =============================================================================
# SPACERS REFERENCE
# =============================================================================

# Organized by section for easy programmatic access
SPACERS = {
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
        "verticalSpacer_filtering_values_search_bottom",
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
    
    "actions": [
        "horizontalSpacer_actions_filter_undo",
        "horizontalSpacer_actions_undo_redo",
        "horizontalSpacer_actions_redo_reset",
        "horizontalSpacer_actions_reset_export",
        "horizontalSpacer_actions_export_about",
    ],
}

# Flat list of all spacers
ALL_SPACERS = [spacer for section in SPACERS.values() for spacer in section]


# =============================================================================
# LAYOUTS REFERENCE
# =============================================================================

# Organized by section for easy programmatic access
LAYOUTS = {
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
        "verticalLayout_exploring_single_selection",  # Already had good name
        "gridLayout_exploring_multiple_content",
        "verticalLayout_exploring_multiple_selection",  # Already had good name
        "verticalLayout_exploring_custom_container",
        "verticalLayout_exploring_custom_selection",  # Already had good name
    ],
    
    "filtering": [
        "verticalLayout_filtering_section",
        "verticalLayout_filtering_container",
        "horizontalLayout_filtering_main",
        "horizontalLayout_filtering_content",
        "verticalLayout_filtering_keys_container",
        "verticalLayout_filtering_keys",  # Already had good name
        "verticalLayout_filtering_values",  # Already had good name
        "horizontalLayout_filtering_values_search",
        "horizontalLayout_filtering_values_buttons",
    ],
    
    "exporting": [
        "verticalLayout_exporting_section",
        "horizontalLayout_exporting_main",
        "verticalLayout_exporting_keys_container",
        "verticalLayout_exporting_keys",  # Already had good name
        "verticalLayout_exporting_values",  # Already had good name
    ],
    
    "config": [
        "verticalLayout_config_section",
        "verticalLayout_configurationPanel",  # Kept original good name
    ],
    
    "actions": [
        "horizontalLayout_actions_container",
        "horizontalLayout_actions_bottom",
    ],
}

# Flat list of all layouts
ALL_LAYOUTS = [layout for section in LAYOUTS.values() for layout in section]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_spacers_by_section(section: str) -> list:
    """
    Get all spacers for a specific section.
    
    Args:
        section: Section name (e.g., 'exploring', 'filtering_keys')
    
    Returns:
        List of spacer names
    """
    return SPACERS.get(section, [])


def get_layouts_by_section(section: str) -> list:
    """
    Get all layouts for a specific section.
    
    Args:
        section: Section name (e.g., 'main', 'filtering')
    
    Returns:
        List of layout names
    """
    return LAYOUTS.get(section, [])


def get_all_vertical_spacers() -> list:
    """Get all vertical spacer names."""
    return [s for s in ALL_SPACERS if s.startswith('verticalSpacer_')]


def get_all_horizontal_spacers() -> list:
    """Get all horizontal spacer names."""
    return [s for s in ALL_SPACERS if s.startswith('horizontalSpacer_')]


def get_all_vertical_layouts() -> list:
    """Get all vertical layout names."""
    return [l for l in ALL_LAYOUTS if l.startswith('verticalLayout_')]


def get_all_horizontal_layouts() -> list:
    """Get all horizontal layout names."""
    return [l for l in ALL_LAYOUTS if l.startswith('horizontalLayout_')]


def get_all_grid_layouts() -> list:
    """Get all grid layout names."""
    return [l for l in ALL_LAYOUTS if l.startswith('gridLayout_')]


# =============================================================================
# DIMENSION CONFIGURATION HELPERS
# =============================================================================

# Default spacer sizes for compact mode (can be customized per section)
# Optimized for small screens - tighter spacing to maximize content area
COMPACT_SPACER_SIZES = {
    "main": 6,              # Main container spacers
    "exploring": 5,         # Exploring section spacers
    "filtering_keys": 4,    # Between key fields (tight)
    "filtering_values": 5,  # Between value controls
    "exporting_keys": 4,    # Between key fields (tight)
    "exporting_values": 5,  # Between value controls
    "config": 8,            # Config section (more breathing room)
    "actions": 0,           # Action buttons (no spacing for compact layout)
}

# Default spacer sizes for normal mode
# Optimized for larger screens - comfortable spacing
NORMAL_SPACER_SIZES = {
    "main": 10,             # Main container spacers
    "exploring": 1,         # Exploring section spacers - minimal pour maximiser l'espace
    "filtering_keys": 6,    # Between key fields
    "filtering_values": 8,  # Between value controls
    "exporting_keys": 6,    # Between key fields
    "exporting_values": 8,  # Between value controls
    "config": 12,           # Config section (more space)
    "actions": 2,           # Action buttons (minimal spacing)
}


def get_spacer_size(spacer_name: str, compact_mode: bool = True) -> int:
    """
    Get recommended spacer size based on section and mode.
    
    Args:
        spacer_name: Name of the spacer
        compact_mode: True for compact mode, False for normal mode
    
    Returns:
        Recommended size in pixels
    """
    # Determine section from spacer name
    for section, spacers in SPACERS.items():
        if spacer_name in spacers:
            sizes = COMPACT_SPACER_SIZES if compact_mode else NORMAL_SPACER_SIZES
            return sizes.get(section, 10 if compact_mode else 15)
    
    # Default fallback
    return 10 if compact_mode else 15


# =============================================================================
# USAGE EXAMPLES
# =============================================================================

if __name__ == "__main__":
    # Example: Get all exploring spacers
    print("Exploring spacers:")
    for spacer in get_spacers_by_section("exploring"):
        size = get_spacer_size(spacer, compact_mode=True)
        print(f"  - {spacer}: {size}px (compact)")
    
    # Example: Get all filtering layouts
    print("\nFiltering layouts:")
    for layout in get_layouts_by_section("filtering"):
        print(f"  - {layout}")
    
    # Example: Get all vertical spacers
    print(f"\nTotal vertical spacers: {len(get_all_vertical_spacers())}")
    print(f"Total horizontal spacers: {len(get_all_horizontal_spacers())}")
    print(f"Total layouts: {len(ALL_LAYOUTS)}")
