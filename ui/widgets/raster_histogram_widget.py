"""
Raster Histogram Widget.

Custom QPainter-based histogram widget with interactive range selection.
Zero external dependencies (no matplotlib, no pyqtgraph).

Features:
    - Draws histogram bars with QPainter
    - Interactive range selection via mouse drag
    - Hover tooltip showing bin value and count
    - Emits rangeChanged signal when user modifies selection
    - set_data() / clear() API for external data feeding

Phase 2: Histogram visualization for raster band analysis.
"""
import logging
from typing import List, Optional, Tuple

from qgis.PyQt.QtCore import (
    QPointF,
    QRectF,
    Qt,
    pyqtSignal,
)
from qgis.PyQt.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainter,
    QPainterPath,
    QPen,
)
from qgis.PyQt.QtWidgets import QToolTip, QWidget

logger = logging.getLogger(__name__)

# Layout constants
_MARGIN_LEFT = 50
_MARGIN_RIGHT = 10
_MARGIN_TOP = 10
_MARGIN_BOTTOM = 30
_MIN_HEIGHT = 160
_MIN_WIDTH = 200

# Colors
_COLOR_BAR = QColor(65, 105, 225)  # Royal blue
_COLOR_BAR_HOVER = QColor(100, 149, 237)  # Cornflower blue
_COLOR_SELECTION = QColor(255, 165, 0, 80)  # Orange, semi-transparent
_COLOR_SELECTION_BORDER = QColor(255, 140, 0)  # Dark orange
_COLOR_GRID = QColor(200, 200, 200)
_COLOR_AXIS = QColor(80, 80, 80)
_COLOR_TEXT = QColor(60, 60, 60)
_COLOR_BG = QColor(250, 250, 250)


