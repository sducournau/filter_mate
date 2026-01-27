---
title: "User Stories - FilterMate Raster Integration"
epic: "EPIC-2"
version: "1.0"
date: "2026-01-27"
prd: "prd-raster.md"
architecture: "architecture-raster.md"
sprint_count: 4
---

# User Stories - FilterMate Raster Integration (EPIC-2)

## Story Map Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           EPIC-2: RASTER INTEGRATION                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Sprint 1 (Week 1-2)        Sprint 2 (Week 3-4)                             │
│  ┌─────────────────────┐    ┌─────────────────────┐                         │
│  │ US-01: Layer Detect │    │ US-05: Histogram UI │                         │
│  │ US-02: Raster Port  │    │ US-06: Cell Filter  │                         │
│  │ US-03: QGIS Backend │    │ US-07: Range Slider │                         │
│  │ US-04: Stats Service│    │ US-08: Sync Histo   │                         │
│  └─────────────────────┘    └─────────────────────┘                         │
│                                                                              │
│  Sprint 3 (Week 5-6)        Sprint 4 (Week 7-8)                             │
│  ┌─────────────────────┐    ┌─────────────────────┐                         │
│  │ US-09: Expr Filter  │    │ US-13: Performance  │                         │
│  │ US-10: Common Btns  │    │ US-14: Export CSV   │                         │
│  │ US-11: Identify Pix │    │ US-15: Integration  │                         │
│  │ US-12: Preview Real │    │ US-16: Testing      │                         │
│  └─────────────────────┘    └─────────────────────┘                         │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Sprint 1: Core Infrastructure (Week 1-2)

### US-01: Layer Type Detection

**As a** FilterMate user  
**I want** the UI to automatically detect when I select a raster layer  
**So that** the appropriate raster tools are displayed

**Acceptance Criteria:**
- [ ] When I select a raster layer in QGIS, the RASTER accordion expands
- [ ] When I select a vector layer, the VECTOR accordion expands
- [ ] When no layer is selected, both accordions are collapsed
- [ ] Layer type detection works for all supported raster formats

**Technical Notes:**
```python
# Check: layer.type() == QgsMapLayerType.RasterLayer
# Signal: iface.layerTreeView().currentLayerChanged
```

**Story Points:** 2  
**Priority:** MUST  
**Dependencies:** None

---

### US-02: Raster Port Interface

**As a** developer  
**I want** an abstract interface for raster operations  
**So that** the business logic is decoupled from QGIS/GDAL implementations

**Acceptance Criteria:**
- [ ] RasterPort abstract class created with all required methods
- [ ] RasterStats dataclass defined
- [ ] HistogramData dataclass defined
- [ ] Interface methods documented with docstrings

**Technical Notes:**
```python
# File: core/ports/raster_port.py
# Methods: get_stats, get_histogram, apply_transparency, identify_pixel, reset_transparency
```

**Story Points:** 1  
**Priority:** MUST  
**Dependencies:** None

---

### US-03: QGIS Raster Backend

**As a** developer  
**I want** a QGIS API implementation of RasterPort  
**So that** I can use QGIS native raster functions

**Acceptance Criteria:**
- [ ] QGISRasterBackend class implements RasterPort
- [ ] get_stats uses QgsRasterBandStats
- [ ] get_histogram uses provider.histogram()
- [ ] apply_transparency uses QgsRasterTransparency
- [ ] identify_pixel uses provider.identify()
- [ ] Unit tests pass with mock layers

**Technical Notes:**
```python
# File: adapters/backends/raster/qgis_backend.py
# Uses: QgsRasterLayer, QgsRasterDataProvider, QgsRasterTransparency
```

**Story Points:** 3  
**Priority:** MUST  
**Dependencies:** US-02

---

### US-04: Raster Stats Service

**As a** developer  
**I want** a service layer for raster statistics  
**So that** business logic is separated from UI and data access

**Acceptance Criteria:**
- [ ] RasterService class created
- [ ] Stats caching implemented
- [ ] apply_range_filter method works
- [ ] Expression parsing works for simple expressions
- [ ] Unit tests achieve 80% coverage

**Technical Notes:**
```python
# File: core/services/raster_service.py
# Features: caching, expression parsing, filter application
```

**Story Points:** 3  
**Priority:** MUST  
**Dependencies:** US-02, US-03

---

## Sprint 2: UI Components (Week 3-4)

### US-05: Histogram Widget

