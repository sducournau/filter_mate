"""
Button Styler for FilterMate.

Manages button styling, states, and theme integration.
Extracted from filter_mate_dockwidget.py (lines 1041-1153, 6166-6245).

Story: MIG-068
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, List
import logging

from qgis.PyQt.QtWidgets import QPushButton, QToolButton, QAbstractButton, QSizePolicy
from qgis.PyQt.QtCore import Qt, QSize
from qgis.PyQt.QtGui import QCursor

from .base_styler import StylerBase

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class ButtonStyler(StylerBase):
    """
    Manages button styling for FilterMate dockwidget.

    Handles:
    - Checkable button harmonization
    - Button configuration (size, cursor, tooltip)
    - Style application (CSS)
    - State updates (enabled/disabled, checked)

    Extracted methods from filter_mate_dockwidget.py:
    - _harmonize_checkable_pushbuttons() (lines 1041-1100)
    - _configure_pushbuttons() (lines 1102-1153)
    - _apply_button_styles() (lines 6166-6200)
    - _update_button_states() (lines 6202-6245)

    Attributes:
        _styled_buttons: List of styled buttons for tracking
        _current_theme: Current theme name ('default', 'dark', 'light')
        _ui_config: Lazy-loaded UIConfig reference

    Example:
        styler = ButtonStyler(dockwidget)
        styler.setup()

        # On theme change:
        styler.on_theme_changed('dark')
    """

    # Button height by profile
    BUTTON_HEIGHTS = {
        'compact': {
            'standard': 24,
            'action': 28,
            'tool': 22,
        },
        'normal': {
            'standard': 28,
            'action': 36,
            'tool': 26,
        }
    }

    # Icon sizes by profile
    ICON_SIZES = {
        'compact': {
            'standard': 16,
            'action': 20,
            'tool': 14,
        },
        'normal': {
            'standard': 20,
            'action': 24,
            'tool': 18,
        }
    }

    def __init__(self, dockwidget: 'FilterMateDockWidget') -> None:
        """
        Initialize ButtonStyler.

        Args:
            dockwidget: Parent FilterMateDockWidget instance
        """
        super().__init__(dockwidget)
        self._styled_buttons: List[QAbstractButton] = []
        self._current_theme: str = 'default'
        self._ui_config = None
        self._profile: str = 'normal'

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

    def _get_profile(self) -> str:
        """Get current UI profile."""
        UIConfig = self._get_ui_config()
        if UIConfig:
            return UIConfig.get_active_profile() or 'normal'
        return self._profile

    def setup(self) -> None:
        """
        Initial setup of button styling.

        Called during dockwidget initialization.
        """
        self._detect_theme()
        success = self.apply()
        if not success:
            logger.warning("ButtonStyler: Initial setup failed - some buttons may be unstyled")
        self._initialized = True
        logger.debug(f"ButtonStyler setup complete (success={success})")

    def apply(self) -> bool:
        """
        Apply button styling to all buttons.

        Main entry point for button styling.
        Orchestrates all styling operations.

        Returns:
            bool: True if all styling applied successfully, False otherwise
        """
        try:
            self._configure_pushbuttons()
            self._harmonize_checkable_pushbuttons()
            self._apply_button_styles()
            self._update_button_states()
            logger.debug("ButtonStyler: Applied all button styles")
            return True
        except Exception as e:
            logger.error(f"ButtonStyler: Error applying styles: {e}", exc_info=True)
            return False

    def on_theme_changed(self, theme: str) -> None:
        """
        Handle theme change event.

        Args:
            theme: New theme name ('default', 'dark', 'light')
        """
        self._current_theme = theme
        success = self.apply()
        if success:
            logger.info(f"ButtonStyler: Theme changed to '{theme}'")
        else:
            logger.warning(f"ButtonStyler: Theme change to '{theme}' had errors")

    def is_dark_theme(self) -> bool:
        """Check if current theme is dark."""
        return self._current_theme == 'dark'

    def _detect_theme(self) -> None:
        """Detect theme from dockwidget or QGIS."""
        try:
            if hasattr(self.dockwidget, 'theme_manager'):
                self._current_theme = self.dockwidget.theme_manager.current_theme
            elif hasattr(self.dockwidget, '_current_theme'):
                self._current_theme = self.dockwidget._current_theme
        except Exception:
            self._current_theme = 'default'

    def _configure_pushbuttons(self) -> None:
        """
        Configure all pushbuttons in the dockwidget.

        Sets up:
        - Size policies (expanding horizontally, fixed vertically)
        - Cursor styles (pointing hand)
        - Minimum heights based on profile

        Extracted from filter_mate_dockwidget.py lines 1102-1153.
        """
        profile = self._get_profile()
        heights = self.BUTTON_HEIGHTS.get(profile, self.BUTTON_HEIGHTS['normal'])

        # Find all QPushButtons
        for button in self.dockwidget.findChildren(QPushButton):
            # Set cursor to pointing hand
            button.setCursor(QCursor(Qt.PointingHandCursor))

            # Set size policy: expand horizontally, fixed vertically
            button.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Fixed
            )

            # Set minimum height based on button type
            if self._is_action_button(button):
                button.setMinimumHeight(heights['action'])
            else:
                button.setMinimumHeight(heights['standard'])

        # Configure QToolButtons similarly
        for button in self.dockwidget.findChildren(QToolButton):
            button.setCursor(QCursor(Qt.PointingHandCursor))
            button.setMinimumHeight(heights['tool'])

    def _harmonize_checkable_pushbuttons(self) -> None:
        """
        Harmonize styling of checkable pushbuttons.

        Ensures consistent appearance for all checkable buttons:
        - Same checked/unchecked styling
        - Consistent icon placement
        - Uniform size policy

        Extracted from filter_mate_dockwidget.py lines 1041-1100.
        """
        profile = self._get_profile()
        icon_sizes = self.ICON_SIZES.get(profile, self.ICON_SIZES['normal'])

        for button in self.dockwidget.findChildren(QPushButton):
            if button.isCheckable():
                # Set icon size
                button.setIconSize(QSize(icon_sizes['standard'], icon_sizes['standard']))

                # Ensure flat appearance when not checked
                if not button.isChecked():
                    button.setFlat(True)

                # Track for later updates
                if button not in self._styled_buttons:
                    self._styled_buttons.append(button)

    def _apply_button_styles(self) -> None:
        """
        Apply CSS styles to buttons.

        Applies theme-appropriate styles including:
        - Background colors
        - Border styles
        - Hover effects
        - Pressed effects

        Extracted from filter_mate_dockwidget.py lines 6166-6200.

        v4.0.3: Checkable buttons in widget_filtering_keys and widget_exporting_keys
        are styled by default.qss - don't override with inline styles.
        """
        # Get action buttons if they exist
        action_buttons = self._get_action_buttons()

        for button in action_buttons:
            if button:
                self._apply_action_button_style(button)

        # Skip inline stylesheet for checkable buttons
        # Let default.qss handle widget_filtering_keys/widget_exporting_keys styles
        # This ensures harmonization between FILTERING and EXPORTING tabs

    def _update_button_states(self) -> None:
        """
        Update visual states of buttons.

        Synchronizes button visual states with their logical states:
        - Checked state styling
        - Enabled/disabled styling
        - Flat mode based on check state

        Extracted from filter_mate_dockwidget.py lines 6202-6245.
        """
        for button in self._styled_buttons:
            if not button:
                continue

            # Update flat state based on checked state
            if button.isCheckable():
                button.setFlat(not button.isChecked())

            # Update enabled state visual
            if not button.isEnabled():
                button.setStyleSheet(self._get_disabled_style())

    def _get_action_buttons(self) -> List[QPushButton]:
        """Get list of action buttons from dockwidget."""
        buttons = []
        action_button_names = [
            'btn_filtering', 'btn_exploring', 'btn_exporting',
            'btn_filter', 'btn_explore', 'btn_export',
            'btn_undo', 'btn_redo', 'btn_reset', 'btn_clear'
        ]

        for name in action_button_names:
            if hasattr(self.dockwidget, name):
                btn = getattr(self.dockwidget, name)
                if btn:
                    buttons.append(btn)

        return buttons

    def _is_action_button(self, button: QPushButton) -> bool:
        """Check if button is an action button."""
        action_names = ['filter', 'explore', 'export', 'undo', 'redo', 'reset', 'clear']
        obj_name = button.objectName().lower() if button.objectName() else ''
        return any(name in obj_name for name in action_names)

    def _apply_action_button_style(self, button: QPushButton) -> None:
        """
        Apply styling to an action button.

        Args:
            button: Action button to style
        """
        profile = self._get_profile()
        heights = self.BUTTON_HEIGHTS.get(profile, self.BUTTON_HEIGHTS['normal'])
        icon_sizes = self.ICON_SIZES.get(profile, self.ICON_SIZES['normal'])

        button.setMinimumHeight(heights['action'])
        button.setIconSize(QSize(icon_sizes['action'], icon_sizes['action']))

        # Apply theme-specific styling
        if self.is_dark_theme():
            button.setStyleSheet(self._get_dark_action_button_style())
        else:
            button.setStyleSheet(self._get_light_action_button_style())

        if button not in self._styled_buttons:
            self._styled_buttons.append(button)

    def _get_dark_action_button_style(self) -> str:
        """
        Get CSS for action buttons in dark theme.

        Returns:
            CSS stylesheet string
        """
        return """
            QPushButton {
                background-color: #3d3d3d;
                color: #ffffff;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #4d4d4d;
                border-color: #666666;
            }
            QPushButton:pressed {
                background-color: #2d2d2d;
            }
            QPushButton:checked {
                background-color: #0d6efd;
                border-color: #0d6efd;
            }
            QPushButton:disabled {
                background-color: #2d2d2d;
                color: #666666;
            }
        """

    def _get_light_action_button_style(self) -> str:
        """
        Get CSS for action buttons in light theme.

        Returns:
            CSS stylesheet string
        """
        return """
            QPushButton {
                background-color: #f8f9fa;
                color: #212529;
                border: 1px solid #dee2e6;
                border-radius: 4px;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
            }
            QPushButton:checked {
                background-color: #0d6efd;
                color: #ffffff;
                border-color: #0d6efd;
            }
            QPushButton:disabled {
                background-color: #e9ecef;
                color: #adb5bd;
            }
        """

    def _get_checkable_button_style(self) -> str:
        """Get CSS for checkable buttons based on theme."""
        if self.is_dark_theme():
            return """
                QPushButton {
                    background-color: transparent;
                    color: #cccccc;
                    border: none;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #3d3d3d;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: transparent;
                    color: #333333;
                    border: none;
                    padding: 4px 8px;
                }
                QPushButton:hover {
                    background-color: #e9ecef;
                }
            """

    def _get_disabled_style(self) -> str:
        """Get CSS for disabled buttons."""
        if self.is_dark_theme():
            return """
                QPushButton:disabled {
                    background-color: #2d2d2d;
                    color: #666666;
                    border-color: #444444;
                }
            """
        else:
            return """
                QPushButton:disabled {
                    background-color: #e9ecef;
                    color: #adb5bd;
                    border-color: #dee2e6;
                }
            """

    def style_action_buttons(self) -> None:
        """
        Style the main action buttons explicitly.

        Call this to force-apply styling to action buttons.
        """
        for button in self._get_action_buttons():
            if button:
                self._apply_action_button_style(button)

    def refresh_button_states(self) -> None:
        """Refresh visual states of all tracked buttons."""
        self._update_button_states()

    def teardown(self) -> None:
        """Clean up resources."""
        self._styled_buttons.clear()
        super().teardown()
