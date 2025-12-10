# Configuration Reload System

## Overview

FilterMate now includes a robust configuration reload system that allows you to:
- Reset configuration to default values
- Reload configuration from disk
- Save configuration changes
- Create automatic backups

## Files

- **config/config.default.json**: Default configuration template (read-only)
- **config/config.json**: Active configuration (modified at runtime)
- **config/config.backup.*.json**: Automatic backups (created on reset)

## Functions

### In `config/config.py`

#### `load_default_config()`
Load the default configuration from `config.default.json`.

```python
from config.config import load_default_config

default_config = load_default_config()
```

#### `reset_config_to_default(backup=True, preserve_app_settings=True)`
Reset `config.json` to default values.

**Parameters:**
- `backup` (bool): Create backup before resetting (default: True)
- `preserve_app_settings` (bool): Keep APP_SQLITE_PATH and other app settings (default: True)

```python
from config.config import reset_config_to_default

# Reset with backup and preserve app settings
success = reset_config_to_default()

# Reset without backup
success = reset_config_to_default(backup=False)

# Reset and clear all settings
success = reset_config_to_default(preserve_app_settings=False)
```

#### `reload_config()`
Reload configuration from `config.json` and update `ENV_VARS`.

```python
from config.config import reload_config

new_config = reload_config()
```

#### `save_config(config_data)`
Save configuration data to `config.json`.

```python
from config.config import save_config

config_data["CURRENT_PROJECT"]["EXPORTING"]["PROJECTION_TO_EXPORT"] = "EPSG:3857"
success = save_config(config_data)
```

### In `modules/config_helpers.py`

Convenience wrappers for the above functions:

```python
from modules.config_helpers import (
    reload_config_from_file,
    reset_config_to_defaults,
    save_config_to_file
)

# Reload
config = reload_config_from_file()

# Reset
success = reset_config_to_defaults(backup=True, preserve_app_settings=True)

# Save
success = save_config_to_file(config_data)
```

## Usage Examples

### 1. Reset Configuration on Project Change

When a user opens a different QGIS project, reset project-specific settings:

```python
from config.config import ENV_VARS, load_default_config, save_config

# Get current config
current_config = ENV_VARS["CONFIG_DATA"]

# Load defaults for CURRENT_PROJECT only
default_config = load_default_config()

# Replace project settings with defaults
current_config["CURRENT_PROJECT"] = default_config["CURRENT_PROJECT"]

# Save
save_config(current_config)
```

### 2. Clear Project-Specific Data

Clear layers and export settings when project changes:

```python
config_data["CURRENT_PROJECT"]["EXPORTING"]["LAYERS_TO_EXPORT"] = []
config_data["CURRENT_PROJECT"]["EXPORTING"]["PROJECTION_TO_EXPORT"] = "EPSG:3857"
config_data["CURRENT_PROJECT"]["layers"] = []

save_config(config_data)
```

### 3. Full Reset with Backup

Reset entire configuration to defaults:

```python
from config.config import reset_config_to_default

# Creates backup at: config/config.backup.20251210_143022.json
success = reset_config_to_default(backup=True, preserve_app_settings=True)

if success:
    # Reload to update runtime variables
    reload_config()
```

### 4. Restore from Backup

Manually restore from a backup:

```python
import shutil
from pathlib import Path

config_dir = Path(__file__).parent / "config"
backup_file = config_dir / "config.backup.20251210_143022.json"
config_file = config_dir / "config.json"

shutil.copy2(backup_file, config_file)
reload_config()
```

## Testing

Run the test suite:

```bash
cd tests
python test_config_reload.py
```

Tests verify:
- Loading default configuration
- Resetting to defaults with backup
- Reloading from file
- Save and reload cycle
- Config helper functions

## Best Practices

### 1. Always Backup on Reset
```python
# Good
reset_config_to_default(backup=True)

# Risky
reset_config_to_default(backup=False)
```

### 2. Preserve App Settings
```python
# Good - preserve user's APP_SQLITE_PATH
reset_config_to_default(preserve_app_settings=True)

# Only if intentional
reset_config_to_default(preserve_app_settings=False)
```

### 3. Reload After External Changes
```python
# After modifying config.json manually
reload_config()
```

### 4. Use Helpers for Convenience
```python
# Instead of importing from config.config
from modules.config_helpers import reload_config_from_file
config = reload_config_from_file()
```

## Project Change Detection

To automatically reset config when project changes, add this to `filter_mate_app.py`:

```python
def on_project_read(self):
    """Called when project is loaded"""
    from config.config import ENV_VARS, load_default_config, save_config
    
    current_project_path = self.PROJECT.fileName()
    stored_project_path = self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_PATH"]
    
    if current_project_path != stored_project_path:
        # Different project - reset project settings
        default_config = load_default_config()
        
        # Keep APP settings, reset CURRENT_PROJECT
        self.CONFIG_DATA["CURRENT_PROJECT"] = default_config["CURRENT_PROJECT"]
        
        # Update project path
        self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_PATH"] = current_project_path
        
        # Save
        save_config(self.CONFIG_DATA)
        
        print("FilterMate: Project settings reset for new project")
```

## Configuration Structure

### APP Section (Preserved on Reset)
- UI settings (theme, profile, colors)
- Button styles and icons
- App-wide options (GitHub URLs, SQLite paths)

### CURRENT_PROJECT Section (Reset on Project Change)
- Export settings and layer lists
- Project-specific options
- Layer properties and filters

## Default Values

### Default CRS
```json
"PROJECTION_TO_EXPORT": "EPSG:3857"
```

### Default Layer Lists
```json
"LAYERS_TO_EXPORT": []
```

### Default Layer Properties
```json
"layers": []
```

## Troubleshooting

### Config Not Reloading
```python
# Force reload
from config.config import reload_config
reload_config()

# Check ENV_VARS
from config.config import ENV_VARS
print(ENV_VARS["CONFIG_DATA"]["CURRENT_PROJECT"]["EXPORTING"]["PROJECTION_TO_EXPORT"])
```

### Backup Not Created
Check write permissions in config directory:
```bash
ls -la config/
```

### Default Config Not Found
Ensure `config.default.json` exists:
```bash
ls -la config/config.default.json
```

## Migration Guide

### From Old System

Before:
```python
# Manual file operations
with open('config.json', 'r') as f:
    config = json.load(f)

# Modify
config["CURRENT_PROJECT"]["EXPORTING"]["LAYERS_TO_EXPORT"] = []

with open('config.json', 'w') as f:
    json.dump(config, f, indent=4)
```

After:
```python
# Use helpers
from modules.config_helpers import reload_config_from_file, save_config_to_file

config = reload_config_from_file()
config["CURRENT_PROJECT"]["EXPORTING"]["LAYERS_TO_EXPORT"] = []
save_config_to_file(config)
```

## Future Enhancements

- [ ] Config versioning and migration
- [ ] Schema validation with JSON Schema
- [ ] Config profiles (per-project or per-user)
- [ ] UI for reset/reload operations
- [ ] Automatic cleanup of old backups
