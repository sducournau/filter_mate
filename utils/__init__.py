"""
FilterMate Utilities Package.

Common utilities shared across the plugin.
"""

from .deprecation import (  # noqa: F401
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
