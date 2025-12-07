# FilterMate Theme Synchronization

## Overview

FilterMate now automatically synchronizes its theme with QGIS, providing a seamless and consistent user experience.

## How It Works

### Automatic Theme Detection

The plugin analyzes QGIS's palette to detect whether a dark or light theme is active:

1. **Extracts background color** from QGIS palette
2. **Calculates luminance** using the formula: `(0.299*R + 0.587*G + 0.114*B)`
3. **Determines theme**:
   - Luminance < 128 → **Dark theme**
   - Luminance ≥ 128 → **Light theme**

### Configuration

#### Set Theme Mode in `config.json`:

```json
{
    "APP": {
        "DOCKWIDGET": {
            "COLORS": {
                "ACTIVE_THEME": "auto"
            }
        }
    }
}
```

#### Available Theme Options:

| Value | Behavior |
|-------|----------|
| `"auto"` | ✅ **Automatically sync with QGIS theme** (recommended) |
| `"default"` | Force light theme |
| `"dark"` | Force dark theme |
| `"light"` | Force high-contrast light theme |

## Benefits

✅ **Consistency** - Plugin matches QGIS appearance  
✅ **Automatic** - No manual configuration needed  
✅ **Accessible** - Respects user's theme preference  
✅ **Flexible** - Can override with manual selection  

## Theme Detection Details

### QGIS Light Theme Detection
```
Background RGB: (240, 240, 240)
Luminance: 239.4 → Light theme
Plugin applies: 'default' theme
```

### QGIS Dark Theme Detection
```
Background RGB: (50, 50, 50)
Luminance: 49.9 → Dark theme
Plugin applies: 'dark' theme
```

## Manual Override

If you prefer a specific theme regardless of QGIS:

1. Open `config/config.json`
2. Change `"ACTIVE_THEME"` to `"default"`, `"dark"`, or `"light"`
3. Restart plugin or reload QGIS

## Technical Implementation

### Code Location
- **Detection Logic**: `modules/ui_styles.py` → `StyleLoader.detect_qgis_theme()`
- **Theme Application**: `filter_mate_dockwidget.py` → `manage_ui_style()`

### API Usage

```python
from modules.ui_styles import StyleLoader

# Auto-detect and apply QGIS theme
theme = StyleLoader.detect_qgis_theme()  # Returns 'dark' or 'default'

# Apply with auto-detection
StyleLoader.set_theme_from_config(widget, config_data, theme='auto')

# Or let it auto-detect from config
StyleLoader.set_theme_from_config(widget, config_data)  # Uses ACTIVE_THEME
```

## Troubleshooting

### Plugin doesn't match QGIS theme

**Check console output:**
```
FilterMate: Detected QGIS dark theme (luminance: 45)
FilterMate: Applied theme 'dark' from config
```

**Solution:**
1. Verify `ACTIVE_THEME` is set to `"auto"` in config.json
2. Restart the plugin
3. Check QGIS Python console for detection messages

### Want to force a specific theme

Set `ACTIVE_THEME` to a fixed value:
```json
"ACTIVE_THEME": "dark"  // Always use dark theme
```

## Custom Themes

You can still create custom themes and use auto-detection:

```json
"THEMES": {
    "custom_dark": { ... },
    "custom_light": { ... }
}
```

Then manually set:
```json
"ACTIVE_THEME": "custom_dark"
```

## Future Enhancements

🔜 Real-time theme switching when QGIS theme changes  
🔜 Per-user theme preferences  
🔜 Theme preview in settings dialog  

---

**Recommendation:** Keep `ACTIVE_THEME: "auto"` for the best experience!
