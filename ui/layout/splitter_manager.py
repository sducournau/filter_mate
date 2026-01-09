"""
Splitter Manager for FilterMate.

Handles main splitter configuration between exploring and toolset frames.
Extracted from filter_mate_dockwidget.py (lines 693-848).

Story: MIG-061
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, Dict, Any, List
import logging

from qgis.PyQt.QtWidgets import QSplitter, QSizePolicy

from .base_manager import LayoutManagerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class SplitterManager(LayoutManagerBase):
    """
    Manages the main splitter between exploring and toolset frames.
    
    The splitter divides the dockwidget vertically:
    - Top: frame_exploring (layer info, field values)
    - Bottom: frame_toolset (tabs: filtering, exporting, config)
    
    Configuration is loaded from UIConfig and supports:
    - Handle width and margins
    - Stretch factors for proportional sizing
    - Collapsible behavior
    - Size policies for child frames
    - Initial size distribution
    
    Methods extracted from dockwidget:
    - _setup_main_splitter() -> setup()
    - _apply_splitter_frame_policies() -> _apply_frame_policies()
    - _set_initial_splitter_sizes() -> _set_initial_sizes()
    
    Attributes:
        _splitter: Reference to the QSplitter widget
        _config: Splitter configuration from UIConfig
    
    Example:
        manager = SplitterManager(dockwidget)
        manager.setup()  # Configure splitter
        
        # Later, to reapply after config change:
        manager.apply()
        
        # Get/set sizes programmatically:
        sizes = manager.get_sizes()
        manager.set_sizes([200, 400])
    """
    
    # Policy string to Qt enum mapping
    POLICY_MAP: Dict[str, 'QSizePolicy.Policy'] = {
        'Fixed': QSizePolicy.Fixed,
        'Minimum': QSizePolicy.Minimum,
        'Maximum': QSizePolicy.Maximum,
        'Preferred': QSizePolicy.Preferred,
        'Expanding': QSizePolicy.Expanding,
        'MinimumExpanding': QSizePolicy.MinimumExpanding,
        'Ignored': QSizePolicy.Ignored
    }
    
    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the SplitterManager.
        
        Args:
            dockwidget: The main FilterMate dockwidget instance
        """
        super().__init__(dockwidget)
        self._splitter: Optional[QSplitter] = None
        self._config: Dict[str, Any] = {}
    
    def setup(self) -> None:
        """
        Setup the main splitter with configuration from UIConfig.
        
        Configures:
        - Splitter properties (handle width, collapsible, etc.)
        - Frame size policies
        - Stretch factors
        - Initial size distribution
        - Handle styling
        
        This method replaces the original _setup_main_splitter() from
        filter_mate_dockwidget.py (lines 693-771).
        """
        UIConfig = None
        try:
            # Try relative import first (package context)
            from ...ui.config import UIConfig
        except ImportError:
            try:
                # Fallback to absolute import (QGIS plugin context)
                from ui.config import UIConfig
            except ImportError:
                logger.warning("UIConfig not available, using defaults")
        
        try:
            # Get splitter reference from dockwidget
            if not hasattr(self.dockwidget, 'splitter_main'):
                logger.warning("splitter_main not found in dockwidget")
                return
            
            self._splitter = self.dockwidget.splitter_main
            
            # Also set as main_splitter for backward compatibility
            self.dockwidget.main_splitter = self._splitter
            
            # Load configuration
            if UIConfig:
                self._config = UIConfig.get_config('splitter') or {}
            else:
                self._config = self._get_default_config()
            
            # Apply splitter properties
            self._apply_splitter_properties()
            
            # Apply handle styling
            self._apply_handle_style()
            
            # Configure frame size policies
            self._apply_frame_policies()
            
            # Set stretch factors
            self._apply_stretch_factors()
            
            # Set initial sizes
            self._set_initial_sizes()
            
            self._initialized = True
            logger.debug(
                f"SplitterManager setup complete: handle={self._config.get('handle_width', 6)}px, "
                f"stretch={self._config.get('exploring_stretch', 2)}:{self._config.get('toolset_stretch', 5)}"
            )
            
        except Exception as e:
            logger.error(f"Error setting up splitter: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self._splitter = None
    
    def apply(self) -> None:
        """
        Reapply splitter configuration.
        
        Called when configuration changes (e.g., profile switch).
        Reloads config from UIConfig and reapplies all settings.
        """
        if not self._splitter:
            logger.warning("Cannot apply - splitter not initialized")
            return
        
        UIConfig = None
        try:
            from ...ui.config import UIConfig
        except ImportError:
            try:
                from ui.config import UIConfig
            except ImportError:
                pass
        
        if UIConfig:
            self._config = UIConfig.get_config('splitter') or {}
        else:
            self._config = self._get_default_config()
        
        self._apply_splitter_properties()
        self._apply_handle_style()
        self._apply_frame_policies()
        self._apply_stretch_factors()
        
        logger.debug("SplitterManager configuration reapplied")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default splitter configuration.
        
        Used when UIConfig is not available.
        
        Returns:
            Dict with default configuration values
        """
        return {
            'handle_width': 6,
            'handle_margin': 40,
            'exploring_stretch': 2,
            'toolset_stretch': 5,
            'collapsible': False,
            'opaque_resize': True,
            'initial_exploring_ratio': 0.50,
            'initial_toolset_ratio': 0.50,
        }
    
    def _apply_splitter_properties(self) -> None:
        """Apply basic splitter properties from config."""
        handle_width = self._config.get('handle_width', 6)
        collapsible = self._config.get('collapsible', False)
        opaque_resize = self._config.get('opaque_resize', True)
        
        self._splitter.setChildrenCollapsible(collapsible)
        self._splitter.setHandleWidth(handle_width)
        self._splitter.setOpaqueResize(opaque_resize)
    
    def _apply_handle_style(self) -> None:
        """
        Apply styling to the splitter handle.
        
        Creates a subtle, minimal handle style with hover effect.
        """
        handle_width = self._config.get('handle_width', 6)
        handle_margin = self._config.get('handle_margin', 40)
        
        # Subtle and minimal handle style
        self._splitter.setStyleSheet(f"""
            QSplitter::handle:vertical {{
                background-color: #d0d0d0;
                height: {handle_width - 2}px;
                margin: 2px {handle_margin}px;
                border-radius: {(handle_width - 2) // 2}px;
            }}
            QSplitter::handle:vertical:hover {{
                background-color: #3498db;
            }}
        """)
    
    def _apply_frame_policies(self) -> None:
        """
        Apply size policies to frames within the splitter.
        
        This replaces the original _apply_splitter_frame_policies() from
        filter_mate_dockwidget.py (lines 773-811).
        
        Policies:
        - frame_exploring: Minimum policy (can shrink to min but prefers base)
        - frame_toolset: Expanding policy (takes remaining space)
        """
        UIConfig = None
        try:
            from ...ui.config import UIConfig
        except ImportError:
            try:
                from ui.config import UIConfig
            except ImportError:
                pass
        
        # Configure frame_exploring
        if hasattr(self.dockwidget, 'frame_exploring'):
            if UIConfig:
                exploring_config = UIConfig.get_config('frame_exploring') or {}
            else:
                exploring_config = {'size_policy_h': 'Preferred', 'size_policy_v': 'Minimum'}
            
            h_policy = self.POLICY_MAP.get(
                exploring_config.get('size_policy_h', 'Preferred'),
                QSizePolicy.Preferred
            )
            v_policy = self.POLICY_MAP.get(
                exploring_config.get('size_policy_v', 'Minimum'),
                QSizePolicy.Minimum
            )
            self.dockwidget.frame_exploring.setSizePolicy(h_policy, v_policy)
            logger.debug(
                f"frame_exploring policy: "
                f"{exploring_config.get('size_policy_h')}/{exploring_config.get('size_policy_v')}"
            )
        
        # Configure frame_toolset
        if hasattr(self.dockwidget, 'frame_toolset'):
            if UIConfig:
                toolset_config = UIConfig.get_config('frame_toolset') or {}
            else:
                toolset_config = {'size_policy_h': 'Preferred', 'size_policy_v': 'Expanding'}
            
            h_policy = self.POLICY_MAP.get(
                toolset_config.get('size_policy_h', 'Preferred'),
                QSizePolicy.Preferred
            )
            v_policy = self.POLICY_MAP.get(
                toolset_config.get('size_policy_v', 'Expanding'),
                QSizePolicy.Expanding
            )
            self.dockwidget.frame_toolset.setSizePolicy(h_policy, v_policy)
            logger.debug(
                f"frame_toolset policy: "
                f"{toolset_config.get('size_policy_h')}/{toolset_config.get('size_policy_v')}"
            )
    
    def _apply_stretch_factors(self) -> None:
        """Set stretch factors for proportional sizing."""
        exploring_stretch = self._config.get('exploring_stretch', 2)
        toolset_stretch = self._config.get('toolset_stretch', 5)
        
        self._splitter.setStretchFactor(0, exploring_stretch)
        self._splitter.setStretchFactor(1, toolset_stretch)
        
        logger.debug(f"Stretch factors: exploring={exploring_stretch}, toolset={toolset_stretch}")
    
    def _set_initial_sizes(self) -> None:
        """
        Set initial splitter sizes based on configuration ratios.
        
        This replaces the original _set_initial_splitter_sizes() from
        filter_mate_dockwidget.py (lines 813-840).
        
        Uses the available height to distribute space between frames
        according to the configured ratios (50/50 by default).
        """
        exploring_ratio = self._config.get('initial_exploring_ratio', 0.50)
        toolset_ratio = self._config.get('initial_toolset_ratio', 0.50)
        
        # Get available height from splitter or use default
        total_height = self._splitter.height()
        if total_height < 100:  # Splitter not yet sized
            total_height = 600
        
        # Calculate sizes based on ratios
        exploring_size = int(total_height * exploring_ratio)
        toolset_size = int(total_height * toolset_ratio)
        
        self._splitter.setSizes([exploring_size, toolset_size])
        
        logger.debug(
            f"Initial sizes: exploring={exploring_size}px ({exploring_ratio:.0%}), "
            f"toolset={toolset_size}px ({toolset_ratio:.0%})"
        )
    
    @property
    def splitter(self) -> Optional[QSplitter]:
        """Return the managed splitter widget."""
        return self._splitter
    
    def get_sizes(self) -> List[int]:
        """
        Return current splitter sizes.
        
        Returns:
            List of [exploring_size, toolset_size] in pixels
        """
        if self._splitter:
            return self._splitter.sizes()
        return []
    
    def set_sizes(self, sizes: List[int]) -> None:
        """
        Set splitter sizes programmatically.
        
        Args:
            sizes: List of [exploring_size, toolset_size] in pixels
        """
        if self._splitter and len(sizes) == 2:
            self._splitter.setSizes(sizes)
            logger.debug(f"Splitter sizes set to: {sizes}")
    
    def save_sizes(self) -> List[int]:
        """
        Save current sizes for later restoration.
        
        Returns:
            Current sizes that can be passed to set_sizes()
        """
        return self.get_sizes()
    
    def restore_sizes(self, sizes: List[int]) -> None:
        """
        Restore previously saved sizes.
        
        Args:
            sizes: Sizes previously returned by save_sizes()
        """
        self.set_sizes(sizes)
    
    def teardown(self) -> None:
        """Clean up splitter resources."""
        super().teardown()
        self._splitter = None
        self._config = {}
