"""
Phase 6 Regression Tests - Orchestrator & Utils.

Story: MIG-089
Tests for Sprint 9 (Final Refactoring) components.
"""

import pytest
import warnings
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


class MockApp:
    """Mock FilterMateApp."""
    pass


class MockIface:
    """Mock QGIS iface."""
    pass


# ─────────────────────────────────────────────────────────────────
# Test DockWidgetOrchestrator
# ─────────────────────────────────────────────────────────────────

class TestDockWidgetOrchestratorRegression:
    """Regression tests for DockWidgetOrchestrator."""
    
    def test_import(self):
        """Test DockWidgetOrchestrator can be imported."""
        from ui import DockWidgetOrchestrator
        assert DockWidgetOrchestrator is not None
    
    def test_init(self):
        """Test DockWidgetOrchestrator initialization."""
        from ui import DockWidgetOrchestrator
        dw = MockDockWidget()
        app = MockApp()
        iface = MockIface()
        
        orch = DockWidgetOrchestrator(dw, app, iface)
        
        assert orch is not None
        assert not orch.is_initialized
    
    def test_factory_function(self):
        """Test create_orchestrator factory function."""
        from ui import create_orchestrator
        
        assert create_orchestrator is not None
        assert callable(create_orchestrator)


# ─────────────────────────────────────────────────────────────────
# Test Deprecation Utilities
# ─────────────────────────────────────────────────────────────────

class TestDeprecationRegression:
    """Regression tests for deprecation utilities."""
    
    def test_import(self):
        """Test deprecation utilities can be imported."""
        from utils import deprecated, deprecated_property, deprecated_class
        
        assert deprecated is not None
        assert deprecated_property is not None
        assert deprecated_class is not None
    
    def test_decorator_works(self):
        """Test @deprecated decorator works."""
        from utils import deprecated
        
        @deprecated(version='4.0', reason='Testing')
        def old_func():
            return 'result'
        
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = old_func()
            
            assert len(w) == 1
            assert result == 'result'
    
    def test_registry(self):
        """Test DeprecationRegistry works."""
        from utils.deprecation import DeprecationRegistry
        
        registry = DeprecationRegistry.get_instance()
        assert registry is not None
        
        # Reset for clean state
        registry.reset()
        
        registry.register('test.func', '4.0', 'Testing', None)
        items = registry.get_all_deprecated()
        
        assert len(items) >= 1


# ─────────────────────────────────────────────────────────────────
# Test Integration - Full Phase 6 Stack
# ─────────────────────────────────────────────────────────────────

class TestPhase6Integration:
    """Integration tests for Phase 6 components."""
    
    def test_layout_module_exports(self):
        """Test ui.layout exports all expected managers."""
        from ui.layout import (
            SplitterManager,
            DimensionsManager,
            SpacingManager,
            ActionBarManager,
        )
        
        assert SplitterManager is not None
        assert DimensionsManager is not None
        assert SpacingManager is not None
        assert ActionBarManager is not None
    
    def test_styles_module_exports(self):
        """Test ui.styles exports all expected managers."""
        from ui.styles import (
            ThemeManager,
            IconManager,
            ButtonStyler,
        )
        
        assert ThemeManager is not None
        assert IconManager is not None
        assert ButtonStyler is not None
    
    def test_controllers_module_exports(self):
        """Test ui.controllers exports all expected controllers."""
        from ui.controllers import (
            ConfigController,
            BackendController,
            FavoritesController,
            LayerSyncController,
            PropertyController,
            FilteringController,
            ExploringController,
            ExportingController,
        )
        
        assert ConfigController is not None
        assert BackendController is not None
        assert FavoritesController is not None
        assert LayerSyncController is not None
        assert PropertyController is not None
        assert FilteringController is not None
        assert ExploringController is not None
        assert ExportingController is not None
    
    def test_services_module_exports(self):
        """Test core.services exports all expected services."""
        from core.services import (
            BackendService,
            FilterService,
            FavoritesService,
            LayerService,
            PostgresSessionManager,
        )
        
        assert BackendService is not None
        assert FilterService is not None
        assert FavoritesService is not None
        assert LayerService is not None
        assert PostgresSessionManager is not None
    
    def test_signals_module_exports(self):
        """Test adapters.qgis.signals exports all expected classes."""
        from adapters.qgis.signals import (
            SignalManager,
            LayerSignalHandler,
            SignalMigrationHelper,
        )
        
        assert SignalManager is not None
        assert LayerSignalHandler is not None
        assert SignalMigrationHelper is not None
    
    def test_dialogs_module_exports(self):
        """Test ui.dialogs exports all expected dialogs."""
        from ui.dialogs import (
            FavoritesManagerDialog,
            OptimizationDialog,
            PostgresInfoDialog,
        )
        
        assert FavoritesManagerDialog is not None
        assert OptimizationDialog is not None
        assert PostgresInfoDialog is not None


