---
sidebar_position: 3
---

# Custom Themes

Create your own color themes for FilterMate's JSON editor to match your personal style or brand guidelines. This guide covers everything from basic theme creation to advanced QSS styling.

:::tip Quick Start
Copy an existing theme as a template, modify colors, and register it - you can have a custom theme running in under 5 minutes!
:::

## Theme Architecture

### Theme Class Structure

Every theme inherits from the `Theme` base class:

```python
from modules.qt_json_view.themes import Theme
from qgis.PyQt.QtGui import QColor

class MyCustomTheme(Theme):
    def __init__(self):
        super().__init__("My Custom Theme")  # Display name
        
        # Define colors for each JSON data type
        self.colors = {
            'none': QColor("#999999"),       # null values
            'string': QColor("#00FF00"),     # text strings
            'integer': QColor("#FF00FF"),    # whole numbers
            'float': QColor("#FF00FF"),      # decimal numbers
            'boolean': QColor("#FF8800"),    # true/false
            'list': QColor("#FFFF00"),       # arrays
            'dict': QColor("#00FFFF"),       # objects
            'url': QColor("#00FF88"),        # URLs
            'filepath': QColor("#00FF88"),   # file paths
            'range': QColor("#FF00FF"),      # ranges
            'choices': QColor("#00FF00"),    # choice types
        }
```

### Required Color Keys

All 11 color keys must be defined:

| Key | Data Type | Example Value | Description |
|-----|----------|---------------|-------------|
| `none` | NoneType | `null`, `None` | Null/undefined values |
| `string` | StrType | `"hello"` | Text strings |
| `integer` | IntType | `42` | Whole numbers |
| `float` | FloatType | `3.14` | Decimal numbers |
| `boolean` | BoolType | `true`, `false` | Boolean values |
| `list` | ListType | `[1, 2, 3]` | Arrays/lists |
| `dict` | DictType | `{"key": "value"}` | Objects/dictionaries |
| `url` | UrlType | `"https://..."` | URL strings |
| `filepath` | FilepathType | `"/path/to/file"` | File paths |
| `range` | RangeType | `{"start": 0}` | Range objects |
| `choices` | ChoicesType | `["opt1", "opt2"]` | Choice arrays |

:::warning Missing Keys
If any color key is missing, the theme will fail to load and fall back to the default theme.
:::

## Creating Your First Theme

### Step 1: Create Theme File

Create a new Python file in `modules/qt_json_view/themes/`:

```python
# modules/qt_json_view/themes/my_theme.py

from .base import Theme
from qgis.PyQt.QtGui import QColor

class MyTheme(Theme):
    def __init__(self):
        super().__init__("My Awesome Theme")
        
        self.colors = {
            'none': QColor("#A0A0A0"),
            'string': QColor("#98C379"),
            'integer': QColor("#D19A66"),
            'float': QColor("#D19A66"),
            'boolean': QColor("#C678DD"),
            'list': QColor("#61AFEF"),
            'dict': QColor("#56B6C2"),
            'url': QColor("#4DB8E8"),
            'filepath': QColor("#98C379"),
            'range': QColor("#E06C75"),
            'choices': QColor("#E5C07B"),
        }
```

### Step 2: Register Theme

Add your theme to the themes registry in `modules/qt_json_view/themes/__init__.py`:

```python
from .my_theme import MyTheme

# Add to THEMES dictionary
THEMES['my_theme'] = MyTheme()
```

### Step 3: Test Theme

Test in QGIS Python Console:

```python
from modules.qt_json_view import view, model

# Load some test data
data = {
    "string": "Hello World",
    "number": 42,
    "float": 3.14,
    "bool": True,
    "list": [1, 2, 3],
    "object": {"nested": "value"}
}

# Create view
json_model = model.JsonModel(data)
json_view = view.JsonView(json_model)

# Apply your theme
json_view.set_theme('my_theme')

# Show view
json_view.show()
```

## Example: GitHub Theme

Here's a complete example of a GitHub-inspired theme:

