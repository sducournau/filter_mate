# Proposition d'Harmonisation de la Configuration FilterMate

**Date**: 15 décembre 2025  
**Objectif**: Simplifier et harmoniser la structure de configuration sans introduire de régression

## 1. Analyse de l'existant

### 1.1 Problèmes identifiés

#### Incohérences structurelles
- **Format mixte**: Certaines valeurs utilisent `{"value": "x", "choices": [...]}` (ChoicesType) et d'autres sont directes
- **Profondeur excessive**: Chemins comme `APP.DOCKWIDGET.COLORS.ACTIVE_THEME` sont verbeux
- **Métadonnées non utilisées**: Les clés `_*_META` occupent de l'espace mais ne sont pas exploitées programmatiquement
- **Duplication**: Les thèmes sont définis à deux endroits (`THEMES` et `COLORS` au même niveau)

#### Accès à la configuration
- **86 accès directs** à `CONFIG_DATA` trouvés dans la codebase
- Accès imbriqués fragiles : `CONFIG_DATA["APP"]["DOCKWIDGET"]["COLORS"]["FONT"][0]`
- Peu d'utilisation des helpers existants dans `config_helpers.py`
- Risque élevé de `KeyError` en cas de restructuration

#### Compatibilité JsonView
- Le widget `qt_json_view` affiche toute la config en arborescence éditable
- Il nécessite une structure JSON valide et cohérente
- Les clés `_META` encombrent l'affichage sans apporter de valeur à l'utilisateur
- Le widget supporte l'édition de clés ET de valeurs (risque de casser la structure)

### 1.2 Points positifs existants

✅ **config_helpers.py** fournit déjà une base solide :
- `get_config_value()`: extraction automatique du format ChoicesType
- `set_config_value()`: validation des choix
- Fonctions de commodité pour chemins courants

✅ **Thèmes** : système de thèmes dark/light bien pensé

✅ **Profils UI** : système compact/normal adapté aux petits écrans

## 2. Proposition de nouvelle structure

### 2.1 Principes directeurs

1. **Cohérence**: Toutes les valeurs configurables suivent le même format
2. **Simplicité**: Chemins raccourcis et structure aplatie
3. **Compatibilité**: Transition progressive avec fallback sur ancienne structure
4. **Documentation**: Métadonnées dans un fichier séparé (schema.json)
5. **Sécurité**: Validation stricte via helpers obligatoires

### 2.2 Structure proposée

