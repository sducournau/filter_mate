# Configuration JSON Tree View Reactivity

## Vue d'ensemble

Le plugin FilterMate permet de modifier la configuration directement depuis l'interface via un **JSON Tree View**. Les changements effectués dans cette vue sont automatiquement détectés, enregistrés et appliqués à l'interface utilisateur en temps réel.

## Fonctionnalités

### 1. Détection automatique des changements

Lorsqu'une valeur est modifiée dans le JSON Tree View :
- Le signal `itemChanged` est émis par le modèle `JsonModel`
- Le handler `data_changed_configuration_model()` est appelé automatiquement
- Les changements sont enregistrés dans `config.json`

### 2. Application automatique des profils UI

Le paramètre `UI_PROFILE` dans le JSON peut prendre 3 valeurs :
- **`"auto"`** : Détection automatique basée sur la taille de l'écran
- **`"compact"`** : Mode compact pour petits écrans (laptops, tablettes)
- **`"normal"`** : Mode normal pour grands écrans

**Quand `UI_PROFILE` est modifié** :
1. La nouvelle valeur est détectée
2. Le profil `UIConfig` est mis à jour
3. `apply_dynamic_dimensions()` est appelé pour appliquer les nouvelles dimensions
4. Un message de confirmation est affiché à l'utilisateur

### 3. Application automatique des thèmes

Le paramètre `ACTIVE_THEME` dans `COLORS` peut prendre 4 valeurs :
- **`"auto"`** : Détection automatique basée sur le thème QGIS actif
- **`"default"`** : Thème clair par défaut
- **`"dark"`** : Thème sombre
- **`"light"`** : Thème clair

**Quand `ACTIVE_THEME` est modifié** :
1. La nouvelle valeur est détectée
2. Le thème est appliqué via `StyleLoader.set_theme_from_config()`
3. Tous les widgets sont restyled automatiquement
4. Un message de confirmation est affiché à l'utilisateur

### 4. Application automatique des formats d'export

Les paramètres `DATATYPE_TO_EXPORT` et `STYLES_TO_EXPORT` peuvent être modifiés :

**DATATYPE_TO_EXPORT** (format de fichier) :
- `"GPKG"`, `"SHP"`, `"GEOJSON"`, `"KML"`, `"DXF"`, `"CSV"`

**STYLES_TO_EXPORT** (format de style) :
- `"QML"`, `"SLD"`, `"None"`

**Quand ces valeurs sont modifiées** :
1. La nouvelle valeur est détectée
2. Le combobox correspondant dans l'onglet Export est mis à jour
3. Un message informatif est affiché à l'utilisateur

### 5. Gestion des icônes

Les changements dans les chemins contenant `ICONS` déclenchent :
- La mise à jour automatique des icônes des widgets
- Le rechargement des icônes depuis le dossier `icons/`

## Architecture technique

### Signal Flow

```
JsonModel (QStandardItemModel)
    ↓
itemChanged signal
    ↓
data_changed_configuration_model()
    ↓
┌─────────────────────────────────┐
│ Détection du type de changement │
└─────────────────────────────────┘
    ↓
    ├─→ UI_PROFILE changed
    │       ↓
    │   UIConfig.set_profile()
    │       ↓
    │   apply_dynamic_dimensions()
    │       ↓
    │   Message utilisateur
    │
    ├─→ ACTIVE_THEME changed
    │       ↓
    │   StyleLoader.detect_qgis_theme() (si 'auto')
    │       ↓
    │   StyleLoader.set_theme_from_config()
    │       ↓
    │   Message utilisateur
    │
    ├─→ DATATYPE_TO_EXPORT changed
    │       ↓
    │   Update export format combobox
    │       ↓
    │   Message utilisateur
    │
    ├─→ STYLES_TO_EXPORT changed
    │       ↓
    │   Update export style combobox
    │       ↓
    │   Message utilisateur
    │
    ├─→ ICONS changed
    │       ↓
    │   set_widget_icon()
    │
    └─→ Autres changements
            ↓
        (enregistrement uniquement)
    ↓
save_configuration_model()
    ↓
config.json mis à jour
```

### Code clé

#### 1. Connexion du signal (filter_mate_dockwidget.py)

```python
# Dans connect_widgets_signals()
self.widgets["DOCK"]["CONFIGURATION_MODEL"]["WIDGET"].itemChanged.connect(
    self.data_changed_configuration_model
)
```

