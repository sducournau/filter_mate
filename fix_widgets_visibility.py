"""
Script pour forcer la visibilité des widgets dynamiques de FilterMate.

À exécuter dans la console Python de QGIS après avoir diagnostiqué le problème:
    exec(open('C:/Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/fix_widgets_visibility.py').read())
"""

from qgis.utils import plugins

if 'filter_mate' not in plugins:
    print("❌ Plugin filter_mate non trouvé")
else:
    # Récupérer le dockwidget
    from qgis.PyQt.QtWidgets import QDockWidget
    from qgis.utils import iface
    
    dockwidget = None
    for dock in iface.mainWindow().findChildren(QDockWidget):
        if 'FilterMate' in dock.windowTitle():
            dockwidget = dock
            break
    
    if not dockwidget:
        print("❌ Dockwidget non trouvé")
    else:
        print("=" * 60)
        print("CORRECTION DE LA VISIBILITÉ DES WIDGETS")
        print("=" * 60)
        print()
        
        fixed_count = 0
        
        # 1. Widget FILTERING - layers_to_filter
        if hasattr(dockwidget, 'checkableComboBoxLayer_filtering_layers_to_filter'):
            w = dockwidget.checkableComboBoxLayer_filtering_layers_to_filter
            print(f"1. layers_to_filter: Visible={w.isVisible()}, Size={w.size().width()}x{w.size().height()}")
            
            # Force la visibilité
            w.show()
            w.setVisible(True)
            
            # Force la mise à jour du parent
            if w.parent():
                w.parent().updateGeometry()
                w.parent().update()
            
            # Force la mise à jour du widget
            w.updateGeometry()
            w.update()
            
            print(f"   ✅ Après correction: Visible={w.isVisible()}")
            fixed_count += 1
        
        # 2. Widget EXPORTING - layers_to_export  
        if hasattr(dockwidget, 'checkableComboBoxLayer_exporting_layers'):
            w = dockwidget.checkableComboBoxLayer_exporting_layers
            print(f"2. layers_to_export: Visible={w.isVisible()}, Size={w.size().width()}x{w.size().height()}")
            
            w.show()
            w.setVisible(True)
            
            if w.parent():
                w.parent().updateGeometry()
                w.parent().update()
            
            w.updateGeometry()
            w.update()
            
            print(f"   ✅ Après correction: Visible={w.isVisible()}")
            fixed_count += 1
        
        # 3. Widget EXPLORING - multiple selection
        if hasattr(dockwidget, 'checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection'):
            w = dockwidget.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection
            print(f"3. multiple_selection: Visible={w.isVisible()}, Size={w.size().width()}x{w.size().height()}")
            
            w.show()
            w.setVisible(True)
            
            if w.parent():
                w.parent().updateGeometry()
                w.parent().update()
            
            w.updateGeometry()
            w.update()
            
            print(f"   ✅ Après correction: Visible={w.isVisible()}")
            fixed_count += 1
        
        # 4. Force la mise à jour complète du dockwidget
        dockwidget.updateGeometry()
        dockwidget.update()
        
        print()
        print(f"✅ {fixed_count} widgets corrigés")
        print("=" * 60)
        print()
        print("⚠️ Si les widgets ne sont toujours pas visibles:")
        print("1. Il faut corriger le code de setup_*_tab_widgets()")
        print("2. Les layouts doivent être invalidés et activés")
        print("3. Le plugin doit appeler .show() sur les widgets APRÈS insertion")
