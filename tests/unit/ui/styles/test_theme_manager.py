"""
Tests for ThemeManager.

Story: MIG-066
Phase: 6 - God Class DockWidget Migration

Note: QGIS mocks are configured in conftest.py to be shared across all style tests.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))

# QGIS mocks are configured in conftest.py - do not reconfigure here


class TestThemeManager:
    """Tests for ThemeManager class."""
    
    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        dockwidget.setStyleSheet = Mock()
        return dockwidget
    
    def test_creation(self, mock_dockwidget):
        """Should create manager with dockwidget reference."""
        from ui.styles.theme_manager import ThemeManager
        
        manager = ThemeManager(mock_dockwidget)
        
        assert manager.dockwidget is mock_dockwidget
        assert not manager.is_initialized
        assert manager.current_theme == 'default'
    
    def test_setup_initializes_manager(self, mock_dockwidget):
        """Setup should initialize the manager."""
        from ui.styles.theme_manager import ThemeManager
        
        manager = ThemeManager(mock_dockwidget)
        manager.setup()
        
        assert manager.is_initialized
    
    def test_set_theme_changes_theme(self, mock_dockwidget):
        """set_theme should change current theme."""
        from ui.styles.theme_manager import ThemeManager
        
        manager = ThemeManager(mock_dockwidget)
        manager.setup()
        
        manager.set_theme('dark')
        
        assert manager.current_theme == 'dark'
        assert manager.is_dark_mode
    
    def test_set_theme_unknown_falls_back(self, mock_dockwidget):
        """set_theme with unknown theme should fall back to default."""
        from ui.styles.theme_manager import ThemeManager
        
        manager = ThemeManager(mock_dockwidget)
        manager.setup()
        
        manager.set_theme('nonexistent_theme')
        
        assert manager.current_theme == 'default'
    
    def test_set_theme_auto_detects(self, mock_dockwidget):
        """set_theme('auto') should detect system theme."""
        from ui.styles.theme_manager import ThemeManager
        
        manager = ThemeManager(mock_dockwidget)
        manager.setup()
        
        with patch.object(manager, 'detect_system_theme', return_value='dark'):
            manager.set_theme('auto')
        
        assert manager.current_theme == 'dark'
    
    def test_detect_system_theme_dark(self, mock_dockwidget):
        """detect_system_theme should return 'dark' for dark palette."""
        from ui.styles.theme_manager import ThemeManager
        
        manager = ThemeManager(mock_dockwidget)
        
        # Mock returns low luminance colors (dark)
        result = manager.detect_system_theme()
        
        assert result == 'dark'
    
    def test_detect_system_theme_light(self, mock_dockwidget):
        """detect_system_theme should return 'default' for light palette."""
        from ui.styles.theme_manager import ThemeManager
        
        # Configure palette for light mode
        _bg_color_mock.red.return_value = 240
        _bg_color_mock.green.return_value = 240
        _bg_color_mock.blue.return_value = 240
        
        manager = ThemeManager(mock_dockwidget)
        result = manager.detect_system_theme()
        
        # Restore dark mode config for other tests
        _bg_color_mock.red.return_value = 30
        _bg_color_mock.green.return_value = 30
        _bg_color_mock.blue.return_value = 30
        
        assert result == 'default'
    
    def test_get_color_returns_theme_color(self, mock_dockwidget):
        """get_color should return color value for current theme."""
        from ui.styles.theme_manager import ThemeManager
        
        manager = ThemeManager(mock_dockwidget)
        manager._current_theme = 'default'
        
        color = manager.get_color('color_accent')
        
        assert color == '#1565C0'
    
    def test_get_color_unknown_returns_empty(self, mock_dockwidget):
        """get_color with unknown key should return empty string."""
        from ui.styles.theme_manager import ThemeManager
        
        manager = ThemeManager(mock_dockwidget)
        
        color = manager.get_color('nonexistent_color')
        
        assert color == ''
    
    def test_get_colors_returns_all_colors(self, mock_dockwidget):
        """get_colors should return all colors for current theme."""
        from ui.styles.theme_manager import ThemeManager
        
        manager = ThemeManager(mock_dockwidget)
        manager._current_theme = 'dark'
        
        colors = manager.get_colors()
        
        assert 'color_accent' in colors
        assert 'color_bg_0' in colors
        assert colors['color_bg_0'] == '#1E1E1E'
    
    def test_get_available_themes(self, mock_dockwidget):
        """get_available_themes should return all theme names."""
        from ui.styles.theme_manager import ThemeManager
        
        manager = ThemeManager(mock_dockwidget)
        
        themes = manager.get_available_themes()
        
        assert 'default' in themes
        assert 'dark' in themes
        assert 'light' in themes
    
    def test_clear_cache(self, mock_dockwidget):
        """clear_cache should empty the styles cache."""
        from ui.styles.theme_manager import ThemeManager
        
        manager = ThemeManager(mock_dockwidget)
        manager._styles_cache['test'] = 'cached_value'
        
        manager.clear_cache()
        
        assert 'test' not in manager._styles_cache
    
    def test_teardown_clears_cache(self, mock_dockwidget):
        """teardown should clear cache and reset initialized."""
        from ui.styles.theme_manager import ThemeManager
        
        manager = ThemeManager(mock_dockwidget)
        manager.setup()
        manager._styles_cache['test'] = 'value'
        
        manager.teardown()
        
        assert not manager.is_initialized
        assert len(manager._styles_cache) == 0
    
    def test_on_theme_changed_updates_theme(self, mock_dockwidget):
        """on_theme_changed should update to new theme."""
        from ui.styles.theme_manager import ThemeManager
        
        manager = ThemeManager(mock_dockwidget)
        manager.setup()
        
        manager.on_theme_changed('dark')
        
        assert manager.current_theme == 'dark'
    
    def test_color_schemes_have_required_keys(self, mock_dockwidget):
        """All color schemes should have required color keys."""
        from ui.styles.theme_manager import ThemeManager
        
        required_keys = [
            'color_bg_0', 'color_1', 'color_2', 'color_3',
            'color_font_0', 'color_font_1', 'color_font_2',
            'color_accent', 'color_accent_hover', 'color_accent_pressed'
        ]
        
        for theme_name, colors in ThemeManager.COLOR_SCHEMES.items():
            for key in required_keys:
                assert key in colors, f"Theme '{theme_name}' missing '{key}'"