```python
# modules/qt_json_view/themes/github_theme.py

from .base import Theme
from qgis.PyQt.QtGui import QColor

class GitHubTheme(Theme):
    """
    GitHub-inspired theme with clean, professional colors.
    Optimized for light backgrounds.
    """
    
    def __init__(self):
        super().__init__("GitHub")
        
        # GitHub color palette
        self.colors = {
            # Primitives
            'none': QColor("#6A737D"),        # Gray 6
            'string': QColor("#032F62"),      # Blue 9
            'integer': QColor("#005CC5"),     # Blue 5
            'float': QColor("#005CC5"),       # Blue 5
            'boolean': QColor("#D73A49"),     # Red 5
            
            # Collections
            'list': QColor("#6F42C1"),        # Purple 5
            'dict': QColor("#22863A"),        # Green 6
            
            # Special types
            'url': QColor("#0366D6"),         # Blue 6
            'filepath': QColor("#032F62"),    # Blue 9
            'range': QColor("#E36209"),       # Orange 6
            'choices': QColor("#6F42C1"),     # Purple 5
        }
    
    def get_description(self):
        """Optional: provide theme description"""
        return "Clean, professional theme inspired by GitHub's color palette"
    
    def get_background_color(self):
        """Optional: suggest background color"""
        return QColor("#FFFFFF")
    
    def get_recommended_for(self):
        """Optional: usage recommendations"""
        return ["light mode", "professional use", "documentation"]
```

## Advanced Features

### Color Utilities

Use Qt's `QColor` methods for advanced color manipulation:

```python
from qgis.PyQt.QtGui import QColor

# Create colors from different formats
color1 = QColor("#FF5733")           # Hex
color2 = QColor(255, 87, 51)         # RGB
color3 = QColor(255, 87, 51, 200)    # RGBA with alpha

# Color manipulation
darker = color1.darker(150)          # 50% darker
lighter = color1.lighter(150)        # 50% lighter
with_alpha = color1.setAlpha(128)    # Semi-transparent

# Color information
print(f"Red: {color1.red()}")
print(f"Green: {color1.green()}")
print(f"Blue: {color1.blue()}")
print(f"Hue: {color1.hue()}")
print(f"Saturation: {color1.saturation()}")
print(f"Value: {color1.value()}")
```

### Dynamic Colors Based on QGIS Theme

Adapt your theme to match QGIS:

```python
from qgis.PyQt.QtWidgets import QApplication
from qgis.PyQt.QtGui import QPalette, QColor

class AdaptiveTheme(Theme):
    def __init__(self):
        super().__init__("Adaptive Theme")
        
        # Get QGIS palette
        palette = QApplication.palette()
        
        # Base colors on QGIS theme
        bg = palette.color(QPalette.Base)
        fg = palette.color(QPalette.Text)
        
        # Determine if dark theme
        is_dark = bg.value() < 128
        
        if is_dark:
            # Dark theme colors
            self.colors = {
                'none': QColor("#808080"),
                'string': QColor("#CE9178"),
                'integer': QColor("#B5CEA8"),
                # ... more colors
            }
        else:
            # Light theme colors
            self.colors = {
                'none': QColor("#808080"),
                'string': QColor("#A31515"),
                'integer': QColor("#098658"),
                # ... more colors
            }
```

### Color Palette Generation

Generate harmonious color palettes programmatically:

```python
from qgis.PyQt.QtGui import QColor

class HarmoniousTheme(Theme):
    def __init__(self, base_hue=200):
        super().__init__(f"Harmonious {base_hue}")
        
        # Generate analogous colors
        self.colors = {
            'none': self._create_color(base_hue, 0.2, 0.5),
            'string': self._create_color(base_hue, 0.7, 0.6),
            'integer': self._create_color(base_hue + 30, 0.7, 0.6),
            'float': self._create_color(base_hue + 30, 0.7, 0.6),
            'boolean': self._create_color(base_hue + 60, 0.7, 0.6),
            'list': self._create_color(base_hue - 30, 0.7, 0.6),
            'dict': self._create_color(base_hue - 60, 0.7, 0.6),
            'url': self._create_color(base_hue + 120, 0.7, 0.6),
            'filepath': self._create_color(base_hue, 0.7, 0.7),
            'range': self._create_color(base_hue + 180, 0.7, 0.6),
            'choices': self._create_color(base_hue + 90, 0.7, 0.6),
        }
    
    def _create_color(self, hue, saturation, value):
        """Create QColor from HSV values"""
        color = QColor()
        color.setHsv(
            hue % 360,           # Hue (0-359)
            int(saturation * 255),  # Saturation (0-255)
            int(value * 255)        # Value (0-255)
        )
        return color
```

## QSS Styling Integration

Themes can provide Qt Style Sheets (QSS) for complete UI customization:

### Basic QSS

