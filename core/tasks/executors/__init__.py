"""
Filter execution specialized classes.

This package contains executor classes extracted from FilterEngineTask
as part of Phase E13 refactoring (January 2026).
"""

from .attribute_filter_executor import AttributeFilterExecutor  # noqa: F401
from .spatial_filter_executor import SpatialFilterExecutor  # noqa: F401

__all__ = ['AttributeFilterExecutor', 'SpatialFilterExecutor']
