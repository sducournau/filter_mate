---
sidebar_position: 7
---

# Configuration System

FilterMate v2.2+ includes a **comprehensive JSON-based configuration system** with live editing, validation, and hot-reload capabilities.

## Overview

The configuration system provides:

- **JSON Tree Editor**: Visual configuration editor in the UI
- **Live Updates**: Changes apply immediately without restart
- **Type Validation**: Ensures configuration values are valid
- **ChoicesType**: Dropdown-style configuration for predefined options
- **Backup System**: Automatic backups before modifications
- **Migration**: Automatic upgrade from older configuration formats

## Configuration Files

### Location

```
filter_mate/
├── config/
│   ├── config.json                 # Active configuration
│   ├── config.default.json         # Default values (reference)
│   ├── config_schema.json          # JSON schema validation
│   ├── config.py                   # Configuration loader
│   └── backups/                    # Automatic backups
│       ├── config.backup.1.json
│       ├── config.backup.2.json
│       └── ...
```

### File Purposes

| File | Purpose | Modify? |
|------|---------|---------|
| `config.json` | Active user configuration | ✅ Yes (via UI or manually) |
| `config.default.json` | Default values, reset reference | ❌ No (read-only) |
| `config_schema.json` | JSON schema for validation | ❌ No (developer only) |
| `config.py` | Python loader module | ❌ No (developer only) |
| `backups/*.json` | Automatic backups | ℹ️ Read-only (auto-generated) |

## Configuration Structure

### Basic Format

```json
{
  "SIMPLE_VALUE": "direct_value",
  "CHOICES_VALUE": {
    "value": "current_selection",
    "choices": ["option1", "option2", "option3"]
  }
}
```

### ChoicesType Pattern

For settings with predefined options:

```json
{
  "UI_PROFILE": {
    "value": "auto",
    "choices": ["auto", "compact", "normal"]
  }
}
```

**Reading ChoicesType values** in code:

```python
from modules.config_helpers import get_config_value

# Returns just the value, not the dict
ui_profile = get_config_value('UI_PROFILE')  # Returns: 'auto'
```

## Available Settings

### UI Configuration

#### UI_PROFILE
**Type**: ChoicesType  
**Options**: `auto`, `compact`, `normal`  
**Default**: `auto`

Controls UI density and spacing:
- `auto`: Automatic based on screen resolution
- `compact`: Dense layout (< 1920px screens)
- `normal`: Spacious layout (≥ 1920px screens)

```json
{
  "UI_PROFILE": {
    "value": "auto",
    "choices": ["auto", "compact", "normal"]
  }
}
```

#### ACTIVE_THEME
**Type**: ChoicesType  
**Options**: `auto`, `default`, `dark`, `light`  
**Default**: `auto`

Sets FilterMate color theme:
- `auto`: Follow QGIS theme
- `default`: FilterMate default theme
- `dark`: Dark theme (high contrast)
- `light`: Light theme (low contrast)

```json
{
  "ACTIVE_THEME": {
    "value": "auto",
    "choices": ["auto", "default", "dark", "light"]
  }
}
```

#### THEME_SOURCE
**Type**: ChoicesType  
**Options**: `config`, `qgis`, `system`  
**Default**: `qgis`

Determines theme source:
- `config`: Use `ACTIVE_THEME` value
- `qgis`: Follow QGIS theme setting
- `system`: Follow OS theme

```json
{
  "THEME_SOURCE": {
    "value": "qgis",
    "choices": ["config", "qgis", "system"]
  }
}
```

### Export Configuration

#### STYLES_TO_EXPORT
**Type**: ChoicesType  
**Options**: `QML`, `SLD`, `None`  
**Default**: `QML`

Determines which style format to export with features:
- `QML`: QGIS native style format (recommended)
- `SLD`: OGC Styled Layer Descriptor (interoperable)
- `None`: No style export (geometry only)

```json
{
  "STYLES_TO_EXPORT": {
    "value": "QML",
    "choices": ["QML", "SLD", "None"]
  }
}
```

#### DATATYPE_TO_EXPORT
**Type**: ChoicesType  
**Options**: `GPKG`, `SHP`, `GEOJSON`, `KML`, `DXF`, `CSV`  
**Default**: `GPKG`

Default export format:
- `GPKG`: GeoPackage (recommended, modern)
- `SHP`: Shapefile (legacy, widely compatible)
- `GEOJSON`: GeoJSON (web-friendly)
- `KML`: Keyhole Markup Language (Google Earth)
- `DXF`: AutoCAD format
- `CSV`: Comma-separated values (no geometry)

```json
{
  "DATATYPE_TO_EXPORT": {
    "value": "GPKG",
    "choices": ["GPKG", "SHP", "GEOJSON", "KML", "DXF", "CSV"]
  }
}
```

### System Configuration

#### ICON_PATH
**Type**: String  
**Default**: `"icons/"`

