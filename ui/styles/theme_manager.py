"""
Theme Manager for FilterMate.

Centralized theme management with QGIS theme synchronization.
Migrated from modules/ui_styles.py (StyleLoader class).

Story: MIG-066
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, Dict, Any
import logging
import os

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import QgsApplication

from .base_styler import StylerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class ThemeManager(StylerBase, QObject):
    """
    Centralized theme management for FilterMate.
    
    Provides:
    - Theme detection from QGIS palette
    - Theme application to widgets
    - Theme change events
    - Color scheme management
    
    Migrated methods from modules/ui_styles.py:
    - detect_qgis_theme() -> detect_system_theme()
    - set_theme() -> set_theme()
    - get_current_theme() -> current_theme property
    - load_stylesheet() -> _load_stylesheet()
    
    Signals:
        theme_changed: Emitted when theme changes, carries new theme name
    
    Example:
        manager = ThemeManager(dockwidget)
        manager.setup()
        
        # React to theme changes
        manager.theme_changed.connect(on_theme_changed)
        
        # Change theme
        manager.set_theme('dark')
    """
    
    # Signal emitted when theme changes
    theme_changed = pyqtSignal(str)
    
    # Default color schemes
    COLOR_SCHEMES = {
        'default': {
            'color_bg_0': '#EFEFEF',
            'color_1': '#FFFFFF',
            'color_2': '#D0D0D0',
            'color_bg_3': '#2196F3',
            'color_3': '#4A4A4A',
            'color_font_0': '#1A1A1A',
            'color_font_1': '#4A4A4A',
            'color_font_2': '#888888',
            'color_accent': '#1565C0',
            'color_accent_hover': '#1E88E5',
            'color_accent_pressed': '#0D47A1',
            'color_accent_light_bg': '#E3F2FD',
            'color_accent_dark': '#01579B',
            'icon_filter': 'none'
        },
        'dark': {
            'color_bg_0': '#1E1E1E',
            'color_1': '#252526',
            'color_2': '#37373D',
            'color_bg_3': '#0E639C',
            'color_3': '#CCCCCC',
            'color_font_0': '#D4D4D4',
            'color_font_1': '#9D9D9D',
            'color_font_2': '#6A6A6A',
            'color_accent': '#007ACC',
            'color_accent_hover': '#1177BB',
            'color_accent_pressed': '#005A9E',
            'color_accent_light_bg': '#264F78',
            'color_accent_dark': '#FFFFFF',
            'icon_filter': 'invert(100%)'
        },
        'light': {
            'color_bg_0': '#FFFFFF',
            'color_1': '#F8F8F8',
            'color_2': '#CCCCCC',
            'color_bg_3': '#2196F3',
            'color_3': '#333333',
            'color_font_0': '#000000',
            'color_font_1': '#333333',
            'color_font_2': '#999999',
            'color_accent': '#1976D2',
            'color_accent_hover': '#2196F3',
            'color_accent_pressed': '#0D47A1',
            'color_accent_light_bg': '#E3F2FD',
            'color_accent_dark': '#0D47A1',
            'icon_filter': 'none'
        }
    }
    
    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the ThemeManager.
        
        Args:
            dockwidget: The main FilterMate dockwidget instance
        """
        # Initialize both base classes
        StylerBase.__init__(self, dockwidget)
        QObject.__init__(self)
        
        self._current_theme: str = 'default'
        self._auto_detect: bool = True
        self._styles_cache: Dict[str, str] = {}
        self._config_data: Optional[Dict] = None
    
    @property
    def current_theme(self) -> str:
        """Get current active theme name."""
        return self._current_theme
    
    @property
    def is_dark_mode(self) -> bool:
        """Check if current theme is dark mode."""
        return self._current_theme == 'dark'
    
    def setup(self) -> None:
        """
        Initialize theme from QGIS settings or config.
        
        Auto-detects theme from QGIS if auto-detect is enabled.
        """
        # Try to load config
        self._load_config()
        
        # Detect and apply theme
        if self._auto_detect:
            detected = self.detect_system_theme()
            self._current_theme = detected
        
        self.apply()
        self._initialized = True
        logger.info(f"ThemeManager initialized with theme: {self._current_theme}")
    
    def apply(self) -> None:
        """Apply current theme to dockwidget."""
        stylesheet = self._load_stylesheet(self._current_theme)
        if stylesheet:
            self.dockwidget.setStyleSheet(stylesheet)
            logger.debug(f"Applied theme '{self._current_theme}' to dockwidget")
    
    def set_theme(self, theme: str) -> None:
        """
        Set and apply a new theme.
        
        Args:
            theme: Theme name ('light', 'dark', 'default', 'auto')
        """
        if theme == 'auto':
            theme = self.detect_system_theme()
        
        if theme not in self.COLOR_SCHEMES:
            logger.warning(f"Unknown theme '{theme}', falling back to 'default'")
            theme = 'default'
        
        if theme != self._current_theme:
            old_theme = self._current_theme
            self._current_theme = theme
            self.apply()
            self.theme_changed.emit(theme)
            logger.info(f"Theme changed from '{old_theme}' to '{theme}'")
    
    def detect_system_theme(self) -> str:
        """
        Detect current QGIS theme.
        
        Analyzes QGIS palette luminance to determine dark/light mode.
        
        Returns:
            str: 'dark' if QGIS uses dark theme, 'default' for light theme
        """
        try:
            app = QgsApplication.instance()
            if app is None:
                return 'default'
            
            palette = app.palette()
            bg_color = palette.color(palette.Window)
            
            # Calculate luminance (perceived brightness)
            luminance = (0.299 * bg_color.red() + 
                        0.587 * bg_color.green() + 
                        0.114 * bg_color.blue())
            
            if luminance < 128:
                logger.debug(f"Detected QGIS dark theme (luminance: {luminance:.0f})")
                return 'dark'
            else:
                logger.debug(f"Detected QGIS light theme (luminance: {luminance:.0f})")
                return 'default'
                
        except Exception as e:
            logger.warning(f"Could not detect QGIS theme: {e}")
            return 'default'
    
    def on_theme_changed(self, theme: str) -> None:
        """
        Handle external theme change event.
        
        Args:
            theme: New theme name
        """
        self.set_theme(theme)
    
    def get_color(self, color_key: str) -> str:
        """
        Get a color value from current theme.
        
        Args:
            color_key: Color key name (e.g., 'color_accent')
        
        Returns:
            str: Color value (hex) or empty string if not found
        """
        colors = self.COLOR_SCHEMES.get(self._current_theme, {})
        return colors.get(color_key, '')
    
    def get_colors(self) -> Dict[str, str]:
        """
        Get all colors for current theme.
        
        Returns:
            Dict of color key -> color value
        """
        return self.COLOR_SCHEMES.get(self._current_theme, {}).copy()
    
    def get_available_themes(self) -> list:
        """
        Get list of available theme names.
        
        Returns:
            List of theme names
        """
        return list(self.COLOR_SCHEMES.keys())
    
    def clear_cache(self) -> None:
        """Clear stylesheet cache."""
        self._styles_cache.clear()
        logger.debug("Theme cache cleared")
    
    def _load_config(self) -> None:
        """Load configuration from dockwidget or config file."""
        try:
            if hasattr(self.dockwidget, 'config_data'):
                self._config_data = self.dockwidget.config_data
                
                # Check for auto-detect setting
                if self._config_data:
                    active_theme = self._config_data.get('app', {}).get('active_theme', 'auto')
                    self._auto_detect = (active_theme == 'auto')
                    if not self._auto_detect:
                        self._current_theme = active_theme
        except Exception as e:
            logger.debug(f"Could not load theme config: {e}")
    
    def _load_stylesheet(self, theme: str) -> str:
        """
        Load QSS stylesheet for theme.
        
        Args:
            theme: Theme name
        
        Returns:
            Stylesheet content with colors applied
        """
        # Check cache
        if theme in self._styles_cache:
            return self._styles_cache[theme]
        
        # Get raw stylesheet
        stylesheet = self._load_raw_stylesheet(theme)
        if not stylesheet:
            return ""
        
        # Apply colors
        colors = self.COLOR_SCHEMES.get(theme, self.COLOR_SCHEMES['default'])
        for key, value in colors.items():
            stylesheet = stylesheet.replace(f'{{{key}}}', value)
        
        # Cache result
        self._styles_cache[theme] = stylesheet
        
        return stylesheet
    
    def _load_raw_stylesheet(self, theme: str) -> str:
        """
        Load raw QSS file without color replacement.
        
        Args:
            theme: Theme name
        
        Returns:
            Raw stylesheet content
        """
        plugin_dir = self.get_plugin_dir()
        if not plugin_dir:
            # Try to determine from dockwidget location
            try:
                import filter_mate_dockwidget
                plugin_dir = os.path.dirname(filter_mate_dockwidget.__file__)
            except:
                return ""
        
        style_file = os.path.join(plugin_dir, 'resources', 'styles', f'{theme}.qss')
        
        # Fallback to default
        if not os.path.exists(style_file):
            style_file = os.path.join(plugin_dir, 'resources', 'styles', 'default.qss')
        
        if not os.path.exists(style_file):
            logger.warning(f"Stylesheet not found: {style_file}")
            return ""
        
        try:
            with open(style_file, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error loading stylesheet: {e}")
            return ""
    
    def teardown(self) -> None:
        """Clean up resources."""
        self.clear_cache()
        super().teardown()
