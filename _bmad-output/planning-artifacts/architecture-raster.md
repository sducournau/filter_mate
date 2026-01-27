---
title: "Architecture Document - FilterMate Raster Integration"
epic: "EPIC-2"
version: "1.0"
date: "2026-01-27"
status: "Draft"
prd: "prd-raster.md"
---

# Architecture Document - FilterMate Raster Integration (EPIC-2)

## 1. Executive Summary

Ce document décrit l'architecture technique pour l'intégration raster dans FilterMate v5.0. L'architecture suit le pattern hexagonal existant et ajoute ~1,700 lignes de nouveau code.

## 2. Architecture Overview

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        UI LAYER                                  │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ filter_mate_     │  │ RasterController │  │ HistogramWidget│  │
│  │ dockwidget.py    │  │                  │  │               │  │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘  │
│           │                     │                     │          │
└───────────┼─────────────────────┼─────────────────────┼──────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      CORE LAYER (Ports)                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ RasterPort       │  │ RasterService    │  │ RasterTask    │  │
│  │ (Interface)      │  │ (Business Logic) │  │ (Async Ops)   │  │
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬───────┘  │
│           │                     │                     │          │
└───────────┼─────────────────────┼─────────────────────┼──────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ADAPTERS LAYER                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ QGISRasterBackend│  │ GDALRasterBackend│  │ BackendFactory│  │
│  │ (QgsRaster* API) │  │ (Windowed Read)  │  │               │  │
│  └──────────────────┘  └──────────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Module Structure

```
filter_mate/
├── core/
│   ├── ports/
│   │   └── raster_port.py          # 🆕 Interface abstraite
│   ├── services/
│   │   └── raster_service.py       # 🆕 Logique métier raster
│   └── tasks/
│       └── raster_task.py          # 🆕 Opérations async (QgsTask)
├── adapters/
│   └── backends/
│       └── raster/
│           ├── __init__.py         # 🆕 Exports
│           ├── qgis_backend.py     # 🆕 QgsRasterLayer adapter
│           └── gdal_backend.py     # 🆕 GDAL windowed reading
└── ui/
    ├── widgets/
    │   └── histogram_widget.py     # 🆕 Widget histogramme PyQt5
    └── controllers/
        └── raster_controller.py    # 🆕 Controller UI raster
```

## 3. Component Specifications

### 3.1 RasterPort (Interface)

```python
# core/ports/raster_port.py
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

@dataclass
class RasterStats:
    """Statistics for a raster band."""
    min: float
    max: float
    mean: float
    std: float
    nodata: Optional[float]
    pixel_count: int
    
@dataclass
class HistogramData:
    """Histogram data for visualization."""
    bins: List[float]
    counts: List[int]
    bin_width: float
    
class RasterPort(ABC):
    """Abstract interface for raster operations."""
    
    @abstractmethod
    def get_stats(self, layer_id: str, band: int = 1) -> RasterStats:
        """Get statistics for a raster band."""
        pass
    
    @abstractmethod
    def get_histogram(self, layer_id: str, band: int = 1, 
                      num_bins: int = 256) -> HistogramData:
        """Get histogram data for a raster band."""
        pass
    
    @abstractmethod
    def apply_transparency(self, layer_id: str, min_val: float, 
                          max_val: float, band: int = 1) -> bool:
        """Apply transparency mask to pixels outside range."""
        pass
    
    @abstractmethod
    def identify_pixel(self, layer_id: str, x: float, y: float) -> Dict:
        """Get pixel values at coordinates."""
        pass
    
    @abstractmethod
    def reset_transparency(self, layer_id: str) -> bool:
        """Remove transparency mask."""
        pass
```

### 3.2 RasterService (Business Logic)

