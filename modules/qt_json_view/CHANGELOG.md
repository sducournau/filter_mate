# Qt JSON View - Changelog

## [1.1.0] - 2025-01-05

### Added
- **Color Theme System** - Support for multiple color themes
  - 8 built-in themes: Default, Monokai, Solarized Light/Dark, Nord, Dracula, One Dark, Gruvbox
  - Theme selection API in JsonView widget
  - `set_theme()`, `get_current_theme_name()`, `get_available_themes()` methods
  - Automatic color refresh when theme changes
  
- **Theme Infrastructure**
  - New `themes.py` module with Theme base class
  - Color definitions for all JSON data types
  - Global theme management functions
  - Support for custom theme creation and registration
  
- **DataType Theme Integration**
  - Added `THEME_COLOR_KEY` to all DataType classes
  - `get_color()` method for dynamic color retrieval
  - Automatic color application from active theme
  
- **Documentation**
  - `THEMES.md` - Comprehensive theme documentation
  - `README.md` - Updated with theme usage examples
  - `example_themes.py` - Example implementation with theme selector
  - `theme_demo.py` - Interactive theme preview dialog
  
- **Testing**
  - `test_qt_json_view_themes.py` - Unit tests for theme system
  - Tests for theme switching, color application, and custom themes

### Changed
- DataType classes now use `get_color()` instead of static `COLOR` attribute
- Colors are now dynamically retrieved from the current theme
- Item colors are refreshed automatically on theme change

### Technical Details
- Color themes use Qt `QColor` and `QBrush` for rendering
- Theme state is managed globally but can be changed per-view
- Backward compatible - existing code continues to work without themes
- No performance impact - colors are cached by theme objects

## [1.0.0] - Previous

### Features
- Tree-based JSON visualization
- Editable keys and values
- Custom data types (URLs, file paths, ranges, choices)
- Context menu actions
- Type-specific editors

---

## Usage Examples

### Basic theme switching:
```python
json_view.set_theme('monokai')
```

### Interactive theme selector:
```python
from modules.qt_json_view.theme_demo import show_theme_demo
show_theme_demo()
```

### Custom theme:
```python
from modules.qt_json_view.themes import Theme, THEMES
from qgis.PyQt.QtGui import QColor

class MyTheme(Theme):
    def __init__(self):
        super().__init__("My Theme")
        self.colors = {
            'string': QColor("#00FF00"),
            # ... other colors
        }

THEMES['my_theme'] = MyTheme()
json_view.set_theme('my_theme')
```

## Migration Guide

### For existing code:
No changes required! The default theme maintains the original black text appearance.

### To add theme support:
```python
# Old code (still works):
json_view = JsonView(json_model)

# New code with theme:
json_view = JsonView(json_model)
json_view.set_theme('monokai')  # Add this line
```

### For custom DataType classes:
```python
# Add THEME_COLOR_KEY to your custom DataType:
class MyCustomType(DataType):
    THEME_COLOR_KEY = 'string'  # or any other color key
    
    def matches(self, data):
        # ... your logic
```

## Future Enhancements

Potential additions for future versions:
- Theme import/export (JSON/XML format)
- Per-view theme overrides
- Theme editor UI
- Light/dark mode auto-detection
- Color customization per data type
- Theme inheritance
- More built-in themes (Material, GitHub, Tokyo Night, etc.)
