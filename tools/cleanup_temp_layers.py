#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FilterMate Temporary Layer Cleanup Utility

This script removes temporary layers created by FilterMate that were not
properly cleaned up. These layers typically have names containing:
- _safe_source
- _safe_target  
- _safe_intersect_
- source_from_task
- source_selection
- source_filtered
- source_field_based
- source_expr_filtered

Usage from QGIS Python Console:
    from filter_mate.tools.cleanup_temp_layers import cleanup_filtermate_temp_layers
    cleanup_filtermate_temp_layers()

Or run the script directly:
    exec(open('/path/to/cleanup_temp_layers.py').read())
"""

import re
from qgis.core import QgsProject


# Patterns to identify FilterMate temporary layers
TEMP_LAYER_PATTERNS = [
    r'_safe_source$',
    r'_safe_target$', 
    r'_safe_intersect_\d+$',
    r'_safe$',
    r'^source_from_task$',
    r'^source_selection$',
    r'^source_filtered$',
    r'^source_field_based$',
    r'^source_expr_filtered$',
    # Also match patterns like "zone_pop_safe_intersect_12345"
    r'_safe_intersect_\d+',
    r'_geos_safe$',
]


def is_filtermate_temp_layer(layer_name: str) -> bool:
    """
    Check if a layer name matches FilterMate temporary layer patterns.
    
    Args:
        layer_name: Name of the layer to check
        
    Returns:
        bool: True if layer appears to be a FilterMate temp layer
    """
    for pattern in TEMP_LAYER_PATTERNS:
        if re.search(pattern, layer_name):
            return True
    return False


def get_filtermate_temp_layers() -> list:
    """
    Get list of FilterMate temporary layers in the current project.
    
    Returns:
        list: List of (layer_id, layer_name) tuples for temp layers
    """
    temp_layers = []
    project = QgsProject.instance()
    
    for layer_id, layer in project.mapLayers().items():
        if is_filtermate_temp_layer(layer.name()):
            temp_layers.append((layer_id, layer.name()))
            
    return temp_layers


def cleanup_filtermate_temp_layers(dry_run: bool = False) -> int:
    """
    Remove FilterMate temporary layers from the current project.
    
    Args:
        dry_run: If True, only report layers without removing them
        
    Returns:
        int: Number of layers removed (or would be removed in dry run)
    """
    temp_layers = get_filtermate_temp_layers()
    
    if not temp_layers:
        print("✓ No FilterMate temporary layers found.")
        return 0
    
    print(f"{'Would remove' if dry_run else 'Removing'} {len(temp_layers)} FilterMate temporary layer(s):")
    
    project = QgsProject.instance()
    removed_count = 0
    
    for layer_id, layer_name in temp_layers:
        print(f"  - {layer_name} (id: {layer_id})")
        if not dry_run:
            try:
                project.removeMapLayer(layer_id)
                removed_count += 1
            except Exception as e:
                print(f"    ⚠️ Failed to remove: {e}")
    
    if dry_run:
        print(f"\nDry run complete. Use cleanup_filtermate_temp_layers(dry_run=False) to remove layers.")
    else:
        print(f"\n✓ Removed {removed_count} temporary layer(s).")
        
    return removed_count if not dry_run else len(temp_layers)


def cleanup_by_memory_provider() -> int:
    """
    Remove all memory layers that are hidden (not in legend).
    
    This is more aggressive - removes ANY hidden memory layer.
    Use with caution!
    
    Returns:
        int: Number of layers removed
    """
    project = QgsProject.instance()
    root = project.layerTreeRoot()
    removed_count = 0
    
    for layer_id, layer in list(project.mapLayers().items()):
        if layer.providerType() == 'memory':
            # Check if layer is in legend
            tree_layer = root.findLayer(layer_id)
            if tree_layer is None:
                # Not in legend - likely a temp layer
                print(f"  Removing hidden memory layer: {layer.name()}")
                try:
                    project.removeMapLayer(layer_id)
                    removed_count += 1
                except Exception as e:
                    print(f"    ⚠️ Failed: {e}")
                    
    print(f"✓ Removed {removed_count} hidden memory layer(s).")
    return removed_count


# If run directly in QGIS Python console
if __name__ == '__main__':
    print("=" * 60)
    print("FilterMate Temporary Layer Cleanup")
    print("=" * 60)
    print("\nScanning for temporary layers...")
    
    # First do a dry run
    cleanup_filtermate_temp_layers(dry_run=True)
    
    print("\nTo actually remove these layers, run:")
    print("  cleanup_filtermate_temp_layers(dry_run=False)")
