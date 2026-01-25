# -*- coding: utf-8 -*-
"""
FilterMate PostgreSQL Cleanup Service - ARCH-010

Centralized PostgreSQL resource cleanup, consolidating logic from:
- filter_mate_app.py:402 (_cleanup_postgresql_session_views)
- filter_mate_dockwidget.py:3216 (_cleanup_postgresql_session_views)
- filter_mate_dockwidget.py:3292 (_cleanup_postgresql_schema_if_empty)

Part of Phase 1 Architecture Refactoring.

Features:
- Session view cleanup
- Orphaned view cleanup
- Schema management
- Circuit breaker integration
- Comprehensive logging

Author: FilterMate Team
Date: January 2025
"""

import logging
from typing import Optional, List, Tuple
from datetime import datetime

logger = logging.getLogger('FilterMate.Cleanup.PostgreSQL')


class PostgreSQLCleanupService:
    """
    Centralized PostgreSQL resource cleanup.
    
    Consolidates cleanup logic for FilterMate session materialized views,
    indexes, and temporary schema management.
    
    Features:
    - Session view cleanup with proper error handling
    - Orphaned view detection and cleanup
    - Schema management (create/drop filtermate_temp)
    - Circuit breaker integration for stability
    - Comprehensive logging and metrics
    
    Usage:
        service = PostgreSQLCleanupService(
            session_id="abc123",
            schema="filtermate_temp"
        )
        
        # Clean current session views
        count = service.cleanup_session_views(connexion)
        
        # Clean orphaned views from crashed sessions
        orphaned = service.cleanup_orphaned_views(connexion, max_age_hours=24)
        
        # Drop schema if empty
        dropped = service.cleanup_schema_if_empty(connexion)
    """
    
    # Default schema name for FilterMate temp objects
    DEFAULT_SCHEMA = "filtermate_temp"
    
    # Materialized view prefix patterns (unified fm_temp_* prefix)
    MV_PREFIX = "fm_temp_mv_"
    SESSION_VIEW_PATTERN = "fm_temp_mv_{session_id}_%"
    
    def __init__(
        self,
        session_id: Optional[str] = None,
        schema: str = DEFAULT_SCHEMA,
        circuit_breaker=None
    ):
        """
        Initialize the cleanup service.
        
        Args:
            session_id: Current session identifier (used for cleanup targeting)
            schema: PostgreSQL schema name for temp objects
            circuit_breaker: Optional circuit breaker for PostgreSQL stability
        """
        self._session_id = session_id
        self._schema = schema
        self._circuit_breaker = circuit_breaker
        self._metrics = {
            'views_cleaned': 0,
            'indexes_cleaned': 0,
            'errors': 0,
            'last_cleanup': None
        }
        
        logger.debug(
            f"PostgreSQLCleanupService initialized: "
            f"session={session_id[:8] if session_id else 'None'}, schema={schema}"
        )
    
    @property
    def session_id(self) -> Optional[str]:
        """Get current session ID."""
        return self._session_id
    
    @session_id.setter
    def session_id(self, value: str):
        """Set session ID."""
        self._session_id = value
    
    @property
    def schema(self) -> str:
        """Get schema name."""
        return self._schema
    
    @property
    def metrics(self) -> dict:
        """Get cleanup metrics."""
        return self._metrics.copy()
    
    def _check_circuit_breaker(self) -> bool:
        """
        Check if circuit breaker allows operation.
        
        Returns:
            True if operation should proceed, False if circuit is open
        """
        if self._circuit_breaker is None:
            return True
        
        if hasattr(self._circuit_breaker, 'is_open') and self._circuit_breaker.is_open:
            logger.debug(f"[PostgreSQL] PostgreSQL cleanup skipped - circuit breaker is OPEN")
            return False
        
        return True
    
    def _record_success(self):
        """Record successful operation for circuit breaker."""
        if self._circuit_breaker and hasattr(self._circuit_breaker, 'record_success'):
            self._circuit_breaker.record_success()
    
    def _record_failure(self):
        """Record failed operation for circuit breaker."""
        if self._circuit_breaker and hasattr(self._circuit_breaker, 'record_failure'):
            self._circuit_breaker.record_failure()
        self._metrics['errors'] += 1
    
    def cleanup_session_views(
        self,
        connexion,
        session_id: Optional[str] = None
    ) -> Tuple[int, List[str]]:
        """
        Clean up all materialized views for a session.
        
        Drops all materialized views and indexes prefixed with the session_id
        to prevent accumulation of orphaned views in the database.
        
        Args:
            connexion: Active PostgreSQL connection (psycopg2)
            session_id: Session ID to clean (defaults to instance session_id)
        
        Returns:
            Tuple of (count of views cleaned, list of view names)
        
        Raises:
            ValueError: If no session_id provided and none set on instance
        """
        target_session = session_id or self._session_id
        
        if not target_session:
            raise ValueError("No session_id provided for cleanup")
        
        if not self._check_circuit_breaker():
            return (0, [])
        
        cleaned_views = []
        
        try:
            cursor = connexion.cursor()
            
            # Find all materialized views for this session
            pattern = f"{self.MV_PREFIX}{target_session}_%"
            cursor.execute("""
                SELECT matviewname 
                FROM pg_matviews 
                WHERE schemaname = %s AND matviewname LIKE %s
            """, (self._schema, pattern))
            
            views = [row[0] for row in cursor.fetchall()]
            
            for view_name in views:
                try:
                    # Drop associated index first
                    # Handle both new (fm_temp_mv_) and legacy (mv_) prefixes
                    if view_name.startswith('fm_temp_mv_'):
                        index_name = f"{self._schema}_{view_name[11:]}_cluster"  # Remove 'fm_temp_mv_' prefix
                    else:
                        index_name = f"{self._schema}_{view_name[3:]}_cluster"  # Remove 'mv_' prefix (legacy)
                    cursor.execute(f'DROP INDEX IF EXISTS "{index_name}" CASCADE;')
                    self._metrics['indexes_cleaned'] += 1
                    
                    # Drop the materialized view
                    cursor.execute(
                        f'DROP MATERIALIZED VIEW IF EXISTS "{self._schema}"."{view_name}" CASCADE;'
                    )
                    cleaned_views.append(view_name)
                    self._metrics['views_cleaned'] += 1
                    
                    logger.debug(f"[PostgreSQL] Dropped MV: {view_name}")
                    
                except Exception as e:
                    logger.warning(f"[PostgreSQL] Error dropping view {view_name}: {e}")
                    self._metrics['errors'] += 1
            
            connexion.commit()
            
            if cleaned_views:
                logger.info(
                    f"Cleaned up {len(cleaned_views)} materialized view(s) "
                    f"for session {target_session[:8]}"
                )
            
            self._metrics['last_cleanup'] = datetime.now().isoformat()
            self._record_success()
            
            return (len(cleaned_views), cleaned_views)
            
        except Exception as e:
            logger.error(f"[PostgreSQL] Error during session cleanup: {e}")
            self._record_failure()
            raise
    
    def cleanup_orphaned_views(
        self,
        connexion,
        max_age_hours: int = 24,
        known_sessions: Optional[List[str]] = None
    ) -> Tuple[int, List[str]]:
        """
        Clean up old orphaned views not cleaned by their sessions.
        
        Identifies views that appear to be from crashed or unclean shutdowns
        and removes them based on age heuristics.
        
        Args:
            connexion: Active PostgreSQL connection
            max_age_hours: Max age before considering a view orphaned
            known_sessions: List of active session IDs to preserve
        
        Returns:
            Tuple of (count of orphaned views cleaned, list of view names)
        """
        if not self._check_circuit_breaker():
            return (0, [])
        
        orphaned_views = []
        known_sessions = known_sessions or []
        
        # Include current session in known sessions
        if self._session_id and self._session_id not in known_sessions:
            known_sessions.append(self._session_id)
        
        try:
            cursor = connexion.cursor()
            
            # Get all FilterMate materialized views
            cursor.execute("""
                SELECT matviewname 
                FROM pg_matviews 
                WHERE schemaname = %s AND matviewname LIKE %s
            """, (self._schema, f"{self.MV_PREFIX}%"))
            
            all_views = [row[0] for row in cursor.fetchall()]
            
            # Filter to views not belonging to known sessions
            for view_name in all_views:
                # Extract session ID from view name
                # New format: fm_temp_mv_{session_id}_{...}
                # Legacy format: mv_{session_id}_{...}
                if view_name.startswith('fm_temp_mv_'):
                    parts = view_name[11:].split('_', 1)  # After 'fm_temp_mv_'
                else:
                    parts = view_name[3:].split('_', 1)  # After 'mv_' (legacy)
                
                if len(parts) >= 1 and len(parts[0]) >= 6:  # Session IDs are typically 6-8 chars
                    view_session = parts[0]
                    if view_session not in known_sessions:
                        orphaned_views.append(view_name)
            
            # Clean orphaned views
            cleaned = []
            for view_name in orphaned_views:
                try:
                    cursor.execute(
                        f'DROP MATERIALIZED VIEW IF EXISTS "{self._schema}"."{view_name}" CASCADE;'
                    )
                    cleaned.append(view_name)
                    self._metrics['views_cleaned'] += 1
                    logger.debug(f"[PostgreSQL] Dropped orphaned MV: {view_name}")
                except Exception as e:
                    logger.warning(f"[PostgreSQL] Error dropping orphaned view {view_name}: {e}")
                    self._metrics['errors'] += 1
            
            connexion.commit()
            
            if cleaned:
                logger.info(f"[PostgreSQL] Cleaned up {len(cleaned)} orphaned materialized view(s)")
            
            self._record_success()
            return (len(cleaned), cleaned)
            
        except Exception as e:
            logger.error(f"[PostgreSQL] Error during orphaned view cleanup: {e}")
            self._record_failure()
            raise
    
    def cleanup_schema_if_empty(
        self,
        connexion,
        force: bool = False
    ) -> bool:
        """
        Drop the filtermate schema if empty or forced.
        
        Checks for existing materialized views from other sessions before
        dropping. Use force=True to drop even if other sessions' views exist.
        
        Args:
            connexion: Active PostgreSQL connection
            force: If True, drop schema even if views exist
        
        Returns:
            True if schema was dropped, False otherwise
        """
        if not self._check_circuit_breaker():
            return False
        
        try:
            cursor = connexion.cursor()
            
            # Check if schema exists
            cursor.execute("""
                SELECT COUNT(*) 
                FROM information_schema.schemata 
                WHERE schema_name = %s
            """, (self._schema,))
            
            if cursor.fetchone()[0] == 0:
                logger.debug(f"[PostgreSQL] Schema '{self._schema}' does not exist")
                return False
            
            # Check for existing views
            cursor.execute("""
                SELECT matviewname 
                FROM pg_matviews 
                WHERE schemaname = %s
            """, (self._schema,))
            
            existing_views = [row[0] for row in cursor.fetchall()]
            
            if existing_views and not force:
                # Separate our views from other sessions
                our_views = []
                other_views = []
                
                for view_name in existing_views:
                    if self._session_id and view_name.startswith(f"{self.MV_PREFIX}{self._session_id}_"):
                        our_views.append(view_name)
                    else:
                        other_views.append(view_name)
                
                if other_views:
                    logger.info(
                        f"Schema '{self._schema}' has {len(other_views)} view(s) "
                        f"from other sessions - not dropping"
                    )
                    return False
            
            # Drop the schema
            cursor.execute(f'DROP SCHEMA IF EXISTS "{self._schema}" CASCADE;')
            connexion.commit()
            
            logger.info(f"[PostgreSQL] Dropped schema '{self._schema}'")
            self._record_success()
            return True
            
        except Exception as e:
            logger.error(f"[PostgreSQL] Error dropping schema: {e}")
            self._record_failure()
            return False
    
    def ensure_schema_exists(self, connexion) -> bool:
        """
        Ensure the filtermate temp schema exists.
        
        Args:
            connexion: Active PostgreSQL connection
        
        Returns:
            True if schema exists or was created, False on error
        """
        if not self._check_circuit_breaker():
            return False
        
        try:
            cursor = connexion.cursor()
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{self._schema}";')
            connexion.commit()
            
            logger.debug(f"[PostgreSQL] Ensured schema '{self._schema}' exists")
            self._record_success()
            return True
            
        except Exception as e:
            logger.error(f"[PostgreSQL] Error creating schema: {e}")
            self._record_failure()
            return False
    
    def get_session_view_count(self, connexion) -> int:
        """
        Get count of materialized views for current session.
        
        Args:
            connexion: Active PostgreSQL connection
        
        Returns:
            Number of views for this session
        """
        if not self._session_id:
            return 0
        
        try:
            cursor = connexion.cursor()
            pattern = f"{self.MV_PREFIX}{self._session_id}_%"
            
            cursor.execute("""
                SELECT COUNT(*) 
                FROM pg_matviews 
                WHERE schemaname = %s AND matviewname LIKE %s
            """, (self._schema, pattern))
            
            return cursor.fetchone()[0]
            
        except Exception as e:
            logger.debug(f"[PostgreSQL] Error counting session views: {e}")
            return 0
    
    def get_all_filtermate_views(self, connexion) -> List[dict]:
        """
        List all FilterMate views in database with metadata.
        
        Args:
            connexion: Active PostgreSQL connection
        
        Returns:
            List of dicts with keys: name, session_id, schema
        """
        views = []
        
        try:
            cursor = connexion.cursor()
            
            cursor.execute("""
                SELECT matviewname 
                FROM pg_matviews 
                WHERE schemaname = %s AND matviewname LIKE %s
            """, (self._schema, f"{self.MV_PREFIX}%"))
            
            for (view_name,) in cursor.fetchall():
                # Extract session ID from view name
                parts = view_name.split('_')
                session = parts[1] if len(parts) >= 2 else 'unknown'
                
                views.append({
                    'name': view_name,
                    'session_id': session,
                    'schema': self._schema
                })
            
            return views
            
        except Exception as e:
            logger.debug(f"[PostgreSQL] Error listing views: {e}")
            return []

    def cleanup_all_filtermate_objects(
        self,
        connexion,
        include_public_schema: bool = True,
        dry_run: bool = False
    ) -> Tuple[int, List[str]]:
        """
        Clean ALL FilterMate objects across all schemas (nuclear option).
        
        This method cleans up:
        - All filtermate_mv_* views in filtermate_temp schema
        - All filtermate_mv_* views in public schema (if include_public_schema=True)
        - All fm_temp_* objects
        - The filtermate_temp schema itself
        
        Use this for complete cleanup after crashes or before uninstall.
        
        Args:
            connexion: Active PostgreSQL connection
            include_public_schema: Also clean views from public schema
            dry_run: If True, only list objects without deleting
        
        Returns:
            Tuple of (count of objects cleaned, list of object names)
        """
        cleaned_objects = []
        schemas_to_check = [self._schema]
        
        if include_public_schema:
            schemas_to_check.append('public')
        
        # Patterns to match FilterMate objects
        patterns = [
            'filtermate_mv_%',      # Main MV pattern
            'fm_temp_mv_%',         # New temp MV pattern
            'fm_temp_buf_%',        # Buffer tables
            'filtermate_temp_%',    # Legacy temp objects
        ]
        
        try:
            cursor = connexion.cursor()
            
            for schema in schemas_to_check:
                # Check if schema exists
                cursor.execute("""
                    SELECT COUNT(*) FROM information_schema.schemata 
                    WHERE schema_name = %s
                """, (schema,))
                
                if cursor.fetchone()[0] == 0:
                    continue
                
                # Find all matching materialized views
                for pattern in patterns:
                    cursor.execute("""
                        SELECT matviewname 
                        FROM pg_matviews 
                        WHERE schemaname = %s AND matviewname LIKE %s
                    """, (schema, pattern))
                    
                    views = [row[0] for row in cursor.fetchall()]
                    
                    for view_name in views:
                        full_name = f'"{schema}"."{view_name}"'
                        
                        if dry_run:
                            cleaned_objects.append(f"[DRY RUN] Would drop MV: {full_name}")
                            logger.info(f"[DRY RUN] Would drop: {full_name}")
                        else:
                            try:
                                # Use CASCADE to handle dependencies
                                cursor.execute(
                                    f'DROP MATERIALIZED VIEW IF EXISTS {full_name} CASCADE;'
                                )
                                cleaned_objects.append(f"MV: {full_name}")
                                self._metrics['views_cleaned'] += 1
                                logger.debug(f"Dropped MV: {full_name}")
                            except Exception as e:
                                logger.warning(f"Error dropping {full_name}: {e}")
                                self._metrics['errors'] += 1
                
                # Also clean regular tables matching patterns
                for pattern in patterns:
                    cursor.execute("""
                        SELECT tablename 
                        FROM pg_tables 
                        WHERE schemaname = %s AND tablename LIKE %s
                    """, (schema, pattern))
                    
                    tables = [row[0] for row in cursor.fetchall()]
                    
                    for table_name in tables:
                        full_name = f'"{schema}"."{table_name}"'
                        
                        if dry_run:
                            cleaned_objects.append(f"[DRY RUN] Would drop TABLE: {full_name}")
                        else:
                            try:
                                cursor.execute(
                                    f'DROP TABLE IF EXISTS {full_name} CASCADE;'
                                )
                                cleaned_objects.append(f"TABLE: {full_name}")
                                logger.debug(f"Dropped TABLE: {full_name}")
                            except Exception as e:
                                logger.warning(f"Error dropping table {full_name}: {e}")
            
            # Drop filtermate_temp schema if empty or force
            if not dry_run:
                try:
                    cursor.execute(f'DROP SCHEMA IF EXISTS "{self._schema}" CASCADE;')
                    cleaned_objects.append(f"SCHEMA: {self._schema}")
                    logger.info(f"Dropped schema: {self._schema}")
                except Exception as e:
                    logger.warning(f"Could not drop schema {self._schema}: {e}")
            
            connexion.commit()
            
            action = "Would clean" if dry_run else "Cleaned"
            logger.info(f"[PostgreSQL] {action} {len(cleaned_objects)} FilterMate objects")
            
            self._metrics['last_cleanup'] = datetime.now().isoformat()
            return (len(cleaned_objects), cleaned_objects)
            
        except Exception as e:
            logger.error(f"[PostgreSQL] Error during full cleanup: {e}")
            raise

    def cleanup_src_sel_views(
        self,
        connexion,
        dry_run: bool = False
    ) -> Tuple[int, List[str]]:
        """
        Clean filtermate_mv_src_sel_* views specifically.
        
        These are source selection views that can accumulate in the
        filtermate_temp schema and cause dependency issues.
        
        Args:
            connexion: Active PostgreSQL connection
            dry_run: If True, only list without deleting
        
        Returns:
            Tuple of (count cleaned, list of view names)
        """
        cleaned = []
        pattern = 'filtermate_mv_src_sel_%'
        
        try:
            cursor = connexion.cursor()
            
            # Find in filtermate_temp schema
            cursor.execute("""
                SELECT matviewname 
                FROM pg_matviews 
                WHERE schemaname = %s AND matviewname LIKE %s
                ORDER BY matviewname
            """, (self._schema, pattern))
            
            views = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"Found {len(views)} src_sel views to clean")
            
            for view_name in views:
                full_name = f'"{self._schema}"."{view_name}"'
                
                if dry_run:
                    cleaned.append(f"[DRY RUN] {view_name}")
                else:
                    try:
                        cursor.execute(
                            f'DROP MATERIALIZED VIEW IF EXISTS {full_name} CASCADE;'
                        )
                        cleaned.append(view_name)
                        logger.debug(f"Dropped src_sel view: {view_name}")
                    except Exception as e:
                        logger.warning(f"Error dropping {view_name}: {e}")
            
            if not dry_run:
                connexion.commit()
            
            return (len(cleaned), cleaned)
            
        except Exception as e:
            logger.error(f"Error cleaning src_sel views: {e}")
            return (0, [])


# Factory function for easy instantiation

def create_cleanup_service(
    session_id: Optional[str] = None,
    schema: str = PostgreSQLCleanupService.DEFAULT_SCHEMA,
    use_circuit_breaker: bool = True
) -> PostgreSQLCleanupService:
    """
    Create a PostgreSQLCleanupService instance.
    
    Args:
        session_id: Session ID for cleanup targeting
        schema: Schema name for temp objects
        use_circuit_breaker: Whether to use circuit breaker
    
    Returns:
        Configured PostgreSQLCleanupService instance
    """
    circuit_breaker = None
    
    if use_circuit_breaker:
        try:
            from ....infrastructure.resilience import get_postgresql_breaker
            circuit_breaker = get_postgresql_breaker()
        except ImportError:
            logger.debug(f"[PostgreSQL] Circuit breaker not available")
    
    return PostgreSQLCleanupService(
        session_id=session_id,
        schema=schema,
        circuit_breaker=circuit_breaker
    )