```json
{
  "app": {
    "ui": {
      "profile": {
        "value": "auto",
        "choices": ["auto", "compact", "normal"]
      },
      "theme": {
        "active": {
          "value": "auto",
          "choices": ["auto", "default", "dark", "light"]
        },
        "source": {
          "value": "config",
          "choices": ["config", "qgis", "system"]
        }
      },
      "action_bar": {
        "position": {
          "value": "left",
          "choices": ["top", "bottom", "left", "right"]
        },
        "vertical_alignment": {
          "value": "top",
          "choices": ["top", "bottom"]
        }
      },
      "feedback": {
        "level": {
          "value": "normal",
          "choices": ["minimal", "normal", "verbose"]
        }
      }
    },
    "buttons": {
      "style": {
        "border_radius": "10px",
        "padding": "10px 10px 10px 10px",
        "background_color": "#F0F0F0"
      },
      "icon_sizes": {
        "action": 25,
        "others": 20
      },
      "icons": {
        "action": {
          "filter": "filter.png",
          "undo": "undo.png",
          "redo": "redo.png",
          "unfilter": "unfilter.png",
          "reset": "reset.png",
          "export": "export.png",
          "about": "icon.png"
        },
        "exploring": {
          "identify": "identify_alt.png",
          "zoom": "zoom.png",
          "select": "select_black.png",
          "track": "track.png",
          "link": "link.png",
          "reset_properties": "save_properties.png"
        },
        "filtering": {
          "auto_layer": "auto_layer_white.png",
          "layers": "layers.png",
          "combine": "add_multi.png",
          "predicates": "geo_predicates.png",
          "buffer_value": "buffer_value.png",
          "buffer_type": "buffer_type.png"
        },
        "exporting": {
          "layers": "layers.png",
          "projection": "projection_black.png",
          "styles": "styles_black.png",
          "datatype": "datatype.png",
          "folder": "folder_black.png",
          "zip": "zip.png"
        }
      }
    },
    "themes": {
      "default": {
        "background": ["#F5F5F5", "#FFFFFF", "#E0E0E0", "#2196F3"],
        "font": ["#212121", "#616161", "#BDBDBD"],
        "accent": {
          "primary": "#1976D2",
          "hover": "#2196F3",
          "pressed": "#0D47A1",
          "light_bg": "#E3F2FD",
          "dark": "#01579B"
        }
      },
      "dark": {
        "background": ["#1E1E1E", "#2D2D30", "#3E3E42", "#007ACC"],
        "font": ["#EFF0F1", "#D0D0D0", "#808080"],
        "accent": {
          "primary": "#007ACC",
          "hover": "#1E90FF",
          "pressed": "#005A9E",
          "light_bg": "#1E3A5F",
          "dark": "#003D66"
        }
      },
      "light": {
        "background": ["#FFFFFF", "#F5F5F5", "#E0E0E0", "#2196F3"],
        "font": ["#000000", "#424242", "#9E9E9E"],
        "accent": {
          "primary": "#2196F3",
          "hover": "#64B5F6",
          "pressed": "#1976D2",
          "light_bg": "#E3F2FD",
          "dark": "#0D47A1"
        }
      }
    },
    "paths": {
      "github_page": "https://sducournau.github.io/filter_mate/",
      "github_repo": "https://github.com/sducournau/filter_mate/",
      "plugin_repo": "https://plugins.qgis.org/plugins/filter_mate/",
      "sqlite_storage": ""
    },
    "flags": {
      "fresh_reload": false
    }
  },
  "project": {
    "meta": {
      "id": "",
      "path": ""
    },
    "layers": {
      "link_legend": true,
      "properties_count": 35,
      "feature_limit": 10000,
      "list": []
    },
    "postgresql": {
      "active_connection": "",
      "is_active": false,
      "sqlite_path": ""
    },
    "export": {
      "layers": {
        "enabled": false,
        "selected": []
      },
      "projection": {
        "enabled": false,
        "epsg": "EPSG:3857"
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
          "choices": ["GPKG", "SHP", "GEOJSON", "KML"]
        }
      },
      "output": {
        "folder": {
          "enabled": false,
          "path": ""
        },
        "zip": {
          "enabled": false,
          "path": ""
        },
        "batch_folder": false,
        "batch_zip": false
      }
    }
  }
}
```

### 2.3 Changements clés

#### Simplifications structurelles
- ❌ `APP.DOCKWIDGET.COLORS` → ✅ `app.themes`
- ❌ `APP.DOCKWIDGET.FEEDBACK_LEVEL` → ✅ `app.ui.feedback.level`
- ❌ `APP.DOCKWIDGET.PushButton` → ✅ `app.buttons`
- ❌ `CURRENT_PROJECT.OPTIONS.LAYERS` → ✅ `project.layers`
- ❌ `CURRENT_PROJECT.EXPORTING` → ✅ `project.export`

#### Normalisation des noms
- Tous les chemins en `snake_case` (minuscules avec underscore)
- Noms de clés cohérents et explicites
- Abandon des préfixes `HAS_*` redondants avec la structure imbriquée

#### Suppression des métadonnées inline
- Les `_*_META` sont déplacées dans un fichier séparé `config/schema.json`
- Cela allège l'affichage dans JsonView
- Permet une validation de schéma plus rigoureuse

## 3. Plan de migration progressive

### 3.1 Phase 1: Extension des helpers (SANS RÉGRESSION)

**Objectif**: Ajouter des helpers pour tous les chemins actuels

