# Qt JSON View Module

A Qt-based JSON viewer and editor widget for QGIS plugins, with support for color themes.

## Features

- **Tree-based JSON visualization** - Display JSON data in an expandable tree structure
- **Editable keys and values** - Optionally allow editing of JSON content
- **Custom data types** - Special handling for URLs, file paths, ranges, choices, and colors
- **Color picker integration** - QgsColorButton for hex color values with live preview
- **Color themes** - 8 built-in themes plus support for custom themes
- **Context menu actions** - Add, remove, rename, and modify JSON elements
- **Type-specific editors** - Specialized editors for different data types

## Quick Start

### Basic Usage

```python
from modules.qt_json_view import view, model

# Your JSON data
data = {
    "name": "Example",
    "count": 42,
    "enabled": True,
    "items": ["a", "b", "c"]
}

# Create model and view
json_model = model.JsonModel(data, editable_keys=True, editable_values=True)
json_view = view.JsonView(json_model)

# Show the view
json_view.show()
json_view.expandAll()
```

### Using Color Themes

```python
# Set a theme
json_view.set_theme('monokai')

# Get current theme
current = json_view.get_current_theme_name()

# List available themes
themes = json_view.get_available_themes()
# Returns: {'default': 'Default', 'monokai': 'Monokai', ...}
```

### Adding a Theme Selector

```python
from qgis.PyQt.QtWidgets import QComboBox

theme_combo = QComboBox()
for key, name in json_view.get_available_themes().items():
    theme_combo.addItem(name, key)

theme_combo.currentIndexChanged.connect(
    lambda: json_view.set_theme(theme_combo.currentData())
)
```

## Available Themes

- **Default** - Black text for all types
- **Monokai** - Vibrant dark theme (Sublime Text inspired)
- **Solarized Light** - Warm, readable colors on light background
- **Solarized Dark** - Warm, readable colors on dark background
- **Nord** - Cool, arctic-inspired colors
- **Dracula** - Vivid colors on dark background
- **One Dark** - Modern theme (Atom/VS Code style)
- **Gruvbox** - Warm, retro colors

See [THEMES.md](THEMES.md) for detailed theme documentation.

## Module Structure

```
qt_json_view/
├── __init__.py           # Package initialization
├── view.py              # JsonView - main tree view widget
├── model.py             # JsonModel - data model
├── delegate.py          # JsonDelegate - custom rendering
├── datatypes.py         # DataType classes for different JSON types
├── themes.py            # Color theme system (NEW)
├── example_themes.py    # Example usage with themes (NEW)
├── THEMES.md           # Theme documentation (NEW)
└── README.md           # This file
```

## Custom Data Types

The module includes special handling for:

### URLs
```python
data = {"homepage": "https://example.com"}
# Right-click provides "Explore..." action
```

### File Paths
```python
data = {"config": "/path/to/file.json"}
# Right-click provides "View" and "Change" actions
```

### Ranges
```python
data = {"zoom": {"start": 1, "end": 20, "step": 1}}
# Displayed as three spinboxes
```

### Choices
```python
data = {
    "backend": {
        "value": "postgresql",
        "choices": ["postgresql", "spatialite", "ogr"]
    }
}
# Displayed as a combobox
```

### Hex Colors
```python
data = {
    "theme": {
        "background": "#F5F5F5",
        "primary": "#2196F3",
        "accent": "#FF5722CC"  # With alpha/transparency
    }
}
# Automatically detected and displayed with color preview
# Click to open QgsColorButton color picker
# Supports RGB (#RRGGBB) and RGBA (#RRGGBBAA) formats
```

## Creating Custom Themes

```python
from modules.qt_json_view.themes import Theme, THEMES
from qgis.PyQt.QtGui import QColor

class MyTheme(Theme):
    def __init__(self):
        super().__init__("My Theme Name")
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

# Register the theme
THEMES['my_theme'] = MyTheme()

# Use it
json_view.set_theme('my_theme')
```

## API Reference

### JsonView

Main widget for displaying JSON data.

**Methods:**
- `set_theme(theme_name: str) -> bool` - Change color theme
- `get_current_theme_name() -> str` - Get name of active theme
- `get_available_themes() -> dict` - Get dict of available themes
- `refresh_colors()` - Refresh colors after theme change

### JsonModel

Data model for JSON structure.

**Constructor:**
```python
JsonModel(data, editable_keys=False, editable_values=False)
```

### Theme System

**Functions in `themes` module:**
- `get_current_theme() -> Theme` - Get active theme object
- `set_theme(name: str) -> bool` - Set active theme globally
- `get_available_themes() -> list` - Get list of theme keys
- `get_theme_display_names() -> dict` - Get display names

## Integration with FilterMate

This module is used in FilterMate for displaying:
- Filter history (JSON filter expressions)
- Configuration settings
- Task results and metadata
- Backend connection information

## Testing

Run the theme tests:
```bash
python -m pytest tests/test_qt_json_view_themes.py -v
```

## Dependencies

- QGIS 3.x (PyQt5 via qgis.PyQt)
- Python 3.7+

## Contributing

When adding new data types:
1. Create a new class inheriting from `DataType` in `datatypes.py`
2. Add `THEME_COLOR_KEY` attribute
3. Implement `matches()` method
4. Add the type to `DATA_TYPES` list
5. Update theme color keys in `themes.py` if needed

When adding new themes:
1. Create a new class inheriting from `Theme` in `themes.py`
2. Define all color keys in the constructor
3. Add to `THEMES` dictionary
4. Update documentation

## License

This module is part of FilterMate QGIS plugin.
See LICENSE file in the root directory.

## Credits

- Original qt_json_view concept from Qt examples
- Theme colors inspired by popular editor themes
- Enhanced for QGIS plugin integration by FilterMate team
