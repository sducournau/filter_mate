"""
Phase 6 Regression Tests - Signals.

Story: MIG-089
Tests for Sprint 8 (Dialogs & Signals) components.
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
    pass


class MockSignalManager:
    """Mock signal manager."""
    
    def __init__(self, dockwidget=None):
        self.dockwidget = dockwidget


# ─────────────────────────────────────────────────────────────────
# Test SignalManager
# ─────────────────────────────────────────────────────────────────

class TestSignalManagerRegression:
    """Regression tests for SignalManager."""
    
    def test_import(self):
        """Test SignalManager can be imported."""
        from adapters.qgis.signals import SignalManager
        assert SignalManager is not None
    
    def test_init(self):
        """Test SignalManager initialization."""
        from adapters.qgis.signals import SignalManager
        dw = MockDockWidget()
        
        manager = SignalManager(dw)
        
        assert manager is not None
    
    def test_connect_method_exists(self):
        """Test connect method exists."""
        from adapters.qgis.signals import SignalManager
        dw = MockDockWidget()
        manager = SignalManager(dw)
        
        assert hasattr(manager, 'connect')
        assert callable(manager.connect)
    
    def test_disconnect_method_exists(self):
        """Test disconnect method exists."""
        from adapters.qgis.signals import SignalManager
        dw = MockDockWidget()
        manager = SignalManager(dw)
        
        assert hasattr(manager, 'disconnect')
        assert callable(manager.disconnect)


# ─────────────────────────────────────────────────────────────────
# Test LayerSignalHandler
# ─────────────────────────────────────────────────────────────────

class TestLayerSignalHandlerRegression:
    """Regression tests for LayerSignalHandler."""
    
    def test_import(self):
        """Test LayerSignalHandler can be imported."""
        from adapters.qgis.signals import LayerSignalHandler
        assert LayerSignalHandler is not None
    
    def test_init(self):
        """Test LayerSignalHandler initialization."""
        from adapters.qgis.signals import LayerSignalHandler
        dw = MockDockWidget()
        sm = MockSignalManager(dw)
        
        handler = LayerSignalHandler(dw, sm)
        
        assert handler is not None


# ─────────────────────────────────────────────────────────────────
# Test SignalMigrationHelper
# ─────────────────────────────────────────────────────────────────

class TestSignalMigrationHelperRegression:
    """Regression tests for SignalMigrationHelper."""
    
    def test_import(self):
        """Test SignalMigrationHelper can be imported."""
        from adapters.qgis.signals import SignalMigrationHelper
        assert SignalMigrationHelper is not None
    
    def test_signal_definitions(self):
        """Test DOCKWIDGET_WIDGET_SIGNALS can be imported."""
        from adapters.qgis.signals import DOCKWIDGET_WIDGET_SIGNALS
        
        assert len(DOCKWIDGET_WIDGET_SIGNALS) > 0


# ─────────────────────────────────────────────────────────────────
# Test Dialogs
# ─────────────────────────────────────────────────────────────────

class TestFavoritesManagerDialogRegression:
    """Regression tests for FavoritesManagerDialog."""
    
    def test_import(self):
        """Test FavoritesManagerDialog can be imported."""
        from ui.dialogs import FavoritesManagerDialog
        assert FavoritesManagerDialog is not None


class TestOptimizationDialogRegression:
    """Regression tests for OptimizationDialog."""
    
    def test_import(self):
        """Test OptimizationDialog can be imported."""
        from ui.dialogs import OptimizationDialog
        assert OptimizationDialog is not None


class TestPostgresInfoDialogRegression:
    """Regression tests for PostgresInfoDialog."""
    
    def test_import(self):
        """Test PostgresInfoDialog can be imported."""
        from ui.dialogs import PostgresInfoDialog
        assert PostgresInfoDialog is not None
