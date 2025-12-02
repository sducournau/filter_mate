# Correction appliquée - ModuleNotFoundError

## Problème identifié

L'erreur `ModuleNotFoundError: No module named 'modules'` était causée par un **import dynamique incorrect** dans le fichier `modules/appTasks.py` à la ligne 1173.

### Code incorrect (avant):
```python
from modules.appUtils import create_temp_spatialite_table, get_spatialite_datasource_from_layer
```

### Code corrigé (après):
```python
from .appUtils import create_temp_spatialite_table, get_spatialite_datasource_from_layer
```

## Explication technique

Dans un plugin QGIS (qui est un package Python), tous les imports entre modules du même package **DOIVENT utiliser des imports relatifs** (avec le préfixe `.`).

### ✅ Correct - Import relatif:
```python
from .appUtils import fonction          # Même niveau
from ..config import CONFIG             # Niveau parent
```

### ❌ Incorrect - Import absolu:
```python
from modules.appUtils import fonction   # Ne fonctionne pas dans un plugin QGIS
```

## Fichier modifié

**Fichier:** `modules/appTasks.py`  
**Ligne:** 1173  
**Méthode:** `_create_spatialite_materialized_view`  

## Instructions pour appliquer le correctif

### Option 1: La correction est déjà faite dans le code source

Si vous utilisez ce dépôt Git, la correction est déjà appliquée. Vous devez simplement:

1. **Nettoyer le cache Python:**
   - Sur Windows: Double-cliquez sur `clear_cache.bat`
   - Ou exécutez: `python clear_cache.py`

2. **Redémarrer QGIS:**
   - Fermez QGIS complètement
   - Rouvrez QGIS
   - Plugin Manager > Installed > Décochez puis recochez FilterMate

### Option 2: Si vous avez déjà installé le plugin

Si le plugin est déjà installé dans QGIS, suivez ces étapes:

```powershell
# 1. Nettoyer le cache QGIS
Remove-Item -Path "$env:APPDATA\QGIS\QGIS3\profiles\imagodata\python\plugins\filter_mate\__pycache__" -Recurse -Force
Remove-Item -Path "$env:APPDATA\QGIS\QGIS3\profiles\imagodata\python\plugins\filter_mate\modules\__pycache__" -Recurse -Force

# 2. Copier la nouvelle version
Copy-Item -Path "C:\Users\Simon\OneDrive\Documents\GitHub\filter_mate\modules\appTasks.py" `
          -Destination "$env:APPDATA\QGIS\QGIS3\profiles\imagodata\python\plugins\filter_mate\modules\appTasks.py" `
          -Force
```

Puis redémarrez QGIS.

## Vérification

Après avoir appliqué le correctif, vérifiez dans la console Python QGIS:

```python
# Test d'import
from filter_mate.modules.appUtils import POSTGRESQL_AVAILABLE
print(f"PostgreSQL disponible: {POSTGRESQL_AVAILABLE}")
print("✅ Import réussi!")
```

## Contexte du bug

Ce bug a été introduit lors du développement de la Phase 2 (support Spatialite). Un import dynamique a été ajouté dans une méthode sans utiliser la syntaxe d'import relatif requise pour les plugins QGIS.

### Pourquoi l'import était dynamique?

L'import était dans la méthode `_create_spatialite_materialized_view()` pour éviter les imports circulaires et pour n'importer ces fonctions que lorsqu'elles sont réellement nécessaires (lazy loading).

### Solution retenue

Garder l'import dynamique (car il est approprié pour éviter les imports circulaires) mais utiliser la syntaxe d'import relatif correcte avec le préfixe `.`

## Prévention

Pour éviter ce type d'erreur à l'avenir:

1. **Toujours utiliser des imports relatifs** dans un plugin QGIS
2. **Vérifier les imports dynamiques** dans les méthodes
3. **Tester après chaque modification** avec un QGIS fraîchement redémarré
4. **Utiliser les scripts de nettoyage** fournis avant chaque test

## Scripts de nettoyage fournis

- `clear_cache.py` - Script Python multiplateforme
- `clear_cache.bat` - Script Windows (double-clic)
- `clear_cache.ps1` - Script PowerShell avec sortie détaillée

## Documentation associée

- `FIX_MODULE_ERROR.md` - Guide détaillé de dépannage
- `.github/copilot-instructions.md` - Bonnes pratiques d'import (section "Import Order")
