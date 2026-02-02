"""
Force show all dynamic widgets after dockwidget is visible.

Run in QGIS Python console:
    exec(open('C:/Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/force_show_widgets.py').read())
"""

from qgis.utils import iface
from qgis.PyQt.QtWidgets import QDockWidget, QApplication

print("=" * 70)
print("FORCE SHOW ALL DYNAMIC WIDGETS")
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
    # Ensure dockwidget is visible
    if not d.isVisible():
        d.show()
        QApplication.processEvents()
    
    print(f"Dockwidget visible: {d.isVisible()}")
    print()
    
    # Force show each widget
    widgets_to_show = [
        ('checkableComboBoxLayer_filtering_layers_to_filter', 'FILTERING layers'),
        ('checkBox_filtering_use_centroids_distant_layers', 'FILTERING centroids'),
        ('checkableComboBoxLayer_exporting_layers', 'EXPORTING layers'),
        ('checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection', 'EXPLORING multiple'),
    ]
    
    for attr_name, desc in widgets_to_show:
        if hasattr(d, attr_name):
            w = getattr(d, attr_name)
            if w is not None:
                print(f"{desc}:")
                print(f"  Before: isVisible={w.isVisible()}, isHidden={w.isHidden()}, isEnabled={w.isEnabled()}")
                
                # Force enable
                w.setEnabled(True)
                
                # Force show - multiple methods
                w.setVisible(True)
                w.show()
                w.setAttribute(1, False)  # WA_WState_Hidden = 1
                
                # Force geometry update
                w.updateGeometry()
                w.update()
                w.repaint()
                
                # Update parent
                if w.parent():
                    w.parent().updateGeometry()
                    w.parent().update()
                
                QApplication.processEvents()
                
                print(f"  After: isVisible={w.isVisible()}, isHidden={w.isHidden()}, isEnabled={w.isEnabled()}")
                print(f"  Size: {w.size().width()}x{w.size().height()}")
                print(f"  Parent: {type(w.parent()).__name__} ({w.parent().objectName()})")
                print()
        else:
            print(f"{desc}: NOT FOUND")
            print()
    
    # Force update on FILTERING tab
    if hasattr(d, 'FILTERING'):
        d.FILTERING.updateGeometry()
        d.FILTERING.update()
        d.FILTERING.repaint()
    
    # Switch to FILTERING tab to ensure it's refreshed
    if hasattr(d, 'toolBox_tabTools'):
        tb = d.toolBox_tabTools
        for i in range(tb.count()):
            if tb.widget(i) == d.FILTERING:
                tb.setCurrentIndex(i)
                break
    
    QApplication.processEvents()
    
    print("=" * 70)
    print("Vérifiez maintenant l'onglet FILTERING visuellement.")
    print("Le widget checkableComboBoxLayer_filtering_layers_to_filter")
    print("devrait apparaître sous 'Couche source'.")
    print("=" * 70)
