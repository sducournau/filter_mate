"""
Test structure améliorée de config.default.json avec métadonnées intégrées

Valide que:
1. Les métadonnées sont correctement intégrées
2. ConfigMetadataHandler fonctionne correctement
3. La structure est compatible avec qt_json_view
"""

import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.config_metadata_handler import ConfigMetadataHandler, MetadataAwareConfigModel


def test_config_default_structure():
    """Test that config.default.json has improved integrated metadata structure"""
    
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'config',
        'config.default.json'
    )
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    print("\n=== Testing Improved Config Structure ===\n")
    
    # Test 1: Version marker
    assert "_CONFIG_VERSION" in config, "❌ Missing _CONFIG_VERSION"
    assert config["_CONFIG_VERSION"] == "2.0", "❌ Wrong version"
    print("✓ Version marker: 2.0")
    
    # Test 2: Integrated metadata in LANGUAGE
    language = config["APP"]["DOCKWIDGET"]["LANGUAGE"]
    assert "value" in language, "❌ Missing value in LANGUAGE"
    assert "choices" in language, "❌ Missing choices in LANGUAGE"
    assert "description" in language, "❌ Missing description in LANGUAGE"
    print("✓ LANGUAGE has integrated metadata (value, choices, description)")
    
    # Test 3: No separate _META sections
    meta_count = sum(1 for key in config["APP"]["DOCKWIDGET"].keys() if key.startswith("_") and key != "_CONFIG_VERSION")
    # Should only have _CONFIG_VERSION at top level, not _*_META sections
    dockwidget_meta = sum(1 for key in config["APP"]["DOCKWIDGET"].keys() if key.startswith("_"))
    assert dockwidget_meta == 0, f"❌ Found {dockwidget_meta} _*_META sections in DOCKWIDGET (should be 0)"
    print("✓ No fragmented _*_META sections (metadata integrated)")
    
    # Test 4: FEEDBACK_LEVEL structure
    feedback = config["APP"]["DOCKWIDGET"]["FEEDBACK_LEVEL"]
    assert "value" in feedback, "❌ Missing value in FEEDBACK_LEVEL"
    assert "choices" in feedback, "❌ Missing choices in FEEDBACK_LEVEL"
    assert "description" in feedback, "❌ Missing description in FEEDBACK_LEVEL"
    assert "categories_affected" in feedback, "❌ Missing categories_affected in FEEDBACK_LEVEL"
    print("✓ FEEDBACK_LEVEL has integrated structure with description and metadata")
    
    # Test 5: SMALL_DATASET_OPTIMIZATION structure
    opt = config["APP"]["OPTIONS"]["SMALL_DATASET_OPTIMIZATION"]
    assert "description" in opt, "❌ Missing description in SMALL_DATASET_OPTIMIZATION"
    assert "enabled" in opt and "value" in opt["enabled"], "❌ Wrong enabled structure"
    assert "threshold" in opt and "value" in opt["threshold"], "❌ Wrong threshold structure"
    assert "method" in opt and "value" in opt["method"], "❌ Wrong method structure"
    print("✓ SMALL_DATASET_OPTIMIZATION has proper structure with nested values")
    
    # Test 6: Icons structure
    icons_sizes = config["APP"]["DOCKWIDGET"]["PushButton"]["ICONS_SIZES"]
    assert "description" in icons_sizes, "❌ Missing description in ICONS_SIZES"
    assert "ACTION" in icons_sizes and isinstance(icons_sizes["ACTION"], dict), "❌ Wrong ACTION structure"
    assert "value" in icons_sizes["ACTION"], "❌ Missing value in ACTION"
    assert "description" in icons_sizes["ACTION"], "❌ Missing description in ACTION"
    print("✓ ICONS_SIZES has integrated metadata for each icon type")
    
    return True


