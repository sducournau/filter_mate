# -*- coding: utf-8 -*-
"""
FilterMate Modules Package

This package contains all core modules for FilterMate plugin:
- appUtils: Database connections and utility functions
- appTasks: Async task definitions (QgsTask)
- backends: Multi-backend system (PostgreSQL, Spatialite, OGR, Memory)
- tasks: Specialized task implementations
- widgets: Custom UI widgets
- config_*: Configuration management modules

v2.8.6: Package initialization for proper relative imports
"""

# This file is required for Python to recognize 'modules' as a package,
# enabling relative imports like 'from ..appUtils import ...'