```python
# core/services/raster_service.py
from typing import Optional, Callable
from qgis.core import QgsRasterLayer, QgsProject
from ..ports.raster_port import RasterPort, RasterStats, HistogramData

class RasterService:
    """Business logic for raster operations."""
    
    def __init__(self, backend: RasterPort):
        self._backend = backend
        self._cache: Dict[str, RasterStats] = {}
        
    def get_layer_stats(self, layer: QgsRasterLayer, 
                        use_cache: bool = True) -> RasterStats:
        """Get stats with optional caching."""
        layer_id = layer.id()
        if use_cache and layer_id in self._cache:
            return self._cache[layer_id]
        
        stats = self._backend.get_stats(layer_id)
        self._cache[layer_id] = stats
        return stats
    
    def apply_range_filter(self, layer: QgsRasterLayer,
                          min_val: float, max_val: float) -> bool:
        """Apply cell filter with range."""
        return self._backend.apply_transparency(layer.id(), min_val, max_val)
    
    def apply_expression_filter(self, layer: QgsRasterLayer,
                                expression: str) -> bool:
        """Apply filter from expression string."""
        # Parse expression and convert to transparency rules
        parsed = self._parse_expression(expression)
        if parsed:
            return self._backend.apply_transparency(
                layer.id(), parsed['min'], parsed['max']
            )
        return False
    
    def get_selection_stats(self, layer: QgsRasterLayer,
                           min_val: float, max_val: float) -> RasterStats:
        """Get stats for selected range only."""
        # Calculate stats on subset
        return self._backend.get_stats_for_range(
            layer.id(), min_val, max_val
        )
    
    def _parse_expression(self, expr: str) -> Optional[Dict]:
        """Parse QGIS-style expression to min/max range."""
        # Simple parser for expressions like: "band1" > 500 AND "band1" < 1000
        import re
        pattern = r'"?(\w+)"?\s*([><=]+)\s*(\d+\.?\d*)'
        matches = re.findall(pattern, expr)
        
        result = {'min': float('-inf'), 'max': float('inf')}
        for field, op, value in matches:
            val = float(value)
            if op in ('>', '>='):
                result['min'] = max(result['min'], val)
            elif op in ('<', '<='):
                result['max'] = min(result['max'], val)
        
        return result if result['min'] != float('-inf') or result['max'] != float('inf') else None
```

### 3.3 RasterTask (Async Operations)

```python
# core/tasks/raster_task.py
from qgis.core import QgsTask, QgsRasterLayer
from qgis.PyQt.QtCore import pyqtSignal
import numpy as np

class RasterHistogramTask(QgsTask):
    """Background task for histogram calculation."""
    
    histogramReady = pyqtSignal(object)  # HistogramData
    progressUpdated = pyqtSignal(int)
    
    def __init__(self, layer: QgsRasterLayer, band: int = 1,
                 num_bins: int = 256, sample_size: int = 1000000):
        super().__init__(f"Calculate histogram: {layer.name()}", 
                        QgsTask.CanCancel)
        self.layer = layer
        self.band = band
        self.num_bins = num_bins
        self.sample_size = sample_size
        self.result = None
        
    def run(self):
        """Main task execution (background thread)."""
        try:
            provider = self.layer.dataProvider()
            extent = self.layer.extent()
            
            # Check if sampling needed
            total_pixels = (self.layer.width() * self.layer.height())
            use_sampling = total_pixels > self.sample_size
            
            if use_sampling:
                # Sample random pixels
                data = self._sample_pixels(provider, extent)
            else:
                # Read all pixels
                data = self._read_all_pixels(provider, extent)
            
            if self.isCanceled():
                return False
            
            # Calculate histogram
            nodata = provider.sourceNoDataValue(self.band)
            if nodata is not None:
                data = data[data != nodata]
            
            counts, bin_edges = np.histogram(data, bins=self.num_bins)
            
            self.result = HistogramData(
                bins=bin_edges.tolist(),
                counts=counts.tolist(),
                bin_width=bin_edges[1] - bin_edges[0]
            )
            return True
            
        except Exception as e:
            self.exception = e
            return False
    
    def finished(self, result):
        """Called when task completes (main thread)."""
        if result and self.result:
            self.histogramReady.emit(self.result)
    
    def _sample_pixels(self, provider, extent):
        """Sample random pixels for large rasters."""
        # Use GDAL for efficient windowed reading
        import random
        samples = []
        
        for i in range(min(self.sample_size, 1000)):
            if self.isCanceled():
                break
            # Random window
            x = random.uniform(extent.xMinimum(), extent.xMaximum())
            y = random.uniform(extent.yMinimum(), extent.yMaximum())
            
            result = provider.identify(
                QgsPointXY(x, y),
                QgsRaster.IdentifyFormatValue
            )
            if result.isValid():
                val = result.results().get(self.band)
                if val is not None:
                    samples.append(val)
            
            self.setProgress(int(i / 1000 * 100))
        
        return np.array(samples)
    
    def _read_all_pixels(self, provider, extent):
        """Read all pixels (small rasters)."""
        block = provider.block(self.band, extent, 
                              self.layer.width(), self.layer.height())
        data = []
        for row in range(block.height()):
            for col in range(block.width()):
                data.append(block.value(row, col))
            self.setProgress(int(row / block.height() * 100))
        return np.array(data)


class RasterStatsTask(QgsTask):
    """Background task for stats calculation."""
    
    statsReady = pyqtSignal(object)  # RasterStats
    
    def __init__(self, layer: QgsRasterLayer, band: int = 1,
                 min_val: float = None, max_val: float = None):
        super().__init__(f"Calculate stats: {layer.name()}", 
                        QgsTask.CanCancel)
        self.layer = layer
        self.band = band
        self.min_val = min_val
        self.max_val = max_val
        self.result = None
        
    def run(self):
        """Calculate statistics."""
        try:
            provider = self.layer.dataProvider()
            stats = provider.bandStatistics(
                self.band,
                QgsRasterBandStats.All
            )
            
            self.result = RasterStats(
                min=stats.minimumValue,
                max=stats.maximumValue,
                mean=stats.mean,
                std=stats.stdDev,
                nodata=provider.sourceNoDataValue(self.band),
                pixel_count=int(stats.elementCount)
            )
            return True
        except Exception as e:
            self.exception = e
            return False
    
    def finished(self, result):
        if result and self.result:
            self.statsReady.emit(self.result)
```