```python
# Dans config/config_helpers.py

# === UI Configuration ===

def get_feedback_level(config_data: dict) -> str:
    """Get feedback level (minimal/normal/verbose)."""
    return get_config_with_fallback(
        config_data,
        ("app", "ui", "feedback", "level"),  # New structure
        ("APP", "DOCKWIDGET", "FEEDBACK_LEVEL"),  # Old structure
        default="normal"
    )

def get_ui_action_bar_position(config_data: dict) -> str:
    """Get action bar position (top/bottom/left/right)."""
    return get_config_with_fallback(
        config_data,
        ("app", "ui", "action_bar", "position"),
        ("APP", "DOCKWIDGET", "ACTION_BAR_POSITION"),
        default="left"
    )

def get_ui_action_bar_alignment(config_data: dict) -> str:
    """Get action bar vertical alignment (top/bottom)."""
    return get_config_with_fallback(
        config_data,
        ("app", "ui", "action_bar", "vertical_alignment"),
        ("APP", "DOCKWIDGET", "ACTION_BAR_VERTICAL_ALIGNMENT"),
        default="top"
    )

# === Button Configuration ===

def get_button_icon(config_data: dict, category: str, name: str) -> str:
    """Get button icon filename."""
    # Try new structure
    try:
        return config_data["app"]["buttons"]["icons"][category.lower()][name.lower()]
    except (KeyError, TypeError):
        pass
    
    # Fallback to old structure
    category_map = {
        "action": "ACTION",
        "exploring": "EXPLORING",
        "filtering": "FILTERING",
        "exporting": "EXPORTING"
    }
    old_category = category_map.get(category.lower(), category.upper())
    
    return get_config_value(
        config_data,
        "APP", "DOCKWIDGET", "PushButton", "ICONS", old_category, name.upper(),
        default="icon.png"
    )

def get_button_icon_size(config_data: dict, button_type: str = "action") -> int:
    """Get button icon size."""
    return get_config_with_fallback(
        config_data,
        ("app", "buttons", "icon_sizes", button_type.lower()),
        ("APP", "DOCKWIDGET", "PushButton", "ICONS_SIZES", button_type.upper()),
        default=25 if button_type.lower() == "action" else 20
    )

# === Theme/Color Configuration ===

def get_theme_colors(config_data: dict, theme_name: str = None) -> dict:
    """Get color palette for a theme."""
    if theme_name is None:
        theme_name = get_active_theme(config_data)
    
    # Try new structure
    try:
        return config_data["app"]["themes"][theme_name]
    except (KeyError, TypeError):
        pass
    
    # Fallback to old structure
    return get_config_value(
        config_data,
        "APP", "DOCKWIDGET", "COLORS", "THEMES", theme_name,
        default={}
    )

def get_font_colors(config_data: dict) -> list:
    """Get font colors array [primary, secondary, disabled]."""
    theme_name = get_active_theme(config_data)
    colors = get_theme_colors(config_data, theme_name)
    return colors.get("font", ["#212121", "#616161", "#BDBDBD"])

def get_background_colors(config_data: dict) -> list:
    """Get background colors array."""
    theme_name = get_active_theme(config_data)
    colors = get_theme_colors(config_data, theme_name)
    return colors.get("background", ["#F5F5F5", "#FFFFFF", "#E0E0E0", "#2196F3"])

def get_accent_colors(config_data: dict) -> dict:
    """Get accent colors dict."""
    theme_name = get_active_theme(config_data)
    colors = get_theme_colors(config_data, theme_name)
    return colors.get("accent", {
        "primary": "#1976D2",
        "hover": "#2196F3",
        "pressed": "#0D47A1",
        "light_bg": "#E3F2FD",
        "dark": "#01579B"
    })

# === Project Configuration ===

def get_layer_properties_count(config_data: dict) -> int:
    """Get expected layer properties count."""
    return get_config_with_fallback(
        config_data,
        ("project", "layers", "properties_count"),
        ("CURRENT_PROJECT", "OPTIONS", "LAYERS", "LAYER_PROPERTIES_COUNT"),
        default=35
    )

def set_layer_properties_count(config_data: dict, count: int) -> None:
    """Set layer properties count."""
    try:
        # Try new structure
        if "project" in config_data:
            config_data["project"]["layers"]["properties_count"] = count
            return
    except (KeyError, TypeError):
        pass
    
    # Fallback to old structure
    if "CURRENT_PROJECT" in config_data:
        config_data["CURRENT_PROJECT"]["OPTIONS"]["LAYERS"]["LAYER_PROPERTIES_COUNT"] = count

def get_postgresql_active_connection(config_data: dict) -> str:
    """Get active PostgreSQL connection string."""
    return get_config_with_fallback(
        config_data,
        ("project", "postgresql", "active_connection"),
        ("CURRENT_PROJECT", "OPTIONS", "ACTIVE_POSTGRESQL"),
        default=""
    )

def is_postgresql_active(config_data: dict) -> bool:
    """Check if PostgreSQL is active."""
    return get_config_with_fallback(
        config_data,
        ("project", "postgresql", "is_active"),
        ("CURRENT_PROJECT", "OPTIONS", "IS_ACTIVE_POSTGRESQL"),
        default=False
    )

def set_postgresql_connection(config_data: dict, connection_string: str, is_active: bool) -> None:
    """Set PostgreSQL connection."""
    try:
        # Try new structure
        if "project" in config_data:
            config_data["project"]["postgresql"]["active_connection"] = connection_string
            config_data["project"]["postgresql"]["is_active"] = is_active
            return
    except (KeyError, TypeError):
        pass
    
    # Fallback to old structure
    if "CURRENT_PROJECT" in config_data:
        config_data["CURRENT_PROJECT"]["OPTIONS"]["ACTIVE_POSTGRESQL"] = connection_string
        config_data["CURRENT_PROJECT"]["OPTIONS"]["IS_ACTIVE_POSTGRESQL"] = is_active

# === Export Configuration ===

def get_export_layers_enabled(config_data: dict) -> bool:
    """Check if layers export is enabled."""
    return get_config_with_fallback(
        config_data,
        ("project", "export", "layers", "enabled"),
        ("CURRENT_PROJECT", "EXPORTING", "HAS_LAYERS_TO_EXPORT"),
        default=False
    )

def get_export_layers_list(config_data: dict) -> list:
    """Get list of layers to export."""
    return get_config_with_fallback(
        config_data,
        ("project", "export", "layers", "selected"),
        ("CURRENT_PROJECT", "EXPORTING", "LAYERS_TO_EXPORT"),
        default=[]
    )

def get_export_projection_epsg(config_data: dict) -> str:
    """Get export projection EPSG code."""
    return get_config_with_fallback(
        config_data,
        ("project", "export", "projection", "epsg"),
        ("CURRENT_PROJECT", "EXPORTING", "PROJECTION_TO_EXPORT"),
        default="EPSG:3857"
    )

# === App Paths ===

def get_github_page_url(config_data: dict) -> str:
    """Get GitHub documentation page URL."""
    return get_config_with_fallback(
        config_data,
        ("app", "paths", "github_page"),
        ("APP", "OPTIONS", "GITHUB_PAGE"),
        default="https://sducournau.github.io/filter_mate/"
    )

def get_sqlite_storage_path(config_data: dict) -> str:
    """Get SQLite storage path."""
    return get_config_with_fallback(
        config_data,
        ("app", "paths", "sqlite_storage"),
        ("APP", "OPTIONS", "APP_SQLITE_PATH"),
        default=""
    )

def get_fresh_reload_flag(config_data: dict) -> bool:
    """Get fresh reload flag."""
    return get_config_with_fallback(
        config_data,
        ("app", "flags", "fresh_reload"),
        ("APP", "OPTIONS", "FRESH_RELOAD_FLAG"),
        default=False
    )

def set_fresh_reload_flag(config_data: dict, value: bool) -> None:
    """Set fresh reload flag."""
    try:
        # Try new structure
        if "app" in config_data:
            config_data["app"]["flags"]["fresh_reload"] = value
            return
    except (KeyError, TypeError):
        pass
    
    # Fallback to old structure
    if "APP" in config_data:
        config_data["APP"]["OPTIONS"]["FRESH_RELOAD_FLAG"] = value
```

