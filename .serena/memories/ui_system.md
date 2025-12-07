# UI System Documentation - FilterMate v2.1.0

## Overview

FilterMate v2.1.0 implements a comprehensive, adaptive UI system with dynamic dimensions, theme synchronization, and responsive design.

## Architecture

### Core UI Components

```
modules/
├── ui_config.py              # Dynamic dimensions configuration
├── ui_styles.py              # Theme management and QSS generation
├── ui_elements.py            # UI element creation and management
├── ui_elements_helpers.py    # Helper functions for UI operations
├── ui_widget_utils.py        # Widget utility functions
├── widgets.py                # Custom widget implementations
└── signal_utils.py           # Signal management utilities
```

## Dynamic Dimensions System

### Resolution Detection

**Threshold:** 1920x1080 pixels

**Modes:**
- **Compact Mode** (< 1920x1080): Optimized for laptops and small screens
- **Normal Mode** (≥ 1920x1080): Comfortable spacing for large displays

**Implementation:** `modules/ui_config.py`

### Dimension Categories

1. **Tool Buttons**
   - Compact: 18×18px (16px icons)
   - Normal: 24×24px (22px icons)

2. **Input Widgets** (ComboBox, LineEdit)
   - Compact: 24px height
   - Normal: 30px height

3. **Frames** (Exploring, Filtering)
   - Compact: 150px min height
   - Normal: 180px min height

4. **Widget Keys** (Button columns)
   - Compact: 45-90px width
   - Normal: 55-110px width

5. **GroupBox**
   - Compact: 40px min height
   - Normal: 50px min height

6. **Layouts**
   - Spacing - Compact: 3px / Normal: 6px
   - Margins - Compact: 2px / Normal: 4px

7. **Separators**
   - Compact: 1px
   - Normal: 2px

8. **Font Sizes**
   - Compact: 8-9pt
   - Normal: 9-10pt

### Application Method

```python
from modules.ui_config import UIConfig

# Initialize
ui_config = UIConfig()

# Apply dimensions
ui_config.apply_dynamic_dimensions(dockwidget)
```

**Auto-Detection:** Dimensions applied automatically on plugin initialization

**Benefit:** 15-20% vertical space savings in compact mode

## Theme System

### Theme Synchronization

**Auto-Detection:** Detects current QGIS theme on startup and changes

**Supported Themes:**
- Blend of Gray (Light)
- Night Mapping (Dark)
- Custom themes (auto-detect light/dark)

**Implementation:** `modules/ui_styles.py`

### Theme Categories

1. **Background Colors**
   - Main backgrounds
   - Frame backgrounds
   - GroupBox backgrounds

2. **Text Colors**
   - Primary text
   - Secondary text
   - Disabled text

3. **Border Colors**
   - Frame borders
   - Focus borders
   - Separator colors

4. **Interactive Elements**
   - Button styles
   - Hover states
   - Active/checked states

### QSS Generation

**Dynamic QSS:** Generated at runtime based on detected theme

```python
from modules.ui_styles import UIStyles

# Get QSS for current theme
qss = UIStyles.get_qss_for_theme('Night Mapping')

# Apply to widget
widget.setStyleSheet(qss)
```

### Theme Files

**Location:** `resources/styles/`
- `default.qss`: Base styles
- `light_theme.qss`: Light theme overrides
- `dark_theme.qss`: Dark theme overrides

## Custom Widgets

### 1. QgsCheckableComboBoxLayer

**Purpose:** Layer selection with checkboxes

**Features:**
- Multi-selection support
- Custom icons per layer
- Right-click context menu
- Geometry type filtering

**Location:** `modules/widgets.py`

**Key Methods:**
- `addItem(icon, text, data)`: Add layer
- `checkedItems()`: Get selected layers
- `select_by_geometry(geom_type)`: Filter by geometry

### 2. QgsCheckableComboBoxFeaturesListPickerWidget

**Purpose:** Feature selection with live updates

**Features:**
- Async population (QgsTask)
- Live search/filter
- Checkbox selection
- Icon display

**Location:** `modules/widgets.py`

### 3. Custom JSON Tree View

**Purpose:** Display layer properties in tree format

**Features:**
- Expandable tree structure
- Theme-aware styling
- Copy/export functionality

**Location:** `modules/qt_json_view/`

## Signal Management

### SignalBlocker

**Purpose:** Safely block/unblock Qt signals with automatic cleanup

