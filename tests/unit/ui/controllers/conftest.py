"""
Pytest fixtures for controller tests.

Provides shared fixtures for testing UI controllers.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))


@pytest.fixture
def mock_dockwidget():
    """Create mock dockwidget with common properties."""
    dockwidget = Mock()
    dockwidget.plugin_dir = str(plugin_path)
    dockwidget.CONFIG_DATA = {}
    dockwidget.widgets_initialized = True
    dockwidget.config_changes_pending = False
    dockwidget.pending_config_changes = []
    
    # Mock config_view and model
    mock_model = Mock()
    mock_item = Mock()
    mock_item.data = Mock(return_value="test_key")
    mock_item.parent = Mock(return_value=None)
    mock_model.itemFromIndex = Mock(return_value=mock_item)
    
    mock_view = Mock()
    mock_view.model = mock_model
    mock_view.setModel = Mock()
    
    dockwidget.config_view = mock_view
    dockwidget.config_model = mock_model
    dockwidget.buttonBox = Mock()
    dockwidget.buttonBox.setEnabled = Mock()
    
    # Mock methods
    dockwidget.save_configuration_model = Mock()
    dockwidget.set_widget_icon = Mock()
    dockwidget.apply_dynamic_dimensions = Mock()
    dockwidget.dockWidgetContents = Mock()
    
    return dockwidget


@pytest.fixture
def mock_filter_service():
    """Create mock filter service."""
    service = Mock()
    return service


@pytest.fixture
def mock_signal_manager():
    """Create mock signal manager."""
    manager = Mock()
    manager.connect = Mock(return_value="conn_id_1")
    manager.disconnect = Mock(return_value=True)
    return manager