**As a** user  
**I want** to see a histogram of my raster values  
**So that** I can understand the data distribution

**Acceptance Criteria:**
- [ ] Histogram displays when raster is selected
- [ ] Histogram loads in < 2s for rasters < 100Mo
- [ ] Stats displayed inline (min, max, mean, std)
- [ ] Histogram respects theme colors (dark/light mode)
- [ ] "Sampled" indicator shows for large rasters

**Technical Notes:**
```python
# File: ui/widgets/histogram_widget.py
# PyQt5 QWidget with custom paintEvent
# Colors: selected (blue), unselected (gray)
```

**Story Points:** 5  
**Priority:** MUST  
**Dependencies:** US-04

---

### US-06: Cell Filter (Transparency)

**As a** user  
**I want** to hide pixels outside a value range  
**So that** I can focus on specific terrain features

**Acceptance Criteria:**
- [ ] Pixels outside range become transparent
- [ ] Transparency applies in < 200ms
- [ ] NoData values remain transparent
- [ ] Filter can be reset with double-click
- [ ] Map repaints automatically

**Technical Notes:**
```python
# Uses: QgsRasterTransparency.setTransparentSingleValuePixelList()
# Apply: layer.renderer().setRasterTransparency()
```

**Story Points:** 3  
**Priority:** MUST  
**Dependencies:** US-03

---

### US-07: Range Slider

**As a** user  
**I want** a dual slider to set min/max values  
**So that** I can easily define a filter range

**Acceptance Criteria:**
- [ ] Slider has two handles (min and max)
- [ ] Values can also be typed in input fields
- [ ] Slider range matches raster data range
- [ ] Debounce prevents excessive updates (100ms)
- [ ] Values display with appropriate precision

**Technical Notes:**
```python
# Custom QWidget or QRangeSlider
# Connect: valueChanged signal to filter update
```

**Story Points:** 3  
**Priority:** MUST  
**Dependencies:** US-05

---

### US-08: Histogram-Slider Sync

**As a** user  
**I want** the histogram and slider to stay synchronized  
**So that** changes in one reflect in the other

**Acceptance Criteria:**
- [ ] Drag on histogram updates slider
- [ ] Move slider updates histogram highlight
- [ ] Type values updates both
- [ ] Double-click histogram resets both
- [ ] No infinite update loops

**Technical Notes:**
```python
# Signals: histogram.rangeChanged ↔ slider.valueChanged
# Block signals during sync to prevent loops
```

**Story Points:** 2  
**Priority:** MUST  
**Dependencies:** US-05, US-07

---

## Sprint 3: Advanced Features (Week 5-6)

### US-09: Expression Filter

**As a** user  
**I want** to filter raster by expression  
**So that** I can apply complex conditions like vectors

**Acceptance Criteria:**
- [ ] Expression input field available
- [ ] Supports: "band1" > 500
- [ ] Supports: "band1" > 500 AND "band1" < 1000
- [ ] Invalid expressions show error message
- [ ] Expression can be saved as favorite

**Technical Notes:**
```python
# Parse expression to min/max range
# Apply via same transparency mechanism
```

**Story Points:** 3  
**Priority:** MUST  
**Dependencies:** US-06

---

### US-10: Common Buttons (Raster)

**As a** user  
**I want** Zoom/Pan/Identify buttons to work with rasters  
**So that** I have consistent navigation tools

**Acceptance Criteria:**
- [ ] Zoom: zooms to raster extent
- [ ] Pan: pans to raster center
- [ ] Identify: shows pixel values popup
- [ ] Buttons adapt behavior based on layer type
- [ ] Tooltips updated for raster mode

**Technical Notes:**
```python
# Zoom: canvas.setExtent(layer.extent())
# Identify: provider.identify(point, QgsRaster.IdentifyFormatValue)
```

**Story Points:** 2  
**Priority:** MUST  
**Dependencies:** US-01

---

### US-11: Identify Pixel Popup

**As a** user  
**I want** to see pixel values when I click on the map  
**So that** I can inspect specific locations

**Acceptance Criteria:**
- [ ] Popup shows coordinates (X, Y)
- [ ] Popup shows CRS
- [ ] Popup shows all band values
- [ ] Popup shows NoData status
- [ ] Popup shows cell size

**Technical Notes:**
```python
# Uses: QgsMapToolIdentify or custom map tool
# Format values with appropriate precision
```

