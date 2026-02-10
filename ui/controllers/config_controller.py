"""
Configuration Controller for FilterMate.

Manages the Settings tab and configuration operations.
Extracted from filter_mate_dockwidget.py (lines 5074-5777).

Story: MIG-070
Phase: 6 - God Class DockWidget Migration
"""

from typing import TYPE_CHECKING, Any, Dict, Optional, List
import logging
import json

from qgis.PyQt.QtCore import pyqtSignal, Qt

from .base_controller import BaseController

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget
    from ...core.services.filter_service import FilterService
    from ...adapters.qgis.signals.signal_manager import SignalManager

logger = logging.getLogger(__name__)


class ConfigController(BaseController):
    """
    Controller for configuration management.

    Handles:
    - Theme changes (dark/light mode)
    - UI profile changes (compact/normal/auto)
    - Action bar position/alignment
    - Export settings (style, format)
    - Configuration persistence (save/load/cancel)

    Signals:
        config_changed: Emitted when any configuration value changes (key, value)
        theme_changed: Emitted when theme changes (theme_name)
        profile_changed: Emitted when UI profile changes (profile_name)

    Extracted methods from filter_mate_dockwidget.py:
    - data_changed_configuration_model() (lines 5286-5320)
    - _apply_theme_change() (lines 5323-5368)
    - _apply_ui_profile_change() (lines 5370-5428)
    - _apply_action_bar_position_change() (lines 5430-5497)
    - _apply_export_style_change() (lines 5499-5539)
    - _apply_export_format_change() (lines 5541-5582)
    - apply_pending_config_changes() (lines 5584-5625)
    - cancel_pending_config_changes() (lines 5627-5675)

    Example:
        controller = ConfigController(dockwidget)
        controller.setup()

        # React to config changes
        controller.config_changed.connect(on_config_changed)
        controller.theme_changed.connect(on_theme_changed)

        # Apply or cancel pending changes
        controller.apply_pending_config_changes()
        controller.cancel_pending_config_changes()
    """

    # Qt Signals
    config_changed = pyqtSignal(str, object)  # key, value
    theme_changed = pyqtSignal(str)  # theme name
    profile_changed = pyqtSignal(str)  # profile name

    def __init__(
        self,
        dockwidget: 'FilterMateDockWidget',
        filter_service: Optional['FilterService'] = None,
        signal_manager: Optional['SignalManager'] = None
    ) -> None:
        """
        Initialize the configuration controller.

        Args:
            dockwidget: Parent FilterMateDockWidget instance
            filter_service: Optional filter service for business logic
            signal_manager: Optional centralized signal manager
        """
        super().__init__(dockwidget, filter_service, signal_manager)
        self._pending_changes: List[Dict[str, Any]] = []
        self._changes_pending: bool = False
        self._initialized: bool = False

    @property
    def pending_changes(self) -> List[Dict[str, Any]]:
        """Get list of pending configuration changes."""
        return self._pending_changes

    @property
    def has_pending_changes(self) -> bool:
        """Check if there are pending changes."""
        return self._changes_pending and len(self._pending_changes) > 0

    def setup(self) -> None:
        """
        Initialize configuration controller.

        Called once during dockwidget initialization.
        Connects signals and initializes state.
        """
        logger.debug("ConfigController.setup() called")
        self._initialized = True

    def teardown(self) -> None:
        """
        Clean up the controller.

        Called when dockwidget is closing.
        """
        self._disconnect_all_signals()
        self._pending_changes.clear()
        self._changes_pending = False
        logger.debug("ConfigController.teardown() completed")

    def on_tab_activated(self) -> None:
        """Called when Settings tab becomes active."""
        super().on_tab_activated()
        logger.debug("ConfigController tab activated")

    def on_tab_deactivated(self) -> None:
        """Called when switching away from Settings tab."""
        super().on_tab_deactivated()
        logger.debug("ConfigController tab deactivated")

    # === Configuration Change Tracking ===

    def data_changed_configuration_model(self, input_data: Any = None) -> None:
        """
        Track configuration changes without applying them immediately.

        Called when user edits a value in the configuration tree view.
        Stores the change for later application when OK is clicked.

        Args:
            input_data: The QStandardItem that was changed
        """
        if not self._initialized:
            return

        if input_data is None:
            return

        try:
            index = input_data.index()
            item_key = self.dockwidget.config_view.model.itemFromIndex(
                index.siblingAtColumn(0)
            )

            # Build path to changed item
            items_keys_values_path = []
            while item_key is not None:
                items_keys_values_path.append(item_key.data(Qt.DisplayRole))
                item_key = item_key.parent()

            items_keys_values_path.reverse()

            # Store change for later application
            change = {
                'path': items_keys_values_path,
                'index': index,
                'item': input_data
            }
            self._pending_changes.append(change)
            self._changes_pending = True

            # Enable OK/Cancel buttons when changes are pending
            self._update_buttonbox_state(enabled=True)

            logger.info(
                f"Configuration change pending: {' → '.join(items_keys_values_path)}"
            )

            # Emit signal
            key = items_keys_values_path[-1] if items_keys_values_path else ''
            self.config_changed.emit(key, None)

        except Exception as e:
            logger.error(f"Error tracking configuration change: {e}")

    # === Apply Configuration Changes ===

    def apply_pending_config_changes(self) -> bool:
        """
        Apply all pending configuration changes when OK button is clicked.

        Orchestrates the application of different config change types by
        delegating to specialized methods.

        Returns:
            True if changes were applied successfully, False otherwise
        """
        if not self.has_pending_changes:
            logger.info("No pending configuration changes to apply")
            return True

        logger.info(
            f"Applying {len(self._pending_changes)} pending configuration change(s)"
        )

        changes_summary: List[str] = []

        try:
            for change in self._pending_changes:
                items_keys_values_path = change['path']

                # Handle ICONS changes
                if 'ICONS' in items_keys_values_path:
                    self._apply_icon_change(change, changes_summary)

                # Apply specialized change handlers
                self._apply_theme_change(change, changes_summary)
                self._apply_ui_profile_change(change, changes_summary)
                self._apply_action_bar_position_change(change, changes_summary)
                self._apply_export_style_change(change, changes_summary)
                self._apply_export_format_change(change, changes_summary)

                # Save configuration after each change
                self._save_configuration()

            # Clear pending changes after applying them
            self._pending_changes.clear()
            self._changes_pending = False

            # Disable OK/Cancel buttons after changes have been applied
            self._update_buttonbox_state(enabled=False)

            logger.info(
                "All pending configuration changes have been applied and saved"
            )

            if changes_summary:
                logger.info(f"Applied changes: {', '.join(changes_summary)}")

            return True

        except Exception as e:
            logger.error(f"Error applying configuration changes: {e}")
            return False

    def cancel_pending_config_changes(self) -> None:
        """
        Cancel pending configuration changes when Cancel button is clicked.

        Reloads configuration from file to revert changes in tree view.
        """
        if not self.has_pending_changes:
            logger.info("No pending configuration changes to cancel")
            return

        logger.info(
            f"Cancelling {len(self._pending_changes)} pending configuration change(s)"
        )

        try:
            # Reload configuration from file
            self._reload_configuration()

            # Clear pending changes
            self._pending_changes.clear()
            self._changes_pending = False

            # Disable buttons after cancelling changes
            self._update_buttonbox_state(enabled=False)

            logger.info("Configuration changes cancelled successfully")

        except Exception as e:
            logger.error(f"Error cancelling configuration changes: {e}")
            self._show_error(f"Error cancelling changes: {str(e)}")

    # === Specialized Change Handlers ===

    def _apply_theme_change(
        self,
        change: Dict[str, Any],
        changes_summary: List[str]
    ) -> None:
        """
        Apply ACTIVE_THEME configuration change.

        Detects theme from config change and applies it using StyleLoader.
        Supports 'auto', 'default', 'dark', and 'light' themes.

        Args:
            change: Change dictionary with 'path', 'index', 'item'
            changes_summary: List to append change description to
        """
        items_keys_values_path = change['path']
        index = change['index']

        if 'ACTIVE_THEME' not in items_keys_values_path:
            return

        try:
            value_item = self.dockwidget.config_view.model.itemFromIndex(
                index.siblingAtColumn(1)
            )
            value_data = value_item.data(Qt.UserRole)

            # Handle ChoicesType format (dict with 'value' and 'choices')
            if isinstance(value_data, dict) and 'value' in value_data:
                new_theme_value = value_data['value']
            else:
                new_theme_value = value_item.data(Qt.DisplayRole) if value_item else None

            if new_theme_value:
                logger.info(f"ACTIVE_THEME changed to: {new_theme_value}")

                # Import StyleLoader
                try:
                    from ui.styles import StyleLoader
                except ImportError:
                    logger.warning("StyleLoader not available")
                    return

                if new_theme_value == 'auto':
                    # Auto-detect and apply theme
                    StyleLoader.set_theme_from_config(
                        self.dockwidget.dockWidgetContents,
                        self.dockwidget.CONFIG_DATA,
                        None
                    )
                else:
                    # Apply specified theme (default, dark, light)
                    StyleLoader.set_theme_from_config(
                        self.dockwidget.dockWidgetContents,
                        self.dockwidget.CONFIG_DATA,
                        new_theme_value
                    )

                changes_summary.append(f"Theme: {new_theme_value}")
                self.theme_changed.emit(new_theme_value)

        except Exception as e:
            logger.error(f"Error applying ACTIVE_THEME change: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _apply_ui_profile_change(
        self,
        change: Dict[str, Any],
        changes_summary: List[str]
    ) -> None:
        """
        Apply UI_PROFILE configuration change.

        Updates UIConfig with new profile (compact/normal/auto) and
        re-applies dynamic dimensions.

        Args:
            change: Change dictionary with 'path', 'index', 'item'
            changes_summary: List to append change description to
        """
        items_keys_values_path = change['path']
        index = change['index']

        if 'UI_PROFILE' not in items_keys_values_path:
            return

        try:
            value_item = self.dockwidget.config_view.model.itemFromIndex(
                index.siblingAtColumn(1)
            )
            value_data = value_item.data(Qt.UserRole)

            # Handle ChoicesType format
            if isinstance(value_data, dict) and 'value' in value_data:
                new_profile_value = value_data['value']
            else:
                new_profile_value = value_item.data(Qt.DisplayRole) if value_item else None

            if new_profile_value:
                logger.info(f"UI_PROFILE changed to: {new_profile_value}")

                try:
                    from ui.config import UIConfig, DisplayProfile
                except ImportError:
                    logger.warning("UIConfig not available")
                    return

                if new_profile_value == 'compact':
                    UIConfig.set_profile(DisplayProfile.COMPACT)
                    logger.info("Switched to COMPACT profile")
                elif new_profile_value == 'normal':
                    UIConfig.set_profile(DisplayProfile.NORMAL)
                    logger.info("Switched to NORMAL profile")
                elif new_profile_value == 'auto':
                    detected_profile = UIConfig.detect_optimal_profile()
                    UIConfig.set_profile(detected_profile)
                    logger.info(f"Auto-detected profile: {detected_profile.value}")

                # Re-apply dynamic dimensions with new profile
                if hasattr(self.dockwidget, 'apply_dynamic_dimensions'):
                    self.dockwidget.apply_dynamic_dimensions()

                profile_display = UIConfig.get_profile_name().upper()
                logger.info(f"UI profile changed to {profile_display} mode")

                changes_summary.append(f"Profile: {new_profile_value}")
                self.profile_changed.emit(new_profile_value)

        except Exception as e:
            logger.error(f"Error applying UI_PROFILE change: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _apply_action_bar_position_change(
        self,
        change: Dict[str, Any],
        changes_summary: List[str]
    ) -> None:
        """
        Apply ACTION_BAR_POSITION or ACTION_BAR_VERTICAL_ALIGNMENT change.

        Updates the action bar layout position/alignment dynamically.

        Args:
            change: Change dictionary with 'path', 'index', 'item'
            changes_summary: List to append change description to
        """
        items_keys_values_path = change['path']
        index = change['index']

        is_position_change = (
            'ACTION_BAR_POSITION' in items_keys_values_path
            and 'VERTICAL' not in items_keys_values_path
        )
        is_alignment_change = 'ACTION_BAR_VERTICAL_ALIGNMENT' in items_keys_values_path

        if not is_position_change and not is_alignment_change:
            return

        try:
            value_item = self.dockwidget.config_view.model.itemFromIndex(
                index.siblingAtColumn(1)
            )
            value_data = value_item.data(Qt.UserRole)

            # Handle ChoicesType format
            if isinstance(value_data, dict) and 'value' in value_data:
                new_value = value_data['value']
            else:
                new_value = value_item.data(Qt.DisplayRole) if value_item else None

            if new_value:
                if is_position_change:
                    logger.info(f"ACTION_BAR_POSITION changed to: {new_value}")
                    if hasattr(self.dockwidget, '_action_bar_manager'):
                        self.dockwidget._action_bar_manager.set_position(new_value)
                    changes_summary.append(f"Action bar: {new_value}")
                elif is_alignment_change:
                    logger.info(f"ACTION_BAR_VERTICAL_ALIGNMENT changed to: {new_value}")
                    if hasattr(self.dockwidget, '_action_bar_manager'):
                        self.dockwidget._action_bar_manager.set_vertical_alignment(new_value)
                    changes_summary.append(f"Action bar alignment: {new_value}")

        except Exception as e:
            logger.error(f"Error applying action bar change: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _apply_export_style_change(
        self,
        change: Dict[str, Any],
        changes_summary: List[str]
    ) -> None:
        """
        Apply STYLES_TO_EXPORT configuration change.

        Updates the export style combobox with new value.

        Args:
            change: Change dictionary with 'path', 'index', 'item'
            changes_summary: List to append change description to
        """
        items_keys_values_path = change['path']
        index = change['index']

        if 'STYLES_TO_EXPORT' not in items_keys_values_path:
            return

        try:
            value_item = self.dockwidget.config_view.model.itemFromIndex(
                index.siblingAtColumn(1)
            )
            value_data = value_item.data(Qt.UserRole)

            # Handle ChoicesType format
            if isinstance(value_data, dict) and 'value' in value_data:
                new_style_value = value_data['value']
            else:
                new_style_value = value_item.data(Qt.DisplayRole) if value_item else None

            widgets = getattr(self.dockwidget, 'widgets', {})
            if new_style_value and 'STYLES_TO_EXPORT' in widgets.get('EXPORTING', {}):
                logger.info(f"STYLES_TO_EXPORT changed to: {new_style_value}")

                style_combo = widgets["EXPORTING"]["STYLES_TO_EXPORT"]["WIDGET"]
                index_to_set = style_combo.findText(new_style_value)
                if index_to_set >= 0:
                    style_combo.setCurrentIndex(index_to_set)
                    logger.info(f"Export style updated to: {new_style_value}")
                    changes_summary.append(f"Style: {new_style_value}")

        except Exception as e:
            logger.error(f"Error applying STYLES_TO_EXPORT change: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _apply_export_format_change(
        self,
        change: Dict[str, Any],
        changes_summary: List[str]
    ) -> None:
        """
        Apply DATATYPE_TO_EXPORT configuration change.

        Updates the export format combobox with new value.

        Args:
            change: Change dictionary with 'path', 'index', 'item'
            changes_summary: List to append change description to
        """
        items_keys_values_path = change['path']
        index = change['index']

        if 'DATATYPE_TO_EXPORT' not in items_keys_values_path:
            return

        try:
            value_item = self.dockwidget.config_view.model.itemFromIndex(
                index.siblingAtColumn(1)
            )
            value_data = value_item.data(Qt.UserRole)

            # Handle ChoicesType format
            if isinstance(value_data, dict) and 'value' in value_data:
                new_format_value = value_data['value']
            else:
                new_format_value = value_item.data(Qt.DisplayRole) if value_item else None

            widgets = getattr(self.dockwidget, 'widgets', {})
            if new_format_value and 'DATATYPE_TO_EXPORT' in widgets.get('EXPORTING', {}):
                logger.info(f"DATATYPE_TO_EXPORT changed to: {new_format_value}")

                format_combo = widgets["EXPORTING"]["DATATYPE_TO_EXPORT"]["WIDGET"]
                index_to_set = format_combo.findText(new_format_value)
                if index_to_set >= 0:
                    format_combo.setCurrentIndex(index_to_set)
                    logger.info(f"Export format updated to: {new_format_value}")
                    changes_summary.append(f"Format: {new_format_value}")

        except Exception as e:
            logger.error(f"Error applying DATATYPE_TO_EXPORT change: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _apply_icon_change(
        self,
        change: Dict[str, Any],
        changes_summary: List[str]
    ) -> None:
        """
        Apply ICONS configuration change.

        Args:
            change: Change dictionary with 'path', 'index', 'item'
            changes_summary: List to append change description to
        """
        items_keys_values_path = change['path']

        try:
            if hasattr(self.dockwidget, 'set_widget_icon'):
                self.dockwidget.set_widget_icon(items_keys_values_path)
                changes_summary.append(
                    f"Icon: {' → '.join(items_keys_values_path[-2:])}"
                )
        except Exception as e:
            logger.error(f"Error applying icon change: {e}")

    # === Configuration Persistence ===

    def _save_configuration(self) -> bool:
        """
        Save current configuration to file.

        Returns:
            True if save successful, False otherwise
        """
        try:
            if hasattr(self.dockwidget, 'save_configuration_model'):
                self.dockwidget.save_configuration_model()
                return True
            return False
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            return False

    def _reload_configuration(self) -> bool:
        """
        Reload configuration from file to revert changes.

        Returns:
            True if reload successful, False otherwise
        """
        try:
            from ...config.config import ENV_VARS
            from ..widgets.tree_view import JsonModel

            config_json_path = ENV_VARS.get(
                'CONFIG_JSON_PATH',
                self.dockwidget.plugin_dir + '/config/config.json'
            )

            with open(config_json_path, 'r') as infile:
                self.dockwidget.CONFIG_DATA = json.load(infile)

            # Recreate model with original data
            self.dockwidget.config_model = JsonModel(
                data=self.dockwidget.CONFIG_DATA,
                editable_keys=False,
                editable_values=True,
                plugin_dir=self.dockwidget.plugin_dir
            )

            # Update view
            if hasattr(self.dockwidget, 'config_view') and self.dockwidget.config_view is not None:
                self.dockwidget.config_view.setModel(self.dockwidget.config_model)
                self.dockwidget.config_view.model = self.dockwidget.config_model

            return True

        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
            return False

    def get_current_config(self) -> Dict[str, Any]:
        """
        Get the current configuration data.

        Returns:
            Configuration dictionary
        """
        if hasattr(self.dockwidget, 'CONFIG_DATA'):
            return self.dockwidget.CONFIG_DATA
        return {}

    def set_config_value(self, key: str, value: Any) -> bool:
        """
        Set a configuration value programmatically.

        Args:
            key: Configuration key
            value: New value

        Returns:
            True if set successfully, False otherwise
        """
        try:
            if hasattr(self.dockwidget, 'CONFIG_DATA'):
                self.dockwidget.CONFIG_DATA[key] = value
                self.config_changed.emit(key, value)
                return True
            return False
        except Exception as e:
            logger.error(f"Error setting config value: {e}")
            return False

    # === Helper Methods ===

    def _update_buttonbox_state(self, enabled: bool) -> None:
        """
        Update the OK/Cancel button box state.

        Args:
            enabled: True to enable buttons, False to disable
        """
        if hasattr(self.dockwidget, 'buttonBox'):
            self.dockwidget.buttonBox.setEnabled(enabled)
            state = "enabled" if enabled else "disabled"
            logger.debug(f"Configuration buttons {state}")

    def _show_error(self, message: str) -> None:
        """
        Show error message to user.

        Args:
            message: Error message to display
        """
        try:
            from ...config.feedback_config import show_error
            show_error("FilterMate", message)
        except ImportError:
            logger.error(f"UI Error: {message}")

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            "<ConfigController "
            f"pending={len(self._pending_changes)} "
            f"active={self._is_active}>"
        )
