"""
FilterMate Utilities Package.

Common utilities shared across the plugin.
"""

from .deprecation import (
    deprecated,
    deprecated_property,
    deprecated_class,
    DeprecationRegistry,
)

__all__ = [
    'deprecated',
    'deprecated_property',
    'deprecated_class',
    'DeprecationRegistry',
]