### 3.2 Phase 2: Migration des accès dans le code (PROGRESSIVE)

**Principe**: Remplacer les accès directs par les helpers, fichier par fichier

**Exemple de migration dans `modules/widgets.py`**:

```python
# AVANT (accès direct)
font_color = self.config_data["APP"]["DOCKWIDGET"]["COLORS"]["FONT"][0]

# APRÈS (avec helper)
from ..config.config_helpers import get_font_colors
font_colors = get_font_colors(self.config_data)
font_color = font_colors[0]
```

**Ordre de migration**:
1. ✅ `modules/widgets.py` (8 accès)
2. ✅ `filter_mate_dockwidget.py` (40+ accès) 
3. ✅ `filter_mate_app.py` (20+ accès)
4. ✅ `modules/ui_styles.py` (3 accès)
5. ✅ `modules/tasks/` (15 accès)

### 3.3 Phase 3: Basculement vers nouvelle structure

**Une fois tous les accès migrés**:

1. Créer `config/config.v2.json` avec la nouvelle structure
2. Créer `config/schema.json` avec les métadonnées et validation
3. Script de migration `migrate_config_v1_to_v2.py`
4. Détection automatique de la version au démarrage
5. Migration transparente pour l'utilisateur

### 3.4 Phase 4: Nettoyage

