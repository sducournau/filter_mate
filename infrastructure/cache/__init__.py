"""
FilterMate Infrastructure Cache.

Caching utilities for performance optimization.
"""

# Re-export legacy cache classes for backward compatibility
from ...infrastructure.cache import ExploringFeaturesCache

__all__ = [
    'ExploringFeaturesCache',
]
