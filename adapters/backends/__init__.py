"""
FilterMate Backend Adapters.

Multi-backend support for different data providers.
Part of the Hexagonal Architecture refactoring.
"""

from .factory import BackendFactory, BackendSelector, create_backend_factory

__all__ = [
    'BackendFactory',
    'BackendSelector', 
    'create_backend_factory',
]
