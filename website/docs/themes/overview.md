---
sidebar_position: 1
---

# Themes Overview

FilterMate features a comprehensive theming system that automatically synchronizes with QGIS and provides enhanced color harmonization for optimal readability.

## Available Themes

FilterMate supports multiple themes to match your QGIS interface and personal preferences:

### Auto Theme
**Recommended** - Automatically detects and matches your active QGIS theme.

- Detects QGIS dark/light mode
- Seamless integration with QGIS interface
- Updates automatically when QGIS theme changes

### Default Theme
Clean, professional light theme with excellent readability.

- **Background**: Light gray frames (#EFEFEF), white widgets (#FFFFFF)
- **Text**: High contrast (17.4:1 ratio for primary text)
- **Accent**: Deep blue (#1565C0) for interactive elements
- **Best for**: General use, long work sessions

### Dark Theme
Easy on the eyes for low-light environments.

- **Background**: Dark backgrounds with subtle contrast
- **Text**: Light text optimized for dark backgrounds
- **Accent**: Brighter colors for visibility
- **Best for**: Night work, reduced eye strain

### Light Theme
Maximum brightness theme for bright environments.

- **Background**: Pure white frames, subtle gray widgets
- **Text**: Maximum contrast (21:1 ratio)
- **Accent**: Saturated colors for visibility
- **Best for**: Bright offices, outdoor work

## Theme Configuration

### Changing Theme

You can change the theme in two ways:

**1. Via Configuration Tab:**
1. Open FilterMate dockwidget
2. Go to Configuration tab
3. Navigate to `APP` → `DOCKWIDGET` → `COLORS` → `ACTIVE_THEME`
4. Select from dropdown: `auto`, `default`, `dark`, `light`
5. Theme applies instantly (no restart required)

**2. Via config.json:**
```json
{
  "APP": {
    "DOCKWIDGET": {
      "COLORS": {
        "ACTIVE_THEME": {
          "value": "auto",
          "choices": ["auto", "default", "dark", "light"]
        }
      }
    }
  }
}
```

### Theme Source

Control where FilterMate gets theme information:

- **`config`**: Use theme specified in configuration
- **`qgis`**: Always follow QGIS theme (override config)
- **`system`**: Use system theme (Windows/macOS/Linux)

```json
{
  "THEME_SOURCE": {
    "value": "config",
    "choices": ["config", "qgis", "system"]
  }
}
```

## Color Harmonization

FilterMate v2.2.2+ includes enhanced color harmonization for better visual distinction:

### Key Improvements

- **+300% Frame Contrast**: Frames clearly separated from widgets
- **WCAG 2.1 Compliance**: AA/AAA accessibility standards met
- **Better Readability**: Primary text at 17.4:1 contrast ratio
- **Reduced Eye Strain**: Optimized color palette

### Color Schemes

Each theme defines:
- **Background colors** (frames, widgets, borders)
- **Font colors** (primary, secondary, disabled)
- **Accent colors** (primary, hover, pressed)
- **State colors** (success, warning, error, info)

See [Color Harmonization](./color-harmonization.md) for detailed specifications.

## QGIS Synchronization

### Automatic Detection

When `ACTIVE_THEME` is set to `auto`:

1. FilterMate detects active QGIS theme on startup
2. Maps QGIS theme to FilterMate theme:
   - QGIS dark themes → FilterMate `dark`
   - QGIS light themes → FilterMate `default`
3. Updates automatically when QGIS theme changes

### Supported QGIS Themes

FilterMate detects and maps these QGIS themes:

**Dark Themes:**
- Blend of Gray
- Night Mapping
- Custom dark themes

**Light Themes:**
- Default
- Custom light themes

## Theme Customization

### Via Configuration

All theme colors are configurable in `config.json`:

```json
{
  "COLORS": {
    "THEMES": {
      "default": {
        "BACKGROUND": ["#EFEFEF", "#FFFFFF", "#D0D0D0"],
        "FONT": ["#1A1A1A", "#4A4A4A", "#888888"],
        "PRIMARY": "#1565C0",
        "HOVER": "#1E88E5",
        "PRESSED": "#0D47A1",
        "SUCCESS": "#2E7D32",
        "WARNING": "#F57C00",
        "ERROR": "#C62828",
        "INFO": "#0277BD"
      }
    }
  }
}
```

### Creating Custom Themes

You can add custom themes to the configuration:

```json
{
  "THEMES": {
    "my_custom": {
      "BACKGROUND": ["#YOUR_FRAME", "#YOUR_WIDGET", "#YOUR_BORDER"],
      "FONT": ["#PRIMARY_TEXT", "#SECONDARY_TEXT", "#DISABLED_TEXT"],
      "PRIMARY": "#YOUR_ACCENT",
      // ... other colors
    }
  }
}
```

Then set `ACTIVE_THEME` to `my_custom`.

## JSON Tree View Themes

The Configuration tab JSON viewer supports multiple syntax highlighting themes:

### Available Themes

- **Default**: Black text for all types
- **Monokai**: Dark theme with vibrant colors (Sublime Text style)
- **Solarized Light**: Warm colors on light background
- **Solarized Dark**: Warm colors on dark background
- **Nord**: Cool Arctic-inspired colors
- **Dracula**: Dark with saturated colors (popular in code editors)
- **One Dark**: Atom/VS Code style
- **Gruvbox**: Retro warm colors

### Changing JSON Theme

```python
# In Python console or custom code
json_view.set_theme('monokai')
```

Currently, JSON themes are set programmatically. UI selector coming in future version.

## Accessibility

FilterMate themes are designed with accessibility in mind:

### WCAG 2.1 Compliance

- **Primary Text**: 17.4:1 contrast (AAA) in default theme
- **Secondary Text**: 8.86:1 contrast (AAA) in default theme
- **Disabled Text**: 4.6:1 contrast (AA) in default theme
- **UI Elements**: 3:1 minimum contrast for borders

### Benefits

- ✅ Reduced eye strain with optimized contrasts
- ✅ Clear visual hierarchy
- ✅ Better for users with mild visual impairments
- ✅ Long work session comfort

See [Accessibility](../advanced/accessibility.md) for detailed information.

## Technical Details

### Theme Loading

Themes are loaded via `modules/ui_styles.py`:

```python
from modules.ui_styles import StyleLoader

# Load and apply theme
StyleLoader.set_theme_from_config(
    widget,        # QWidget to style
    config_data,   # Configuration dictionary
    theme_name     # 'auto', 'default', 'dark', 'light'
)

# Detect QGIS theme
detected = StyleLoader.detect_qgis_theme()
# Returns: 'dark' or 'default'
```

### QSS Stylesheets

FilterMate uses Qt Style Sheets (QSS) with placeholders:

```qss
/* resources/styles/default.qss */
QFrame {
    background-color: {BACKGROUND[0]};
    color: {FONT[0]};
    border: 1px solid {BACKGROUND[2]};
}

QLineEdit {
    background-color: {BACKGROUND[1]};
    color: {FONT[0]};
    border: 1px solid {BACKGROUND[2]};
}
```

Placeholders are replaced with actual colors from theme configuration.

## Best Practices

### Choosing a Theme

- **Auto**: Recommended for most users - matches QGIS automatically
- **Default**: Best for bright environments and long work sessions
- **Dark**: Best for low-light environments and night work
- **Light**: Best for very bright offices or outdoor use

### Performance

Themes have no performance impact:
- Loaded once on startup
- Cached in memory
- Instant switching (no restart required)

### Consistency

For consistent experience across QGIS:
1. Set `ACTIVE_THEME` to `auto`
2. Set `THEME_SOURCE` to `qgis`
3. FilterMate will always match QGIS interface

## Troubleshooting

### Theme Not Applying

**Problem**: Changed theme but UI doesn't update

**Solutions:**
1. Ensure you're editing configuration in **Configuration tab** (auto-applies)
2. If editing `config.json` directly, restart QGIS
3. Check console for error messages

### Colors Look Wrong

**Problem**: Theme colors don't look as expected

**Solutions:**
1. Check `ACTIVE_THEME` value is valid: `auto`, `default`, `dark`, `light`
2. Verify theme configuration in `config.json` has all required color keys
3. Try resetting to default: Delete custom theme section from config

### QGIS Theme Not Detected

**Problem**: Auto theme not matching QGIS

**Solutions:**
1. Ensure `THEME_SOURCE` is set to `qgis` or `config`
2. Check if QGIS theme name is recognized (see supported themes above)
3. Set theme explicitly if detection fails

## References

- [Color Harmonization](./color-harmonization.md) - Detailed color specifications
- [Configuration Reactivity](../advanced/configuration-reactivity.md) - How theme switching works
- [Accessibility](../advanced/accessibility.md) - WCAG compliance details
- [Backend API](../api/backend-api.md) - Technical architecture

---

**Related Documentation:**
- Source: `docs/THEMES.md`
- Implementation: `modules/ui_styles.py`
- Styles: `resources/styles/`
