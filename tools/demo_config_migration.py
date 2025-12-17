#!/usr/bin/env python3
"""
Configuration Migration Demo

Interactive demonstration of the configuration migration system.
Shows all features: detection, migration, backup, validation, rollback.
"""

import sys
import os
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.config_migration import ConfigMigration


def print_header(title):
    """Print formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_config_summary(config, title="Configuration"):
    """Print summary of configuration structure."""
    print(f"\n{title}:")
    
    def count_keys(d, indent=0):
        count = 0
        for key, value in d.items():
            if key.startswith('_'):
                continue
            count += 1
            if isinstance(value, dict) and not ('value' in value and 'choices' in value):
                count += count_keys(value, indent + 1)
        return count
    
    total_keys = count_keys(config)
    print(f"  Total keys: {total_keys}")
    
    # Show top-level structure
    print("  Structure:")
    for key in config.keys():
        if not key.startswith('_'):
            print(f"    • {key}")


def demo_version_detection():
    """Demonstrate version detection."""
    print_header("1. Version Detection")
    
    migrator = ConfigMigration()
    
    # Test cases
    test_configs = {
        "v1.0 config": {
            "APP": {
                "DOCKWIDGET": {
                    "FEEDBACK_LEVEL": {"value": "normal", "choices": []}
                }
            }
        },
        "v2.0 config": {
            "_schema_version": "2.0",
            "app": {
                "ui": {}
            }
        },
        "Unknown config": {
            "random_key": "random_value"
        }
    }
    
    for name, config in test_configs.items():
        version = migrator.detect_version(config)
        needs_migration = migrator.needs_migration(config)
        print(f"\n{name}:")
        print(f"  Detected version: {version}")
        print(f"  Needs migration: {'Yes ⚠️' if needs_migration else 'No ✓'}")


def demo_migration():
    """Demonstrate migration process."""
    print_header("2. Migration Process (v1.0 → v2.0)")
    
    # Sample v1.0 config
    config_v1 = {
        "APP": {
            "AUTO_ACTIVATE": {"value": False},
            "DOCKWIDGET": {
                "FEEDBACK_LEVEL": {
                    "value": "normal",
                    "choices": ["minimal", "normal", "verbose"]
                },
                "UI_PROFILE": {
                    "value": "auto",
                    "choices": ["auto", "compact", "normal"]
                },
                "COLORS": {
                    "ACTIVE_THEME": {
                        "value": "dark",
                        "choices": ["auto", "default", "dark", "light"]
                    }
                },
                "BUTTONS": {
                    "ICON_SIZE": {
                        "ACTION_BUTTONS": 25,
                        "OTHERS": 20
                    }
                }
            }
        }
    }
    
    print("\nOriginal v1.0 configuration:")
    print_config_summary(config_v1, "Before migration")
    
    migrator = ConfigMigration()
    print("\n⚙️ Performing migration...")
    
    migrated, warnings = migrator.migrate(config_v1, create_backup=False, validate=True)
    
    print("\n✓ Migration completed!")
    print_config_summary(migrated, "After migration")
    
    # Show specific changes
    print("\nKey changes:")
    print(f"  • Version marker: {migrated.get('_schema_version')}")
    print(f"  • Migrated from: {migrated.get('_migrated_from')}")
    print(f"  • Structure: APP.DOCKWIDGET → app.ui")
    
    if warnings:
        print(f"\n⚠️ Warnings ({len(warnings)}):")
        for warning in warnings:
            print(f"  • {warning}")
    else:
        print("\n✓ No warnings")
    
    return migrated


def demo_validation():
    """Demonstrate validation."""
    print_header("3. Validation")
    
    # Create a sample migrated config
    migrator = ConfigMigration()
    config_v1 = {
        "APP": {
            "DOCKWIDGET": {
                "FEEDBACK_LEVEL": {"value": "normal", "choices": []}
            }
        }
    }
    
    migrated, _ = migrator.migrate(config_v1, create_backup=False, validate=False)
    
    print("\nValidating migrated configuration...")
    validation_warnings = migrator.validate_migrated_config(migrated)
    
    if validation_warnings:
        print(f"\n⚠️ Validation issues ({len(validation_warnings)}):")
        for warning in validation_warnings:
            print(f"  • {warning}")
    else:
        print("\n✓ Configuration is valid")


def demo_backup_system():
    """Demonstrate backup system."""
    print_header("4. Backup System")
    
    # Create temporary test directory
    import tempfile
    test_dir = tempfile.mkdtemp()
    config_path = os.path.join(test_dir, "config.json")
    
    try:
        migrator = ConfigMigration(config_path)
        
        # Create sample config
        config = {"APP": {"test": "value"}}
        
        print("\nCreating backups...")
        backup1 = migrator.create_backup(config)
        print(f"  Backup 1: {os.path.basename(backup1)}")
        
        import time
        time.sleep(1)  # Ensure different timestamp
        
        backup2 = migrator.create_backup(config)
        print(f"  Backup 2: {os.path.basename(backup2)}")
        
        # List backups
        print("\nListing all backups:")
        backups = migrator.list_backups()
        
        for i, backup in enumerate(backups, 1):
            print(f"  {i}. {backup['filename']}")
            print(f"     Date: {backup['date'][:19]}")
            print(f"     Version: v{backup['version']}")
            print(f"     Size: {backup['size']} bytes")
        
        print(f"\n✓ Total backups: {len(backups)}")
        
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(test_dir)


def demo_value_extraction():
    """Demonstrate value extraction from ChoicesType."""
    print_header("5. Value Extraction")
    
    migrator = ConfigMigration()
    
    test_values = [
        {"value": "normal", "choices": ["minimal", "normal", "verbose"]},
        {"value": "auto"},
        "plain_string",
        123,
        True
    ]
    
    print("\nExtracting values from different formats:")
    for i, test_val in enumerate(test_values, 1):
        result = migrator._extract_value(test_val)
        print(f"\n  {i}. Input: {test_val}")
        print(f"     Output: {result}")
        print(f"     Type: {type(result).__name__}")


def demo_mapping_examples():
    """Show mapping examples."""
    print_header("6. Mapping Examples (v1.0 → v2.0)")
    
    mappings = [
        ("APP.DOCKWIDGET.FEEDBACK_LEVEL", "app.ui.feedback.level", "Feedback level"),
        ("APP.DOCKWIDGET.UI_PROFILE", "app.ui.profile", "UI profile"),
        ("APP.DOCKWIDGET.COLORS.ACTIVE_THEME", "app.ui.theme.active", "Active theme"),
        ("APP.DOCKWIDGET.BUTTONS.ICON_SIZE.ACTION_BUTTONS", "app.buttons.icon_sizes.action", "Action icon size"),
        ("APP.DOCKWIDGET.EXPORT.STYLE", "app.export.style.format", "Export style format"),
        ("CURRENT_PROJECT.OPTIONS.FEATURE_COUNT_LIMIT", "app.project.feature_count_limit", "Feature limit"),
    ]
    
    print("\nKey path transformations:")
    print(f"\n{'Old (v1.0)':<50} → {'New (v2.0)':<40}")
    print("-" * 92)
    
    for old, new, desc in mappings:
        print(f"{old:<50} → {new:<40}")


def interactive_migration():
    """Interactive migration tool."""
    print_header("Interactive Migration")
    
    print("\nThis will demonstrate a full migration cycle.")
    
    # Create sample v1 config
    config_v1 = {
        "APP": {
            "AUTO_ACTIVATE": {"value": False},
            "DOCKWIDGET": {
                "FEEDBACK_LEVEL": {"value": "normal", "choices": ["minimal", "normal", "verbose"]},
                "UI_PROFILE": {"value": "compact", "choices": ["auto", "compact", "normal"]},
                "COLORS": {
                    "ACTIVE_THEME": {"value": "dark", "choices": ["auto", "default", "dark", "light"]}
                }
            }
        }
    }
    
    print("\nSample v1.0 configuration created")
    print_config_summary(config_v1, "Original")
    
    migrator = ConfigMigration()
    
    # Detect version
    version = migrator.detect_version(config_v1)
    print(f"\n✓ Detected version: {version}")
    
    # Check if migration needed
    if migrator.needs_migration(config_v1):
        print("⚠️ Migration required!")
        
        response = input("\nProceed with migration? (y/n): ")
        
        if response.lower() == 'y':
            print("\n⚙️ Migrating...")
            
            migrated, warnings = migrator.migrate(config_v1, create_backup=False, validate=True)
            
            print("\n✓ Migration completed!")
            print_config_summary(migrated, "Migrated")
            
            # Show some migrated values
            print("\nMigrated values:")
            if "app" in migrated and "ui" in migrated["app"]:
                ui = migrated["app"]["ui"]
                if "profile" in ui:
                    print(f"  • UI Profile: {ui['profile']}")
                if "feedback" in ui and "level" in ui["feedback"]:
                    print(f"  • Feedback Level: {ui['feedback']['level']}")
                if "theme" in ui and "active" in ui["theme"]:
                    print(f"  • Theme: {ui['theme']['active']}")
            
            if warnings:
                print(f"\n⚠️ Warnings:")
                for warning in warnings[:5]:
                    print(f"  • {warning}")
        else:
            print("\nMigration cancelled")
    else:
        print("✓ No migration needed")


def main():
    """Run all demonstrations."""
    print("\n" + "╔" + "=" * 68 + "╗")
    print("║" + " " * 18 + "Configuration Migration Demo" + " " * 22 + "║")
    print("╚" + "=" * 68 + "╝")
    
    try:
        demo_version_detection()
        demo_migration()
        demo_validation()
        demo_backup_system()
        demo_value_extraction()
        demo_mapping_examples()
        
        print_header("Interactive Demo")
        print("\nWould you like to try interactive migration?")
        response = input("Enter 'y' for yes, any other key to skip: ")
        
        if response.lower() == 'y':
            interactive_migration()
        
        print_header("Demo Complete")
        print("\n✓ All demonstrations completed successfully!")
        print("\nNext steps:")
        print("  1. Run tests: python tests/test_config_migration.py")
        print("  2. Migrate real config: python modules/config_migration.py")
        print("  3. Read docs: docs/CONFIG_MIGRATION.md")
        print("\n")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
