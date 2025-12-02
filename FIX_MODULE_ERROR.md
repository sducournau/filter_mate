# Solution: ModuleNotFoundError: No module named 'modules'

## Problème
QGIS a mis en cache une ancienne version du code avec un import incorrect. L'erreur indique:
```
File "...\filter_mate_app.py", line 886, in update_datasource
    from modules.appUtils import POSTGRESQL_AVAILABLE
ModuleNotFoundError: No module named 'modules'
```

Mais le code actuel (ligne 22) utilise correctement l'import relatif:
```python
from .modules.appUtils import POSTGRESQL_AVAILABLE
```

## Cause
QGIS utilise le cache bytecode Python (.pyc files) pour améliorer les performances. Quand vous modifiez le code source, l'ancien bytecode peut rester en cache et causer des erreurs.

## Solutions (essayez dans cet ordre)

### Solution 1: Nettoyer le cache avec le script
```bash
cd /windows/c/Users/Simon/OneDrive/Documents/GitHub/filter_mate
python clear_cache.py
```

Ensuite:
1. Ouvrez QGIS
2. Plugin Manager > Installed > Décochez FilterMate
3. **Fermez QGIS complètement**
4. Rouvrez QGIS
5. Plugin Manager > Installed > Cochez FilterMate

### Solution 2: Nettoyer manuellement le cache QGIS
```bash
# Supprimez le cache du plugin dans le profil QGIS
rm -rf "C:/Users/Simon/AppData/Roaming/QGIS/QGIS3/profiles/imagodata/python/plugins/filter_mate/__pycache__"
rm -rf "C:/Users/Simon/AppData/Roaming/QGIS/QGIS3/profiles/imagodata/python/plugins/filter_mate/modules/__pycache__"
rm -rf "C:/Users/Simon/AppData/Roaming/QGIS/QGIS3/profiles/imagodata/python/plugins/filter_mate/config/__pycache__"
```

Puis fermez et rouvrez QGIS complètement.

### Solution 3: Réinstaller le plugin
1. Dans QGIS, allez dans Plugin Manager > Installed
2. Sélectionnez FilterMate > Uninstall Plugin
3. Fermez QGIS complètement
4. Supprimez le répertoire du plugin:
   ```bash
   rm -rf "C:/Users/Simon/AppData/Roaming/QGIS/QGIS3/profiles/imagodata/python/plugins/filter_mate"
   ```
5. Copiez le plugin source vers le répertoire QGIS:
   ```bash
   cp -r /windows/c/Users/Simon/OneDrive/Documents/GitHub/filter_mate "C:/Users/Simon/AppData/Roaming/QGIS/QGIS3/profiles/imagodata/python/plugins/"
   ```
6. Rouvrez QGIS
7. Plugin Manager > Installed > Cochez FilterMate

### Solution 4: Forcer le rechargement en Python
Si vous avez accès à la console Python de QGIS:

```python
import sys
# Supprimer tous les modules FilterMate du cache
modules_to_remove = [m for m in sys.modules if m.startswith('filter_mate')]
for module in modules_to_remove:
    del sys.modules[module]

# Recharger le plugin
from qgis.utils import reloadPlugin
reloadPlugin('FilterMate')
```

## Vérification
Après avoir appliqué une solution, vérifiez dans la console Python QGIS:

```python
import filter_mate.modules.appUtils as utils
print(utils.POSTGRESQL_AVAILABLE)
print("Import successful!")
```

## Prévention future
Pour éviter ce problème:
1. Toujours fermer QGIS complètement après modification du code
2. Utiliser le Plugin Reloader pour le développement
3. Exécuter `clear_cache.py` avant chaque test de modification majeure

## Note technique
Le code source actuel est correct. Tous les imports utilisent la syntaxe relative correcte (`.modules`) nécessaire pour les packages QGIS. Le problème vient uniquement du cache Python de QGIS.
