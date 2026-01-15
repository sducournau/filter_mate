"""
FilterMate Diagnostic Script - Distant Layers Geometric Filter Issue

Run this script in the QGIS Python Console after:
1. Open FilterMate
2. Select the source layer (Distribution Cluster)
3. Select a polygon feature
4. Do NOT click Filter yet

This will diagnose why distant layers are not being filtered geometrically.

Usage:
    exec(open(r'C:\Users\Simon\AppData\Roaming\QGIS\QGIS3\profiles\imagodata\python\plugins\filter_mate\DIAGNOSTIC_DISTANT_FILTER.py').read())
"""

def run_diagnostic():
    from qgis.core import QgsProject, QgsMessageLog, Qgis
    
    print("=" * 70)
    print("FilterMate Distant Filter Diagnostic v1.0")
    print("=" * 70)
    
    # Find FilterMate dockwidget
    dockwidget = None
    for plugin_name, plugin_obj in qgis.utils.plugins.items():
        if 'filter_mate' in plugin_name.lower():
            if hasattr(plugin_obj, 'dockwidget'):
                dockwidget = plugin_obj.dockwidget
                break
    
    if dockwidget is None:
        print("❌ ERROR: FilterMate dockwidget not found!")
        print("   Make sure FilterMate plugin is loaded.")
        return
    
    print(f"✓ FilterMate dockwidget found")
    
    # Check current layer
    current_layer = getattr(dockwidget, 'current_layer', None)
    if current_layer is None:
        print("❌ ERROR: No current layer selected in FilterMate!")
        return
    
    print(f"✓ Current layer: {current_layer.name()} (id: {current_layer.id()[:16]}...)")
    print(f"  Provider: {current_layer.providerType()}")
    print(f"  Feature count: {current_layer.featureCount()}")
    print(f"  Selected features: {current_layer.selectedFeatureCount()}")
    print(f"  Subset string: '{current_layer.subsetString()[:100]}...' " if current_layer.subsetString() else "  Subset string: (none)")
    
    # Check PROJECT_LAYERS
    PROJECT_LAYERS = getattr(dockwidget, 'PROJECT_LAYERS', {})
    if not PROJECT_LAYERS:
        print("❌ ERROR: PROJECT_LAYERS is empty!")
        return
    
    print(f"\n✓ PROJECT_LAYERS contains {len(PROJECT_LAYERS)} layers")
    
    # Check if current layer is in PROJECT_LAYERS
    if current_layer.id() not in PROJECT_LAYERS:
        print(f"❌ ERROR: Current layer not in PROJECT_LAYERS!")
        return
    
    layer_props = PROJECT_LAYERS[current_layer.id()]
    print(f"✓ Current layer found in PROJECT_LAYERS")
    
    # Check filtering configuration
    filtering = layer_props.get("filtering", {})
    print(f"\n--- FILTERING CONFIGURATION ---")
    
    # 1. Check has_geometric_predicates
    has_geom_pred = filtering.get("has_geometric_predicates", False)
    geom_preds = filtering.get("geometric_predicates", [])
    print(f"\n1. GEOMETRIC PREDICATES:")
    print(f"   has_geometric_predicates: {has_geom_pred}")
    print(f"   geometric_predicates: {geom_preds}")
    if not has_geom_pred:
        print("   ⚠️ PROBLEM: Geometric predicates are DISABLED!")
        print("   → Enable the geometric predicates button (Intersects, Contains, etc.)")
    elif len(geom_preds) == 0:
        print("   ⚠️ PROBLEM: No predicates selected!")
        print("   → Select at least one predicate (e.g., 'Intersects')")
    else:
        print(f"   ✓ OK: {len(geom_preds)} predicate(s) configured")
    
    # 2. Check has_layers_to_filter
    has_layers_flag = filtering.get("has_layers_to_filter", False)
    layers_to_filter = filtering.get("layers_to_filter", [])
    print(f"\n2. LAYERS TO FILTER:")
    print(f"   has_layers_to_filter: {has_layers_flag}")
    print(f"   layers_to_filter: {len(layers_to_filter)} layer(s)")
    if not has_layers_flag:
        print("   ⚠️ PROBLEM: 'Layers to filter' checkbox is NOT checked!")
        print("   → Check the 'Layers to filter' checkbox button")
    elif len(layers_to_filter) == 0:
        print("   ⚠️ PROBLEM: No layers selected for filtering!")
        print("   → Select layers in the 'Layers to filter' combobox")
    else:
        print(f"   ✓ OK: {len(layers_to_filter)} layer(s) selected")
        for lid in layers_to_filter[:5]:
            layer = QgsProject.instance().mapLayer(lid)
            name = layer.name() if layer else "NOT FOUND"
            print(f"      - {name} ({lid[:16]}...)")
        if len(layers_to_filter) > 5:
            print(f"      ... and {len(layers_to_filter) - 5} more")
    
    # 3. Check buffer configuration
    has_buffer = filtering.get("has_buffer_value", False)
    buffer_val = filtering.get("buffer_value", 0.0)
    print(f"\n3. BUFFER CONFIGURATION:")
    print(f"   has_buffer_value: {has_buffer}")
    print(f"   buffer_value: {buffer_val}")
    
    # 4. Check forced backends
    forced_backends = getattr(dockwidget, 'forced_backends', {})
    print(f"\n4. FORCED BACKENDS:")
    if forced_backends:
        for lid, backend in forced_backends.items():
            layer = QgsProject.instance().mapLayer(lid)
            name = layer.name() if layer else lid[:16]
            print(f"   - {name}: {backend}")
    else:
        print("   (none - using auto-detection)")
    
    # 5. Check UI widget states
    print(f"\n5. UI WIDGET STATES:")
    
    # Check has_layers_to_filter button
    btn = getattr(dockwidget, 'pushButton_checkable_filtering_layers_to_filter', None)
    if btn:
        print(f"   pushButton_checkable_filtering_layers_to_filter.isChecked(): {btn.isChecked()}")
    else:
        print("   ❌ Button not found!")
    
    # Check geometric predicates button
    btn_geom = getattr(dockwidget, 'pushButton_checkable_filtering_geometric_predicates', None)
    if btn_geom:
        print(f"   pushButton_checkable_filtering_geometric_predicates.isChecked(): {btn_geom.isChecked()}")
    else:
        print("   ❌ Geometric predicates button not found!")
    
    # Check predicates combobox
    cbb_pred = None
    widgets = getattr(dockwidget, 'widgets', {})
    if widgets and 'FILTERING' in widgets and 'GEOMETRIC_PREDICATES' in widgets['FILTERING']:
        cbb_pred = widgets['FILTERING']['GEOMETRIC_PREDICATES'].get('WIDGET')
    if cbb_pred:
        from qgis.PyQt.QtWidgets import QListWidget
        if hasattr(cbb_pred, 'selectedItems'):
            selected = [item.text() for item in cbb_pred.selectedItems()]
            print(f"   Selected predicates in UI: {selected}")
        elif hasattr(cbb_pred, 'checkedItems'):
            checked = cbb_pred.checkedItems()
            print(f"   Checked predicates in UI: {checked}")
    
    # 6. Check source geometry availability
    print(f"\n6. SOURCE GEOMETRY CHECK:")
    if current_layer.selectedFeatureCount() > 0:
        for feat in current_layer.selectedFeatures():
            geom = feat.geometry()
            print(f"   Selected feature ID: {feat.id()}")
            print(f"   Geometry valid: {geom is not None and not geom.isEmpty()}")
            if geom and not geom.isEmpty():
                print(f"   Geometry type: {geom.wkbType()}")
                print(f"   Geometry area: {geom.area():.2f}")
                print(f"   Bounding box: {geom.boundingBox().toString()[:60]}...")
            break  # Only show first
    else:
        # Check if layer has subset that filters to some features
        if current_layer.subsetString():
            print(f"   Layer has subset filter, checking features...")
            count = 0
            for feat in current_layer.getFeatures():
                geom = feat.geometry()
                if geom and not geom.isEmpty():
                    print(f"   First feature ID: {feat.id()}")
                    print(f"   Geometry type: {geom.wkbType()}")
                    print(f"   Geometry area: {geom.area():.2f}")
                    break
                count += 1
                if count > 10:
                    break
        else:
            print("   ⚠️ No selection and no subset string - source geometry may not be available!")
    
    print("\n" + "=" * 70)
    print("DIAGNOSTIC SUMMARY")
    print("=" * 70)
    
    issues = []
    
    if not has_geom_pred:
        issues.append("• Enable geometric predicates (button with spatial icons)")
    if len(geom_preds) == 0:
        issues.append("• Select at least one geometric predicate (e.g., 'Intersects')")
    if not has_layers_flag:
        issues.append("• Check the 'Layers to filter' checkbox")
    if len(layers_to_filter) == 0:
        issues.append("• Select layers to filter in the combobox")
    if current_layer.selectedFeatureCount() == 0 and not current_layer.subsetString():
        issues.append("• Select a feature or apply a filter to the source layer first")
    
    if issues:
        print("\n⚠️ ISSUES FOUND:")
        for issue in issues:
            print(f"   {issue}")
    else:
        print("\n✓ Configuration looks correct!")
        print("   If filtering still doesn't work, check the Python console")
        print("   for error messages during the filter operation.")
    
    print("\n" + "=" * 70)

# Run diagnostic
run_diagnostic()
