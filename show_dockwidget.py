"""
Show the FilterMate dockwidget and verify widgets.

Run in QGIS Python console:
    exec(open('C:/Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/show_dockwidget.py').read())
"""

from qgis.utils import iface
from qgis.PyQt.QtWidgets import QDockWidget, QApplication

print("=" * 70)
print("SHOWING FILTERMATE DOCKWIDGET")
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
    print(f"Before show:")
    print(f"  d.isVisible(): {d.isVisible()}")
    print(f"  d.isHidden(): {d.isHidden()}")
    
    # Show the dockwidget
    d.show()
    d.setVisible(True)
    d.raise_()
    
    QApplication.processEvents()
    
    print(f"After show:")
    print(f"  d.isVisible(): {d.isVisible()}")
    print(f"  d.isHidden(): {d.isHidden()}")
    
    # Now check the filtering widget
    print()
    print("Checking dynamic widgets after dockwidget show:")
    
    if hasattr(d, 'checkableComboBoxLayer_filtering_layers_to_filter'):
        w = d.checkableComboBoxLayer_filtering_layers_to_filter
        print(f"  FILTERING widget: isVisible={w.isVisible()}, size={w.size().width()}x{w.size().height()}")
    
    if hasattr(d, 'checkableComboBoxLayer_exporting_layers'):
        w = d.checkableComboBoxLayer_exporting_layers
        print(f"  EXPORTING widget: isVisible={w.isVisible()}, size={w.size().width()}x{w.size().height()}")
    
    if hasattr(d, 'checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection'):
        w = d.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection
        print(f"  EXPLORING widget: isVisible={w.isVisible()}, size={w.size().width()}x{w.size().height()}")

print()
print("=" * 70)
print("Le dockwidget FilterMate devrait maintenant être visible.")
print("Vérifiez l'onglet FILTERING - le widget layers_to_filter est-il affiché?")
print("=" * 70)
