"""
Shared test fixtures and configuration for ui/styles tests.

This file extends the parent conftest.py in tests/unit/ui/.
QGIS mocks are configured there.
"""

import pytest
from unittest.mock import Mock, MagicMock
import sys
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))

# ============================================================================
# Styles-specific Fixtures
# ============================================================================

# Note: The main QGIS mocks are configured in tests/unit/ui/conftest.py
# This file only adds styles-specific fixtures if needed.


@pytest.fixture
def mock_dockwidget_dark():
    """Create mock dockwidget configured for dark theme."""
    dockwidget = Mock()
    dockwidget.plugin_dir = str(plugin_path)
    dockwidget.setStyleSheet = Mock()
    dockwidget.findChildren.return_value = []
    return dockwidget

