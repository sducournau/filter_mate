"""
Phase 6 Regression Tests - Services.

Story: MIG-089
Tests for core services.
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


# ─────────────────────────────────────────────────────────────────
# Test BackendService
# ─────────────────────────────────────────────────────────────────

class TestBackendServiceRegression:
    """Regression tests for BackendService."""
    
    def test_import(self):
        """Test BackendService can be imported."""
        from core.services import BackendService
        assert BackendService is not None
    
    def test_init(self):
        """Test BackendService initialization."""
        from core.services import BackendService
        dw = MockDockWidget()
        
        service = BackendService(dw)
        
        assert service is not None


# ─────────────────────────────────────────────────────────────────
# Test FilterService
# ─────────────────────────────────────────────────────────────────

class TestFilterServiceRegression:
    """Regression tests for FilterService."""
    
    def test_import(self):
        """Test FilterService can be imported."""
        from core.services import FilterService
        assert FilterService is not None
    
    def test_init(self):
        """Test FilterService initialization."""
        from core.services import FilterService
        dw = MockDockWidget()
        
        service = FilterService(dw)
        
        assert service is not None


# ─────────────────────────────────────────────────────────────────
# Test FavoritesService
# ─────────────────────────────────────────────────────────────────

class TestFavoritesServiceRegression:
    """Regression tests for FavoritesService."""
    
    def test_import(self):
        """Test FavoritesService can be imported."""
        from core.services import FavoritesService
        assert FavoritesService is not None
    
    def test_init(self):
        """Test FavoritesService initialization."""
        from core.services import FavoritesService
        dw = MockDockWidget()
        
        service = FavoritesService(dw)
        
        assert service is not None


# ─────────────────────────────────────────────────────────────────
# Test LayerService
# ─────────────────────────────────────────────────────────────────

class TestLayerServiceRegression:
    """Regression tests for LayerService."""
    
    def test_import(self):
        """Test LayerService can be imported."""
        from core.services import LayerService
        assert LayerService is not None
    
    def test_init(self):
        """Test LayerService initialization."""
        from core.services import LayerService
        dw = MockDockWidget()
        
        service = LayerService(dw)
        
        assert service is not None


# ─────────────────────────────────────────────────────────────────
# Test PostgresSessionManager
# ─────────────────────────────────────────────────────────────────

class TestPostgresSessionManagerRegression:
    """Regression tests for PostgresSessionManager."""
    
    def test_import(self):
        """Test PostgresSessionManager can be imported."""
        from core.services import PostgresSessionManager
        assert PostgresSessionManager is not None
    
    def test_init(self):
        """Test PostgresSessionManager initialization."""
        from core.services import PostgresSessionManager
        dw = MockDockWidget()
        
        manager = PostgresSessionManager(dw)
        
        assert manager is not None


# ─────────────────────────────────────────────────────────────────
# Test ExpressionService
# ─────────────────────────────────────────────────────────────────

class TestExpressionServiceRegression:
    """Regression tests for ExpressionService."""
    
    def test_import(self):
        """Test ExpressionService can be imported."""
        from core.services import ExpressionService
        assert ExpressionService is not None


# ─────────────────────────────────────────────────────────────────
# Test HistoryService
# ─────────────────────────────────────────────────────────────────

class TestHistoryServiceRegression:
    """Regression tests for HistoryService."""
    
    def test_import(self):
        """Test HistoryService can be imported."""
        from core.services import HistoryService
        assert HistoryService is not None
