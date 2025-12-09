# Configuration JSON - Analyse et Améliorations

## Analyse de la configuration actuelle

### Problèmes identifiés

#### 1. Champs qui devraient être des choix (ChoicesType)

**UI_PROFILE** (actuellement: texte libre)
```json
"UI_PROFILE": "auto"
```
**Devrait être:**
```json
"UI_PROFILE": {
    "value": "auto",
    "choices": ["auto", "compact", "normal"]
}
```

**ACTIVE_THEME** (actuellement: texte libre)
```json
"ACTIVE_THEME": "auto"
```
**Devrait être:**
```json
"ACTIVE_THEME": {
    "value": "auto",
    "choices": ["auto", "default", "dark", "light"]
}
```

**THEME_SOURCE** (actuellement: texte libre)
```json
"THEME_SOURCE": "config"
```
**Devrait être:**
```json
"THEME_SOURCE": {
    "value": "config",
    "choices": ["config", "qgis", "system"]
}
```

**STYLES_TO_EXPORT** (actuellement: texte libre)
```json
"STYLES_TO_EXPORT": "QML"
```
**Devrait être:**
```json
"STYLES_TO_EXPORT": {
    "value": "QML",
    "choices": ["QML", "SLD", "None"]
}
```

**DATATYPE_TO_EXPORT** (actuellement: texte libre)
```json
"DATATYPE_TO_EXPORT": "GPKG"
```
**Devrait être:**
```json
"DATATYPE_TO_EXPORT": {
    "value": "GPKG",
    "choices": ["GPKG", "SHP", "GEOJSON", "KML", "DXF", "CSV"]
}
```

#### 2. Nommage incohérent

**Incohérence dans les préfixes:**
- `HAS_LAYERS_TO_EXPORT` vs `LAYERS_TO_EXPORT`
- `HAS_PROJECTION_TO_EXPORT` vs `PROJECTION_TO_EXPORT`

**Suggestion:** 
- Utiliser un pattern cohérent : `ENABLED_*` + nom du paramètre
- Exemple : `LAYERS_EXPORT_ENABLED` + `LAYERS_EXPORT_LIST`

**Redondance:**
- `UI_PROFILE` + `UI_PROFILE_OPTIONS` → fusionner dans `UI_PROFILE` avec metadata
- Sections dupliquées : `EXPORTING` et `EXPORT` dans `CURRENT_PROJECT`

#### 3. Structure désorganisée

**Options métadata mélangées avec valeurs:**
```json
"UI_PROFILE": "auto",
"UI_PROFILE_OPTIONS": {
    "description": "...",
    "available_profiles": ["auto", "compact", "normal"],
    ...
}
```

**Suggestion:** Les métadonnées devraient être séparées ou intégrées au type ChoicesType

#### 4. Types de données incorrects

**Booléens représentés comme strings (dans certaines parties du code):**
- À vérifier dans le code pour assurer la cohérence

**Nombres représentés comme strings:**
- Les seuils et dimensions devraient être des nombres, pas des strings

## Proposition de restructuration

### Structure proposée

