# -*- coding: utf-8 -*-
"""
UI Managers Package

Specialized managers for UI configuration and state management.
Part of FilterMate v4.0 refactoring - Sprint 6.

v5.0 Phase 2: Added DockwidgetSignalManager for signal management extraction.
"""

from .configuration_manager import ConfigurationManager
from .dockwidget_signal_manager import DockwidgetSignalManager, SignalStateChangeError

__all__ = ['ConfigurationManager', 'DockwidgetSignalManager', 'SignalStateChangeError']
