# Fix: AUTO_ACTIVATE Configuration Access Bug

**Date**: 2025-12-17  
**Status**: ✅ Fixed  
**Priority**: High  
**Impact**: Configuration option ignored, auto-activation always enabled

## Problem

L'option `AUTO_ACTIVATE` à `false` dans [config/config.json](config/config.json) était ignorée - le plugin démarrait automatiquement malgré cette configuration.

### Root Cause

Deux bugs d'accès à la configuration dans `ENV_VARS`:

1. **[filter_mate.py](filter_mate.py#L277)** - Méthode `_connect_auto_activation_signals()`
2. **[modules/backends/factory.py](modules/backends/factory.py#L38)** - Fonction `get_small_dataset_config()`

Les deux utilisaient incorrectement:
```python
ENV_VARS.get('APP', {})  # ❌ 'APP' n'existe pas directement dans ENV_VARS
```

Au lieu de:
```python
ENV_VARS.get('CONFIG_DATA', {}).get('APP', {})  # ✅ Chemin correct
```

### Impact

- `AUTO_ACTIVATE.value = false` était ignoré → le plugin démarrait toujours automatiquement
- `SMALL_DATASET_OPTIMIZATION` était potentiellement mal lu → fallback aux valeurs par défaut
- Les signaux `projectRead`, `newProjectCreated`, et `layersAdded` étaient toujours connectés

## Solution

### Changes Applied

**1. [filter_mate.py](filter_mate.py#L274-L280)** - `_connect_auto_activation_signals()`

```python
# Before (ligne 277)
auto_activate_enabled = ENV_VARS.get('APP', {}).get('AUTO_ACTIVATE', {}).get('value', True)

# After
config_data = ENV_VARS.get('CONFIG_DATA', {})
auto_activate_enabled = config_data.get('APP', {}).get('AUTO_ACTIVATE', {}).get('value', True)
```

**2. [modules/backends/factory.py](modules/backends/factory.py#L35-L40)** - `get_small_dataset_config()`

```python
# Before (ligne 38)
config = ENV_VARS.get('APP', {}).get('OPTIONS', {}).get('SMALL_DATASET_OPTIMIZATION', {})

# After
config_data = ENV_VARS.get('CONFIG_DATA', {})
config = config_data.get('APP', {}).get('OPTIONS', {}).get('SMALL_DATASET_OPTIMIZATION', {})
```

## Verification

Pour tester que le fix fonctionne:

1. **Vérifier la configuration actuelle**:
   ```json
   // config/config.json
   {
     "APP": {
       "AUTO_ACTIVATE": {
         "value": false  // ← doit être false
       }
     }
   }
   ```

2. **Redémarrer QGIS** (pour recharger le plugin)

3. **Ouvrir un projet avec des couches vectorielles**

4. **Résultat attendu**:
   - Le plugin ne s'active PAS automatiquement
   - Dans les logs QGIS (console Python):
     ```
     FilterMate: Auto-activation disabled in configuration
     ```
   - Aucun signal connecté pour auto-activation

5. **Pour activer manuellement** : Menu Vector → FilterMate

## Technical Details

### Structure de ENV_VARS

```python
# Après init_env_vars()
ENV_VARS = {
    "PROJECT": QgsProject.instance(),
    "PLATFORM": sys.platform,
    "DIR_CONFIG": "/path/to/plugin/config",
    "CONFIG_DATA": {  # ← Configuration complète ici
        "APP": {
            "AUTO_ACTIVATE": {"value": false},
            "OPTIONS": {...},
            ...
        }
    },
    "PLUGIN_CONFIG_DIRECTORY": "/path/to/QGIS/FilterMate",
    ...
}
```

### Correct Access Pattern

```python
# ✅ Correct - via CONFIG_DATA
config_data = ENV_VARS.get('CONFIG_DATA', {})
value = config_data.get('APP', {}).get('KEY', {}).get('value')

# ❌ Incorrect - accès direct à APP
value = ENV_VARS.get('APP', {})  # Retourne toujours {} (dict vide)
```

### Why This Bug Existed

- `ENV_VARS.get('APP', {})` retourne toujours `{}` (valeur par défaut)
- `.get('AUTO_ACTIVATE', {})` sur `{}` retourne `{}`
- `.get('value', True)` sur `{}` retourne `True` (valeur par défaut)
- **Résultat**: Auto-activation toujours activée, quelle que soit la config

## Related Code

### Exemples d'accès correct dans le codebase

**[filter_mate_app.py](filter_mate_app.py#L225)**:
```python
self.CONFIG_DATA = ENV_VARS["CONFIG_DATA"]  # ✅ Correct
```

**[config/config.py](config/config.py#L167)**:
```python
ENV_VARS["CONFIG_DATA"] = CONFIG_DATA  # Comment c'est stocké
```

## Testing Checklist

- [x] Vérifier que `AUTO_ACTIVATE = false` empêche l'auto-activation
- [x] Vérifier que les logs affichent "Auto-activation disabled in configuration"
- [x] Vérifier qu'aucun signal n'est connecté (`_auto_activation_signals_connected == False`)
- [ ] Tester `SMALL_DATASET_OPTIMIZATION` est correctement lu depuis la config
- [ ] Tester activation manuelle via menu fonctionne toujours

## Code Quality Improvements

### Recommendation: Centralized Config Access Helper

Pour éviter ce type de bug à l'avenir, considérer:

```python
# config/config.py
def get_config_value(*keys, default=None):
    """
    Safe access to configuration values.
    
    Args:
        *keys: Path to config value (e.g., 'APP', 'AUTO_ACTIVATE', 'value')
        default: Default value if path not found
    
    Returns:
        Configuration value or default
    
    Example:
        >>> get_config_value('APP', 'AUTO_ACTIVATE', 'value', default=True)
        False
    """
    config_data = ENV_VARS.get('CONFIG_DATA', {})
    result = config_data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key)
        else:
            return default
        if result is None:
            return default
    return result
```

Usage:
```python
# Au lieu de
config_data = ENV_VARS.get('CONFIG_DATA', {})
auto_activate = config_data.get('APP', {}).get('AUTO_ACTIVATE', {}).get('value', True)

# Utiliser
from .config.config import get_config_value
auto_activate = get_config_value('APP', 'AUTO_ACTIVATE', 'value', default=True)
```

## References

- [config/config.py](config/config.py#L22-L169) - `init_env_vars()` function
- [filter_mate.py](filter_mate.py#L265-L306) - `_connect_auto_activation_signals()` method
- [modules/backends/factory.py](modules/backends/factory.py#L27-L46) - `get_small_dataset_config()` function
- User report: "l'option auto active est a false dans me config, le plugin ne devrait pas démarrer automatiquement"

## See Also

- [CONFIG_HARMONIZATION_PROPOSAL.md](../CONFIG_HARMONIZATION_PROPOSAL.md)
- [.github/copilot-instructions.md](../../.github/copilot-instructions.md) - Critical pattern: Check configuration correctly
