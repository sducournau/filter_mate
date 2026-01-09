"""
Tests for ButtonStyler.

Story: MIG-068
Phase: 6 - God Class DockWidget Migration

Note: QGIS mocks are configured in conftest.py to be shared across all style tests.
ButtonStyler is loaded directly via importlib to avoid importing ThemeManager
which causes metaclass conflicts even with mocked QObject.
"""

import pytest
from unittest.mock import Mock, MagicMock
import sys
from pathlib import Path
import types
import importlib.util
from abc import ABC, abstractmethod

# Add plugin path for imports
plugin_path = Path(__file__).parents[4]
if str(plugin_path) not in sys.path:
    sys.path.insert(0, str(plugin_path))

# IMPORTANT: Mocks are configured in conftest.py - do not reconfigure here
# We only need to load ButtonStyler directly to avoid ThemeManager import chain


# Create a real StylerBase class that will work with ButtonStyler
class StylerBase(ABC):
    """Base class for style managers."""
    
    def __init__(self, dockwidget):
        self._dockwidget = dockwidget
        self._initialized = False
    
    @property
    def dockwidget(self):
        return self._dockwidget
    
    @property
    def is_initialized(self):
        return self._initialized
    
    def get_plugin_dir(self):
        """Get the plugin directory path."""
        if hasattr(self._dockwidget, 'plugin_dir'):
            return self._dockwidget.plugin_dir
        return None
    
    @abstractmethod
    def setup(self):
        """Set up the styler."""
        pass
    
    @abstractmethod
    def apply(self):
        """Apply styling."""
        pass
    
    def teardown(self):
        """Clean up resources."""
        self._initialized = False
    
    @abstractmethod
    def on_theme_changed(self, theme: str):
        """Handle theme change."""
        pass


# Create a module for base_styler
_base_styler_module = types.ModuleType('ui.styles.base_styler')
_base_styler_module.StylerBase = StylerBase

# Save original modules to restore later
_original_base_styler = sys.modules.get('ui.styles.base_styler')
_original_button_styler = sys.modules.get('ui.styles.button_styler')

# Pre-populate sys.modules to prevent loading real modules
sys.modules['ui.styles.base_styler'] = _base_styler_module

# Now load button_styler directly, bypassing ui/styles/__init__.py
# This avoids the chain import that loads ThemeManager which causes metaclass conflict
spec = importlib.util.spec_from_file_location(
    "ui.styles.button_styler", 
    str(plugin_path / "ui" / "styles" / "button_styler.py"),
    submodule_search_locations=[]
)
button_styler_module = importlib.util.module_from_spec(spec)
sys.modules['ui.styles.button_styler'] = button_styler_module
spec.loader.exec_module(button_styler_module)
ButtonStyler = button_styler_module.ButtonStyler


def _cleanup_modules():
    """Restore original modules after tests."""
    if _original_base_styler is not None:
        sys.modules['ui.styles.base_styler'] = _original_base_styler
    elif 'ui.styles.base_styler' in sys.modules:
        del sys.modules['ui.styles.base_styler']
    
    if _original_button_styler is not None:
        sys.modules['ui.styles.button_styler'] = _original_button_styler
    elif 'ui.styles.button_styler' in sys.modules:
        del sys.modules['ui.styles.button_styler']


