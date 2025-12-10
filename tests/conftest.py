"""
Pytest configuration and fixtures for FilterMate tests.

This module provides common test fixtures and configuration
for the FilterMate plugin test suite.
"""
import pytest
import sys
from pathlib import Path

# Add plugin directory to Python path
plugin_dir = Path(__file__).parent.parent
sys.path.insert(0, str(plugin_dir))


@pytest.fixture
def plugin_dir_path():
    """Return the plugin directory path."""
    return str(plugin_dir)


@pytest.fixture
def mock_iface():
    """
    Mock QGIS iface object.
    
    Returns a mock object that simulates the QGIS interface
    for testing without a full QGIS environment.
    """
    from unittest.mock import Mock, MagicMock
    
    iface = Mock()
    iface.mainWindow.return_value = Mock()
    iface.addDockWidget = Mock()
    iface.removeDockWidget = Mock()
    iface.messageBar.return_value = Mock()
    iface.mapCanvas.return_value = Mock()
    iface.activeLayer.return_value = None
    iface.addToolBar = Mock()
    iface.pluginMenu.return_value = Mock()
    
    return iface


@pytest.fixture
def mock_qgs_project():
    """
    Mock QgsProject instance.
    
    Returns a mock QGIS project for testing.
    """
    from unittest.mock import Mock
    
    project = Mock()
    project.instance.return_value = project
    project.mapLayers.return_value = {}
    project.readPath.return_value = './'
    project.fileName.return_value = ''
    
    return project


@pytest.fixture
def sample_layer_metadata():
    """Return sample layer metadata for testing."""
    return {
        'id': 'test_layer_123',
        'name': 'Test Layer',
        'provider_type': 'spatialite',
        'feature_count': 100,
        'geometry_type': 'Point',
        'crs': 'EPSG:4326'
    }


@pytest.fixture
def sample_filter_params():
    """Return sample filter parameters for testing."""
    return {
        'layer_id': 'test_layer_123',
        'attribute_expression': 'population > 10000',
        'spatial_predicates': ['intersects'],
        'buffer_distance': 100.0,
        'buffer_unit': 'meters',
        'combine_operator': 'AND'
    }
