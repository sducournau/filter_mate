# Configuration System - FilterMate

**Date**: 17 décembre 2025  
**Version**: 2.0

## Vue d'ensemble

Le système de configuration de FilterMate a été amélioré pour être plus **user-friendly** et **maintenable**. Chaque paramètre de configuration possède désormais :

- 📝 **Description** : Explication claire du paramètre
- 🎨 **Type de widget** : Widget approprié (checkbox, combobox, textbox, spinbox, colorpicker)
- ✅ **Validation** : Règles de validation automatiques
- 🏷️ **Label** : Libellé convivial pour l'interface
- 🎯 **Valeur par défaut** : Valeur initiale recommandée

## Architecture

### Fichiers principaux

```
config/
├── config.json              # Configuration utilisateur (valeurs actuelles)
├── config.default.json      # Configuration par défaut (structure v1 legacy)
├── config.v2.example.json   # Exemple structure v2 (future migration)
└── config_schema.json       # ✨ NOUVEAU: Métadonnées et schéma

modules/
├── config_metadata.py       # ✨ NOUVEAU: Gestion des métadonnées
├── config_helpers.py        # ✅ AMÉLIORÉ: Fonctions helper avec métadonnées
└── config_editor_widget.py  # ✨ NOUVEAU: Widget d'édition auto-généré
```

## Utilisation

### 1. Accéder aux métadonnées d'un paramètre

```python
from modules.config_metadata import get_config_metadata

metadata = get_config_metadata()

# Obtenir les métadonnées d'un paramètre
info = metadata.get_metadata('app.ui.profile')
print(info['description'])  # "UI layout profile - auto detects screen size..."
print(info['widget_type'])  # "combobox"
print(info['default'])      # "auto"
```

### 2. Utiliser les helpers améliorés

```python
from modules.config_helpers import (
    get_widget_type_for_config,
    get_config_description,
    get_config_label,
    validate_config_value_with_metadata
)

# Obtenir le type de widget recommandé
widget_type = get_widget_type_for_config('app.auto_activate')
# Retourne: 'checkbox'

# Obtenir la description
desc = get_config_description('app.ui.theme.active')
# Retourne: "Color theme - auto follows QGIS theme..."

# Obtenir le label user-friendly
label = get_config_label('app.ui.feedback.level')
# Retourne: "Feedback Level"

# Valider une valeur
valid, error = validate_config_value_with_metadata('app.ui.profile', 'invalid')
print(valid, error)
# False, "Value must be one of: auto, compact, normal"
```

### 3. Créer un widget de configuration automatiquement

```python
from modules.config_editor_widget import ConfigEditorWidget, SimpleConfigDialog
from config.config import ENV_VARS

# Méthode 1: Widget simple à intégrer
config_widget = ConfigEditorWidget(ENV_VARS["CONFIG_DATA"])
layout.addWidget(config_widget)

# Écouter les changements
config_widget.config_changed.connect(
    lambda path, value: print(f"{path} changed to {value}")
)

# Méthode 2: Dialog standalone
dialog = SimpleConfigDialog(ENV_VARS["CONFIG_DATA"])
dialog.show()
```

## Structure du schéma (config_schema.json)

### Format d'un paramètre

```json
{
  "app": {
    "ui": {
      "profile": {
        "description": "UI layout profile - auto detects screen size, compact for small screens, normal for large screens",
        "widget_type": "combobox",
        "data_type": "string",
        "validation": {
          "required": true,
          "allowed_values": ["auto", "compact", "normal"]
        },
        "default": "auto",
        "user_friendly_label": "UI Profile"
      }
    }
  }
}
```

### Types de widgets supportés

| Widget Type   | Description                          | Cas d'usage                    |
|--------------|--------------------------------------|--------------------------------|
| `checkbox`   | Case à cocher on/off                 | Valeurs booléennes             |
| `combobox`   | Liste déroulante                     | Choix parmi valeurs définies   |
| `textbox`    | Champ de texte                       | Texte libre, chemins           |
| `spinbox`    | Sélecteur numérique                  | Entiers avec min/max           |
| `colorpicker`| Sélecteur de couleur                 | Codes couleur hexadécimaux     |

### Types de données

- `boolean` : true/false
- `string` : Texte
- `integer` : Nombre entier
- `number` : Nombre décimal

### Règles de validation

```json
"validation": {
  "required": true,                           // Obligatoire
  "allowed_values": ["auto", "compact"],      // Liste de valeurs autorisées
  "min": 0,                                   // Minimum (nombres)
  "max": 100,                                 // Maximum (nombres)
  "pattern": "^#[0-9A-Fa-f]{6}$"            // Expression régulière (strings)
}
```

## Exemples complets

