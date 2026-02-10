"""
FilterMate Dual Mode Toggle Widget.

Segment control for switching between Vector and Raster exploration modes.
Auto-detects layer type from QGIS layer tree and emits modeChanged signal.
"""
import logging
from enum import IntEnum

from qgis.PyQt.QtCore import pyqtSignal, Qt, QSize
from qgis.PyQt.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QButtonGroup, QSizePolicy
)

logger = logging.getLogger(__name__)


class DualMode(IntEnum):
    """Exploration mode enum."""
    VECTOR = 0
    RASTER = 1


class DualModeToggle(QWidget):
    """Segment control for Vector/Raster mode switching.

    Emits modeChanged(int) when the user clicks a button or when
    setMode() is called programmatically (unless blocked).

    Usage:
        toggle = DualModeToggle(parent)
        toggle.modeChanged.connect(on_mode_changed)

        # Programmatic switch (emits signal):
        toggle.setMode(DualMode.RASTER)

        # Read current mode:
        current = toggle.mode()
    """

    modeChanged = pyqtSignal(int)  # 0=vector, 1=raster

    # QSS for segment-control look
    _STYLE = """
        QPushButton {
            border: 1px solid palette(mid);
            padding: 2px 6px;
            font-size: 9pt;
            font-weight: bold;
            min-height: 20px;
        }
        QPushButton:checked {
            background-color: palette(highlight);
            color: palette(highlighted-text);
            border-color: palette(highlight);
        }
        QPushButton:!checked {
            background-color: palette(button);
            color: palette(button-text);
        }
        QPushButton:!checked:hover {
            background-color: palette(midlight);
        }
        QPushButton#btn_vector {
            border-top-left-radius: 4px;
            border-bottom-left-radius: 4px;
            border-right: none;
        }
        QPushButton#btn_raster {
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dual_mode_toggle")

        self._btn_vector = QPushButton("V")
        self._btn_vector.setObjectName("btn_vector")
        self._btn_vector.setToolTip(self.tr("Vector mode"))
        self._btn_vector.setCheckable(True)
        self._btn_vector.setChecked(True)
        self._btn_vector.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self._btn_raster = QPushButton("R")
        self._btn_raster.setObjectName("btn_raster")
        self._btn_raster.setToolTip(self.tr("Raster mode"))
        self._btn_raster.setCheckable(True)
        self._btn_raster.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)
        self._btn_group.addButton(self._btn_vector, DualMode.VECTOR)
        self._btn_group.addButton(self._btn_raster, DualMode.RASTER)
        self._btn_group.idClicked.connect(self._on_button_clicked)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._btn_vector)
        layout.addWidget(self._btn_raster)

        self.setStyleSheet(self._STYLE)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def mode(self) -> int:
        """Return current mode (DualMode.VECTOR or DualMode.RASTER)."""
        return self._btn_group.checkedId()

    def setMode(self, mode: int) -> None:
        """Switch to given mode programmatically.

        Args:
            mode: DualMode.VECTOR (0) or DualMode.RASTER (1)
        """
        if mode == self.mode():
            return
        btn = self._btn_group.button(mode)
        if btn:
            btn.setChecked(True)
            self.modeChanged.emit(mode)
            logger.debug(f"DualModeToggle: switched to {'RASTER' if mode else 'VECTOR'}")

    def _on_button_clicked(self, button_id: int) -> None:
        """Handle user click on toggle button."""
        self.modeChanged.emit(button_id)
        logger.debug(f"DualModeToggle: user clicked {'RASTER' if button_id else 'VECTOR'}")