```json
{
    "APP": {
        "UI": {
            "profile": {
                "value": "auto",
                "choices": ["auto", "compact", "normal"],
                "_meta": {
                    "description": "UI display mode",
                    "auto_thresholds": {
                        "width": 1920,
                        "height": 1080
                    }
                }
            },
            "theme": {
                "active": {
                    "value": "auto",
                    "choices": ["auto", "default", "dark", "light"]
                },
                "source": {
                    "value": "config",
                    "choices": ["config", "qgis", "system"]
                },
                "definitions": {
                    "default": { ... },
                    "dark": { ... },
                    "light": { ... }
                }
            },
            "buttons": {
                "style": { ... },
                "icon_sizes": {
                    "action": 25,
                    "standard": 20
                },
                "icons": {
                    "action": { ... },
                    "exploring": { ... },
                    "filtering": { ... },
                    "exporting": { ... }
                }
            }
        },
        "OPTIONS": {
            "github_page": "...",
            "github_repository": "...",
            "qgis_plugin_repository": "...",
            "sqlite_path": "...",
            "fresh_reload": false
        }
    },
    "PROJECT": {
        "metadata": {
            "id": "",
            "path": "",
            "sqlite_path": ""
        },
        "layers": {
            "link_legend_to_current": true,
            "properties_count": 35,
            "feature_limit": 10000
        },
        "postgresql": {
            "enabled": false,
            "active_connection": ""
        },
        "export": {
            "layers": {
                "enabled": false,
                "selected": []
            },
            "projection": {
                "enabled": false,
                "epsg": "EPSG:31370"
            },
            "styles": {
                "enabled": false,
                "format": {
                    "value": "QML",
                    "choices": ["QML", "SLD", "None"]
                }
            },
            "format": {
                "enabled": false,
                "type": {
                    "value": "GPKG",
                    "choices": ["GPKG", "SHP", "GEOJSON", "KML", "DXF", "CSV"]
                }
            },
            "output": {
                "folder": {
                    "enabled": false,
                    "path": ""
                },
                "zip": {
                    "enabled": false,
                    "name": ""
                }
            }
        }
    }
}
```

### Avantages de cette structure

1. **Hiérarchie claire**: UI, OPTIONS, PROJECT
2. **Nommage cohérent**: snake_case, pas de préfixe HAS_
3. **Types appropriés**: Utilisation de ChoicesType pour les énumérations
4. **Métadonnées séparées**: Préfixe `_meta` pour la documentation
5. **Groupement logique**: Paramètres liés regroupés ensemble
6. **Pas de duplication**: Une seule section export par projet

## Mapping ancien → nouveau

| Ancien chemin | Nouveau chemin |
|--------------|----------------|
| `APP.DOCKWIDGET.UI_PROFILE` | `APP.UI.profile` |
| `APP.DOCKWIDGET.UI_PROFILE_OPTIONS` | `APP.UI.profile._meta` |
| `APP.DOCKWIDGET.COLORS.ACTIVE_THEME` | `APP.UI.theme.active` |
| `APP.DOCKWIDGET.COLORS.THEME_SOURCE` | `APP.UI.theme.source` |
| `APP.DOCKWIDGET.COLORS.THEMES` | `APP.UI.theme.definitions` |
| `APP.DOCKWIDGET.PushButton` | `APP.UI.buttons` |
| `APP.OPTIONS.GITHUB_PAGE` | `APP.OPTIONS.github_page` |
| `CURRENT_PROJECT.OPTIONS` | `PROJECT.metadata` + `PROJECT.layers` + `PROJECT.postgresql` |
| `CURRENT_PROJECT.EXPORTING` / `EXPORT` | `PROJECT.export` (fusionné) |

## Migration

### Étape 1: Ajouter support ChoicesType

Le code existant dans `data_changed_configuration_model()` doit être adapté pour gérer les ChoicesType:

```python
def data_changed_configuration_model(self, input_data=None):
    if self.widgets_initialized is True:
        # ... code existant ...
        
        # Handle UI_PROFILE changes (now with ChoicesType)
        if 'profile' in items_keys_values_path or 'UI_PROFILE' in items_keys_values_path:
            # Get value from ChoicesType dict
            value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
            value_data = value_item.data(QtCore.Qt.UserRole)
            
            if isinstance(value_data, dict) and 'value' in value_data:
                new_profile_value = value_data['value']
            else:
                # Fallback pour l'ancien format
                new_profile_value = value_item.data(QtCore.Qt.DisplayRole)
            
            # ... rest of logic
```

### Étape 2: Créer un script de migration

```python
# migrate_config.py
import json
import os

def migrate_config_v1_to_v2(old_config):
    """Migrate configuration from v1 to v2 structure"""
    new_config = {
        "APP": {
            "UI": {
                "profile": {
                    "value": old_config["APP"]["DOCKWIDGET"].get("UI_PROFILE", "auto"),
                    "choices": ["auto", "compact", "normal"]
                },
                # ... rest of migration
            }
        }
    }
    return new_config
```

### Étape 3: Rétro-compatibilité

