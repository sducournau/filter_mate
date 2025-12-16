#!/usr/bin/env python3
"""
Script to analyze and fix PostgreSQL statistics issues.

This script:
1. Checks for missing statistics on geometry columns
2. Generates ANALYZE commands to update statistics
3. Validates column names in filters

Usage in QGIS Python Console:
    from filter_mate.tools.diagnostic import fix_postgresql_stats
    fix_postgresql_stats.analyze_missing_stats()
    fix_postgresql_stats.fix_all_stats()
"""

from qgis.core import QgsProject, QgsDataSourceUri
from qgis.utils import iface

try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    print("⚠️  psycopg2 not available - PostgreSQL operations disabled")


def get_postgresql_connection(layer):
    """
    Get PostgreSQL connection from layer.
    
    Args:
        layer: QgsVectorLayer with PostgreSQL provider
        
    Returns:
        psycopg2 connection or None
    """
    if not PSYCOPG2_AVAILABLE:
        return None
        
    if layer.providerType() != 'postgres':
        return None
    
    try:
        uri = QgsDataSourceUri(layer.source())
        
        conn_params = {
            'host': uri.host(),
            'port': int(uri.port()) if uri.port() else 5432,
            'database': uri.database(),
            'user': uri.username(),
            'password': uri.password()
        }
        
        # Remove None values
        conn_params = {k: v for k, v in conn_params.items() if v}
        
        return psycopg2.connect(**conn_params)
    except Exception as e:
        print(f"❌ Error connecting to PostgreSQL: {e}")
        return None


def analyze_missing_stats():
    """
    Analyze all PostgreSQL layers and report missing statistics.
    """
    if not PSYCOPG2_AVAILABLE:
        print("❌ psycopg2 not available")
        return
    
    print("\n" + "=" * 80)
    print("ANALYZING POSTGRESQL STATISTICS")
    print("=" * 80)
    
    project = QgsProject.instance()
    layers = [l for l in project.mapLayers().values() if l.providerType() == 'postgres']
    
    if not layers:
        print("ℹ️  No PostgreSQL layers found in project")
        return
    
    missing_stats = []
    
    for layer in layers:
        uri = QgsDataSourceUri(layer.source())
        schema = uri.schema()
        table = uri.table()
        geom_column = uri.geometryColumn() or 'geom'
        
        print(f"\nLayer: {layer.name()}")
        print(f"  Schema: {schema}")
        print(f"  Table: {table}")
        print(f"  Geometry column: {geom_column}")
        
        conn = get_postgresql_connection(layer)
        if not conn:
            print(f"  ❌ Could not connect")
            continue
        
        try:
            cursor = conn.cursor()
            
            # Check if statistics exist
            cursor.execute("""
                SELECT 
                    schemaname,
                    tablename,
                    attname,
                    n_distinct,
                    most_common_vals IS NOT NULL as has_mcv,
                    histogram_bounds IS NOT NULL as has_histogram
                FROM pg_stats
                WHERE schemaname = %s 
                  AND tablename = %s 
                  AND attname = %s
            """, (schema, table, geom_column))
            
            result = cursor.fetchone()
            
            if result:
                print(f"  ✓ Statistics exist")
                print(f"    n_distinct: {result[3]}")
                print(f"    has_mcv: {result[4]}")
                print(f"    has_histogram: {result[5]}")
            else:
                print(f"  ⚠️  NO STATISTICS FOUND")
                missing_stats.append({
                    'layer': layer.name(),
                    'schema': schema,
                    'table': table,
                    'geom_column': geom_column
                })
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"  ❌ Error checking stats: {e}")
            if conn:
                conn.close()
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total PostgreSQL layers: {len(layers)}")
    print(f"Layers with missing stats: {len(missing_stats)}")
    
    if missing_stats:
        print("\n⚠️  The following layers need statistics update:")
        for item in missing_stats:
            print(f"  - {item['layer']} ({item['schema']}.{item['table']}.{item['geom_column']})")
        print("\nRun fix_all_stats() to update statistics.")
    else:
        print("\n✓ All layers have statistics")
    
    return missing_stats


