# Configuration FilterMate v2.0 - Guide Rapide pour Développeurs

**Version**: 2.0  
**Date**: 17 décembre 2025  
**Audience**: Développeurs travaillant sur FilterMate

---

## 🚀 TL;DR - Accès Rapide

### Lire un Paramètre

```python
from modules.config_helpers import get_config_value

# ✅ RECOMMANDÉ - Fonctionne v1.0 et v2.0
value = get_config_value(config_data, "APP", "DOCKWIDGET", "LANGUAGE")
```

### Écrire un Paramètre

```python
from modules.config_helpers import set_config_value

# ✅ RECOMMANDÉ - Sûr pour les deux formats
set_config_value(config_data, "fr", "APP", "DOCKWIDGET", "LANGUAGE")
```

### Accès Rétrocompatible (Legacy)

```python
# ✅ OK pour maintenance - Gère les deux formats
value = self.CONFIG_DATA.get('APP', {}).get('DOCKWIDGET', {}).get('LANGUAGE', {})
if isinstance(value, dict):
    actual = value.get('value', 'auto')
else:
    actual = value
```

---

## 📚 Format v2.0

```json
{
  "APP": {
    "DOCKWIDGET": {
      "LANGUAGE": {
        "value": "auto",
        "choices": ["auto", "en", "fr", "de"],
        "description": "Interface language"
      }
    }
  }
}
```

**Clés**:
- `value`: Valeur actuelle
- `choices`: Options disponibles (pour ChoicesType)
- `description`: Texte d'aide utilisateur

---

## 🔄 Où CONFIG_DATA est Disponible

### GlobalFormat

```python
ENV_VARS["CONFIG_DATA"]  # config/config.py
```

### Dans FilterMateApp

```python
self.CONFIG_DATA  # filter_mate_app.py:226
```

### Dans DockWidget et Components UI

```python
self.CONFIG_DATA  # filter_mate_dockwidget.py:170
# Disponible dans tous les components internes
```

---

## 🎯 Cas d'Usage Courants

### 1. Lire un Simple Paramètre

```python
# Configuration:
# "LANGUAGE": {"value": "fr", "choices": [...]}

language = get_config_value(
    self.CONFIG_DATA,
    "APP", "DOCKWIDGET", "LANGUAGE"
)  # → "fr"
```

### 2. Lire avec Fallback

```python
from modules.config_helpers import get_config_with_fallback

# Essaie d'abord nouveau path, puis ancien path
theme = get_config_with_fallback(
    config_data,
    ("APP", "UI", "theme", "active"),      # Path v3.0 futur
    ("APP", "DOCKWIDGET", "COLORS", "ACTIVE_THEME"),  # Path v2.0 actuel
    default="auto"
)
```

### 3. Écrire un Paramètre

```python
# Configuration avant:
# "ACTION_BAR_POSITION": {"value": "top", "choices": ["top", "bottom", "left", "right"]}

set_config_value(
    self.CONFIG_DATA,
    "bottom",
    "APP", "DOCKWIDGET", "ACTION_BAR_POSITION"
)
# Configuration après:
# "ACTION_BAR_POSITION": {"value": "bottom", "choices": [...]}
```

### 4. Vérifier l'Existence

```python
# Sûr:
if "APP" in self.CONFIG_DATA and "DOCKWIDGET" in self.CONFIG_DATA["APP"]:
    # Accédez à CONFIG_DATA["APP"]["DOCKWIDGET"]
    pass
```

### 5. Accès aux Données Projet

```python
# Configuration:
# "CURRENT_PROJECT": { "EXPORTING": {...}, "FILTERING": {...} }

project_config = self.CONFIG_DATA.get("CURRENT_PROJECT", {})
export_settings = project_config.get("EXPORTING", {})
```

---

## 📋 Patterns par Situation

### Situation: Ajouter un Nouveau Paramètre

**Étape 1**: Ajouter dans [config/config.default.json](config/config.default.json)

```json
{
  "APP": {
    "DOCKWIDGET": {
      "MY_NEW_PARAM": {
        "value": "default_value",
        "choices": ["option1", "option2"],
        "description": "Description pour utilisateur"
      }
    }
  }
}
```

**Étape 2**: Lire dans le code

```python
value = get_config_value(
    self.CONFIG_DATA,
    "APP", "DOCKWIDGET", "MY_NEW_PARAM"
)
```

**Étape 3**: Écrire

