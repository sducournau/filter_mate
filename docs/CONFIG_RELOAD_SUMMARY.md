# Système de Reload de Configuration - Résumé

## 📋 Changements Effectués

### Fichiers Créés

1. **config/config.default.json**
   - Configuration par défaut (template)
   - CRS par défaut : EPSG:3857
   - Listes de layers vides
   - Référence pour les resets

2. **docs/CONFIG_RELOAD.md**
   - Documentation complète du système
   - Exemples d'utilisation
   - Guide des meilleures pratiques
   - Troubleshooting

3. **docs/PROJECT_CHANGE_INTEGRATION.py**
   - Exemples d'intégration
   - Détection de changement de projet
   - Code prêt à l'emploi

4. **tests/test_config_reload.py**
   - Tests unitaires complets
   - Validation de toutes les fonctions
   - Tests de sauvegarde/rechargement

### Fichiers Modifiés

1. **config/config.py**
   - Ajout de `load_default_config()`
   - Ajout de `reset_config_to_default()`
   - Ajout de `reload_config()`
   - Ajout de `save_config()`
   - Support des backups automatiques

2. **modules/config_helpers.py**
   - Ajout de `reload_config_from_file()`
   - Ajout de `reset_config_to_defaults()`
   - Ajout de `save_config_to_file()`
   - Wrappers de convenance

3. **config/config.json**
   - Nettoyé : listes de layers vidées
   - CRS par défaut : EPSG:3857
   - Section EXPORT dupliquée supprimée
   - Harmonisé avec config.default.json

## ✨ Fonctionnalités

### 1. Reload de Configuration
```python
from config.config import reload_config
config = reload_config()
```

### 2. Reset aux Valeurs Par Défaut
```python
from config.config import reset_config_to_default
success = reset_config_to_default(backup=True, preserve_app_settings=True)
```

### 3. Sauvegarde de Configuration
```python
from config.config import save_config
config["CURRENT_PROJECT"]["EXPORTING"]["PROJECTION_TO_EXPORT"] = "EPSG:3857"
save_config(config)
```

### 4. Backups Automatiques
- Créés lors du reset avec timestamp
- Format : `config.backup.YYYYMMDD_HHMMSS.json`
- Conserve l'historique des configurations

### 5. Préservation des Paramètres App
- Option pour garder APP_SQLITE_PATH
- Utile lors des resets pour éviter de perdre les chemins

## 🎯 Cas d'Usage

### Changement de Projet QGIS
```python
def on_project_loaded(self):
    from config.config import load_default_config, save_config
    
    current_path = self.PROJECT.fileName()
    stored_path = self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_PATH"]
    
    if current_path != stored_path:
        # Projet différent - reset
        default_config = load_default_config()
        self.CONFIG_DATA["CURRENT_PROJECT"] = default_config["CURRENT_PROJECT"]
        self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_PATH"] = current_path
        save_config(self.CONFIG_DATA)
```

### Nettoyage Manuel
```python
from modules.config_helpers import reset_config_to_defaults
success = reset_config_to_defaults(backup=True)
```

### Restauration depuis Backup
```python
import shutil
shutil.copy2("config/config.backup.20251210_143022.json", "config/config.json")
reload_config()
```

## 📊 Structure

```
config/
├── config.json              # Configuration active (modifiée)
├── config.default.json      # Template par défaut (lecture seule)
├── config.backup.*.json     # Backups automatiques
└── config.py                # Fonctions de gestion

modules/
└── config_helpers.py        # Wrappers de convenance

docs/
├── CONFIG_RELOAD.md         # Documentation complète
└── PROJECT_CHANGE_INTEGRATION.py  # Exemples d'intégration

tests/
└── test_config_reload.py    # Tests unitaires
```

## 🔧 Configuration Par Défaut

### CRS
```json
"PROJECTION_TO_EXPORT": "EPSG:3857"
```

### Listes de Layers
```json
"LAYERS_TO_EXPORT": [],
"layers": []
```

### Options Projet
```json
"PROJECT_ID": "",
"PROJECT_PATH": "",
"PROJECT_SQLITE_PATH": ""
```

## ✅ Tests

Exécuter les tests :
```bash
cd tests
python test_config_reload.py
```

Tests inclus :
- ✓ Chargement config par défaut
- ✓ Reset avec backup
- ✓ Reload depuis fichier
- ✓ Cycle sauvegarde/rechargement
- ✓ Config helpers

## 🚀 Intégration

### Dans filter_mate_app.py

Ajouter la détection de changement de projet :

```python
class FilterMateApp:
    def __init__(self, iface):
        # ... code existant ...
        
        # Activer détection changement de projet
        self.PROJECT.readProject.connect(self.on_project_loaded)
    
    def on_project_loaded(self):
        """Détecte changement de projet et reset config"""
        from config.config import load_default_config, save_config
        
        current_path = self.PROJECT.fileName()
        stored_path = self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_PATH"]
        
        if current_path != stored_path:
            default_config = load_default_config()
            if default_config:
                self.CONFIG_DATA["CURRENT_PROJECT"] = default_config["CURRENT_PROJECT"]
                self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_PATH"] = current_path
                save_config(self.CONFIG_DATA)
                
                from qgis.utils import iface
                iface.messageBar().pushInfo("FilterMate", "Configuration réinitialisée pour le nouveau projet", 3)
```

## 📝 Meilleures Pratiques

1. **Toujours créer un backup lors du reset**
   ```python
   reset_config_to_default(backup=True)  # ✓ Bon
   ```

2. **Préserver les paramètres app par défaut**
   ```python
   reset_config_to_default(preserve_app_settings=True)  # ✓ Bon
   ```

3. **Recharger après modifications externes**
   ```python
   # Après édition manuelle de config.json
   reload_config()
   ```

4. **Utiliser les helpers pour la simplicité**
   ```python
   from modules.config_helpers import reload_config_from_file
   config = reload_config_from_file()  # ✓ Simple
   ```

## 🔍 Debugging

### Vérifier config actuelle
```python
from config.config import ENV_VARS
print(ENV_VARS["CONFIG_DATA"]["CURRENT_PROJECT"]["EXPORTING"]["PROJECTION_TO_EXPORT"])
```

### Lister les backups
```bash
ls -la config/config.backup.*.json
```

### Restaurer un backup spécifique
```python
import shutil
shutil.copy2("config/config.backup.20251210_143022.json", "config/config.json")
```

## 🎉 Avantages

- ✓ Configuration propre au démarrage
- ✓ Pas de données d'anciens projets
- ✓ CRS cohérent (EPSG:3857)
- ✓ Backups automatiques
- ✓ Préservation paramètres app
- ✓ Tests complets
- ✓ Documentation détaillée
- ✓ Facile à intégrer

## 📌 Prochaines Étapes

1. Intégrer `on_project_loaded()` dans `filter_mate_app.py`
2. Tester avec différents projets QGIS
3. Ajouter UI pour reset manuel (optionnel)
4. Nettoyage automatique des vieux backups (optionnel)
