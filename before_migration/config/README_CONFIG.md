# Configuration System - Quick Start

## 📋 Vue d'ensemble

Système de configuration amélioré pour FilterMate avec :
- ✨ **Métadonnées** pour chaque paramètre (description, type de widget, validation)
- 🎨 **Widgets auto-générés** (checkbox, combobox, spinbox, etc.)
- ✅ **Validation automatique** des valeurs
- 📚 **Documentation** générée automatiquement

## 🚀 Démarrage rapide

### 1. Lire les métadonnées d'un paramètre

```python
from modules.config_metadata import get_config_metadata

metadata = get_config_metadata()
info = metadata.get_metadata('app.ui.profile')

print(info['description'])      # Description complète
print(info['widget_type'])      # Type de widget recommandé
print(info['default'])          # Valeur par défaut
```

### 2. Utiliser les helpers

```python
from modules.config_helpers import (
    get_widget_type_for_config,
    get_config_description,
    validate_config_value_with_metadata
)

# Obtenir le type de widget
widget = get_widget_type_for_config('app.auto_activate')  # 'checkbox'

# Valider une valeur
valid, error = validate_config_value_with_metadata('app.ui.profile', 'invalid')
if not valid:
    print(error)  # "Value must be one of: auto, compact, normal"
```

### 3. Créer une interface de configuration

```python
from modules.config_editor_widget import SimpleConfigDialog

# Ouvrir le dialog de configuration
dialog = SimpleConfigDialog(config_data)
dialog.show()

# Écouter les changements
dialog.editor.config_changed.connect(
    lambda path, value: print(f"{path} = {value}")
)
```

## 📁 Fichiers créés

| Fichier | Description |
|---------|-------------|
| **config/config_schema.json** | Schéma avec métadonnées pour tous les paramètres |
| **modules/config_metadata.py** | Module de gestion des métadonnées |
| **modules/config_helpers.py** | Helpers améliorés avec support métadonnées |
| **modules/config_editor_widget.py** | Widget d'édition auto-généré |
| **docs/CONFIG_SYSTEM.md** | Documentation complète |
| **docs/CONFIG_INTEGRATION_EXAMPLES.py** | Exemples d'intégration |
| **tools/demo_config_system.py** | Script de démonstration |

## 🎯 Types de widgets supportés

| Widget | Usage | Exemple |
|--------|-------|---------|
| **checkbox** | Booléens | Auto-activate plugin |
| **combobox** | Choix multiples | Theme selection |
| **textbox** | Texte libre | File paths |
| **spinbox** | Nombres entiers | Icon size, limits |
| **colorpicker** | Couleurs | Button colors |

## 📖 Documentation complète

- **[CONFIG_SYSTEM.md](CONFIG_SYSTEM.md)** - Guide complet du système
- **[CONFIG_INTEGRATION_EXAMPLES.py](CONFIG_INTEGRATION_EXAMPLES.py)** - Exemples d'intégration
- **[config_schema.json](../config/config_schema.json)** - Schéma complet

## 🧪 Tester le système

```bash
# Lancer le script de démonstration
cd /path/to/filter_mate
python3 tools/demo_config_system.py
```

## ✨ Avantages

### Pour les développeurs
- 🔧 Auto-documentation du code
- ✅ Validation automatique
- 🛠️ Maintenance simplifiée
- 🔄 Type-safety améliorée

### Pour les utilisateurs
- 🎨 Interface intuitive
- 📝 Descriptions claires
- ⚡ Validation immédiate
- 💡 Aide contextuelle

### Pour l'interface
- 🤖 Génération automatique
- 🎯 Cohérence garantie
- 📈 Extensibilité facile
- 🔌 Intégration simple

## 🔨 Ajouter un nouveau paramètre

1. **Ajouter au schéma** (`config/config_schema.json`) :
```json
{
  "app": {
    "mon_parametre": {
      "description": "Description claire",
      "widget_type": "checkbox",
      "data_type": "boolean",
      "validation": {"required": true},
      "default": true,
      "user_friendly_label": "Mon Paramètre"
    }
  }
}
```

2. **Créer un helper** (optionnel mais recommandé) :
```python
def get_mon_parametre(config_data: dict) -> bool:
    return get_config_value(config_data, "app", "mon_parametre")
```

