# Raster Integration API - Developer Documentation

**EPIC-2: Raster Integration for FilterMate**
**Version:** 5.0 | **Date:** January 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Core Components](#core-components)
4. [UI Widgets](#ui-widgets)
5. [Usage Guide](#usage-guide)
6. [API Reference](#api-reference)
7. [Configuration](#configuration)
8. [Performance Optimization](#performance-optimization)
9. [Error Handling](#error-handling)
10. [Testing](#testing)
11. [Migration Guide](#migration-guide)

---

## Overview

The Raster Integration module extends FilterMate with comprehensive raster layer support, enabling:

- **Band Statistics**: Min, max, mean, std_dev, null percentage per band
- **Histogram Visualization**: Interactive histograms with range selection
- **Pixel Identification**: Click-to-identify pixel values with map tool
- **Transparency Control**: Opacity slider and value-based transparency

### Key Features

| Feature            | Description                             |
| ------------------ | --------------------------------------- |
| Multi-band support | Handle rasters with 1-N bands           |
| Statistics caching | LRU cache with TTL expiration           |
| Smart sampling     | Automatic sampling for large rasters    |
| Progress tracking  | Async operations with progress feedback |
| Error handling     | Typed exception hierarchy               |

---

## Architecture

### Hexagonal Architecture Pattern

```
┌─────────────────────────────────────────────────────────────────┐
│                         UI Layer                                │
│  ┌──────────────────┐  ┌──────────────────┐  ┌────────────────┐│
│  │  RasterGroupBox  │  │  HistogramWidget │  │ TransparencyW. ││
│  └────────┬─────────┘  └────────┬─────────┘  └───────┬────────┘│
│           │                     │                     │         │
│           └─────────────────────┼─────────────────────┘         │
│                                 ▼                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              RasterExploringController                    │  │
│  │              (Orchestration Layer)                        │  │
│  └─────────────────────────┬────────────────────────────────┘  │
└────────────────────────────┼────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Core Layer                                │
│  ┌───────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │  RasterPort       │  │ RasterStatsService│  │ RasterErrors │ │
│  │  (Interface)      │  │                  │  │              │ │
│  └─────────┬─────────┘  └────────┬─────────┘  └──────────────┘ │
└────────────┼─────────────────────┼──────────────────────────────┘
             ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                         │
│  ┌───────────────────┐  ┌──────────────────┐  ┌──────────────┐ │
│  │ QGISRasterBackend │  │ RasterStatsCache │  │ Performance  │ │
│  │                   │  │                  │  │ Utilities    │ │
│  └───────────────────┘  └──────────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Layer          | Component                   | Responsibility                    |
| -------------- | --------------------------- | --------------------------------- |
| UI             | `RasterExploringGroupBox`   | Container for all raster widgets  |
| UI             | `RasterStatsPanel`          | Display statistics and layer info |
| UI             | `HistogramWidget`           | Render interactive histograms     |
| UI             | `PixelIdentifyWidget`       | Pixel value identification        |
| UI             | `TransparencyWidget`        | Opacity and transparency control  |
| Controller     | `RasterExploringController` | Orchestrate UI/Service/Backend    |
| Core           | `RasterPort`                | Abstract backend interface        |
| Core           | `RasterStatsService`        | Business logic orchestration      |
| Core           | `RasterErrors`              | Exception hierarchy               |
| Infrastructure | `QGISRasterBackend`         | QGIS API implementation           |
| Infrastructure | `RasterStatsCache`          | LRU caching with TTL              |
| Infrastructure | `RasterPerformance`         | Sampling and optimization         |

---

## Core Components

### RasterPort (Interface)

The `RasterPort` defines the contract for raster backends:

```python
from core.ports.raster_port import (
    RasterPort,
    BandStatistics,
    HistogramData,
    PixelValue,
    RasterLayerSnapshot
)

class MyCustomBackend(RasterPort):
    """Custom raster backend implementation."""

    def is_valid(self, layer) -> bool:
        """Check if layer is valid and accessible."""
        ...

    def get_band_count(self, layer) -> int:
        """Return number of bands in raster."""
        ...

    def get_statistics(self, layer, band_number: int) -> BandStatistics:
        """Compute band statistics."""
        ...

    def get_histogram(
        self,
        layer,
        band_number: int,
        bin_count: int = 256
    ) -> HistogramData:
        """Compute histogram for band."""
        ...

    def get_pixel_value(
        self,
        layer,
        point,
        crs
    ) -> List[PixelValue]:
        """Get pixel values at point for all bands."""
        ...
```

### Data Classes

```python
from dataclasses import dataclass
from typing import Optional, List, Tuple

@dataclass
class BandStatistics:
    """Statistics for a single raster band."""
    band_number: int
    min_value: float
    max_value: float
    mean: float
    std_dev: float
    no_data_value: Optional[float]
    has_no_data: bool
    null_percentage: float
    data_type: str

@dataclass
class HistogramData:
    """Histogram data for a band."""
    band_number: int
    bin_count: int
    min_value: float
    max_value: float
    counts: List[int]
    is_sampled: bool = False

@dataclass
class PixelValue:
    """Pixel value at a specific location."""
    band_number: int
    value: Optional[float]
    is_no_data: bool
    x: float
    y: float

@dataclass
class RasterLayerSnapshot:
    """Immutable snapshot of raster layer properties."""
    layer_id: str
    layer_name: str
    band_count: int
    width: int
    height: int
    crs_auth_id: str
    extent: Tuple[float, float, float, float]
    data_type: str
    band_statistics: List[BandStatistics]
```

---

## UI Widgets

### Widget Hierarchy

```
RasterExploringGroupBox (Container)
├── Tab 1: Statistics
│   └── RasterStatsPanel
│       ├── StatCard (layer info)
│       └── BandStatsRow[] (per band)
├── Tab 2: Histogram
│   └── HistogramWidget
│       ├── HistogramCanvas (matplotlib)
│       └── Band selector + range controls
├── Tab 3: Transparency
│   └── TransparencyWidget
│       ├── OpacitySlider
│       └── RangeTransparencyWidget
└── PixelIdentifyWidget (floating)
    ├── PixelValueCard[] (per band)
    └── RasterIdentifyMapTool
```

### RasterExploringGroupBox

Main container widget with tabbed interface:

```python
from ui.widgets.raster_groupbox import RasterExploringGroupBox

# Create groupbox
groupbox = RasterExploringGroupBox(parent=self)

# Set layer - updates all child widgets
groupbox.set_layer(raster_layer)

# Clear all widgets
groupbox.clear()

# Access child widgets
stats_panel = groupbox.stats_panel
histogram_widget = groupbox.histogram_widget
transparency_widget = groupbox.transparency_widget

# Signals
groupbox.band_changed.connect(self.on_band_changed)
groupbox.transparency_changed.connect(self.on_transparency_changed)
groupbox.histogram_range_selected.connect(self.on_range_selected)
```

### RasterStatsPanel

Displays layer information and band statistics:

```python
from ui.widgets.raster_stats_panel import RasterStatsPanel, StatCard, BandStatsRow

# Create panel
panel = RasterStatsPanel(parent=self)

# Set layer snapshot
panel.set_layer_snapshot(snapshot)

# Update individual band stats
panel.update_band_stats(band_number=1, stats=band_statistics)

# Clear display
panel.clear()
```

**StatCard Component:**

```python
# Displays key-value pairs in a card format
card = StatCard(title="Layer Info", parent=self)
card.add_row("Name", "DEM_Layer")
card.add_row("Size", "1000 x 1000")
card.add_row("CRS", "EPSG:32632")
```

**BandStatsRow Component:**

```python
# Displays statistics for a single band
row = BandStatsRow(band_number=1, parent=self)
row.set_statistics(
    min_val=0.0,
    max_val=255.0,
    mean=127.5,
    std_dev=50.0,
    null_pct=2.5
)
```

### HistogramWidget

Interactive histogram with range selection:

```python
from ui.widgets.histogram_widget import HistogramWidget, HistogramCanvas

# Create widget
histogram = HistogramWidget(parent=self)

# Set histogram data
histogram.set_histogram_data(histogram_data)

# Set band selector options
histogram.set_band_count(3)

# Handle range selection
histogram.range_selected.connect(self.on_range_selected)

# Get current range
min_val, max_val = histogram.get_selected_range()

# Reset to full range
histogram.reset_range()
```

**HistogramCanvas (matplotlib-based):**

```python
canvas = HistogramCanvas(parent=self)
canvas.set_data(counts=[...], min_val=0, max_val=255)
canvas.set_range_highlight(50, 200)  # Highlight range
canvas.clear()
```

**Signals:**

- `band_changed(int)` - Band selection changed
- `range_selected(float, float)` - User selected value range
- `range_reset()` - Range reset to full extent

### PixelIdentifyWidget

Click-to-identify pixel values:

```python
from ui.widgets.pixel_identify_widget import (
    PixelIdentifyWidget,
    PixelValueCard,
    RasterIdentifyMapTool
)

# Create widget
identify = PixelIdentifyWidget(parent=self)

# Set layer
identify.set_layer(raster_layer)

# Enable/disable map tool
identify.activate_tool()
identify.deactivate_tool()

# Display pixel values
identify.display_values(pixel_values=[
    PixelValue(band=1, value=125.5, is_no_data=False, x=100.0, y=200.0),
    PixelValue(band=2, value=89.2, is_no_data=False, x=100.0, y=200.0),
])

# Clear display
identify.clear()
```

**RasterIdentifyMapTool:**

```python
from qgis.gui import QgsMapTool

tool = RasterIdentifyMapTool(canvas=iface.mapCanvas())
tool.pixel_identified.connect(self.on_pixel_identified)

# Activate tool
iface.mapCanvas().setMapTool(tool)
```

### TransparencyWidget

Opacity and value-based transparency:

```python
from ui.widgets.transparency_widget import (
    TransparencyWidget,
    OpacitySlider,
    RangeTransparencyWidget
)

# Create widget
transparency = TransparencyWidget(parent=self)

# Set layer
transparency.set_layer(raster_layer)

# Handle opacity changes
transparency.opacity_changed.connect(self.on_opacity_changed)

# Get/set opacity
current = transparency.get_opacity()  # 0.0 - 1.0
transparency.set_opacity(0.75)

# Apply transparency
transparency.apply_to_layer()
```

**OpacitySlider Component:**

```python
slider = OpacitySlider(parent=self)
slider.set_value(75)  # 0-100 percentage
slider.value_changed.connect(lambda v: print(f"Opacity: {v}%"))
```

**RangeTransparencyWidget Component:**

```python
range_widget = RangeTransparencyWidget(parent=self)
range_widget.set_band(1)
range_widget.set_transparent_range(0, 10)  # Make values 0-10 transparent
range_widget.range_changed.connect(self.on_transparent_range_changed)
```

### Widget Styling

All widgets support FilterMate themes:

```python
from config.theme_helpers import apply_widget_theme

# Apply current theme to widget
apply_widget_theme(widget)

# Widgets automatically inherit:
# - Background colors
# - Font styles
# - Border styles
# - Icon colors
```

### Widget Signals Summary

| Widget                    | Signal                 | Parameters         | Description              |
| ------------------------- | ---------------------- | ------------------ | ------------------------ |
| `RasterExploringGroupBox` | `band_changed`         | `int`              | Band selection changed   |
| `RasterExploringGroupBox` | `transparency_changed` | `float`            | Opacity value changed    |
| `HistogramWidget`         | `range_selected`       | `float, float`     | Value range selected     |
| `HistogramWidget`         | `band_changed`         | `int`              | Band selector changed    |
| `PixelIdentifyWidget`     | `pixel_identified`     | `List[PixelValue]` | Pixel clicked on map     |
| `TransparencyWidget`      | `opacity_changed`      | `float`            | Opacity slider moved     |
| `TransparencyWidget`      | `transparency_applied` | -                  | Changes applied to layer |

---

## Usage Guide

### Basic Usage

```python
from core.services.raster_stats_service import RasterStatsService
from adapters.backends.qgis_raster_backend import QGISRasterBackend

# Initialize service with backend
backend = QGISRasterBackend()
service = RasterStatsService(backend)

# Get layer snapshot with all statistics
layer = iface.activeLayer()
snapshot = service.get_layer_snapshot(layer)

print(f"Layer: {snapshot.layer_name}")
print(f"Bands: {snapshot.band_count}")
print(f"Size: {snapshot.width}x{snapshot.height}")

# Access band statistics
for band_stats in snapshot.band_statistics:
    print(f"Band {band_stats.band_number}:")
    print(f"  Range: {band_stats.min_value} - {band_stats.max_value}")
    print(f"  Mean: {band_stats.mean:.2f}")
```

### With Controller

```python
from ui.controllers.raster_exploring_controller import RasterExploringController

# Initialize controller (in dockwidget)
controller = RasterExploringController(
    raster_groupbox=self.raster_groupbox,
    dockwidget=self
)

# Connect to layer changes
controller.set_current_layer(layer)

# Controller automatically:
# - Validates layer type
# - Computes statistics
# - Updates UI widgets
```

### With Caching

```python
from infrastructure.cache.raster_stats_cache import (
    RasterStatsCache,
    RasterStatsCacheConfig
)

# Configure cache
config = RasterStatsCacheConfig(
    max_entries=100,
    ttl_seconds=300,  # 5 minutes
    max_memory_mb=50.0
)
cache = RasterStatsCache(config)

# Store statistics
cache.set_statistics(layer_id, stats)

# Retrieve (returns None if expired/missing)
cached_stats = cache.get_statistics(layer_id)

# Invalidate when layer changes
cache.invalidate_layer(layer_id)
```

---

## API Reference

### RasterExploringController

```python
class RasterExploringController:
    """
    MVC Controller for raster exploration functionality.

    Orchestrates:
    - UI widget updates
    - Statistics service calls
    - Backend operations
    - Error handling
    """

    def __init__(
        self,
        raster_groupbox: QGroupBox,
        dockwidget: QDockWidget
    ):
        """Initialize controller with UI components."""

    def set_current_layer(self, layer: QgsRasterLayer) -> None:
        """Set current layer and update UI."""

    def refresh_statistics(self) -> None:
        """Force refresh statistics for current layer."""

    def on_band_changed(self, band_index: int) -> None:
        """Handle band selection change."""

    def on_transparency_changed(self, value: float) -> None:
        """Handle transparency slider change."""
```

### RasterStatsCache

```python
class RasterStatsCache:
    """
    LRU cache for raster statistics with TTL expiration.

    Features:
    - Thread-safe with RLock
    - Automatic TTL expiration
    - Memory limit enforcement
    - Hit/miss tracking
    """

    def get_statistics(self, layer_id: str) -> Optional[RasterLayerSnapshot]:
        """Get cached statistics or None if miss."""

    def set_statistics(
        self,
        layer_id: str,
        stats: RasterLayerSnapshot
    ) -> None:
        """Store statistics in cache."""

    def get_histogram(
        self,
        layer_id: str,
        band_number: int
    ) -> Optional[HistogramData]:
        """Get cached histogram or None if miss."""

    def set_histogram(
        self,
        layer_id: str,
        band_number: int,
        histogram: HistogramData
    ) -> None:
        """Store histogram in cache."""

    def invalidate_layer(self, layer_id: str) -> int:
        """Remove all entries for layer. Returns count removed."""

    def clear(self) -> None:
        """Clear entire cache."""

    def get_cache_stats(self) -> CacheStats:
        """Get hit/miss statistics."""
```

### Error Classes

```python
from core.domain.raster_errors import (
    RasterError,
    RasterLayerNotValidError,
    RasterBandOutOfRangeError,
    RasterStatisticsComputationError,
    RasterHistogramComputationError,
    RasterPixelReadError,
    ErrorSeverity,
    RasterErrorCategory
)

# Example usage
try:
    stats = backend.get_statistics(layer, band=5)
except RasterBandOutOfRangeError as e:
    print(f"Band {e.band_number} invalid. Valid: 1-{e.band_count}")
except RasterError as e:
    print(f"Raster error: {e.message}")
```

---

## Configuration

### Cache Configuration

```python
from infrastructure.cache.raster_stats_cache import RasterStatsCacheConfig

config = RasterStatsCacheConfig(
    max_entries=100,        # Maximum cached items
    ttl_seconds=300,        # Time-to-live (5 min default)
    max_memory_mb=50.0,     # Memory limit in MB
    cleanup_interval=60     # Cleanup every 60 seconds
)
```

### Performance Configuration

```python
from core.optimization.raster_performance import RasterSampler

sampler = RasterSampler(
    max_pixels=1_000_000,      # Sample if above this
    sample_rate=0.1,           # 10% sample rate
    min_sample_size=10_000     # Minimum samples
)
```

---

## Performance Optimization

### Smart Sampling

Large rasters (>1M pixels) are automatically sampled:

```python
from core.optimization.raster_performance import RasterSampler

sampler = RasterSampler()
total_pixels = 50_000 * 50_000  # 2.5B pixels

if sampler.needs_sampling(total_pixels):
    strategy = sampler.get_sampling_strategy(total_pixels)
    # strategy.sample_rate = 0.0004 (0.04%)
    # strategy.estimated_samples = 1,000,000
```

### Memory Estimation

```python
from core.optimization.raster_performance import estimate_memory_usage

# Before loading full raster
mem_mb = estimate_memory_usage(
    width=10000,
    height=10000,
    band_count=3,
    data_type="Float32"
)
# mem_mb ≈ 1144 MB

if mem_mb > 500:
    # Use sampling instead
    ...
```

### Progress Tracking

```python
from core.optimization.raster_performance import ProgressTracker

tracker = ProgressTracker(total_steps=100)

for i in range(100):
    # Do work
    tracker.update(i + 1)
    print(f"Progress: {tracker.percentage}%")
    print(f"ETA: {tracker.eta_seconds}s")
```

---

## Error Handling

### Exception Hierarchy

```
RasterError (base)
├── RasterLayerNotValidError
├── RasterBandOutOfRangeError
├── RasterStatisticsComputationError
├── RasterHistogramComputationError
├── RasterPixelReadError
├── RasterCacheError
└── RasterPerformanceError
```

### Error Handler Pattern

```python
from core.domain.raster_errors import RasterErrorHandler, ErrorResult

handler = RasterErrorHandler()

@handler.safe_execute
def compute_stats(layer):
    # May raise RasterError
    return backend.get_statistics(layer, band=1)

# Returns ErrorResult on error, or actual result
result = compute_stats(my_layer)

if isinstance(result, ErrorResult):
    print(f"Error: {result.message}")
    print(f"Severity: {result.severity}")
else:
    print(f"Stats: {result}")
```

### UI Error Display

```python
from core.domain.raster_errors import format_error_for_ui

try:
    stats = backend.get_statistics(layer, band=1)
except RasterError as e:
    # Get user-friendly message
    ui_message = format_error_for_ui(e)
    iface.messageBar().pushWarning("FilterMate", ui_message)
```

---

## Testing

### Unit Tests

```bash
# Run all raster tests
python -m pytest tests/test_raster*.py -v

# Run specific test class
python -m pytest tests/test_raster_stats_cache.py::TestCacheOperations -v

# Run with coverage
python -m pytest tests/test_raster*.py --cov=core --cov=ui --cov-report=html
```

### Test Categories

| File                                  | Tests          | Coverage       |
| ------------------------------------- | -------------- | -------------- |
| `test_raster_port.py`                 | Port interface | Core           |
| `test_qgis_raster_backend.py`         | QGIS backend   | Adapters       |
| `test_raster_stats_service.py`        | Service layer  | Core           |
| `test_raster_stats_panel.py`          | Stats widget   | UI             |
| `test_histogram_widget.py`            | Histogram      | UI             |
| `test_pixel_identify_widget.py`       | Pixel tool     | UI             |
| `test_transparency_widget.py`         | Transparency   | UI             |
| `test_raster_groupbox.py`             | Container      | UI             |
| `test_raster_exploring_controller.py` | Controller     | Integration    |
| `test_raster_stats_cache.py`          | Cache          | Infrastructure |
| `test_raster_errors.py`               | Errors         | Core           |
| `test_raster_performance.py`          | Performance    | Core           |
| `test_raster_integration.py`          | End-to-end     | Integration    |

### Mock Layer Creation

```python
from unittest.mock import Mock

def create_mock_raster_layer(
    name="test_raster",
    band_count=3,
    width=1000,
    height=1000
):
    """Create mock raster layer for testing."""
    layer = Mock()
    layer.type.return_value = 1  # QgsMapLayerType.RasterLayer
    layer.id.return_value = f"layer_{name}"
    layer.name.return_value = name
    layer.isValid.return_value = True
    layer.width.return_value = width
    layer.height.return_value = height
    layer.bandCount.return_value = band_count
    return layer
```

---

## Migration Guide

### From v4.x to v5.0

#### 1. Import Changes

```python
# Old (v4.x) - No raster support
from core.services.filter_service import FilterService

# New (v5.0) - Add raster imports
from core.services.raster_stats_service import RasterStatsService
from core.ports.raster_port import RasterPort, BandStatistics
from adapters.backends.qgis_raster_backend import QGISRasterBackend
```

#### 2. Controller Integration

```python
# Old - Vector only
class MyController:
    def set_layer(self, layer):
        if is_vector_layer(layer):
            self.process_vector(layer)

# New - Vector + Raster
class MyController:
    def set_layer(self, layer):
        if is_vector_layer(layer):
            self.process_vector(layer)
        elif is_raster_layer(layer):
            self.raster_controller.set_current_layer(layer)
```

#### 3. Layer Type Detection

```python
from adapters.layer_validator import LayerValidator

validator = LayerValidator()

# Get layer type
layer_type = validator.get_layer_type(layer)

if layer_type == "raster":
    # Use raster widgets
    ...
elif layer_type == "vector":
    # Use vector widgets
    ...
```

---

## Changelog

### v5.0.0 (January 2026)

**EPIC-2: Raster Integration**

- ✅ Sprint 1: Core Backend (US-01 to US-04)
- ✅ Sprint 2: UI Widgets (US-05 to US-08)
- ✅ Sprint 3: Service Integration (US-09 to US-12)
- ✅ Sprint 4: Testing & Documentation (US-13 to US-15)

**New Features:**

- `RasterPort` interface for backend abstraction
- `QGISRasterBackend` implementation
- `RasterStatsService` for business logic
- `RasterStatsPanel` widget
- `HistogramWidget` with range selection
- `PixelIdentifyWidget` with map tool
- `TransparencyWidget` with opacity control
- `RasterExploringController` MVC controller
- `RasterStatsCache` with LRU/TTL
- Comprehensive error handling
- Performance optimization utilities

---

_Documentation generated for FilterMate v5.0 - EPIC-2 Raster Integration_
