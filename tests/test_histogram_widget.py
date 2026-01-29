# -*- coding: utf-8 -*-
"""
Unit tests for HistogramWidget.

EPIC-2: Raster Integration
US-06: Histogram Visualization

Tests:
- HistogramCanvas rendering
- HistogramWidget functionality
- Range selection interaction
- Theme color handling

Author: FilterMate Team
Date: January 2026
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import List, Optional


# Mock PyQt classes before importing
class MockQt:
    AlignLeft = 1
    AlignCenter = 2
    AlignRight = 4
    LeftButton = 1
    DashLine = 2


class MockQtSignal:
    def __init__(self, *args):
        self._callbacks = []
        self._last_emit = None
    
    def emit(self, *args):
        self._last_emit = args
        for cb in self._callbacks:
            cb(*args)
    
    def connect(self, callback):
        self._callbacks.append(callback)


class MockWidget:
    def __init__(self, parent=None):
        self._visible = True
        self._enabled = True
        self._layout = None
    
    def setVisible(self, visible):
        self._visible = visible
    
    def setEnabled(self, enabled):
        self._enabled = enabled
    
    def isVisible(self):
        return self._visible
    
    def setLayout(self, layout):
        self._layout = layout
    
    def setMinimumHeight(self, h):
        pass
    
    def setMinimumWidth(self, w):
        pass
    
    def setSizePolicy(self, *args):
        pass
    
    def setMouseTracking(self, tracking):
        pass
    
    def palette(self):
        return MockPalette()
    
    def rect(self):
        return MockRect(0, 0, 400, 200)
    
    def width(self):
        return 400
    
    def height(self):
        return 200
    
    def update(self):
        pass


class MockPalette:
    WindowText = 1
    Window = 2
    Base = 3
    
    def color(self, role):
        return MockColor(100, 100, 100)  # Medium gray


class MockColor:
    def __init__(self, r=0, g=0, b=0):
        self._r = r
        self._g = g
        self._b = b
    
    def lightness(self):
        return (self._r + self._g + self._b) // 3
    
    def darker(self, factor=100):
        return MockColor(self._r * 100 // factor, self._g * 100 // factor, self._b * 100 // factor)


class MockRect:
    def __init__(self, x, y, w, h):
        self._x = x
        self._y = y
        self._w = w
        self._h = h


class MockRectF:
    def __init__(self, x, y, w, h):
        self._x = x
        self._y = y
        self._w = w
        self._h = h
    
    def left(self):
        return self._x
    
    def right(self):
        return self._x + self._w
    
    def top(self):
        return self._y
    
    def bottom(self):
        return self._y + self._h
    
    def width(self):
        return self._w
    
    def height(self):
        return self._h
    
    def center(self):
        return MockPointF(self._x + self._w / 2, self._y + self._h / 2)


class MockPointF:
    def __init__(self, x, y):
        self._x = x
        self._y = y
    
    def x(self):
        return self._x
    
    def y(self):
        return self._y


class MockLabel(MockWidget):
    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._text = text
    
    def setText(self, text):
        self._text = text
    
    def text(self):
        return self._text
    
    def setStyleSheet(self, style):
        pass
    
    def setAlignment(self, alignment):
        pass
    
    def setToolTip(self, tip):
        pass


class MockFrame(MockWidget):
    StyledPanel = 1
    
    def setFrameShape(self, shape):
        pass


class MockLayout:
    def __init__(self):
        self._widgets = []
    
    def addWidget(self, widget, *args):
        self._widgets.append(widget)
    
    def addLayout(self, layout):
        self._widgets.append(layout)
    
    def addStretch(self):
        pass
    
    def setContentsMargins(self, *args):
        pass
    
    def setSpacing(self, spacing):
        pass


class MockVBoxLayout(MockLayout):
    pass


class MockHBoxLayout(MockLayout):
    pass


class MockSizePolicy:
    Expanding = 1
    
    def __init__(self, *args):
        pass


# Mock dataclass for HistogramData
@dataclass
class MockHistogramData:
    band_index: int
    counts: List[int]
    bin_edges: List[float]
    total_pixels: int
    null_count: int
    is_sampled: bool = False
    sample_fraction: float = 1.0


class TestHistogramCanvas(unittest.TestCase):
    """Test cases for HistogramCanvas widget."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.patches = []
        
        qgis_pyqt_patch = patch.dict('sys.modules', {
            'qgis': Mock(),
            'qgis.PyQt': Mock(),
            'qgis.PyQt.QtCore': Mock(Qt=MockQt, pyqtSignal=MockQtSignal, QPointF=MockPointF, QRectF=MockRectF),
            'qgis.PyQt.QtWidgets': Mock(
                QWidget=MockWidget,
                QLabel=MockLabel,
                QVBoxLayout=MockVBoxLayout,
                QHBoxLayout=MockHBoxLayout,
                QFrame=MockFrame,
                QSizePolicy=MockSizePolicy,
            ),
            'qgis.PyQt.QtGui': Mock(
                QPainter=Mock,
                QPen=Mock,
                QBrush=Mock,
                QColor=MockColor,
                QPainterPath=Mock,
                QFont=Mock,
                QFontMetrics=Mock,
                QPalette=MockPalette,
            ),
        })
        qgis_pyqt_patch.start()
        self.patches.append(qgis_pyqt_patch)
    
    def tearDown(self):
        """Clean up patches."""
        for p in self.patches:
            p.stop()
    
    def test_canvas_set_histogram_data(self):
        """Test setting histogram data on canvas."""
        from ui.widgets.histogram_widget import HistogramCanvas
        
        canvas = HistogramCanvas()
        
        data = MockHistogramData(
            band_index=1,
            counts=[10, 20, 30, 40, 50, 40, 30, 20, 10],
            bin_edges=[0.0, 28.3, 56.6, 85.0, 113.3, 141.6, 170.0, 198.3, 226.6, 255.0],
            total_pixels=250,
            null_count=0
        )
        
        canvas.set_histogram_data(data)
        
        self.assertEqual(len(canvas._bin_counts), 9)
        self.assertEqual(len(canvas._bin_edges), 10)
        self.assertEqual(canvas._range_min, 0.0)
        self.assertEqual(canvas._range_max, 255.0)
    
    def test_canvas_set_selection_range(self):
        """Test setting selection range on canvas."""
        from ui.widgets.histogram_widget import HistogramCanvas
        
        canvas = HistogramCanvas()
        
        data = MockHistogramData(
            band_index=1,
            counts=[10, 20, 30, 40, 50],
            bin_edges=[0.0, 51.0, 102.0, 153.0, 204.0, 255.0],
            total_pixels=150,
            null_count=0
        )
        
        canvas.set_histogram_data(data)
        canvas.set_selection_range(50.0, 150.0)
        
        self.assertEqual(canvas._range_min, 50.0)
        self.assertEqual(canvas._range_max, 150.0)
    
    def test_canvas_reset_selection(self):
        """Test resetting selection to full range."""
        from ui.widgets.histogram_widget import HistogramCanvas
        
        canvas = HistogramCanvas()
        canvas.range_changed = MockQtSignal(float, float)
        
        data = MockHistogramData(
            band_index=1,
            counts=[10, 20, 30],
            bin_edges=[0.0, 85.0, 170.0, 255.0],
            total_pixels=60,
            null_count=0
        )
        
        canvas.set_histogram_data(data)
        canvas.set_selection_range(100.0, 200.0)
        canvas.reset_selection()
        
        self.assertEqual(canvas._range_min, 0.0)
        self.assertEqual(canvas._range_max, 255.0)
    
    def test_canvas_clear(self):
        """Test clearing canvas data."""
        from ui.widgets.histogram_widget import HistogramCanvas
        
        canvas = HistogramCanvas()
        
        data = MockHistogramData(
            band_index=1,
            counts=[10, 20, 30],
            bin_edges=[0.0, 85.0, 170.0, 255.0],
            total_pixels=60,
            null_count=0
        )
        
        canvas.set_histogram_data(data)
        canvas.clear()
        
        self.assertIsNone(canvas._histogram_data)
        self.assertEqual(len(canvas._bin_counts), 0)
        self.assertEqual(len(canvas._bin_edges), 0)
    
    def test_is_bin_selected_full_range(self):
        """Test bin selection with no range specified."""
        from ui.widgets.histogram_widget import HistogramCanvas
        
        canvas = HistogramCanvas()
        canvas._range_min = None
        canvas._range_max = None
        
        # All bins should be selected when no range
        self.assertTrue(canvas._is_bin_selected(0, 100))
        self.assertTrue(canvas._is_bin_selected(100, 200))
    
    def test_is_bin_selected_partial_range(self):
        """Test bin selection with partial range."""
        from ui.widgets.histogram_widget import HistogramCanvas
        
        canvas = HistogramCanvas()
        canvas._range_min = 50.0
        canvas._range_max = 150.0
        
        # Bin fully inside range
        self.assertTrue(canvas._is_bin_selected(60, 100))
        
        # Bin partially overlapping
        self.assertTrue(canvas._is_bin_selected(0, 60))
        self.assertTrue(canvas._is_bin_selected(140, 200))
        
        # Bin fully outside range
        self.assertFalse(canvas._is_bin_selected(0, 50))
        self.assertFalse(canvas._is_bin_selected(150, 200))


