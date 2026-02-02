"""
Script to force visibility of all dynamic widgets.

Run in QGIS Python console:
    exec(open('C:/Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/force_visibility.py').read())
"""

from qgis.utils import iface
from qgis.PyQt.QtWidgets import QDockWidget, QApplication

print("=" * 70)
print("FORCING VISIBILITY OF DYNAMIC WIDGETS")
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
    
    # 1. FILTERING widget
    print("1. FILTERING - checkableComboBoxLayer_filtering_layers_to_filter")
    if hasattr(d, 'checkableComboBoxLayer_filtering_layers_to_filter'):
        w = d.checkableComboBoxLayer_filtering_layers_to_filter
        print(f"   Before: isVisible={w.isVisible()}, size={w.size().width()}x{w.size().height()}")
        
        # Force visibility
        w.setVisible(True)
        w.show()
        w.raise_()
        w.updateGeometry()
        
        # Update parent chain
        parent = w.parent()
        while parent:
            parent.updateGeometry()
            if hasattr(parent, 'update'):
                parent.update()
            parent = parent.parent() if hasattr(parent, 'parent') else None
        
        # Process events
        QApplication.processEvents()
        
        print(f"   After: isVisible={w.isVisible()}, size={w.size().width()}x{w.size().height()}")
        
        # Check if parent is visible
        if w.parent():
            print(f"   Parent visible: {w.parent().isVisible()}")
            if w.parent().parent():
                print(f"   Grandparent visible: {w.parent().parent().isVisible()}")
    else:
        print("   ❌ Widget NOT FOUND")
    
    print()
    
    # 2. EXPORTING widget
    print("2. EXPORTING - checkableComboBoxLayer_exporting_layers")
    if hasattr(d, 'checkableComboBoxLayer_exporting_layers'):
        w = d.checkableComboBoxLayer_exporting_layers
        print(f"   Before: isVisible={w.isVisible()}, size={w.size().width()}x{w.size().height()}")
        
        w.setVisible(True)
        w.show()
        w.raise_()
        w.updateGeometry()
        
        QApplication.processEvents()
        
        print(f"   After: isVisible={w.isVisible()}, size={w.size().width()}x{w.size().height()}")
    else:
        print("   ❌ Widget NOT FOUND")
    
    print()
    
    # 3. EXPLORING widget
    print("3. EXPLORING - checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection")
    if hasattr(d, 'checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection'):
        w = d.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection
        print(f"   Before: isVisible={w.isVisible()}, size={w.size().width()}x{w.size().height()}")
        
        w.setVisible(True)
        w.show()
        w.raise_()
        w.updateGeometry()
        
        QApplication.processEvents()
        
        print(f"   After: isVisible={w.isVisible()}, size={w.size().width()}x{w.size().height()}")
    else:
        print("   ❌ Widget NOT FOUND")
    
    print()
    
    # Force update on main dockwidget
    d.updateGeometry()
    d.update()
    QApplication.processEvents()
    
    print("=" * 70)
    print("Check the FILTERING tab - is the layers combobox visible?")
    print("=" * 70)