Ajouter une fonction de détection de version:

```python
def get_config_version(config):
    """Detect config version"""
    if "APP" in config and "DOCKWIDGET" in config["APP"]:
        return 1  # Old structure
    elif "APP" in config and "UI" in config["APP"]:
        return 2  # New structure
    return 0  # Unknown

def load_config_with_migration(config_path):
    """Load config and migrate if necessary"""
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    version = get_config_version(config)
    if version == 1:
        logger.info("Migrating config from v1 to v2")
        config = migrate_config_v1_to_v2(config)
        # Backup old config
        backup_path = config_path + '.v1.backup'
        shutil.copy(config_path, backup_path)
        # Save new config
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
    
    return config
```

## Priorités d'implémentation

### Phase 1: Conversion des types (PRIORITAIRE)
- [ ] Convertir `UI_PROFILE` en ChoicesType
- [ ] Convertir `ACTIVE_THEME` en ChoicesType
- [ ] Convertir `THEME_SOURCE` en ChoicesType
- [ ] Convertir `STYLES_TO_EXPORT` en ChoicesType
- [ ] Convertir `DATATYPE_TO_EXPORT` en ChoicesType
- [ ] Adapter `data_changed_configuration_model()` pour ChoicesType

### Phase 2: Harmonisation des noms
- [ ] Renommer les clés en snake_case
- [ ] Supprimer les préfixes `HAS_` redondants
- [ ] Renommer `ICONS_SIZES` → `icon_sizes`

### Phase 3: Restructuration complète
- [ ] Créer nouvelle structure proposée
- [ ] Implémenter script de migration
- [ ] Tester la rétro-compatibilité
- [ ] Mettre à jour la documentation

### Phase 4: Nettoyage
- [ ] Supprimer sections dupliquées
- [ ] Fusionner métadonnées
- [ ] Validation du schéma JSON

## Tests à ajouter

```python
# tests/test_config_structure.py

def test_ui_profile_is_choices_type():
    """Test that UI_PROFILE uses ChoicesType"""
    config = load_config()
    ui_profile = config['APP']['UI']['profile']
    assert isinstance(ui_profile, dict)
    assert 'value' in ui_profile
    assert 'choices' in ui_profile
    assert ui_profile['value'] in ui_profile['choices']

def test_theme_active_is_choices_type():
    """Test that ACTIVE_THEME uses ChoicesType"""
    # Similar test

def test_export_formats_are_choices_type():
    """Test that export formats use ChoicesType"""
    # Similar test

def test_config_migration_v1_to_v2():
    """Test configuration migration"""
    old_config = load_fixture('config_v1.json')
    new_config = migrate_config_v1_to_v2(old_config)
    assert get_config_version(new_config) == 2
```

## Impact sur le code existant

### Fichiers à modifier

1. **filter_mate_dockwidget.py**
   - `data_changed_configuration_model()`: Gérer ChoicesType
   - `reload_configuration_model()`: Support migration
   - `manage_configuration_model()`: Validation

2. **modules/ui_config.py**
   - Lecture de `UI.profile` au lieu de `DOCKWIDGET.UI_PROFILE`

3. **filter_mate_app.py**
   - Mise à jour des chemins d'accès config

4. **config/config.py**
   - Nouvelles constantes pour chemins config

### Exemple de modification

**Avant:**
```python
profile_value = self.CONFIG_DATA["APP"]["DOCKWIDGET"]["UI_PROFILE"]
```

**Après (avec rétro-compatibilité):**
```python
# Try new structure first
try:
    profile_data = self.CONFIG_DATA["APP"]["UI"]["profile"]
    if isinstance(profile_data, dict) and 'value' in profile_data:
        profile_value = profile_data['value']
    else:
        profile_value = profile_data
except KeyError:
    # Fallback to old structure
    profile_value = self.CONFIG_DATA["APP"]["DOCKWIDGET"]["UI_PROFILE"]
```

---

**Date de création**: 7 décembre 2025  
**Statut**: Proposition - En attente de validation  
**Auteur**: FilterMate Development Team
