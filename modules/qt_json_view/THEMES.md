# Qt JSON View - Color Themes

Le module `qt_json_view` supporte maintenant plusieurs thèmes de couleurs pour afficher les données JSON de manière plus lisible et agréable.

## Utilisation

### Changer le thème

```python
from modules.qt_json_view import view, model

# Créer la vue JSON
json_model = model.JsonModel(data, editable_keys=True, editable_values=True)
json_view = view.JsonView(json_model)

# Changer le thème
json_view.set_theme('monokai')  # Retourne True si succès
```

### Obtenir le thème actuel

```python
current_theme = json_view.get_current_theme_name()
print(f"Thème actuel: {current_theme}")
```

### Lister les thèmes disponibles

```python
themes = json_view.get_available_themes()
# Retourne: {'default': 'Default', 'monokai': 'Monokai', 'nord': 'Nord', ...}

for key, name in themes.items():
    print(f"{key}: {name}")
```

### Ajouter un sélecteur de thème dans l'interface

```python
from qgis.PyQt.QtWidgets import QComboBox

# Créer un combo box pour sélectionner le thème
theme_combo = QComboBox()
themes_dict = json_view.get_available_themes()

for key, name in themes_dict.items():
    theme_combo.addItem(name, key)

# Connecter au changement de thème
theme_combo.currentIndexChanged.connect(
    lambda: json_view.set_theme(theme_combo.currentData())
)
```

## Thèmes disponibles

### Default
Thème par défaut avec texte noir pour tous les types.

### Monokai
Thème sombre inspiré de l'éditeur Sublime Text, avec des couleurs vives :
- Strings: Jaune
- Nombres: Violet
- Booléens: Orange
- Listes: Rose
- Dictionnaires: Cyan

### Solarized Light
Thème clair avec des couleurs chaudes et lisibles, inspiré du palette Solarized.

### Solarized Dark
Version sombre du thème Solarized, optimisé pour les fonds sombres.

### Nord
Thème avec des couleurs froides inspirées de l'Arctique :
- Couleurs glacées et apaisantes
- Bon contraste sur fond clair ou sombre

### Dracula
Thème sombre avec des couleurs vives et saturées :
- Très populaire dans les éditeurs de code
- Excellent contraste sur fond sombre

### One Dark
Thème style Atom/VS Code :
- Couleurs modernes et équilibrées
- Confortable pour de longues sessions

### Gruvbox
Thème rétro avec des couleurs chaudes :
- Inspiré des terminaux vintage
- Couleurs terreuses et confortables

## Créer un thème personnalisé

Vous pouvez créer votre propre thème en créant une classe qui hérite de `Theme` :

```python
from modules.qt_json_view.themes import Theme, THEMES
from qgis.PyQt.QtGui import QColor

class MyCustomTheme(Theme):
    def __init__(self):
        super().__init__("My Custom Theme")
        self.colors = {
            'none': QColor("#999999"),
            'string': QColor("#00FF00"),
            'integer': QColor("#FF00FF"),
            'float': QColor("#FF00FF"),
            'boolean': QColor("#FF8800"),
            'list': QColor("#FFFF00"),
            'dict': QColor("#00FFFF"),
            'url': QColor("#00FF88"),
            'filepath': QColor("#00FF88"),
            'range': QColor("#FF00FF"),
            'choices': QColor("#00FF00"),
        }

# Enregistrer le thème
THEMES['my_custom'] = MyCustomTheme()

# Utiliser le thème
json_view.set_theme('my_custom')
```

## Types de données et clés de couleur

Chaque type de donnée JSON correspond à une clé de couleur dans le thème :

| Type de donnée | Clé de couleur | Description |
|----------------|----------------|-------------|
| NoneType | `none` | Valeurs null/None |
| StrType | `string` | Chaînes de caractères |
| IntType | `integer` | Nombres entiers |
| FloatType | `float` | Nombres décimaux |
| BoolType | `boolean` | Valeurs booléennes (true/false) |
| ListType | `list` | Tableaux/listes |
| DictType | `dict` | Objets/dictionnaires |
| UrlType | `url` | URLs (http://, https://, file://) |
| FilepathType | `filepath` | Chemins de fichiers |
| RangeType | `range` | Ranges (start/end/step) |
| ChoicesType | `choices` | Valeurs avec choix multiples |

## API du module themes

### Fonctions globales

```python
from modules.qt_json_view import themes

# Obtenir le thème actuel
current = themes.get_current_theme()

# Changer le thème globalement
themes.set_theme('monokai')  # Retourne True/False

# Obtenir la liste des thèmes disponibles
theme_names = themes.get_available_themes()  # ['default', 'monokai', ...]

# Obtenir les noms d'affichage
display_names = themes.get_theme_display_names()  
# {'default': 'Default', 'monokai': 'Monokai', ...}
```

### Méthodes de la classe Theme

```python
theme = themes.get_current_theme()

# Obtenir une couleur pour un type
color = theme.get_color('string')  # Retourne QColor

# Obtenir le nom du thème
name = theme.name  # Ex: "Monokai"
```

## Notes techniques

- Les couleurs sont appliquées via `QtCore.Qt.ForegroundRole` sur les items du modèle
- Le rafraîchissement des couleurs est automatique lors du changement de thème
- Les thèmes sont globaux et affectent toutes les vues JSON actives
- Les couleurs utilisent `QColor` et `QBrush` de Qt