#### 2. Handler principal (filter_mate_dockwidget.py)

```python
def data_changed_configuration_model(self, input_data=None):
    if self.widgets_initialized is True:
        # Récupération du chemin de la clé modifiée
        index = input_data.index()
        item = input_data
        item_key = self.config_view.model.itemFromIndex(index.siblingAtColumn(0))
        
        items_keys_values_path = []
        while item_key != None:
            items_keys_values_path.append(item_key.data(QtCore.Qt.DisplayRole))
            item_key = item_key.parent()
        items_keys_values_path.reverse()
        
        # Gestion spécifique selon le type de changement
        
        # 1. Changements d'icônes
        if 'ICONS' in items_keys_values_path:
            self.set_widget_icon(items_keys_values_path)
        
        # 2. Changements de thème
        if 'ACTIVE_THEME' in items_keys_values_path:
            value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
            value_data = value_item.data(QtCore.Qt.UserRole)
            
            # Handle ChoicesType format
            if isinstance(value_data, dict) and 'value' in value_data:
                new_theme_value = value_data['value']
            else:
                new_theme_value = value_item.data(QtCore.Qt.DisplayRole)
            
            if new_theme_value:
                from .modules.ui_styles import StyleLoader
                
                if new_theme_value == 'auto':
                    detected_theme = StyleLoader.detect_qgis_theme()
                    StyleLoader.set_theme_from_config(
                        self.dockWidgetContents, 
                        self.CONFIG_DATA, 
                        detected_theme
                    )
                else:
                    StyleLoader.set_theme_from_config(
                        self.dockWidgetContents, 
                        self.CONFIG_DATA, 
                        new_theme_value
                    )
                
                iface.messageBar().pushSuccess(
                    "FilterMate",
                    f"Theme changed to {new_theme_value.upper()}. UI updated.",
                    3
                )
        
        # 3. Changements de profil UI
        if 'UI_PROFILE' in items_keys_values_path:
            value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
            value_data = value_item.data(QtCore.Qt.UserRole)
            
            # Handle ChoicesType format
            if isinstance(value_data, dict) and 'value' in value_data:
                new_profile_value = value_data['value']
            else:
                new_profile_value = value_item.data(QtCore.Qt.DisplayRole)
            
            if new_profile_value and UI_CONFIG_AVAILABLE:
                from .modules.ui_config import UIConfig, DisplayProfile
                
                if new_profile_value == 'compact':
                    UIConfig.set_profile(DisplayProfile.COMPACT)
                elif new_profile_value == 'normal':
                    UIConfig.set_profile(DisplayProfile.NORMAL)
                elif new_profile_value == 'auto':
                    detected_profile = UIConfig.detect_optimal_profile()
                    UIConfig.set_profile(detected_profile)
                
                # Réapplication des dimensions
                self.apply_dynamic_dimensions()
                
                # Message utilisateur
                profile_display = UIConfig.get_profile_name().upper()
                iface.messageBar().pushSuccess(
                    "FilterMate",
                    f"UI profile changed to {profile_display} mode. Dimensions updated.",
                    3
                )
        
        # 4. Changements de format d'export
        if 'DATATYPE_TO_EXPORT' in items_keys_values_path:
            value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
            value_data = value_item.data(QtCore.Qt.UserRole)
            
            if isinstance(value_data, dict) and 'value' in value_data:
                new_format_value = value_data['value']
            else:
                new_format_value = value_item.data(QtCore.Qt.DisplayRole)
            
            if new_format_value and 'DATATYPE_TO_EXPORT' in self.widgets.get('EXPORTING', {}):
                format_combo = self.widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"]
                index_to_set = format_combo.findText(new_format_value)
                if index_to_set >= 0:
                    format_combo.setCurrentIndex(index_to_set)
                    iface.messageBar().pushInfo(
                        "FilterMate",
                        f"Export format changed to {new_format_value}",
                        3
                    )
        
        # 5. Changements de style d'export
        if 'STYLES_TO_EXPORT' in items_keys_values_path:
            value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
            value_data = value_item.data(QtCore.Qt.UserRole)
            
            if isinstance(value_data, dict) and 'value' in value_data:
                new_style_value = value_data['value']
            else:
                new_style_value = value_item.data(QtCore.Qt.DisplayRole)
            
            if new_style_value and 'STYLE_TO_EXPORT' in self.widgets.get('EXPORTING', {}):
                style_combo = self.widgets["EXPORTING"]["STYLE_TO_EXPORT"]["WIDGET"]
                index_to_set = style_combo.findText(new_style_value)
                if index_to_set >= 0:
                    style_combo.setCurrentIndex(index_to_set)
                    iface.messageBar().pushInfo(
                        "FilterMate",
                        f"Export style changed to {new_style_value}",
                        3
                    )
        
        # Sauvegarde systématique
        self.save_configuration_model()
```
        
        if 'UI_PROFILE' in items_keys_values_path:
            # Récupération de la nouvelle valeur
            value_item = self.config_view.model.itemFromIndex(index.siblingAtColumn(1))
            new_profile_value = value_item.data(QtCore.Qt.DisplayRole)
            
            # Application du nouveau profil
            if new_profile_value == 'compact':
                UIConfig.set_profile(DisplayProfile.COMPACT)
            elif new_profile_value == 'normal':
                UIConfig.set_profile(DisplayProfile.NORMAL)
            elif new_profile_value == 'auto':
                detected_profile = UIConfig.detect_optimal_profile()
                UIConfig.set_profile(detected_profile)
            
            # Réapplication des dimensions
            self.apply_dynamic_dimensions()
            
            # Message utilisateur
            iface.messageBar().pushSuccess(
                "FilterMate",
                f"UI profile changed to {profile_display} mode. Dimensions updated.",
                3
            )
        
        # Sauvegarde systématique
        self.save_configuration_model()
