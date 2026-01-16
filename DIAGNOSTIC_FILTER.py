"""
Script de diagnostic pour FilterMate - À exécuter dans Console Python QGIS

Vérifie:
1. Les prédicats géométriques sont-ils activés?
2. Les couches distantes sont-elles sélectionnées?
3. Le logging est-il actif?
4. Les paramètres de filtrage sont-ils corrects?
"""

from qgis.utils import iface, plugins
from qgis.core import QgsMessageLog, Qgis
import logging

# Configurer le logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('FilterMate.Diagnostic')
logger.setLevel(logging.DEBUG)

# Handler console
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

print("=" * 80)
print("DIAGNOSTIC FILTERMATE")
print("=" * 80)

# 1. Vérifier que FilterMate est chargé
if 'filter_mate' not in plugins:
    print("❌ FilterMate n'est pas chargé!")
    print("   → Activez le plugin dans Gestionnaire d'extensions")
else:
    print("✓ FilterMate est chargé")
    
    # 2. Récupérer l'instance de FilterMateApp
    filter_mate = plugins['filter_mate']
    app = filter_mate.app  # FIX: C'est 'app', pas 'filter_mate_app'
    
    print(f"\n📋 État de l'application:")
    print(f"  - Plugin: {type(filter_mate).__name__}")
    print(f"  - App: {type(app).__name__}")
    
    # 3. Vérifier les paramètres de filtrage
    print(f"\n🔍 Paramètres du widget:")
    dockwidget = app.dockwidget  # FIX: Le dockwidget est dans app, pas dans filter_mate
    
    if dockwidget:
        # Prédicats géométriques (nouvelle interface avec QgsCheckableComboBox)
        geom_combo = dockwidget.comboBox_filtering_geometric_predicates
        checked_items = geom_combo.checkedItems()
        
        print(f"  - Prédicats géométriques disponibles: {geom_combo.count()}")
        print(f"  - Prédicats sélectionnés: {len(checked_items)}")
        
        if len(checked_items) > 0:
            print(f"  - Prédicats cochés: {checked_items}")
        
        # Note: Les couches à filtrer sont maintenant gérées via app.PROJECT_LAYERS
        # Il n'y a plus de widget list_layers_to_filter dans la nouvelle interface
    
    # 4. Vérifier PROJECT_LAYERS
    print(f"\n📦 PROJECT_LAYERS:")
    if hasattr(app, 'PROJECT_LAYERS'):
        total = sum(len(layers) for layers in app.PROJECT_LAYERS.values())
        print(f"  - Couches enregistrées: {total}")
        for provider, layers in app.PROJECT_LAYERS.items():
            print(f"    • {provider}: {len(layers)} couches")
    else:
        print("  ❌ PROJECT_LAYERS non initialisé")
    
    # 5. Tester la construction des paramètres de tâche
    print(f"\n🔧 Test de construction des paramètres:")
    
    # Vérifier si une couche est sélectionnée
    if not hasattr(dockwidget, 'current_layer') or dockwidget.current_layer is None:
        print(f"  ⚠️ Aucune couche sélectionnée - impossible de tester get_task_parameters")
        print(f"  💡 Sélectionnez une couche dans QGIS pour tester cette fonctionnalité")
    else:
        try:
            # Signature correcte: get_task_parameters(task_name, data=None)
            task_params = app.get_task_parameters(task_name="filter")
            
            if task_params:
                filtering = task_params.get("filtering", {})
                print(f"  - has_geometric_predicates: {filtering.get('has_geometric_predicates')}")
                print(f"  - geometric_predicates: {filtering.get('geometric_predicates')}")
                print(f"  - has_layers_to_filter: {filtering.get('has_layers_to_filter')}")
                print(f"  - layers_to_filter count: {len(filtering.get('layers_to_filter', []))}")
                
                task = task_params.get("task", {})
                print(f"  - task['layers'] count: {len(task.get('layers', []))}")
                
                if len(task.get('layers', [])) > 0:
                    print(f"  - Couches dans task['layers']:")
                    for layer_dict in task['layers'][:5]:
                        print(f"      • {layer_dict.get('layer_name', 'unknown')}")
            else:
                print(f"  ⚠️ get_task_parameters a retourné None (validation échouée)")
        
        except Exception as e:
            print(f"  ❌ Erreur: {e}")
            import traceback
            traceback.print_exc()

print("\n" + "=" * 80)
print("FIN DU DIAGNOSTIC")
print("=" * 80)
print("\n💡 Pour activer le logging détaillé, exécutez ENABLE_LOGGING.py")
print("💡 Ensuite, lancez votre filtre et vérifiez la Console Python")
