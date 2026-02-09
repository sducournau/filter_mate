"""
Welcome dialog inviting users to join the FilterMate Discord community.
Shown on first plugin launch with a "Don't show again" checkbox.
"""

from qgis.PyQt.QtCore import QCoreApplication, QSettings, Qt, QUrl
from qgis.PyQt.QtGui import QDesktopServices
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Replace with your actual Discord invite link
DISCORD_INVITE_URL = "https://discord.com/channels/1470496084441825303/1470497580520571133"

SETTINGS_KEY = "FilterMate/hideWelcomeDialog"


class WelcomeDialog(QDialog):
    """Welcome dialog promoting the FilterMate Discord community."""

    def __init__(self, parent: QWidget = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("FilterMate — Community"))
        self.setMinimumWidth(480)
        self.setModal(True)
        self._dont_show_cb: QCheckBox = None
        self._setup_ui()

    def tr(self, text: str) -> str:
        return QCoreApplication.translate("WelcomeDialog", text)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        header = QLabel(self.tr("Welcome to FilterMate!"))
        header.setStyleSheet("font-size: 18pt; font-weight: bold;")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)

        # Body
        body = QLabel(self.tr(
            "<p style='font-size: 11pt; line-height: 1.6;'>"
            "Join the <b>FilterMate Discord</b> community to:"
            "</p>"
            "<ul style='font-size: 11pt; line-height: 1.8;'>"
            "<li>Ask questions and get help</li>"
            "<li>Report bugs and get quick feedback</li>"
            "<li>Suggest new features and improvements</li>"
            "<li>Follow the changelog and development roadmap</li>"
            "<li>Share your workflows and maps</li>"
            "</ul>"
        ))
        body.setWordWrap(True)
        body.setTextFormat(Qt.RichText)
        body.setAlignment(Qt.AlignLeft)
        layout.addWidget(body)

        # Discord button
        discord_btn = QPushButton(self.tr("Join Discord"))
        discord_btn.setStyleSheet(
            "QPushButton {"
            "  background-color: #5865F2; color: white;"
            "  font-size: 13pt; font-weight: bold;"
            "  padding: 10px 24px; border-radius: 6px; border: none;"
            "}"
            "QPushButton:hover { background-color: #4752C4; }"
        )
        discord_btn.setCursor(Qt.PointingHandCursor)
        discord_btn.clicked.connect(self._open_discord)
        layout.addWidget(discord_btn, alignment=Qt.AlignCenter)

        layout.addSpacing(8)

        # Don't show again checkbox
        self._dont_show_cb = QCheckBox(self.tr("Don't show this message again"))
        layout.addWidget(self._dont_show_cb, alignment=Qt.AlignCenter)

        # Close button
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self._on_close)
        layout.addWidget(button_box)

    def _open_discord(self) -> None:
        QDesktopServices.openUrl(QUrl(DISCORD_INVITE_URL))

    def _on_close(self) -> None:
        if self._dont_show_cb.isChecked():
            QSettings().setValue(SETTINGS_KEY, True)
        self.reject()

    @staticmethod
    def should_show() -> bool:
        """Return True if the dialog should be displayed."""
        return not QSettings().value(SETTINGS_KEY, False, type=bool)
