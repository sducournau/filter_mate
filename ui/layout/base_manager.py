"""
Base class for layout managers.

All layout managers inherit from LayoutManagerBase which provides:
- Common initialization pattern
- Reference to dockwidget
- Logging setup
- Abstract methods for subclasses

Story: MIG-060
Phase: 6 - God Class DockWidget Migration
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Optional
import logging

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class LayoutManagerBase(ABC):
    """
    Abstract base class for layout managers.
    
    Provides common infrastructure for managers that handle
    UI layout, sizing, and positioning operations.
    
    All layout managers extracted from filter_mate_dockwidget.py
    should inherit from this class.
    
    Attributes:
        dockwidget: Reference to the main dockwidget
        _initialized: Whether setup() has been called
    
    Example:
        class MyManager(LayoutManagerBase):
            def setup(self) -> None:
                # Perform initial setup
                self._initialized = True
            
            def apply(self) -> None:
                # Apply configuration
                pass
    """
    
    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the layout manager.
        
        Args:
            dockwidget: The main FilterMate dockwidget instance
        """
        self.dockwidget = dockwidget
        self._initialized = False
        logger.debug(f"{self.__class__.__name__} created")
    
    @abstractmethod
    def setup(self) -> None:
        """
        Perform initial setup of layout elements.
        
        Called once during dockwidget initialization.
        Subclasses must implement this method.
        
        After successful setup, set self._initialized = True.
        """
        pass
    
    @abstractmethod
    def apply(self) -> None:
        """
        Apply layout configuration.
        
        Called when layout needs to be refreshed or reapplied,
        for example after a profile change (compact/normal).
        
        Subclasses must implement this method.
        """
        pass
    
    def teardown(self) -> None:
        """
        Clean up resources when manager is destroyed.
        
        Override in subclasses if cleanup is needed.
        Base implementation just resets initialized flag.
        """
        logger.debug(f"{self.__class__.__name__} teardown")
        self._initialized = False
    
    @property
    def is_initialized(self) -> bool:
        """Return whether the manager has been initialized."""
        return self._initialized
    
    def _get_plugin_dir(self) -> str:
        """
        Get the plugin directory path.
        
        Returns:
            str: Absolute path to the plugin directory
        """
        if hasattr(self.dockwidget, 'plugin_dir'):
            return self.dockwidget.plugin_dir
        return ''
