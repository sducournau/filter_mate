"""
Tests for SplitterManager.

Story: MIG-061
Phase: 6 - God Class DockWidget Migration
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import sys
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))


class TestSplitterManager:
    """Tests for SplitterManager class."""
    
    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget with required attributes."""
        dockwidget = Mock()
        dockwidget.splitter_main = Mock()
        dockwidget.splitter_main.height.return_value = 600
        dockwidget.splitter_main.sizes.return_value = [200, 400]
        dockwidget.frame_exploring = Mock()
        dockwidget.frame_toolset = Mock()
        return dockwidget
    
    @pytest.fixture
    def mock_ui_config(self):
        """Mock UIConfig module."""
        mock_config = {
            'handle_width': 6,
            'handle_margin': 40,
            'exploring_stretch': 2,
            'toolset_stretch': 5,
            'collapsible': False,
            'opaque_resize': True,
            'initial_exploring_ratio': 0.50,
            'initial_toolset_ratio': 0.50,
        }
        
        with patch.dict('sys.modules', {'modules.ui_config': Mock()}):
            with patch('ui.layout.splitter_manager.UIConfig') as mock_uic:
                mock_uic.get_config.return_value = mock_config
                yield mock_uic
    
    def test_creation(self, mock_dockwidget):
        """Should create manager with dockwidget reference."""
        from ui.layout.splitter_manager import SplitterManager
        
        manager = SplitterManager(mock_dockwidget)
        
        assert manager.dockwidget is mock_dockwidget
        assert not manager.is_initialized
        assert manager.splitter is None
    
    def test_setup_initializes_splitter(self, mock_dockwidget):
        """Setup should initialize splitter from dockwidget."""
        from ui.layout.splitter_manager import SplitterManager
        
        with patch.dict('sys.modules', {'modules.ui_config': Mock()}):
            manager = SplitterManager(mock_dockwidget)
            manager.setup()
            
            assert manager.is_initialized
            assert manager.splitter is mock_dockwidget.splitter_main
            assert mock_dockwidget.main_splitter is mock_dockwidget.splitter_main
    
    def test_setup_applies_properties(self, mock_dockwidget):
        """Setup should apply splitter properties from config."""
        from ui.layout.splitter_manager import SplitterManager
        
        with patch.dict('sys.modules', {'modules.ui_config': Mock()}):
            manager = SplitterManager(mock_dockwidget)
            manager.setup()
            
            splitter = mock_dockwidget.splitter_main
            splitter.setChildrenCollapsible.assert_called()
            splitter.setHandleWidth.assert_called()
            splitter.setOpaqueResize.assert_called()
    
    def test_setup_applies_stretch_factors(self, mock_dockwidget):
        """Setup should apply stretch factors."""
        from ui.layout.splitter_manager import SplitterManager
        
        with patch.dict('sys.modules', {'modules.ui_config': Mock()}):
            manager = SplitterManager(mock_dockwidget)
            manager.setup()
            
            splitter = mock_dockwidget.splitter_main
            # Check that setStretchFactor was called for both indices
            assert splitter.setStretchFactor.call_count >= 2
    
    def test_setup_applies_stylesheet(self, mock_dockwidget):
        """Setup should apply handle styling."""
        from ui.layout.splitter_manager import SplitterManager
        
        with patch.dict('sys.modules', {'modules.ui_config': Mock()}):
            manager = SplitterManager(mock_dockwidget)
            manager.setup()
            
            splitter = mock_dockwidget.splitter_main
            splitter.setStyleSheet.assert_called_once()
            stylesheet = splitter.setStyleSheet.call_args[0][0]
            assert 'QSplitter::handle:vertical' in stylesheet
    
    def test_setup_handles_missing_splitter(self):
        """Setup should handle missing splitter_main gracefully."""
        from ui.layout.splitter_manager import SplitterManager
        
        mock_dockwidget = Mock(spec=['frame_exploring', 'frame_toolset'])
        # splitter_main is not in spec, so hasattr will return False
        
        with patch.dict('sys.modules', {'modules.ui_config': Mock()}):
            manager = SplitterManager(mock_dockwidget)
            manager.setup()  # Should not raise
            
            assert not manager.is_initialized
    
    def test_apply_reapplies_config(self, mock_dockwidget):
        """Apply should reload and reapply configuration."""
        from ui.layout.splitter_manager import SplitterManager
        
        with patch.dict('sys.modules', {'modules.ui_config': Mock()}):
            manager = SplitterManager(mock_dockwidget)
            manager.setup()
            
            # Reset mock calls
            mock_dockwidget.splitter_main.reset_mock()
            
            manager.apply()
            
            # Should reapply properties
            mock_dockwidget.splitter_main.setChildrenCollapsible.assert_called()
    
    def test_apply_without_init_does_not_crash(self, mock_dockwidget):
        """Apply without setup should not crash."""
        from ui.layout.splitter_manager import SplitterManager
        
        manager = SplitterManager(mock_dockwidget)
        manager.apply()  # Should not raise, just log warning
    
    def test_get_sizes(self, mock_dockwidget):
        """get_sizes should return current splitter sizes."""
        from ui.layout.splitter_manager import SplitterManager
        
        mock_dockwidget.splitter_main.sizes.return_value = [200, 400]
        
        with patch.dict('sys.modules', {'modules.ui_config': Mock()}):
            manager = SplitterManager(mock_dockwidget)
            manager.setup()
            
            sizes = manager.get_sizes()
            assert sizes == [200, 400]
    
    def test_get_sizes_before_init(self, mock_dockwidget):
        """get_sizes before init should return empty list."""
        from ui.layout.splitter_manager import SplitterManager
        
        manager = SplitterManager(mock_dockwidget)
        assert manager.get_sizes() == []
    
    def test_set_sizes(self, mock_dockwidget):
        """set_sizes should update splitter sizes."""
        from ui.layout.splitter_manager import SplitterManager
        
        with patch.dict('sys.modules', {'modules.ui_config': Mock()}):
            manager = SplitterManager(mock_dockwidget)
            manager.setup()
            
            manager.set_sizes([150, 450])
            
            mock_dockwidget.splitter_main.setSizes.assert_called_with([150, 450])
    
    def test_set_sizes_invalid_length(self, mock_dockwidget):
        """set_sizes with wrong length should not crash."""
        from ui.layout.splitter_manager import SplitterManager
        
        with patch.dict('sys.modules', {'modules.ui_config': Mock()}):
            manager = SplitterManager(mock_dockwidget)
            manager.setup()
            
            mock_dockwidget.splitter_main.reset_mock()
            
            manager.set_sizes([100])  # Only one size
            
            # setSizes should not be called with invalid length
            mock_dockwidget.splitter_main.setSizes.assert_not_called()
    
    def test_save_and_restore_sizes(self, mock_dockwidget):
        """save_sizes and restore_sizes should work together."""
        from ui.layout.splitter_manager import SplitterManager
        
        mock_dockwidget.splitter_main.sizes.return_value = [200, 400]
        
        with patch.dict('sys.modules', {'modules.ui_config': Mock()}):
            manager = SplitterManager(mock_dockwidget)
            manager.setup()
            
            saved = manager.save_sizes()
            assert saved == [200, 400]
            
            manager.restore_sizes(saved)
            mock_dockwidget.splitter_main.setSizes.assert_called_with([200, 400])
    
    def test_teardown(self, mock_dockwidget):
        """Teardown should clean up resources."""
        from ui.layout.splitter_manager import SplitterManager
        
        with patch.dict('sys.modules', {'modules.ui_config': Mock()}):
            manager = SplitterManager(mock_dockwidget)
            manager.setup()
            
            assert manager.is_initialized
            assert manager.splitter is not None
            
            manager.teardown()
            
            assert not manager.is_initialized
            assert manager.splitter is None
    
    def test_policy_map_has_all_policies(self):
        """POLICY_MAP should contain all Qt size policies."""
        from ui.layout.splitter_manager import SplitterManager
        
        expected = ['Fixed', 'Minimum', 'Maximum', 'Preferred', 
                   'Expanding', 'MinimumExpanding', 'Ignored']
        
        assert all(p in SplitterManager.POLICY_MAP for p in expected)
    
    def test_default_config_values(self, mock_dockwidget):
        """Default config should have reasonable values."""
        from ui.layout.splitter_manager import SplitterManager
        
        manager = SplitterManager(mock_dockwidget)
        default_config = manager._get_default_config()
        
        assert default_config['handle_width'] == 6
        assert default_config['collapsible'] == False
        assert 'initial_exploring_ratio' in default_config
        assert 'initial_toolset_ratio' in default_config