### 3.4 QGISRasterBackend (Adapter)

```python
# adapters/backends/raster/qgis_backend.py
from qgis.core import (
    QgsRasterLayer, QgsProject, QgsRasterTransparency,
    QgsRaster, QgsPointXY, QgsRasterBandStats
)
from ....core.ports.raster_port import RasterPort, RasterStats, HistogramData
from typing import Dict, Optional

class QGISRasterBackend(RasterPort):
    """QGIS API implementation of RasterPort."""
    
    def __init__(self):
        self._project = QgsProject.instance()
    
    def _get_layer(self, layer_id: str) -> Optional[QgsRasterLayer]:
        """Get layer by ID."""
        layer = self._project.mapLayer(layer_id)
        if isinstance(layer, QgsRasterLayer):
            return layer
        return None
    
    def get_stats(self, layer_id: str, band: int = 1) -> RasterStats:
        """Get band statistics using QGIS API."""
        layer = self._get_layer(layer_id)
        if not layer:
            raise ValueError(f"Layer {layer_id} not found")
        
        provider = layer.dataProvider()
        stats = provider.bandStatistics(band, QgsRasterBandStats.All)
        
        return RasterStats(
            min=stats.minimumValue,
            max=stats.maximumValue,
            mean=stats.mean,
            std=stats.stdDev,
            nodata=provider.sourceNoDataValue(band),
            pixel_count=int(stats.elementCount)
        )
    
    def get_histogram(self, layer_id: str, band: int = 1,
                      num_bins: int = 256) -> HistogramData:
        """Get histogram using QGIS API."""
        layer = self._get_layer(layer_id)
        if not layer:
            raise ValueError(f"Layer {layer_id} not found")
        
        provider = layer.dataProvider()
        histogram = provider.histogram(band, num_bins)
        
        return HistogramData(
            bins=list(range(num_bins + 1)),  # Simplified
            counts=histogram.histogramVector,
            bin_width=(histogram.maximum - histogram.minimum) / num_bins
        )
    
    def apply_transparency(self, layer_id: str, min_val: float,
                          max_val: float, band: int = 1) -> bool:
        """Apply transparency to pixels outside range."""
        layer = self._get_layer(layer_id)
        if not layer:
            return False
        
        renderer = layer.renderer()
        if not renderer:
            return False
        
        # Create transparency list
        transparency = QgsRasterTransparency()
        
        # Get stats for full range
        stats = self.get_stats(layer_id, band)
        
        # Make pixels < min transparent
        if min_val > stats.min:
            transparency_list = [
                QgsRasterTransparency.TransparentSingleValuePixel(
                    stats.min, min_val, 0
                )
            ]
        else:
            transparency_list = []
        
        # Make pixels > max transparent
        if max_val < stats.max:
            transparency_list.append(
                QgsRasterTransparency.TransparentSingleValuePixel(
                    max_val, stats.max, 0
                )
            )
        
        transparency.setTransparentSingleValuePixelList(transparency_list)
        renderer.setRasterTransparency(transparency)
        
        layer.triggerRepaint()
        return True
    
    def identify_pixel(self, layer_id: str, x: float, y: float) -> Dict:
        """Get pixel values at coordinates."""
        layer = self._get_layer(layer_id)
        if not layer:
            return {}
        
        provider = layer.dataProvider()
        point = QgsPointXY(x, y)
        
        result = provider.identify(point, QgsRaster.IdentifyFormatValue)
        
        if result.isValid():
            return {
                'coordinates': (x, y),
                'crs': layer.crs().authid(),
                'bands': result.results(),
                'nodata': provider.sourceNoDataValue(1),
                'cell_size': (
                    layer.rasterUnitsPerPixelX(),
                    layer.rasterUnitsPerPixelY()
                )
            }
        return {}
    
    def reset_transparency(self, layer_id: str) -> bool:
        """Remove all transparency."""
        layer = self._get_layer(layer_id)
        if not layer:
            return False
        
        renderer = layer.renderer()
        if renderer:
            transparency = QgsRasterTransparency()
            renderer.setRasterTransparency(transparency)
            layer.triggerRepaint()
            return True
        return False
```