```

## Utilisation

### Modifier le profil UI depuis l'interface

1. Ouvrir le panneau **Configuration** dans FilterMate
2. Naviguer jusqu'à `APP → DOCKWIDGET → UI_PROFILE`
3. Double-cliquer sur la valeur pour l'éditer
4. Entrer une nouvelle valeur : `"auto"`, `"compact"` ou `"normal"`
5. Valider avec Entrée

**Résultat** : L'interface est immédiatement mise à jour avec les nouvelles dimensions !

### Modifier le thème depuis l'interface

1. Ouvrir le panneau **Configuration** dans FilterMate
2. Naviguer jusqu'à `APP → DOCKWIDGET → COLORS → ACTIVE_THEME`
3. Double-cliquer sur la valeur pour l'éditer
4. Entrer une nouvelle valeur : `"auto"`, `"default"`, `"dark"` ou `"light"`
5. Valider avec Entrée

**Résultat** : Le thème de l'interface est immédiatement appliqué !

### Modifier le format d'export depuis l'interface

1. Ouvrir le panneau **Configuration** dans FilterMate
2. Naviguer jusqu'à `APP → EXPORTING → DATATYPE_TO_EXPORT`
3. Double-cliquer sur la valeur pour l'éditer
4. Entrer une nouvelle valeur : `"GPKG"`, `"SHP"`, `"GEOJSON"`, etc.
5. Valider avec Entrée

**Résultat** : Le format d'export par défaut est mis à jour dans l'onglet Export !

### Modifier le style d'export depuis l'interface

1. Ouvrir le panneau **Configuration** dans FilterMate
2. Naviguer jusqu'à `APP → EXPORTING → STYLES_TO_EXPORT`
3. Double-cliquer sur la valeur pour l'éditer
4. Entrer une nouvelle valeur : `"QML"`, `"SLD"` ou `"None"`
5. Valider avec Entrée

**Résultat** : Le style d'export par défaut est mis à jour dans l'onglet Export !

### Modifier une icône depuis l'interface

1. Naviguer jusqu'à un chemin contenant `ICONS`
   - Exemple : `APP → DOCKWIDGET → PushButton → ICONS → ACTION → FILTER`
2. Double-cliquer sur le nom du fichier (ex: `"filter.png"`)
3. Entrer le nouveau nom de fichier
4. Valider avec Entrée

**Résultat** : L'icône du widget est rechargée automatiquement !

## Extensions futures

La structure actuelle permet d'ajouter facilement de nouveaux types de changements réactifs :

```python
# Dans data_changed_configuration_model()

if 'CUSTOM_SETTING' in items_keys_values_path:
    self.apply_custom_setting_change(items_keys_values_path)

if 'LANGUAGE' in items_keys_values_path:
    self.change_language(items_keys_values_path)