def test_metadata_handler():
    """Test ConfigMetadataHandler functions"""
    
    print("\n=== Testing ConfigMetadataHandler ===\n")
    
    # Test 1: Extract metadata
    config_item = {
        "value": "auto",
        "choices": ["auto", "en", "fr"],
        "description": "Language selection",
        "available_translations": ["en (English)", "fr (Français)"]
    }
    
    metadata = ConfigMetadataHandler.extract_metadata(config_item)
    assert "description" in metadata, "❌ Description not extracted"
    assert "available_translations" in metadata, "❌ Metadata not extracted"
    print("✓ extract_metadata() works correctly")
    
    # Test 2: Get description
    desc = ConfigMetadataHandler.get_description(config_item)
    assert desc == "Language selection", "❌ Wrong description"
    print("✓ get_description() returns correct value")
    
    # Test 3: Has description
    assert ConfigMetadataHandler.has_description(config_item) is True, "❌ has_description() failed"
    assert ConfigMetadataHandler.has_description({"value": 42}) is False, "❌ has_description() should return False"
    print("✓ has_description() works correctly")
    
    # Test 4: Editable value detection
    assert ConfigMetadataHandler.is_editable_value("description", "text") is False, "❌ description should not be editable"
    assert ConfigMetadataHandler.is_editable_value("value", 42) is True, "❌ value should be editable"
    print("✓ is_editable_value() works correctly")
    
    # Test 5: Get displayable value
    value, vtype = ConfigMetadataHandler.get_displayable_value(config_item)
    assert value == "auto", "❌ Wrong value extracted"
    assert vtype == "choice", "❌ Wrong type (should be choice)"
    print("✓ get_displayable_value() detects choice type")
    
    # Test 6: Format metadata for tooltip
    tooltip = ConfigMetadataHandler.format_metadata_for_tooltip(config_item)
    assert "Language selection" in tooltip, "❌ Description not in tooltip"
    assert "Available languages" in tooltip, "❌ Translations not formatted in tooltip"
    print("✓ format_metadata_for_tooltip() formats correctly")
    
    return True


def test_metadata_aware_model():
    """Test MetadataAwareConfigModel"""
    
    print("\n=== Testing MetadataAwareConfigModel ===\n")
    
    config_data = {
        "APP": {
            "DOCKWIDGET": {
                "LANGUAGE": {
                    "value": "auto",
                    "choices": ["auto", "en", "fr"],
                    "description": "Language selection"
                }
            }
        }
    }
    
    model = MetadataAwareConfigModel(config_data)
    
    # Test 1: Get metadata at path
    path = ["APP", "DOCKWIDGET", "LANGUAGE"]
    metadata = model.get_metadata(path)
    assert "description" in metadata, "❌ Metadata not found at path"
    print("✓ get_metadata() retrieves metadata for path")
    
    # Test 2: Get description at path
    desc = model.get_description(path)
    assert desc == "Language selection", "❌ Wrong description from path"
    print("✓ get_description() retrieves description for path")
    
    # Test 3: Invalid path returns empty
    metadata = model.get_metadata(["INVALID", "PATH"])
    assert metadata == {}, "❌ Should return empty dict for invalid path"
    desc = model.get_description(["INVALID", "PATH"])
    assert desc == "", "❌ Should return empty string for invalid path"
    print("✓ Invalid paths handled gracefully")
    
    return True


def test_json_validity():
    """Test that config.default.json is still valid JSON"""
    
    print("\n=== Testing JSON Validity ===\n")
    
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'config',
        'config.default.json'
    )
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        print("✓ config.default.json is valid JSON")
        print(f"  Size: {len(json.dumps(config))} bytes")
        return True
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        return False


if __name__ == '__main__':
    try:
        success = True
        success &= test_json_validity()
        success &= test_config_default_structure()
        success &= test_metadata_handler()
        success &= test_metadata_aware_model()
        
        if success:
            print("\n" + "="*50)
            print("✓ All tests passed!")
            print("="*50)
            exit(0)
        else:
            print("\n" + "="*50)
            print("❌ Some tests failed")
            print("="*50)
            exit(1)
    except Exception as e:
        print(f"\n❌ Test error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
