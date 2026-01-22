"""
Tests for SpacingManager.

Story: MIG-063
Phase: 6 - God Class DockWidget Migration
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))

# Mock QGIS modules before any imports that use them
_qgis_mock = MagicMock()
_qgis_pyqt_mock = MagicMock()
_qgis_gui_mock = MagicMock()

# Setup QSizePolicy mock with proper enum values
class MockQSizePolicy:
    Fixed = 0
    Minimum = 1
    Maximum = 4
    Preferred = 5
    Expanding = 7
    MinimumExpanding = 3
    Ignored = 13

_qgis_pyqt_mock.QtWidgets.QSizePolicy = MockQSizePolicy
_qgis_pyqt_mock.QtWidgets.QSpacerItem = MagicMock
_qgis_pyqt_mock.QtCore.QSize = Mock
_qgis_pyqt_mock.QtCore.Qt = Mock()

# Patch QGIS modules in sys.modules before imports
sys.modules['qgis'] = _qgis_mock
sys.modules['qgis.PyQt'] = _qgis_pyqt_mock
sys.modules['qgis.PyQt.QtWidgets'] = _qgis_pyqt_mock.QtWidgets
sys.modules['qgis.PyQt.QtCore'] = _qgis_pyqt_mock.QtCore
sys.modules['qgis.gui'] = _qgis_gui_mock
sys.modules['qgis.core'] = MagicMock()

# Mock modules before import
sys.modules['modules'] = MagicMock()
sys.modules['ui.config'] = MagicMock()
sys.modules['ui.elements'] = MagicMock()


class TestSpacingManager:
    """Tests for SpacingManager class."""
    
    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget with required attributes."""
        dockwidget = Mock()
        
        # Layouts
        dockwidget.verticalLayout_main_content = Mock()
        dockwidget.verticalLayout_exploring_single_selection = Mock()
        dockwidget.verticalLayout_exploring_multiple_selection = Mock()
        dockwidget.verticalLayout_exploring_custom_selection = Mock()
        dockwidget.verticalLayout_filtering_keys = Mock()
        dockwidget.verticalLayout_filtering_values = Mock()
        dockwidget.verticalLayout_exporting_keys = Mock()
        dockwidget.verticalLayout_exporting_values = Mock()
        dockwidget.verticalLayout_exploring_content = Mock()
        dockwidget.horizontalLayout_filtering_content = Mock()
        dockwidget.horizontalLayout_exporting_content = Mock()
        
        # Groupbox layouts
        dockwidget.gridLayout_exploring_single_content = Mock()
        dockwidget.gridLayout_exploring_multiple_content = Mock()
        dockwidget.verticalLayout_exploring_custom_container = Mock()
        
        # Widget keys with layouts
        dockwidget.widget_exploring_keys = Mock()
        dockwidget.widget_exploring_keys.layout.return_value = Mock()
        dockwidget.widget_filtering_keys = Mock()
        dockwidget.widget_filtering_keys.layout.return_value = Mock()
        dockwidget.widget_exporting_keys = Mock()
        dockwidget.widget_exporting_keys.layout.return_value = Mock()
        
        # Frame actions
        dockwidget.frame_actions = Mock()
        dockwidget.frame_actions.layout.return_value = Mock()
        
        return dockwidget
    
    @pytest.fixture
    def mock_ui_config(self):
        """Mock UIConfig module with typical configuration."""
        config_values = {
            ('layout', 'spacing_frame'): 8,
            ('layout', 'spacing_content'): 6,
            ('layout', 'spacing_section'): 8,
            ('layout', 'spacing_main'): 8,
            ('layout', 'margins_frame'): {'left': 8, 'top': 8, 'right': 8, 'bottom': 10},
            ('layout', 'margins_actions'): {'left': 8, 'top': 6, 'right': 8, 'bottom': 12},
            ('key_button',): {'min_size': 26, 'max_size': 32, 'icon_size': 16, 'spacing': 2},
        }
        
        def get_config(*args):
            if len(args) == 1:
                return config_values.get((args[0],), {})
            return config_values.get(args, None)
        
        return get_config
    
    def test_creation(self, mock_dockwidget):
        """Should create manager with dockwidget reference."""
        from ui.layout.spacing_manager import SpacingManager
        
        manager = SpacingManager(mock_dockwidget)
        
        assert manager.dockwidget is mock_dockwidget
        assert not manager.is_initialized
    
    def test_setup_initializes_manager(self, mock_dockwidget):
        """Setup should initialize the manager and apply spacing."""
        from ui.layout.spacing_manager import SpacingManager
        
        with patch('ui.layout.spacing_manager.SpacingManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = Mock(return_value=None)
            mock_get_config.return_value = mock_config
            
            manager = SpacingManager(mock_dockwidget)
            manager.setup()
            
            assert manager.is_initialized
    
    def test_apply_calls_all_spacing_methods(self, mock_dockwidget, mock_ui_config):
        """Apply should call all spacing-related methods."""
        from ui.layout.spacing_manager import SpacingManager
        
        with patch('ui.layout.spacing_manager.SpacingManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = mock_ui_config
            mock_get_config.return_value = mock_config
            
            manager = SpacingManager(mock_dockwidget)
            
            with patch.object(manager, 'apply_layout_spacing') as mock_layout:
                with patch.object(manager, 'harmonize_spacers') as mock_spacers:
                    with patch.object(manager, 'adjust_row_spacing') as mock_row:
                        manager.apply()
                        
                        mock_layout.assert_called_once()
                        mock_spacers.assert_called_once()
                        mock_row.assert_called_once()
    
    def test_apply_layout_spacing_sets_main_content_spacing(self, mock_dockwidget, mock_ui_config):
        """Apply layout spacing should set spacing on main content."""
        from ui.layout.spacing_manager import SpacingManager
        
        with patch('ui.layout.spacing_manager.SpacingManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = mock_ui_config
            mock_get_config.return_value = mock_config
            
            manager = SpacingManager(mock_dockwidget)
            manager.apply_layout_spacing()
            
            mock_dockwidget.verticalLayout_main_content.setSpacing.assert_called_with(8)
    
    def test_apply_layout_spacing_sets_exploring_spacing(self, mock_dockwidget, mock_ui_config):
        """Apply layout spacing should set spacing on exploring layouts."""
        from ui.layout.spacing_manager import SpacingManager
        
        with patch('ui.layout.spacing_manager.SpacingManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = mock_ui_config
            mock_get_config.return_value = mock_config
            
            manager = SpacingManager(mock_dockwidget)
            manager.apply_layout_spacing()
            
            mock_dockwidget.verticalLayout_exploring_single_selection.setSpacing.assert_called()
            mock_dockwidget.verticalLayout_exploring_multiple_selection.setSpacing.assert_called()
    
    def test_apply_layout_spacing_sets_filtering_spacing(self, mock_dockwidget, mock_ui_config):
        """Apply layout spacing should set spacing on filtering layouts."""
        from ui.layout.spacing_manager import SpacingManager
        
        with patch('ui.layout.spacing_manager.SpacingManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = mock_ui_config
            mock_get_config.return_value = mock_config
            
            manager = SpacingManager(mock_dockwidget)
            manager.apply_layout_spacing()
            
            mock_dockwidget.verticalLayout_filtering_keys.setSpacing.assert_called()
            mock_dockwidget.verticalLayout_filtering_values.setSpacing.assert_called()
    
    def test_apply_layout_spacing_applies_margins(self, mock_dockwidget, mock_ui_config):
        """Apply layout spacing should set margins on groupbox layouts."""
        from ui.layout.spacing_manager import SpacingManager
        
        with patch('ui.layout.spacing_manager.SpacingManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = mock_ui_config
            mock_get_config.return_value = mock_config
            
            manager = SpacingManager(mock_dockwidget)
            manager.apply_layout_spacing()
            
            mock_dockwidget.gridLayout_exploring_single_content.setContentsMargins.assert_called_with(8, 8, 8, 10)
    
    def test_adjust_row_spacing_sets_layout_spacing(self, mock_dockwidget, mock_ui_config):
        """Adjust row spacing should set spacing on value layouts."""
        from ui.layout.spacing_manager import SpacingManager
        
        # Mock the layout to return items
        mock_dockwidget.verticalLayout_filtering_values.count.return_value = 0
        mock_dockwidget.verticalLayout_exporting_values.count.return_value = 0
        
        with patch('ui.layout.spacing_manager.SpacingManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = mock_ui_config
            mock_config._active_profile = 'NORMAL'
            mock_get_config.return_value = mock_config
            
            with patch('ui.config.DisplayProfile') as mock_profile:
                mock_profile.COMPACT = 'COMPACT'
                
                with patch('ui.elements.get_spacer_size', return_value=4):
                    manager = SpacingManager(mock_dockwidget)
                    manager.adjust_row_spacing()
                    
                    mock_dockwidget.verticalLayout_filtering_values.setSpacing.assert_called()
                    mock_dockwidget.verticalLayout_exporting_values.setSpacing.assert_called()
    
    def test_teardown_resets_initialized(self, mock_dockwidget):
        """Teardown should reset initialized flag."""
        from ui.layout.spacing_manager import SpacingManager
        
        manager = SpacingManager(mock_dockwidget)
        manager._initialized = True
        
        manager.teardown()
        
        assert not manager.is_initialized


class TestSpacingManagerSpacerHarmonization:
    """Tests for spacer harmonization functionality."""
    
    @pytest.fixture
    def mock_dockwidget_with_spacers(self):
        """Create mock dockwidget with nested layouts containing spacers."""
        dockwidget = Mock()
        
        # Create mock spacer items without spec= (QGIS is mocked)
        mock_spacer1 = MagicMock()
        mock_spacer1.sizePolicy.return_value.horizontalPolicy.return_value = 1
        mock_spacer1.sizePolicy.return_value.verticalPolicy.return_value = 1
        
        mock_spacer2 = MagicMock()
        mock_spacer2.sizePolicy.return_value.horizontalPolicy.return_value = 1
        mock_spacer2.sizePolicy.return_value.verticalPolicy.return_value = 1
        
        # Create nested layout with spacers
        mock_nested_layout = Mock()
        mock_nested_layout.count.return_value = 2
        mock_nested_layout.itemAt.side_effect = [mock_spacer1, mock_spacer2]
        
        mock_layout_item = Mock()
        mock_layout_item.layout.return_value = mock_nested_layout
        
        mock_outer_layout = Mock()
        mock_outer_layout.count.return_value = 1
        mock_outer_layout.itemAt.return_value = mock_layout_item
        
        # Set up widget keys
        mock_widget = Mock()
        mock_widget.layout.return_value = mock_outer_layout
        
        dockwidget.widget_exploring_keys = mock_widget
        dockwidget.widget_filtering_keys = mock_widget
        dockwidget.widget_exporting_keys = mock_widget
        
        return dockwidget, [mock_spacer1, mock_spacer2]
    
    @pytest.mark.skip(reason="Requires real QGIS environment for isinstance() check on QSpacerItem")
    def test_harmonize_spacers_changes_spacer_sizes(self, mock_dockwidget_with_spacers):
        """Harmonize spacers should change spacer sizes."""
        from ui.layout.spacing_manager import SpacingManager
        from qgis.PyQt.QtWidgets import QSpacerItem
        
        dockwidget, mock_spacers = mock_dockwidget_with_spacers
        
        with patch('ui.layout.spacing_manager.SpacingManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = Mock(return_value=None)
            mock_config._active_profile = 'NORMAL'
            mock_get_config.return_value = mock_config
            
            with patch('ui.config.DisplayProfile') as mock_profile:
                mock_profile.COMPACT = 'COMPACT'
                
                with patch('ui.elements.get_spacer_size', return_value=6):
                    manager = SpacingManager(dockwidget)
                    manager.harmonize_spacers()
                    
                    # Spacers should have had changeSize called
                    for spacer in mock_spacers:
                        spacer.changeSize.assert_called()
