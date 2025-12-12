# UI System Documentation - FilterMate v2.3.0-alpha

**Last Updated:** December 12, 2025

## Overview

FilterMate implements a comprehensive, adaptive UI system with dynamic dimensions, theme synchronization, responsive design, and real-time configuration updates.

## Architecture

### Core UI Modules

```
modules/
├── ui_config.py              # Dynamic dimensions configuration (DisplayProfile enum)
├── ui_styles.py              # Theme management and QSS generation
├── ui_elements.py            # UI element creation and management
├── ui_elements_helpers.py    # Helper functions for UI operations
├── ui_widget_utils.py        # Widget utility functions
├── widgets.py                # Custom widget implementations
├── signal_utils.py           # Signal management utilities
├── config_helpers.py         # Configuration access utilities (v2.2.2)
└── qt_json_view/             # JSON tree view widgets
    ├── view.py               # JSON tree view
    ├── model.py              # JSON data model
    ├── themes.py             # Theme definitions
    └── delegate.py           # Custom item delegate
```

## Dynamic Dimensions System (v2.1.0+)

### Display Profile Enum
**File:** `modules/ui_config.py`

**Modes:**
- `AUTO`: Automatic detection based on screen resolution
- `COMPACT`: Optimized for small screens (< 1920x1080)
- `NORMAL`: Comfortable spacing for large displays (≥ 1920x1080)

### Resolution Detection
**Threshold:** 1920×1080 pixels
**Detection:** `QApplication.primaryScreen().size()`

### Dimension Categories

#### 1. Tool Buttons
- **Compact:** 18×18px (16px icons)
- **Normal:** 24×24px (22px icons)
- **Elements:** Play, pause, clear, help buttons

#### 2. Input Widgets (ComboBox, LineEdit, SpinBox)
- **Compact:** 24px height
- **Normal:** 30px height
- **Elements:** All dropdowns, text inputs, number inputs

#### 3. Frames (Exploring, Filtering, Export)
- **Compact:** 150px minimum height
- **Normal:** 180px minimum height
- **Benefit:** Better content visibility on large screens

#### 4. Widget Keys (Button columns)
- **Compact:** 45-90px width
- **Normal:** 55-110px width
- **Elements:** Label columns, button groups

#### 5. GroupBox
- **Compact:** 40px minimum height
- **Normal:** 50px minimum height

#### 6. Layout Spacing & Margins
- **Spacing:**
  - Compact: 3px
  - Normal: 6px
- **Margins:**
  - Compact: 2px
  - Normal: 4px

#### 7. Separators
- **Compact:** 1px
- **Normal:** 2px

#### 8. Font Sizes
- **Labels:**
  - Compact: 8pt
  - Normal: 9pt
- **Buttons:**
  - Compact: 9pt
  - Normal: 10pt

### Implementation

**UIConfig Class:**
```python
from modules.ui_config import UIConfig, DisplayProfile

# Initialize with auto-detection
ui_config = UIConfig()

# Or specify profile
ui_config = UIConfig(profile=DisplayProfile.COMPACT)

# Apply to dockwidget
ui_config.apply_dynamic_dimensions(dockwidget)

# Get specific dimension
button_size = ui_config.get_dimension('tool_button_size')
```

**Dimension Access:**
```python
# Get dimension by key
width = ui_config.get_dimension('input_widget_height')

# Get all dimensions
dims = ui_config.get_all_dimensions()

# Update profile
ui_config.update_profile(DisplayProfile.NORMAL)
```

### Benefits
- **15-20% vertical space savings** in compact mode
- **Better readability** on large screens in normal mode
- **Consistent spacing** across all UI elements
- **Automatic adaptation** based on screen size

## Theme System (v2.1.0+)

### Theme Synchronization

**Sources (v2.2.2):**
- `config`: Use theme from config.json
- `qgis`: Sync with QGIS interface theme (default)
- `system`: Use system theme

**Auto-Detection:**
- Detects current QGIS theme on startup
- Responds to QGIS theme changes
- Fallback to default if detection fails

