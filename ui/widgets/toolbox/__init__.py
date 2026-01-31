# -*- coding: utf-8 -*-
"""
FilterMate - Dual QToolBox Architecture

This package contains the main QToolBox widgets for the unified UI:
- ExploringToolBox: Vector and Raster exploration (2 pages)
- ToolsetToolBox: Filtering, Exporting, Configuration (3 pages)
- Integration Bridge: Connects QToolBox with existing components
"""

from .exploring_toolbox import (
    ExploringToolBox,
    VectorExploringPage,
    RasterExploringPage
)
from .toolset_toolbox import (
    ToolsetToolBox,
    FilteringPage,
    ExportingPage,
    ConfigurationPage
)
from .base_toolbox import BaseToolBox
from .integration_bridge import (
    ToolBoxIntegrationBridge,
    DualToolBoxContainer
)

__all__ = [
    # Base
    'BaseToolBox',
    # EXPLORING QToolBox
    'ExploringToolBox',
    'VectorExploringPage',
    'RasterExploringPage',
    # TOOLSET QToolBox
    'ToolsetToolBox',
    'FilteringPage',
    'ExportingPage',
    'ConfigurationPage',
    # Integration
    'ToolBoxIntegrationBridge',
    'DualToolBoxContainer',
]