class RasterHistogramWidget(QWidget):
    """Custom QPainter-based histogram widget with range selection.

    Signals:
        rangeChanged(float, float): Emitted when user changes the selected range
            via mouse drag. Arguments are (min_value, max_value).
    """

    rangeChanged = pyqtSignal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(_MIN_HEIGHT)
        self.setMinimumWidth(_MIN_WIDTH)
        self.setMouseTracking(True)

        # Data
        self._counts: List[int] = []
        self._bin_edges: List[float] = []
        self._max_count: int = 0

        # Range selection state
        self._range_min: Optional[float] = None
        self._range_max: Optional[float] = None
        self._is_dragging: bool = False
        self._drag_start_x: Optional[int] = None
        self._drag_current_x: Optional[int] = None

        # Hover state
        self._hover_bin: int = -1

    # ================================================================
    # Public API
    # ================================================================

    def set_data(self, counts: List[int], bin_edges: List[float]) -> None:
        """Set histogram data.

        Args:
            counts: List of bin counts (length N).
            bin_edges: List of bin edge values (length N+1).
        """
        if not counts or not bin_edges:
            self.clear()
            return

        if len(bin_edges) != len(counts) + 1:
            logger.warning(
                f"Invalid histogram data: {len(counts)} counts vs "
                f"{len(bin_edges)} edges (expected {len(counts) + 1})"
            )
            self.clear()
            return

        self._counts = list(counts)
        self._bin_edges = list(bin_edges)
        self._max_count = max(counts) if counts else 0

        # Reset selection
        self._range_min = None
        self._range_max = None
        self._hover_bin = -1

        self.update()

    def set_range(self, range_min: float, range_max: float) -> None:
        """Set the selected range programmatically.

        Args:
            range_min: Minimum value of the range.
            range_max: Maximum value of the range.
        """
        if not self._bin_edges:
            return

        data_min = self._bin_edges[0]
        data_max = self._bin_edges[-1]

        self._range_min = max(range_min, data_min)
        self._range_max = min(range_max, data_max)

        self.update()

    def get_range(self) -> Optional[Tuple[float, float]]:
        """Get the currently selected range.

        Returns:
            Tuple of (min_value, max_value) or None if no selection.
        """
        if self._range_min is not None and self._range_max is not None:
            return (self._range_min, self._range_max)
        return None

    def clear(self) -> None:
        """Clear all histogram data and selection."""
        self._counts = []
        self._bin_edges = []
        self._max_count = 0
        self._range_min = None
        self._range_max = None
        self._hover_bin = -1
        self._is_dragging = False
        self.update()

    def has_data(self) -> bool:
        """Return True if histogram data is loaded."""
        return len(self._counts) > 0

    # ================================================================
    # Coordinate Mapping
    # ================================================================

    def _plot_rect(self) -> QRectF:
        """Return the plotting area rectangle (inside margins)."""
        w = self.width()
        h = self.height()
        return QRectF(
            _MARGIN_LEFT,
            _MARGIN_TOP,
            w - _MARGIN_LEFT - _MARGIN_RIGHT,
            h - _MARGIN_TOP - _MARGIN_BOTTOM,
        )

    def _value_to_x(self, value: float) -> float:
        """Map a data value to an x pixel coordinate."""
        if not self._bin_edges or len(self._bin_edges) < 2:
            return _MARGIN_LEFT
        rect = self._plot_rect()
        data_min = self._bin_edges[0]
        data_max = self._bin_edges[-1]
        data_range = data_max - data_min
        if data_range == 0:
            return rect.left()
        return rect.left() + ((value - data_min) / data_range) * rect.width()

    def _x_to_value(self, x: float) -> float:
        """Map an x pixel coordinate to a data value."""
        if not self._bin_edges or len(self._bin_edges) < 2:
            return 0.0
        rect = self._plot_rect()
        data_min = self._bin_edges[0]
        data_max = self._bin_edges[-1]
        data_range = data_max - data_min
        if rect.width() == 0:
            return data_min
        ratio = (x - rect.left()) / rect.width()
        ratio = max(0.0, min(1.0, ratio))
        return data_min + ratio * data_range

    def _count_to_y(self, count: int) -> float:
        """Map a count value to a y pixel coordinate."""
        rect = self._plot_rect()
        if self._max_count == 0:
            return rect.bottom()
        ratio = count / self._max_count
        return rect.bottom() - ratio * rect.height()

    def _x_to_bin(self, x: float) -> int:
        """Map an x pixel coordinate to a bin index, or -1 if outside."""
        if not self._counts:
            return -1
        rect = self._plot_rect()
        if x < rect.left() or x > rect.right():
            return -1
        bin_width_px = rect.width() / len(self._counts)
        if bin_width_px == 0:
            return -1
        idx = int((x - rect.left()) / bin_width_px)
        return max(0, min(idx, len(self._counts) - 1))

    # ================================================================
    # Painting
    # ================================================================

    def paintEvent(self, event):
        """Render the histogram using QPainter."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        # Background
        painter.fillRect(self.rect(), _COLOR_BG)

        if not self._counts:
            self._draw_empty_state(painter)
            painter.end()
            return

        rect = self._plot_rect()

        # Grid lines (horizontal)
        self._draw_grid(painter, rect)

        # Histogram bars
        self._draw_bars(painter, rect)

        # Range selection overlay
        self._draw_selection(painter, rect)

        # Drag preview
        self._draw_drag_preview(painter, rect)

        # Axes
        self._draw_axes(painter, rect)

        painter.end()

    def _draw_empty_state(self, painter: QPainter) -> None:
        """Draw placeholder text when no data is loaded."""
        painter.setPen(QPen(_COLOR_TEXT))
        font = QFont()
        font.setItalic(True)
        painter.setFont(font)
        painter.drawText(
            self.rect(),
            Qt.AlignCenter,
            self.tr("No histogram data"),
        )

    def _draw_grid(self, painter: QPainter, rect: QRectF) -> None:
        """Draw horizontal grid lines."""
        pen = QPen(_COLOR_GRID, 1, Qt.DotLine)
        painter.setPen(pen)

        n_grid_lines = 4
        for i in range(1, n_grid_lines + 1):
            y = rect.bottom() - (i / n_grid_lines) * rect.height()
            painter.drawLine(
                QPointF(rect.left(), y),
                QPointF(rect.right(), y),
            )

    def _draw_bars(self, painter: QPainter, rect: QRectF) -> None:
        """Draw histogram bars."""
        n_bins = len(self._counts)
        if n_bins == 0:
            return

        bin_width_px = rect.width() / n_bins

        for i, count in enumerate(self._counts):
            if count == 0:
                continue

            x = rect.left() + i * bin_width_px
            bar_height = (count / self._max_count) * rect.height() if self._max_count > 0 else 0
            y = rect.bottom() - bar_height

            bar_rect = QRectF(x, y, bin_width_px, bar_height)

            # Highlight hovered bin
            if i == self._hover_bin:
                painter.fillRect(bar_rect, QBrush(_COLOR_BAR_HOVER))
            else:
                painter.fillRect(bar_rect, QBrush(_COLOR_BAR))

            # Bar outline (only if bars are wide enough)
            if bin_width_px > 2:
                painter.setPen(QPen(_COLOR_BG, 0.5))
                painter.drawRect(bar_rect)

    def _draw_selection(self, painter: QPainter, rect: QRectF) -> None:
        """Draw the range selection overlay."""
        if self._range_min is None or self._range_max is None:
            return

        x_min = self._value_to_x(self._range_min)
        x_max = self._value_to_x(self._range_max)

        # Clamp to plot area
        x_min = max(x_min, rect.left())
        x_max = min(x_max, rect.right())

        if x_max <= x_min:
            return

        sel_rect = QRectF(x_min, rect.top(), x_max - x_min, rect.height())

        # Fill
        painter.fillRect(sel_rect, QBrush(_COLOR_SELECTION))

        # Border
        painter.setPen(QPen(_COLOR_SELECTION_BORDER, 1.5))
        painter.drawRect(sel_rect)

    def _draw_drag_preview(self, painter: QPainter, rect: QRectF) -> None:
        """Draw drag preview during mouse drag."""
        if not self._is_dragging or self._drag_start_x is None or self._drag_current_x is None:
            return

        x_min = min(self._drag_start_x, self._drag_current_x)
        x_max = max(self._drag_start_x, self._drag_current_x)

        # Clamp to plot area
        x_min = max(x_min, rect.left())
        x_max = min(x_max, rect.right())

        if x_max <= x_min:
            return

        drag_rect = QRectF(x_min, rect.top(), x_max - x_min, rect.height())

        # Semi-transparent preview
        preview_color = QColor(255, 165, 0, 40)
        painter.fillRect(drag_rect, QBrush(preview_color))
        painter.setPen(QPen(_COLOR_SELECTION_BORDER, 1, Qt.DashLine))
        painter.drawRect(drag_rect)

    def _draw_axes(self, painter: QPainter, rect: QRectF) -> None:
        """Draw axes with labels."""
        pen = QPen(_COLOR_AXIS, 1)
        painter.setPen(pen)

        # X axis
        painter.drawLine(
            QPointF(rect.left(), rect.bottom()),
            QPointF(rect.right(), rect.bottom()),
        )
        # Y axis
        painter.drawLine(
            QPointF(rect.left(), rect.top()),
            QPointF(rect.left(), rect.bottom()),
        )

        # X-axis tick labels (5 ticks)
        font = QFont()
        font.setPointSize(7)
        painter.setFont(font)
        painter.setPen(QPen(_COLOR_TEXT))

        fm = QFontMetrics(font)
        n_ticks = 5
        for i in range(n_ticks + 1):
            ratio = i / n_ticks
            x = rect.left() + ratio * rect.width()
            value = self._bin_edges[0] + ratio * (self._bin_edges[-1] - self._bin_edges[0])

            # Tick mark
            painter.setPen(QPen(_COLOR_AXIS, 1))
            painter.drawLine(
                QPointF(x, rect.bottom()),
                QPointF(x, rect.bottom() + 3),
            )

            # Label
            painter.setPen(QPen(_COLOR_TEXT))
            label = self._format_value(value)
            label_width = fm.horizontalAdvance(label)
            label_x = x - label_width / 2
            painter.drawText(
                QPointF(label_x, rect.bottom() + 15),
                label,
            )

        # Y-axis: max count label
        painter.setPen(QPen(_COLOR_TEXT))
        max_label = str(self._max_count)
        painter.drawText(
            QPointF(2, rect.top() + fm.height()),
            max_label,
        )

    @staticmethod
    def _format_value(value: float) -> str:
        """Format a value for axis labels."""
        if abs(value) >= 10000:
            return f"{value:.0f}"
        elif abs(value) >= 100:
            return f"{value:.1f}"
        elif abs(value) >= 1:
            return f"{value:.2f}"
        else:
            return f"{value:.3f}"

    # ================================================================
    # Mouse Events
    # ================================================================

    def mousePressEvent(self, event):
        """Start range selection drag."""
        if event.button() == Qt.LeftButton and self._counts:
            rect = self._plot_rect()
            if rect.contains(QPointF(event.pos())):
                self._is_dragging = True
                self._drag_start_x = event.pos().x()
                self._drag_current_x = event.pos().x()
                self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Update drag and hover state."""
        if self._is_dragging:
            self._drag_current_x = event.pos().x()
            self.update()
        else:
            # Update hover bin
            new_hover = self._x_to_bin(event.pos().x())
            if new_hover != self._hover_bin:
                self._hover_bin = new_hover
                self.update()

            # Tooltip for hovered bin
            if self._hover_bin >= 0 and self._hover_bin < len(self._counts):
                edge_lo = self._bin_edges[self._hover_bin]
                edge_hi = self._bin_edges[self._hover_bin + 1]
                count = self._counts[self._hover_bin]
                tip = (
                    f"[{self._format_value(edge_lo)} - "
                    f"{self._format_value(edge_hi)}]\n"
                    f"Count: {count}"
                )
                QToolTip.showText(event.globalPos(), tip, self)

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Finalize range selection."""
        if event.button() == Qt.LeftButton and self._is_dragging:
            self._is_dragging = False

            if self._drag_start_x is not None and self._drag_current_x is not None:
                x_min = min(self._drag_start_x, self._drag_current_x)
                x_max = max(self._drag_start_x, self._drag_current_x)

                # Ignore tiny drags (likely a click, not a drag)
                if abs(x_max - x_min) > 3:
                    val_min = self._x_to_value(x_min)
                    val_max = self._x_to_value(x_max)

                    self._range_min = val_min
                    self._range_max = val_max

                    self.rangeChanged.emit(val_min, val_max)

            self._drag_start_x = None
            self._drag_current_x = None
            self.update()

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Double-click clears the selection."""
        if event.button() == Qt.LeftButton:
            self._range_min = None
            self._range_max = None
            self.rangeChanged.emit(0.0, 0.0)  # Signal "no selection"
            self.update()
        super().mouseDoubleClickEvent(event)

    def leaveEvent(self, event):
        """Clear hover state when mouse leaves."""
        self._hover_bin = -1
        self.update()
        super().leaveEvent(event)