### Supported QGIS Themes
- **Blend of Gray** (Light theme)
- **Night Mapping** (Dark theme)
- **Default** (QGIS default)
- **Custom themes** (auto-detect light/dark)

### Theme Categories

#### 1. Background Colors
- Main widget background
- Frame background (exploring, filtering, export)
- GroupBox background
- TreeView background

#### 2. Text Colors
- Primary text (labels, normal text)
- Secondary text (hints, placeholders)
- Disabled text
- Link text

#### 3. Border Colors
- Frame borders
- Focus borders (active inputs)
- Separator colors
- GroupBox borders

#### 4. Interactive Element Colors
- Button background (normal, hover, pressed)
- CheckBox states (unchecked, checked, indeterminate)
- ComboBox dropdown
- ScrollBar colors

#### 5. Accent Colors
- Selection background
- Highlight color
- Focus indicator
- Active tab color

### QSS Generation

**UIStyles Class:**
```python
from modules.ui_styles import UIStyles

# Get QSS for current QGIS theme
qss = UIStyles.get_qss_for_theme('Night Mapping')

# Apply to widget
widget.setStyleSheet(qss)

# Detect current QGIS theme
current_theme = UIStyles.detect_qgis_theme()

# Get theme type (light/dark)
theme_type = UIStyles.get_theme_type('Night Mapping')  # Returns 'dark'
```

**Dynamic QSS:**
- Generated at runtime based on theme
- Includes all UI elements
- Respects QGIS color palette
- Ensures readability and contrast

### Theme Files Structure

**Location:** `resources/styles/`
```
styles/
├── base.qss           # Base styles (common to all themes)
├── light_theme.qss    # Light theme overrides
├── dark_theme.qss     # Dark theme overrides
└── qgis_sync.qss      # QGIS synchronization styles
```

**Loading Order:**
1. Load base.qss
2. Detect current theme
3. Load theme-specific overrides
4. Apply QGIS synchronization adjustments

## Custom Widgets (v2.0+)

### 1. QgsCheckableComboBoxLayer

**Purpose:** Multi-select layer picker with icons
**File:** `modules/widgets.py`
**Lines:** ~800-1100

**Features:**
- Checkbox for each layer
- Custom icons per geometry type
- Right-click context menu
- "Select All" / "Deselect All"
- Geometry type filtering

**Key Methods:**
```python
# Add layer with icon
combobox.addItem(icon, layer_name, layer_id)

# Get selected layers
selected = combobox.checkedItems()

# Filter by geometry type
combobox.select_by_geometry('Polygon')

# Clear all selections
combobox.clear_selection()
```

**Geometry Icons:**
- Point → `point.svg`
- Line → `line.svg`
- Polygon → `polygon.svg`
- No Geometry → `no_geometry.svg`

### 2. QgsCheckableComboBoxFeaturesListPickerWidget

**Purpose:** Feature selection with async loading
**File:** `modules/widgets.py`
**Lines:** ~1100-1400

**Features:**
- Asynchronous population (QgsTask)
- Live search/filter
- Multi-select with checkboxes
- Icon display per feature
- Progress indicator

**Key Methods:**
```python
# Populate from layer
widget.populate_from_layer(layer, display_expression)

# Get selected features
selected_ids = widget.get_selected_feature_ids()

# Set selected features
widget.set_selected_features([1, 2, 3])

# Clear all
widget.clear()
```

**Performance:**
- Non-blocking population
- Handles 10k+ features smoothly
- Cancellable operation

### 3. JSON Tree View (qt_json_view)

**Purpose:** Interactive JSON configuration editor
**File:** `modules/qt_json_view/view.py`

**Features (v2.2.2):**
- Expandable tree structure
- **ChoicesType support:** Dropdown selectors for validated fields
- Inline editing
- Theme-aware styling
- Copy/export functionality
- Real-time validation

**ChoicesType Integration:**
When a configuration field has format:
```json
{
  "value": "auto",
  "choices": ["auto", "compact", "normal"]
}
```

