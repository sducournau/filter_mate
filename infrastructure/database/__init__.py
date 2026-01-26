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
    - Connection Pool: PostgreSQL connection pooling (v4.0.4)
"""

from .prepared_statements import (
    PreparedStatementManager,
    PostgreSQLPreparedStatements,
    SpatialitePreparedStatements,
    NullPreparedStatements,
    create_prepared_statements,
)

from .connection_pool import (
    # Main API
    get_pool_manager,
    get_pooled_connection_from_layer,
    release_pooled_connection,
    pooled_connection_from_layer,
    cleanup_pools,
    # Classes
    PostgreSQLConnectionPool,
    PostgreSQLPoolManager,
    PoolStats,
    # Legacy compatibility
    get_pool,
    register_pool,
    unregister_pool,
)

from .postgresql_support import (
    psycopg2,
    PSYCOPG2_AVAILABLE,
    POSTGRESQL_AVAILABLE,
)

from .style_filter_fixer import (
    apply_type_casting_to_expression,
    fix_rule_based_renderer_filters,
    fix_layer_style_filters,
    scan_layers_for_type_mismatches,
    fix_expression_for_postgresql,
)

__all__ = [
    # Prepared Statements
    'PreparedStatementManager',
    'PostgreSQLPreparedStatements',
    'SpatialitePreparedStatements',
    'NullPreparedStatements',
    'create_prepared_statements',
    # Connection Pool
    'get_pool_manager',
    'get_pooled_connection_from_layer',
    'release_pooled_connection',
    'pooled_connection_from_layer',
    'cleanup_pools',
    'PostgreSQLConnectionPool',
    'PostgreSQLPoolManager',
    'PoolStats',
    'get_pool',
    'register_pool',
    'unregister_pool',
    # PostgreSQL Support
    'psycopg2',
    'PSYCOPG2_AVAILABLE',
    'POSTGRESQL_AVAILABLE',
    # Style Filter Fixer (v4.8.3)
    'apply_type_casting_to_expression',
    'fix_rule_based_renderer_filters',
    'fix_layer_style_filters',
    'scan_layers_for_type_mismatches',
    'fix_expression_for_postgresql',
]
