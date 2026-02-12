# -*- coding: utf-8 -*-
"""
FilterMate Test Configuration -- Root conftest.py

Provides shared fixtures for all test modules.
All fixtures mock QGIS dependencies so tests run without a QGIS environment.

Usage:
    pytest                       # Run all unit tests (default marker filter)
    pytest -m unit               # Run only unit-marked tests
    pytest -m integration        # Run only integration tests (requires QGIS)
    pytest tests/unit/core/      # Run only core unit tests
"""
import sys
from unittest.mock import MagicMock

import pytest


# ---------------------------------------------------------------------------
# QGIS Mock Setup -- patch qgis.* BEFORE any plugin code is imported
# ---------------------------------------------------------------------------

def _create_qgis_mocks():
    """Create a comprehensive set of QGIS mock modules.

    Returns a dict mapping module name -> mock object, suitable
    for patching into sys.modules.
    """
    mocks = {}

    # qgis top-level
    qgis_mock = MagicMock()
    mocks["qgis"] = qgis_mock

    # qgis.core -- most commonly imported
    qgis_core = MagicMock()
    # Provide commonly referenced classes as distinct mocks so
    # isinstance() checks don't accidentally pass for unrelated types.
    qgis_core.QgsVectorLayer = MagicMock
    qgis_core.QgsRasterLayer = MagicMock
    qgis_core.QgsProject = MagicMock
    qgis_core.QgsFeatureRequest = MagicMock
    qgis_core.QgsDataSourceUri = MagicMock
    qgis_core.QgsField = MagicMock
    qgis_core.QgsFields = MagicMock
    qgis_core.QgsFeature = MagicMock
    qgis_core.QgsGeometry = MagicMock
    qgis_core.QgsTask = MagicMock
    qgis_core.QgsTaskManager = MagicMock
    qgis_core.QgsCoordinateReferenceSystem = MagicMock
    qgis_core.QgsCoordinateTransform = MagicMock
    qgis_core.QgsWkbTypes = MagicMock
    qgis_core.QgsPointXY = MagicMock
    qgis_core.QgsRectangle = MagicMock
    mocks["qgis.core"] = qgis_core

    # qgis.gui
    qgis_gui = MagicMock()
    mocks["qgis.gui"] = qgis_gui

    # qgis.utils (provides iface)
    qgis_utils = MagicMock()
    qgis_utils.iface = MagicMock()
    mocks["qgis.utils"] = qgis_utils

    # qgis.PyQt wrappers
    qgis_pyqt = MagicMock()
    qgis_pyqt_qtcore = MagicMock()
    qgis_pyqt_qtcore.QObject = MagicMock
    qgis_pyqt_qtwidgets = MagicMock()
    qgis_pyqt_qtgui = MagicMock()
    mocks["qgis.PyQt"] = qgis_pyqt
    mocks["qgis.PyQt.QtCore"] = qgis_pyqt_qtcore
    mocks["qgis.PyQt.QtWidgets"] = qgis_pyqt_qtwidgets
    mocks["qgis.PyQt.QtGui"] = qgis_pyqt_qtgui

    return mocks


# Install mocks into sys.modules so any subsequent `import qgis.core` picks
# them up. This runs at import-time of conftest, i.e. before test collection.
_qgis_mocks = _create_qgis_mocks()
for _mod_name, _mock_obj in _qgis_mocks.items():
    if _mod_name not in sys.modules:
        sys.modules[_mod_name] = _mock_obj


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_iface():
    """Return a mock QGIS iface with common methods."""
    iface = MagicMock()
    iface.mapCanvas.return_value = MagicMock()
    iface.messageBar.return_value = MagicMock()
    iface.mainWindow.return_value = MagicMock()
    return iface


@pytest.fixture
def mock_vector_layer():
    """Return a mock QgsVectorLayer with common attributes."""
    layer = MagicMock()
    layer.id.return_value = "test_layer_001"
    layer.name.return_value = "test_layer"
    layer.isValid.return_value = True
    layer.providerType.return_value = "ogr"
    layer.featureCount.return_value = 100
    layer.source.return_value = "/tmp/test.gpkg|layername=test"  # nosec B108
    layer.subsetString.return_value = ""
    layer.setSubsetString.return_value = True
    layer.hasSubsetString = MagicMock(return_value=False)

    # Fields mock
    fields = MagicMock()
    fields.indexOf.return_value = 0
    field_mock = MagicMock()
    field_mock.name.return_value = "id"
    field_mock.typeName.return_value = "integer"
    field_mock.isNumeric.return_value = True
    fields.__getitem__ = MagicMock(return_value=field_mock)
    layer.fields.return_value = fields

    # Primary key
    layer.primaryKeyAttributes.return_value = [0]

    # Selected features
    layer.selectedFeatureCount.return_value = 0
    layer.selectedFeatures.return_value = []

    return layer


@pytest.fixture
def mock_raster_layer():
    """Return a mock QgsRasterLayer."""
    layer = MagicMock()
    layer.id.return_value = "raster_layer_001"
    layer.name.return_value = "test_raster"
    layer.isValid.return_value = True
    layer.providerType.return_value = "gdal"
    layer.bandCount.return_value = 3
    layer.width.return_value = 1000
    layer.height.return_value = 800
    layer.source.return_value = "/tmp/test.tif"  # nosec B108
    return layer


@pytest.fixture
def mock_qgs_project():
    """Return a mock QgsProject singleton."""
    project = MagicMock()
    project.instance.return_value = project
    project.mapLayers.return_value = {}
    return project


@pytest.fixture
def mock_feature():
    """Return a mock QgsFeature."""
    feature = MagicMock()
    feature.id.return_value = 1
    feature.geometry.return_value = MagicMock()
    feature.attribute.return_value = 1
    feature.isValid.return_value = True
    return feature
