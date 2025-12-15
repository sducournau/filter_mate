# QgsColorButton Integration for Config Colors

## Overview

FilterMate now includes automatic color picker support for hex color values in the configuration JSON tree view. When users edit the configuration through the JSON viewer, any hex color string is automatically displayed with a color preview and can be edited using a `QgsColorButton`.

## Implementation

### ColorType Class

A new `ColorType` data type class has been added to `modules/qt_json_view/datatypes.py` that:

1. **Detects hex color strings** using regex pattern matching:
   - `#RGB` (3 hex digits)
   - `#RRGGBB` (6 hex digits)
   - `#RRGGBBAA` (8 hex digits with alpha)

2. **Displays color previews** by painting a colored rectangle next to the hex value

3. **Provides color editing** via `QgsColorButton`:
   - Click on any color value to open the color picker
   - Supports alpha/opacity channel
   - Updates immediately on color change
   - Formats output as hex string (#RRGGBB or #RRGGBBAA)

### Integration with JSON Tree View

The `ColorType` is registered in the `DATA_TYPES` list before `StrType` to ensure color strings are detected before being treated as generic strings:

```python
DATA_TYPES = [
    # ... other types ...
    ColorType(),  # Must be before StrType
    StrType(),
    # ... other types ...
]
```

## Usage

### In Configuration JSON

Any hex color value in `config.json` will automatically be detected and editable:

```json
{
  "app": {
    "themes": {
      "default": {
        "background": [
          "#F5F5F5",  // Editable with color picker
          "#FFFFFF",  // Editable with color picker
          "#E0E0E0",  // Editable with color picker
          "#2196F3"   // Editable with color picker
        ],
        "font": [
          "#212121",  // Editable with color picker
          "#616161",  // Editable with color picker
          "#BDBDBD"   // Editable with color picker
        ],
        "accent": {
          "primary": "#1976D2",   // Editable with color picker
          "hover": "#2196F3",     // Editable with color picker
          "pressed": "#0D47A1"    // Editable with color picker
        }
      }
    }
  }
}
```

### User Experience

1. **Visual Preview**: Each color value displays a small colored rectangle showing the actual color
2. **Easy Editing**: Click on the color value to open a `QgsColorButton` dialog
3. **Immediate Feedback**: Color changes are applied instantly to the configuration
4. **Transparency Support**: Full alpha channel support for semi-transparent colors

## Testing

A test script is provided at `test_color_picker.py` to verify the functionality:

```bash
# From plugin directory
python test_color_picker.py
```

The test creates a sample configuration window with various theme colors that can be edited.

## Benefits

### For Users
- **Intuitive Color Selection**: Use a visual color picker instead of typing hex codes
- **Live Preview**: See colors immediately in the tree view
- **No Mistakes**: Color picker ensures valid hex codes
- **Transparency Control**: Easy opacity adjustment with slider

### For Developers
- **Automatic Detection**: No special configuration needed
- **Consistent UX**: Same color picker used throughout QGIS
- **Type Safety**: Invalid colors are handled gracefully
- **Extensible**: Easy to add custom color types or constraints

## Technical Details

### Color Detection Pattern

```python
HEX_COLOR_PATTERN = re.compile(r'^#[0-9A-Fa-f]{3}([0-9A-Fa-f]{3})?([0-9A-Fa-f]{2})?$')
```

This pattern matches:
- `#RGB` → 3 hex digits (e.g., `#F00` for red)
- `#RRGGBB` → 6 hex digits (e.g., `#FF0000` for red)
- `#RRGGBBAA` → 8 hex digits with alpha (e.g., `#FF0000CC` for semi-transparent red)

### QgsColorButton Features Used

- `setAllowOpacity(True)`: Enable alpha channel editing
- `setShowNoColor(False)`: Require a valid color (no "no color" option)
- `colorChanged` signal: Immediate update on color selection
- `color()` method: Get selected QColor
- `setColor()` method: Set initial color from hex string

### Color Format Output

Colors are formatted based on opacity:
- **Opaque colors** (alpha = 255): `#RRGGBB` format
- **Semi-transparent colors** (alpha < 255): `#RRGGBBAA` format

This ensures minimal change to existing configuration values while supporting transparency when needed.

## Future Enhancements

Possible improvements for future versions:

1. **Color Palettes**: Predefined color schemes users can select from
2. **Theme Inheritance**: Colors inherit from parent theme with overrides
3. **Color Validation**: Ensure sufficient contrast between text/background colors
4. **Recent Colors**: Remember recently used colors
5. **Color Naming**: Optional color names displayed alongside hex values
6. **Batch Editing**: Change multiple related colors at once

## Related Files

- `modules/qt_json_view/datatypes.py`: ColorType implementation
- `modules/qt_json_view/delegate.py`: Editor creation and painting
- `modules/qt_json_view/view.py`: JSON tree view
- `config/config.json`: Configuration with color values
- `test_color_picker.py`: Test script for color picker functionality

## References

- QGIS API: [QgsColorButton](https://qgis.org/pyqgis/master/gui/QgsColorButton.html)
- PyQt5: [QColor](https://doc.qt.io/qt-5/qcolor.html)
- CSS Colors: [Hex Color Notation](https://www.w3.org/TR/css-color-3/#rgb-color)
