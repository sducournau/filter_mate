# FilterMate Configuration System v2.0

## Overview

La configuration de FilterMate a été restructurée pour offrir :

1. **Structure hiérarchique claire** - Sections logiques bien définies
2. **Intégration qt_json_view** - Paramètres de thème et d'affichage harmonisés
3. **Feature toggles** - Possibilité d'activer/désactiver des fonctionnalités
4. **Typage des valeurs** - Validation automatique des paramètres
5. **Migration automatique** - Passage transparent de v1 à v2

## Structure du fichier config.json (v2)

```
config.v2.json
├── GENERAL           # Langue, feedback, chemins
├── FEATURES          # Activation/désactivation des fonctionnalités
├── UI                # Interface utilisateur (thème, positions, tailles)
├── JSON_VIEW         # Paramètres du visualiseur de configuration
├── LAYERS            # Gestion des couches
├── EXPORT            # Paramètres d'export par défaut
├── BACKEND           # Préférences de backend (PostgreSQL, Spatialite, OGR)
├── ADVANCED          # Options avancées
├── LINKS             # URLs (GitHub, documentation)
├── THEMES            # Définitions des thèmes couleur
└── RUNTIME           # État runtime (non éditable par l'utilisateur)
```

## Sections détaillées

### GENERAL

```json
{
    "LANGUAGE": {
        "type": "choices",
        "choices": ["auto", "en", "fr", "pt", "es", "it", "de", "nl"],
        "value": "auto"
    },
    "FEEDBACK_LEVEL": {
        "type": "choices",
        "choices": ["minimal", "normal", "verbose"],
        "value": "normal"
    },
    "APP_SQLITE_PATH": {
        "type": "filepath",
        "value": ""
    }
}
```

### FEATURES (Nouveau)

Permet d'activer/désactiver des fonctionnalités spécifiques :

```json
{
    "ENABLE_UNDO_REDO": { "type": "boolean", "value": true },
    "ENABLE_FILTER_HISTORY": { "type": "boolean", "value": true },
    "ENABLE_EXPORT": { "type": "boolean", "value": true },
    "ENABLE_LAYER_LINKING": { "type": "boolean", "value": true },
    "ENABLE_GEOMETRIC_PREDICATES": { "type": "boolean", "value": true },
    "ENABLE_BUFFER_FILTER": { "type": "boolean", "value": true },
    "ENABLE_ADVANCED_CONFIG": { "type": "boolean", "value": true },
    "AUTO_CURRENT_LAYER": { "type": "boolean", "value": false }
}
```

### JSON_VIEW (Nouveau)

Configuration du visualiseur JSON (qt_json_view) :

```json
{
    "THEME": {
        "type": "choices",
        "choices": ["auto", "default", "monokai", "solarized_light", 
                   "solarized_dark", "nord", "dracula", "one_dark", "gruvbox"],
        "value": "auto"
    },
    "FONT_SIZE": {
        "type": "range",
        "min": 8,
        "max": 16,
        "value": 9
    },
    "SHOW_ALTERNATING_ROWS": { "type": "boolean", "value": true },
    "EDITABLE_KEYS": { "type": "boolean", "value": true },
    "EDITABLE_VALUES": { "type": "boolean", "value": true },
    "COLUMN_WIDTH_KEY": {
        "type": "range",
        "min": 100,
        "max": 300,
        "value": 180
    },
    "COLUMN_WIDTH_VALUE": {
        "type": "range",
        "min": 150,
        "max": 400,
        "value": 240
    }
}
```

### BACKEND (Nouveau)

Préférences de traitement :

```json
{
    "PREFERRED_BACKEND": {
        "type": "choices",
        "choices": ["auto", "postgresql", "spatialite", "ogr"],
        "value": "auto"
    },
    "USE_MATERIALIZED_VIEWS": { "type": "boolean", "value": true },
    "SPATIALITE_TEMP_TABLES": { "type": "boolean", "value": true },
    "CONNECTION_TIMEOUT": {
        "type": "range",
        "min": 5,
        "max": 120,
        "value": 30
    }
}
```

## Types de valeurs supportés