**Story Points:** 2  
**Priority:** MUST  
**Dependencies:** US-03

---

### US-12: Real-time Preview

**As a** user  
**I want** to see filter changes immediately on the map  
**So that** I can fine-tune my selection

**Acceptance Criteria:**
- [ ] Map updates as I drag the slider
- [ ] Update rate is smooth (no lag)
- [ ] Debounce prevents excessive repaints
- [ ] Progress indicator for slow updates
- [ ] Cancel previous update if new one starts

**Technical Notes:**
```python
# Debounce: 100ms delay before applying
# Use QTimer for debounce
```

**Story Points:** 2  
**Priority:** MUST  
**Dependencies:** US-06, US-07

---

## Sprint 4: Polish & Release (Week 7-8)

### US-13: Large Raster Performance

**As a** user  
**I want** to work with large rasters (>500Mo)  
**So that** I can analyze IGN LiDAR data

**Acceptance Criteria:**
- [ ] Auto-sampling activates for rasters > 500Mo
- [ ] Histogram loads in < 5s with sampling
- [ ] "Sampled (10%)" indicator visible
- [ ] Memory usage stays < 200Mo
- [ ] No QGIS crash on 2GB rasters

**Technical Notes:**
```python
# Sampling: random 1M pixels
# GDAL windowed reading for efficiency
```

**Story Points:** 3  
**Priority:** MUST  
**Dependencies:** US-05

---

### US-14: Export Stats CSV

**As a** user  
**I want** to export raster statistics to CSV  
**So that** I can use them in reports

**Acceptance Criteria:**
- [ ] "Export Stats" button available
- [ ] CSV includes: layer, band, min, max, mean, std
- [ ] CSV includes current filter range if active
- [ ] File save dialog for path selection
- [ ] Success message after export

**Technical Notes:**
```python
# Format: CSV with headers
# Use QFileDialog for path
```

**Story Points:** 2  
**Priority:** MUST  
**Dependencies:** US-04

---

### US-15: Full Integration

**As a** user  
**I want** raster features fully integrated in FilterMate  
**So that** I have a seamless experience

**Acceptance Criteria:**
- [ ] Raster accordion in EXPLORING section
- [ ] Layer switch works smoothly
- [ ] No conflicts with vector features
- [ ] Settings persisted in config
- [ ] Documentation updated

**Technical Notes:**
```python
# Integration in filter_mate_dockwidget.py
# Config: config.json raster section
```

**Story Points:** 3  
**Priority:** MUST  
**Dependencies:** All previous stories

---

### US-16: Testing & Quality

**As a** developer  
**I want** comprehensive tests for raster features  
**So that** the code is reliable and maintainable

**Acceptance Criteria:**
- [ ] Unit tests: 80% coverage on new code
- [ ] Integration tests with sample rasters
- [ ] Performance benchmarks documented
- [ ] Manual testing checklist completed
- [ ] No critical bugs in issue tracker

**Technical Notes:**
```python
# pytest for unit tests
# qgis.testing for integration
# tests/data/dem_sample.tif for testing
```

**Story Points:** 3  
**Priority:** MUST  
**Dependencies:** All previous stories

---

## Sprint Summary

| Sprint | Stories | Total Points | Focus |
|--------|---------|--------------|-------|
| Sprint 1 | US-01 to US-04 | 9 | Core infrastructure |
| Sprint 2 | US-05 to US-08 | 13 | UI components |
| Sprint 3 | US-09 to US-12 | 9 | Advanced features |
| Sprint 4 | US-13 to US-16 | 11 | Polish & release |
| **TOTAL** | **16 stories** | **42 points** | |

---

## Definition of Done (DoD)

- [ ] Code written and reviewed
- [ ] Unit tests pass (80% coverage)
- [ ] Integration test pass
- [ ] Documentation updated
- [ ] No lint errors (pylint score > 9.0)
- [ ] Tested in QGIS 3.22+
- [ ] PR approved and merged

---

## Risk Register

| Risk | Story | Mitigation |
|------|-------|------------|
| Large raster OOM | US-13 | Sampling + windowed reading |
| Transparency API limits | US-06 | Fallback to renderer rules |
| Histogram performance | US-05 | Background task + sampling |
| Expression complexity | US-09 | Simple parser only (MVP) |

---

**Document Status: ✅ COMPLETE**
**Date: January 27, 2026**
**Author: BMAD Scrum Master**