### Exemple 1: Paramètre booléen (checkbox)

```json
{
  "app": {
    "auto_activate": {
      "description": "Automatically open FilterMate when loading a project with vector layers",
      "widget_type": "checkbox",
      "data_type": "boolean",
      "validation": {
        "required": true
      },
      "default": false,
      "user_friendly_label": "Auto-activate Plugin"
    }
  }
}
```

**Usage dans le code :**

```python
from modules.config_helpers import get_config_value

auto_activate = get_config_value(config_data, "app", "auto_activate")
if auto_activate:
    # Ouvrir automatiquement le plugin
    pass
```

### Exemple 2: Paramètre avec choix (combobox)

```json
{
  "app": {
    "ui": {
      "theme": {
        "active": {
          "description": "Color theme - auto follows QGIS theme, or force specific theme",
          "widget_type": "combobox",
          "data_type": "string",
          "validation": {
            "required": true,
            "allowed_values": ["auto", "default", "dark", "light"]
          },
          "default": "auto",
          "user_friendly_label": "Active Theme"
        }
      }
    }
  }
}
```

**Génération automatique du widget :**

```python
# Le ConfigEditorWidget crée automatiquement:
# - Un QComboBox
# - Avec les 4 options: auto, default, dark, light
# - Valeur par défaut: "auto"
# - Validation automatique des valeurs
```

### Exemple 3: Paramètre numérique (spinbox)

```json
{
  "app": {
    "project": {
      "feature_count_limit": {
        "description": "Maximum number of features to display at once (performance limit)",
        "widget_type": "spinbox",
        "data_type": "integer",
        "validation": {
          "required": true,
          "min": 1000,
          "max": 1000000
        },
        "default": 100000,
        "user_friendly_label": "Feature Count Limit"
      }
    }
  }
}
```

### Exemple 4: Paramètre couleur (colorpicker)

```json
{
  "app": {
    "buttons": {
      "style": {
        "background_color": {
          "description": "Background color for buttons (hex color code)",
          "widget_type": "colorpicker",
          "data_type": "string",
          "validation": {
            "required": true,
            "pattern": "^#[0-9A-Fa-f]{6}$"
          },
          "default": "#F0F0F0",
          "user_friendly_label": "Button Background Color"
        }
      }
    }
  }
}
```

## Fonctionnalités avancées

### Lister tous les paramètres configurables

```python
from modules.config_helpers import get_all_configurable_paths

paths = get_all_configurable_paths()
# Retourne: ['app.ui.profile', 'app.ui.theme.active', 'app.auto_activate', ...]

for path in paths:
    print(f"{path}: {get_config_label(path)}")
```

### Grouper les paramètres par catégorie

```python
from modules.config_helpers import get_config_groups

groups = get_config_groups()
# Retourne: {'UI': [...], 'Buttons': [...], 'Export': [...], ...}

for category, paths in groups.items():
    print(f"\n{category}:")
    for path in paths:
        print(f"  - {get_config_label(path)}")
```

### Générer la documentation automatiquement

```python
from modules.config_metadata import get_config_metadata

metadata = get_config_metadata()

# Exporter vers Markdown
markdown = metadata.export_schema_to_markdown("docs/CONFIG_REFERENCE.md")
print("Documentation générée!")
```

## Intégration dans l'interface

### Ajouter un menu de configuration

Dans `filter_mate_app.py` ou `filter_mate_dockwidget.py`:

```python
from modules.config_editor_widget import SimpleConfigDialog

def open_config_dialog(self):
    """Ouvrir le dialog de configuration."""
    from config.config import ENV_VARS
    
    dialog = SimpleConfigDialog(ENV_VARS["CONFIG_DATA"], parent=self)
    dialog.show()
```

### Bouton dans l'interface

```python
# Créer un bouton "Settings" ou "Preferences"
settings_btn = QPushButton("Settings")
settings_btn.clicked.connect(self.open_config_dialog)
action_bar_layout.addWidget(settings_btn)
```

## Migration depuis l'ancien système

### Compatibilité v1 / v2

Les helpers dans `config_helpers.py` supportent **les deux structures** :

```python
# Structure v1 (actuelle)
config = {
    "APP": {
        "DOCKWIDGET": {
            "FEEDBACK_LEVEL": {
                "value": "normal",
                "choices": ["minimal", "normal", "verbose"]
            }
        }
    }
}

# Structure v2 (nouvelle)
config = {
    "app": {
        "ui": {
            "feedback": {
                "level": {
                    "value": "normal",
                    "choices": ["minimal", "normal", "verbose"]
                }
            }
        }
    }
}

# Les helpers fonctionnent avec les deux!
from modules.config_helpers import get_feedback_level
level = get_feedback_level(config)  # "normal"
```

