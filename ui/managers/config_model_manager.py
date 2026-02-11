# -*- coding: utf-8 -*-
"""
ConfigModelManager - Extracted from filter_mate_dockwidget.py

v5.0 Phase 2 P2-2 E2: Extract configuration model management
from God Class (7,029 lines).

Manages:
    - Configuration JSON model creation and lifecycle
    - Config change tracking (pending changes)
    - Config model signal connections (itemChanged)
    - Config view setup (SearchableJsonView / JsonView)
    - Reload button and plugin reload
    - OK/Cancel button handling for config panel

Author: FilterMate Team
Created: February 2026
"""

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from filter_mate_dockwidget import FilterMateDockWidget

logger = logging.getLogger(__name__)


class ConfigModelManager:
    """
    Manages the configuration model, view, and persistence for FilterMate.

    Extracted from FilterMateDockWidget to reduce God Class complexity.

    Args:
        dockwidget: Reference to FilterMateDockWidget instance.
    """

    def __init__(self, dockwidget: 'FilterMateDockWidget'):
        self.dockwidget = dockwidget
        logger.debug("ConfigModelManager initialized")

    # ========================================
    # CONFIG CHANGE TRACKING
    # ========================================

    def data_changed_configuration_model(self, input_data=None):
        """Track configuration changes without applying immediately.

        Delegates to ConfigController if available.
        """
        dw = self.dockwidget
        if dw._controller_integration:
            dw._controller_integration.delegate_config_data_changed(input_data)
            # Enable OK/Cancel buttons when changes are pending
            if (
                hasattr(dw, 'buttonBox')
                and dw._controller_integration.delegate_config_has_pending_changes()
            ):
                dw.buttonBox.setEnabled(True)

    def apply_pending_config_changes(self):
        """Apply all pending configuration changes when OK button is clicked.

        Delegates to ConfigController if available, falls back to local reset.
        """
        dw = self.dockwidget
        if dw._controller_integration:
            if dw._controller_integration.delegate_config_apply_pending_changes():
                # Disable OK/Cancel buttons after changes applied
                if hasattr(dw, 'buttonBox'):
                    dw.buttonBox.setEnabled(False)
                return

        # Clear local state as fallback
        dw.pending_config_changes = []
        dw.config_changes_pending = False

    def cancel_pending_config_changes(self):
        """Cancel pending configuration changes.

        Disconnects signal before recreating model to prevent multiple
        signal connections (v4.0.7 FIX).
        """
        from ...infrastructure.feedback import show_error
        from ...config.config import ENV_VARS
        dw = self.dockwidget
        if not dw.config_changes_pending or not dw.pending_config_changes:
            return
        try:
            # Disconnect signal before replacing model
            self.disconnect_config_model_signal()

            config_path = ENV_VARS.get(
                'CONFIG_JSON_PATH', dw.plugin_dir + '/config/config.json'
            )
            with open(config_path, 'r') as f:
                dw.CONFIG_DATA = json.load(f)

            from ...ui.widgets.json_view.model import JsonModel
            dw.config_model = JsonModel(
                data=dw.CONFIG_DATA,
                editable_keys=False,
                editable_values=True,
                plugin_dir=dw.plugin_dir,
            )
            if hasattr(dw, 'config_view') and dw.config_view:
                dw.config_view.setModel(dw.config_model)
                dw.config_view.model = dw.config_model

            # Reconnect signal to new model
            self.connect_config_model_signal()

            dw.pending_config_changes = []
            dw.config_changes_pending = False
            if hasattr(dw, 'buttonBox'):
                dw.buttonBox.setEnabled(False)
        except Exception as e:
            show_error(
                "FilterMate",
                dw.tr("Error cancelling changes: {0}").format(str(e))
            )

    # ========================================
    # OK / CANCEL BUTTON HANDLERS
    # ========================================

    def on_config_buttonbox_accepted(self):
        """Handle OK button click in config panel."""
        dw = self.dockwidget
        logger.info("Configuration OK button clicked")
        if (
            dw._controller_integration
            and dw._controller_integration.delegate_config_apply_pending_changes()
        ):
            return
        self.apply_pending_config_changes()

    def on_config_buttonbox_rejected(self):
        """Handle Cancel button click in config panel."""
        dw = self.dockwidget
        logger.info("Configuration Cancel button clicked")
        if (
            dw._controller_integration
            and dw._controller_integration.delegate_config_cancel_pending_changes()
        ):
            return
        self.cancel_pending_config_changes()

    # ========================================
    # MODEL RELOAD & SAVE
    # ========================================

    def reload_configuration_model(self):
        """Reload config model from CONFIG_DATA and save to file."""
        from ...config.config import ENV_VARS
        dw = self.dockwidget
        if not dw.widgets_initialized:
            return
        try:
            from ...ui.widgets.json_view.model import JsonModel
            dw.config_model = JsonModel(
                data=dw.CONFIG_DATA,
                editable_keys=False,
                editable_values=True,
                plugin_dir=dw.plugin_dir,
            )
            if hasattr(dw, 'config_view') and dw.config_view:
                dw.config_view.setModel(dw.config_model)
                dw.config_view.model = dw.config_model
            config_path = ENV_VARS.get(
                'CONFIG_JSON_PATH', dw.plugin_dir + '/config/config.json'
            )
            with open(config_path, 'w') as f:
                f.write(json.dumps(dw.CONFIG_DATA, indent=4))
        except Exception as e:
            logger.error(f"Error reloading configuration model: {e}")

    def save_configuration_model(self):
        """Save current config model to file."""
        from ...config.config import ENV_VARS
        dw = self.dockwidget
        if not dw.widgets_initialized:
            return
        dw.CONFIG_DATA = dw.config_model.serialize()
        config_path = ENV_VARS.get(
            'CONFIG_JSON_PATH', dw.plugin_dir + '/config/config.json'
        )
        with open(config_path, 'w') as f:
            f.write(json.dumps(dw.CONFIG_DATA, indent=4))

    # ========================================
    # SIGNAL MANAGEMENT
    # ========================================

    def disconnect_config_model_signal(self):
        """Disconnect itemChanged signal from config_model.

        Prevents signal accumulation when model is recreated (v4.0.7 FIX).
        """
        dw = self.dockwidget
        try:
            if hasattr(dw, 'config_model') and dw.config_model is not None:
                try:
                    dw.config_model.itemChanged.disconnect(
                        dw.data_changed_configuration_model
                    )
                    logger.debug("Config model itemChanged signal disconnected")
                except (TypeError, RuntimeError):
                    # Signal was not connected or already disconnected
                    pass
        except Exception as e:
            logger.debug(f"Could not disconnect config_model signal: {e}")

    def connect_config_model_signal(self):
        """Connect itemChanged signal to config_model.

        Centralized connection method for consistency (v4.0.7 FIX).
        """
        dw = self.dockwidget
        try:
            if hasattr(dw, 'config_model') and dw.config_model is not None:
                dw.config_model.itemChanged.connect(
                    dw.data_changed_configuration_model
                )
                logger.debug("Config model itemChanged signal connected")
        except Exception as e:
            logger.error(f"Could not connect config_model signal: {e}")

    # ========================================
    # MODEL & VIEW SETUP
    # ========================================

    def manage_configuration_model(self):
        """Setup config model, view, and signals.

        Creates JsonModel from CONFIG_DATA, sets up SearchableJsonView
        (with fallback to standard JsonView), connects signals,
        and adds reload button.
        """
        from qgis.PyQt.QtCore import Qt
        from qgis.PyQt import QtGui, QtWidgets
        from qgis.PyQt.QtCore import QCoreApplication
        dw = self.dockwidget
        try:
            # Disconnect any existing signal first
            self.disconnect_config_model_signal()

            from ...ui.widgets.json_view.model import JsonModel
            dw.config_model = JsonModel(
                data=dw.CONFIG_DATA,
                editable_keys=False,
                editable_values=True,
                plugin_dir=dw.plugin_dir,
            )

            # Use SearchableJsonView with integrated search bar
            try:
                from ui.widgets.json_view import SearchableJsonView
                dw.config_view_container = SearchableJsonView(
                    dw.config_model, dw.plugin_dir
                )
                dw.config_view = dw.config_view_container.json_view
                dw.CONFIGURATION.layout().insertWidget(0, dw.config_view_container)
                dw.config_view_container.setAnimated(True)
                dw.config_view_container.setEnabled(True)
                dw.config_view_container.show()
                logger.debug("Using SearchableJsonView with search bar")
            except ImportError:
                # Fallback to standard JsonView
                from ...ui.widgets.json_view.view import JsonView
                dw.config_view = JsonView(dw.config_model, dw.plugin_dir)
                dw.config_view_container = None
                dw.CONFIGURATION.layout().insertWidget(0, dw.config_view)
                dw.config_view.setAnimated(True)
                dw.config_view.setEnabled(True)
                dw.config_view.show()
                logger.debug(
                    "Using standard JsonView (SearchableJsonView not available)"
                )

            # Connect signal using centralized method
            self.connect_config_model_signal()
            self.setup_reload_button()

            if hasattr(dw, 'buttonBox'):
                dw.buttonBox.setEnabled(False)
                dw.buttonBox.accepted.connect(dw.on_config_buttonbox_accepted)
                dw.buttonBox.rejected.connect(dw.on_config_buttonbox_rejected)
        except Exception as e:
            logger.error(f"Error creating configuration model: {e}")

    def setup_reload_button(self):
        """Setup Reload Plugin button in config panel."""
        from qgis.PyQt import QtGui, QtWidgets
        from qgis.PyQt.QtCore import Qt, QCoreApplication
        dw = self.dockwidget
        try:
            dw.pushButton_reload_plugin = QtWidgets.QPushButton(
                "Reload Plugin"
            )
            dw.pushButton_reload_plugin.setObjectName("pushButton_reload_plugin")
            dw.pushButton_reload_plugin.setToolTip(
                QCoreApplication.translate(
                    "FilterMate",
                    "Reload the plugin to apply layout changes (action bar position)"
                )
            )
            dw.pushButton_reload_plugin.setCursor(
                QtGui.QCursor(Qt.PointingHandCursor)
            )
            dw.pushButton_reload_plugin.clicked.connect(
                dw._on_reload_button_clicked
            )
            if dw.CONFIGURATION.layout():
                dw.CONFIGURATION.layout().insertWidget(
                    dw.CONFIGURATION.layout().count() - 1,
                    dw.pushButton_reload_plugin
                )
        except Exception as e:
            logger.error(f"Error setting up reload button: {e}")

    def on_reload_button_clicked(self):
        """Reload plugin after saving config."""
        from qgis.PyQt.QtWidgets import QMessageBox
        dw = self.dockwidget
        if dw.config_changes_pending and dw.pending_config_changes:
            self.apply_pending_config_changes()
        self.save_configuration_model()
        if QMessageBox.question(
            dw,
            dw.tr("Reload Plugin"),
            dw.tr(
                "Do you want to reload FilterMate to apply all "
                "configuration changes?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        ) == QMessageBox.Yes:
            dw.reload_plugin()
