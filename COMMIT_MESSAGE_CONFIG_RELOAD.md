feat: Add configuration reload and reset system

Implements a comprehensive configuration management system with reload, reset, 
and backup capabilities for FilterMate plugin.

## New Features

### Configuration Management
- Load default configuration from template
- Reset configuration to defaults with backup
- Reload configuration from disk
- Save configuration with validation
- Automatic backup creation with timestamps

### Files Created

1. **config/config.default.json**
   - Default configuration template (read-only)
   - Default CRS: EPSG:3857 (Web Mercator)
   - Empty layer lists for clean project start
   - Reference for all reset operations

2. **New Functions in config/config.py**
   - `load_default_config()`: Load default template
   - `reset_config_to_default()`: Reset with backup and settings preservation
   - `reload_config()`: Reload from disk and update ENV_VARS
   - `save_config()`: Save with error handling

3. **Helper Functions in modules/config_helpers.py**
   - `reload_config_from_file()`: Convenience wrapper
   - `reset_config_to_defaults()`: Convenience wrapper
   - `save_config_to_file()`: Convenience wrapper

4. **Documentation**
   - docs/CONFIG_RELOAD.md: Complete system documentation
   - docs/CONFIG_RELOAD_SUMMARY.md: Quick reference and integration guide
   - docs/PROJECT_CHANGE_INTEGRATION.py: Integration examples

5. **Tests**
   - tests/test_config_reload.py: Comprehensive test suite

### Configuration Cleanup

- **config/config.json**
  - Removed duplicate EXPORT section (kept EXPORTING)
  - Cleared LAYERS_TO_EXPORT lists
  - Set default CRS to EPSG:3857
  - Cleared project-specific layers list

## Key Features

### Backup System
- Automatic backup creation: `config.backup.YYYYMMDD_HHMMSS.json`
- Optional backup preservation
- Manual restore capability

### Settings Preservation
- Option to preserve APP_SQLITE_PATH on reset
- Keeps user preferences while resetting project data
- Selective reset capability

### Project Change Detection
- Ready for integration with QGIS project signals
- Automatic config reset when project changes
- Example code provided in documentation

## Usage Examples

### Reset to Defaults
```python
from config.config import reset_config_to_default
success = reset_config_to_default(backup=True, preserve_app_settings=True)
```

### Reload Configuration
```python
from config.config import reload_config
config = reload_config()
```

### Save Changes
```python
from config.config import save_config
config["CURRENT_PROJECT"]["EXPORTING"]["PROJECTION_TO_EXPORT"] = "EPSG:3857"
save_config(config)
```

### Project Change Integration
```python
def on_project_loaded(self):
    from config.config import load_default_config, save_config
    
    current_path = self.PROJECT.fileName()
    stored_path = self.CONFIG_DATA["CURRENT_PROJECT"]["OPTIONS"]["PROJECT_PATH"]
    
    if current_path != stored_path:
        default_config = load_default_config()
        self.CONFIG_DATA["CURRENT_PROJECT"] = default_config["CURRENT_PROJECT"]
        save_config(self.CONFIG_DATA)
```

## Testing

Run test suite:
```bash
cd tests
python test_config_reload.py
```

Tests verify:
- Default config loading
- Reset with backup creation
- Reload from file
- Save and reload cycle
- Helper function wrappers

## Benefits

- ✓ Clean configuration on project change
- ✓ No residual data from previous projects
- ✓ Consistent default CRS (EPSG:3857)
- ✓ Automatic backups for safety
- ✓ Preserves user app settings
- ✓ Comprehensive test coverage
- ✓ Detailed documentation
- ✓ Easy to integrate

## Breaking Changes

None - fully backward compatible. Existing config.json files remain valid.

## Next Steps

- Integrate project change detection in filter_mate_app.py
- Add UI for manual reset (optional)
- Implement automatic cleanup of old backups (optional)

---

Refs: #config-management #reload #reset #backup
