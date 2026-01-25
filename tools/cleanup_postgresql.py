# -*- coding: utf-8 -*-
"""
FilterMate PostgreSQL Cleanup Utility

This script provides manual cleanup functions for FilterMate PostgreSQL objects.
Run from QGIS Python Console or as a standalone script.

Usage in QGIS Python Console:
    from filter_mate.tools.cleanup_postgresql import cleanup_all, list_orphaned_views
    
    # List all FilterMate objects (dry run)
    list_orphaned_views()
    
    # Clean all FilterMate objects
    cleanup_all()

Author: FilterMate Team
Date: January 2026
"""

import logging
from typing import Optional, List, Tuple

logger = logging.getLogger('FilterMate.Tools.Cleanup')


def _get_filter_mate_module():
    """Get the filter_mate module dynamically."""
    try:
        import filter_mate
        return filter_mate
    except ImportError:
        return None


def get_postgresql_connection(layer=None):
    """
    Get a PostgreSQL connection from a layer or active project.
    
    Args:
        layer: Optional QgsVectorLayer to get connection from
        
    Returns:
        psycopg2 connection or None
    """
    try:
        # Try absolute import first (when used from QGIS console)
        try:
            from filter_mate.adapters.backends.postgresql_availability import (
                POSTGRESQL_AVAILABLE
            )
        except ImportError:
            from adapters.backends.postgresql_availability import POSTGRESQL_AVAILABLE
        
        if not POSTGRESQL_AVAILABLE:
            print("❌ PostgreSQL (psycopg2) not available")
            return None
        
        import psycopg2
        
        # Try to get from provided layer
        if layer is not None:
            try:
                from filter_mate.infrastructure.utils import (
                    get_datasource_connexion_from_layer
                )
            except ImportError:
                from infrastructure.utils import get_datasource_connexion_from_layer
            
            conn, uri = get_datasource_connexion_from_layer(layer)
            if conn:
                return conn
        
        # Try to find a PostgreSQL layer in project
        from qgis.core import QgsProject
        project = QgsProject.instance()
        
        for lyr in project.mapLayers().values():
            if hasattr(lyr, 'providerType') and lyr.providerType() == 'postgres':
                try:
                    from filter_mate.infrastructure.utils import (
                        get_datasource_connexion_from_layer
                    )
                except ImportError:
                    from infrastructure.utils import get_datasource_connexion_from_layer
                
                conn, uri = get_datasource_connexion_from_layer(lyr)
                if conn:
                    print(f"✓ Connected via layer: {lyr.name()}")
                    return conn
        
        print("❌ No PostgreSQL layer found in project")
        return None
        
    except Exception as e:
        print(f"❌ Connection error: {e}")
        return None


