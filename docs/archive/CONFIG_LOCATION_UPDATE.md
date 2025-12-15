# Configuration Location Update

## Problème résolu

Le fichier `config.json` était situé dans le répertoire du plugin (`/plugins/filter_mate/config/`), ce qui posait problème lors de la réinitialisation de la configuration et de la base SQLite.

## Solution implémentée

Le fichier `config.json` est maintenant **situé dans le même répertoire que la base de données SQLite** (`PLUGIN_CONFIG_DIRECTORY`), typiquement :
- `%APPDATA%\QGIS\QGIS3\profiles\default\FilterMate\config.json` (Windows)
- `~/.local/share/QGIS/QGIS3/profiles/default/FilterMate/config.json` (Linux)

## Modifications effectuées

### 1. `config/config.py`

#### Fonction `init_env_vars()`
- **Avant** : Lisait `config.json` depuis `DIR_CONFIG` (répertoire du plugin)
- **Après** : 
  - Lit `config.json` depuis `PLUGIN_CONFIG_DIRECTORY` 
  - Copie automatiquement `config.default.json` si `config.json` n'existe pas
  - Ajoute `CONFIG_JSON_PATH` dans `ENV_VARS` pour référence

#### Nouvelle fonction `reset_config_to_default()`
```python
def reset_config_to_default():
    """
    Reset configuration to default by copying config.default.json 
    to the active config location (PLUGIN_CONFIG_DIRECTORY/config.json).
    
    Use this when reinitializing the config and SQLite database.
    """
```
- Sauvegarde l'ancien `config.json` en `.backup`
- Copie `config.default.json` vers `PLUGIN_CONFIG_DIRECTORY/config.json`
- Recharge la configuration dans `ENV_VARS`

### 2. `filter_mate_dockwidget.py`

Modifié 3 occurrences utilisant des chemins hardcodés :
```python
# AVANT
with open(self.plugin_dir + '/config/config.json', 'r') as infile:

# APRÈS
config_json_path = ENV_VARS.get('CONFIG_JSON_PATH', self.plugin_dir + '/config/config.json')
with open(config_json_path, 'r') as infile:
```

### 3. `filter_mate_app.py`

Modifié 2 occurrences :
```python
# AVANT
with open(ENV_VARS["DIR_CONFIG"] + os.sep + 'config.json', 'w') as outfile:

# APRÈS
with open(ENV_VARS["CONFIG_JSON_PATH"], 'w') as outfile:
```

## Comportement

### Au premier démarrage
1. `PLUGIN_CONFIG_DIRECTORY` est créé si nécessaire
2. `config.default.json` est copié vers `PLUGIN_CONFIG_DIRECTORY/config.json`
3. Message info dans les logs QGIS

### Lors des réinitialisations
1. Supprimer la base SQLite : `rm PLUGIN_CONFIG_DIRECTORY/*.db`
2. Appeler `reset_config_to_default()` pour restaurer la config par défaut
3. Un backup est créé : `config.json.backup`

### Fallback
Si la copie échoue, le système utilise `config.json` du répertoire du plugin comme fallback.

## Migration pour utilisateurs existants

Lors du prochain démarrage :
- Le plugin détecte que `config.json` n'existe pas dans `PLUGIN_CONFIG_DIRECTORY`
- Il copie automatiquement `config.default.json`
- L'ancien `config.json` dans le répertoire du plugin reste intact (non utilisé)

Les utilisateurs peuvent :
1. Copier manuellement leur ancien `config.json` si personnalisé
2. Ou laisser le système utiliser les valeurs par défaut

## Avantages

✅ Configuration et base SQLite au même endroit  
✅ Réinitialisation simplifiée (supprimer le dossier)  
✅ Séparation claire : plugin (code) vs données utilisateur (config + DB)  
✅ Backup automatique lors des réinitialisations  
✅ Migration transparente pour les utilisateurs existants  

## Tests recommandés

- [ ] Premier démarrage : vérifier copie de config.default.json
- [ ] Réinitialisation : appeler `reset_config_to_default()`
- [ ] Modification config via UI : vérifier sauvegarde au bon endroit
- [ ] Suppression de PLUGIN_CONFIG_DIRECTORY : vérifier recréation
- [ ] Migration depuis ancienne version

## Fichiers modifiés

- `config/config.py` - Logic principale
- `filter_mate_dockwidget.py` - Lectures/écritures de config
- `filter_mate_app.py` - Sauvegardes de config
- `CONFIG_LOCATION_UPDATE.md` - Cette documentation
