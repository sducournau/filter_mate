#!/usr/bin/env python3
"""
Diagnostic script to check if remote layers have filters applied.

Usage in QGIS Python Console:
    from filter_mate.tools.diagnostic import check_remote_layers_filter
    check_remote_layers_filter.diagnose()
"""

from qgis.core import QgsProject
from qgis.utils import iface


def diagnose():
    """
    Check all layers in the project and report their filter status.
    """
    print("\n" + "=" * 80)
    print("DIAGNOSTIC: Remote Layers Filter Status")
    print("=" * 80)
    
    project = QgsProject.instance()
    layers = project.mapLayers().values()
    
    filtered_count = 0
    unfiltered_count = 0
    
    for layer in layers:
        if not hasattr(layer, 'subsetString'):
            continue
            
        subset = layer.subsetString()
        feature_count = layer.featureCount()
        provider = layer.providerType()
        
        print(f"\nLayer: {layer.name()}")
        print(f"  Provider: {provider}")
        print(f"  Feature count: {feature_count:,}")
        
        if subset and subset.strip():
            print(f"  ✓ FILTERED")
            print(f"  Subset: {subset[:100]}{'...' if len(subset) > 100 else ''}")
            filtered_count += 1
        else:
            print(f"  ✗ NO FILTER (unfiltered)")
            unfiltered_count += 1
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total layers: {filtered_count + unfiltered_count}")
    print(f"✓ Filtered: {filtered_count}")
    print(f"✗ Unfiltered: {unfiltered_count}")
    print("=" * 80)
    
    if unfiltered_count > 0:
        print("\n⚠️  WARNING: Some layers have no filter applied!")
        print("This may indicate the remote layers filtering issue.")
    else:
        print("\n✓ All layers have filters applied.")


def check_layer_by_name(layer_name):
    """
    Check specific layer filter status.
    
    Args:
        layer_name: Name of the layer to check
    """
    project = QgsProject.instance()
    layers = [l for l in project.mapLayersByName(layer_name)]
    
    if not layers:
        print(f"❌ Layer '{layer_name}' not found in project")
        return
    
    layer = layers[0]
    
    print(f"\n{'=' * 60}")
    print(f"Layer: {layer.name()}")
    print(f"{'=' * 60}")
    print(f"ID: {layer.id()}")
    print(f"Provider: {layer.providerType()}")
    print(f"Feature count: {layer.featureCount():,}")
    print(f"CRS: {layer.crs().authid()}")
    
    subset = layer.subsetString()
    if subset and subset.strip():
        print(f"\n✓ Filter applied:")
        print(f"  {subset}")
    else:
        print(f"\n✗ NO FILTER")
    
    print(f"{'=' * 60}")


if __name__ == "__main__":
    print("Run this script in QGIS Python Console:")
    print("  from filter_mate.tools.diagnostic import check_remote_layers_filter")
    print("  check_remote_layers_filter.diagnose()")