# ─────────────────────────────────────────────────────────────────
# Test CRIT-005 Prevention (Layer Sync)
# ─────────────────────────────────────────────────────────────────

class TestCRIT005Prevention:
    """
    Tests to prevent CRIT-005 regression.
    
    CRIT-005: Layer combo box selection is lost after filter operations.
    The LayerSyncController should maintain layer selection state.
    """
    
    def test_layer_sync_controller_exists(self):
        """Verify LayerSyncController exists for CRIT-005."""
        from ui.controllers import LayerSyncController
        assert LayerSyncController is not None
    
    def test_layer_sync_has_current_layer(self):
        """Verify LayerSyncController has current_layer property."""
        from ui.controllers import LayerSyncController
        dw = MockDockWidget()
        
        controller = LayerSyncController(dw)
        
        # Should have current_layer attribute or property
        assert hasattr(controller, 'current_layer') or hasattr(type(controller), 'current_layer')


# ─────────────────────────────────────────────────────────────────
# Summary Test
# ─────────────────────────────────────────────────────────────────

class TestPhase6Summary:
    """
    Summary test ensuring all Phase 6 components exist.
    
    This test fails if ANY Phase 6 component is missing.
    """
    
    def test_phase6_complete(self):
        """Verify all Phase 6 components exist."""
        components = []
        
        # Layout managers (Sprint 6)
        try:
            from ui.layout import SplitterManager
            components.append(('SplitterManager', True))
        except ImportError:
            components.append(('SplitterManager', False))
        
        try:
            from ui.layout import DimensionsManager
            components.append(('DimensionsManager', True))
        except ImportError:
            components.append(('DimensionsManager', False))
        
        try:
            from ui.layout import SpacingManager
            components.append(('SpacingManager', True))
        except ImportError:
            components.append(('SpacingManager', False))
        
        try:
            from ui.layout import ActionBarManager
            components.append(('ActionBarManager', True))
        except ImportError:
            components.append(('ActionBarManager', False))
        
        # Style managers (Sprint 6)
        try:
            from ui.styles import ThemeManager
            components.append(('ThemeManager', True))
        except ImportError:
            components.append(('ThemeManager', False))
        
        try:
            from ui.styles import IconManager
            components.append(('IconManager', True))
        except ImportError:
            components.append(('IconManager', False))
        
        try:
            from ui.styles import ButtonStyler
            components.append(('ButtonStyler', True))
        except ImportError:
            components.append(('ButtonStyler', False))
        
        # Controllers (Sprint 7)
        try:
            from ui.controllers import ConfigController
            components.append(('ConfigController', True))
        except ImportError:
            components.append(('ConfigController', False))
        
        try:
            from ui.controllers import BackendController
            components.append(('BackendController', True))
        except ImportError:
            components.append(('BackendController', False))
        
        try:
            from ui.controllers import LayerSyncController
            components.append(('LayerSyncController', True))
        except ImportError:
            components.append(('LayerSyncController', False))
        
        # Services (Sprint 7)
        try:
            from core.services import PostgresSessionManager
            components.append(('PostgresSessionManager', True))
        except ImportError:
            components.append(('PostgresSessionManager', False))
        
        # Signals (Sprint 8)
        try:
            from adapters.qgis.signals import SignalManager
            components.append(('SignalManager', True))
        except ImportError:
            components.append(('SignalManager', False))
        
        try:
            from adapters.qgis.signals import LayerSignalHandler
            components.append(('LayerSignalHandler', True))
        except ImportError:
            components.append(('LayerSignalHandler', False))
        
        try:
            from adapters.qgis.signals import SignalMigrationHelper
            components.append(('SignalMigrationHelper', True))
        except ImportError:
            components.append(('SignalMigrationHelper', False))
        
        # Dialogs (Sprint 8)
        try:
            from ui.dialogs import FavoritesManagerDialog
            components.append(('FavoritesManagerDialog', True))
        except ImportError:
            components.append(('FavoritesManagerDialog', False))
        
        try:
            from ui.dialogs import OptimizationDialog
            components.append(('OptimizationDialog', True))
        except ImportError:
            components.append(('OptimizationDialog', False))
        
        try:
            from ui.dialogs import PostgresInfoDialog
            components.append(('PostgresInfoDialog', True))
        except ImportError:
            components.append(('PostgresInfoDialog', False))
        
        # Orchestrator (Sprint 9)
        try:
            from ui import DockWidgetOrchestrator
            components.append(('DockWidgetOrchestrator', True))
        except ImportError:
            components.append(('DockWidgetOrchestrator', False))
        
        # Deprecation (Sprint 9)
        try:
            from utils import deprecated
            components.append(('deprecated decorator', True))
        except ImportError:
            components.append(('deprecated decorator', False))
        
        # Check results
        failed = [name for name, exists in components if not exists]
        
        if failed:
            pytest.fail(
                f"Phase 6 incomplete! Missing components: {', '.join(failed)}"
            )
        
        # All components exist
        assert all(exists for _, exists in components), \
            "All Phase 6 components should exist"
