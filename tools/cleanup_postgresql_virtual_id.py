#!/usr/bin/env python3
"""
FilterMate - PostgreSQL virtual_id Cleanup Tool

This script cleans up corrupted layer properties in FilterMate's Spatialite database
where PostgreSQL layers were incorrectly configured to use 'virtual_id' as their
primary key field.

PROBLEM:
- Virtual fields (virtual_id) created by QGIS only exist in memory
- They cannot be used in SQL queries executed on PostgreSQL
- Layers with virtual_id cause "column does not exist" errors

SOLUTION:
- This script removes the corrupted layer properties from FilterMate's database
- After running this script, you must re-add the affected PostgreSQL layers
- Ensure your PostgreSQL tables have proper PRIMARY KEY constraints

USAGE:
    python cleanup_postgresql_virtual_id.py

    Or from QGIS Python console:
    exec(open('/path/to/cleanup_postgresql_virtual_id.py').read())
"""

import sqlite3
import os
import sys
from pathlib import Path

def find_filtermate_db():
    """
    Locate FilterMate's Spatialite database.
    
    Returns:
        Path or None: Path to filter_mate.db if found
    """
    # Try common locations
    possible_paths = [
        # Current directory
        Path(".") / "filter_mate.db",
        # QGIS plugin directory (Windows)
        Path(os.path.expanduser("~")) / "AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/filter_mate.db",
        # QGIS plugin directory (Linux)
        Path(os.path.expanduser("~")) / ".local/share/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/filter_mate.db",
        # QGIS plugin directory (Mac)
        Path(os.path.expanduser("~")) / "Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/filter_mate/filter_mate.db",
    ]
    
    for path in possible_paths:
        if path.exists():
            return path
    
    return None


def cleanup_virtual_id_layers(db_path):
    """
    Clean up PostgreSQL layers with virtual_id primary key.
    
    Args:
        db_path (Path): Path to filter_mate.db
    
    Returns:
        tuple: (success, cleaned_count, layer_names)
    """
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        
        # Find PostgreSQL layers with virtual_id
        cur.execute("""
            SELECT DISTINCT p1.layer_id, p2.meta_value as layer_name
            FROM fm_project_layers_properties p1
            LEFT JOIN fm_project_layers_properties p2 
                ON p1.layer_id = p2.layer_id 
                AND p2.meta_key = 'layer_name'
            WHERE p1.meta_key = 'primary_key_name' 
              AND p1.meta_value = 'virtual_id'
              AND EXISTS (
                  SELECT 1 FROM fm_project_layers_properties p3
                  WHERE p3.layer_id = p1.layer_id
                    AND p3.meta_key = 'layer_provider'
                    AND p3.meta_value = 'postgresql'
              )
        """)
        
        problematic_layers = cur.fetchall()
        
        if not problematic_layers:
            print("✅ No corrupted PostgreSQL layers found!")
            return True, 0, []
        
        print(f"\n⚠️  Found {len(problematic_layers)} PostgreSQL layer(s) with virtual_id:\n")
        layer_names = []
        for layer_id, layer_name in problematic_layers:
            display_name = layer_name if layer_name else layer_id
            layer_names.append(display_name)
            print(f"  - {display_name} (ID: {layer_id})")
        
        print("\n❓ These layers will be REMOVED from FilterMate.")
        print("   You will need to re-add them after cleanup.")
        response = input("\nProceed with cleanup? (yes/no): ").strip().lower()
        
        if response not in ['yes', 'y', 'oui', 'o']:
            print("❌ Cleanup canceled by user")
            return False, 0, []
        
        # Delete properties for problematic layers
        cleaned = 0
        for layer_id, layer_name in problematic_layers:
            cur.execute("""
                DELETE FROM fm_project_layers_properties 
                WHERE layer_id = ?
            """, (layer_id,))
            cleaned += 1
            print(f"  ✅ Cleaned: {layer_name or layer_id}")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"\n✅ Successfully cleaned {cleaned} layer(s)")
        return True, cleaned, layer_names
        
    except Exception as e:
        print(f"\n❌ Error during cleanup: {e}")
        return False, 0, []


def main():
    """Main entry point."""
    print("=" * 60)
    print("FilterMate - PostgreSQL virtual_id Cleanup Tool")
    print("=" * 60)
    
    # Find database
    print("\n🔍 Searching for FilterMate database...")
    db_path = find_filtermate_db()
    
    if not db_path:
        print("❌ Could not find filter_mate.db")
        print("\nPlease specify the path manually:")
        manual_path = input("Path to filter_mate.db: ").strip()
        db_path = Path(manual_path)
        
        if not db_path.exists():
            print(f"❌ File not found: {db_path}")
            return 1
    
    print(f"✅ Found database: {db_path}")
    
    # Create backup
    backup_path = db_path.with_suffix('.db.backup')
    print(f"\n💾 Creating backup: {backup_path}")
    
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        print("✅ Backup created successfully")
    except Exception as e:
        print(f"⚠️  Warning: Could not create backup: {e}")
        response = input("\nContinue without backup? (yes/no): ").strip().lower()
        if response not in ['yes', 'y', 'oui', 'o']:
            print("❌ Cleanup canceled")
            return 1
    
    # Perform cleanup
    success, count, layer_names = cleanup_virtual_id_layers(db_path)
    
    if success and count > 0:
        print("\n" + "=" * 60)
        print("✅ CLEANUP COMPLETE")
        print("=" * 60)
        print("\n📋 Next steps:")
        print("  1. Restart QGIS")
        print("  2. Ensure your PostgreSQL tables have PRIMARY KEY constraints:")
        print()
        for name in layer_names:
            print(f'     ALTER TABLE "{name}" ADD PRIMARY KEY (id);')
        print()
        print("  3. Re-add the cleaned layers to FilterMate")
        print("  4. The virtual_id error should now be resolved")
        print()
        return 0
    elif success and count == 0:
        print("\n✅ No cleanup needed - database is clean")
        return 0
    else:
        print("\n❌ Cleanup failed or was canceled")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n❌ Cleanup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