The tree view displays:
- **Field name** with dropdown icon
- **Current value** in dropdown selector
- **Valid choices** in dropdown menu
- **Validation** prevents invalid values

**Key Methods:**
```python
from modules.qt_json_view import JsonView

# Create view
view = JsonView(model=JsonModel(data), parent=parent)

# Connect to changes
view.model().itemChanged.connect(on_change)

# Get data
data = view.model().to_dict()

# Expand all
view.expandAll()
```

**Theme Synchronization:**
- Automatically matches QGIS theme
- Custom delegates for ChoicesType fields
- Syntax highlighting for values
- Color-coded by data type

## Signal Management (v2.1.0+)

### SignalBlocker

**Purpose:** Safely block/unblock Qt signals
**File:** `modules/signal_utils.py`

**Usage:**
```python
from modules.signal_utils import SignalBlocker

with SignalBlocker(widget):
    # Signals blocked here
    widget.setValue(new_value)
    # No signal emitted
# Signals automatically restored
```

**Features:**
- Context manager (automatic cleanup)
- Preserves original signal state
- Exception-safe

### SignalConnection

**Purpose:** Temporary signal connections
**File:** `modules/signal_utils.py`

**Usage:**
```python
from modules.signal_utils import SignalConnection

with SignalConnection(button.clicked, handler):
    # Signal connected only in this block
    button.click()
# Signal automatically disconnected
```

### SignalBlockerGroup

**Purpose:** Block signals for multiple widgets
**File:** `modules/signal_utils.py`

**Usage:**
```python
from modules.signal_utils import SignalBlockerGroup

widgets = [combobox1, combobox2, lineedit]
with SignalBlockerGroup(widgets):
    # All widgets blocked
    update_widgets(widgets)
# All signals restored
```

### ConnectionManager

**Purpose:** Manage multiple connections with lifecycle
**File:** `modules/signal_utils.py`

**Usage:**
```python
from modules.signal_utils import ConnectionManager

manager = ConnectionManager()
manager.connect(button.clicked, handler1)
manager.connect(combo.currentIndexChanged, handler2)

# Later: disconnect all
manager.disconnect_all()
```

## Configuration Reactivity (v2.2.2)

### Real-Time Updates

**Feature:** Configuration changes apply immediately without restart

**Supported Fields:**
- `UI_PROFILE`: Instant dimension update
- `ACTIVE_THEME`: Immediate theme switch
- `ICON_PATH`: Icon reload
- `THEME_SOURCE`: Theme source switch

**Implementation:**
```python
# In filter_mate_dockwidget.py
def _on_config_item_changed(self, item):
    # Detect change type
    path = self._get_item_path(item)
    
    if 'UI_PROFILE' in path:
        new_profile = get_config_value('UI_PROFILE')
        self.ui_config.update_profile(new_profile)
        self.ui_config.apply_dynamic_dimensions(self)
        show_success(f"UI profile changed to {new_profile}")
    
    elif 'ACTIVE_THEME' in path:
        new_theme = get_config_value('ACTIVE_THEME')
        self.apply_theme(new_theme)
        show_success(f"Theme changed to {new_theme}")
    
    # Save to config.json
    save_config()
```

### ChoicesType Support

**Format:**
```json
{
  "UI_PROFILE": {
    "value": "auto",
    "choices": ["auto", "compact", "normal"]
  }
}
```

**Features:**
- Dropdown selector in JSON tree view
- Type-safe selection (no typos)
- Validation at UI level
- Clear available options

**Configuration Fields with ChoicesType:**
1. `UI_PROFILE` (auto/compact/normal)
2. `ACTIVE_THEME` (auto/default/dark/light)
3. `THEME_SOURCE` (config/qgis/system)
4. `STYLES_TO_EXPORT` (QML/SLD/None)
5. `DATATYPE_TO_EXPORT` (GPKG/SHP/GEOJSON/KML/DXF/CSV)

### Configuration Helpers (v2.2.2)

