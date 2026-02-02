"""
Script pour FORCER l'insertion des widgets dynamiques dans les layouts.

Ce script contourne le problème de rechargement du plugin en insérant
manuellement les widgets dans les layouts.

À exécuter dans la console Python de QGIS:
    exec(open('C:/Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/force_add_widgets.py').read())
"""

from qgis.utils import iface, plugins
from qgis.PyQt.QtWidgets import QDockWidget, QHBoxLayout, QVBoxLayout

# Récupérer le dockwidget
dockwidget = None
for dock in iface.mainWindow().findChildren(QDockWidget):
    if 'FilterMate' in dock.windowTitle():
        dockwidget = dock
        break

if not dockwidget:
    print("❌ FilterMate dockwidget non trouvé")
else:
    print("=" * 70)
    print("INSERTION FORCÉE DES WIDGETS DYNAMIQUES")
    print("=" * 70)
    print()
    
    # ========================================================================
    # 1. FILTERING - checkableComboBoxLayer_filtering_layers_to_filter
    # ========================================================================
    print("1. FILTERING - layers_to_filter")
    
    if hasattr(dockwidget, 'checkableComboBoxLayer_filtering_layers_to_filter'):
        widget = dockwidget.checkableComboBoxLayer_filtering_layers_to_filter
        
        # Vérifier si le layout horizontal existe déjà
        if hasattr(dockwidget, 'horizontalLayout_filtering_distant_layers'):
            layout = dockwidget.horizontalLayout_filtering_distant_layers
            print(f"   ✓ horizontalLayout_filtering_distant_layers existe déjà")
            print(f"   - Count: {layout.count()} widgets")
        else:
            # Créer le layout horizontal
            layout = QHBoxLayout()
            layout.setSpacing(4)
            layout.setContentsMargins(0, 0, 0, 0)
            dockwidget.horizontalLayout_filtering_distant_layers = layout
            print(f"   ✓ horizontalLayout_filtering_distant_layers créé")
            
            # Ajouter le widget au layout
            layout.addWidget(widget)
            
            # Ajouter le checkbox centroids si disponible
            if hasattr(dockwidget, 'checkBox_filtering_use_centroids_distant_layers'):
                layout.addWidget(dockwidget.checkBox_filtering_use_centroids_distant_layers)
            
            # Insérer le layout dans verticalLayout_filtering_values à la position 2
            if hasattr(dockwidget, 'verticalLayout_filtering_values'):
                v_layout = dockwidget.verticalLayout_filtering_values
                print(f"   - verticalLayout_filtering_values count avant: {v_layout.count()}")
                v_layout.insertLayout(2, layout)
                v_layout.invalidate()
                v_layout.activate()
                print(f"   ✅ Layout inséré à la position 2")
                print(f"   - verticalLayout_filtering_values count après: {v_layout.count()}")
            else:
                print("   ❌ verticalLayout_filtering_values NOT FOUND")
        
        # Forcer la visibilité
        widget.show()
        widget.setVisible(True)
        widget.setMinimumHeight(26)
        widget.updateGeometry()
        
        print(f"   - Widget visible: {widget.isVisible()}")
        print(f"   - Widget size: {widget.size().width()}x{widget.size().height()}")
        print(f"   - Widget minSize: {widget.minimumSize().width()}x{widget.minimumSize().height()}")
    else:
        print("   ❌ Widget n'existe pas")
    
    print()
    
    # ========================================================================
    # 2. EXPORTING - checkableComboBoxLayer_exporting_layers
    # ========================================================================
    print("2. EXPORTING - layers_to_export")
    
    if hasattr(dockwidget, 'checkableComboBoxLayer_exporting_layers'):
        widget = dockwidget.checkableComboBoxLayer_exporting_layers
        
        # Vérifier si le widget est déjà dans le layout
        if hasattr(dockwidget, 'verticalLayout_exporting_values'):
            v_layout = dockwidget.verticalLayout_exporting_values
            print(f"   - verticalLayout_exporting_values count avant: {v_layout.count()}")
            
            # Vérifier si le widget est déjà dans le layout
            widget_in_layout = False
            for i in range(v_layout.count()):
                item = v_layout.itemAt(i)
                if item and item.widget() == widget:
                    widget_in_layout = True
                    break
            
            if not widget_in_layout:
                # Insérer le widget à la position 0
                v_layout.insertWidget(0, widget)
                v_layout.invalidate()
                v_layout.activate()
                print(f"   ✅ Widget inséré à la position 0")
                print(f"   - verticalLayout_exporting_values count après: {v_layout.count()}")
            else:
                print(f"   ✓ Widget déjà dans le layout")
        else:
            print("   ❌ verticalLayout_exporting_values NOT FOUND")
        
        # Forcer la visibilité
        widget.show()
        widget.setVisible(True)
        widget.setMinimumHeight(26)
        widget.updateGeometry()
        
        print(f"   - Widget visible: {widget.isVisible()}")
        print(f"   - Widget size: {widget.size().width()}x{widget.size().height()}")
    else:
        print("   ❌ Widget n'existe pas")
    
    print()
    
    # ========================================================================
    # 3. EXPLORING - checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection
    # ========================================================================
    print("3. EXPLORING - multiple_selection_features")
    
    if hasattr(dockwidget, 'checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection'):
        widget = dockwidget.checkableComboBoxFeaturesListPickerWidget_exploring_multiple_selection
        
        # Vérifier si le widget est dans le layout
        if hasattr(dockwidget, 'horizontalLayout_exploring_multiple_feature_picker'):
            h_layout = dockwidget.horizontalLayout_exploring_multiple_feature_picker
            print(f"   - horizontalLayout_exploring_multiple_feature_picker count avant: {h_layout.count()}")
            
            # Vérifier si le widget est déjà dans le layout
            widget_in_layout = False
            for i in range(h_layout.count()):
                item = h_layout.itemAt(i)
                if item and item.widget() == widget:
                    widget_in_layout = True
                    break
            
            if not widget_in_layout:
                # Insérer le widget à la position 0
                h_layout.insertWidget(0, widget, 1)
                h_layout.invalidate()
                h_layout.activate()
                print(f"   ✅ Widget inséré à la position 0")
                print(f"   - horizontalLayout_exploring_multiple_feature_picker count après: {h_layout.count()}")
            else:
                print(f"   ✓ Widget déjà dans le layout")
        else:
            print("   ❌ horizontalLayout_exploring_multiple_feature_picker NOT FOUND")
        
        # Forcer la visibilité
        widget.show()
        widget.setVisible(True)
        widget.setMinimumHeight(158)
        widget.updateGeometry()
        
        # Forcer la visibilité du parent groupbox
        if hasattr(dockwidget, 'mGroupBox_exploring_multiple_selection'):
            parent = dockwidget.mGroupBox_exploring_multiple_selection
            parent.updateGeometry()
            parent.update()
        
        print(f"   - Widget visible: {widget.isVisible()}")
        print(f"   - Widget size: {widget.size().width()}x{widget.size().height()}")
    else:
        print("   ❌ Widget n'existe pas")
    
    print()
    
    # Force la mise à jour complète
    if hasattr(dockwidget, 'FILTERING'):
        dockwidget.FILTERING.updateGeometry()
        dockwidget.FILTERING.update()
    
    if hasattr(dockwidget, 'EXPORTING'):
        dockwidget.EXPORTING.updateGeometry()
        dockwidget.EXPORTING.update()
    
    dockwidget.updateGeometry()
    dockwidget.update()
    
    print("=" * 70)
    print("✅ INSERTION FORCÉE TERMINÉE")
    print("=" * 70)
    print()
    print("Les widgets devraient maintenant être visibles.")
    print("Si ce n'est pas le cas, le problème vient de la structure des layouts.")
