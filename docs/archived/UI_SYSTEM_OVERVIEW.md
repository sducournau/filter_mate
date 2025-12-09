# FilterMate UI System - Overview

**Last Updated:** December 7, 2025  
**Version:** 2.1.0

---

## 🎨 UI System Architecture

FilterMate features a modern, adaptive UI system that automatically adjusts to screen size and QGIS theme preferences.

### Core Components

```
modules/
├── ui_config.py           # Display profiles and dimension configurations
├── ui_styles.py           # Theme colors and style generation
├── ui_widget_utils.py     # Widget configuration utilities
├── ui_elements.py         # UI element creation and management
├── ui_elements_helpers.py # Helper functions for UI operations
└── qt_json_view/          # JSON viewer with theme support
```

---

## 📐 Display Profiles

FilterMate supports two adaptive display profiles:

### Compact Mode
**For:** Laptops, tablets, small screens  
**Features:**
- Reduced spacing and margins
- Smaller widget dimensions
- Optimized for screen real estate
- Height: ~600-800px

### Normal Mode  
**For:** Desktop monitors, large screens  
**Features:**
- Comfortable spacing and margins
- Generous widget dimensions
- Maximum readability
- Height: ~800-1000px

### Configuration

```json
// config/config.json
{
    "APP": {
        "DOCKWIDGET": {
            "UI_PROFILE": "compact"  // or "normal"
        }
    }
}
```

```python
# Programmatic control
from modules.ui_config import UIConfig, DisplayProfile

UIConfig.set_profile(DisplayProfile.COMPACT)
UIConfig.set_profile(DisplayProfile.NORMAL)
```

---

## 🌓 Theme System

FilterMate automatically synchronizes with QGIS interface themes and provides custom theme support.

### Supported Themes
- **Default** - QGIS default light theme
- **Blend of Gray** - QGIS gray theme
- **Night Mapping** - QGIS dark theme
- **Monokai** - Custom dark theme with syntax highlighting
- **Nord** - Popular Nordic color palette
- **Solarized Dark/Light** - Precision color schemes

### Theme Synchronization

Themes automatically sync when:
- QGIS theme changes
- Plugin is loaded
- User manually refreshes theme

### Theme API

```python
from modules.ui_styles import ThemeManager

# Get current theme
current = ThemeManager.detect_qgis_theme()

# Apply theme to widget
ThemeManager.apply_theme_to_widget(widget, "monokai")

# Get available themes
themes = ThemeManager.get_available_themes()
```

---

## 🧩 Widget System

### Dynamic Widget Configuration

All widgets support dynamic configuration based on:
- Display profile (compact/normal)
- Current theme
- Screen resolution
- User preferences

### Common Widget Patterns

```python
from modules.ui_widget_utils import configure_widget
from modules.ui_config import UIConfig

# Configure widget with current profile
configure_widget(
    widget=my_widget,
    min_height=UIConfig.get_dimension('widget_height'),
    max_height=UIConfig.get_dimension('widget_max_height')
)
```

### Spacing & Margins

All spacing follows profile-specific rules:
- **Compact:** 3-4px spacing, 3-6px margins
- **Normal:** 6-9px spacing, 6-9px margins

---

## 📦 GroupBox Standardization

All GroupBoxes follow consistent patterns:

### Single Selection
```python
# Compact: 50-70px height
# Normal: 60-80px height
- Single line edit or combo box
- Minimal spacing (3-4px)
```

### Multiple Selection  
```python
# Compact: 65-100px height
# Normal: 75-110px height
- Multi-select widgets
- Filter + display fields
```

### Custom Selection
```python
# Compact: 90-150px height
# Normal: 100-160px height
- Expression builder
- Complex input widgets
```

---

## 🔧 Testing & Validation

### Testing Checklist
- ✅ Both display profiles (compact/normal)
- ✅ All QGIS themes (light/gray/dark)
- ✅ Different screen resolutions
- ✅ Theme switching without restart
- ✅ Widget visibility and overlap
- ✅ Consistent spacing and margins

### Test Guide
See [UI_TESTING_GUIDE.md](UI_TESTING_GUIDE.md) for complete testing procedures.

### Style Testing
See [UI_STYLES_TESTING_CHECKLIST.md](UI_STYLES_TESTING_CHECKLIST.md) for style-specific tests.

---

## 📖 Related Documentation

### Active Documentation
- **[UI_DYNAMIC_CONFIG.md](UI_DYNAMIC_CONFIG.md)** - Dynamic configuration system details
- **[THEMES.md](THEMES.md)** - Theme system and JSON viewer themes
- **[UI_TESTING_GUIDE.md](UI_TESTING_GUIDE.md)** - Testing procedures
- **[UI_STYLES_TESTING_CHECKLIST.md](UI_STYLES_TESTING_CHECKLIST.md)** - Style testing checklist

### Archived Documentation
- **[archived/ui-improvements/](archived/ui-improvements/)** - Historical UI improvements
  - Compact mode harmonization
  - Style refactoring
  - Theme implementation details

---

## 🚀 Key Features

### Adaptive Dimensions
- Automatic adjustment based on screen size
- Profile switching without restart
- Persistent user preferences

### Theme Sync
- Automatic QGIS theme detection
- Real-time theme switching
- Custom theme support

### Consistent Spacing
- Standardized margins and spacing
- Profile-specific adjustments
- Visual harmony across all widgets

### Modern Aesthetics
- Clean, professional appearance
- Proper contrast and readability
- Accessibility considerations

---

## 🔮 Future Enhancements (Optional)

- Additional custom themes
- User-defined color schemes
- High contrast accessibility mode
- Font size customization
- Layout presets

**Note:** Current UI system is complete and production-ready. Future enhancements are optional improvements.

---

**Status:** ✅ **Production Ready - December 2025**

Complete UI system with adaptive profiles, theme synchronization, and comprehensive testing.