### 3.5 HistogramWidget (UI)

```python
# ui/widgets/histogram_widget.py
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from qgis.PyQt.QtCore import pyqtSignal, Qt, QRectF
from qgis.PyQt.QtGui import QPainter, QColor, QPen, QBrush
from typing import Optional, List

class HistogramWidget(QWidget):
    """Interactive histogram widget with range selection."""
    
    rangeChanged = pyqtSignal(float, float)  # min, max selected
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(100)
        self.setMaximumHeight(150)
        
        # Data
        self._bins: List[float] = []
        self._counts: List[int] = []
        self._data_min: float = 0
        self._data_max: float = 1
        
        # Selection
        self._selection_min: Optional[float] = None
        self._selection_max: Optional[float] = None
        
        # Interaction
        self._dragging = False
        self._drag_start_x: int = 0
        
        # Colors
        self._color_selected = QColor(66, 133, 244)  # Blue
        self._color_unselected = QColor(200, 200, 200)  # Gray
        self._color_highlight = QColor(255, 193, 7)  # Yellow
        
        self.setMouseTracking(True)
    
    def set_data(self, bins: List[float], counts: List[int]):
        """Set histogram data."""
        self._bins = bins
        self._counts = counts
        if bins:
            self._data_min = bins[0]
            self._data_max = bins[-1]
        self.update()
    
    def set_range(self, min_val: float, max_val: float):
        """Set selected range (from external control)."""
        self._selection_min = min_val
        self._selection_max = max_val
        self.update()
    
    def paintEvent(self, event):
        """Draw the histogram."""
        if not self._counts:
            return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        width = self.width()
        height = self.height() - 20  # Leave space for labels
        
        max_count = max(self._counts) if self._counts else 1
        bar_width = width / len(self._counts)
        
        for i, count in enumerate(self._counts):
            bar_height = (count / max_count) * height
            x = i * bar_width
            y = height - bar_height
            
            # Determine color based on selection
            bin_value = self._bins[i] if i < len(self._bins) else self._data_max
            
            if self._selection_min is not None and self._selection_max is not None:
                if self._selection_min <= bin_value <= self._selection_max:
                    color = self._color_selected
                else:
                    color = self._color_unselected
            else:
                color = self._color_selected
            
            painter.fillRect(QRectF(x, y, bar_width - 1, bar_height), color)
        
        # Draw selection overlay
        if self._selection_min is not None and self._selection_max is not None:
            x1 = self._value_to_x(self._selection_min)
            x2 = self._value_to_x(self._selection_max)
            
            pen = QPen(QColor(0, 0, 0), 2)
            painter.setPen(pen)
            painter.drawLine(int(x1), 0, int(x1), height)
            painter.drawLine(int(x2), 0, int(x2), height)
        
        # Draw axis labels
        painter.setPen(QColor(0, 0, 0))
        painter.drawText(5, height + 15, f"{self._data_min:.1f}")
        painter.drawText(width - 50, height + 15, f"{self._data_max:.1f}")
    
    def mousePressEvent(self, event):
        """Start drag selection."""
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start_x = event.x()
            self._selection_min = self._x_to_value(event.x())
            self._selection_max = self._selection_min
            self.update()
    
    def mouseMoveEvent(self, event):
        """Update drag selection."""
        if self._dragging:
            current_val = self._x_to_value(event.x())
            start_val = self._x_to_value(self._drag_start_x)
            
            self._selection_min = min(start_val, current_val)
            self._selection_max = max(start_val, current_val)
            self.update()
    
    def mouseReleaseEvent(self, event):
        """End drag selection and emit signal."""
        if self._dragging:
            self._dragging = False
            if self._selection_min is not None and self._selection_max is not None:
                self.rangeChanged.emit(self._selection_min, self._selection_max)
    
    def mouseDoubleClickEvent(self, event):
        """Reset selection on double-click."""
        self._selection_min = None
        self._selection_max = None
        self.rangeChanged.emit(self._data_min, self._data_max)
        self.update()
    
    def _value_to_x(self, value: float) -> float:
        """Convert data value to x coordinate."""
        if self._data_max == self._data_min:
            return 0
        return ((value - self._data_min) / (self._data_max - self._data_min)) * self.width()
    
    def _x_to_value(self, x: int) -> float:
        """Convert x coordinate to data value."""
        return self._data_min + (x / self.width()) * (self._data_max - self._data_min)
```

