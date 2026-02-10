"""
PostgresInfoDialog - PostgreSQL Session Information Dialog.

Displays PostgreSQL session information including:
- Connection status
- Current schema
- Active temporary views
- Cleanup options

Extracted from filter_mate_dockwidget.py as part of God Class migration.

Story: MIG-083
Phase: 6 - God Class DockWidget Migration
Pattern: Strangler Fig - Gradual extraction
"""

import logging
from typing import Optional, TYPE_CHECKING

try:
    from qgis.PyQt.QtCore import Qt
    from qgis.PyQt.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
        QLabel, QPushButton, QCheckBox, QGroupBox,
        QListWidget, QMessageBox, QDialogButtonBox,
        QWidget, QFrame
    )
except ImportError:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
        QLabel, QPushButton, QCheckBox, QGroupBox,
        QListWidget, QMessageBox, QDialogButtonBox,
        QWidget, QFrame
    )

if TYPE_CHECKING:
    from ...core.services.postgres_session_manager import PostgresSessionManager
logger = logging.getLogger(__name__)


class PostgresInfoDialog(QDialog):
    """
    Dialog displaying PostgreSQL session information.

    Shows:
    - Connection status and session ID
    - Schema used for temp objects
    - Active temporary views list
    - Cleanup options

    If PostgreSQL is not available (session_manager is None),
    shows a message with installation instructions.
    """

    def __init__(
        self,
        session_manager: Optional['PostgresSessionManager'] = None,
        connection_name: str = "Default",
        parent: Optional[QWidget] = None
    ) -> None:
        """
        Initialize PostgresInfoDialog.

        Args:
            session_manager: PostgresSessionManager instance (or None if unavailable)
            connection_name: Display name for the connection
            parent: Parent widget
        """
        super().__init__(parent)

        self._session_manager = session_manager
        self._connection_name = connection_name

        # UI elements
        self._views_list: Optional[QListWidget] = None
        self._cleanup_btn: Optional[QPushButton] = None
        self._auto_cleanup_cb: Optional[QCheckBox] = None

        self.setWindowTitle(self.tr("PostgreSQL Session Info"))
        self.setMinimumWidth(420)
        self.setMinimumHeight(300)
        self.setModal(True)

        self._setup_ui()

    def tr(self, text: str) -> str:
        """Translate text."""
        try:
            from qgis.PyQt.QtCore import QCoreApplication
            return QCoreApplication.translate("PostgresInfoDialog", text)
        except ImportError:
            return text

    def _setup_ui(self) -> None:
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Check if PostgreSQL is available
        if not self._session_manager:
            self._setup_unavailable_ui(layout)
        else:
            self._setup_available_ui(layout)

        # Button box
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _setup_unavailable_ui(self, layout: QVBoxLayout) -> None:
        """Setup UI when PostgreSQL is not available."""
        # Warning icon and message
        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet("font-size: 32px;")
        icon_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(icon_label)

        message = QLabel(
            "<b>PostgreSQL is not available</b><br><br>"
            "To use PostgreSQL features, install psycopg2:<br><br>"
            "<code>pip install psycopg2-binary</code><br><br>"
            "Then restart QGIS to apply changes."
        )
        message.setAlignment(Qt.AlignCenter)
        message.setWordWrap(True)
        message.setTextFormat(Qt.RichText)
        message.setStyleSheet("color: #666; padding: 20px;")
        layout.addWidget(message)

        layout.addStretch()

    def _setup_available_ui(self, layout: QVBoxLayout) -> None:
        """Setup UI when PostgreSQL is available."""
        # Status header
        status_frame = QFrame()
        status_frame.setStyleSheet(
            "QFrame { background: #27ae60; border-radius: 4px; padding: 8px; }"
        )
        status_layout = QHBoxLayout(status_frame)

        status_label = QLabel("🟢 " + self.tr("PostgreSQL Active"))
        status_label.setStyleSheet("color: white; font-weight: bold; font-size: 12pt;")
        status_layout.addWidget(status_label)
        status_layout.addStretch()

        if self._session_manager.session_id:
            session_label = QLabel(f"Session: {self._session_manager.session_id}")
            session_label.setStyleSheet("color: white; font-size: 10pt;")
            status_layout.addWidget(session_label)

        layout.addWidget(status_frame)

        # Connection info group
        info_group = QGroupBox(self.tr("Connection Info"))
        info_layout = QFormLayout()
        info_layout.setSpacing(8)

        connection_label = QLabel(self._connection_name)
        connection_label.setStyleSheet("font-weight: bold;")
        info_layout.addRow(self.tr("Connection:"), connection_label)

        schema_label = QLabel(self._session_manager.schema)
        schema_label.setStyleSheet("font-family: monospace;")
        info_layout.addRow(self.tr("Temp Schema:"), schema_label)

        status_text = self._session_manager.status.name.replace('_', ' ').title()
        status_value = QLabel(status_text)
        info_layout.addRow(self.tr("Status:"), status_value)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Temporary views group
        views_group = QGroupBox(self.tr("Temporary Views"))
        views_layout = QVBoxLayout()
        views_layout.setSpacing(8)

        self._views_list = QListWidget()
        self._views_list.setMaximumHeight(120)
        self._views_list.setAlternatingRowColors(True)
        views_layout.addWidget(self._views_list)

        # View count label
        view_count = self._session_manager.view_count
        count_label = QLabel(f"{view_count} view(s) in this session")
        count_label.setStyleSheet("color: #888; font-style: italic;")
        views_layout.addWidget(count_label)

        views_group.setLayout(views_layout)
        layout.addWidget(views_group)

        # Cleanup options group
        cleanup_group = QGroupBox(self.tr("Cleanup Options"))
        cleanup_layout = QVBoxLayout()
        cleanup_layout.setSpacing(8)

        # Auto-cleanup checkbox
        self._auto_cleanup_cb = QCheckBox(self.tr("Auto-cleanup on close"))
        self._auto_cleanup_cb.setChecked(self._session_manager.auto_cleanup)
        self._auto_cleanup_cb.setToolTip(
            self.tr("Automatically cleanup temporary views when FilterMate closes.")
        )
        self._auto_cleanup_cb.stateChanged.connect(self._on_auto_cleanup_changed)
        cleanup_layout.addWidget(self._auto_cleanup_cb)

        # Cleanup button
        button_layout = QHBoxLayout()
        self._cleanup_btn = QPushButton(self.tr("🗑️ Cleanup Now"))
        self._cleanup_btn.setToolTip(
            self.tr("Drop all temporary views created by FilterMate in this session.")
        )
        self._cleanup_btn.clicked.connect(self._on_cleanup_clicked)
        button_layout.addWidget(self._cleanup_btn)
        button_layout.addStretch()
        cleanup_layout.addLayout(button_layout)

        cleanup_group.setLayout(cleanup_layout)
        layout.addWidget(cleanup_group)

        # Load initial data
        self._refresh_views()

    def _refresh_views(self) -> None:
        """Refresh the list of temporary views."""
        if not self._views_list or not self._session_manager:
            return

        self._views_list.clear()
        views = self._session_manager.get_session_views()

        if views:
            for view in views:
                self._views_list.addItem(f"📋 {view}")
            self._cleanup_btn.setEnabled(True)
        else:
            self._views_list.addItem(self.tr("(No temporary views)"))
            self._views_list.item(0).setForeground(Qt.gray)
            self._cleanup_btn.setEnabled(False)

    def _on_auto_cleanup_changed(self, state: int) -> None:
        """Handle auto-cleanup checkbox change."""
        if not self._session_manager:
            return

        enabled = state == Qt.Checked
        self._session_manager.auto_cleanup = enabled
        logger.debug(f"Auto-cleanup set to {enabled}")

    def _on_cleanup_clicked(self) -> None:
        """Handle cleanup button click."""
        if not self._session_manager:
            return

        view_count = self._session_manager.view_count

        if view_count == 0:
            QMessageBox.information(
                self,
                self.tr("No Views"),
                self.tr("There are no temporary views to clean up.")
            )
            return

        reply = QMessageBox.question(
            self,
            self.tr("Confirm Cleanup"),
            self.tr(
                f"This will drop {view_count} temporary view(s) created by FilterMate.\n\n"
                "Any unsaved filter results will be lost.\n\n"
                "Continue?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # Note: cleanup requires a database connection
                # The session manager tracks views, but actual cleanup
                # needs to be done through the backend
                result = self._session_manager.cleanup_session_views(None)

                if result.success:
                    QMessageBox.information(
                        self,
                        self.tr("Cleanup Complete"),
                        self.tr(f"Removed {result.views_dropped} temporary view(s).")
                    )
                else:
                    QMessageBox.warning(
                        self,
                        self.tr("Cleanup Issue"),
                        self.tr(f"Some views could not be removed: {result.error_message}")
                    )

                self._refresh_views()

            except Exception as e:
                logger.error(f"Cleanup failed: {e}")
                QMessageBox.critical(
                    self,
                    self.tr("Cleanup Failed"),
                    self.tr(f"Error during cleanup: {str(e)}")
                )

    @property
    def session_manager(self) -> Optional['PostgresSessionManager']:
        """Get the session manager."""
        return self._session_manager

    @property
    def is_available(self) -> bool:
        """Check if PostgreSQL is available."""
        return self._session_manager is not None
