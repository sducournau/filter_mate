"""
Fix script to update layers that incorrectly use 'ctid' when they have a proper 'id' field.

This script will:
1. Scan all PostgreSQL layers in the FilterMate database
2. Check if they use 'ctid' as primary key
3. Check if they have a field with 'id' in the name
4. Update the database to use the proper ID field
5. Update QGIS layer variables

Usage from QGIS Python console:
    exec(open(r'C:\Users\Simon\AppData\Roaming\QGIS\QGIS3\profiles\imagodata\python\plugins\filter_mate\tools\diagnostic\fix_ctid_layers.py').read())
"""

import sqlite3
import json
from qgis.core import QgsProject, QgsExpressionContextUtils
from pathlib import Path

def fix_ctid_layers():
    """Fix layers that incorrectly use ctid."""
    
    # Get FilterMate database path
    import os
    plugin_dir = Path(__file__).parent.parent.parent
    db_path = plugin_dir / "filterMate.db"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    print("\n" + "="*80)
    print("FIXING CTID LAYERS")
    print("="*80 + "\n")
    
    # Connect to database
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Get project UUID
    cursor.execute("SELECT project_uuid FROM fm_project LIMIT 1")
    result = cursor.fetchone()
    if not result:
        print("❌ No FilterMate project found in database")
        conn.close()
        return
    
    project_uuid = result[0]
    print(f"Project UUID: {project_uuid}\n")
    
    # Find all layers with ctid as primary key
    cursor.execute("""
        SELECT DISTINCT layer_id, meta_value as layer_name
        FROM fm_project_layers_properties
        WHERE fk_project = ?
          AND meta_type = 'infos'
          AND meta_key = 'primary_key_name'
          AND meta_value = 'ctid'
    """, (project_uuid,))
    
    ctid_layers = cursor.fetchall()
    
    if not ctid_layers:
        print("✓ No layers using ctid found")
        conn.close()
        return
    
    print(f"Found {len(ctid_layers)} layer(s) using ctid\n")
    
    project = QgsProject.instance()
    fixed_count = 0
    
    for layer_id, _ in ctid_layers:
        # Get layer from QGIS
        layer = project.mapLayer(layer_id)
        if not layer:
            print(f"⚠️  Layer {layer_id} not found in QGIS project, skipping")
            continue
        
        print(f"Checking layer: {layer.name()} ({layer_id})")
        
        # Check if it's a PostgreSQL layer
        if layer.providerType() != 'postgres':
            print(f"  ⚠️  Not a PostgreSQL layer, skipping")
            continue
        
        # Find a suitable ID field
        id_field = None
        id_field_idx = None
        for idx, field in enumerate(layer.fields()):
            if 'id' in field.name().lower():
                id_field = field.name()
                id_field_idx = idx
                print(f"  ✓ Found ID field: '{id_field}' (index {idx})")
                break
        
        if not id_field:
            print(f"  ✗ No ID field found, cannot fix")
            continue
        
        # Get field properties
        field = layer.fields()[id_field_idx]
        field_type = field.typeName()
        is_numeric = field.isNumeric()
        
        print(f"  → Updating to use '{id_field}' (type: {field_type}, numeric: {is_numeric})")
        
        # Update database
        try:
            # Update primary_key_name
            cursor.execute("""
                UPDATE fm_project_layers_properties
                SET meta_value = ?
                WHERE fk_project = ?
                  AND layer_id = ?
                  AND meta_type = 'infos'
                  AND meta_key = 'primary_key_name'
            """, (id_field, project_uuid, layer_id))
            
            # Update primary_key_idx
            cursor.execute("""
                UPDATE fm_project_layers_properties
                SET meta_value = ?
                WHERE fk_project = ?
                  AND layer_id = ?
                  AND meta_type = 'infos'
                  AND meta_key = 'primary_key_idx'
            """, (str(id_field_idx), project_uuid, layer_id))
            
            # Update primary_key_type
            cursor.execute("""
                UPDATE fm_project_layers_properties
                SET meta_value = ?
                WHERE fk_project = ?
                  AND layer_id = ?
                  AND meta_type = 'infos'
                  AND meta_key = 'primary_key_type'
            """, (field_type, project_uuid, layer_id))
            
            # Update primary_key_is_numeric
            cursor.execute("""
                UPDATE fm_project_layers_properties
                SET meta_value = ?
                WHERE fk_project = ?
                  AND layer_id = ?
                  AND meta_type = 'infos'
                  AND meta_key = 'primary_key_is_numeric'
            """, (str(is_numeric).lower(), project_uuid, layer_id))
            
            conn.commit()
            
            # Update QGIS layer variables
            QgsExpressionContextUtils.setLayerVariable(layer, 'filterMate_infos_primary_key_name', id_field)
            QgsExpressionContextUtils.setLayerVariable(layer, 'filterMate_infos_primary_key_idx', id_field_idx)
            QgsExpressionContextUtils.setLayerVariable(layer, 'filterMate_infos_primary_key_type', field_type)
            QgsExpressionContextUtils.setLayerVariable(layer, 'filterMate_infos_primary_key_is_numeric', is_numeric)
            
            print(f"  ✓ Successfully updated to use '{id_field}'")
            fixed_count += 1
            
        except Exception as e:
            print(f"  ❌ Error updating: {e}")
            conn.rollback()
    
    conn.close()
    
    print("\n" + "="*80)
    print(f"SUMMARY: Fixed {fixed_count} layer(s)")
    print("="*80)
    print("\nIMPORTANT: Reload the FilterMate plugin for changes to take effect:")
    print("  Plugins → Recharger l'extension: filter_mate")
    print("="*80)

# Run the fix
fix_ctid_layers()