### Chemin de migration

1. **Phase actuelle** : Structure v1 + métadonnées dans `config_schema.json`
2. **Phase intermédiaire** : Helpers supportent v1 et v2
3. **Phase future** : Migration complète vers v2

## Avantages du nouveau système

### ✨ Pour les développeurs

- **Auto-documentation** : Chaque paramètre est documenté dans le schéma
- **Validation automatique** : Plus d'erreurs de configuration invalides
- **Type-safety** : Types de données explicites
- **Maintenance facilitée** : Un seul endroit pour gérer les métadonnées

### 🎨 Pour les utilisateurs

- **Interface intuitive** : Widgets appropriés pour chaque type de paramètre
- **Labels clairs** : Descriptions compréhensibles
- **Validation immédiate** : Retour instantané sur les valeurs invalides
- **Aide contextuelle** : Tooltips avec descriptions complètes

### 🔧 Pour l'interface

- **Génération automatique** : Plus besoin de coder manuellement les formulaires
- **Cohérence** : Interface uniforme pour tous les paramètres
- **Extensibilité** : Ajouter un paramètre = ajouter une entrée au schéma

## Ajouter un nouveau paramètre

### 1. Ajouter au schéma (config_schema.json)

```json
{
  "app": {
    "performance": {
      "cache_query_results": {
        "description": "Cache query results to improve response time",
        "widget_type": "checkbox",
        "data_type": "boolean",
        "validation": {
          "required": true
        },
        "default": true,
        "user_friendly_label": "Cache Query Results"
      }
    }
  }
}
```

### 2. Ajouter à la configuration par défaut (optionnel)

```json
// config/config.default.json
{
  "APP": {
    "PERFORMANCE": {
      "CACHE_QUERY_RESULTS": {
        "value": true
      }
    }
  }
}
```

### 3. Créer un helper (optionnel mais recommandé)

```python
# modules/config_helpers.py

def get_cache_query_results(config_data: dict) -> bool:
    """Get cache query results setting."""
    return get_config_with_fallback(
        config_data,
        ("app", "performance", "cache_query_results"),
        ("APP", "PERFORMANCE", "CACHE_QUERY_RESULTS"),
        default=True
    )
```

### 4. Utiliser dans le code

```python
from modules.config_helpers import get_cache_query_results

if get_cache_query_results(self.config_data):
    # Utiliser le cache
    pass
```

**C'est tout !** Le widget de configuration affichera automatiquement le nouveau paramètre.

## Bonnes pratiques

### ✅ DO

- Toujours définir un `default` dans le schéma
- Utiliser des descriptions claires et concises
- Choisir le widget approprié pour le type de donnée
- Valider les entrées utilisateur
- Utiliser les helpers plutôt que l'accès direct

### ❌ DON'T

- Ne pas accéder directement à `config_data["APP"]["DOCKWIDGET"]...`
- Ne pas oublier de documenter un nouveau paramètre
- Ne pas utiliser de valeurs magiques dans le code
- Ne pas dupliquer la validation (le schéma suffit)

## Dépannage

### Métadonnées non disponibles

```python
from modules.config_helpers import METADATA_AVAILABLE

if not METADATA_AVAILABLE:
    print("Metadata module not available!")
    # Fallback vers comportement par défaut
```

### Schéma non trouvé

```bash
# Vérifier l'emplacement du fichier
ls -la config/config_schema.json

# Vérifier les permissions
chmod 644 config/config_schema.json
```

### Widget ne s'affiche pas

```python
# Vérifier si le paramètre est dans le schéma
from modules.config_metadata import get_config_metadata

metadata = get_config_metadata()
info = metadata.get_metadata('app.mon.parametre')
if info is None:
    print("Paramètre non trouvé dans le schéma!")
```

## Ressources

- **Schéma complet** : [config/config_schema.json](../config/config_schema.json)
- **Exemples de configuration** : [config/config.v2.example.json](../config/config.v2.example.json)
- **Proposition d'harmonisation** : [docs/CONFIG_HARMONIZATION_PROPOSAL.md](CONFIG_HARMONIZATION_PROPOSAL.md)
- **Résumé de l'harmonisation** : [docs/CONFIG_HARMONIZATION_SUMMARY.md](CONFIG_HARMONIZATION_SUMMARY.md)

## Contribution

Pour améliorer le système de configuration :

1. Ajouter les métadonnées dans `config_schema.json`
2. Créer des helpers dans `config_helpers.py`
3. Mettre à jour cette documentation
4. Ajouter des tests si nécessaire

---

**Maintainers** : Équipe FilterMate  
**Dernière mise à jour** : 17 décembre 2025
