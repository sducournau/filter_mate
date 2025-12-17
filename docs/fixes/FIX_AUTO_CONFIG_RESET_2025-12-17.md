# Correction: Reset Automatique de la Configuration Obsolète

**Date**: 2025-12-17  
**Type**: Amélioration + Correction  
**Priorité**: Haute  
**Statut**: ✅ Terminé

## Problème

1. Les utilisateurs avec d'anciennes configurations pouvaient rencontrer des erreurs
2. Pas de mécanisme automatique pour détecter et remplacer les configs obsolètes
3. La structure de `config.default.json` n'était pas optimisée pour `qt_json_view` (widgets inconsistants)

## Solution Implémentée

### 1. Optimisation de `config.default.json`

**Fichier**: `config/config.default.json`

**Nouvelle structure améliorée** - Métadonnées intégrées directement:

```json
{
  "_CONFIG_VERSION": "2.0",
  "_CONFIG_META": {
    "description": "FilterMate Configuration File",
    "version": "2.0",
    "last_updated": "2025-12-17",
    "compatible_with": "FilterMate 1.0+"
  },
  "APP": {
    "AUTO_ACTIVATE": {
      "value": false,
      "description": "Auto-activate plugin when a project with vector layers is loaded",
      "applies_to": "Plugin initialization behavior"
    },
    "DOCKWIDGET": {
      "LANGUAGE": {
        "value": "auto",
        "choices": ["auto", "en", "fr", "de", "es", "it", "nl", "pt"],
        "description": "Interface language: 'auto' (use QGIS locale), or force specific language",
        "available_translations": ["en (English)", "fr (Français)", ...]
      }
    }
  }
}
```

**Avantages de cette structure**:
- ✅ **Métadonnées intégrées** - Chaque paramètre contient sa description
- ✅ **Plus logique** - Pas de sections `_*_META` séparées
- ✅ **UX améliorée** - Les descriptions s'affichent en tooltips dans qt_json_view
- ✅ **Facilement extensible** - Ajouter des métadonnées sans fragmenter la structure
- ✅ **Structure cohérente** - Pattern uniforme: `{value, choices, description, ...}`

Ancien pattern (fragmenté):
```json
{
  "LANGUAGE": {
    "value": "auto",
    "choices": ["auto", "en", "fr", ...]
  },
  "_LANGUAGE_META": {
    "description": "...",
    "available_translations": [...]
  }
}
```

Nouveau pattern (intégré):
```json
{
  "LANGUAGE": {
    "value": "auto",
    "choices": ["auto", "en", "fr", ...],
    "description": "...",
    "available_translations": [...]
  }
}
```

**Changements clés apportés**:
- ✅ Suppression de toutes les sections `_*_META`
- ✅ Intégration directe des métadonnées dans chaque paramètre
- ✅ Structure `{value, choices, description, ...}` uniforme
- ✅ Facilite l'édition dans config editor avec affichage des descriptions

### 2. Amélioration de `ConfigMigration`

**Fichier**: `modules/config_migration.py`

Nouvelles fonctionnalités:

#### a) Constante de version minimale

```python
class ConfigMigration:
    VERSION_1_0 = "1.0"
    VERSION_2_0 = "2.0"
    CURRENT_VERSION = VERSION_2_0
    MINIMUM_SUPPORTED_VERSION = VERSION_1_0  # NEW
```

#### b) Méthode `is_obsolete()`

```python
def is_obsolete(self, config_data: Dict[str, Any]) -> bool:
    """
    Check if configuration is too old and should be reset.
    """
    version = self.detect_version(config_data)
    
    # Unknown or corrupted configs should be reset
    if version == self.VERSION_UNKNOWN:
        return True
    
    # Check if version is not in supported list
    if version not in [self.VERSION_1_0, self.VERSION_2_0]:
        return True
    
    return False
```

#### c) Méthode `reset_to_default()`