| Type | Description | Propriétés |
|------|-------------|------------|
| `boolean` | Vrai/Faux | `value` |
| `string` | Texte libre | `value` |
| `choices` | Liste de choix | `choices`, `value` |
| `range` | Valeur numérique avec bornes | `min`, `max`, `value` |
| `filepath` | Chemin fichier/dossier | `value`, `file_mode` (optionnel) |
| `url` | Lien URL | `value` |

## Utilisation avec ConfigManager

### Initialisation

```python
from config.config_manager import ConfigManager

# Créer le gestionnaire
config = ConfigManager(plugin_dir)

# Accéder aux valeurs
language = config.get('GENERAL', 'LANGUAGE')
icon_size = config.get('UI', 'ICONS', 'SIZE_ACTION')
```

### Vérifier les features

```python
if config.is_feature_enabled('ENABLE_UNDO_REDO'):
    # Initialiser undo/redo
    pass

# Obtenir toutes les features
features = config.get_enabled_features()
```

### Intégration JSON View

```python
from modules.qt_json_view import JsonView, JsonModel

# Obtenir les settings pour JSON View
settings = config.get_json_view_settings()

# Créer la vue avec les settings
json_view = JsonView(model, settings=settings)

# Ou appliquer après création
json_view.apply_config_settings(config)
```

### Synchronisation des thèmes

```python
# Le thème JSON View peut être synchronisé avec le thème UI
json_theme = config.sync_json_view_with_ui_theme()
json_view.set_theme(json_theme)
```

## Migration v1 → v2

La migration est automatique avec **réinitialisation aux valeurs par défaut** :

1. Au chargement, `ConfigManager` cherche d'abord `config.v2.json`
2. Si absent, il détecte `config.json` (v1) comme ancienne configuration
3. **Réinitialisation** : La config est réinitialisée aux valeurs par défaut
4. **Préservation** : Certains paramètres utilisateur sont préservés :
   - `GENERAL.LANGUAGE` - Langue choisie par l'utilisateur
   - `GENERAL.APP_SQLITE_PATH` - Chemin de stockage personnalisé
5. **Backup** : L'ancien fichier est sauvegardé avec timestamp (`config.v1_backup_YYYYMMDD_HHMMSS.json`)
6. Le fichier `config.v2.json` est créé avec la nouvelle structure

### Pourquoi réinitialiser ?

- La nouvelle structure v2 est significativement différente
- Évite les problèmes de compatibilité avec des paramètres obsolètes
- Garantit que toutes les nouvelles fonctionnalités ont leurs valeurs par défaut
- Les paramètres essentiels (langue, chemins) sont préservés

### Réinitialisation manuelle

```python
# Réinitialiser avec préservation des paramètres utilisateur
config.reset_to_defaults(preserve_user_settings=True)

# Réinitialisation complète (tout effacer)
config.reset_to_defaults(preserve_user_settings=False)

# Vérifier si une migration a eu lieu
if config.was_migrated_from_v1():
    print("Configuration réinitialisée depuis l'ancienne version")
```

## Harmonisation UI ↔ JSON View

Le système maintient une cohérence entre :

| Thème UI | Thème JSON View recommandé |
|----------|---------------------------|
| `auto` | Détection automatique (dark→dracula, light→default) |
| `dark` | `dracula` ou `monokai` |
| `light` | `solarized_light` ou `default` |
| `default` | `default` |

## Fichiers

| Fichier | Description |
|---------|-------------|
| `config/config.v2.json` | Configuration utilisateur (nouveau format) |
| `config/config.json` | Ancien format (compatibilité) |
| `config/config_schema.py` | Schéma de configuration avec métadonnées |
| `config/config_manager.py` | Gestionnaire de configuration unifié |

## Bonnes pratiques

1. **Utiliser ConfigManager** pour accéder aux paramètres (pas d'accès direct au JSON)
2. **Vérifier les features** avant d'initialiser des fonctionnalités optionnelles
3. **Sauvegarder les changements** via `config.save()` après modification
4. **Synchroniser les thèmes** quand l'utilisateur change le thème UI
