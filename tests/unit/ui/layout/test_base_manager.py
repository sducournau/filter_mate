"""
Tests for LayoutManagerBase abstract class.

Story: MIG-060
Phase: 6 - God Class DockWidget Migration
"""

import pytest
from unittest.mock import Mock, MagicMock
import sys
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))


class TestLayoutManagerBase:
    """Tests for LayoutManagerBase abstract class."""
    
    def test_cannot_instantiate_abstract(self):
        """Should not instantiate abstract class directly."""
        from ui.layout.base_manager import LayoutManagerBase
        
        mock_dockwidget = Mock()
        with pytest.raises(TypeError) as exc_info:
            LayoutManagerBase(mock_dockwidget)
        
        assert "abstract" in str(exc_info.value).lower() or "instantiate" in str(exc_info.value).lower()
    
    def test_concrete_manager_creation(self):
        """Should create concrete implementation."""
        from ui.layout.base_manager import LayoutManagerBase
        
        # Create a concrete implementation for testing
        class ConcreteManager(LayoutManagerBase):
            def setup(self):
                self._initialized = True
            
            def apply(self):
                pass
        
        mock_dockwidget = Mock()
        manager = ConcreteManager(mock_dockwidget)
        
        assert manager.dockwidget is mock_dockwidget
        assert not manager.is_initialized
    
    def test_setup_sets_initialized(self):
        """Setup should set initialized flag."""
        from ui.layout.base_manager import LayoutManagerBase
        
        class ConcreteManager(LayoutManagerBase):
            def setup(self):
                self._initialized = True
            
            def apply(self):
                pass
        
        mock_dockwidget = Mock()
        manager = ConcreteManager(mock_dockwidget)
        
        assert not manager.is_initialized
        manager.setup()
        assert manager.is_initialized
    
    def test_teardown_clears_initialized(self):
        """Teardown should clear initialized flag."""
        from ui.layout.base_manager import LayoutManagerBase
        
        class ConcreteManager(LayoutManagerBase):
            def setup(self):
                self._initialized = True
            
            def apply(self):
                pass
        
        mock_dockwidget = Mock()
        manager = ConcreteManager(mock_dockwidget)
        
        manager.setup()
        assert manager.is_initialized
        
        manager.teardown()
        assert not manager.is_initialized
    
    def test_get_plugin_dir(self):
        """Should return plugin directory from dockwidget."""
        from ui.layout.base_manager import LayoutManagerBase
        
        class ConcreteManager(LayoutManagerBase):
            def setup(self):
                self._initialized = True
            
            def apply(self):
                pass
        
        mock_dockwidget = Mock()
        mock_dockwidget.plugin_dir = "/path/to/plugin"
        
        manager = ConcreteManager(mock_dockwidget)
        assert manager._get_plugin_dir() == "/path/to/plugin"
    
    def test_get_plugin_dir_missing(self):
        """Should return empty string if plugin_dir not available."""
        from ui.layout.base_manager import LayoutManagerBase
        
        class ConcreteManager(LayoutManagerBase):
            def setup(self):
                self._initialized = True
            
            def apply(self):
                pass
        
        mock_dockwidget = Mock(spec=[])  # No plugin_dir attribute
        
        manager = ConcreteManager(mock_dockwidget)
        assert manager._get_plugin_dir() == ''


class TestLayoutModuleImports:
    """Tests for layout module imports."""
    
    def test_import_layout_module(self):
        """Should import layout module without errors."""
        from ui import layout
        
        assert hasattr(layout, 'LayoutManagerBase')
        assert hasattr(layout, 'SplitterManager')
        assert hasattr(layout, 'DimensionsManager')
        assert hasattr(layout, 'SpacingManager')
        assert hasattr(layout, 'ActionBarManager')
    
    def test_all_exports(self):
        """__all__ should contain all public classes."""
        from ui.layout import __all__
        
        expected = [
            'LayoutManagerBase',
            'SplitterManager',
            'DimensionsManager',
            'SpacingManager',
            'ActionBarManager',
        ]
        assert set(__all__) == set(expected)
    
    def test_direct_imports(self):
        """Should be able to import classes directly."""
        from ui.layout import LayoutManagerBase
        from ui.layout import SplitterManager
        from ui.layout import DimensionsManager
        from ui.layout import SpacingManager
        from ui.layout import ActionBarManager
        
        assert LayoutManagerBase is not None
        assert SplitterManager is not None
        assert DimensionsManager is not None
        assert SpacingManager is not None
        assert ActionBarManager is not None
