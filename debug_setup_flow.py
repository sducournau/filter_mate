"""
Debug script to trace exactly what happens during setup_filtering_tab_widgets.

Run in QGIS Python console:
    exec(open('C:/Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/debug_setup_flow.py').read())
"""

from qgis.utils import iface, plugins
from qgis.PyQt.QtWidgets import QDockWidget, QHBoxLayout, QVBoxLayout

print("=" * 70)
print("DEBUG: Tracing setup_filtering_tab_widgets flow")
print("=" * 70)

# Find dockwidget
d = None
for dock in iface.mainWindow().findChildren(QDockWidget):
    if 'FilterMate' in dock.windowTitle():
        d = dock
        break

if not d:
    print("❌ FilterMate dockwidget NOT FOUND")
else:
    print("✓ Found FilterMate dockwidget")
    print()
    
    # Check FILTERING page
    print("1. FILTERING page check:")
    if hasattr(d, 'FILTERING'):
        print(f"   ✓ FILTERING exists: {d.FILTERING}")
        print(f"   - id: {hex(id(d.FILTERING))}")
    else:
        print("   ❌ FILTERING NOT FOUND")
    
    print()
    
    # Check verticalLayout_filtering_values
    print("2. verticalLayout_filtering_values check:")
    if hasattr(d, 'verticalLayout_filtering_values'):
        vl = d.verticalLayout_filtering_values
        print(f"   ✓ Layout exists: {vl}")
        print(f"   - count: {vl.count()}")
        print(f"   - parentWidget: {vl.parentWidget()}")
        if vl.parentWidget():
            print(f"   - parentWidget id: {hex(id(vl.parentWidget()))}")
        
        print()
        print("   Items in verticalLayout_filtering_values:")
        for i in range(vl.count()):
            item = vl.itemAt(i)
            if item:
                if item.widget():
                    print(f"     [{i}] Widget: {item.widget().objectName() or type(item.widget()).__name__}")
                elif item.layout():
                    print(f"     [{i}] Layout: {item.layout()} (count={item.layout().count()})")
                elif item.spacerItem():
                    print(f"     [{i}] Spacer")
                else:
                    print(f"     [{i}] Unknown item type")
    else:
        print("   ❌ verticalLayout_filtering_values NOT FOUND")
    
    print()
    
    # Check horizontalLayout_filtering_distant_layers
    print("3. horizontalLayout_filtering_distant_layers check:")
    if hasattr(d, 'horizontalLayout_filtering_distant_layers'):
        hl = d.horizontalLayout_filtering_distant_layers
        print(f"   ✓ Layout exists: {hl}")
        print(f"   - count: {hl.count()}")
        print(f"   - parentWidget: {hl.parentWidget()}")
        if hl.parentWidget():
            print(f"   - parentWidget id: {hex(id(hl.parentWidget()))}")
            print(f"   - Is parentWidget == FILTERING? {hl.parentWidget() == d.FILTERING if hasattr(d, 'FILTERING') else 'N/A'}")
    else:
        print("   ❌ horizontalLayout_filtering_distant_layers NOT FOUND")
    
    print()
    
    # Check the widget
    print("4. checkableComboBoxLayer_filtering_layers_to_filter check:")
    if hasattr(d, 'checkableComboBoxLayer_filtering_layers_to_filter'):
        w = d.checkableComboBoxLayer_filtering_layers_to_filter
        print(f"   ✓ Widget exists: {w}")
        print(f"   - parent: {w.parent()}")
        if w.parent():
            print(f"   - parent id: {hex(id(w.parent()))}")
            print(f"   - Is parent == FILTERING? {w.parent() == d.FILTERING if hasattr(d, 'FILTERING') else 'N/A'}")
    else:
        print("   ❌ Widget NOT FOUND")
    
    print()
    print("=" * 70)
    print("MANUAL FIX ATTEMPT")
    print("=" * 70)
    print()
    
    # Try manual fix
    if hasattr(d, 'checkableComboBoxLayer_filtering_layers_to_filter') and \
       hasattr(d, 'checkBox_filtering_use_centroids_distant_layers') and \
       hasattr(d, 'verticalLayout_filtering_values') and \
       hasattr(d, 'FILTERING'):
        
        layers_widget = d.checkableComboBoxLayer_filtering_layers_to_filter
        centroids_widget = d.checkBox_filtering_use_centroids_distant_layers
        vl = d.verticalLayout_filtering_values
        
        print("Step 1: Remove old layout reference if exists")
        if hasattr(d, 'horizontalLayout_filtering_distant_layers'):
            old_hl = d.horizontalLayout_filtering_distant_layers
            # Remove widgets from old layout
            while old_hl.count():
                item = old_hl.takeAt(0)
                print(f"   Removed item from old layout")
            # Try to remove from parent layout
            if hasattr(d, 'verticalLayout_filtering_values'):
                vl_check = d.verticalLayout_filtering_values
                for i in range(vl_check.count()):
                    item = vl_check.itemAt(i)
                    if item and item.layout() == old_hl:
                        vl_check.takeAt(i)
                        print(f"   Removed old layout from vl at position {i}")
                        break
            delattr(d, 'horizontalLayout_filtering_distant_layers')
            print("   Deleted old layout reference")
        else:
            print("   No old layout to remove")
        
        print()
        print("Step 2: Create NEW layout (empty)")
        new_hl = QHBoxLayout()
        new_hl.setSpacing(4)
        new_hl.setContentsMargins(0, 0, 0, 0)
        print(f"   Created: {new_hl}")
        print(f"   parentWidget BEFORE insert: {new_hl.parentWidget()}")
        
        print()
        print("Step 3: Insert EMPTY layout into vl at position 1")
        print(f"   vl.count() BEFORE: {vl.count()}")
        vl.insertLayout(1, new_hl)
        print(f"   vl.count() AFTER: {vl.count()}")
        print(f"   parentWidget AFTER insert: {new_hl.parentWidget()}")
        
        print()
        print("Step 4: Store reference")
        d.horizontalLayout_filtering_distant_layers = new_hl
        
        print()
        print("Step 5: Add widgets to layout")
        new_hl.addWidget(layers_widget, 1)
        new_hl.addWidget(centroids_widget, 0)
        print(f"   Layout count after adding widgets: {new_hl.count()}")
        
        print()
        print("Step 6: Force visibility and update")
        layers_widget.setVisible(True)
        layers_widget.show()
        centroids_widget.setVisible(True)
        centroids_widget.show()
        
        vl.invalidate()
        vl.activate()
        vl.update()
        
        d.FILTERING.updateGeometry()
        d.FILTERING.update()
        
        print()
        print("=" * 70)
        print("VERIFICATION")
        print("=" * 70)
        print(f"   layers_widget.isVisible(): {layers_widget.isVisible()}")
        print(f"   layers_widget.size(): {layers_widget.size().width()}x{layers_widget.size().height()}")
        print(f"   layers_widget.parent(): {layers_widget.parent()}")
        print(f"   new_hl.parentWidget(): {new_hl.parentWidget()}")
        
        # Check if in vl
        in_vl = False
        for i in range(vl.count()):
            item = vl.itemAt(i)
            if item and item.layout() == new_hl:
                in_vl = True
                print(f"   ✅ Layout IS in vl at position {i}")
                break
        if not in_vl:
            print(f"   ❌ Layout NOT in vl!")
            print()
            print("   Current vl contents:")
            for i in range(vl.count()):
                item = vl.itemAt(i)
                if item:
                    if item.widget():
                        print(f"     [{i}] Widget: {item.widget()}")
                    elif item.layout():
                        print(f"     [{i}] Layout: {item.layout()}")
                    else:
                        print(f"     [{i}] Other")
    else:
        print("Missing required attributes for manual fix")

print()
print("=" * 70)
print("DEBUG COMPLETE")
print("=" * 70)
