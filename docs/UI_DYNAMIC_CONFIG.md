# Système de Configuration UI Dynamique - FilterMate

## Vue d'ensemble

Le système de configuration UI dynamique permet à FilterMate d'adapter automatiquement les dimensions, espacements et styles de son interface selon deux profils d'affichage :

- **Compact** : Pour les petits écrans (laptops, tablettes) - éléments plus petits et espacements réduits
- **Normal** : Pour les écrans standards (desktops) - dimensions confortables et généreuses

## Architecture

### Fichiers clés

```
modules/
├── ui_config.py          # Configuration des profils et dimensions
├── ui_widget_utils.py    # Utilitaires d'application aux widgets
├── ui_styles.py          # Gestion des thèmes de couleurs (étendu)
config/
└── config.json           # Configuration persistante (étendu)
```

## Utilisation

### 1. Changer de profil d'affichage

#### Via config.json
```json
{
    "APP": {
        "DOCKWIDGET": {
            "UI_PROFILE": "compact",  // ou "normal"
            ...
        }
    }
}
```

#### Programmatiquement
```python
from modules.ui_config import UIConfig, DisplayProfile

# Changer vers compact
UIConfig.set_profile(DisplayProfile.COMPACT)

# Changer vers normal
UIConfig.set_profile(DisplayProfile.NORMAL)
```

### 2. Obtenir des dimensions

```python
from modules.ui_config import UIConfig

# Hauteur d'un bouton standard
height = UIConfig.get_button_height("button")  # 32px (compact) ou 40px (normal)

# Taille d'icône pour bouton d'action
icon_size = UIConfig.get_icon_size("action_button")  # 22px (compact) ou 25px (normal)

# Espacement moyen
spacing = UIConfig.get_spacing("medium")  # 6px (compact) ou 10px (normal)

# Marges normales
margins = UIConfig.get_margins("normal")  # {'top': 6, 'right': 6, ...} (compact)
```

### 3. Appliquer des styles à des widgets

#### Méthode simple avec utilitaires

```python
from modules import ui_widget_utils as ui_utils

# Appliquer automatiquement selon le type de widget
ui_utils.apply_widget_dimensions(my_button, "button")

# Ou avec détection automatique
ui_utils.apply_widget_dimensions(my_widget, "auto")

# Boutons d'action
ui_utils.apply_button_dimensions(filter_button, "action_button")

# Boutons d'outils
ui_utils.apply_button_dimensions(zoom_button, "tool_button")

# Champs de saisie
ui_utils.apply_input_dimensions(line_edit)

# ComboBox
ui_utils.apply_combobox_dimensions(combo_box)

# Layout spacing
ui_utils.apply_layout_spacing(layout, "medium")

# Layout margins
ui_utils.apply_layout_margins(layout, "normal")
```

#### Méthode manuelle

```python
from modules.ui_config import UIConfig
from PyQt5.QtCore import QSize

# Bouton avec dimensions dynamiques
button = QPushButton("Filter")
height = UIConfig.get_button_height("action_button")
icon_size = UIConfig.get_icon_size("action_button")

button.setMinimumHeight(height)
button.setMaximumHeight(height)
button.setIconSize(QSize(icon_size, icon_size))
```

### 4. Configuration de groupes de widgets

```python
from modules import ui_widget_utils as ui_utils

# Configurer plusieurs boutons d'action
ui_utils.configure_action_buttons(
    parent_widget,
    ['btn_filter', 'btn_export', 'btn_reset']
)

# Configurer plusieurs boutons d'outils
ui_utils.configure_tool_buttons(
    parent_widget,
    ['btn_zoom', 'btn_identify', 'btn_select']
)
```

## Profils disponibles

### Profil Compact

**Caractéristiques** :
- Boutons : 32px (standard), 36px (action), 28px (outils)
- Icônes : 18-22px
- Espacements : 3-10px
- Marges : 3-10px
- ComboBox : 28px
- Inputs : 28px

**Usage recommandé** : Laptops 13-14", tablettes, résolutions < 1920x1080

### Profil Normal (par défaut)

**Caractéristiques** :
- Boutons : 40px (standard), 48px (action), 36px (outils)
- Icônes : 20-25px
- Espacements : 6-10px (principal), 6-8px (sections)
- Marges : 4-10px
- Padding frames : 8px
- ComboBox : 36px
- Inputs : 36px

**Usage recommandé** : Desktops, laptops 15"+, résolutions ≥ 1920x1080

## Types de composants configurables

### Boutons

- `button` : Bouton standard
- `action_button` : Boutons principaux (Filter, Export, Reset)
- `tool_button` : Boutons d'outils (Zoom, Identify, Select)

