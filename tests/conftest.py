"""
FilterMate Test Configuration

Pytest configuration and shared fixtures for FilterMate tests.
"""

import pytest
import sys
import os
from unittest.mock import Mock, MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock QGIS modules before any imports
sys.modules['qgis'] = MagicMock()
sys.modules['qgis.core'] = MagicMock()
sys.modules['qgis.gui'] = MagicMock()
sys.modules['qgis.PyQt'] = MagicMock()
sys.modules['qgis.PyQt.QtCore'] = MagicMock()
sys.modules['qgis.PyQt.QtGui'] = MagicMock()
sys.modules['qgis.PyQt.QtWidgets'] = MagicMock()
sys.modules['qgis.utils'] = MagicMock()
sys.modules['PyQt5'] = MagicMock()
sys.modules['PyQt5.QtCore'] = MagicMock()
sys.modules['PyQt5.QtGui'] = MagicMock()
sys.modules['PyQt5.QtWidgets'] = MagicMock()


@pytest.fixture
def mock_qgis_iface():
    """Mock QGIS interface"""
    iface = Mock()
    iface.messageBar.return_value = Mock()
    iface.activeLayer.return_value = None
    iface.mapCanvas.return_value = Mock()
    return iface


@pytest.fixture
def mock_qgis_project():
    """Mock QGIS project"""
    project = Mock()
    project.mapLayers.return_value = {}
    project.instance.return_value = project
    return project


@pytest.fixture
def sample_point_layer():
    """Create a sample point layer for testing"""
    layer = Mock()
    layer.name.return_value = "Test Points"
    layer.providerType.return_value = "memory"
    layer.featureCount.return_value = 50
    layer.geometryType.return_value = 0  # Point
    layer.isValid.return_value = True
    return layer


@pytest.fixture
def sample_pg_layer():
    """Create a mock PostgreSQL layer"""
    layer = Mock()
    layer.name.return_value = "PG Layer"
    layer.providerType.return_value = "postgres"
    layer.featureCount.return_value = 10000
    layer.isValid.return_value = True
    return layer


@pytest.fixture
def sample_spatialite_layer():
    """Create a mock Spatialite layer"""
    layer = Mock()
    layer.name.return_value = "Spatialite Layer"
    layer.providerType.return_value = "spatialite"
    layer.featureCount.return_value = 5000
    layer.isValid.return_value = True
    return layer


@pytest.fixture
def sample_shapefile_layer():
    """Create a mock Shapefile layer"""
    layer = Mock()
    layer.name.return_value = "Shapefile Layer"
    layer.providerType.return_value = "ogr"
    layer.featureCount.return_value = 1000
    layer.isValid.return_value = True
    layer.dataProvider().capabilities.return_value = 0  # No Spatialite caps
    return layer


@pytest.fixture
def mock_postgresql_connection():
    """Mock PostgreSQL connection"""
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    return conn, cursor


@pytest.fixture
def temp_config(tmp_path):
    """Create temporary configuration"""
    config = {
        "PATH_ABSOLUTE_PROJECT": str(tmp_path),
        "PLUGIN_CONFIG_DIRECTORY": str(tmp_path / "config")
    }
    return config
