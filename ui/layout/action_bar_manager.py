"""
Action Bar Manager for FilterMate.

Handles action bar positioning and layout management.
Extracted from filter_mate_dockwidget.py (lines 4039-4604).

Story: MIG-064
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Optional, Dict, Any, List
import logging

from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import Qt

from .base_manager import LayoutManagerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class ActionBarManager(LayoutManagerBase):
    """
    Manages action bar positioning and layout.

    The action bar contains the main filter/export action buttons.
    It can be positioned at: top, bottom, left, or right of the toolset.

    Extracted methods from dockwidget (14 methods, lines 4039-4604):
    - _setup_action_bar_layout()
    - _get_action_bar_position()
    - _get_action_bar_vertical_alignment()
    - _apply_action_bar_position()
    - _adjust_header_for_side_position()
    - _restore_header_from_wrapper()
    - _clear_action_bar_layout()
    - _create_horizontal_action_layout()
    - _create_vertical_action_layout()
    - _apply_action_bar_size_constraints()
    - _reposition_action_bar_in_main_layout()
    - _create_horizontal_wrapper_for_side_action_bar()
    - _restore_side_action_bar_layout()
    - _restore_original_layout()

    Attributes:
        _position: Current action bar position ('top', 'bottom', 'left', 'right')
        _config: Current configuration from UIConfig

    Example:
        manager = ActionBarManager(dockwidget)
        manager.setup()

        # Change position:
        manager.set_position('left')
    """

    # Valid positions
    VALID_POSITIONS = ('top', 'bottom', 'left', 'right')

    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize the ActionBarManager.

        Args:
            dockwidget: The main FilterMate dockwidget instance
        """
        super().__init__(dockwidget)
        self._position: str = 'bottom'
        self._alignment: str = 'top'
        self._config: Dict[str, Any] = {}
        self._ui_config = None  # Lazy-loaded

        # State tracking
        self._side_action_bar_active: bool = False
        self._side_action_wrapper: Optional[QtWidgets.QWidget] = None
        self._vertical_action_spacer: Optional[QtWidgets.QSpacerItem] = None
        self._header_wrapper: Optional[QtWidgets.QWidget] = None
        self._header_spacer: Optional[QtWidgets.QWidget] = None

    def _get_ui_config(self):
        """Lazy load UIConfig to avoid circular imports."""
        if self._ui_config is None:
            try:
                from ...ui.config import UIConfig
                self._ui_config = UIConfig
            except ImportError:
                try:
                    from ui.config import UIConfig
                    self._ui_config = UIConfig
                except ImportError:
                    self._ui_config = None
        return self._ui_config

    def setup(self) -> None:
        """
        Setup action bar layout based on configuration.
        """
        if not hasattr(self.dockwidget, 'frame_actions'):
            self._initialized = True
            logger.debug("ActionBarManager: No frame_actions found, skipping setup")
            return

        # Get configured position
        self._position = self._read_position_from_config()
        self._alignment = self._read_alignment_from_config()

        logger.info(f"ActionBarManager: Setting up with position={self._position}")

        # Initialize tracking attributes on dockwidget for compatibility
        self.dockwidget._side_action_bar_active = False
        self.dockwidget._side_action_bar_position = None
        self.dockwidget._side_action_bar_alignment = None
        self.dockwidget._vertical_action_spacer = None
        self.dockwidget._side_action_wrapper = None

        # Apply the position
        success = self.apply()
        if not success:
            logger.warning("ActionBarManager: apply() failed during setup")

        self._initialized = True
        logger.debug("ActionBarManager setup complete")

    def apply(self) -> bool:
        """
        Apply action bar configuration based on current position.

        Returns:
            bool: True if configuration was applied successfully, False otherwise
        """
        if not hasattr(self.dockwidget, 'frame_actions'):
            logger.warning("ActionBarManager: No frame_actions found")
            return False

        try:
            if self._position in ('left', 'right'):
                self.apply_position()
            else:
                # For top/bottom, use the default horizontal layout
                self.dockwidget.frame_actions.show()
                self.dockwidget._current_action_bar_position = self._position
                logger.info(f"ActionBarManager: Using '{self._position}' position")
            return True
        except Exception as e:
            logger.error(f"ActionBarManager: Error applying configuration: {e}", exc_info=True)
            return False

    def get_position(self) -> str:
        """
        Get current action bar position.

        Returns:
            Position string: 'top', 'bottom', 'left', or 'right'
        """
        return self._position

    def set_position(self, position: str) -> None:
        """
        Set action bar position.

        Args:
            position: One of 'top', 'bottom', 'left', 'right'

        Raises:
            ValueError: If position is invalid
        """
        if position not in self.VALID_POSITIONS:
            raise ValueError(f"Invalid position: {position}. Must be one of {self.VALID_POSITIONS}")

        self._position = position
        self.apply_position()
        logger.debug(f"ActionBarManager: Position set to {position}")

    def _read_position_from_config(self) -> str:
        """
        Get action bar position from configuration.

        Returns:
            str: Position value ('top', 'bottom', 'left', 'right')
        """
        try:
            if hasattr(self.dockwidget, 'CONFIG_DATA'):
                position_config = self.dockwidget.CONFIG_DATA.get('APP', {}).get('DOCKWIDGET', {}).get('ACTION_BAR_POSITION', {})
                if isinstance(position_config, dict):
                    return position_config.get('value', 'top')
                return position_config if position_config else 'top'
        except (KeyError, TypeError, AttributeError):
            pass
        return 'top'

    def _read_alignment_from_config(self) -> str:
        """
        Get action bar vertical alignment from configuration.

        Returns:
            str: Alignment value ('top', 'bottom')
        """
        try:
            if hasattr(self.dockwidget, 'CONFIG_DATA'):
                alignment_config = self.dockwidget.CONFIG_DATA.get('APP', {}).get('DOCKWIDGET', {}).get('ACTION_BAR_VERTICAL_ALIGNMENT', {})
                if isinstance(alignment_config, dict):
                    return alignment_config.get('value', 'top')
                return alignment_config if alignment_config else 'top'
        except (KeyError, TypeError, AttributeError):
            pass
        return 'top'

    def apply_position(self) -> None:
        """
        Apply action bar position dynamically.

        Reorganizes the layout to place the action bar at the specified position.
        """
        if not hasattr(self.dockwidget, 'frame_actions'):
            return

        logger.info(f"ActionBarManager: Applying position={self._position}")

        # First, restore from any previous side action bar setup
        if self._side_action_bar_active:
            self.restore_side_action_bar_layout()

        # Get all action buttons
        action_buttons = self._get_action_buttons()

        # Step 1: Clear old layout
        self.clear_layout()

        # Step 2: Create new layout based on position
        is_horizontal = self._position in ('top', 'bottom')
        if is_horizontal:
            self.create_horizontal_layout(action_buttons)
        else:
            self.create_vertical_layout(action_buttons)

        # Step 3: Apply size constraints
        self.apply_size_constraints()

        # Step 4: Reposition in main layout
        self.reposition_in_main_layout()

        # Step 5: Adjust header for side positions
        self.adjust_header_for_side_position()

        # Store current position
        self.dockwidget._current_action_bar_position = self._position

    def _get_action_buttons(self) -> List[QtWidgets.QPushButton]:
        """Get list of action buttons from dockwidget."""
        buttons = []
        button_names = [
            'pushButton_action_filter',
            'pushButton_action_undo_filter',
            'pushButton_action_redo_filter',
            'pushButton_action_unfilter',
            'pushButton_action_export',
            'pushButton_action_about'
        ]
        for name in button_names:
            if hasattr(self.dockwidget, name):
                buttons.append(getattr(self.dockwidget, name))
        return buttons

    def _get_button_height(self) -> int:
        """Get action button height from config or use fallback."""
        UIConfig = self._get_ui_config()
        if UIConfig and hasattr(UIConfig, 'get_button_height'):
            return UIConfig.get_button_height("action_button")
        return 42  # Fallback

    def clear_layout(self) -> None:
        """
        Clear the existing action bar layout completely.
        """
        old_layout = self.dockwidget.frame_actions.layout()
        if old_layout:
            # Remove all items from the layout
            while old_layout.count():
                item = old_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
            # Delete the layout
            temp_widget = QtWidgets.QWidget()
            temp_widget.setLayout(old_layout)
            temp_widget.deleteLater()

    def create_horizontal_layout(self, action_buttons: List[QtWidgets.QPushButton]) -> None:
        """
        Create horizontal layout for action bar (top/bottom position).

        Args:
            action_buttons: List of QPushButton widgets to add
        """
        new_layout = QtWidgets.QHBoxLayout(self.dockwidget.frame_actions)
        new_layout.setContentsMargins(8, 8, 8, 16)
        new_layout.setSpacing(6)

        for i, btn in enumerate(action_buttons):
            btn.setParent(self.dockwidget.frame_actions)
            new_layout.addWidget(btn)
            # Add expanding spacer between buttons
            if i < len(action_buttons) - 1:
                spacer = QtWidgets.QSpacerItem(
                    4, 20,
                    QtWidgets.QSizePolicy.Expanding,
                    QtWidgets.QSizePolicy.Minimum
                )
                new_layout.addItem(spacer)

        logger.debug("ActionBarManager: Created horizontal layout")

    def create_vertical_layout(self, action_buttons: List[QtWidgets.QPushButton]) -> None:
        """
        Create vertical layout for action bar (left/right position).

        Args:
            action_buttons: List of QPushButton widgets to add
        """
        new_layout = QtWidgets.QVBoxLayout(self.dockwidget.frame_actions)
        new_layout.setContentsMargins(4, 4, 4, 4)
        new_layout.setSpacing(12)

        for btn in action_buttons:
            btn.setParent(self.dockwidget.frame_actions)
            new_layout.addWidget(btn, 0, Qt.AlignHCenter)

        # Add stretch at end to push buttons to top
        new_layout.addStretch(1)

        logger.debug("ActionBarManager: Created vertical layout")

    def apply_size_constraints(self) -> None:
        """
        Apply appropriate size constraints to frame_actions based on position.
        """
        frame = self.dockwidget.frame_actions
        button_height = self._get_button_height()

        if self._position in ('top', 'bottom'):
            # Horizontal mode
            frame_height = max(int(button_height * 1.8), 56)
            frame.setMinimumHeight(frame_height)
            frame.setMaximumHeight(frame_height + 15)
            frame.setMinimumWidth(0)
            frame.setMaximumWidth(16777215)
            frame.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Preferred
            )
        else:
            # Vertical mode
            frame_width = int(button_height * 1.3)
            frame.setMinimumWidth(frame_width)
            frame.setMaximumWidth(frame_width)
            frame.setMinimumHeight(0)
            frame.setMaximumHeight(16777215)
            frame.setSizePolicy(
                QtWidgets.QSizePolicy.Fixed,
                QtWidgets.QSizePolicy.Expanding
            )

        logger.debug(f"ActionBarManager: Applied size constraints for {self._position}")

    def reposition_in_main_layout(self) -> None:
        """
        Reposition the action bar frame in the main layout.
        """
        frame = self.dockwidget.frame_actions
        container = self.dockwidget.horizontalLayout_actions_container

        # Remove from container if present
        if container.indexOf(frame) >= 0:
            container.removeWidget(frame)

        frame.setParent(self.dockwidget.dockWidgetContents)

        if self._position == 'top':
            self.dockwidget.verticalLayout_main.insertWidget(0, frame)
            logger.info("ActionBarManager: Positioned at TOP")
        elif self._position == 'bottom':
            container.addWidget(frame)
            logger.info("ActionBarManager: Positioned at BOTTOM")
        elif self._position in ('left', 'right'):
            self._create_side_wrapper()
            logger.info(f"ActionBarManager: Positioned at {self._position.upper()}")

    def _create_side_wrapper(self) -> None:
        """
        Create wrapper for side (left/right) action bar positioning.
        """
        button_height = self._get_button_height()
        spacer_width = int(button_height * 1.3)

        # Remove from container
        container = self.dockwidget.horizontalLayout_actions_container
        if container.indexOf(self.dockwidget.frame_actions) >= 0:
            container.removeWidget(self.dockwidget.frame_actions)

        self.dockwidget.frame_actions.setParent(self.dockwidget.dockWidgetContents)
        splitter = self.dockwidget.main_splitter

        if self._alignment == 'top' and splitter is not None:
            parent_layout = self.dockwidget.verticalLayout_main
            splitter_idx = parent_layout.indexOf(splitter)

            if splitter_idx >= 0:
                parent_layout.removeWidget(splitter)

                # Create wrapper
                self._side_action_wrapper = QtWidgets.QWidget(self.dockwidget.dockWidgetContents)
                self._side_action_wrapper.setObjectName("side_action_wrapper")
                wrapper_layout = QtWidgets.QHBoxLayout(self._side_action_wrapper)
                wrapper_layout.setContentsMargins(0, 0, 0, 0)
                wrapper_layout.setSpacing(0)

                if self._position == 'left':
                    wrapper_layout.addWidget(self.dockwidget.frame_actions, 0)
                    wrapper_layout.addWidget(splitter, 1)
                else:
                    wrapper_layout.addWidget(splitter, 1)
                    wrapper_layout.addWidget(self.dockwidget.frame_actions, 0)

                parent_layout.insertWidget(splitter_idx, self._side_action_wrapper)

                # Add spacer to actions container
                self._vertical_action_spacer = QtWidgets.QSpacerItem(
                    spacer_width, 0,
                    QtWidgets.QSizePolicy.Fixed,
                    QtWidgets.QSizePolicy.Minimum
                )
                if self._position == 'left':
                    container.insertItem(0, self._vertical_action_spacer)
                else:
                    container.addItem(self._vertical_action_spacer)
        else:
            # Bottom alignment
            if self._position == 'left':
                container.insertWidget(0, self.dockwidget.frame_actions)
            else:
                container.addWidget(self.dockwidget.frame_actions)

        # Update state on dockwidget
        self._side_action_bar_active = True
        self.dockwidget._side_action_bar_active = True
        self.dockwidget._side_action_bar_position = self._position
        self.dockwidget._side_action_bar_alignment = self._alignment
        self.dockwidget._side_action_wrapper = self._side_action_wrapper
        self.dockwidget._vertical_action_spacer = self._vertical_action_spacer

    def adjust_header_for_side_position(self) -> None:
        """
        Adjust header layout when action bar is in side position.
        """
        if not hasattr(self.dockwidget, 'frame_header') or not self.dockwidget.frame_header:
            return

        button_height = self._get_button_height()
        spacer_width = int(button_height * 1.3)

        if self._position in ('left', 'right'):
            if self._header_wrapper:
                return  # Already wrapped

            parent_layout = getattr(self.dockwidget, 'verticalLayout_8', None)
            if not parent_layout:
                return

            header_idx = parent_layout.indexOf(self.dockwidget.frame_header)
            if header_idx < 0:
                return

            parent_layout.removeWidget(self.dockwidget.frame_header)

            self._header_wrapper = QtWidgets.QWidget(self.dockwidget.dockWidgetContents)
            self._header_wrapper.setObjectName("header_wrapper")
            wrapper_layout = QtWidgets.QHBoxLayout(self._header_wrapper)
            wrapper_layout.setContentsMargins(0, 0, 0, 0)
            wrapper_layout.setSpacing(0)

            self._header_spacer = QtWidgets.QWidget(self._header_wrapper)
            self._header_spacer.setFixedWidth(spacer_width)
            self._header_spacer.setObjectName("header_spacer")

            if self._position == 'left':
                wrapper_layout.addWidget(self._header_spacer, 0)
                wrapper_layout.addWidget(self.dockwidget.frame_header, 1)
            else:
                wrapper_layout.addWidget(self.dockwidget.frame_header, 1)
                wrapper_layout.addWidget(self._header_spacer, 0)

            parent_layout.insertWidget(header_idx, self._header_wrapper)
            logger.debug(f"ActionBarManager: Header wrapped for {self._position} position")
        else:
            self.restore_header_from_wrapper()

    def restore_header_from_wrapper(self) -> None:
        """
        Restore header from wrapper when switching away from side position.
        """
        if not self._header_wrapper:
            return

        if not hasattr(self.dockwidget, 'frame_header') or not self.dockwidget.frame_header:
            return

        parent_layout = getattr(self.dockwidget, 'verticalLayout_8', None)
        if not parent_layout:
            return

        wrapper_idx = parent_layout.indexOf(self._header_wrapper)
        if wrapper_idx < 0:
            return

        wrapper_layout = self._header_wrapper.layout()
        if wrapper_layout:
            wrapper_layout.removeWidget(self.dockwidget.frame_header)

        parent_layout.removeWidget(self._header_wrapper)

        self.dockwidget.frame_header.setParent(self.dockwidget.dockWidgetContents)
        parent_layout.insertWidget(wrapper_idx, self.dockwidget.frame_header)

        if self._header_spacer:
            self._header_spacer.deleteLater()
            self._header_spacer = None

        self._header_wrapper.deleteLater()
        self._header_wrapper = None

        logger.debug("ActionBarManager: Header restored from wrapper")

    def restore_side_action_bar_layout(self) -> None:
        """
        Restore layout when switching away from side position.
        """
        if self._side_action_wrapper:
            splitter = self.dockwidget.main_splitter
            if splitter is not None:
                wrapper_layout = self._side_action_wrapper.layout()
                if wrapper_layout:
                    wrapper_layout.removeWidget(splitter)
                    splitter.setParent(self.dockwidget.dockWidgetContents)

                parent_layout = self.dockwidget.verticalLayout_main
                wrapper_idx = parent_layout.indexOf(self._side_action_wrapper)

                if wrapper_idx >= 0:
                    parent_layout.removeWidget(self._side_action_wrapper)
                    parent_layout.insertWidget(wrapper_idx, splitter)

            self._side_action_wrapper.deleteLater()
            self._side_action_wrapper = None
            self.dockwidget._side_action_wrapper = None

        self.restore_header_from_wrapper()

        if self._vertical_action_spacer:
            container = self.dockwidget.horizontalLayout_actions_container
            idx = container.indexOf(self._vertical_action_spacer)
            if idx >= 0:
                container.takeAt(idx)
            self._vertical_action_spacer = None
            self.dockwidget._vertical_action_spacer = None

        self._side_action_bar_active = False
        self.dockwidget._side_action_bar_active = False

        logger.debug("ActionBarManager: Side action bar layout restored")

    def restore_original_layout(self) -> None:
        """
        Restore original layout before action bar modifications.
        """
        self.restore_side_action_bar_layout()
        self.restore_header_from_wrapper()

        # Move frame_actions back to container
        container = self.dockwidget.horizontalLayout_actions_container
        frame = self.dockwidget.frame_actions

        # Remove from any current parent layout
        if hasattr(self.dockwidget, 'verticalLayout_main'):
            idx = self.dockwidget.verticalLayout_main.indexOf(frame)
            if idx >= 0:
                self.dockwidget.verticalLayout_main.removeWidget(frame)

        frame.setParent(self.dockwidget.dockWidgetContents)
        container.addWidget(frame)

        self._position = 'bottom'
        self.dockwidget._current_action_bar_position = 'bottom'

        logger.debug("ActionBarManager: Original layout restored")