**Propriétés** :
- `height` : Hauteur du bouton
- `icon_size` : Taille de l'icône
- `padding` : Padding intérieur (dict avec top, right, bottom, left)
- `border_radius` : Rayon de bordure
- `min_width` : Largeur minimale

### Champs de saisie

- `input` : QLineEdit, QSpinBox, QDoubleSpinBox
- `combobox` : QComboBox et variantes

**Propriétés** :
- `height` : Hauteur du champ
- `padding` : Padding intérieur
- `border_radius` : Rayon de bordure
- `item_height` (combobox) : Hauteur des items
- `icon_size` (combobox) : Taille des icônes

### Conteneurs

- `frame` : QFrame standard
- `action_frame` : Frame de boutons d'action
- `splitter` : QSplitter

**Propriétés** :
- `min_height`, `max_height` : Contraintes de hauteur
- `padding` : Padding intérieur
- `border_width` : Épaisseur de bordure
- `handle_width` (splitter) : Largeur du séparateur

### Texte et labels

- `label` : QLabel
- `tab` : QTabWidget

**Propriétés** :
- `font_size` : Taille de police en points
- `line_height` : Hauteur de ligne
- `padding` : Espacement

### Espacements et marges

- `spacing` : Espacement entre widgets
  - `small` : 3px (compact) / 5px (normal)
  - `medium` : 6px (compact) / 10px (normal)
  - `large` : 10px (compact) / 15px (normal)
  - `extra_large` : 15px (compact) / 20px (normal)

- `margins` : Marges de layout
  - `tight` : 3-5px
  - `normal` : 6-10px
  - `loose` : 10-15px

## Intégration avec les thèmes de couleurs

Le système de profils UI fonctionne en parallèle avec le système de thèmes existant :

```python
from modules.ui_styles import StyleLoader

# Les thèmes de couleurs sont indépendants des profils de dimensions
# Vous pouvez avoir "compact" + "dark" ou "normal" + "light", etc.

# Le stylesheet est automatiquement enrichi avec les dimensions
StyleLoader.load_stylesheet_from_config(config_data, theme="dark")
```

### Placeholders dans les QSS

Vous pouvez utiliser des placeholders dans vos fichiers `.qss` :

```css
QPushButton {
    min-height: {button_height};
    padding: {button_padding};
    border-radius: {button_border_radius};
}

QPushButton#action_button {
    min-height: {action_button_height};
    icon-size: {action_button_icon_size};
}

QComboBox {
    min-height: {combobox_height};
    padding: {combobox_padding};
}

QLayout {
    spacing: {spacing_medium};
}
```

Ces placeholders seront automatiquement remplacés par les valeurs du profil actif.

## Informations sur le profil actif

```python
from modules import ui_widget_utils as ui_utils

# Obtenir les informations du profil
info = ui_utils.get_profile_info()
print(info)
# {
#     'available': True,
#     'profile': 'compact',
#     'description': 'Compact layout for small screens...',
#     'button_height': 32,
#     'icon_size': 18,
#     'spacing_medium': 6
# }
```

## Basculement dynamique de profil

```python
from modules import ui_widget_utils as ui_utils

# Changer de profil
success = ui_utils.switch_profile("compact")

if success:
    # Recharger l'UI
    # Note: Nécessite de réappliquer les styles aux widgets
    # Ou redémarrer le plugin
    pass
```

## Extension du système

### Ajouter un nouveau composant

Éditez `modules/ui_config.py` et ajoutez votre composant dans les deux profils :

```python
PROFILES: Dict[str, Dict[str, Any]] = {
    "compact": {
        # ... autres composants ...
        
        "mon_widget": {
            "height": 30,
            "padding": {"top": 4, "right": 6, "bottom": 4, "left": 6},
            "custom_prop": "value"
        }
    },
    
    "normal": {
        # ... autres composants ...
        
        "mon_widget": {
            "height": 40,
            "padding": {"top": 6, "right": 10, "bottom": 6, "left": 10},
            "custom_prop": "value"
        }
    }
}
```

### Utiliser le nouveau composant

```python
# Récupérer une propriété
height = UIConfig.get_config("mon_widget", "height")

# Récupérer tout le composant
config = UIConfig.get_config("mon_widget")
```

### Créer un utilitaire d'application

Dans `modules/ui_widget_utils.py` :

```python
def apply_mon_widget_dimensions(widget: QWidget) -> None:
    """Apply dynamic dimensions to mon_widget."""
    if not UI_CONFIG_AVAILABLE:
        return
    
    try:
        height = UIConfig.get_config("mon_widget", "height")
        if height:
            widget.setMinimumHeight(height)
            widget.setMaximumHeight(height)
    except Exception as e:
        print(f"Error applying mon_widget dimensions: {e}")
```

## Bonnes pratiques

### ✅ À faire