### 3.6 RasterController (UI Controller)

```python
# ui/controllers/raster_controller.py
from qgis.core import QgsRasterLayer, QgsApplication
from qgis.PyQt.QtCore import QObject, pyqtSignal
from ...core.services.raster_service import RasterService
from ...core.tasks.raster_task import RasterHistogramTask, RasterStatsTask
from ...adapters.backends.raster.qgis_backend import QGISRasterBackend
from ..widgets.histogram_widget import HistogramWidget

class RasterController(QObject):
    """Controller for raster UI components."""
    
    statsUpdated = pyqtSignal(object)  # RasterStats
    filterApplied = pyqtSignal(bool)
    
    def __init__(self, histogram_widget: HistogramWidget):
        super().__init__()
        
        # Initialize backend and service
        self._backend = QGISRasterBackend()
        self._service = RasterService(self._backend)
        
        # UI references
        self._histogram = histogram_widget
        self._current_layer: QgsRasterLayer = None
        
        # Active tasks
        self._histogram_task = None
        self._stats_task = None
        
        # Connect signals
        self._histogram.rangeChanged.connect(self._on_range_changed)
    
    def set_layer(self, layer: QgsRasterLayer):
        """Set the active raster layer."""
        if not isinstance(layer, QgsRasterLayer):
            return
        
        self._current_layer = layer
        
        # Start histogram calculation
        self._load_histogram()
        
        # Start stats calculation
        self._load_stats()
    
    def _load_histogram(self):
        """Load histogram in background."""
        if not self._current_layer:
            return
        
        # Cancel previous task
        if self._histogram_task:
            self._histogram_task.cancel()
        
        # Create and start task
        self._histogram_task = RasterHistogramTask(self._current_layer)
        self._histogram_task.histogramReady.connect(self._on_histogram_ready)
        
        QgsApplication.taskManager().addTask(self._histogram_task)
    
    def _load_stats(self):
        """Load stats in background."""
        if not self._current_layer:
            return
        
        if self._stats_task:
            self._stats_task.cancel()
        
        self._stats_task = RasterStatsTask(self._current_layer)
        self._stats_task.statsReady.connect(self._on_stats_ready)
        
        QgsApplication.taskManager().addTask(self._stats_task)
    
    def _on_histogram_ready(self, data):
        """Handle histogram data ready."""
        self._histogram.set_data(data.bins, data.counts)
    
    def _on_stats_ready(self, stats):
        """Handle stats ready."""
        self.statsUpdated.emit(stats)
    
    def _on_range_changed(self, min_val: float, max_val: float):
        """Handle range selection change."""
        if not self._current_layer:
            return
        
        # Apply filter
        success = self._service.apply_range_filter(
            self._current_layer, min_val, max_val
        )
        self.filterApplied.emit(success)
        
        # Update selection stats
        self._load_selection_stats(min_val, max_val)
    
    def _load_selection_stats(self, min_val: float, max_val: float):
        """Calculate stats for selection."""
        if self._stats_task:
            self._stats_task.cancel()
        
        self._stats_task = RasterStatsTask(
            self._current_layer, 
            min_val=min_val, 
            max_val=max_val
        )
        self._stats_task.statsReady.connect(self._on_stats_ready)
        QgsApplication.taskManager().addTask(self._stats_task)
    
    def apply_expression_filter(self, expression: str) -> bool:
        """Apply expression-based filter."""
        if not self._current_layer:
            return False
        
        success = self._service.apply_expression_filter(
            self._current_layer, expression
        )
        self.filterApplied.emit(success)
        return success
    
    def reset_filter(self):
        """Reset all filters."""
        if not self._current_layer:
            return
        
        self._backend.reset_transparency(self._current_layer.id())
        self._histogram.set_range(None, None)
        self.filterApplied.emit(True)
    
    def identify_at_point(self, x: float, y: float) -> dict:
        """Get pixel values at point."""
        if not self._current_layer:
            return {}
        
        return self._backend.identify_pixel(self._current_layer.id(), x, y)
```

