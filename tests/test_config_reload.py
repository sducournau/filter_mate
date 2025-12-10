"""
Test for configuration reload functionality

Tests:
1. Load default config
2. Reset config to defaults
3. Reload config from file
4. Save and reload cycle
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# Add plugin to path
plugin_path = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_path))

def test_load_default_config():
    """Test loading default configuration"""
    from config.config import load_default_config
    
    default_config = load_default_config()
    assert default_config is not None, "Failed to load default config"
    assert "APP" in default_config, "APP section missing from default config"
    assert "CURRENT_PROJECT" in default_config, "CURRENT_PROJECT section missing from default config"
    
    # Check default values
    assert default_config["CURRENT_PROJECT"]["EXPORTING"]["PROJECTION_TO_EXPORT"] == "EPSG:3857"
    assert default_config["CURRENT_PROJECT"]["EXPORTING"]["LAYERS_TO_EXPORT"] == []
    assert default_config["CURRENT_PROJECT"]["layers"] == []
    
    print("✓ Load default config test passed")


def test_reset_config():
    """Test resetting configuration to defaults"""
    from config.config import reset_config_to_default, load_default_config
    
    config_dir = Path(__file__).parent.parent / "config"
    config_path = config_dir / "config.json"
    
    # Load current config
    with open(config_path, 'r') as f:
        original_config = json.load(f)
    
    try:
        # Modify current config
        original_config["CURRENT_PROJECT"]["EXPORTING"]["LAYERS_TO_EXPORT"] = ["test_layer_1", "test_layer_2"]
        original_config["CURRENT_PROJECT"]["EXPORTING"]["PROJECTION_TO_EXPORT"] = "EPSG:2154"
        
        with open(config_path, 'w') as f:
            json.dump(original_config, f, indent=4)
        
        # Reset to defaults (with backup, preserve app settings)
        success = reset_config_to_default(backup=True, preserve_app_settings=True)
        assert success, "Failed to reset config"
        
        # Load reset config
        with open(config_path, 'r') as f:
            reset_config = json.load(f)
        
        # Verify reset values
        assert reset_config["CURRENT_PROJECT"]["EXPORTING"]["LAYERS_TO_EXPORT"] == []
        assert reset_config["CURRENT_PROJECT"]["EXPORTING"]["PROJECTION_TO_EXPORT"] == "EPSG:3857"
        
        # Verify backup was created
        backups = list(config_dir.glob("config.backup.*.json"))
        assert len(backups) > 0, "No backup file created"
        
        print("✓ Reset config test passed")
        
        # Clean up backups
        for backup in backups:
            backup.unlink()
            
    except Exception as e:
        print(f"✗ Reset config test failed: {e}")
        raise


def test_config_helpers():
    """Test config helper functions"""
    from modules.config_helpers import (
        reload_config_from_file,
        reset_config_to_defaults,
        save_config_to_file,
        get_config_value
    )
    
    config_dir = Path(__file__).parent.parent / "config"
    config_path = config_dir / "config.json"
    
    # Test get_config_value
    with open(config_path, 'r') as f:
        test_config = json.load(f)
    
    value = get_config_value(test_config, "CURRENT_PROJECT", "EXPORTING", "PROJECTION_TO_EXPORT")
    assert value == "EPSG:3857", f"Expected EPSG:3857, got {value}"
    
    # Test with ChoicesType format
    ui_profile = get_config_value(test_config, "APP", "DOCKWIDGET", "UI_PROFILE")
    assert ui_profile == "auto", f"Expected 'auto', got {ui_profile}"
    
    print("✓ Config helpers test passed")


def test_save_and_reload():
    """Test save and reload cycle"""
    from config.config import save_config, reload_config
    
    config_dir = Path(__file__).parent.parent / "config"
    config_path = config_dir / "config.json"
    
    # Load current config
    with open(config_path, 'r') as f:
        original_config = json.load(f)
    
    try:
        # Modify and save
        test_value = "TEST_LAYER_123"
        original_config["CURRENT_PROJECT"]["EXPORTING"]["LAYERS_TO_EXPORT"] = [test_value]
        
        success = save_config(original_config)
        assert success, "Failed to save config"
        
        # Reload
        reloaded_config = reload_config()
        assert reloaded_config is not None, "Failed to reload config"
        
        # Verify
        layers = reloaded_config["CURRENT_PROJECT"]["EXPORTING"]["LAYERS_TO_EXPORT"]
        assert test_value in layers, f"Test value not found after reload: {layers}"
        
        print("✓ Save and reload test passed")
        
    finally:
        # Restore original config
        with open(config_path, 'w') as f:
            json.dump(original_config, f, indent=4)


if __name__ == "__main__":
    print("Testing FilterMate configuration reload functionality...")
    print("=" * 60)
    
    try:
        test_load_default_config()
        test_reset_config()
        test_config_helpers()
        test_save_and_reload()
        
        print("=" * 60)
        print("✓ All tests passed!")
        
    except Exception as e:
        print("=" * 60)
        print(f"✗ Tests failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