```python
def reset_to_default(self, reason: str = "obsolete", 
                     config_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, str]:
    """
    Reset configuration to default, creating a backup first.
    """
    # Create backup of current config
    if config_data is not None:
        backup_path = self.create_backup(config_data)
    # ...
    
    # Copy default config to config.json
    shutil.copy2(default_config_path, self.config_path)
    msg = f"Configuration reset to default (reason: {reason})"
    if backup_path:
        msg += f". Backup created: {backup_path}"
    return True, msg
```

#### d) Amélioration de `detect_version()`

Détecte maintenant `_CONFIG_VERSION` en plus de `_schema_version`:

```python
def detect_version(self, config_data: Dict[str, Any]) -> str:
    # Check for explicit version markers (new format)
    if "_CONFIG_VERSION" in config_data:
        return config_data["_CONFIG_VERSION"]
    
    if "_schema_version" in config_data:
        return config_data["_schema_version"]
    # ...
```

#### e) `auto_migrate_if_needed()` renforcée

Maintenant gère automatiquement:

1. **Config manquante** → Reset avec reason="missing"
2. **Config corrompue** (JSON invalide) → Reset avec reason="corrupted"
3. **Config obsolète** (version non supportée) → Reset avec reason="obsolete"
4. **Config migratable** → Migration normale

```python
def auto_migrate_if_needed(self) -> Tuple[bool, List[str]]:
    # Config missing
    if not os.path.exists(self.config_path):
        success, msg = self.reset_to_default(reason="missing")
        # ...
    
    # Config corrupted
    try:
        config_data = json.load(f)
    except Exception:
        success, msg = self.reset_to_default(reason="corrupted")
        # ...
    
    # Config obsolete
    if self.is_obsolete(config_data):
        success, msg = self.reset_to_default(reason="obsolete")
        # ...
    
    # Config migratable
    if self.needs_migration(config_data):
        # Normal migration process
        # ...
```

### 3. Intégration dans `init_env_vars()`

**Fichier**: `config/config.py`

La fonction `init_env_vars()` appelle maintenant automatiquement la migration au démarrage:

```python
def init_env_vars():
    """
    Initialize environment variables and configuration paths.
    
    Automatically detects and migrates/resets obsolete configurations.
    """
    from modules.config_migration import ConfigMigration
    
    # ... setup paths ...
    
    # Auto-migrate or reset obsolete configurations
    try:
        migrator = ConfigMigration(config_json_path)
        migration_performed, warnings = migrator.auto_migrate_if_needed()
        
        if migration_performed:
            QgsMessageLog.logMessage(
                "Configuration has been automatically migrated or reset to default",
                "FilterMate",
                Qgis.Info
            )
        
        if warnings:
            for warning in warnings:
                QgsMessageLog.logMessage(
                    f"Config migration warning: {warning}",
                    "FilterMate",
                    Qgis.Warning
                )
    except Exception as e:
        QgsMessageLog.logMessage(
            f"Error during configuration migration: {e}",
            "FilterMate",
            Qgis.Warning
        )
    
    # ... rest of init ...
```

## Scénarios Gérés

### Scénario 1: Config Manquante
- **Détection**: `config.json` n'existe pas
- **Action**: Copie de `config.default.json`
- **Log**: "Configuration has been automatically migrated or reset to default"

### Scénario 2: Config Corrompue
- **Détection**: JSON invalide ou erreur de parsing
- **Action**: Backup + Reset vers default
- **Log**: "Configuration was corrupted. Configuration reset to default (reason: corrupted). Backup created: ..."

### Scénario 3: Config Obsolète
- **Détection**: `detect_version()` retourne VERSION_UNKNOWN ou version non supportée
- **Action**: Backup + Reset vers default
- **Log**: "Configuration version unknown is obsolete or unknown"

### Scénario 4: Config Migratable
- **Détection**: Version = 1.0, CURRENT_VERSION = 2.0
- **Action**: Migration automatique 1.0 → 2.0
- **Log**: "Configuration successfully migrated!"