**File:** `modules/config_helpers.py`

**Key Functions:**
```python
from modules.config_helpers import (
    get_config_value,
    set_config_value,
    get_ui_profile,
    get_active_theme
)

# Read config value (handles ChoicesType)
profile = get_config_value('UI_PROFILE')  # Returns 'auto', not {'value': 'auto', ...}

# Write config value (validates)
set_config_value('UI_PROFILE', 'compact')

# Get available choices
choices = get_config_choices('UI_PROFILE')  # ['auto', 'compact', 'normal']

# Validate value
is_valid = validate_config_value('UI_PROFILE', 'invalid')  # False

# Convenience functions
profile = get_ui_profile()  # Direct access
theme = get_active_theme()
```

## UI Element Creation Helpers

### Element Factory Functions

**File:** `modules/ui_elements_helpers.py`

**Functions:**
```python
from modules.ui_elements_helpers import (
    create_label,
    create_button,
    create_combobox,
    create_groupbox,
    create_frame,
    create_checkbox,
    create_spinbox
)

# Create themed label
label = create_label("Text", parent, bold=True)

# Create button with icon
button = create_button("Click", icon_path, parent, tooltip="Help")

# Create styled combobox
combo = create_combobox(parent, items=['A', 'B', 'C'])

# Create frame with border
frame = create_frame(parent, border=True, title="Section")
```

### Layout Helpers

**File:** `modules/ui_widget_utils.py`

**Functions:**
```python
from modules.ui_widget_utils import (
    create_horizontal_layout,
    create_vertical_layout,
    create_grid_layout,
    add_stretch,
    set_margins
)

# Create HBox with spacing
hbox = create_horizontal_layout(spacing=6, margins=(4, 4, 4, 4))

# Create VBox
vbox = create_vertical_layout(spacing=3)

# Add stretch
add_stretch(vbox)

# Set margins
set_margins(layout, left=5, top=5, right=5, bottom=5)
```

## Responsive Design

### Minimum Sizes

**Dockwidget:**
- Minimum width: 421px
- Minimum height: 611px (compact) / 700px (normal)

**Frames:**
- Exploring frame: 150px (compact) / 180px (normal)
- Filtering frame: 150px (compact) / 180px (normal)
- Export frame: 120px (fixed)

**Widgets:**
- ComboBox: 24px (compact) / 30px (normal)
- Tool buttons: 18px (compact) / 24px (normal)
- LineEdit: 24px (compact) / 30px (normal)

### Stretch Factors

**Main Vertical Layout:**
```python
layout.addWidget(exploring_frame, stretch=1)  # Expandable
layout.addWidget(filtering_frame, stretch=1)  # Expandable
layout.addWidget(export_frame, stretch=0)     # Fixed
```

**Benefit:** Available space distributed proportionally

### Scroll Areas

**When Needed:**
- Window height < minimum required
- Many layers in list (> 20)
- Long expressions

**Implementation:**
```python
scroll_area = QScrollArea()
scroll_area.setWidget(content_widget)
scroll_area.setWidgetResizable(True)
```

## Performance Considerations

### Icon Caching

**Implementation:** `modules/appUtils.py`
```python
_icon_cache = {}

def get_icon_for_geometry(geom_type):
    if geom_type not in _icon_cache:
        _icon_cache[geom_type] = QIcon(icon_path)
    return _icon_cache[geom_type]
```

**Benefit:** Faster UI updates (no repeated file I/O)

### Lazy Loading

**Combobox Population:**
- Asynchronous via QgsTask
- Non-blocking UI
- Progress feedback

**Example:**
```python
class PopulateTask(QgsTask):
    def run(self):
        # Load data in background
        self.items = fetch_items()
        return True
    
    def finished(self, result):
        # Update UI in main thread
        for item in self.items:
            combobox.addItem(item)
```

### Signal Optimization

**Pattern:** Block signals during batch updates
```python
with SignalBlockerGroup([widget1, widget2, widget3]):
    # Update all widgets without triggering signals
    widget1.setValue(val1)
    widget2.setValue(val2)
    widget3.setValue(val3)
# One update signal after all changes
```

