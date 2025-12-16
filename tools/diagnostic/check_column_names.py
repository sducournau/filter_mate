#!/usr/bin/env python3
"""
Script to diagnose column name issues in filters.

This script helps identify:
1. Invalid column names in QGIS layer filters
2. Saved filter expressions with wrong column names
3. Correct column names in PostgreSQL tables

Usage in QGIS Python Console:
    from filter_mate.tools.diagnostic import check_column_names
    check_column_names.diagnose_all_filters()
    check_column_names.fix_layer_filter("Distribution Cluster")
"""

import os
import sqlite3
from qgis.core import QgsProject, QgsDataSourceUri
from qgis.utils import iface

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("⚠️  psycopg2 not available - PostgreSQL operations disabled")


def get_postgresql_columns(layer):
    """
    Get all column names from a PostgreSQL layer.
    
    Returns:
        dict: {column_name: data_type}
    """
    if not PSYCOPG2_AVAILABLE or layer.providerType() != 'postgres':
        return {}
    
    try:
        uri = QgsDataSourceUri(layer.source())
        conn = psycopg2.connect(
            host=uri.host(),
            port=int(uri.port()) if uri.port() else 5432,
            database=uri.database(),
            user=uri.username(),
            password=uri.password()
        )
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (uri.schema(), uri.table()))
        
        columns = {row[0]: row[1] for row in cursor.fetchall()}
        cursor.close()
        conn.close()
        
        return columns
        
    except Exception as e:
        print(f"❌ Error getting PostgreSQL columns: {e}")
        return {}


def find_similar_columns(columns, search_term):
    """
    Find columns with similar names (case-insensitive).
    
    Args:
        columns: dict of column_name -> data_type
        search_term: term to search for
        
    Returns:
        list: matching column names
    """
    search_lower = search_term.lower()
    matches = []
    
    for col_name in columns.keys():
        col_lower = col_name.lower()
        if search_lower in col_lower or col_lower in search_lower:
            matches.append(col_name)
    
    return matches


def diagnose_layer_filter(layer):
    """
    Diagnose filter issues for a single layer.
    
    Args:
        layer: QgsVectorLayer
        
    Returns:
        dict: diagnosis results
    """
    result = {
        'layer_name': layer.name(),
        'provider': layer.providerType(),
        'has_filter': False,
        'filter_string': '',
        'issues': [],
        'suggestions': []
    }
    
    # Check if layer has filter
    filter_str = layer.subsetString()
    if not filter_str:
        return result
    
    result['has_filter'] = True
    result['filter_string'] = filter_str
    
    # For PostgreSQL layers, validate column names
    if layer.providerType() == 'postgres' and PSYCOPG2_AVAILABLE:
        columns = get_postgresql_columns(layer)
        
        if not columns:
            result['issues'].append("Could not retrieve table columns")
            return result
        
        # Extract quoted column names from filter (simple regex)
        import re
        quoted_cols = re.findall(r'"([^"]+)"', filter_str)
        
        for col_name in quoted_cols:
            if col_name not in columns:
                result['issues'].append(f"Column '{col_name}' does not exist in table")
                
                # Find similar columns
                similar = find_similar_columns(columns, col_name)
                if similar:
                    result['suggestions'].append(
                        f"Did you mean: {', '.join(similar)}?"
                    )
    
    return result


def diagnose_all_filters():
    """
    Diagnose filter issues for all layers in the project.
    """
    print("\n" + "=" * 80)
    print("DIAGNOSING LAYER FILTERS")
    print("=" * 80)
    
    project = QgsProject.instance()
    layers = list(project.mapLayers().values())
    
    issues_found = []
    
    for layer in layers:
        if not hasattr(layer, 'subsetString'):
            continue
        
        diagnosis = diagnose_layer_filter(layer)
        
        if not diagnosis['has_filter']:
            continue
        
        print(f"\n📋 Layer: {diagnosis['layer_name']}")
        print(f"   Provider: {diagnosis['provider']}")
        print(f"   Filter: {diagnosis['filter_string']}")
        
        if diagnosis['issues']:
            print(f"   ⚠️  ISSUES:")
            for issue in diagnosis['issues']:
                print(f"      - {issue}")
            
            if diagnosis['suggestions']:
                print(f"   💡 SUGGESTIONS:")
                for suggestion in diagnosis['suggestions']:
                    print(f"      - {suggestion}")
            
            issues_found.append(diagnosis)
        else:
            print(f"   ✓ No issues detected")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total layers checked: {len([l for l in layers if hasattr(l, 'subsetString')])}")
    print(f"Layers with filters: {len([d for d in [diagnose_layer_filter(l) for l in layers if hasattr(l, 'subsetString')] if d['has_filter']])}")
    print(f"Layers with issues: {len(issues_found)}")
    
    if issues_found:
        print("\n⚠️  Fix required! Run fix_layer_filter(layer_name) to correct filters.")
    else:
        print("\n✓ All filters are valid")
    
    return issues_found