```python
set_config_value(
    self.CONFIG_DATA,
    "new_value",
    "APP", "DOCKWIDGET", "MY_NEW_PARAM"
)
```

**Étape 4**: Qt JSON View reconnaît automatiquement les choix ✅

---

### Situation: Lire depuis Ancien Code

**Ancien Pattern** (v1.0):
```json
{"APP": {"DOCKWIDGET": {"LANGUAGE": "fr"}}}
```

**Nouveau Pattern** (v2.0):
```json
{"APP": {"DOCKWIDGET": {"LANGUAGE": {"value": "fr", "choices": [...]}}}}
```

**Solution**: `get_config_value()` supporte les deux ✅

```python
# Fonctionne avec v1.0 et v2.0:
language = get_config_value(config_data, "APP", "DOCKWIDGET", "LANGUAGE")
# → "fr" dans les deux cas
```

---

### Situation: Migration Utilisateur

**Automatique** - Aucune action nécessaire!

```python
init_env_vars():
  → ConfigMigration.auto_migrate_if_needed()
    → Si v1.0 détecté: migrate_v1_to_v2()
    → Si obsolète: reset_to_default()
    → Si manquant: copy_default()
```

**User Message** automatique via QgsMessageLog

---

## 🛠️ Déboguer la Configuration

### Voir la Configuration Entière

```python
import json
print(json.dumps(self.CONFIG_DATA, indent=2))
```

### Vérifier un Chemin Spécifique

```python
from modules.config_helpers import get_config_value

value = get_config_value(
    self.CONFIG_DATA,
    "APP", "DOCKWIDGET", "LANGUAGE"
)
print(f"LANGUAGE = {value}")  # Affiche la valeur extraite
```

### Vérifier le Format (v1.0 vs v2.0)

```python
config_item = self.CONFIG_DATA['APP']['DOCKWIDGET']['LANGUAGE']

if isinstance(config_item, dict) and 'value' in config_item:
    print(f"Format v2.0: value={config_item['value']}")
else:
    print(f"Format v1.0 ou raw: {config_item}")
```

### Afficher Métadonnées

```python
from modules.config_metadata_handler import ConfigMetadataHandler

metadata = ConfigMetadataHandler.extract_metadata(
    self.CONFIG_DATA['APP']['DOCKWIDGET']['LANGUAGE']
)
print(f"Metadata: {metadata}")
# → {'type': 'ChoicesType', 'description': '...', 'choices': [...], 'value': '...'}
```

---

## ⚠️ Pièges À Éviter

### ❌ Piège 1: Assumer un Format

```python
# ❌ MAUVAIS - Assume v2.0:
language = config["APP"]["DOCKWIDGET"]["LANGUAGE"]["value"]
# KeyError si v1.0!

# ✅ BON:
language = get_config_value(config, "APP", "DOCKWIDGET", "LANGUAGE")
```

### ❌ Piège 2: Écrire Directement

```python
# ❌ MAUVAIS - Casse le format {value, ...}:
config["APP"]["DOCKWIDGET"]["LANGUAGE"] = "en"
# Perd les metadata!

# ✅ BON:
set_config_value(config, "en", "APP", "DOCKWIDGET", "LANGUAGE")
```

### ❌ Piège 3: Pas de Fallback

```python
# ❌ MAUVAIS - KeyError possible:
theme = config["APP"]["COLORS"]["THEME"]

# ✅ BON:
theme = config.get("APP", {}).get("COLORS", {}).get("THEME", "default")
```

### ❌ Piège 4: Supposer l'Existence

```python
# ❌ MAUVAIS:
if self.CONFIG_DATA["APP"]:  # KeyError si manquant!
    pass

# ✅ BON:
if "APP" in self.CONFIG_DATA:
    pass
```

---

## 📞 Fonctions Clés

### `get_config_value(config, *keys, default=None)`

**Usage**: Lire une valeur avec extraction automatique

```python
value = get_config_value(config, "APP", "DOCKWIDGET", "LANGUAGE")
```

**Retourne**:
- La valeur brute si format simple
- Le champ `"value"` si format `{value, choices}`
- Le `default` si clé manquante

