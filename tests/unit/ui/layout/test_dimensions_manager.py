"""
Tests for DimensionsManager.

Story: MIG-062
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


class TestDimensionsManager:
    """Tests for DimensionsManager class."""
    
    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget with required attributes."""
        dockwidget = Mock()
        # Basic size methods
        dockwidget.size.return_value = Mock(width=lambda: 400, height=lambda: 600)
        dockwidget.setMinimumSize = Mock()
        dockwidget.resize = Mock()
        
        # Frames
        dockwidget.frame_exploring = Mock()
        dockwidget.frame_toolset = Mock()
        dockwidget.frame_filtering = Mock()
        
        # Widget keys
        dockwidget.widget_exploring_keys = Mock()
        dockwidget.widget_exploring_keys.layout.return_value = Mock()
        dockwidget.widget_filtering_keys = Mock()
        dockwidget.widget_filtering_keys.layout.return_value = Mock()
        dockwidget.widget_exporting_keys = Mock()
        dockwidget.widget_exporting_keys.layout.return_value = Mock()
        
        # Layouts
        dockwidget.verticalLayout_exploring_content = Mock()
        dockwidget.verticalLayout_filtering_keys = Mock()
        dockwidget.verticalLayout_exporting_keys = Mock()
        dockwidget.verticalLayout_filtering_values = Mock()
        dockwidget.verticalLayout_exporting_values = Mock()
        dockwidget.verticalLayout_main_content = Mock()
        
        # Empty children by default
        dockwidget.findChildren = Mock(return_value=[])
        
        # Checkable buttons
        for btn_name in [
            'pushButton_exploring_identify',
            'pushButton_exploring_zoom',
            'pushButton_checkable_exploring_selecting',
            'pushButton_checkable_filtering_auto_current_layer',
            'pushButton_checkable_exporting_layers',
        ]:
            setattr(dockwidget, btn_name, Mock())
        
        return dockwidget
    
    @pytest.fixture
    def mock_ui_config(self):
        """Mock UIConfig module with typical configuration."""
        config_values = {
            ('dockwidget', 'min_width'): 350,
            ('dockwidget', 'min_height'): 400,
            ('dockwidget', 'preferred_width'): 400,
            ('dockwidget', 'preferred_height'): 600,
            ('combobox', 'height'): 24,
            ('input', 'height'): 24,
            ('groupbox', 'min_height'): 60,
            ('widget_keys', 'min_width'): 34,
            ('widget_keys', 'max_width'): 40,
            ('frame_exploring',): {'min_height': 120, 'max_height': 350, 'size_policy_h': 'Preferred', 'size_policy_v': 'Minimum'},
            ('frame_toolset',): {'min_height': 200, 'max_height': 16777215, 'size_policy_h': 'Preferred', 'size_policy_v': 'Expanding'},
            ('frame_filtering',): {'min_height': 180},
            ('widget_keys',): {'padding': 2, 'min_width': 34, 'max_width': 40},
            ('key_button',): {'min_size': 26, 'max_size': 32, 'icon_size': 16, 'spacing': 2},
            ('layout', 'spacing_frame'): 8,
            ('layout', 'spacing_content'): 6,
            ('layout', 'spacing_section'): 8,
            ('layout', 'spacing_main'): 8,
            ('layout', 'margins_frame'): {'left': 8, 'top': 8, 'right': 8, 'bottom': 10},
            ('layout', 'margins_actions'): {'left': 8, 'top': 6, 'right': 8, 'bottom': 12},
        }
        
        def get_config(*args):
            # Handle single arg (returns dict) vs multi arg (returns value)
            if len(args) == 1:
                return config_values.get((args[0],), {})
            return config_values.get(args, None)
        
        return get_config
    
    def test_creation(self, mock_dockwidget):
        """Should create manager with dockwidget reference."""
        from ui.layout.dimensions_manager import DimensionsManager
        
        manager = DimensionsManager(mock_dockwidget)
        
        assert manager.dockwidget is mock_dockwidget
        assert not manager.is_initialized
    
    def test_setup_initializes_manager(self, mock_dockwidget):
        """Setup should initialize the manager and apply dimensions."""
        from ui.layout.dimensions_manager import DimensionsManager
        
        with patch('ui.layout.dimensions_manager.DimensionsManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = Mock(return_value=None)
            mock_get_config.return_value = mock_config
            
            manager = DimensionsManager(mock_dockwidget)
            manager.setup()
            
            assert manager.is_initialized
    
    def test_apply_dockwidget_dimensions(self, mock_dockwidget, mock_ui_config):
        """Apply should set minimum size on dockwidget."""
        from ui.layout.dimensions_manager import DimensionsManager
        
        with patch('ui.layout.dimensions_manager.DimensionsManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = mock_ui_config
            mock_get_config.return_value = mock_config
            
            manager = DimensionsManager(mock_dockwidget)
            manager.apply_dockwidget_dimensions()
            
            mock_dockwidget.setMinimumSize.assert_called_once()
    
    def test_apply_widget_dimensions_calls_findchildren(self, mock_dockwidget, mock_ui_config):
        """Apply widget dimensions should use findChildren to find widgets."""
        from ui.layout.dimensions_manager import DimensionsManager
        
        with patch('ui.layout.dimensions_manager.DimensionsManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = mock_ui_config
            mock_get_config.return_value = mock_config
            
            manager = DimensionsManager(mock_dockwidget)
            manager.apply_widget_dimensions()
            
            # Should call findChildren at least once (for QComboBox, QLineEdit, etc.)
            assert mock_dockwidget.findChildren.called
    
    def test_apply_frame_dimensions_sets_frame_sizes(self, mock_dockwidget, mock_ui_config):
        """Apply frame dimensions should set min/max heights on frames."""
        from ui.layout.dimensions_manager import DimensionsManager
        
        with patch('ui.layout.dimensions_manager.DimensionsManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = mock_ui_config
            mock_get_config.return_value = mock_config
            
            manager = DimensionsManager(mock_dockwidget)
            manager.apply_frame_dimensions()
            
            # frame_exploring should have min/max height set
            mock_dockwidget.frame_exploring.setMinimumHeight.assert_called()
            mock_dockwidget.frame_exploring.setMaximumHeight.assert_called()
            mock_dockwidget.frame_exploring.setSizePolicy.assert_called()
            
            # frame_toolset should have min/max height set
            mock_dockwidget.frame_toolset.setMinimumHeight.assert_called()
            mock_dockwidget.frame_toolset.setSizePolicy.assert_called()
    
    def test_harmonize_checkable_pushbuttons(self, mock_dockwidget, mock_ui_config):
        """Harmonize should apply consistent sizing to all pushbuttons."""
        from ui.layout.dimensions_manager import DimensionsManager
        
        # Create mock pushbutton with required methods
        mock_button = MagicMock()
        mock_button.setMinimumSize = Mock()
        mock_button.setMaximumSize = Mock()
        mock_button.setIconSize = Mock()
        mock_button.setFlat = Mock()
        mock_button.setSizePolicy = Mock()
        
        mock_dockwidget.pushButton_exploring_identify = mock_button
        
        with patch('ui.layout.dimensions_manager.DimensionsManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = mock_ui_config
            mock_config.get_profile = Mock(return_value='NORMAL')
            mock_config.get_profile_name = Mock(return_value='Normal')
            mock_get_config.return_value = mock_config
            
            # Patch isinstance to return True for our mock button
            original_isinstance = __builtins__['isinstance'] if isinstance(__builtins__, dict) else getattr(__builtins__, 'isinstance')
            def mock_isinstance(obj, cls):
                if obj is mock_button:
                    return True
                return original_isinstance(obj, cls)
            
            with patch('builtins.isinstance', mock_isinstance):
                with patch('modules.ui_config.DisplayProfile'):
                    manager = DimensionsManager(mock_dockwidget)
                    manager.harmonize_checkable_pushbuttons()
                    
                    # Button should have been configured
                    mock_button.setFlat.assert_called_with(True)
    
    def test_apply_layout_spacing(self, mock_dockwidget, mock_ui_config):
        """Apply layout spacing should set spacing on layouts."""
        from ui.layout.dimensions_manager import DimensionsManager
        
        with patch('ui.layout.dimensions_manager.DimensionsManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = mock_ui_config
            mock_get_config.return_value = mock_config
            
            manager = DimensionsManager(mock_dockwidget)
            manager.apply_layout_spacing()
            
            # Main content layout should have spacing set
            mock_dockwidget.verticalLayout_main_content.setSpacing.assert_called()
    
    def test_align_key_layouts(self, mock_dockwidget, mock_ui_config):
        """Align key layouts should configure consistent spacing and margins."""
        from ui.layout.dimensions_manager import DimensionsManager
        
        with patch('ui.layout.dimensions_manager.DimensionsManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = mock_ui_config
            mock_get_config.return_value = mock_config
            
            manager = DimensionsManager(mock_dockwidget)
            manager.align_key_layouts()
            
            # Key layouts should have spacing configured
            mock_dockwidget.verticalLayout_exploring_content.setSpacing.assert_called()
            mock_dockwidget.verticalLayout_exploring_content.setContentsMargins.assert_called()
    
    def test_policy_map_contains_all_policies(self):
        """POLICY_MAP should contain all standard QSizePolicy values."""
        from ui.layout.dimensions_manager import DimensionsManager
        from qgis.PyQt.QtWidgets import QSizePolicy
        
        expected_policies = [
            'Fixed', 'Minimum', 'Maximum', 'Preferred',
            'Expanding', 'MinimumExpanding', 'Ignored'
        ]
        
        for policy_name in expected_policies:
            assert policy_name in DimensionsManager.POLICY_MAP
            assert DimensionsManager.POLICY_MAP[policy_name] == getattr(QSizePolicy, policy_name)
    
    def test_teardown_resets_initialized(self, mock_dockwidget):
        """Teardown should reset initialized flag."""
        from ui.layout.dimensions_manager import DimensionsManager
        
        manager = DimensionsManager(mock_dockwidget)
        manager._initialized = True
        
        manager.teardown()
        
        assert not manager.is_initialized


class TestDimensionsManagerIntegration:
    """Integration tests for DimensionsManager with real QGIS widgets."""
    
    @pytest.fixture
    def mock_dockwidget_with_widgets(self):
        """Create mock dockwidget with widget collections."""
        from qgis.PyQt.QtWidgets import QComboBox, QLineEdit, QSpinBox
        
        dockwidget = Mock()
        
        # Create mock widget lists (without spec= to avoid InvalidSpecError with mocked QGIS)
        mock_combos = [MagicMock() for _ in range(3)]
        mock_lineedits = [MagicMock() for _ in range(2)]
        mock_spinboxes = [MagicMock() for _ in range(2)]
        
        # Store widget types for comparison
        _QComboBox = QComboBox
        _QLineEdit = QLineEdit
        _QSpinBox = QSpinBox
        
        def find_children(widget_type):
            if widget_type is _QComboBox:
                return mock_combos
            elif widget_type is _QLineEdit:
                return mock_lineedits
            elif widget_type is _QSpinBox:
                return mock_spinboxes
            return []
        
        dockwidget.findChildren = find_children
        dockwidget.size.return_value = Mock(width=lambda: 400, height=lambda: 600)
        dockwidget.setMinimumSize = Mock()
        
        return dockwidget, mock_combos, mock_lineedits
    
    def test_apply_widget_dimensions_to_comboboxes(self, mock_dockwidget_with_widgets):
        """Should apply height to all comboboxes found."""
        from ui.layout.dimensions_manager import DimensionsManager
        
        dockwidget, mock_combos, mock_lineedits = mock_dockwidget_with_widgets
        
        with patch('ui.layout.dimensions_manager.DimensionsManager._get_ui_config') as mock_get_config:
            mock_config = Mock()
            mock_config.get_config = Mock(return_value=24)
            mock_get_config.return_value = mock_config
            
            manager = DimensionsManager(dockwidget)
            manager.apply_widget_dimensions()
            
            # Each combo should have height set
            for combo in mock_combos:
                combo.setMinimumHeight.assert_called_with(24)
                combo.setMaximumHeight.assert_called_with(24)