def list_layer_columns(layer_name):
    """
    List all columns for a specific layer.
    
    Args:
        layer_name: Name of the layer
    """
    project = QgsProject.instance()
    layers = project.mapLayersByName(layer_name)
    
    if not layers:
        print(f"❌ Layer '{layer_name}' not found")
        return
    
    layer = layers[0]
    
    print(f"\n{'=' * 80}")
    print(f"COLUMNS IN: {layer_name}")
    print(f"Provider: {layer.providerType()}")
    print(f"{'=' * 80}")
    
    if layer.providerType() == 'postgres' and PSYCOPG2_AVAILABLE:
        columns = get_postgresql_columns(layer)
        
        if not columns:
            print("❌ Could not retrieve columns")
            return
        
        print(f"\n{'Column Name':<40} {'Data Type':<20}")
        print("-" * 60)
        
        for col_name, data_type in sorted(columns.items()):
            print(f"{col_name:<40} {data_type:<20}")
        
        print(f"\nTotal columns: {len(columns)}")
    else:
        # Use QGIS fields
        fields = layer.fields()
        
        print(f"\n{'Column Name':<40} {'Type':<20}")
        print("-" * 60)
        
        for field in fields:
            print(f"{field.name():<40} {field.typeName():<20}")
        
        print(f"\nTotal fields: {len(fields)}")


def clear_layer_filter(layer_name):
    """
    Clear the filter on a specific layer.
    
    Args:
        layer_name: Name of the layer
    """
    project = QgsProject.instance()
    layers = project.mapLayersByName(layer_name)
    
    if not layers:
        print(f"❌ Layer '{layer_name}' not found")
        return
    
    layer = layers[0]
    old_filter = layer.subsetString()
    
    if not old_filter:
        print(f"ℹ️  Layer '{layer_name}' has no filter")
        return
    
    print(f"\n📋 Clearing filter from: {layer_name}")
    print(f"   Old filter: {old_filter}")
    
    layer.setSubsetString("")
    
    print(f"   ✓ Filter cleared")
    print(f"   Features now visible: {layer.featureCount()}")


def check_filtermate_history():
    """
    Check FilterMate history database for problematic filters.
    """
    print("\n" + "=" * 80)
    print("CHECKING FILTERMATE HISTORY")
    print("=" * 80)
    
    # Find FilterMate data directory
    from pathlib import Path
    
    # Try common locations
    possible_paths = [
        Path.home() / ".local" / "share" / "QGIS" / "QGIS3" / "profiles" / "default" / "python" / "plugins" / "filter_mate" / "data",
        Path.home() / "AppData" / "Roaming" / "QGIS" / "QGIS3" / "profiles" / "default" / "python" / "plugins" / "filter_mate" / "data",
    ]
    
    # Also try project directory
    project = QgsProject.instance()
    if project.fileName():
        project_dir = Path(project.fileName()).parent
        possible_paths.append(project_dir / ".filtermate" / "data")
    
    db_path = None
    for path in possible_paths:
        if path.exists():
            db_file = path / "fm_subset_history.db"
            if db_file.exists():
                db_path = db_file
                break
    
    if not db_path:
        print("ℹ️  FilterMate history database not found")
        return
    
    print(f"Found database: {db_path}")
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check for SUB_TYPE in saved filters
        cursor.execute("""
            SELECT layer_id, subset_string, timestamp
            FROM fm_subset_history
            WHERE subset_string LIKE '%SUB_TYPE%'
            ORDER BY timestamp DESC
        """)
        
        results = cursor.fetchall()
        
        if results:
            print(f"\n⚠️  Found {len(results)} filter(s) with 'SUB_TYPE':")
            for layer_id, subset_str, timestamp in results:
                print(f"\n   Layer ID: {layer_id}")
                print(f"   Timestamp: {timestamp}")
                print(f"   Filter: {subset_str}")
        else:
            print("\n✓ No filters with 'SUB_TYPE' found in history")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking history: {e}")


if __name__ == "__main__":
    print("Run this script in QGIS Python Console:")
    print("  from filter_mate.tools.diagnostic import check_column_names")
    print("  check_column_names.diagnose_all_filters()")
    print("  check_column_names.list_layer_columns('Distribution Cluster')")
    print("  check_column_names.clear_layer_filter('Distribution Cluster')")