def fix_all_stats():
    """
    Update statistics for all PostgreSQL layers with missing stats.
    """
    if not PSYCOPG2_AVAILABLE:
        print("❌ psycopg2 not available")
        return
    
    missing = analyze_missing_stats()
    
    if not missing:
        print("\n✓ No statistics updates needed")
        return
    
    print("\n" + "=" * 80)
    print("UPDATING POSTGRESQL STATISTICS")
    print("=" * 80)
    
    project = QgsProject.instance()
    
    for item in missing:
        layer_name = item['layer']
        schema = item['schema']
        table = item['table']
        
        print(f"\nUpdating: {layer_name}")
        
        # Find layer
        layers = [l for l in project.mapLayersByName(layer_name) if l.providerType() == 'postgres']
        if not layers:
            print(f"  ❌ Layer not found")
            continue
        
        layer = layers[0]
        conn = get_postgresql_connection(layer)
        
        if not conn:
            print(f"  ❌ Could not connect")
            continue
        
        try:
            cursor = conn.cursor()
            
            # Run ANALYZE on the table
            analyze_sql = f'ANALYZE VERBOSE "{schema}"."{table}"'
            print(f"  Executing: {analyze_sql}")
            
            cursor.execute(analyze_sql)
            conn.commit()
            
            print(f"  ✓ Statistics updated successfully")
            
            cursor.close()
            conn.close()
            
        except Exception as e:
            print(f"  ❌ Error updating stats: {e}")
            if conn:
                conn.rollback()
                conn.close()
    
    print("\n" + "=" * 80)
    print("✓ Statistics update completed")
    print("=" * 80)


def check_column_exists(layer, column_name):
    """
    Check if a column exists in a PostgreSQL layer.
    
    Args:
        layer: QgsVectorLayer
        column_name: Name of column to check
        
    Returns:
        bool: True if column exists
    """
    if not PSYCOPG2_AVAILABLE:
        return False
    
    if layer.providerType() != 'postgres':
        return False
    
    conn = get_postgresql_connection(layer)
    if not conn:
        return False
    
    try:
        uri = QgsDataSourceUri(layer.source())
        schema = uri.schema()
        table = uri.table()
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s 
              AND table_name = %s 
              AND column_name = %s
        """, (schema, table, column_name))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        return result is not None
        
    except Exception as e:
        print(f"Error checking column: {e}")
        if conn:
            conn.close()
        return False


def list_all_columns(layer):
    """
    List all columns in a PostgreSQL layer.
    
    Args:
        layer: QgsVectorLayer
        
    Returns:
        list: List of (column_name, data_type) tuples
    """
    if not PSYCOPG2_AVAILABLE:
        print("❌ psycopg2 not available")
        return []
    
    if layer.providerType() != 'postgres':
        print("❌ Layer is not PostgreSQL")
        return []
    
    conn = get_postgresql_connection(layer)
    if not conn:
        print("❌ Could not connect to PostgreSQL")
        return []
    
    try:
        uri = QgsDataSourceUri(layer.source())
        schema = uri.schema()
        table = uri.table()
        
        cursor = conn.cursor()
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = %s 
              AND table_name = %s
            ORDER BY ordinal_position
        """, (schema, table))
        
        columns = cursor.fetchall()
        
        print(f"\n{'=' * 80}")
        print(f"Columns in {layer.name()} ({schema}.{table})")
        print(f"{'=' * 80}")
        
        for col_name, data_type, nullable in columns:
            null_str = "NULL" if nullable == 'YES' else "NOT NULL"
            print(f"  {col_name:30s} {data_type:20s} {null_str}")
        
        print(f"{'=' * 80}")
        print(f"Total columns: {len(columns)}")
        
        cursor.close()
        conn.close()
        
        return columns
        
    except Exception as e:
        print(f"❌ Error listing columns: {e}")
        if conn:
            conn.close()
        return []


if __name__ == "__main__":
    print("Run this script in QGIS Python Console:")
    print("  from filter_mate.tools.diagnostic import fix_postgresql_stats")
    print("  fix_postgresql_stats.analyze_missing_stats()")
    print("  fix_postgresql_stats.fix_all_stats()")