### Scénario 5: Config à Jour
- **Détection**: Version = CURRENT_VERSION
- **Action**: Aucune (skip)
- **Log**: "Configuration is up to date (v2.0)"

## Backups Automatiques

Tous les resets et migrations créent automatiquement des backups dans:
```
config/backups/
├── config_backup_v1.0_20251217_143022.json
├── config_backup_vunknown_20251217_143500.json  (config obsolète)
└── config_backup_v1.0_before_reset_corrupted_20251217_144000.json
```

## Widgets qt_json_view Supportés

La nouvelle structure de `config.default.json` exploite intelligemment les widgets de `qt_json_view`:

### 1. ChoicesType (QComboBox)
```json
{
  "LANGUAGE": {
    "value": "auto",
    "choices": ["auto", "en", "fr", "de", "es", "it", "nl", "pt"],
    "description": "Interface language selection"
  }
}
```

### 2. BoolType (QCheckBox via choices)
```json
{
  "enabled": {
    "value": true,
    "choices": [true, false],
    "description": "Enable feature"
  }
}
```

### 3. ColorType (QgsColorButton)
```json
{
  "PRIMARY": {
    "value": "#1976D2",
    "description": "Primary color"
  }
}
```

### 4. IntType & FloatType (QSpinBox)
```json
{
  "threshold": {
    "value": 5000,
    "description": "Feature count threshold"
  }
}
```

### 5. StrType (QLineEdit)
```json
{
  "PROJECT_PATH": {
    "value": "",
    "description": "Path to project"
  }
}
```

### 6. Métadonnées intégrées (affichées en tooltips)
```json
{
  "PARAMETER": {
    "value": "...",
    "description": "User-friendly description",
    "tooltip": "Additional help text",
    "applies_to": "What this affects",
    "categories_affected": ["list", "of", "features"]
  }
}
```

### Nouveau Module: `ConfigMetadataHandler`

Un nouveau module `modules/config_metadata_handler.py` gère intelligemment les métadonnées:

```python
from modules.config_metadata_handler import ConfigMetadataHandler, MetadataAwareConfigModel

# Extraire les métadonnées
metadata = ConfigMetadataHandler.extract_metadata(config_item)

# Obtenir la description
desc = ConfigMetadataHandler.get_description(config_item)

# Vérifier si éditable
if ConfigMetadataHandler.is_editable_value(key, value):
    # Show editor UI

# Formater pour tooltip
tooltip = ConfigMetadataHandler.format_metadata_for_tooltip(config_item)

# Utiliser le modèle aware
model = MetadataAwareConfigModel(config_data)
desc = model.get_description(["APP", "DOCKWIDGET", "LANGUAGE"])
```

## Tests de Validation

Pour tester la fonctionnalité:

### Test 1: Config Obsolète
```bash
# Créer une config avec version inconnue
echo '{"version": "0.5", "old_key": "value"}' > config/config.json

# Lancer QGIS + FilterMate
# → Devrait détecter obsolète et reset
```

### Test 2: Config Corrompue
```bash
# Créer une config JSON invalide
echo '{invalid json' > config/config.json

# Lancer QGIS + FilterMate
# → Devrait détecter corruption et reset
```

### Test 3: Config Migratable
```bash
# Copier une config v1.0
cp config/config.v1.example.json config/config.json

# Lancer QGIS + FilterMate
# → Devrait migrer vers v2.0
```

### Test 4: Widgets qt_json_view
```python
# Dans le config editor
from modules.qt_json_view import view, model

json_model = model.JsonModel(config_data, editable_keys=True, editable_values=True)
json_view = view.JsonView(json_model)
json_view.expandAll()

# Vérifier:
# - LANGUAGE affiche un QComboBox
# - enabled affiche un QCheckBox (via choices)
# - PRIMARY affiche un color picker
# - Les sections _*_META ne sont PAS éditables
```

## Avantages

