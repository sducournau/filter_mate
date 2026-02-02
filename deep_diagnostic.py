"""
Deep diagnostic of widget hierarchy and visibility.

Run in QGIS Python console:
    exec(open('C:/Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/deep_diagnostic.py').read())
"""

from qgis.utils import iface
from qgis.PyQt.QtWidgets import QDockWidget, QApplication, QWidget
from qgis.PyQt.QtCore import Qt

print("=" * 70)
print("DEEP DIAGNOSTIC - Widget Hierarchy")
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
    
    # Check the filtering widget
    if hasattr(d, 'checkableComboBoxLayer_filtering_layers_to_filter'):
        w = d.checkableComboBoxLayer_filtering_layers_to_filter
        
        print("FILTERING WIDGET ANALYSIS:")
        print("-" * 50)
        print(f"Widget: {w}")
        print(f"objectName: {w.objectName()}")
        print(f"isVisible: {w.isVisible()}")
        print(f"isHidden: {w.isHidden()}")
        print(f"isEnabled: {w.isEnabled()}")
        print(f"size: {w.size().width()}x{w.size().height()}")
        print(f"minimumSize: {w.minimumSize().width()}x{w.minimumSize().height()}")
        print(f"maximumSize: {w.maximumSize().width()}x{w.maximumSize().height()}")
        print(f"sizeHint: {w.sizeHint().width()}x{w.sizeHint().height()}")
        print(f"geometry: {w.geometry()}")
        print(f"pos: {w.pos()}")
        print(f"windowFlags: {w.windowFlags()}")
        
        # Check visibility attribute
        print(f"testAttribute(WA_WState_Hidden): {w.testAttribute(Qt.WA_WState_Hidden)}")
        print(f"testAttribute(WA_WState_Visible): {w.testAttribute(Qt.WA_WState_Visible)}")
        
        print()
        print("PARENT CHAIN:")
        print("-" * 50)
        
        parent = w.parent()
        level = 0
        while parent:
            indent = "  " * level
            print(f"{indent}[{level}] {type(parent).__name__}")
            print(f"{indent}    objectName: {parent.objectName()}")
            print(f"{indent}    isVisible: {parent.isVisible()}")
            print(f"{indent}    isHidden: {parent.isHidden()}")
            print(f"{indent}    size: {parent.size().width()}x{parent.size().height()}")
            print(f"{indent}    geometry: {parent.geometry()}")
            
            # Check if this is the FILTERING widget
            if hasattr(d, 'FILTERING') and parent == d.FILTERING:
                print(f"{indent}    *** THIS IS FILTERING ***")
            
            parent = parent.parent()
            level += 1
            if level > 15:  # Safety limit
                print("  ... (truncated)")
                break
        
        print()
        print("LAYOUT CHECK:")
        print("-" * 50)
        
        # Find which layout contains this widget
        if hasattr(d, 'horizontalLayout_filtering_distant_layers'):
            hl = d.horizontalLayout_filtering_distant_layers
            print(f"horizontalLayout_filtering_distant_layers:")
            print(f"  count: {hl.count()}")
            print(f"  parentWidget: {hl.parentWidget()}")
            print(f"  geometry: {hl.geometry()}")
            print(f"  contentsRect: {hl.contentsRect()}")
            
            # Check each item
            for i in range(hl.count()):
                item = hl.itemAt(i)
                if item:
                    if item.widget():
                        iw = item.widget()
                        print(f"  [{i}] Widget: {iw.objectName()} - visible={iw.isVisible()}, size={iw.size().width()}x{iw.size().height()}")
                    elif item.layout():
                        print(f"  [{i}] Layout: {item.layout()}")
                    elif item.spacerItem():
                        print(f"  [{i}] Spacer")
        
        if hasattr(d, 'verticalLayout_filtering_values'):
            vl = d.verticalLayout_filtering_values
            print()
            print(f"verticalLayout_filtering_values:")
            print(f"  count: {vl.count()}")
            print(f"  parentWidget: {vl.parentWidget()}")
            print(f"  geometry: {vl.geometry()}")
            
            # Find our horizontal layout
            for i in range(vl.count()):
                item = vl.itemAt(i)
                if item and item.layout():
                    if hasattr(d, 'horizontalLayout_filtering_distant_layers') and item.layout() == d.horizontalLayout_filtering_distant_layers:
                        print(f"  [{i}] *** OUR LAYOUT *** geometry={item.geometry()}")
                    else:
                        print(f"  [{i}] Layout: geometry={item.geometry()}")
                elif item and item.widget():
                    print(f"  [{i}] Widget: {item.widget().objectName()}")
                elif item and item.spacerItem():
                    print(f"  [{i}] Spacer")
        
        print()
        print("TOOLBOX CHECK:")
        print("-" * 50)
        
        if hasattr(d, 'toolBox_tabTools'):
            tb = d.toolBox_tabTools
            print(f"toolBox_tabTools:")
            print(f"  count: {tb.count()}")
            print(f"  currentIndex: {tb.currentIndex()}")
            
            for i in range(tb.count()):
                item_widget = tb.widget(i)
                item_text = tb.itemText(i)
                is_current = (i == tb.currentIndex())
                print(f"  [{i}] '{item_text}' - widget={item_widget.objectName() if item_widget else 'None'}, current={is_current}")
                
                if hasattr(d, 'FILTERING') and item_widget == d.FILTERING:
                    print(f"      *** THIS IS FILTERING TAB ***")
                    print(f"      FILTERING.isVisible: {d.FILTERING.isVisible()}")
                    print(f"      FILTERING.size: {d.FILTERING.size().width()}x{d.FILTERING.size().height()}")
    else:
        print("❌ checkableComboBoxLayer_filtering_layers_to_filter NOT FOUND")
    
    print()
    print("=" * 70)
    print("ATTEMPTING FIX:")
    print("=" * 70)
    
    # Try switching to FILTERING tab and back
    if hasattr(d, 'toolBox_tabTools') and hasattr(d, 'FILTERING'):
        tb = d.toolBox_tabTools
        
        # Find FILTERING index
        filtering_idx = -1
        for i in range(tb.count()):
            if tb.widget(i) == d.FILTERING:
                filtering_idx = i
                break
        
        if filtering_idx >= 0:
            print(f"Switching to FILTERING tab (index {filtering_idx})...")
            tb.setCurrentIndex(filtering_idx)
            QApplication.processEvents()
            
            if hasattr(d, 'checkableComboBoxLayer_filtering_layers_to_filter'):
                w = d.checkableComboBoxLayer_filtering_layers_to_filter
                print(f"After tab switch: isVisible={w.isVisible()}, size={w.size().width()}x{w.size().height()}")
                
                # Force show
                w.show()
                w.setVisible(True)
                w.updateGeometry()
                w.repaint()
                
                # Update parent
                if w.parent():
                    w.parent().updateGeometry()
                    w.parent().repaint()
                
                d.FILTERING.updateGeometry()
                d.FILTERING.repaint()
                
                QApplication.processEvents()
                
                print(f"After force show: isVisible={w.isVisible()}, size={w.size().width()}x{w.size().height()}")
    
    print()
    print("=" * 70)
