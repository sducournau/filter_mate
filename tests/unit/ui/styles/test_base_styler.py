"""
Tests for StylerBase abstract class.

Story: MIG-065
Phase: 6 - God Class DockWidget Migration

Note: QGIS mocks are configured in conftest.py to be shared across all style tests.
"""

import pytest
from unittest.mock import Mock
import sys
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))

# QGIS mocks are configured in conftest.py - do not reconfigure here


class TestStylerBase:
    """Tests for StylerBase abstract class."""
    
    def test_cannot_instantiate_abstract(self):
        """StylerBase should not be instantiable directly."""
        from ui.styles.base_styler import StylerBase
        
        with pytest.raises(TypeError):
            StylerBase(Mock())
    
    def test_concrete_styler_creation(self):
        """Concrete implementation should be instantiable."""
        from ui.styles.base_styler import StylerBase
        
        class ConcreteStyler(StylerBase):
            def setup(self):
                self._initialized = True
            def apply(self):
                pass
            def on_theme_changed(self, theme):
                pass
        
        mock_dockwidget = Mock()
        styler = ConcreteStyler(mock_dockwidget)
        
        assert styler.dockwidget is mock_dockwidget
        assert not styler.is_initialized
    
    def test_setup_sets_initialized(self):
        """Setup should set initialized flag."""
        from ui.styles.base_styler import StylerBase
        
        class ConcreteStyler(StylerBase):
            def setup(self):
                self._initialized = True
            def apply(self):
                pass
            def on_theme_changed(self, theme):
                pass
        
        styler = ConcreteStyler(Mock())
        styler.setup()
        
        assert styler.is_initialized
    
    def test_teardown_clears_initialized(self):
        """Teardown should clear initialized flag."""
        from ui.styles.base_styler import StylerBase
        
        class ConcreteStyler(StylerBase):
            def setup(self):
                self._initialized = True
            def apply(self):
                pass
            def on_theme_changed(self, theme):
                pass
        
        styler = ConcreteStyler(Mock())
        styler.setup()
        assert styler.is_initialized
        
        styler.teardown()
        assert not styler.is_initialized
    
    def test_get_plugin_dir_from_dockwidget(self):
        """get_plugin_dir should return dockwidget's plugin_dir."""
        from ui.styles.base_styler import StylerBase
        
        class ConcreteStyler(StylerBase):
            def setup(self):
                pass
            def apply(self):
                pass
            def on_theme_changed(self, theme):
                pass
        
        mock_dockwidget = Mock()
        mock_dockwidget.plugin_dir = '/path/to/plugin'
        
        styler = ConcreteStyler(mock_dockwidget)
        
        assert styler.get_plugin_dir() == '/path/to/plugin'
    
    def test_get_plugin_dir_missing_returns_none(self):
        """get_plugin_dir should return None if not available."""
        from ui.styles.base_styler import StylerBase
        
        class ConcreteStyler(StylerBase):
            def setup(self):
                pass
            def apply(self):
                pass
            def on_theme_changed(self, theme):
                pass
        
        mock_dockwidget = Mock(spec=[])  # No plugin_dir attribute
        
        styler = ConcreteStyler(mock_dockwidget)
        
        assert styler.get_plugin_dir() is None


class TestStylesModuleImports:
    """Test module imports and exports."""
    
    def test_import_styles_module(self):
        """Should be able to import ui.styles module."""
        import ui.styles
        assert ui.styles is not None
    
    def test_import_base_styler(self):
        """Should be able to import StylerBase."""
        from ui.styles.base_styler import StylerBase
        assert StylerBase is not None
