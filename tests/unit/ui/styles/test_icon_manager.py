"""
Tests for IconManager.

Story: MIG-067
Phase: 6 - God Class DockWidget Migration

Note: QGIS mocks are configured in conftest.py to be shared across all style tests.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))

# QGIS mocks are configured in conftest.py - do not reconfigure here

# Additional mocks specific to IconManager
sys.modules['ui.styles'] = MagicMock()


class TestIconManager:
    """Tests for IconManager class."""
    
    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.findChildren = Mock(return_value=[])
        return dockwidget
    
    def test_creation(self, mock_dockwidget):
        """Should create manager with dockwidget reference."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        
        assert manager.dockwidget is mock_dockwidget
        assert not manager.is_initialized
        assert not manager.is_dark_mode
    
    def test_setup_initializes_manager(self, mock_dockwidget):
        """Setup should initialize the manager."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        manager.setup()
        
        assert manager.is_initialized
    
    def test_is_dark_mode_default_false(self, mock_dockwidget):
        """is_dark_mode should be False for default theme."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        manager._current_theme = 'default'
        
        assert not manager.is_dark_mode
    
    def test_is_dark_mode_true_for_dark(self, mock_dockwidget):
        """is_dark_mode should be True for dark theme."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        manager._current_theme = 'dark'
        
        assert manager.is_dark_mode
    
    def test_get_icon_returns_qicon(self, mock_dockwidget):
        """get_icon should return a QIcon."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        manager._icons_dir = str(plugin_path / 'icons')
        
        # Create a temp icon file for testing
        icon_path = plugin_path / 'icons' / 'test_icon.png'
        
        with patch('os.path.exists', return_value=False):
            icon = manager.get_icon('test_icon.png')
            
            # Should return empty QIcon for non-existent file
            assert icon is not None
    
    def test_get_icon_excluded_returns_original(self, mock_dockwidget):
        """get_icon should return original for excluded icons."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        manager._current_theme = 'dark'
        
        # logo.png is in EXCLUDE_FROM_INVERSION
        with patch('os.path.exists', return_value=True):
            with patch.object(manager, '_resolve_icon_path', return_value='/path/to/logo.png'):
                icon = manager.get_icon('logo.png')
                
                # Should not be inverted
                assert icon is not None
    
    def test_on_theme_changed_updates_theme(self, mock_dockwidget):
        """on_theme_changed should update theme and clear cache."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        manager.setup()
        manager._icon_cache['test'] = Mock()
        
        manager.on_theme_changed('dark')
        
        assert manager._current_theme == 'dark'
        assert len(manager._icon_cache) == 0
    
    def test_clear_cache(self, mock_dockwidget):
        """clear_cache should empty icon cache."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        manager._icon_cache['key1'] = Mock()
        manager._icon_cache['key2'] = Mock()
        
        manager.clear_cache()
        
        assert len(manager._icon_cache) == 0
    
    def test_teardown_clears_cache(self, mock_dockwidget):
        """teardown should clear cache and reset initialized."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        manager.setup()
        manager._icon_cache['test'] = Mock()
        
        manager.teardown()
        
        assert not manager.is_initialized
        assert len(manager._icon_cache) == 0
    
    def test_set_button_icon_stores_property(self, mock_dockwidget):
        """set_button_icon should store icon_name property."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        manager.setup()
        
        mock_button = Mock()
        mock_button.icon.return_value.isNull.return_value = False
        
        with patch.object(manager, 'get_icon') as mock_get_icon:
            mock_icon = Mock()
            mock_icon.isNull.return_value = False
            mock_get_icon.return_value = mock_icon
            
            manager.set_button_icon(mock_button, 'filter.png')
            
            mock_button.setProperty.assert_called_with('icon_name', 'filter.png')
    
    def test_refresh_all_icons_updates_buttons(self, mock_dockwidget):
        """refresh_all_icons should update buttons with icon_name property."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        manager.setup()
        
        # Create mock buttons
        mock_button1 = Mock()
        mock_button1.property.return_value = 'filter.png'
        mock_button2 = Mock()
        mock_button2.property.return_value = 'export.png'
        mock_button3 = Mock()
        mock_button3.property.return_value = None  # No icon_name
        
        mock_dockwidget.findChildren.return_value = [mock_button1, mock_button2, mock_button3]
        
        with patch.object(manager, 'get_icon') as mock_get_icon:
            mock_icon = Mock()
            mock_icon.isNull.return_value = False
            mock_get_icon.return_value = mock_icon
            
            count = manager.refresh_all_icons()
            
            assert count == 2
            assert mock_button1.setIcon.called
            assert mock_button2.setIcon.called
            assert not mock_button3.setIcon.called
    
    def test_variant_icons_mapping(self, mock_dockwidget):
        """VARIANT_ICONS should map base names to black/white variants."""
        from ui.styles.icon_manager import IconManager
        
        assert 'folder' in IconManager.VARIANT_ICONS
        assert IconManager.VARIANT_ICONS['folder'] == ('folder_black.png', 'folder_white.png')
    
    def test_force_invert_icons_contains_expected(self, mock_dockwidget):
        """FORCE_INVERT_ICONS should contain expected icons."""
        from ui.styles.icon_manager import IconManager
        
        assert 'filter.png' in IconManager.FORCE_INVERT_ICONS
        assert 'undo.png' in IconManager.FORCE_INVERT_ICONS
        assert 'export.png' in IconManager.FORCE_INVERT_ICONS
    
    def test_exclude_from_inversion_contains_logos(self, mock_dockwidget):
        """EXCLUDE_FROM_INVERSION should contain logo icons."""
        from ui.styles.icon_manager import IconManager
        
        assert 'logo.png' in IconManager.EXCLUDE_FROM_INVERSION
        assert 'icon.png' in IconManager.EXCLUDE_FROM_INVERSION


class TestIconManagerWhiteVariant:
    """Tests for white variant resolution."""
    
    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        return dockwidget
    
    def test_get_white_variant_from_black(self, mock_dockwidget):
        """Should find white variant for _black icons."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        
        result = manager._get_white_variant_path('/icons/folder_black.png')
        
        assert result == '/icons/folder_white.png'
    
    def test_get_white_variant_from_variant_mapping(self, mock_dockwidget):
        """Should find white variant from _black suffix replacement."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        
        # _black suffix is replaced with _white
        result = manager._get_white_variant_path('/icons/folder_black.png')
        
        assert result == '/icons/folder_white.png'
    
    def test_get_white_variant_not_found(self, mock_dockwidget):
        """Should return None when no white variant exists."""
        from ui.styles.icon_manager import IconManager
        
        manager = IconManager(mock_dockwidget)
        
        with patch('os.path.exists', return_value=False):
            result = manager._get_white_variant_path('/icons/random_icon.png')
        
        assert result is None
