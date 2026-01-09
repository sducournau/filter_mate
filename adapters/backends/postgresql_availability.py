# -*- coding: utf-8 -*-
"""
PostgreSQL/psycopg2 Availability Module

Centralized module for psycopg2 import and availability checking.
All modules needing psycopg2 should import from here to avoid duplication.

Usage:
    from adapters.backends.postgresql_availability import (
        psycopg2,
        PSYCOPG2_AVAILABLE,
        POSTGRESQL_AVAILABLE
    )
    
    if PSYCOPG2_AVAILABLE:
        conn = psycopg2.connect(...)

Note:
    - POSTGRESQL_AVAILABLE is always True (QGIS native PostgreSQL support)
    - PSYCOPG2_AVAILABLE depends on psycopg2 installation (for advanced features)

Author: FilterMate Team
Version: 3.1.0 (January 2026)
"""

import logging

logger = logging.getLogger('FilterMate.PostgresqlAvailability')

# QGIS PostgreSQL backend always available via native provider
POSTGRESQL_AVAILABLE = True

# Import conditionnel de psycopg2 pour fonctionnalités avancées PostgreSQL
try:
    import psycopg2
    import psycopg2.pool
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
    logger.debug("psycopg2 is available - advanced PostgreSQL features enabled")
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None
    logger.info(
        "psycopg2 not found - PostgreSQL layers will use QGIS native API. "
        "Advanced features (materialized views, connection pooling) disabled."
    )


def get_psycopg2_version() -> str:
    """Get psycopg2 version string."""
    if PSYCOPG2_AVAILABLE and psycopg2:
        return psycopg2.__version__
    return 'not installed'


def check_psycopg2_for_feature(feature_name: str) -> bool:
    """Check if psycopg2 is available for a specific feature."""
    if not PSYCOPG2_AVAILABLE:
        logger.debug(f"Feature '{feature_name}' requires psycopg2 which is not available")
        return False
    return True


__all__ = [
    'psycopg2',
    'PSYCOPG2_AVAILABLE',
    'POSTGRESQL_AVAILABLE',
    'get_psycopg2_version',
    'check_psycopg2_for_feature',
]