```python
class StyledTheme(Theme):
    def __init__(self):
        super().__init__("Styled Theme")
        
        self.colors = {
            # ... color definitions
        }
        
        # Optional: provide QSS stylesheet
        self.stylesheet = """
            QTreeView {
                background-color: #2D2D30;
                color: #CCCCCC;
                border: 1px solid #3E3E42;
                selection-background-color: #094771;
            }
            
            QTreeView::item:hover {
                background-color: #3E3E42;
            }
            
            QTreeView::item:selected {
                background-color: #094771;
                color: #FFFFFF;
            }
            
            QHeaderView::section {
                background-color: #2D2D30;
                color: #CCCCCC;
                border: none;
                padding: 4px;
            }
        """
    
    def apply_stylesheet(self, widget):
        """Apply QSS to widget"""
        widget.setStyleSheet(self.stylesheet)
```

### QSS with Placeholders

Use placeholders for dynamic color injection:

```python
class DynamicStyledTheme(Theme):
    def __init__(self):
        super().__init__("Dynamic Styled")
        
        self.colors = {
            'none': QColor("#999999"),
            'string': QColor("#98C379"),
            # ... more colors
        }
        
        # QSS with placeholders
        self.stylesheet_template = """
            QTreeView {
                background-color: %(bg_color)s;
                color: %(text_color)s;
                selection-background-color: %(selection_color)s;
            }
            
            QTreeView::item:hover {
                background-color: %(hover_color)s;
            }
        """
    
    def get_stylesheet(self, bg_color, text_color, selection_color, hover_color):
        """Generate QSS with actual colors"""
        return self.stylesheet_template % {
            'bg_color': bg_color,
            'text_color': text_color,
            'selection_color': selection_color,
            'hover_color': hover_color,
        }
```

## Color Theory Guidelines

### Contrast Ratios

Ensure accessibility with proper contrast:

```python
def calculate_contrast_ratio(color1, color2):
    """
    Calculate WCAG contrast ratio between two colors.
    """
    def get_luminance(color):
        rgb = [color.red(), color.green(), color.blue()]
        rgb = [x / 255.0 for x in rgb]
        rgb = [
            x / 12.92 if x <= 0.03928 
            else ((x + 0.055) / 1.055) ** 2.4 
            for x in rgb
        ]
        return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    
    l1 = get_luminance(color1)
    l2 = get_luminance(color2)
    
    lighter = max(l1, l2)
    darker = min(l1, l2)
    
    return (lighter + 0.05) / (darker + 0.05)

# Example usage
bg = QColor("#FFFFFF")
fg = QColor("#000000")
ratio = calculate_contrast_ratio(bg, fg)
print(f"Contrast ratio: {ratio:.2f}:1")

# WCAG requirements:
# - AA: 4.5:1 minimum (7:1 for AAA)
# - Large text: 3:1 minimum (4.5:1 for AAA)
```

### Color Harmony

Choose harmonious color combinations:

```python
class HarmonyTheme(Theme):
    """Theme using complementary colors"""
    
    def __init__(self, base_hue=200):
        super().__init__("Harmony Theme")
        
        # Complementary color (opposite on color wheel)
        complement = (base_hue + 180) % 360
        
        # Triadic colors (120° apart)
        triad1 = (base_hue + 120) % 360
        triad2 = (base_hue + 240) % 360
        
        # Split-complementary
        split1 = (base_hue + 150) % 360
        split2 = (base_hue + 210) % 360
        
        self.colors = {
            'string': self._hsv(base_hue, 0.7, 0.7),
            'integer': self._hsv(complement, 0.7, 0.7),
            'boolean': self._hsv(triad1, 0.7, 0.7),
            'list': self._hsv(triad2, 0.7, 0.7),
            'dict': self._hsv(split1, 0.7, 0.7),
            # ... more colors
        }
    
    def _hsv(self, h, s, v):
        """Helper to create QColor from HSV"""
        color = QColor()
        color.setHsv(int(h), int(s * 255), int(v * 255))
        return color
```

## Testing Your Theme

### Visual Testing

```python
# test_theme.py

from modules.qt_json_view import view, model
from modules.qt_json_view.themes import THEMES

def test_theme(theme_name):
    """Visual test for theme"""
    
    # Comprehensive test data
    test_data = {
        "null_value": None,
        "string": "Hello, World!",
        "integer": 42,
        "float": 3.14159,
        "boolean_true": True,
        "boolean_false": False,
        "list": [1, 2, 3, "four", 5.0],
        "nested_dict": {
            "key1": "value1",
            "key2": 123,
            "key3": [True, False]
        },
        "url": "https://example.com/path",
        "filepath": "/path/to/file.txt",
        "range": {"start": 0, "end": 10, "step": 2},
        "choices": ["option1", "option2", "option3"]
    }
    
    # Create view
    json_model = model.JsonModel(test_data, editable_keys=True, editable_values=True)
    json_view = view.JsonView(json_model)
    
    # Apply theme
    success = json_view.set_theme(theme_name)
    
    if success:
        print(f"✓ Theme '{theme_name}' applied successfully")
        json_view.show()
        json_view.expandAll()
    else:
        print(f"✗ Theme '{theme_name}' failed to apply")

# Test all themes
for theme_key in THEMES.keys():
    test_theme(theme_key)
```