**Fichier**: [modules/config_helpers.py](modules/config_helpers.py#L30)

---

### `set_config_value(config, value, *keys)`

**Usage**: Écrire une valeur en gérant les deux formats

```python
set_config_value(config, "en", "APP", "DOCKWIDGET", "LANGUAGE")
```

**Fait**:
- Crée les clés manquantes
- Met à jour `"value"` si format `{value, ...}`
- Remplace la valeur si format simple

**Fichier**: [modules/config_helpers.py](modules/config_helpers.py#L68)

---

### `get_config_with_fallback(config, path, fallback_path, default=None)`

**Usage**: Lire avec support pour migration future

```python
theme = get_config_with_fallback(
    config,
    ("APP", "UI", "theme"),        # Path v3.0 futur
    ("APP", "DOCKWIDGET", "COLORS", "ACTIVE_THEME"),  # Path v2.0 actuel
    default="auto"
)
```

**Essaie**:
1. D'abord le path principal
2. Si non trouvé: le fallback_path
3. Si rien: le default

**Fichier**: [modules/config_helpers.py](modules/config_helpers.py#L191)

---

### `ConfigMetadataHandler.extract_metadata(config_item)`

**Usage**: Extraire métadonnées pour UI (qt_json_view)

```python
metadata = ConfigMetadataHandler.extract_metadata(
    config["APP"]["DOCKWIDGET"]["LANGUAGE"]
)
# → {'type': 'ChoicesType', 'description': '...', 'choices': [...], 'value': '...'}
```

**Retourne**: Dict avec type, description, choices, valeur

**Fichier**: [modules/config_metadata_handler.py](modules/config_metadata_handler.py)

---

## 📖 Ressources

### Documentation
- [CONFIG_INTEGRATION_ANALYSIS_2025-12-17.md](CONFIG_INTEGRATION_ANALYSIS_2025-12-17.md) - Analyse complète
- [CONFIG_USAGE_CASES_2025-12-17.md](CONFIG_USAGE_CASES_2025-12-17.md) - 47 cas d'usage détaillés
- [INTEGRATION_SUMMARY_2025-12-17.md](INTEGRATION_SUMMARY_2025-12-17.md) - Rapport exécutif

### Code
- [config/config.default.json](config/config.default.json) - Configuration par défaut
- [modules/config_helpers.py](modules/config_helpers.py) - Helper functions
- [modules/config_migration.py](modules/config_migration.py) - Migration logic
- [modules/config_metadata_handler.py](modules/config_metadata_handler.py) - Metadata extraction

---

## ✅ Checklist pour Nouveau Code

- [ ] Utiliser `get_config_value()` pour lire
- [ ] Utiliser `set_config_value()` pour écrire
- [ ] Ajouter paramètre dans `config.default.json`
- [ ] Documenter le chemin config en commentaire
- [ ] Tester avec v1.0 et v2.0 si possible
- [ ] Ajouter fallback pour clés optionnelles
- [ ] Afficher message utilisateur si valeur change

---

## 🎓 Exemples Complets

### Exemple 1: Lire le Thème

```python
from modules.config_helpers import get_config_value
from modules.ui_styles import StyleLoader

def apply_theme(widget, config_data):
    theme = get_config_value(
        config_data,
        "APP", "DOCKWIDGET", "COLORS", "ACTIVE_THEME"
    )
    StyleLoader.set_theme_from_config(widget, config_data, theme)
    print(f"Theme applied: {theme}")
```

### Exemple 2: Permettre à l'Utilisateur de Changer

```python
from modules.config_helpers import set_config_value, get_config_value
from qgis.utils import iface

def on_theme_changed(new_theme):
    set_config_value(
        self.CONFIG_DATA,
        new_theme,
        "APP", "DOCKWIDGET", "COLORS", "ACTIVE_THEME"
    )
    iface.messageBar().pushSuccess(
        "FilterMate",
        f"Theme changed to {new_theme}"
    )
```

### Exemple 3: Ajouter un Nouveau Paramètre

```json
// Dans config.default.json:
{
  "APP": {
    "DOCKWIDGET": {
      "MY_FEATURE_ENABLED": {
        "value": true,
        "description": "Enable my awesome feature"
      }
    }
  }
}
```

```python
# Dans votre code:
from modules.config_helpers import get_config_value, set_config_value

def setup_feature(self):
    enabled = get_config_value(
        self.CONFIG_DATA,
        "APP", "DOCKWIDGET", "MY_FEATURE_ENABLED"
    )
    if enabled:
        self.enable_awesome_feature()

def toggle_feature(self, enabled):
    set_config_value(
        self.CONFIG_DATA,
        enabled,
        "APP", "DOCKWIDGET", "MY_FEATURE_ENABLED"
    )
```

---

**Dernière Mise à Jour**: 17 décembre 2025  
**Prochaine Révision**: Avant v2.5
