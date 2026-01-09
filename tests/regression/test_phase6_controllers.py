"""
Phase 6 Regression Tests - Controllers.

Story: MIG-089
Tests for Sprint 7 (Controllers & Services) components.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add plugin path
plugin_path = Path(__file__).parents[3]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))


# ─────────────────────────────────────────────────────────────────
# Mock Classes
# ─────────────────────────────────────────────────────────────────

class MockDockWidget:
    """Mock dockwidget for testing."""
    
    def __init__(self):
        self.comboBox_filtering_layer = Mock()
        self.comboBox_exploring_layer = Mock()
        self.comboBox_backend = Mock()


class MockService:
    """Mock service for testing."""
    
    def __init__(self):
        pass


# ─────────────────────────────────────────────────────────────────
# Test ConfigController
# ─────────────────────────────────────────────────────────────────

class TestConfigControllerRegression:
    """Regression tests for ConfigController."""
    
    def test_import(self):
        """Test ConfigController can be imported."""
        from ui.controllers import ConfigController
        assert ConfigController is not None
    
    def test_init(self):
        """Test ConfigController initialization."""
        from ui.controllers import ConfigController
        dw = MockDockWidget()
        
        controller = ConfigController(dw)
        
        assert controller is not None


# ─────────────────────────────────────────────────────────────────
# Test BackendController
# ─────────────────────────────────────────────────────────────────

class TestBackendControllerRegression:
    """Regression tests for BackendController."""
    
    def test_import(self):
        """Test BackendController can be imported."""
        from ui.controllers import BackendController
        assert BackendController is not None
    
    def test_init(self):
        """Test BackendController initialization."""
        from ui.controllers import BackendController
        dw = MockDockWidget()
        
        controller = BackendController(dw)
        
        assert controller is not None


# ─────────────────────────────────────────────────────────────────
# Test FavoritesController
# ─────────────────────────────────────────────────────────────────

class TestFavoritesControllerRegression:
    """Regression tests for FavoritesController."""
    
    def test_import(self):
        """Test FavoritesController can be imported."""
        from ui.controllers import FavoritesController
        assert FavoritesController is not None
    
    def test_init(self):
        """Test FavoritesController initialization."""
        from ui.controllers import FavoritesController
        dw = MockDockWidget()
        
        controller = FavoritesController(dw)
        
        assert controller is not None


# ─────────────────────────────────────────────────────────────────
# Test LayerSyncController
# ─────────────────────────────────────────────────────────────────

class TestLayerSyncControllerRegression:
    """Regression tests for LayerSyncController."""
    
    def test_import(self):
        """Test LayerSyncController can be imported."""
        from ui.controllers import LayerSyncController
        assert LayerSyncController is not None
    
    def test_init(self):
        """Test LayerSyncController initialization."""
        from ui.controllers import LayerSyncController
        dw = MockDockWidget()
        
        controller = LayerSyncController(dw)
        
        assert controller is not None


# ─────────────────────────────────────────────────────────────────
# Test PropertyController
# ─────────────────────────────────────────────────────────────────

class TestPropertyControllerRegression:
    """Regression tests for PropertyController."""
    
    def test_import(self):
        """Test PropertyController can be imported."""
        from ui.controllers import PropertyController
        assert PropertyController is not None
    
    def test_init(self):
        """Test PropertyController initialization."""
        from ui.controllers import PropertyController
        dw = MockDockWidget()
        
        controller = PropertyController(dw)
        
        assert controller is not None


# ─────────────────────────────────────────────────────────────────
# Test FilteringController
# ─────────────────────────────────────────────────────────────────

class TestFilteringControllerRegression:
    """Regression tests for FilteringController."""
    
    def test_import(self):
        """Test FilteringController can be imported."""
        from ui.controllers import FilteringController
        assert FilteringController is not None
    
    def test_init(self):
        """Test FilteringController initialization."""
        from ui.controllers import FilteringController
        dw = MockDockWidget()
        
        controller = FilteringController(dw)
        
        assert controller is not None


# ─────────────────────────────────────────────────────────────────
# Test ExploringController
# ─────────────────────────────────────────────────────────────────

class TestExploringControllerRegression:
    """Regression tests for ExploringController."""
    
    def test_import(self):
        """Test ExploringController can be imported."""
        from ui.controllers import ExploringController
        assert ExploringController is not None
    
    def test_init(self):
        """Test ExploringController initialization."""
        from ui.controllers import ExploringController
        dw = MockDockWidget()
        
        controller = ExploringController(dw)
        
        assert controller is not None


# ─────────────────────────────────────────────────────────────────
# Test ExportingController
# ─────────────────────────────────────────────────────────────────

class TestExportingControllerRegression:
    """Regression tests for ExportingController."""
    
    def test_import(self):
        """Test ExportingController can be imported."""
        from ui.controllers import ExportingController
        assert ExportingController is not None
    
    def test_init(self):
        """Test ExportingController initialization."""
        from ui.controllers import ExportingController
        dw = MockDockWidget()
        
        controller = ExportingController(dw)
        
        assert controller is not None
