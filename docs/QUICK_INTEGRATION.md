# Configuration System - Quick Integration Guide

## ⚡ Pour démarrer rapidement

Ce guide montre comment intégrer le nouveau système de configuration en **5 minutes**.

## 1️⃣ Activer la migration automatique (2 min)

### Dans `filter_mate.py` ou `filter_mate_app.py`

```python
def initGui(self):
    """Initialize plugin GUI."""
    # ... code existant ...
    
    # ✨ AJOUTER : Migration automatique au démarrage
    self.check_and_migrate_config()
    
    # ... reste du code ...

def check_and_migrate_config(self):
    """Vérifier et migrer la configuration si nécessaire."""
    try:
        from modules.config_migration import ConfigMigration
        
        migrator = ConfigMigration()
        performed, warnings = migrator.auto_migrate_if_needed()
        
        if performed:
            from qgis.utils import iface
            iface.messageBar().pushSuccess(
                "FilterMate",
                "Configuration mise à jour"
            )
            
            # Recharger la config après migration
            from config.config import init_env_vars
            init_env_vars()
    
    except Exception as e:
        print(f"Config migration warning: {e}")
```

**✅ C'est tout !** La migration est maintenant automatique au démarrage.

## 2️⃣ Ajouter un bouton Settings (3 min)

### Option A : Dans la barre d'actions

```python
def setup_action_bar(self):
    """Setup action bar with settings button."""
    # ... boutons existants ...
    
    # ✨ AJOUTER : Bouton Settings
    from qgis.PyQt.QtWidgets import QPushButton
    from qgis.PyQt.QtGui import QIcon
    import os
    
    settings_btn = QPushButton()
    settings_btn.setIcon(QIcon(os.path.join(self.plugin_dir, "icons", "settings.png")))
    settings_btn.setToolTip("Configuration")
    settings_btn.setFixedSize(30, 30)
    settings_btn.clicked.connect(self.open_settings)
    
    self.action_bar_layout.addWidget(settings_btn)

def open_settings(self):
    """Ouvrir le dialog de configuration."""
    from modules.config_editor_widget import SimpleConfigDialog
    
    dialog = SimpleConfigDialog(self.config_data, parent=self)
    dialog.editor.config_changed.connect(self.on_config_changed)
    dialog.show()

def on_config_changed(self, config_path, new_value):
    """Réagir aux changements de configuration."""
    print(f"Config changed: {config_path} = {new_value}")
    
    # Appliquer les changements
    if config_path.startswith('app.ui.theme'):
        self.apply_theme()
    elif config_path == 'app.ui.profile':
        self.apply_ui_profile()
    
    # Sauvegarder
    self.save_config()
```

### Option B : Menu contextuel

```python
# Dans filter_mate.py
def initGui(self):
    # ... code existant ...
    
    # ✨ AJOUTER : Menu Settings
    from qgis.PyQt.QtWidgets import QAction
    
    settings_action = QAction("Settings...", self.iface.mainWindow())
    settings_action.triggered.connect(self.open_settings)
    self.iface.addPluginToMenu("FilterMate", settings_action)
```

**✅ Done!** Les utilisateurs peuvent maintenant accéder aux settings.

## 3️⃣ Utiliser les métadonnées dans le code (bonus)

### Remplacer les accès directs

**Avant ❌**
```python
feedback_level = self.config_data["APP"]["DOCKWIDGET"]["FEEDBACK_LEVEL"]["value"]
```

**Après ✅**
```python
from modules.config_helpers import get_feedback_level

feedback_level = get_feedback_level(self.config_data)
```

### Valider les entrées utilisateur

```python
from modules.config_helpers import validate_config_value_with_metadata

user_input = some_widget.text()
valid, error = validate_config_value_with_metadata('app.ui.profile', user_input)

if not valid:
    QMessageBox.warning(self, "Invalid Input", error)
    return

# Appliquer la valeur validée
apply_config_value(user_input)
```

## 📋 Checklist d'intégration

- [ ] Migration automatique ajoutée au démarrage
- [ ] Bouton Settings ajouté à l'interface
- [ ] Handler `on_config_changed` implémenté
- [ ] Icône settings ajoutée dans `icons/` (optionnel)
- [ ] Testé avec une config v1.0
- [ ] Testé avec une config v2.0
- [ ] Vérifié que les backups sont créés
- [ ] Changements documentés dans CHANGELOG

## 🎨 Ajouter l'icône settings (optionnel)

Télécharger une icône settings (⚙️) et la placer dans :
```
icons/settings.png  (30×30 pixels recommandé)
```

Ou utiliser une icône QGIS existante :
```python
from qgis.PyQt.QtGui import QIcon
icon = QIcon.fromTheme("settings")
```

## 🧪 Tester l'intégration

```bash
# 1. Tests automatiques
python tests/test_config_migration.py

# 2. Test manuel
# - Ouvrir QGIS
# - Charger FilterMate avec une ancienne config
# - Vérifier la migration automatique
# - Ouvrir le dialog Settings
# - Changer quelques valeurs
# - Vérifier que les changements sont appliqués

# 3. Vérifier les backups
ls -la config/backups/
```

## ⚠️ Points d'attention

### 1. Recharger la config après migration

```python
if migration_performed:
    # Recharger ENV_VARS
    from config.config import init_env_vars
    init_env_vars()
    
    # Recharger dans votre classe
    self.config_data = ENV_VARS["CONFIG_DATA"]
```

### 2. Sauvegarder les changements

```python
def save_config(self):
    """Sauvegarder la configuration."""
    import json
    from config.config import ENV_VARS
    
    config_path = ENV_VARS["CONFIG_PATH"]
    
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(self.config_data, f, indent=2, ensure_ascii=False)
```

### 3. Gérer les erreurs

```python
def open_settings(self):
    """Ouvrir settings avec gestion d'erreur."""
    try:
        from modules.config_editor_widget import SimpleConfigDialog
        dialog = SimpleConfigDialog(self.config_data, parent=self)
        dialog.show()
    except Exception as e:
        from qgis.utils import iface
        iface.messageBar().pushCritical(
            "FilterMate",
            f"Error opening settings: {str(e)}"
        )
```

## 📚 Ressources

- **Documentation complète** : [docs/CONFIG_SYSTEM.md](docs/CONFIG_SYSTEM.md)
- **Guide de migration** : [docs/CONFIG_MIGRATION.md](docs/CONFIG_MIGRATION.md)
- **Exemples détaillés** : [docs/CONFIG_INTEGRATION_EXAMPLES.py](docs/CONFIG_INTEGRATION_EXAMPLES.py)
- **Vue d'ensemble** : [docs/CONFIG_OVERVIEW.md](docs/CONFIG_OVERVIEW.md)

## 🆘 Besoin d'aide ?

```python
# Vérifier si les modules sont disponibles
from modules.config_helpers import METADATA_AVAILABLE

if not METADATA_AVAILABLE:
    print("⚠️ Config metadata module not available")

# Tester la migration
from modules.config_migration import ConfigMigration

migrator = ConfigMigration()
version = migrator.detect_version(config_data)
print(f"Config version: {version}")

# Lister les backups
backups = migrator.list_backups()
print(f"Available backups: {len(backups)}")
```

## 🎉 Vous avez terminé !

Le système est maintenant intégré. Les utilisateurs bénéficient de :
- ✅ Migration automatique transparente
- ✅ Interface de configuration intuitive
- ✅ Validation automatique des valeurs
- ✅ Backups automatiques

---

**Temps d'intégration** : 5 minutes  
**Bénéfices** : Énormes ! 🚀