**Usage:**
```python
from modules.signal_utils import SignalBlocker

with SignalBlocker(widget):
    # Signals blocked here
    widget.setValue(new_value)
# Signals automatically restored
```

### SignalConnection

**Purpose:** Temporary signal connections

**Usage:**
```python
from modules.signal_utils import SignalConnection

with SignalConnection(button.clicked, handler):
    # Signal connected only in this block
    button.click()
```

### SignalBlockerGroup

**Purpose:** Block signals for multiple widgets

**Usage:**
```python
from modules.signal_utils import SignalBlockerGroup

widgets = [combobox1, combobox2, lineedit]
with SignalBlockerGroup(widgets):
    # All widgets blocked
    update_widgets(widgets)
```

## UI Element Creation

### Helper Functions

**Location:** `modules/ui_elements_helpers.py`

**Key Functions:**
- `create_label(text, parent)`: Create styled label
- `create_button(text, icon, parent)`: Create button with icon
- `create_combobox(parent)`: Create combobox with theme
- `create_groupbox(title, parent)`: Create styled groupbox
- `create_frame(parent)`: Create themed frame

### Layout Helpers

**Location:** `modules/ui_widget_utils.py`

**Key Functions:**
- `create_horizontal_layout(spacing, margins)`: HBox layout
- `create_vertical_layout(spacing, margins)`: VBox layout
- `create_grid_layout(spacing, margins)`: Grid layout
- `add_stretch(layout)`: Add stretch to layout

## Responsive Design

### Minimum Sizes

**Dockwidget:**
- Minimum width: 421px
- Minimum height: 611px (compact) / 700px (normal)

**Frames:**
- Exploring frame: 150px (compact) / 180px (normal)
- Filtering frame: 150px (compact) / 180px (normal)

**Widgets:**
- ComboBox: 24px (compact) / 30px (normal)
- Buttons: 18px (compact) / 24px (normal)

### Stretch Factors

**Main Layout:**
1. Exploring frame: Stretch factor 1
2. Filtering frame: Stretch factor 1
3. Export frame: Stretch factor 0 (fixed size)

## UI Testing

### Manual Testing Checklist

See `docs/UI_TESTING_GUIDE.md` for comprehensive checklist:

1. **Theme Testing**
   - Switch QGIS themes
   - Verify color adaptation
   - Check contrast and readability

2. **Dimension Testing**
   - Test on laptop (< 1920x1080)
   - Test on desktop (≥ 1920x1080)
   - Verify adaptive sizing

3. **Widget Testing**
   - Layer selection
   - Feature selection
   - Button interactions
   - Combobox functionality

4. **Layout Testing**
   - Window resize
   - Minimum sizes
   - Scroll behavior
   - Overlap detection

### Automated Tests

**Location:** `tests/test_qt_json_view_themes.py`

**Coverage:**
- Theme detection
- QSS generation
- Widget styling
- Color validation

**Run:**
```bash
pytest tests/test_qt_json_view_themes.py -v
```

## Performance Considerations

### Icon Caching

**Implementation:** Icons cached on first load

**Location:** `modules/appUtils.py` (`get_icon_for_geometry`)

**Benefit:** Faster UI updates when switching layers

### Lazy Loading

**Combobox Population:** Populated asynchronously using QgsTask

**Benefit:** Non-blocking UI during layer loading

### Signal Optimization

**Batch Updates:** Use SignalBlocker to prevent cascade updates

**Benefit:** Smoother UI when updating multiple widgets

## Accessibility

### Keyboard Navigation

- Tab order properly configured
- All buttons accessible via keyboard
- Combobox keyboard shortcuts

### Screen Reader Support

- Descriptive tooltips on all buttons
- Labels properly associated with inputs
- Status messages via QGIS message bar

### High Contrast

- Theme system ensures sufficient contrast
- Borders visible in all themes
- Focus indicators clear

## Future UI Enhancements

### Planned Features
- User-customizable themes
- Saved layout preferences
- More compact mode options
- Tablet/touch optimization
- Multi-language support enhancements

## Documentation Files

### UI-Related Documentation
- `docs/UI_IMPROVEMENTS_README.md`: General improvements
- `docs/UI_TESTING_GUIDE.md`: Testing procedures
- `docs/UI_DYNAMIC_CONFIG.md`: Dynamic configuration
- `docs/UI_HARMONIZATION_PLAN.md`: Harmonization strategy
- `docs/THEMES.md`: Theme system details
- `docs/THEME_SYNC.md`: Synchronization mechanism