### Automated Testing

```python
import unittest
from modules.qt_json_view.themes import THEMES, Theme

class TestTheme(unittest.TestCase):
    
    def test_all_themes_have_required_colors(self):
        """Ensure all themes define required color keys"""
        required_keys = [
            'none', 'string', 'integer', 'float', 'boolean',
            'list', 'dict', 'url', 'filepath', 'range', 'choices'
        ]
        
        for theme_key, theme in THEMES.items():
            with self.subTest(theme=theme_key):
                for key in required_keys:
                    self.assertIn(key, theme.colors,
                        f"Theme '{theme_key}' missing color key '{key}'")
    
    def test_theme_colors_are_valid(self):
        """Ensure all theme colors are valid QColor objects"""
        from qgis.PyQt.QtGui import QColor
        
        for theme_key, theme in THEMES.items():
            with self.subTest(theme=theme_key):
                for color_key, color in theme.colors.items():
                    self.assertIsInstance(color, QColor,
                        f"Theme '{theme_key}' color '{color_key}' is not QColor")
                    self.assertTrue(color.isValid(),
                        f"Theme '{theme_key}' color '{color_key}' is invalid")

if __name__ == '__main__':
    unittest.main()
```

## Contributing Themes

Want to share your theme with the FilterMate community?

### Submission Checklist

- [ ] All 11 color keys defined
- [ ] Colors are accessible (contrast ratio > 4.5:1)
- [ ] Theme tested with sample data
- [ ] Documentation added (description, best use cases)
- [ ] Theme name is unique
- [ ] Code follows FilterMate style guide

### Submission Process

1. **Create theme** following guidelines above
2. **Test thoroughly** with various data types
3. **Document theme** with description and recommendations
4. **Submit pull request** to FilterMate repository
5. **Include screenshot** of theme in action

### Theme Template

```python
# modules/qt_json_view/themes/contributor_theme.py

from .base import Theme
from qgis.PyQt.QtGui import QColor

class ContributorTheme(Theme):
    """
    [Theme Name] Theme
    
    Description:
        [Brief description of theme aesthetic and purpose]
    
    Best for:
        - [Use case 1]
        - [Use case 2]
    
    Author: [Your Name]
    Date: [Creation Date]
    Version: 1.0.0
    """
    
    def __init__(self):
        super().__init__("[Theme Display Name]")
        
        self.colors = {
            'none': QColor("#RRGGBB"),
            'string': QColor("#RRGGBB"),
            'integer': QColor("#RRGGBB"),
            'float': QColor("#RRGGBB"),
            'boolean': QColor("#RRGGBB"),
            'list': QColor("#RRGGBB"),
            'dict': QColor("#RRGGBB"),
            'url': QColor("#RRGGBB"),
            'filepath': QColor("#RRGGBB"),
            'range': QColor("#RRGGBB"),
            'choices': QColor("#RRGGBB"),
        }
    
    def get_description(self):
        return "[Detailed theme description]"
    
    def get_recommended_for(self):
        return ["[usage type 1]", "[usage type 2]"]
```

## Troubleshooting

### Theme Not Loading

**Symptom:** Custom theme doesn't appear in dropdown

**Solutions:**
1. Check theme is registered in `__init__.py`
2. Verify all required color keys defined
3. Restart QGIS to reload modules
4. Check Python console for import errors

### Colors Not Applying

**Symptom:** Theme selected but colors don't change

**Solutions:**
1. Verify QColor objects are valid
2. Check for typos in color keys
3. Ensure `super().__init__()` called
4. Try refreshing the JSON view

### Theme Performance Issues

**Symptom:** UI slow with custom theme

**Solutions:**
1. Avoid complex calculations in `__init__`
2. Don't modify colors dynamically on each render
3. Cache computed colors
4. Remove heavy QSS rules

## See Also

- [Available Themes](./available-themes.md) - Built-in theme gallery
- [Color Harmonization](./color-harmonization.md) - Color theory and design
- [UI Configuration](../advanced/configuration.md) - UI customization
- [API Reference](../api/ui-components.md) - Theme API documentation

---

**Last Updated:** December 8, 2025  
**Plugin Version:** 2.2.3  
**Theme API:** v2.0
