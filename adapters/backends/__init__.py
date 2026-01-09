"""
FilterMate Backend Adapters.

Multi-backend support for different data providers.
Part of the Hexagonal Architecture refactoring.
"""

from .factory import BackendFactory, BackendSelector, create_backend_factory

# Re-export POSTGRESQL_AVAILABLE for compatibility
try:
    from .postgresql_availability import POSTGRESQL_AVAILABLE
except ImportError:
    # Default to True (QGIS native PostgreSQL always available)
    POSTGRESQL_AVAILABLE = True

__all__ = [
    'BackendFactory',
    'BackendSelector', 
    'create_backend_factory',
    'POSTGRESQL_AVAILABLE',
]