3. **Utiliser dans le code** :
```python
if get_mon_parametre(self.config_data):
    # Faire quelque chose
    pass
```

**C'est tout !** Le widget se génère automatiquement. ✨

## 🔗 Intégration dans l'UI

### Bouton de configuration
```python
settings_btn = QPushButton("Settings")
settings_btn.clicked.connect(self.open_config_dialog)

def open_config_dialog(self):
    from modules.config_editor_widget import SimpleConfigDialog
    dialog = SimpleConfigDialog(self.config_data, self)
    dialog.show()
```

### Onglet de configuration
```python
from modules.config_editor_widget import ConfigEditorWidget

config_widget = ConfigEditorWidget(self.config_data)
tab_widget.addTab(config_widget, "Settings")
```

Voir [CONFIG_INTEGRATION_EXAMPLES.py](CONFIG_INTEGRATION_EXAMPLES.py) pour plus d'exemples.

## 📊 Structure du schéma

```json
{
  "parameter_path": {
    "description": "User-friendly description",
    "widget_type": "combobox|checkbox|textbox|spinbox|colorpicker",
    "data_type": "boolean|string|integer",
    "validation": {
      "required": true,
      "allowed_values": ["option1", "option2"],
      "min": 0,
      "max": 100,
      "pattern": "^regex$"
    },
    "default": "default_value",
    "user_friendly_label": "Display Label"
  }
}
```

## 🎓 Exemples

### Exemple 1: Checkbox
```json
{
  "app": {
    "auto_activate": {
      "description": "Auto-open plugin on project load",
      "widget_type": "checkbox",
      "data_type": "boolean",
      "default": false
    }
  }
}
```

### Exemple 2: Combobox
```json
{
  "app": {
    "ui": {
      "theme": {
        "active": {
          "description": "Color theme selection",
          "widget_type": "combobox",
          "data_type": "string",
          "validation": {
            "allowed_values": ["auto", "dark", "light"]
          },
          "default": "auto"
        }
      }
    }
  }
}
```

### Exemple 3: Spinbox
```json
{
  "app": {
    "buttons": {
      "icon_sizes": {
        "action": {
          "description": "Icon size for action buttons",
          "widget_type": "spinbox",
          "data_type": "integer",
          "validation": {
            "min": 16,
            "max": 64
          },
          "default": 25
        }
      }
    }
  }
}
```

## 🛠️ Outils disponibles

### 1. Script de démonstration
```bash
python3 tools/demo_config_system.py
```
Montre toutes les fonctionnalités du système.

### 2. Export documentation
```python
from modules.config_metadata import get_config_metadata

metadata = get_config_metadata()
markdown = metadata.export_schema_to_markdown("CONFIG_REFERENCE.md")
```

### 3. Validation
```python
from modules.config_helpers import validate_config_value_with_metadata

valid, error = validate_config_value_with_metadata('app.ui.profile', 'compact')
```

## 🔍 Dépannage

### Métadonnées non disponibles
```python
from modules.config_helpers import METADATA_AVAILABLE

if not METADATA_AVAILABLE:
    print("Module config_metadata not imported correctly")
```

### Paramètre non trouvé
```python
from modules.config_metadata import get_config_metadata

metadata = get_config_metadata()
info = metadata.get_metadata('app.mon.param')
if info is None:
    print("Parameter not in schema!")
```

## 📞 Support

- Documentation complète : [CONFIG_SYSTEM.md](CONFIG_SYSTEM.md)
- Exemples d'intégration : [CONFIG_INTEGRATION_EXAMPLES.py](CONFIG_INTEGRATION_EXAMPLES.py)
- Schéma : [config_schema.json](../config/config_schema.json)

## 🎉 Migration

Le système est **rétro-compatible** :
- ✅ Fonctionne avec l'ancienne structure config v1
- ✅ Helpers supportent v1 et v2
- ✅ Migration progressive possible

## 📝 TODO

- [ ] Intégrer le widget de configuration dans l'interface principale
- [ ] Ajouter icône "Settings" dans `icons/`
- [ ] Créer tests unitaires pour validation
- [ ] Migrer progressivement vers structure v2
- [ ] Ajouter import/export de configuration

---

**Auteur** : Équipe FilterMate  
**Date** : 17 décembre 2025  
**Version** : 2.0
