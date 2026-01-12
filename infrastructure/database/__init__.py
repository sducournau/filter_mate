# -*- coding: utf-8 -*-
"""
Infrastructure Database Package

Database utilities and connection management for FilterMate.

Exports:
    - create_prepared_statements: Factory for prepared statement managers
    - PreparedStatementManager: Base class for prepared statements
    - PostgreSQLPreparedStatements: PostgreSQL implementation
    - SpatialitePreparedStatements: Spatialite implementation
    - NullPreparedStatements: Null object pattern implementation
"""

from .prepared_statements import (
    PreparedStatementManager,
    PostgreSQLPreparedStatements,
    SpatialitePreparedStatements,
    NullPreparedStatements,
    create_prepared_statements,
)

__all__ = [
    'PreparedStatementManager',
    'PostgreSQLPreparedStatements',
    'SpatialitePreparedStatements',
    'NullPreparedStatements',
    'create_prepared_statements',
]
