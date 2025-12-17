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
    
    PostgreSQL column name behavior:
    - Unquoted identifiers are converted to lowercase during table creation
    - Quoted identifiers (e.g., "SUB_TYPE") preserve the original case
    - Most PostgreSQL tables use lowercase column names by convention
    
    Common issue: QGIS may show "SUB_TYPE" but PostgreSQL has "sub_type"
    
    Args:
        columns: dict of column_name -> data_type
        search_term: term to search for
        
    Returns:
        list: matching column names (exact case-insensitive matches first)
    """
    search_lower = search_term.lower()
    exact_matches = []
    partial_matches = []
    
    for col_name in columns.keys():
        col_lower = col_name.lower()
        # Exact case-insensitive match (most likely the correct column)
        if search_lower == col_lower:
            exact_matches.append(col_name)
        # Partial match
        elif search_lower in col_lower or col_lower in search_lower:
            partial_matches.append(col_name)
    
    # Return exact matches first, then partial matches
    return exact_matches + partial_matches


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
                
                # Find similar columns (case-insensitive match)
                similar = find_similar_columns(columns, col_name)
                if similar:
                    # Check if this is a case mismatch issue
                    exact_case_match = [c for c in similar if c.lower() == col_name.lower()]
                    if exact_case_match:
                        result['issues'].append(
                            f"⚠️ PostgreSQL Case Issue: The column exists as '{exact_case_match[0]}' (not '{col_name}')"
                        )
                        result['suggestions'].append(
                            f"Replace \"{col_name}\" with \"{exact_case_match[0]}\" in your filter expression"
                        )
                    else:
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


def fix_column_case(layer_name, dry_run=True):
    """
    Fix column name case issues in a layer's filter expression.
    
    PostgreSQL is case-sensitive for quoted identifiers. This function
    corrects column names in filter expressions to match the actual
    column names in the database.
    
    Args:
        layer_name: Name of the layer to fix
        dry_run: If True, only show what would be changed (default: True)
        
    Returns:
        str: The corrected filter expression, or None if no fixes needed
        
    Usage in QGIS Python Console:
        # Preview changes
        check_column_names.fix_column_case("structures")
        
        # Apply changes
        check_column_names.fix_column_case("structures", dry_run=False)
    """
    import re
    
    project = QgsProject.instance()
    layers = project.mapLayersByName(layer_name)
    
    if not layers:
        print(f"❌ Layer '{layer_name}' not found")
        return None
    
    layer = layers[0]
    
    if layer.providerType() != 'postgres':
        print(f"ℹ️ Layer '{layer_name}' is not a PostgreSQL layer (provider: {layer.providerType()})")
        print("   Column case issues are specific to PostgreSQL.")
        return None
    
    if not PSYCOPG2_AVAILABLE:
        print("❌ psycopg2 not available - cannot verify PostgreSQL column names")
        return None
    
    filter_str = layer.subsetString()
    if not filter_str:
        print(f"ℹ️ Layer '{layer_name}' has no filter")
        return None
    
    print(f"\n{'=' * 80}")
    print(f"FIXING COLUMN CASE: {layer_name}")
    print(f"{'=' * 80}")
    print(f"\nOriginal filter: {filter_str}")
    
    # Get actual PostgreSQL column names
    columns = get_postgresql_columns(layer)
    if not columns:
        print("❌ Could not retrieve table columns")
        return None
    
    # Create case-insensitive lookup map
    col_lower_map = {col.lower(): col for col in columns.keys()}
    
    # Find quoted column names in filter
    quoted_cols = re.findall(r'"([^"]+)"', filter_str)
    
    # Build replacement map
    replacements = {}
    for col_name in quoted_cols:
        if col_name not in columns:
            # Check for case-insensitive match
            col_lower = col_name.lower()
            if col_lower in col_lower_map:
                correct_name = col_lower_map[col_lower]
                replacements[col_name] = correct_name
    
    if not replacements:
        print("\n✓ No case issues found in filter expression")
        return filter_str
    
    print(f"\n⚠️ Found {len(replacements)} column name case issue(s):")
    for wrong, correct in replacements.items():
        print(f"   \"{wrong}\" → \"{correct}\"")
    
    # Apply replacements
    fixed_filter = filter_str
    for wrong, correct in replacements.items():
        fixed_filter = fixed_filter.replace(f'"{wrong}"', f'"{correct}"')
    
    print(f"\nCorrected filter: {fixed_filter}")
    
    if dry_run:
        print(f"\n📋 DRY RUN - No changes applied")
        print(f"   To apply changes, run: fix_column_case('{layer_name}', dry_run=False)")
    else:
        layer.setSubsetString(fixed_filter)
        print(f"\n✓ Filter updated successfully!")
        print(f"   Features now visible: {layer.featureCount()}")
    
    return fixed_filter


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
    print("")
    print("  # Diagnose all layer filters for issues")
    print("  check_column_names.diagnose_all_filters()")
    print("")
    print("  # List columns for a specific layer")
    print("  check_column_names.list_layer_columns('structures')")
    print("")
    print("  # Fix column case issues (preview)")
    print("  check_column_names.fix_column_case('structures')")
    print("")
    print("  # Fix column case issues (apply)")
    print("  check_column_names.fix_column_case('structures', dry_run=False)")
    print("")
    print("  # Clear layer filter")
    print("  check_column_names.clear_layer_filter('structures')")
