"""
FilterMate PostgreSQL Backend Adapter.

PostgreSQL/PostGIS specific implementations including:
- Materialized view management
- Session cleanup
- Spatial query optimization
"""
from .cleanup import PostgreSQLCleanupService, create_cleanup_service

__all__ = [
    'PostgreSQLCleanupService',
    'create_cleanup_service',
]