## 4. Data Flow Diagrams

### 4.1 Histogram Loading Flow

```
User selects raster layer
         │
         ▼
┌─────────────────────┐
│ RasterController    │
│ set_layer()         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ RasterHistogramTask │ ◄── QgsTask (background)
│ run()               │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ QgsRasterDataProvider│
│ histogram()         │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ HistogramWidget     │
│ set_data()          │
└─────────────────────┘
```

### 4.2 Filter Application Flow

```
User drags on histogram
         │
         ▼
┌─────────────────────┐
│ HistogramWidget     │
│ rangeChanged signal │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ RasterController    │
│ _on_range_changed() │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ RasterService       │
│ apply_range_filter()│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ QGISRasterBackend   │
│ apply_transparency()│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ QgsRasterTransparency│
│ + layer.triggerRepaint()│
└─────────────────────┘
```

## 5. Integration Points

### 5.1 Integration with Existing Code

| Component | Integration | Changes Required |
|-----------|-------------|------------------|
| `filter_mate_dockwidget.py` | Add raster accordion section | Add widget, connect signals |
| `filter_mate_app.py` | Layer type detection | Add `_is_raster_layer()` check |
| `LayerService` | Extend for raster | Add `get_layer_type()` method |
| `ExportService` | Stats CSV export | Add `export_raster_stats()` |

### 5.2 Signal Connections

```python
# In filter_mate_dockwidget.py

def _setup_raster_integration(self):
    """Setup raster UI components."""
    
    # Create widgets
    self.histogram_widget = HistogramWidget()
    self.raster_controller = RasterController(self.histogram_widget)
    
    # Connect to layer changes
    self.iface.layerTreeView().currentLayerChanged.connect(
        self._on_layer_changed
    )
    
    # Connect stats updates
    self.raster_controller.statsUpdated.connect(
        self._update_stats_display
    )

def _on_layer_changed(self, layer):
    """Handle layer selection change."""
    if isinstance(layer, QgsRasterLayer):
        # Show raster accordion, hide vector
        self.raster_accordion.setVisible(True)
        self.vector_accordion.setVisible(False)
        self.raster_controller.set_layer(layer)
    elif isinstance(layer, QgsVectorLayer):
        # Show vector accordion, hide raster
        self.raster_accordion.setVisible(False)
        self.vector_accordion.setVisible(True)
```

## 6. Testing Strategy

### 6.1 Unit Tests

```python
# tests/test_raster_service.py
import pytest
from unittest.mock import Mock, MagicMock
from core.services.raster_service import RasterService
from core.ports.raster_port import RasterStats

class TestRasterService:
    
    def test_get_layer_stats_with_cache(self):
        """Test stats caching."""
        mock_backend = Mock()
        mock_backend.get_stats.return_value = RasterStats(
            min=0, max=100, mean=50, std=10, nodata=None, pixel_count=1000
        )
        
        service = RasterService(mock_backend)
        mock_layer = Mock()
        mock_layer.id.return_value = "layer_123"
        
        # First call
        stats1 = service.get_layer_stats(mock_layer)
        # Second call (should use cache)
        stats2 = service.get_layer_stats(mock_layer)
        
        assert mock_backend.get_stats.call_count == 1
        assert stats1.mean == 50
    
    def test_parse_expression_simple(self):
        """Test expression parsing."""
        service = RasterService(Mock())
        
        result = service._parse_expression('"band1" > 500')
        assert result['min'] == 500
        
        result = service._parse_expression('"band1" > 500 AND "band1" < 1000')
        assert result['min'] == 500
        assert result['max'] == 1000
```

