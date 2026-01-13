# -*- coding: utf-8 -*-
"""
DEPRECATED: Legacy compatibility shim for modules/prepared_statements

This module has been migrated to infrastructure/database/prepared_statements.py
This shim provides backward compatibility for imports from modules.prepared_statements

Migration:
    OLD: from modules.prepared_statements import create_prepared_statements
    NEW: from infrastructure.database import create_prepared_statements

Date: January 2026
EPIC: EPIC-1 (Suppression du dossier modules/)
"""
import warnings

warnings.warn(
    "modules.prepared_statements is deprecated. Use infrastructure.database.prepared_statements instead. "
    "This shim will be removed in FilterMate v5.0.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new location
from ..infrastructure.database.prepared_statements import (
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
