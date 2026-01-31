# -*- coding: utf-8 -*-
"""
FilterMate - Base QToolBox Widget

Abstract base class for FilterMate QToolBox implementations.
Provides common functionality for ExploringToolBox and ToolsetToolBox.
"""

from qgis.PyQt.QtWidgets import (
    QToolBox, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QSizePolicy
)
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtGui import QIcon, QFont

from ...styles import ThemeManager

import logging
logger = logging.getLogger('FilterMate.ToolBox')


class BaseToolBox(QToolBox):
    """Base QToolBox with FilterMate styling and common functionality.
    
    Features:
    - Automatic theme synchronization with QGIS
    - Page change signals
    - Icon support for pages
    - Collapsible sections within pages
    
    Signals:
        pageChanged(int): Emitted when active page changes
        pageActivated(str): Emitted with page name when activated
    """
    
    pageChanged = pyqtSignal(int)
    pageActivated = pyqtSignal(str)
    
    def __init__(self, parent=None, title: str = "ToolBox"):
        """Initialize BaseToolBox.
        
        Args:
            parent: Parent widget
            title: Display title for the toolbox
        """
        super().__init__(parent)
        self._title = title
        self._pages = {}  # name -> (index, widget)
        self._page_icons = {}  # name -> QIcon
        self._auto_switch_enabled = True
        
        self._setup_style()
        self._connect_signals()
    
    def _setup_style(self):
        """Apply FilterMate styling to the toolbox."""
        self.setObjectName(f"filtermate_{self._title.lower().replace(' ', '_')}_toolbox")
        
        # Base styling - will be enhanced by ThemeManager
        self.setStyleSheet("""
            QToolBox::tab {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                           stop: 0 #E1E1E1, stop: 0.4 #DDDDDD,
                                           stop: 0.5 #D8D8D8, stop: 1.0 #D3D3D3);
                border-radius: 5px;
                color: darkgray;
                font-weight: bold;
                padding: 5px;
            }
            QToolBox::tab:selected {
                font: italic;
                color: black;
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                           stop: 0 #D3E8F5, stop: 1.0 #B8D4E8);
            }
            QToolBox::tab:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                           stop: 0 #D8D8D8, stop: 1.0 #C8C8C8);
            }
        """)
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    
    def _connect_signals(self):
        """Connect internal signals."""
        self.currentChanged.connect(self._on_page_changed)
    
    def _on_page_changed(self, index: int):
        """Handle page change event."""
        self.pageChanged.emit(index)
        
        # Find page name from index
        for name, (idx, widget) in self._pages.items():
            if idx == index:
                self.pageActivated.emit(name)
                logger.debug(f"{self._title}: Page changed to '{name}' (index {index})")
                break
    
    def add_page(self, name: str, widget: QWidget, icon: QIcon = None, 
                 tooltip: str = None) -> int:
        """Add a page to the toolbox.
        
        Args:
            name: Unique name for the page (used for lookup)
            widget: Widget to add as page content
            icon: Optional icon for the page tab
            tooltip: Optional tooltip for the page tab
            
        Returns:
            Index of the added page
        """
        if name in self._pages:
            logger.warning(f"Page '{name}' already exists in {self._title}")
            return self._pages[name][0]
        
        index = self.addItem(widget, name)
        
        if icon:
            self.setItemIcon(index, icon)
            self._page_icons[name] = icon
        
        if tooltip:
            self.setItemToolTip(index, tooltip)
        
        self._pages[name] = (index, widget)
        logger.debug(f"{self._title}: Added page '{name}' at index {index}")
        
        return index
    
    def get_page(self, name: str) -> QWidget:
        """Get page widget by name.
        
        Args:
            name: Page name
            
        Returns:
            Page widget or None if not found
        """
        if name in self._pages:
            return self._pages[name][1]
        return None
    
    def get_page_index(self, name: str) -> int:
        """Get page index by name.
        
        Args:
            name: Page name
            
        Returns:
            Page index or -1 if not found
        """
        if name in self._pages:
            return self._pages[name][0]
        return -1
    
    def activate_page(self, name: str) -> bool:
        """Activate a page by name.
        
        Args:
            name: Page name to activate
            
        Returns:
            True if page was activated, False if not found
        """
        index = self.get_page_index(name)
        if index >= 0:
            self.setCurrentIndex(index)
            return True
        logger.warning(f"Page '{name}' not found in {self._title}")
        return False
    
    def get_active_page_name(self) -> str:
        """Get the name of the currently active page.
        
        Returns:
            Name of active page or empty string
        """
        current_index = self.currentIndex()
        for name, (idx, widget) in self._pages.items():
            if idx == current_index:
                return name
        return ""
    
    def set_auto_switch_enabled(self, enabled: bool):
        """Enable/disable automatic page switching.
        
        Args:
            enabled: Whether auto-switch is enabled
        """
        self._auto_switch_enabled = enabled
    
    def is_auto_switch_enabled(self) -> bool:
        """Check if auto-switch is enabled."""
        return self._auto_switch_enabled
    
    def update_page_icon(self, name: str, icon: QIcon):
        """Update the icon for a page.
        
        Args:
            name: Page name
            icon: New icon
        """
        index = self.get_page_index(name)
        if index >= 0:
            self.setItemIcon(index, icon)
            self._page_icons[name] = icon
    
    def update_page_text(self, name: str, text: str):
        """Update the text/title for a page.
        
        Args:
            name: Page name
            text: New text/title
        """
        index = self.get_page_index(name)
        if index >= 0:
            self.setItemText(index, text)
    
    def set_page_enabled(self, name: str, enabled: bool):
        """Enable/disable a page.
        
        Args:
            name: Page name
            enabled: Whether the page should be enabled
        """
        index = self.get_page_index(name)
        if index >= 0:
            self.setItemEnabled(index, enabled)
    
    def refresh_theme(self):
        """Refresh styling based on current QGIS theme."""
        # Will be implemented by subclasses with specific styling needs
        pass
    
    @property
    def page_names(self) -> list:
        """Get list of all page names."""
        return list(self._pages.keys())
    
    @property 
    def page_count(self) -> int:
        """Get number of pages."""
        return len(self._pages)
