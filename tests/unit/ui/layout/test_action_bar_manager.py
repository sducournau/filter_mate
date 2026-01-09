"""
Tests for ActionBarManager.

Story: MIG-064
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
_qgis_pyqt_mock.QtCore.QSize = Mock
_qgis_pyqt_mock.QtCore.Qt = Mock()
_qgis_pyqt_mock.QtCore.Qt.AlignCenter = 0x84

# Patch QGIS modules in sys.modules before imports
sys.modules['qgis'] = _qgis_mock
sys.modules['qgis.PyQt'] = _qgis_pyqt_mock
sys.modules['qgis.PyQt.QtWidgets'] = _qgis_pyqt_mock.QtWidgets
sys.modules['qgis.PyQt.QtCore'] = _qgis_pyqt_mock.QtCore
sys.modules['qgis.gui'] = _qgis_gui_mock
sys.modules['qgis.core'] = MagicMock()

# Mock modules.ui_config before import
sys.modules['modules'] = MagicMock()
sys.modules['modules.ui_config'] = MagicMock()
sys.modules['modules.ui_elements'] = MagicMock()


class TestActionBarManager:
    """Tests for ActionBarManager class."""
    
    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget with required attributes."""
        dockwidget = Mock()
        dockwidget.dockWidgetContents = Mock()
        
        # Frame actions
        dockwidget.frame_actions = Mock()
        dockwidget.frame_actions.layout.return_value = Mock()
        dockwidget.frame_actions.show = Mock()
        
        # Action buttons
        dockwidget.pushButton_action_filter = Mock()
        dockwidget.pushButton_action_undo_filter = Mock()
        dockwidget.pushButton_action_redo_filter = Mock()
        dockwidget.pushButton_action_unfilter = Mock()
        dockwidget.pushButton_action_export = Mock()
        dockwidget.pushButton_action_about = Mock()
        
        # Layouts
        dockwidget.horizontalLayout_actions_container = Mock()
        dockwidget.horizontalLayout_actions_container.indexOf.return_value = -1
        dockwidget.verticalLayout_main = Mock()
        dockwidget.verticalLayout_8 = Mock()
        
        # Main splitter
        dockwidget.main_splitter = Mock()
        
        # Frame header
        dockwidget.frame_header = Mock()
        
        # Config data
        dockwidget.CONFIG_DATA = {
            'APP': {
                'DOCKWIDGET': {
                    'ACTION_BAR_POSITION': {'value': 'bottom'},
                    'ACTION_BAR_VERTICAL_ALIGNMENT': {'value': 'top'}
                }
            }
        }
        
        return dockwidget
    
    def test_creation(self, mock_dockwidget):
        """Should create manager with dockwidget reference."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        manager = ActionBarManager(mock_dockwidget)
        
        assert manager.dockwidget is mock_dockwidget
        assert not manager.is_initialized
        assert manager.get_position() == 'bottom'
    
    def test_valid_positions(self):
        """Should define valid positions."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        assert ActionBarManager.VALID_POSITIONS == ('top', 'bottom', 'left', 'right')
    
    def test_set_position_valid(self, mock_dockwidget):
        """Should accept valid positions."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        manager = ActionBarManager(mock_dockwidget)
        
        # Patch apply_position to avoid side effects
        with patch.object(manager, 'apply_position'):
            for position in ('top', 'bottom', 'left', 'right'):
                manager.set_position(position)
                assert manager.get_position() == position
    
    def test_set_position_invalid(self, mock_dockwidget):
        """Should reject invalid positions."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        manager = ActionBarManager(mock_dockwidget)
        
        with pytest.raises(ValueError) as exc_info:
            manager.set_position('invalid')
        
        assert 'Invalid position' in str(exc_info.value)
    
    def test_setup_initializes_manager(self, mock_dockwidget):
        """Setup should initialize the manager."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        manager = ActionBarManager(mock_dockwidget)
        manager.setup()
        
        assert manager.is_initialized
    
    def test_setup_reads_position_from_config(self, mock_dockwidget):
        """Setup should read position from config."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        mock_dockwidget.CONFIG_DATA['APP']['DOCKWIDGET']['ACTION_BAR_POSITION'] = {'value': 'top'}
        
        manager = ActionBarManager(mock_dockwidget)
        manager.setup()
        
        assert manager.get_position() == 'top'
    
    def test_get_action_buttons(self, mock_dockwidget):
        """Should return list of action buttons."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        manager = ActionBarManager(mock_dockwidget)
        buttons = manager._get_action_buttons()
        
        assert len(buttons) == 6
        assert mock_dockwidget.pushButton_action_filter in buttons
        assert mock_dockwidget.pushButton_action_export in buttons
    
    def test_clear_layout(self, mock_dockwidget):
        """Clear layout should remove all items."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        mock_layout = Mock()
        mock_layout.count.side_effect = [2, 1, 0]  # Decreasing count
        mock_layout.takeAt.return_value = Mock(widget=Mock(return_value=Mock()))
        mock_dockwidget.frame_actions.layout.return_value = mock_layout
        
        manager = ActionBarManager(mock_dockwidget)
        manager.clear_layout()
        
        assert mock_layout.takeAt.called
    
    def test_apply_size_constraints_horizontal(self, mock_dockwidget):
        """Should set horizontal constraints for top/bottom positions."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        manager = ActionBarManager(mock_dockwidget)
        manager._position = 'bottom'
        manager.apply_size_constraints()
        
        mock_dockwidget.frame_actions.setMinimumHeight.assert_called()
        mock_dockwidget.frame_actions.setMaximumHeight.assert_called()
        mock_dockwidget.frame_actions.setSizePolicy.assert_called()
    
    def test_apply_size_constraints_vertical(self, mock_dockwidget):
        """Should set vertical constraints for left/right positions."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        manager = ActionBarManager(mock_dockwidget)
        manager._position = 'left'
        manager.apply_size_constraints()
        
        mock_dockwidget.frame_actions.setMinimumWidth.assert_called()
        mock_dockwidget.frame_actions.setMaximumWidth.assert_called()
    
    def test_reposition_in_main_layout_top(self, mock_dockwidget):
        """Should insert frame at top of main layout."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        manager = ActionBarManager(mock_dockwidget)
        manager._position = 'top'
        manager.reposition_in_main_layout()
        
        mock_dockwidget.verticalLayout_main.insertWidget.assert_called_with(
            0, mock_dockwidget.frame_actions
        )
    
    def test_reposition_in_main_layout_bottom(self, mock_dockwidget):
        """Should add frame to actions container for bottom."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        manager = ActionBarManager(mock_dockwidget)
        manager._position = 'bottom'
        manager.reposition_in_main_layout()
        
        mock_dockwidget.horizontalLayout_actions_container.addWidget.assert_called_with(
            mock_dockwidget.frame_actions
        )
    
    def test_teardown_resets_initialized(self, mock_dockwidget):
        """Teardown should reset initialized flag."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        manager = ActionBarManager(mock_dockwidget)
        manager._initialized = True
        
        manager.teardown()
        
        assert not manager.is_initialized


class TestActionBarManagerSidePositions:
    """Tests for side (left/right) action bar positioning."""
    
    @pytest.fixture
    def mock_dockwidget_with_splitter(self):
        """Create mock dockwidget with splitter for side positioning."""
        dockwidget = Mock()
        dockwidget.dockWidgetContents = Mock()
        
        # Frame actions
        dockwidget.frame_actions = Mock()
        dockwidget.frame_actions.layout.return_value = None
        
        # Action buttons
        for btn in ['pushButton_action_filter', 'pushButton_action_undo_filter',
                   'pushButton_action_redo_filter', 'pushButton_action_unfilter',
                   'pushButton_action_export', 'pushButton_action_about']:
            setattr(dockwidget, btn, Mock())
        
        # Layouts
        dockwidget.horizontalLayout_actions_container = Mock()
        dockwidget.horizontalLayout_actions_container.indexOf.return_value = -1
        dockwidget.verticalLayout_main = Mock()
        dockwidget.verticalLayout_main.indexOf.return_value = 0
        dockwidget.verticalLayout_8 = Mock()
        dockwidget.verticalLayout_8.indexOf.return_value = 0
        
        # Main splitter
        dockwidget.main_splitter = Mock()
        
        # Frame header
        dockwidget.frame_header = Mock()
        
        # Config
        dockwidget.CONFIG_DATA = {
            'APP': {
                'DOCKWIDGET': {
                    'ACTION_BAR_POSITION': {'value': 'left'},
                    'ACTION_BAR_VERTICAL_ALIGNMENT': {'value': 'top'}
                }
            }
        }
        
        return dockwidget
    
    def test_adjust_header_for_left_position(self, mock_dockwidget_with_splitter):
        """Should wrap header with spacer for left position."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        manager = ActionBarManager(mock_dockwidget_with_splitter)
        manager._position = 'left'
        manager.adjust_header_for_side_position()
        
        # Header should be removed from layout
        mock_dockwidget_with_splitter.verticalLayout_8.removeWidget.assert_called()
        # New widget should be inserted
        mock_dockwidget_with_splitter.verticalLayout_8.insertWidget.assert_called()
    
    def test_restore_side_action_bar_layout(self, mock_dockwidget_with_splitter):
        """Should restore layout when switching from side position."""
        from ui.layout.action_bar_manager import ActionBarManager
        from qgis.PyQt import QtWidgets
        
        manager = ActionBarManager(mock_dockwidget_with_splitter)
        
        # Simulate active side bar
        manager._side_action_bar_active = True
        manager._side_action_wrapper = Mock()
        manager._side_action_wrapper.layout.return_value = Mock()
        manager.dockwidget._side_action_wrapper = manager._side_action_wrapper
        
        manager.restore_side_action_bar_layout()
        
        assert not manager._side_action_bar_active


