"""
Script de rechargement rapide du plugin FilterMate dans QGIS.

À exécuter dans la Console Python de QGIS :
    exec(open(r'C:/Users/Simon/AppData/Roaming/QGIS/QGIS3/profiles/imagodata/python/plugins/filter_mate/reload_plugin.py').read())
"""

print("\n" + "=" * 60)
print("Rechargement du plugin FilterMate")
print("=" * 60 + "\n")

try:
    from qgis.utils import plugins, reloadPlugin
    
    # Vérifier si le plugin est chargé
    if 'filter_mate' not in plugins:
        print("⚠ Plugin 'filter_mate' non trouvé dans les plugins chargés")
        print("Plugins disponibles:", list(plugins.keys())[:10], "...")
        print("\nChargement du plugin...")
        
        try:
            from qgis.utils import loadPlugin, startPlugin
            loadPlugin('filter_mate')
            startPlugin('filter_mate')
            print("✓ Plugin chargé")
        except Exception as e:
            print(f"✗ Erreur lors du chargement: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("Rechargement du plugin...")
        result = reloadPlugin('filter_mate')
        
        if result:
            print("✓ Plugin rechargé avec succès")
            
            # Vérifier le statut PostgreSQL
            try:
                from filter_mate.modules.appUtils import POSTGRESQL_AVAILABLE
                status = "✓ ACTIVÉ" if POSTGRESQL_AVAILABLE else "✗ DÉSACTIVÉ"
                print(f"\nSupport PostgreSQL: {status}")
                if not POSTGRESQL_AVAILABLE:
                    print("  → psycopg2 n'est pas installé")
                    print("  → Pour l'installer: pip install psycopg2-binary")
            except ImportError as e:
                print(f"⚠ Impossible de vérifier le statut PostgreSQL: {e}")
        else:
            print("✗ Échec du rechargement")
            
except Exception as e:
    print(f"✗ Erreur: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("Fin du rechargement")
print("=" * 60 + "\n")
