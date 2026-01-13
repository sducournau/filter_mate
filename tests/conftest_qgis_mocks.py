# -*- coding: utf-8 -*-
"""
QGIS Mock Classes for Testing Without QGIS Environment.

This module provides proper mock classes that work with isinstance() checks.
Use these in tests that need to simulate QGIS objects.

Author: FilterMate Team
Date: January 2026
"""

import sys
from unittest.mock import Mock, MagicMock
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# ============================================================================
# Mock QGIS Core Classes
# ============================================================================

class MockQgsVectorLayer:
    """
    Mock QgsVectorLayer that properly works with isinstance() checks.
    
    This class simulates a QGIS vector layer for testing purposes.
    """
    
    def __init__(
        self,
        layer_id: str = "test_layer_123",
        name: str = "test_layer",
        provider_type: str = "postgres",
        is_valid: bool = True,
        is_editable: bool = False,
        subset_string: str = "",
        feature_count: int = 1000,
        crs_authid: str = "EPSG:4326",
        wkb_type: int = 1,
        deleted: bool = False
    ):
        self._id = layer_id
        self._name = name
        self._provider_type = provider_type
        self._is_valid = is_valid
        self._is_editable = is_editable
        self._subset_string = subset_string
        self._feature_count = feature_count
        self._crs_authid = crs_authid
        self._wkb_type = wkb_type
        self._deleted = deleted
        self._fields = []
        self._primary_key_attrs = []
    
    def id(self) -> str:
        if self._deleted:
            raise RuntimeError("C++ object deleted")
        return self._id
    
    def name(self) -> str:
        if self._deleted:
            raise RuntimeError("C++ object deleted")
        return self._name
    
    def providerType(self) -> str:
        return self._provider_type
    
    def isValid(self) -> bool:
        return self._is_valid
    
    def isEditable(self) -> bool:
        return self._is_editable
    
    def subsetString(self) -> str:
        return self._subset_string
    
    def setSubsetString(self, subset: str) -> bool:
        self._subset_string = subset
        return True
    
    def featureCount(self) -> int:
        return self._feature_count
    
    def crs(self):
        crs = Mock()
        crs.authid.return_value = self._crs_authid
        return crs
    
    def wkbType(self) -> int:
        return self._wkb_type
    
    def fields(self):
        return self._fields
    
    def primaryKeyAttributes(self) -> List[int]:
        return self._primary_key_attrs