if 'FONT_SIZE' in items_keys_values_path:
    self.apply_font_size_change(items_keys_values_path)
```

### Idées d'extensions

1. ✅ **Changement de thème** : Passer de clair à sombre en temps réel *(implémenté)*
2. ✅ **Changement de profil UI** : Adapter les dimensions dynamiquement *(implémenté)*
3. ✅ **Format d'export** : Modifier le format par défaut *(implémenté)*
4. ✅ **Style d'export** : Modifier le style par défaut *(implémenté)*
5. **Changement de langue** : Appliquer i18n sans redémarrer
6. **Tailles de police** : Ajuster la taille des textes
7. **Espacement** : Modifier les marges et paddings dynamiquement
8. **Projection par défaut** : Changer le CRS d'export
9. **Limite de features** : Ajuster FEATURE_COUNT_LIMIT
10. **Configurations de backend** : PostgreSQL/Spatialite/OGR options

## Tests

Le fichier `tests/test_config_json_reactivity.py` contient des tests complets :

```bash
# Exécuter les tests
python tests/test_config_json_reactivity.py
```

**Tests inclus** :
- ✅ Signal `itemChanged` connecté
- ✅ Détection des changements `UI_PROFILE`
- ✅ Détection des changements `ACTIVE_THEME`
- ✅ Détection des changements `DATATYPE_TO_EXPORT`
- ✅ Détection des changements `STYLES_TO_EXPORT`
- ✅ Application des dimensions dynamiques
- ✅ Application des thèmes
- ✅ Mise à jour des combobox d'export
- ✅ Sauvegarde de la configuration
- ✅ Préservation du traitement des `ICONS`
- ✅ Feedback utilisateur
- ✅ Gestion des erreurs
- ✅ Intégration avec `UIConfig` et `StyleLoader`
- ✅ Présence de `UI_PROFILE` et `ACTIVE_THEME` dans `config.json`

## Dépendances

- **JsonModel** (`modules/qt_json_view/model.py`) : Modèle de données pour le tree view
- **JsonView** (`modules/qt_json_view/view.py`) : Vue Qt pour le JSON
- **UIConfig** (`modules/ui_config.py`) : Système de gestion des profils UI
- **DisplayProfile** : Enum des profils disponibles (COMPACT, NORMAL)
- **StyleLoader** (`modules/ui_styles.py`) : Système de gestion des thèmes et styles
- **iface** (QGIS) : Interface pour les messages utilisateur

## Performances

- **Impact minimal** : Seuls les changements détectés déclenchent des actions
- **Sauvegarde efficace** : Le JSON est sérialisé une seule fois par changement
- **Pas de redémarrage** : Tous les changements sont appliqués instantanément
- **Cache de styles** : StyleLoader met en cache les QSS pour éviter les rechargements inutiles
- **Blocage de signaux** : Prévention des boucles infinies lors de mises à jour programmatiques

## Gestion des erreurs

Tous les changements sont protégés par des blocs `try-except` :
- Les erreurs sont loggées avec `logger.error()` et traceback complet
- Un message d'erreur est affiché à l'utilisateur via `iface.messageBar().pushCritical()`
- Le plugin continue de fonctionner même en cas d'erreur
- La sauvegarde de la configuration se fait toujours, même après une erreur

## Compatibilité

- ✅ QGIS 3.x
- ✅ Windows / Linux / macOS
- ✅ Compatible avec/sans `psycopg2`
- ✅ Fonctionne même si `UI_CONFIG_AVAILABLE = False` (mode dégradé)

## Références

- [UI_SYSTEM_OVERVIEW.md](UI_SYSTEM_OVERVIEW.md) : Vue d'ensemble du système UI
- [UI_CONFIG_VALIDATION.md](UI_CONFIG_VALIDATION.md) : Validation de la configuration
- [UI_DYNAMIC_CONFIG.md](UI_DYNAMIC_CONFIG.md) : Configuration dynamique
- [modules/ui_config.py](../modules/ui_config.py) : Code source UIConfig
- [modules/qt_json_view/](../modules/qt_json_view/) : Composants JSON Tree View

---

**Date de création** : 7 décembre 2025  
**Dernière mise à jour** : 7 décembre 2025  
**Auteur** : FilterMate Development Team  
**Version** : 2.2.0 - Enhanced reactivity with theme, profile, and export format changes