def list_orphaned_views(connection=None) -> List[dict]:
    """
    List all FilterMate objects in the database.
    
    Args:
        connection: Optional psycopg2 connection
        
    Returns:
        List of view info dicts
    """
    conn = connection or get_postgresql_connection()
    if not conn:
        return []
    
    views = []
    
    try:
        cursor = conn.cursor()
        
        # Patterns to search
        patterns = [
            ('filtermate_temp', 'filtermate_mv_%'),
            ('filtermate_temp', 'fm_temp_%'),
            ('public', 'filtermate_mv_%'),
            ('public', 'fm_temp_%'),
        ]
        
        print("\n📋 FilterMate Objects in Database:")
        print("=" * 60)
        
        total = 0
        for schema, pattern in patterns:
            # Check materialized views
            cursor.execute("""
                SELECT schemaname, matviewname 
                FROM pg_matviews 
                WHERE schemaname = %s AND matviewname LIKE %s
                ORDER BY matviewname
            """, (schema, pattern))
            
            results = cursor.fetchall()
            
            if results:
                print(f"\n📁 {schema} schema - Materialized Views ({len(results)}):")
                for schema_name, view_name in results:
                    print(f"   • {view_name}")
                    views.append({
                        'type': 'MATERIALIZED VIEW',
                        'schema': schema_name,
                        'name': view_name
                    })
                    total += 1
            
            # Check tables
            cursor.execute("""
                SELECT schemaname, tablename 
                FROM pg_tables 
                WHERE schemaname = %s AND tablename LIKE %s
                ORDER BY tablename
            """, (schema, pattern))
            
            results = cursor.fetchall()
            
            if results:
                print(f"\n📁 {schema} schema - Tables ({len(results)}):")
                for schema_name, table_name in results:
                    print(f"   • {table_name}")
                    views.append({
                        'type': 'TABLE',
                        'schema': schema_name,
                        'name': table_name
                    })
                    total += 1
        
        # Check for filtermate_temp schema
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.schemata 
            WHERE schema_name = 'filtermate_temp'
        """)
        if cursor.fetchone()[0] > 0:
            views.append({
                'type': 'SCHEMA',
                'schema': 'filtermate_temp',
                'name': 'filtermate_temp'
            })
            print(f"\n📁 Schema 'filtermate_temp' exists")
        
        print("=" * 60)
        print(f"📊 Total FilterMate objects found: {total}")
        
        return views
        
    except Exception as e:
        print(f"❌ Error listing views: {e}")
        return []
    finally:
        if connection is None and conn:
            conn.close()


def cleanup_all(connection=None, dry_run: bool = False) -> Tuple[int, List[str]]:
    """
    Clean ALL FilterMate objects from the database.
    
    Args:
        connection: Optional psycopg2 connection
        dry_run: If True, only show what would be deleted
        
    Returns:
        Tuple of (count cleaned, list of object names)
    """
    conn = connection or get_postgresql_connection()
    if not conn:
        return (0, [])
    
    cleaned = []
    
    try:
        # Try absolute import first
        try:
            from filter_mate.adapters.backends.postgresql.cleanup import (
                PostgreSQLCleanupService
            )
        except ImportError:
            from adapters.backends.postgresql.cleanup import PostgreSQLCleanupService
        
        service = PostgreSQLCleanupService(schema='filtermate_temp')
        
        if dry_run:
            print("\n🔍 DRY RUN - No objects will be deleted")
        else:
            print("\n🧹 Cleaning FilterMate objects...")
        
        count, objects = service.cleanup_all_filtermate_objects(
            conn,
            include_public_schema=True,
            dry_run=dry_run
        )
        
        print("=" * 60)
        for obj in objects:
            print(f"   {'🔍' if dry_run else '✓'} {obj}")
        
        print("=" * 60)
        action = "Would clean" if dry_run else "Cleaned"
        print(f"📊 {action}: {count} objects")
        
        return (count, objects)
        
    except Exception as e:
        print(f"❌ Cleanup error: {e}")
        return (0, [])
    finally:
        if connection is None and conn:
            conn.close()


def cleanup_src_sel_views(connection=None, dry_run: bool = False) -> Tuple[int, List[str]]:
    """
    Clean only filtermate_mv_src_sel_* views (source selection caches).
    
    These accumulate quickly and cause the dependency errors seen in logs.
    
    Args:
        connection: Optional psycopg2 connection
        dry_run: If True, only show what would be deleted
        
    Returns:
        Tuple of (count cleaned, list of view names)
    """
    conn = connection or get_postgresql_connection()
    if not conn:
        return (0, [])
    
    try:
        # Try absolute import first
        try:
            from filter_mate.adapters.backends.postgresql.cleanup import (
                PostgreSQLCleanupService
            )
        except ImportError:
            from adapters.backends.postgresql.cleanup import PostgreSQLCleanupService
        
        service = PostgreSQLCleanupService(schema='filtermate_temp')
        
        if dry_run:
            print("\n🔍 DRY RUN - src_sel views")
        else:
            print("\n🧹 Cleaning src_sel views...")
        
        count, views = service.cleanup_src_sel_views(conn, dry_run=dry_run)
        
        print("=" * 60)
        for view in views:
            print(f"   {'🔍' if dry_run else '✓'} {view}")
        
        print("=" * 60)
        action = "Would clean" if dry_run else "Cleaned"
        print(f"📊 {action}: {count} src_sel views")
        
        return (count, views)
        
    except Exception as e:
        print(f"❌ Cleanup error: {e}")
        return (0, [])
    finally:
        if connection is None and conn:
            conn.close()


def run_sql_cleanup(connection=None) -> bool:
    """
    Run direct SQL cleanup commands for stubborn objects.
    
    Use this when the normal cleanup fails due to dependencies.
    
    Args:
        connection: Optional psycopg2 connection
        
    Returns:
        True if successful
    """
    conn = connection or get_postgresql_connection()
    if not conn:
        return False
    
    cleanup_sql = """
    -- Drop all FilterMate materialized views in filtermate_temp
    DO $$
    DECLARE
        r RECORD;
    BEGIN
        FOR r IN (
            SELECT schemaname, matviewname 
            FROM pg_matviews 
            WHERE schemaname = 'filtermate_temp'
            OR (schemaname = 'public' AND matviewname LIKE 'filtermate_mv_%')
            OR (schemaname = 'public' AND matviewname LIKE 'fm_temp_%')
        )
        LOOP
            EXECUTE 'DROP MATERIALIZED VIEW IF EXISTS "' || r.schemaname || '"."' || r.matviewname || '" CASCADE';
            RAISE NOTICE 'Dropped: %.%', r.schemaname, r.matviewname;
        END LOOP;
    END $$;
    
    -- Drop all FilterMate tables
    DO $$
    DECLARE
        r RECORD;
    BEGIN
        FOR r IN (
            SELECT schemaname, tablename 
            FROM pg_tables 
            WHERE schemaname = 'filtermate_temp'
            OR (schemaname = 'public' AND tablename LIKE 'filtermate_%')
            OR (schemaname = 'public' AND tablename LIKE 'fm_temp_%')
        )
        LOOP
            EXECUTE 'DROP TABLE IF EXISTS "' || r.schemaname || '"."' || r.tablename || '" CASCADE';
            RAISE NOTICE 'Dropped table: %.%', r.schemaname, r.tablename;
        END LOOP;
    END $$;
    
    -- Drop the filtermate_temp schema
    DROP SCHEMA IF EXISTS filtermate_temp CASCADE;
    """
    
    try:
        print("\n🔧 Running SQL cleanup...")
        cursor = conn.cursor()
        cursor.execute(cleanup_sql)
        conn.commit()
        print("✓ SQL cleanup completed successfully")
        return True
        
    except Exception as e:
        print(f"❌ SQL cleanup error: {e}")
        conn.rollback()
        return False
    finally:
        if connection is None and conn:
            conn.close()


# Quick access functions for QGIS Python Console
def quick_list():
    """Quick list of FilterMate objects."""
    return list_orphaned_views()


def quick_clean():
    """Quick cleanup (with confirmation)."""
    print("\n⚠️  This will delete ALL FilterMate temporary objects!")
    print("    Run cleanup_all(dry_run=True) first to see what will be deleted.")
    response = input("    Type 'YES' to proceed: ")
    if response.strip() == 'YES':
        return cleanup_all()
    else:
        print("    Cancelled.")
        return (0, [])


if __name__ == '__main__':
    print("""
╔══════════════════════════════════════════════════════════════╗
║           FilterMate PostgreSQL Cleanup Utility              ║
╠══════════════════════════════════════════════════════════════╣
║  Usage in QGIS Python Console:                               ║
║                                                              ║
║  from filter_mate.tools.cleanup_postgresql import *          ║
║                                                              ║
║  list_orphaned_views()      # List all FilterMate objects    ║
║  cleanup_all(dry_run=True)  # Preview cleanup                ║
║  cleanup_all()              # Clean all objects              ║
║  cleanup_src_sel_views()    # Clean only src_sel views       ║
║  run_sql_cleanup()          # Direct SQL cleanup             ║
╚══════════════════════════════════════════════════════════════╝
    """)