Path to icon directory (relative to plugin root).

```json
{
  "ICON_PATH": "icons/"
}
```

#### POSTGRESQL_AVAILABLE
**Type**: Boolean (read-only)  
**Default**: Auto-detected

Indicates if psycopg2 is installed. **Do not manually modify** - this is set automatically at runtime.

```json
{
  "POSTGRESQL_AVAILABLE": true
}
```

#### ENABLE_DEBUG_LOGGING
**Type**: Boolean  
**Default**: `false`

Enables detailed debug logging to QGIS Python console.

```json
{
  "ENABLE_DEBUG_LOGGING": false
}
```

## Editing Configuration

### Via UI (Recommended)

1. **Open FilterMate panel** in QGIS
2. **Locate Configuration tab** (JSON tree view)
3. **Double-click value** to edit
4. **Press Enter** to apply
5. **Changes apply immediately** - no restart needed

**ChoicesType values** show dropdown:
- Click dropdown icon
- Select from predefined options
- Invalid values are rejected

### Via File (Advanced)

1. **Close QGIS** (recommended)
2. **Edit** `config/config.json` in text editor
3. **Validate JSON syntax** (use JSON validator)
4. **Restart QGIS** to apply

:::warning Backup First
Always backup `config.json` before manual edits. Invalid JSON will fall back to defaults.
:::

## Configuration Reactivity

FilterMate automatically applies configuration changes:

### Reactive Settings (Immediate)

These settings take effect immediately without reload:

| Setting | Effect | Applies To |
|---------|--------|-----------|
| `UI_PROFILE` | Resize widgets, adjust spacing | All widgets |
| `ACTIVE_THEME` | Apply color scheme | Entire UI |
| `ICON_PATH` | Reload icons | Layer icons, buttons |
| `ENABLE_DEBUG_LOGGING` | Toggle logging level | Console output |

### Non-Reactive Settings (Require Reload)

These settings require plugin reload (F5):

| Setting | Reason | Workaround |
|---------|--------|-----------|
| `DATATYPE_TO_EXPORT` | Export dialog initialization | Use dropdown in export dialog |
| `STYLES_TO_EXPORT` | Export task creation | Change before export |

### Reload Methods

**Soft Reload** (Ctrl+F5 or Reload button):
- Reloads layers and UI
- Preserves filter history
- Fast (~1 second)

**Hard Reload** (F5 or plugin restart):
- Full plugin reload
- Clears filter history
- Slower (~3 seconds)

## Configuration Helpers

### Python API

FilterMate provides helper functions for configuration access:

```python
from modules.config_helpers import (
    get_config_value,
    set_config_value,
    get_config_choices,
    validate_config_value
)

# Read value (handles ChoicesType automatically)
theme = get_config_value('ACTIVE_THEME')  # Returns: 'auto'

# Read with default
custom = get_config_value('CUSTOM_KEY', default='fallback')

# Get available choices
profiles = get_config_choices('UI_PROFILE')  
# Returns: ['auto', 'compact', 'normal']

# Validate before setting
is_valid = validate_config_value('UI_PROFILE', 'invalid')  # False

# Set value (validates automatically)
set_config_value('ACTIVE_THEME', 'dark')
```

### Direct Access (Not Recommended)

```python
# Legacy method - use config_helpers instead
from config.config import ENV_VARS

# Read simple value
icon_path = ENV_VARS['ICON_PATH']

# Read ChoicesType value
theme_dict = ENV_VARS['ACTIVE_THEME']
theme_value = theme_dict['value']  # 'auto'
theme_choices = theme_dict['choices']  # ['auto', 'default', ...]
```

## Backup System

### Automatic Backups

FilterMate creates automatic backups before modifications:

**Trigger Events**:
- User edits configuration via UI
- Plugin upgrade with schema changes
- Configuration migration from old format

**Backup Location**: `config/backups/`

**Naming Convention**:
```
config.backup.1.json  # Most recent
config.backup.2.json
config.backup.3.json
...
config.backup.10.json # Oldest (rotates)
```

**Rotation**: Keeps last **10 backups**, oldest is removed

### Restoring from Backup

**Via File System**:
```bash
cd filter_mate/config/
cp backups/config.backup.1.json config.json
```

**Via Python Console**:
```python
import shutil
from pathlib import Path

plugin_dir = Path(__file__).parent
backup = plugin_dir / 'config' / 'backups' / 'config.backup.1.json'
config = plugin_dir / 'config' / 'config.json'

shutil.copy(backup, config)
```

Then reload FilterMate (F5).

### Resetting to Defaults

**Via File System**:
```bash
cd filter_mate/config/
cp config.default.json config.json
```

**Via UI** (planned v2.4):
- Configuration tab → Right-click → "Reset to Defaults"

## Configuration Migration

### Automatic Migration