✅ **Robustesse**: Gère automatiquement toutes les situations de config invalide  
✅ **Transparence**: Logs informatifs dans QGIS Message Log  
✅ **Sécurité**: Backups automatiques avant toute modification  
✅ **UX améliorée**: Widgets qt_json_view cohérents et intelligents  
✅ **Maintenance**: Structure de config claire et documentée  
✅ **Évolutivité**: Facile d'ajouter de nouvelles versions

## Impact Utilisateur

### Pour l'Utilisateur Final

1. **Première utilisation** ou **config manquante**:
   - Copie automatique de la config par défaut
   - Message informatif dans QGIS

2. **Config obsolète** (ancienne version non supportée):
   - Reset automatique vers default
   - Backup de l'ancienne config dans `config/backups/`
   - Message d'information

3. **Config corrompue**:
   - Reset automatique avec backup
   - Pas de crash, plugin démarre normalement

4. **Config migratable** (v1.0 → v2.0):
   - Migration automatique
   - Préservation des paramètres utilisateur
   - Backup de sécurité

### Pour le Développeur

- Plus besoin de gérer manuellement les migrations
- Tests facilités avec `reset_to_default()`
- Structure de config claire et documentée
- Widgets qt_json_view cohérents

## Fichiers Modifiés

1. ✅ `config/config.default.json` - Structure optimisée avec métadonnées intégrées
2. ✅ `modules/config_migration.py` - Nouvelles méthodes de détection et reset
3. ✅ `config/config.py` - Intégration de la migration automatique avec messages améliorés
4. ✅ `filter_mate.py` - Messages UI améliorés pour migration/reset
5. ✅ `modules/config_metadata_handler.py` - **(NOUVEAU)** Gestion intelligente des métadonnées pour qt_json_view

## Prochaines Étapes

1. **Tests manuels** dans QGIS avec différents scénarios
2. **Tests unitaires** pour `is_obsolete()` et `reset_to_default()`
3. **Documentation utilisateur** sur la gestion des backups
4. **Release notes** pour informer les utilisateurs du comportement

## Notes Techniques

### Ordre de Priorité dans detect_version()

```python
1. _CONFIG_VERSION (nouveau format)
2. _schema_version (format précédent)
3. Détection par structure (APP.DOCKWIDGET = v1.0, app.ui = v2.0)
4. VERSION_UNKNOWN (si rien ne correspond)
```

### Raisons de Reset

- `"missing"`: config.json n'existe pas
- `"corrupted"`: JSON invalide ou erreur de parsing
- `"obsolete"`: Version non supportée ou inconnue
- `"manual"`: Reset manuel par l'utilisateur (via UI)

### Compatibilité Backward

- Les configs v1.0 sont **migrables** (pas obsolètes)
- Les configs v2.0 sont **à jour**
- Toute autre version → **obsolète** → reset

## Conclusion

Cette implémentation garantit que:

1. **Configuration robuste** - Tous les utilisateurs démarrent avec une config valide et à jour
2. **Structure intelligente** - Les métadonnées sont intégrées pour une meilleure UX
3. **Transparence** - Messages clairs en interface QGIS et logs informatifs
4. **Sécurité** - Backups automatiques avant toute modification
5. **Maintenabilité** - Code propre et modules réutilisables pour autres projets

### Avantages supplémentaires:

- 🎯 **Métadonnées intégrées** → Pas de fragmentation, structure cohérente
- 🔧 **ConfigMetadataHandler** → Extraction/affichage intelligent des descriptions
- 📝 **Documentation embarquée** → Les descriptions vivent avec la config
- 💡 **UX Config Editor** → Tooltips automatiques des descriptions
- 🔄 **Évolutivité** → Facile d'ajouter des champs de métadonnées

---

**Status**: ✅ Implémenté avec structure optimisée
**Structure actuelle**: Métadonnées intégrées dans chaque paramètre
**Prochaine action**: Tests dans QGIS + intégration ConfigMetadataHandler dans config editor
