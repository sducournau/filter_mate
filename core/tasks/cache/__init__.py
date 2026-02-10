"""
Task-level cache utilities.

This package contains cache wrappers extracted from FilterEngineTask
as part of Phase E13 refactoring (January 2026).

These classes provide task-specific interfaces to the infrastructure cache layer.
"""

from .geometry_cache import GeometryCache  # noqa: F401
from .expression_cache import ExpressionCache  # noqa: F401

__all__ = ['GeometryCache', 'ExpressionCache']