FilterMate automatically migrates old configuration formats:

**Migration Path**:
```
v2.0.x → v2.1.x → v2.2.x → v2.3.x → v2.4.x (latest)
```

**Migration Process**:
1. Detect old format (missing keys, old structure)
2. Create backup of current config
3. Apply migrations in sequence
4. Validate result against schema
5. Save migrated configuration

**Log Migration**:
```
FilterMate: Migrating configuration from v2.1 to v2.2
FilterMate: - Added UI_PROFILE with default 'auto'
FilterMate: - Converted THEME from string to ChoicesType
FilterMate: - Backup saved to config/backups/config.backup.1.json
FilterMate: Configuration migration completed successfully
```

### Manual Migration

If automatic migration fails:

1. **Check logs** for specific error
2. **Compare** your `config.json` with `config.default.json`
3. **Add missing keys** from default
4. **Remove obsolete keys** (check CHANGELOG.md)
5. **Validate JSON syntax**
6. **Restart FilterMate**

## Validation

### JSON Schema

Configuration is validated against `config_schema.json`:

**Schema Structure**:
```json
{
  "type": "object",
  "properties": {
    "UI_PROFILE": {
      "type": "object",
      "properties": {
        "value": { "type": "string", "enum": ["auto", "compact", "normal"] },
        "choices": { "type": "array", "items": { "type": "string" } }
      },
      "required": ["value", "choices"]
    }
  }
}
```

### Validation Errors

**Symptom**: Configuration changes ignored or reset

**Check**:
1. **JSON Syntax**: Use JSONLint or VS Code JSON validator
2. **Value Types**: Ensure strings are quoted, booleans are lowercase
3. **ChoicesType**: Ensure `value` exists in `choices` array
4. **Required Keys**: Check all required fields are present

**Example Errors**:
```json
{
  "UI_PROFILE": "auto"  // ❌ Wrong: missing choices
}

{
  "UI_PROFILE": {
    "value": "invalid",  // ❌ Wrong: not in choices
    "choices": ["auto", "compact", "normal"]
  }
}

{
  "ENABLE_DEBUG_LOGGING": "false"  // ❌ Wrong: should be boolean
}
```

**Correct**:
```json
{
  "UI_PROFILE": {
    "value": "auto",  // ✅ Correct
    "choices": ["auto", "compact", "normal"]
  },
  "ENABLE_DEBUG_LOGGING": false  // ✅ Correct (boolean)
}
```

## Troubleshooting

### Configuration Not Applied

**Symptom**: Changes don't take effect

**Solutions**:
1. Check if setting is reactive or requires reload
2. Reload plugin (F5) if non-reactive
3. Verify JSON syntax is valid
4. Check QGIS Python console for errors

### Configuration Reset on Startup

**Symptom**: Configuration resets to defaults each time

**Causes**:
- Invalid JSON syntax
- Schema validation failure
- File permissions issue

**Solutions**:
1. Validate JSON with online validator
2. Check file permissions (should be writable)
3. Review logs for specific error
4. Restore from backup

### ChoicesType Not Showing Dropdown

**Symptom**: Can't select from dropdown in UI

**Causes**:
- Missing `choices` array
- Invalid JSON structure
- UI editor not detecting ChoicesType

**Solution**:
```json
// Ensure structure is correct
{
  "KEY_NAME": {
    "value": "current",
    "choices": ["option1", "option2", "option3"]
  }
}
```

## Best Practices

### Configuration Management

✅ **Do**:
- Edit via UI when possible (safer)
- Test changes on non-production projects
- Review backups before major changes
- Document custom settings

❌ **Don't**:
- Edit JSON while QGIS is running (file conflicts)
- Remove required keys
- Use invalid choice values
- Modify `POSTGRESQL_AVAILABLE` manually

### Performance Optimization

**For Better Performance**:
```json
{
  "ENABLE_DEBUG_LOGGING": false,  // Disable in production
  "UI_PROFILE": {
    "value": "compact",  // Use on lower-end machines
    "choices": ["auto", "compact", "normal"]
  }
}
```

### Development Settings

**For Development**:
```json
{
  "ENABLE_DEBUG_LOGGING": true,  // Detailed logs
  "UI_PROFILE": {
    "value": "normal",  // Full spacing for testing
    "choices": ["auto", "compact", "normal"]
  }
}
```

## See Also

- [Architecture Overview](../developer-guide/architecture) - Configuration system architecture
- [Code Style Guide](../developer-guide/code-style) - Configuration conventions
- [Testing Guide](../developer-guide/testing) - Configuration testing

## Version History

- **v2.2.0** - Initial JSON configuration system with ChoicesType
- **v2.2.2** - Added UI tree editor and live reload
- **v2.3.0** - Added automatic backup system
- **v2.3.7** - Improved validation and migration
- **v2.4.0** (planned) - Configuration profiles and import/export
