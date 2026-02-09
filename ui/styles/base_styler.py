"""
Base Styler for FilterMate.

Provides abstract base class for all style managers.

Story: MIG-065
Phase: 6 - God Class DockWidget Migration
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional
import logging

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class StylerBase(ABC):
    """
    Abstract base class for all style managers.
    
    Provides common functionality for theme-aware styling:
    - Dockwidget reference management
    - Initialization tracking
    - Theme change handling
    
    Subclasses must implement:
    - setup(): Initial styling configuration
    - apply(): Apply current styles
    - on_theme_changed(): React to theme changes
    
    Example:
        class MyStyler(StylerBase):
            def setup(self):
                self._load_config()
                self.apply()
                self._initialized = True
            
            def apply(self):
                # Apply styling to widgets
                pass
            
            def on_theme_changed(self, theme: str):
                # Update styling for new theme
                self.apply()
    """
    
    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the styler.
        
        Args:
            dockwidget: The main FilterMate dockwidget instance
        """
        self._dockwidget = dockwidget
        self._initialized: bool = False
    
    @property
    def dockwidget(self) -> 'FilterMateDockWidget':
        """Get the dockwidget reference."""
        return self._dockwidget
    
    @property
    def is_initialized(self) -> bool:
        """Check if the styler has been initialized."""
        return self._initialized
    
    @abstractmethod
    def setup(self) -> None:
        """
        Initial setup of styling.
        
        Called once during dockwidget initialization.
        Should configure initial state and call apply().
        """
    
    @abstractmethod
    def apply(self) -> bool:
        """
        Apply current styling.
        
        Called to (re)apply styling to managed widgets.
        Should be idempotent.
        
        Returns:
            bool: True if styling applied successfully, False otherwise.
                  Implementations MUST log errors before returning False.
        """
    
    @abstractmethod
    def on_theme_changed(self, theme: str) -> None:
        """
        Handle theme change event.
        
        Called when the QGIS theme changes (light/dark).
        
        Args:
            theme: New theme name ('light', 'dark', 'default')
        """
    
    def teardown(self) -> None:
        """
        Clean up resources.
        
        Called during dockwidget cleanup.
        Subclasses can override to perform additional cleanup.
        """
        self._initialized = False
        logger.debug(f"{self.__class__.__name__} teardown complete")
    
    def get_plugin_dir(self) -> Optional[str]:
        """
        Get the plugin directory path.
        
        Returns:
            Path to plugin directory or None if not available
        """
        if hasattr(self._dockwidget, 'plugin_dir'):
            return self._dockwidget.plugin_dir
        return None