class MockQgsProject:
    """Mock QgsProject singleton."""
    
    _instance = None
    
    def __init__(self):
        self._layers: Dict[str, MockQgsVectorLayer] = {}
        self._filename = ""
    
    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset for testing."""
        cls._instance = None
    
    def mapLayers(self) -> Dict[str, MockQgsVectorLayer]:
        return self._layers
    
    def mapLayer(self, layer_id: str) -> Optional[MockQgsVectorLayer]:
        return self._layers.get(layer_id)
    
    def addMapLayer(self, layer: MockQgsVectorLayer) -> MockQgsVectorLayer:
        self._layers[layer.id()] = layer
        return layer
    
    def removeMapLayer(self, layer_id: str):
        if layer_id in self._layers:
            del self._layers[layer_id]
    
    def fileName(self) -> str:
        return self._filename


class MockQgsGeometry:
    """Mock QgsGeometry."""
    
    def __init__(self, wkt: str = "POINT(0 0)", is_empty: bool = False):
        self._wkt = wkt
        self._is_empty = is_empty
    
    def isEmpty(self) -> bool:
        return self._is_empty
    
    def asWkt(self, precision: int = 6) -> str:
        return self._wkt
    
    def isGeosValid(self) -> bool:
        return True
    
    def boundingBox(self):
        bbox = Mock()
        bbox.xMinimum.return_value = 0.0
        bbox.yMinimum.return_value = 0.0
        bbox.xMaximum.return_value = 1.0
        bbox.yMaximum.return_value = 1.0
        return bbox


class MockQgsTask:
    """Mock QgsTask base class."""
    
    CanCancel = 1
    
    def __init__(self, description: str = "", flags: int = 0):
        self._description = description
        self._progress = 0
        self._canceled = False
    
    def setProgress(self, progress: float):
        self._progress = progress
    
    def isCanceled(self) -> bool:
        return self._canceled


# ============================================================================
# Mock PyQt5 Classes
# ============================================================================

class MockSignal:
    """Mock pyqtSignal for testing."""
    
    def __init__(self, *args):
        self.args = args
        self.callbacks = []
    
    def emit(self, *args):
        for cb in self.callbacks:
            cb(*args)
    
    def connect(self, callback):
        self.callbacks.append(callback)
    
    def disconnect(self, callback=None):
        if callback:
            if callback in self.callbacks:
                self.callbacks.remove(callback)
        else:
            self.callbacks.clear()


class MockQObject:
    """Mock QObject."""
    
    def __init__(self, parent=None):
        self._parent = parent


# ============================================================================
# QGIS Module Setup
# ============================================================================

def setup_qgis_mocks():
    """
    Set up QGIS mocks in sys.modules.
    
    Call this at the beginning of test modules that need QGIS mocks.
    """
    # Create mock qgis.core module with proper classes
    mock_qgis_core = Mock()
    mock_qgis_core.QgsVectorLayer = MockQgsVectorLayer
    mock_qgis_core.QgsProject = MockQgsProject
    mock_qgis_core.QgsGeometry = MockQgsGeometry
    mock_qgis_core.QgsTask = MockQgsTask
    mock_qgis_core.Qgis = Mock()
    mock_qgis_core.Qgis.QGIS_VERSION = "3.34.0"
    
    # Create mock PyQt modules
    mock_pyqt = Mock()
    mock_pyqt.pyqtSignal = MockSignal
    mock_pyqt.QObject = MockQObject
    
    # Apply mocks
    sys.modules['qgis'] = Mock()
    sys.modules['qgis.core'] = mock_qgis_core
    sys.modules['qgis.PyQt'] = Mock()
    sys.modules['qgis.PyQt.QtCore'] = mock_pyqt
    sys.modules['qgis.PyQt.QtWidgets'] = Mock()
    sys.modules['qgis.PyQt.QtGui'] = Mock()
    sys.modules['qgis.utils'] = Mock()
    sys.modules['PyQt5'] = Mock()
    sys.modules['PyQt5.QtCore'] = mock_pyqt
    sys.modules['PyQt5.QtWidgets'] = Mock()
    sys.modules['PyQt5.QtGui'] = Mock()
    
    return mock_qgis_core


def teardown_qgis_mocks():
    """Remove QGIS mocks from sys.modules."""
    modules_to_remove = [
        'qgis', 'qgis.core', 'qgis.PyQt', 'qgis.PyQt.QtCore',
        'qgis.PyQt.QtWidgets', 'qgis.PyQt.QtGui', 'qgis.utils',
        'PyQt5', 'PyQt5.QtCore', 'PyQt5.QtWidgets', 'PyQt5.QtGui'
    ]
    for mod in modules_to_remove:
        if mod in sys.modules:
            del sys.modules[mod]
    
    MockQgsProject.reset_instance()


# ============================================================================
# Pytest Fixtures
# ============================================================================

def create_mock_vector_layer(**kwargs) -> MockQgsVectorLayer:
    """
    Factory function to create mock vector layers.
    
    Args:
        **kwargs: Override default MockQgsVectorLayer parameters
        
    Returns:
        MockQgsVectorLayer instance
    """
    return MockQgsVectorLayer(**kwargs)


def create_deleted_layer() -> MockQgsVectorLayer:
    """Create a mock layer that simulates a deleted C++ object."""
    return MockQgsVectorLayer(deleted=True)
