# -*- coding: utf-8 -*-
"""
UI Managers Package

Specialized managers for UI configuration and state management.
Part of FilterMate v4.0 refactoring - Sprint 6.

Refactoring: Added DockwidgetSignalManager for signal management extraction.
Phase 3.1: Added RasterExploringManager for raster exploring page extraction.
"""

from .configuration_manager import ConfigurationManager
from .dockwidget_signal_manager import DockwidgetSignalManager, SignalStateChangeError
from .raster_exploring_manager import RasterExploringManager

__all__ = ['ConfigurationManager', 'DockwidgetSignalManager', 'SignalStateChangeError', 'RasterExploringManager']
