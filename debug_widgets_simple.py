"""
Script de diagnostic simplifié - exécuter dans la console QGIS:
exec(open('C:/Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/debug_widgets_simple.py').read())
"""
from qgis.utils import plugins

if 'filter_mate' not in plugins:
    print("❌ Plugin filter_mate not loaded!")
else:
    dw = plugins['filter_mate'].dockwidget
    print(f"Dockwidget: {dw}")
    print()
    
    # Check widget 1: filtering layers_to_filter
    print("=== 1. checkableComboBoxLayer_filtering_layers_to_filter ===")
    if hasattr(dw, 'checkableComboBoxLayer_filtering_layers_to_filter'):
        w = dw.checkableComboBoxLayer_filtering_layers_to_filter
        print(f"  EXISTS: {w}")
        print(f"  Type: {type(w).__name__}")
        print(f"  Parent: {w.parent()} ({type(w.parent()).__name__ if w.parent() else 'None'})")
        print(f"  Visible: {w.isVisible()}")
        print(f"  Size: {w.size().width()}x{w.size().height()}")
        print(f"  MinSize: {w.minimumWidth()}x{w.minimumHeight()}")
        print(f"  Geometry: {w.geometry()}")
    else:
        print("  ❌ DOES NOT EXIST as attribute!")
    print()
    
    # Check widget 2: exporting layers
    print("=== 2. checkableComboBoxLayer_exporting_layers ===")
    if hasattr(dw, 'checkableComboBoxLayer_exporting_layers'):
        w = dw.checkableComboBoxLayer_exporting_layers
        print(f"  EXISTS: {w}")
        print(f"  Type: {type(w).__name__}")
        print(f"  Parent: {w.parent()} ({type(w.parent()).__name__ if w.parent() else 'None'})")
        print(f"  Visible: {w.isVisible()}")
        print(f"  Size: {w.size().width()}x{w.size().height()}")
        print(f"  MinSize: {w.minimumWidth()}x{w.minimumHeight()}")
    else:
        print("  ❌ DOES NOT EXIST as attribute!")
    print()
    
    # Check widget 3: multiple selection
    print("=== 3. checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection ===")
    if hasattr(dw, 'checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection'):
        w = dw.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection
        print(f"  EXISTS: {w}")
        print(f"  Type: {type(w).__name__}")
        print(f"  Parent: {w.parent()} ({type(w.parent()).__name__ if w.parent() else 'None'})")
        print(f"  Visible: {w.isVisible()}")
        print(f"  Size: {w.size().width()}x{w.size().height()}")
        print(f"  MinSize: {w.minimumWidth()}x{w.minimumHeight()}")
    else:
        print("  ❌ DOES NOT EXIST as attribute!")
    print()
    
    # Check layouts
    print("=== LAYOUTS ===")
    
    if hasattr(dw, 'horizontalLayout_filtering_distant_layers'):
        l = dw.horizontalLayout_filtering_distant_layers
        print(f"horizontalLayout_filtering_distant_layers: count={l.count()}")
        for i in range(l.count()):
            item = l.itemAt(i)
            if item.widget():
                print(f"  [{i}] Widget: {type(item.widget()).__name__} visible={item.widget().isVisible()}")
            elif item.layout():
                print(f"  [{i}] Layout: {type(item.layout()).__name__}")
            elif item.spacerItem():
                print(f"  [{i}] Spacer")
    else:
        print("horizontalLayout_filtering_distant_layers: ❌ NOT FOUND")
    
    if hasattr(dw, 'verticalLayout_filtering_values'):
        l = dw.verticalLayout_filtering_values
        print(f"verticalLayout_filtering_values: count={l.count()}")
        for i in range(min(l.count(), 8)):
            item = l.itemAt(i)
            if item.widget():
                print(f"  [{i}] Widget: {type(item.widget()).__name__}")
            elif item.layout():
                print(f"  [{i}] Layout: {type(item.layout()).__name__} count={item.layout().count()}")
            elif item.spacerItem():
                print(f"  [{i}] Spacer")
    else:
        print("verticalLayout_filtering_values: ❌ NOT FOUND")
    
    print()
    print("=== TRY FORCE SHOW ===")
    # Try to force show the widgets
    if hasattr(dw, 'checkableComboBoxLayer_filtering_layers_to_filter'):
        w = dw.checkableComboBoxLayer_filtering_layers_to_filter
        w.setMinimumSize(100, 26)
        w.setVisible(True)
        w.show()
        w.raise_()
        print(f"filtering_layers_to_filter: forced show, now size={w.size().width()}x{w.size().height()}")
    
    if hasattr(dw, 'checkableComboBoxLayer_exporting_layers'):
        w = dw.checkableComboBoxLayer_exporting_layers
        w.setMinimumSize(100, 26)
        w.setVisible(True)
        w.show()
        w.raise_()
        print(f"exporting_layers: forced show, now size={w.size().width()}x{w.size().height()}")