class TestActionBarManagerIntegration:
    """Integration tests for ActionBarManager."""
    
    @pytest.fixture
    def mock_dockwidget_full(self):
        """Create comprehensive mock dockwidget."""
        dockwidget = Mock()
        dockwidget.dockWidgetContents = Mock()
        
        # Frame actions with layout that has items
        mock_layout = Mock()
        mock_layout.count.return_value = 0
        dockwidget.frame_actions = Mock()
        dockwidget.frame_actions.layout.return_value = mock_layout
        
        # All action buttons
        for btn in ['pushButton_action_filter', 'pushButton_action_undo_filter',
                   'pushButton_action_redo_filter', 'pushButton_action_unfilter',
                   'pushButton_action_export', 'pushButton_action_about']:
            setattr(dockwidget, btn, Mock())
        
        # Layouts
        dockwidget.horizontalLayout_actions_container = Mock()
        dockwidget.horizontalLayout_actions_container.indexOf.return_value = -1
        dockwidget.verticalLayout_main = Mock()
        dockwidget.verticalLayout_8 = Mock()
        
        dockwidget.main_splitter = Mock()
        dockwidget.frame_header = None
        
        dockwidget.CONFIG_DATA = {
            'APP': {
                'DOCKWIDGET': {
                    'ACTION_BAR_POSITION': {'value': 'bottom'},
                    'ACTION_BAR_VERTICAL_ALIGNMENT': {'value': 'top'}
                }
            }
        }
        
        return dockwidget
    
    def test_full_setup_and_position_change(self, mock_dockwidget_full):
        """Should handle full setup and position changes."""
        from ui.layout.action_bar_manager import ActionBarManager
        
        manager = ActionBarManager(mock_dockwidget_full)
        manager.setup()
        
        assert manager.is_initialized
        
        # Change position
        with patch.object(manager, 'restore_side_action_bar_layout'):
            manager.set_position('top')
        
        assert manager.get_position() == 'top'
