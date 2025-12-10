# Configuration File Migration

## Overview

FilterMate now stores `config.json` in the same directory as the plugin's SQLite database (`APP_SQLITE_PATH`) instead of in the plugin installation directory. This change improves configuration management and separates user data from plugin code.

## What Changed

### Before (Old Location)
```
<QGIS_PLUGIN_DIR>/filter_mate/config/config.json
```

### After (New Location)
```
<QGIS_SETTINGS_PATH>/FilterMate/config.json
```

**Default paths:**
- **Windows**: `C:\Users\<Username>\AppData\Roaming\QGIS\QGIS3\profiles\default\FilterMate\config.json`
- **Linux**: `~/.local/share/QGIS/QGIS3/profiles/default/FilterMate/config.json`
- **macOS**: `~/Library/Application Support/QGIS/QGIS3/profiles/default/FilterMate/config.json`

## Automatic Migration

The migration happens automatically when you start QGIS with the updated plugin:

1. **Detection**: Plugin checks if `config.json` exists in old location
2. **Migration**: If found, it copies the file to the new location
3. **Backup**: Old config is renamed to `config.json.migrated` (kept as backup)
4. **Verification**: Plugin verifies new location is accessible

### Migration Process

```python
# Executed automatically in config.py during plugin initialization
migrate_config_to_sqlite_dir()
```

**Steps:**
1. Read config from plugin directory to get `APP_SQLITE_PATH`
2. Create SQLite directory if it doesn't exist
3. Copy config to new location
4. Rename old config to `.migrated` (backup)
5. All future reads/writes use new location

## Benefits

### 1. **Separation of Concerns**
- User data (`config.json`, databases) in user directory
- Plugin code in plugin directory
- No mixing of runtime data with installation files

### 2. **Plugin Updates**
- Updates won't overwrite your configuration
- No need to backup config before updating
- Config persists across plugin reinstalls

### 3. **Profile Support**
- Each QGIS profile has its own config
- Easy to manage multiple configurations
- Better isolation between profiles

### 4. **Backup & Portability**
- All user data in one directory
- Easy to backup entire FilterMate directory
- Simple to transfer settings between machines

## Code Changes

### New Helper Function

```python
from config.config import get_config_path

# Always returns correct path (new location)
config_path = get_config_path()

# Use for reading
with open(get_config_path(), 'r') as f:
    config = json.load(f)

# Use for writing
with open(get_config_path(), 'w') as f:
    json.dump(config, f, indent=4)
```

### Updated Files

1. **config/config.py**
   - Added `get_config_path()` function
   - Added `migrate_config_to_sqlite_dir()` function
   - Updated `init_env_vars()` to handle migration
   - Modified all config read/write to use new location

2. **filter_mate_app.py**
   - Updated config writes to use `get_config_path()`
   - Removed hardcoded path construction

3. **filter_mate_dockwidget.py**
   - Updated config reads/writes to use `get_config_path()`
   - Consistent path handling across all methods

4. **modules/config_migration.py** (NEW)
   - Helper functions for migration verification
   - Debugging utilities for config location

## Troubleshooting

### Config Not Found After Update

If the plugin can't find your config after updating:

```python
# Check config location
from modules.config_migration import log_config_location
log_config_location()
```

**Output will show:**
- Current config path
- SQLite directory
- Plugin directory
- Migration status

### Manual Migration

If automatic migration fails, you can manually migrate:

1. **Find old config:**
   ```
   <QGIS_PLUGIN_DIR>/filter_mate/config/config.json
   ```

2. **Copy to new location:**
   - Windows: `%APPDATA%\QGIS\QGIS3\profiles\default\FilterMate\`
   - Linux/Mac: `~/.local/share/QGIS/QGIS3/profiles/default/FilterMate/`

3. **Restart QGIS**

### Permission Issues

If you get permission errors:

1. Check directory permissions:
   ```bash
   # Linux/Mac
   ls -la ~/.local/share/QGIS/QGIS3/profiles/default/FilterMate/
   ```

2. Ensure directory is writable:
   ```bash
   # Linux/Mac
   chmod -R u+w ~/.local/share/QGIS/QGIS3/profiles/default/FilterMate/
   ```

### Verify Migration

Run the test suite:

```bash
cd tests/
python test_config_migration.py
```

**Expected output:**
```
test_config_migration_simulation ... ok
test_config_path_structure ... ok
test_config_read_write_new_location ... ok

----------------------------------------------------------------------
Ran 3 tests in 0.002s

OK
```

## Backward Compatibility

### For Developers

If you have custom code reading config:

**❌ Old way (breaks):**
```python
config_path = ENV_VARS["DIR_CONFIG"] + os.sep + 'config.json'
with open(config_path, 'r') as f:
    config = json.load(f)
```

**✅ New way (works):**
```python
from config.config import get_config_path

with open(get_config_path(), 'r') as f:
    config = json.load(f)
```

### For Users

No action required! Migration is automatic. Your settings are preserved.

## Migration Verification Checklist

After updating the plugin, verify:

- [ ] Plugin starts without errors
- [ ] Configuration loads correctly
- [ ] Can save configuration changes
- [ ] Old config has `.migrated` extension (backup exists)
- [ ] New config exists in SQLite directory

## Related Files

- `config/config.py` - Core configuration management
- `modules/config_migration.py` - Migration helpers
- `tests/test_config_migration.py` - Migration tests
- `.github/copilot-instructions.md` - Updated developer guidelines

## Questions?

- Check logs: QGIS Menu → View → Panels → Log Messages → FilterMate
- Run diagnostics: `log_config_location()` in Python console
- Report issues: https://github.com/sducournau/filter_mate/issues
