"""
Debug script for FilterMate - v8 Force insert
Run in QGIS Python Console:
exec(open('C:/Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/debug_filtering_widgets.py').read())
"""
print("\n" + "="*70)
print("FILTERMATE - FORCE INSERT")
print("="*70)

from qgis.utils import plugins
from qgis.PyQt import QtWidgets

fm = plugins.get('filter_mate')
d = fm.app.dockwidget

# Get widgets
layers_widget = d.checkableComboBoxLayer_filtering_layers_to_filter
centroids_widget = d.checkBox_filtering_use_centroids_distant_layers
vl = d.verticalLayout_filtering_values

print(f"layers_widget: {layers_widget}")
print(f"layers_widget.isVisible(): {layers_widget.isVisible()}")

# Check if h_layout exists
if hasattr(d, 'horizontalLayout_filtering_distant_layers'):
    old_h = d.horizontalLayout_filtering_distant_layers
    print(f"\nOld h_layout exists: {old_h}")
    print(f"  count: {old_h.count()}")
    print(f"  parentWidget: {old_h.parentWidget()}")
    
    # Check if it's in vl
    in_vl = False
    for i in range(vl.count()):
        item = vl.itemAt(i)
        if item and item.layout() == old_h:
            in_vl = True
            print(f"  IN verticalLayout_filtering_values at position {i}")
            break
    if not in_vl:
        print("  NOT IN verticalLayout_filtering_values!")
        
        # The layout has a parentWidget but is NOT in vl
        # This is the problem - we need to abandon this layout and create a new one

print("\n--- FORCE FIX ---")

# STEP 1: Create a completely NEW layout
print("Creating NEW h_layout...")
new_h_layout = QtWidgets.QHBoxLayout()
new_h_layout.setSpacing(4)
new_h_layout.setContentsMargins(0, 0, 0, 0)

# STEP 2: Add widgets to new layout
print("Adding widgets to new layout...")
new_h_layout.addWidget(layers_widget, 1)
new_h_layout.addWidget(centroids_widget, 0)
print(f"new_h_layout.count(): {new_h_layout.count()}")

# STEP 3: Insert new layout into vl
print(f"vl.count() before: {vl.count()}")
vl.insertLayout(1, new_h_layout)
print(f"vl.count() after: {vl.count()}")

# STEP 4: Store reference
d.horizontalLayout_filtering_distant_layers = new_h_layout

# STEP 5: Force visibility and updates
layers_widget.setVisible(True)
layers_widget.show()
centroids_widget.setVisible(True)
centroids_widget.show()

vl.invalidate()
vl.activate()
vl.update()
d.FILTERING.updateGeometry()
d.FILTERING.update()

# Process events
from qgis.PyQt.QtWidgets import QApplication
QApplication.processEvents()

print("\n--- RESULT ---")
print(f"layers_widget.isVisible(): {layers_widget.isVisible()}")
print(f"layers_widget.size(): {layers_widget.size().width()}x{layers_widget.size().height()}")

# Verify insertion
print("\nVerifying vl content:")
for i in range(min(vl.count(), 6)):
    item = vl.itemAt(i)
    if item and item.layout() is not None:
        sub = item.layout()
        print(f"  [{i}] Layout count={sub.count()}")
        if sub == new_h_layout:
            print(f"       ^^^ THIS IS new_h_layout!")
        for j in range(sub.count()):
            sub_item = sub.itemAt(j)
            if sub_item and sub_item.widget() is not None:
                print(f"       [{j}] {sub_item.widget().objectName()}")
    elif item and item.spacerItem() is not None:
        print(f"  [{i}] Spacer")

print("\n" + "="*70)
print("CHECK THE FILTERING TAB NOW!")
print("="*70)