1. **Toujours vérifier UI_CONFIG_AVAILABLE** avant d'utiliser UIConfig
2. **Fournir des fallbacks** pour les valeurs par défaut
3. **Utiliser les utilitaires** (`ui_widget_utils`) plutôt que UIConfig directement
4. **Tester les deux profils** lors du développement
5. **Documenter les nouveaux composants** ajoutés

### ❌ À éviter

1. **Ne pas coder en dur les dimensions** dans les widgets
2. **Ne pas mélanger dimensions fixes et dynamiques** sur le même widget
3. **Ne pas oublier les deux profils** lors de l'ajout d'un composant
4. **Ne pas ignorer les erreurs** d'import de UIConfig

## Compatibilité et migration

### Rétrocompatibilité

Le système est conçu pour être rétrocompatible :

- Si `ui_config.py` n'est pas disponible, les dimensions fixes sont utilisées
- Si `UI_PROFILE` n'est pas dans `config.json`, "normal" est utilisé par défaut
- Les anciens plugins/configurations continuent de fonctionner

### Migration d'un code existant

**Avant** (dimensions fixes) :
```python
button.setMinimumHeight(40)
button.setMaximumHeight(40)
button.setIconSize(QSize(20, 20))
```

**Après** (dimensions dynamiques) :
```python
from modules import ui_widget_utils as ui_utils
ui_utils.apply_button_dimensions(button, "action_button")
```

## Exemples complets

### Exemple 1 : Configuration d'une toolbar

```python
from modules.ui_config import UIConfig
from modules import ui_widget_utils as ui_utils
from PyQt5.QtWidgets import QHBoxLayout, QPushButton

# Créer le layout
toolbar_layout = QHBoxLayout()

# Appliquer espacement et marges dynamiques
ui_utils.apply_layout_spacing(toolbar_layout, "small")
ui_utils.apply_layout_margins(toolbar_layout, "tight")

# Créer et configurer les boutons
for name in ['Filter', 'Export', 'Reset']:
    btn = QPushButton(name)
    ui_utils.apply_button_dimensions(btn, "action_button")
    toolbar_layout.addWidget(btn)
```

### Exemple 2 : Configuration d'un formulaire

```python
from modules import ui_widget_utils as ui_utils
from PyQt5.QtWidgets import QFormLayout, QLabel, QLineEdit, QComboBox

# Créer le layout
form_layout = QFormLayout()
ui_utils.apply_layout_spacing(form_layout, "medium")
ui_utils.apply_layout_margins(form_layout, "normal")

# Créer et configurer les champs
name_label = QLabel("Name:")
name_input = QLineEdit()
ui_utils.apply_input_dimensions(name_input)

type_label = QLabel("Type:")
type_combo = QComboBox()
ui_utils.apply_combobox_dimensions(type_combo)

form_layout.addRow(name_label, name_input)
form_layout.addRow(type_label, type_combo)
```

### Exemple 3 : Détection et ajustement dynamique

```python
from modules.ui_config import UIConfig
from modules import ui_widget_utils as ui_utils

# Détecter le profil actuel
profile_info = ui_utils.get_profile_info()

if profile_info['profile'] == 'compact':
    print("Mode compact actif - optimisé pour petits écrans")
    # Ajustements spécifiques pour compact
    max_items_visible = 5
else:
    print("Mode normal actif - interface spacieuse")
    max_items_visible = 10

# Appliquer les dimensions appropriées
ui_utils.apply_widget_dimensions(my_widget, "auto")
```

## Dépannage

### Le profil ne se charge pas

1. Vérifier que `UI_PROFILE` existe dans `config.json`
2. Vérifier que la valeur est "compact" ou "normal"
3. Vérifier les logs : `print(f"FilterMate UIConfig: Loaded profile...")`

### Les dimensions ne s'appliquent pas

1. Vérifier que `UI_CONFIG_AVAILABLE` est `True`
2. Vérifier que les widgets sont créés après le chargement du profil
3. Utiliser `ui_utils.apply_widget_dimensions()` après création des widgets

### Dimensions mixtes (certains widgets dynamiques, d'autres fixes)

Cela arrive lors d'une migration partielle. Solution :
1. Identifier tous les `setMinimumHeight`, `setMaximumHeight`, etc. dans le code
2. Remplacer par des appels à `ui_utils.apply_*_dimensions()`
3. Tester les deux profils

## Ressources

- **Code source** : `modules/ui_config.py`, `modules/ui_widget_utils.py`
- **Configuration** : `config/config.json`
- **Tests** : `tests/test_ui_config.py` (à créer)
- **Documentation QGIS** : https://qgis.org/pyqgis/

## Notes de version

**v2.0.0** - Décembre 2025
- Système de configuration UI dynamique complet
- Support de profils compact/normal
- Intégration avec système de thèmes existant
- Utilitaires d'application simplifiés
- Rétrocompatibilité garantie