**Benefit:** Prevents cascade updates and UI flicker

## Accessibility

### Keyboard Navigation

**Tab Order:**
- Properly configured tab order
- Logical flow through UI
- Skip disabled widgets

**Shortcuts:**
- All buttons have keyboard shortcuts
- Standard Qt shortcuts (Ctrl+A, etc.)
- ComboBox keyboard navigation

### Screen Reader Support

**Implementation:**
- Descriptive tooltips on all buttons
- Labels properly associated with inputs (`setBuddy()`)
- Status messages via QGIS message bar
- Accessible names for widgets (`setAccessibleName()`)

### High Contrast

**Theme System Ensures:**
- Sufficient contrast ratios (WCAG AA)
- Visible borders in all themes
- Clear focus indicators
- Readable text in all conditions

## UI Testing

### Manual Testing Checklist

**Location:** `docs/UI_TESTING_GUIDE.md`

**Categories:**
1. **Theme Testing**
   - Switch between light/dark themes
   - Verify color adaptation
   - Check contrast and readability
   - Test custom themes

2. **Dimension Testing**
   - Test on small screen (< 1920x1080)
   - Test on large screen (≥ 1920x1080)
   - Verify adaptive sizing
   - Check spacing consistency

3. **Widget Testing**
   - Layer selection combobox
   - Feature selection widget
   - Button interactions
   - Combobox functionality
   - JSON tree view editing

4. **Layout Testing**
   - Window resize behavior
   - Minimum size enforcement
   - Scroll area activation
   - No overlapping elements

5. **Configuration Testing (v2.2.2)**
   - Real-time UI profile switching
   - Theme change without restart
   - ChoicesType dropdown functionality
   - Invalid value prevention

### Automated Tests

**Location:** `tests/test_qt_json_view_themes.py`

**Coverage:**
- Theme detection
- QSS generation
- Widget styling
- Color validation
- ChoicesType delegate

**Run:**
```bash
pytest tests/test_qt_json_view_themes.py -v
```

### UI Styles Testing

**Location:** `docs/UI_STYLES_TESTING_CHECKLIST.md`

**Process:**
1. Load plugin in different QGIS themes
2. Verify all UI elements styled correctly
3. Check borders, colors, fonts
4. Test interactive element states
5. Verify icon visibility

## Documentation Files

### UI-Related Documentation
- `docs/UI_SYSTEM_OVERVIEW.md`: Complete UI architecture
- `docs/UI_DYNAMIC_CONFIG.md`: Dynamic dimensions system
- `docs/UI_STYLE_HARMONIZATION.md`: Theme harmonization
- `docs/UI_TESTING_GUIDE.md`: Testing procedures
- `docs/THEMES.md`: Theme system details
- `docs/CONFIG_JSON_REACTIVITY.md`: Configuration reactivity (v2.2.2)
- `docs/CONFIG_JSON_IMPROVEMENTS.md`: Configuration enhancements (v2.2.2)

## Undo/Redo UI Integration (NEW in v2.3.0-alpha)

### Buttons
- `pushButton_action_undo_filter`: Undo button
- `pushButton_action_redo_filter`: Redo button

### Signals
- `currentLayerChanged`: Emitted when layer selection changes
  - Triggers `update_undo_redo_buttons()` for immediate UI update

### Button State Management
- Buttons auto-enable/disable based on history availability
- Updates after filter operations, undo, redo, or layer changes
- Context-aware: source-only mode vs global mode

### User Feedback
- Success messages indicate which mode was used
- Clear indication of state restoration

## Future UI Enhancements

### Planned Features
- User-customizable themes (save preferences)
- Layout persistence (remember window size/position)
- More dimension profiles (extra-compact for tablets)
- Touch optimization (larger touch targets)
- Multi-language UI support enhancements
- Custom widget styling per user
- Dockable panels (separate exploring/filtering)
- Quick filter presets (save/load common filters)