class TestHistogramWidget(unittest.TestCase):
    """Test cases for HistogramWidget."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.patches = []
        
        qgis_pyqt_patch = patch.dict('sys.modules', {
            'qgis': Mock(),
            'qgis.PyQt': Mock(),
            'qgis.PyQt.QtCore': Mock(Qt=MockQt, pyqtSignal=MockQtSignal, QPointF=MockPointF, QRectF=MockRectF),
            'qgis.PyQt.QtWidgets': Mock(
                QWidget=MockWidget,
                QLabel=MockLabel,
                QVBoxLayout=MockVBoxLayout,
                QHBoxLayout=MockHBoxLayout,
                QFrame=MockFrame,
                QSizePolicy=MockSizePolicy,
            ),
            'qgis.PyQt.QtGui': Mock(
                QPainter=Mock,
                QPen=Mock,
                QBrush=Mock,
                QColor=MockColor,
                QPainterPath=Mock,
                QFont=Mock,
                QFontMetrics=Mock,
                QPalette=MockPalette,
            ),
        })
        qgis_pyqt_patch.start()
        self.patches.append(qgis_pyqt_patch)
    
    def tearDown(self):
        """Clean up patches."""
        for p in self.patches:
            p.stop()
    
    def test_widget_creation(self):
        """Test HistogramWidget is created correctly."""
        from ui.widgets.histogram_widget import HistogramWidget
        
        widget = HistogramWidget()
        
        self.assertIsNotNone(widget._canvas)
        self.assertIsNotNone(widget._band_label)
        self.assertIsNotNone(widget._selection_label)
    
    def test_widget_set_histogram_data(self):
        """Test setting histogram data on widget."""
        from ui.widgets.histogram_widget import HistogramWidget
        
        widget = HistogramWidget()
        
        data = MockHistogramData(
            band_index=1,
            counts=[10, 20, 30, 40, 50],
            bin_edges=[0.0, 51.0, 102.0, 153.0, 204.0, 255.0],
            total_pixels=150,
            null_count=0,
            is_sampled=True
        )
        
        widget.set_histogram_data(data, band_name="Red", is_sampled=True)
        
        # Check that sampled indicator is shown
        self.assertTrue(widget._sampled_label._visible)
        self.assertEqual(widget._band_label._text, "Band: Red")
    
    def test_widget_clear(self):
        """Test clearing widget."""
        from ui.widgets.histogram_widget import HistogramWidget
        
        widget = HistogramWidget()
        
        data = MockHistogramData(
            band_index=1,
            counts=[10, 20],
            bin_edges=[0.0, 127.5, 255.0],
            total_pixels=30,
            null_count=0
        )
        
        widget.set_histogram_data(data)
        widget.clear()
        
        self.assertEqual(widget._band_label._text, "Band: -")
        self.assertFalse(widget._sampled_label._visible)
    
    def test_widget_format_value(self):
        """Test value formatting."""
        from ui.widgets.histogram_widget import HistogramWidget
        
        widget = HistogramWidget()
        
        # Large value
        self.assertEqual(widget._format_value(10000), "10,000")
        
        # Medium value
        self.assertEqual(widget._format_value(42.567), "42.57")
        
        # Small value
        self.assertEqual(widget._format_value(0.00123), "0.0012")
    
    def test_widget_selection_range_property(self):
        """Test selection_range property."""
        from ui.widgets.histogram_widget import HistogramWidget
        
        widget = HistogramWidget()
        
        data = MockHistogramData(
            band_index=1,
            counts=[10, 20, 30],
            bin_edges=[0.0, 85.0, 170.0, 255.0],
            total_pixels=60,
            null_count=0
        )
        
        widget.set_histogram_data(data)
        widget.set_selection_range(50.0, 200.0)
        
        min_val, max_val = widget.selection_range
        self.assertEqual(min_val, 50.0)
        self.assertEqual(max_val, 200.0)


class TestHistogramCanvasValueConversion(unittest.TestCase):
    """Test value-to-coordinate conversion functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.patches = []
        
        qgis_pyqt_patch = patch.dict('sys.modules', {
            'qgis': Mock(),
            'qgis.PyQt': Mock(),
            'qgis.PyQt.QtCore': Mock(Qt=MockQt, pyqtSignal=MockQtSignal, QPointF=MockPointF, QRectF=MockRectF),
            'qgis.PyQt.QtWidgets': Mock(
                QWidget=MockWidget,
                QSizePolicy=MockSizePolicy,
            ),
            'qgis.PyQt.QtGui': Mock(
                QPainter=Mock,
                QPen=Mock,
                QBrush=Mock,
                QColor=MockColor,
                QPainterPath=Mock,
                QFont=Mock,
                QFontMetrics=Mock,
                QPalette=MockPalette,
            ),
        })
        qgis_pyqt_patch.start()
        self.patches.append(qgis_pyqt_patch)
    
    def tearDown(self):
        """Clean up patches."""
        for p in self.patches:
            p.stop()
    
    def test_value_to_x_conversion(self):
        """Test value to X coordinate conversion."""
        from ui.widgets.histogram_widget import HistogramCanvas
        
        canvas = HistogramCanvas()
        canvas._bin_edges = [0.0, 255.0]
        
        rect = MockRectF(50, 10, 300, 150)  # Draw area
        
        # Min value should be at left
        x_min = canvas._value_to_x(0.0, rect)
        self.assertEqual(x_min, 50.0)
        
        # Max value should be at right
        x_max = canvas._value_to_x(255.0, rect)
        self.assertEqual(x_max, 350.0)
        
        # Middle value should be at center
        x_mid = canvas._value_to_x(127.5, rect)
        self.assertEqual(x_mid, 200.0)
    
    def test_x_to_value_conversion(self):
        """Test X coordinate to value conversion."""
        from ui.widgets.histogram_widget import HistogramCanvas
        
        canvas = HistogramCanvas()
        canvas._bin_edges = [0.0, 255.0]
        
        rect = MockRectF(50, 10, 300, 150)  # Draw area
        
        # Left should be min value
        val_min = canvas._x_to_value(50.0, rect)
        self.assertEqual(val_min, 0.0)
        
        # Right should be max value
        val_max = canvas._x_to_value(350.0, rect)
        self.assertEqual(val_max, 255.0)
        
        # Center should be middle value
        val_mid = canvas._x_to_value(200.0, rect)
        self.assertEqual(val_mid, 127.5)


if __name__ == '__main__':
    unittest.main()
