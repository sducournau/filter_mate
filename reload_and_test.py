"""
Script pour recharger FilterMate et afficher le diagnostic.

À exécuter dans la console Python de QGIS.
"""

from qgis.utils import iface, plugins
import importlib

print("=" * 60)
print("RECHARGEMENT DE FILTERMATE")
print("=" * 60)

# 1. Recharger le plugin
plugin_name = "filter_mate"

if plugin_name in plugins:
    print(f"✅ Plugin '{plugin_name}' trouvé")
    
    # Désactiver le plugin
    print("  - Désactivation...")
    try:
        plugins[plugin_name].unload()
        print("  ✅ Plugin désactivé")
    except Exception as e:
        print(f"  ⚠️ Erreur lors de la désactivation: {e}")
    
    # Recharger tous les modules
    print("  - Rechargement des modules...")
    import sys
    modules_to_reload = [name for name in sys.modules.keys() if name.startswith(plugin_name)]
    print(f"  - {len(modules_to_reload)} modules à recharger")
    
    for module_name in modules_to_reload:
        try:
            importlib.reload(sys.modules[module_name])
        except:
            pass
    
    # Réactiver le plugin
    print("  - Réactivation...")
    try:
        plugins[plugin_name].initGui()
        print("  ✅ Plugin réactivé")
    except Exception as e:
        print(f"  ❌ Erreur lors de la réactivation: {e}")
        import traceback
        traceback.print_exc()
else:
    print(f"❌ Plugin '{plugin_name}' NON TROUVÉ dans plugins")
    print(f"Plugins disponibles: {list(plugins.keys())}")

print("=" * 60)
print()

# 2. Exécuter le diagnostic
print("Exécution du diagnostic des widgets...")
print()

try:
    exec(open('C:/Users/SimonDucorneau/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/test_widgets_debug.py').read())
except FileNotFoundError:
    print("❌ Fichier test_widgets_debug.py non trouvé")
    print("Essayez de l'exécuter manuellement:")
    print("  exec(open('C:/Users/.../filter_mate/test_widgets_debug.py').read())")
except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
