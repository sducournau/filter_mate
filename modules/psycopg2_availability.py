# -*- coding: utf-8 -*-
"""
PostgreSQL/psycopg2 Availability Shim for modules package.

Compatibility shim that re-exports psycopg2 availability from adapters.backends.
This module exists for backward compatibility with code that imports from modules.

Usage:
    from modules.psycopg2_availability import (
        psycopg2,
        PSYCOPG2_AVAILABLE,
        POSTGRESQL_AVAILABLE
    )
    
    if PSYCOPG2_AVAILABLE:
        conn = psycopg2.connect(...)

Author: FilterMate Team
Version: 3.1.0 (January 2026)
"""

# Re-export from canonical location
try:
    from adapters.backends.postgresql_availability import (
        psycopg2,
        PSYCOPG2_AVAILABLE,
        POSTGRESQL_AVAILABLE,
        get_psycopg2_version,
        check_psycopg2_for_feature,
    )
except ImportError:
    # Fallback if adapters not available
    import logging
    logger = logging.getLogger('FilterMate.Psycopg2Availability')
    
    POSTGRESQL_AVAILABLE = True  # QGIS native always available
    
    try:
        import psycopg2
        import psycopg2.pool
        import psycopg2.extras
        PSYCOPG2_AVAILABLE = True
    except ImportError:
        PSYCOPG2_AVAILABLE = False
        psycopg2 = None
        logger.info(
            "psycopg2 not found - PostgreSQL layers will use QGIS native API."
        )
    
    def get_psycopg2_version() -> str:
        """Get psycopg2 version string."""
        if PSYCOPG2_AVAILABLE and psycopg2:
            return psycopg2.__version__
        return 'not installed'
    
    def check_psycopg2_for_feature(feature_name: str) -> bool:
        """Check if psycopg2 is available for a specific feature."""
        return PSYCOPG2_AVAILABLE


__all__ = [
    'psycopg2',
    'PSYCOPG2_AVAILABLE',
    'POSTGRESQL_AVAILABLE',
    'get_psycopg2_version',
    'check_psycopg2_for_feature',
]
