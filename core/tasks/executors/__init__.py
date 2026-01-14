"""
Filter execution specialized classes.

This package contains executor classes extracted from FilterEngineTask
as part of Phase E13 refactoring (January 2026).
"""

from .attribute_filter_executor import AttributeFilterExecutor
from .spatial_filter_executor import SpatialFilterExecutor

__all__ = ['AttributeFilterExecutor', 'SpatialFilterExecutor']