1. Supprimer les fallbacks vers ancienne structure
2. Simplifier les helpers
3. Documenter la nouvelle structure
4. Mise à jour des tests

## 4. Compatibilité avec JsonView

### 4.1 Améliorations pour JsonView

Le widget `qt_json_view` bénéficiera de :
- **Structure plus claire** : moins de niveaux, chemins plus courts
- **Affichage simplifié** : suppression des clés `_META` encombrantes
- **Édition plus sûre** : les ChoicesType restent visibles et éditables
- **Performance** : JSON moins volumineux à parser

### 4.2 Contraintes à respecter

⚠️ **Le JsonView nécessite** :
- Structure JSON valide (pas de trailing commas, quotes correctes)
- Clés uniques à chaque niveau
- Types cohérents (pas de mélange list/dict pour une même clé)
- Le format ChoicesType doit rester `{"value": "x", "choices": [...]}`

### 4.3 Configuration du JsonView

Le widget est instancié avec :
```python
JsonModel(data=self.CONFIG_DATA, editable_keys=True, editable_values=True)
```

**Risques** :
- ❌ `editable_keys=True` permet de renommer/supprimer des clés → risque de casser la structure
- ✅ Solution : Passer à `editable_keys=False` après migration

**Améliorations possibles** :
- Ajouter validation au niveau du modèle JsonModel
- Créer des delegates spécifiques pour les ChoicesType (dropdown)
- Colorer les clés système en lecture seule

## 5. Plan d'exécution

### Étapes immédiates (sans risque)

1. ✅ **Étendre config_helpers.py** avec tous les helpers nécessaires
   - Durée: 2-3 heures
   - Risque: Aucun (ajout uniquement)
   - Test: Vérifier que les helpers retournent les bonnes valeurs

2. ✅ **Créer config.v2.json** et **schema.json** en parallèle de l'existant
   - Durée: 1-2 heures
   - Risque: Aucun (fichiers séparés)
   - Test: Valider le JSON, vérifier qu'il contient toutes les données

3. ✅ **Créer script de test** pour comparer v1 vs v2
   - Durée: 1 heure
   - Objectif: S'assurer qu'aucune donnée n'est perdue

### Migration progressive (par fichier)

4. ⏳ **Migrer modules/widgets.py** vers helpers
   - Durée: 30 min
   - Test: Vérifier l'affichage des widgets

5. ⏳ **Migrer modules/ui_styles.py** vers helpers
   - Durée: 20 min
   - Test: Vérifier les thèmes dark/light

6. ⏳ **Migrer filter_mate_dockwidget.py** progressivement
   - Durée: 2-3 heures (40+ remplacements)
   - Test: Tester tous les onglets et actions

7. ⏳ **Migrer filter_mate_app.py**
   - Durée: 1-2 heures
   - Test: Tests end-to-end complets

8. ⏳ **Migrer modules/tasks/**
   - Durée: 1 heure
   - Test: Tester filtres PostgreSQL et exports

### Basculement final

9. ⏳ **Script de migration automatique**
   - Détecte version actuelle
   - Migre config.json vers v2
   - Sauvegarde l'ancienne version

10. ⏳ **Tests complets**
    - Tests unitaires sur tous les helpers
    - Tests d'intégration
    - Test avec JsonView

11. ⏳ **Documentation**
    - Guide de migration pour utilisateurs avancés
    - Changelog détaillé
    - Mise à jour README

## 6. Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| JsonView casse après migration | Faible | Élevé | Tester avec config.v2.json avant basculement |
| Perte de données utilisateur | Faible | Critique | Script de backup automatique |
| Régression sur fonctionnalité | Moyen | Élevé | Tests end-to-end complets |
| Performance dégradée | Très faible | Moyen | Benchmarks avant/après |
| Confusion utilisateurs | Moyen | Faible | Documentation claire + migration auto |

## 7. Conclusion

Cette proposition permet de :

✅ **Simplifier** la structure de configuration  
✅ **Harmoniser** les formats et conventions  
✅ **Sécuriser** les accès via helpers obligatoires  
✅ **Améliorer** l'expérience avec JsonView  
✅ **Migrer progressivement** sans régression  

**Prochaine étape recommandée** : Commencer par la Phase 1 (extension des helpers) qui est sans risque et prépare le terrain pour la suite.