### 6.2 Integration Tests

```python
# tests/test_raster_integration.py
import pytest
from qgis.core import QgsRasterLayer, QgsProject

@pytest.fixture
def sample_raster():
    """Load sample raster for testing."""
    layer = QgsRasterLayer("tests/data/dem_sample.tif", "test_dem")
    QgsProject.instance().addMapLayer(layer)
    yield layer
    QgsProject.instance().removeMapLayer(layer.id())

class TestRasterIntegration:
    
    def test_histogram_calculation(self, sample_raster):
        """Test histogram loads correctly."""
        from adapters.backends.raster.qgis_backend import QGISRasterBackend
        
        backend = QGISRasterBackend()
        histogram = backend.get_histogram(sample_raster.id())
        
        assert len(histogram.counts) == 256
        assert sum(histogram.counts) > 0
    
    def test_transparency_application(self, sample_raster):
        """Test filter applies correctly."""
        from adapters.backends.raster.qgis_backend import QGISRasterBackend
        
        backend = QGISRasterBackend()
        result = backend.apply_transparency(
            sample_raster.id(), 
            min_val=500, 
            max_val=1000
        )
        
        assert result is True
        # Verify transparency was set
        renderer = sample_raster.renderer()
        transparency = renderer.rasterTransparency()
        assert len(transparency.transparentSingleValuePixelList()) > 0
```

## 7. Performance Considerations

### 7.1 Optimization Strategies

| Strategy | Implementation | Target |
|----------|----------------|--------|
| **Lazy loading** | Import raster modules only when needed | Startup < 100ms |
| **Background tasks** | All heavy ops in QgsTask | No UI freeze |
| **Sampling** | Auto-sample rasters > 500Mo | Histogram < 5s |
| **Caching** | Cache stats per layer | Instant re-display |
| **Debouncing** | 100ms debounce on slider | Smooth preview |

### 7.2 Memory Management

```python
# In raster_task.py - Memory-efficient reading
def _read_windowed(self, provider, extent, window_size=1024):
    """Read raster in windows to limit memory."""
    width = self.layer.width()
    height = self.layer.height()
    
    all_values = []
    
    for y in range(0, height, window_size):
        for x in range(0, width, window_size):
            w = min(window_size, width - x)
            h = min(window_size, height - y)
            
            block = provider.block(
                self.band,
                QgsRectangle(x, y, x + w, y + h),
                w, h
            )
            
            for row in range(h):
                for col in range(w):
                    all_values.append(block.value(row, col))
            
            if self.isCanceled():
                return np.array([])
    
    return np.array(all_values)
```

## 8. Deployment & Migration

### 8.1 Migration Steps

1. **Create new modules** (no breaking changes)
2. **Add UI widgets** to dockwidget
3. **Connect signals** for layer changes
4. **Test with sample rasters**
5. **Performance tuning**
6. **Documentation update**

### 8.2 Rollback Plan

- All new code in isolated modules
- Feature flag possible via config
- No changes to existing vector functionality

## 9. Appendix

### 9.1 QGIS API Reference

| Class | Usage | Documentation |
|-------|-------|---------------|
| `QgsRasterLayer` | Layer management | [Link](https://qgis.org/pyqgis/3.22/core/QgsRasterLayer.html) |
| `QgsRasterDataProvider` | Data access | [Link](https://qgis.org/pyqgis/3.22/core/QgsRasterDataProvider.html) |
| `QgsRasterTransparency` | Pixel masking | [Link](https://qgis.org/pyqgis/3.22/core/QgsRasterTransparency.html) |
| `QgsTask` | Background tasks | [Link](https://qgis.org/pyqgis/3.22/core/QgsTask.html) |

### 9.2 File Size Estimates

| File | Lines | Purpose |
|------|-------|---------|
| `raster_port.py` | ~50 | Interface |
| `raster_service.py` | ~400 | Business logic |
| `raster_task.py` | ~300 | Async operations |
| `qgis_backend.py` | ~150 | QGIS adapter |
| `gdal_backend.py` | ~200 | GDAL adapter |
| `histogram_widget.py` | ~350 | UI widget |
| `raster_controller.py` | ~250 | UI controller |
| **TOTAL** | **~1,700** | |

---

**Document Status: ✅ COMPLETE**
**Date: January 27, 2026**
**Author: BMAD Architect**
