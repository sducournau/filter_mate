# -*- coding: utf-8 -*-
"""
PostgreSQL Support for FilterMate.

Provides centralized psycopg2 availability detection and PostgreSQL support.

This module provides backward compatibility for imports from
infrastructure.database.postgresql_support.

Author: FilterMate Team
Date: January 2026
"""

# Try to import psycopg2 availability from various locations
try:
    from ...adapters.backends.postgresql_availability import (
        psycopg2,
        PSYCOPG2_AVAILABLE,
        POSTGRESQL_AVAILABLE,
    )
except ImportError:
    try:
        from ..utils.layer_utils import (
            psycopg2,
            PSYCOPG2_AVAILABLE,
            POSTGRESQL_AVAILABLE,
        )
    except ImportError:
        # Final fallback - try direct import
        try:
            import psycopg2
            PSYCOPG2_AVAILABLE = True
        except ImportError:
            psycopg2 = None
            PSYCOPG2_AVAILABLE = False
        # QGIS native PostgreSQL provider is always available
        POSTGRESQL_AVAILABLE = True

__all__ = [
    'psycopg2',
    'PSYCOPG2_AVAILABLE',
    'POSTGRESQL_AVAILABLE',
]