# Register cleanup to run at module exit
import atexit
atexit.register(_cleanup_modules)
class TestButtonStyler:
    """Tests for ButtonStyler class."""
    
    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget with buttons."""
        dockwidget = Mock()
        dockwidget.plugin_dir = str(plugin_path)
        
        # Create mock buttons
        dockwidget.btn_filtering = Mock()
        dockwidget.btn_filtering.objectName.return_value = 'btn_filtering'
        dockwidget.btn_filtering.isCheckable.return_value = False
        dockwidget.btn_filtering.isChecked.return_value = False
        dockwidget.btn_filtering.isEnabled.return_value = True
        
        dockwidget.btn_exploring = Mock()
        dockwidget.btn_exploring.objectName.return_value = 'btn_exploring'
        dockwidget.btn_exploring.isCheckable.return_value = False
        
        dockwidget.btn_exporting = Mock()
        dockwidget.btn_exporting.objectName.return_value = 'btn_exporting'
        dockwidget.btn_exporting.isCheckable.return_value = False
        
        # Mock findChildren to return empty by default
        dockwidget.findChildren.return_value = []
        
        return dockwidget
    
    def test_creation(self, mock_dockwidget):
        """Should create styler with dockwidget reference."""
        styler = ButtonStyler(mock_dockwidget)
        
        assert styler.dockwidget is mock_dockwidget
        assert not styler.is_initialized
        assert styler._styled_buttons == []
        assert styler._current_theme == 'default'
    
    def test_setup_initializes_styler(self, mock_dockwidget):
        """Setup should initialize the styler."""
        styler = ButtonStyler(mock_dockwidget)
        styler.setup()
        
        assert styler.is_initialized
    
    def test_apply_calls_all_methods(self, mock_dockwidget):
        """Apply should call all styling methods."""
        styler = ButtonStyler(mock_dockwidget)
        
        # Mock the internal methods
        styler._configure_pushbuttons = Mock()
        styler._harmonize_checkable_pushbuttons = Mock()
        styler._apply_button_styles = Mock()
        styler._update_button_states = Mock()
        
        styler.apply()
        
        styler._configure_pushbuttons.assert_called_once()
        styler._harmonize_checkable_pushbuttons.assert_called_once()
        styler._apply_button_styles.assert_called_once()
        styler._update_button_states.assert_called_once()
    
    def test_is_dark_theme_default(self, mock_dockwidget):
        """is_dark_theme should return False for default theme."""
        styler = ButtonStyler(mock_dockwidget)
        styler._current_theme = 'default'
        
        assert not styler.is_dark_theme()
    
    def test_is_dark_theme_dark(self, mock_dockwidget):
        """is_dark_theme should return True for dark theme."""
        styler = ButtonStyler(mock_dockwidget)
        styler._current_theme = 'dark'
        
        assert styler.is_dark_theme()
    
    def test_on_theme_changed_updates_theme(self, mock_dockwidget):
        """on_theme_changed should update theme and reapply."""
        styler = ButtonStyler(mock_dockwidget)
        styler.apply = Mock()
        
        styler.on_theme_changed('dark')
        
        assert styler._current_theme == 'dark'
        styler.apply.assert_called_once()
    
    def test_style_action_buttons(self, mock_dockwidget):
        """style_action_buttons should style all available action buttons."""
        styler = ButtonStyler(mock_dockwidget)
        styler._apply_action_button_style = Mock()
        
        styler.style_action_buttons()
        
        # Should style all action buttons found (10 because Mock returns attribute for all names)
        assert styler._apply_action_button_style.call_count >= 3
    
    def test_action_button_height_normal_profile(self, mock_dockwidget):
        """Action button height should be 36 for normal profile."""
        styler = ButtonStyler(mock_dockwidget)
        styler._profile = 'normal'
        
        button = mock_dockwidget.btn_filtering
        styler._apply_action_button_style(button)
        
        button.setMinimumHeight.assert_called_with(36)
    
    def test_action_button_height_compact_profile(self, mock_dockwidget):
        """Action button height should be 28 for compact profile."""
        styler = ButtonStyler(mock_dockwidget)
        styler._profile = 'compact'
        styler._ui_config = None  # Force use of _profile
        
        # Mock _get_profile to return compact
        styler._get_profile = Mock(return_value='compact')
        
        button = mock_dockwidget.btn_filtering
        styler._apply_action_button_style(button)
        
        button.setMinimumHeight.assert_called_with(28)
    
    def test_dark_theme_style_applied(self, mock_dockwidget):
        """Dark theme style should be applied for dark theme."""
        styler = ButtonStyler(mock_dockwidget)
        styler._current_theme = 'dark'
        
        button = mock_dockwidget.btn_filtering
        styler._apply_action_button_style(button)
        
        call_args = button.setStyleSheet.call_args[0][0]
        assert '#3d3d3d' in call_args
    
    def test_light_theme_style_applied(self, mock_dockwidget):
        """Light theme style should be applied for light/default theme."""
        styler = ButtonStyler(mock_dockwidget)
        styler._current_theme = 'default'
        
        button = mock_dockwidget.btn_filtering
        styler._apply_action_button_style(button)
        
        call_args = button.setStyleSheet.call_args[0][0]
        assert '#f8f9fa' in call_args
    
    def test_teardown_clears_buttons(self, mock_dockwidget):
        """teardown should clear styled buttons list."""
        styler = ButtonStyler(mock_dockwidget)
        styler._styled_buttons = [Mock(), Mock()]
        
        styler.teardown()
        
        assert styler._styled_buttons == []
        assert not styler.is_initialized
    
    def test_get_action_buttons(self, mock_dockwidget):
        """_get_action_buttons should return action buttons."""
        styler = ButtonStyler(mock_dockwidget)
        
        buttons = styler._get_action_buttons()
        
        # Should return at least the 3 main buttons we configured
        assert len(buttons) >= 3
        assert mock_dockwidget.btn_filtering in buttons
    
    def test_is_action_button(self, mock_dockwidget):
        """_is_action_button should identify action buttons."""
        styler = ButtonStyler(mock_dockwidget)
        
        assert styler._is_action_button(mock_dockwidget.btn_filtering)
    
    def test_button_heights_has_profiles(self, mock_dockwidget):
        """BUTTON_HEIGHTS should have compact and normal profiles."""
        assert 'compact' in ButtonStyler.BUTTON_HEIGHTS
        assert 'normal' in ButtonStyler.BUTTON_HEIGHTS
    
    def test_icon_sizes_has_profiles(self, mock_dockwidget):
        """ICON_SIZES should have compact and normal profiles."""
        assert 'compact' in ButtonStyler.ICON_SIZES
        assert 'normal' in ButtonStyler.ICON_SIZES


class TestButtonStylerCSS:
    """Test CSS generation methods."""
    
    @pytest.fixture
    def styler(self):
        """Create ButtonStyler instance."""
        from ui.styles.button_styler import ButtonStyler
        return ButtonStyler(Mock())
    
    def test_dark_action_style_includes_hover(self, styler):
        """Dark action style should include hover state."""
        css = styler._get_dark_action_button_style()
        assert ':hover' in css
    
    def test_dark_action_style_includes_checked(self, styler):
        """Dark action style should include checked state."""
        css = styler._get_dark_action_button_style()
        assert ':checked' in css
    
    def test_dark_action_style_includes_disabled(self, styler):
        """Dark action style should include disabled state."""
        css = styler._get_dark_action_button_style()
        assert ':disabled' in css
    
    def test_light_action_style_includes_hover(self, styler):
        """Light action style should include hover state."""
        css = styler._get_light_action_button_style()
        assert ':hover' in css
    
    def test_light_action_style_includes_pressed(self, styler):
        """Light action style should include pressed state."""
        css = styler._get_light_action_button_style()
        assert ':pressed' in css
    
    def test_checkable_style_dark(self, styler):
        """Checkable button style for dark theme."""
        styler._current_theme = 'dark'
        css = styler._get_checkable_button_style()
        
        assert ':checked' in css
        assert '#264f78' in css  # Dark checked background
    
    def test_checkable_style_light(self, styler):
        """Checkable button style for light theme."""
        styler._current_theme = 'default'
        css = styler._get_checkable_button_style()
        
        assert ':checked' in css
        assert '#cce5ff' in css  # Light checked background
    
    def test_disabled_style_dark(self, styler):
        """Disabled button style for dark theme."""
        styler._current_theme = 'dark'
        css = styler._get_disabled_style()
        
        assert ':disabled' in css
        assert '#2d2d2d' in css
    
    def test_disabled_style_light(self, styler):
        """Disabled button style for light theme."""
        styler._current_theme = 'default'
        css = styler._get_disabled_style()
        
        assert ':disabled' in css
        assert '#e9ecef' in css


class TestButtonStylerConfiguration:
    """Test button configuration methods."""
    
    @pytest.fixture
    def mock_dockwidget(self):
        """Create mock dockwidget."""
        dockwidget = Mock()
        return dockwidget
    
    def test_configure_pushbuttons_sets_cursor(self, mock_dockwidget):
        """_configure_pushbuttons should set pointing hand cursor."""
        from ui.styles.button_styler import ButtonStyler
        
        mock_button = Mock()
        mock_button.objectName.return_value = 'test_button'
        mock_button.isCheckable.return_value = False
        mock_dockwidget.findChildren.return_value = [mock_button]
        
        styler = ButtonStyler(mock_dockwidget)
        styler._configure_pushbuttons()
        
        mock_button.setCursor.assert_called()
    
    def test_harmonize_checkable_tracks_buttons(self, mock_dockwidget):
        """_harmonize_checkable_pushbuttons should track checkable buttons."""
        from ui.styles.button_styler import ButtonStyler
        
        mock_button = Mock()
        mock_button.isCheckable.return_value = True
        mock_button.isChecked.return_value = False
        mock_dockwidget.findChildren.return_value = [mock_button]
        
        styler = ButtonStyler(mock_dockwidget)
        styler._harmonize_checkable_pushbuttons()
        
        assert mock_button in styler._styled_buttons
