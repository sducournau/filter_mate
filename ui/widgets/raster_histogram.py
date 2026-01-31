"""
Note: Interactive Raster Histogram Widget for FilterMate.

Provides a visual histogram of raster band values with draggable range selection.
Uses PyQtGraph for fast rendering and interaction.

Author: FilterMate Team
Date: January 2026
"""

import numpy as np
from typing import Optional, Tuple

from qgis.PyQt.QtCore import Qt, pyqtSignal, QRectF
from qgis.PyQt.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from qgis.PyQt.QtGui import QColor, QPen, QBrush

from qgis.core import QgsRasterLayer, QgsRasterBandStats


from qgis.gui import QgsHistogramWidget

from infrastructure.logging import get_logger

logger = get_logger(__name__)


class RasterHistogramWidget(QWidget):
    """Interactive histogram widget for raster value selection.
    
    Features:
    - Display histogram of raster band values
    - Draggable min/max range selection
    - Real-time update of selected range
    - Integration with FilterMate raster filtering
    
    Signals:
        rangeChanged(float, float): Emitted when selection range changes
        rangeSelectionFinished(float, float): Emitted when user finishes dragging
    """
    
    rangeChanged = pyqtSignal(float, float)
    rangeSelectionFinished = pyqtSignal(float, float)
    
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        
        self._layer: Optional[QgsRasterLayer] = None
        self._band_index: int = 1
        self._histogram_data: Optional[np.ndarray] = None
        self._bin_edges: Optional[np.ndarray] = None
        self._min_val: float = 0.0
        self._max_val: float = 1.0
        self._selected_min: float = 0.0
        self._selected_max: float = 1.0
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the widget UI with QGIS native histogram widget."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        self._histogram_widget = QgsHistogramWidget(self)
        self._histogram_widget.setMinimumHeight(60)
        self._histogram_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._histogram_widget)

        # Info label (optionnel)
        self._info_label = QLabel("Histogram (QGIS native)")
        self._info_label.setAlignment(Qt.AlignCenter)
        self._info_label.setStyleSheet("font-size: 9px; color: #666;")
        layout.addWidget(self._info_label)

        logger.debug("RasterHistogramWidget (QGIS native) UI setup complete")
    
    def set_layer(self, layer: QgsRasterLayer, band_index: int = 1):
        """Set the raster layer and band to display histogram for (QGIS native)."""
        self._layer = layer
        self._band_index = band_index
        if layer is None:
            self._histogram_widget.clear()
            self._info_label.setText("No raster layer selected")
            return
        self._histogram_widget.setRasterLayer(layer, band_index)
        self._info_label.setText(f"Histogram: {layer.name()} (Band {band_index})")
    
    def force_compute(self):
        """v5.0: Force histogram computation even for large rasters.
        
        Called when user clicks Refresh button. Uses sampling for large rasters.
        """
        if not PYQTGRAPH_AVAILABLE or not self._layer:
            return
        
        logger.info(f"v5.0: Force computing histogram for {self._layer.name()}")
        self._info_label.setText("Computing histogram...")
        
        # Process events to show message before computation
        from qgis.PyQt.QtWidgets import QApplication
        QApplication.processEvents()
        
        self._compute_histogram()
        self._update_display()
    
    def _show_large_raster_placeholder(self, layer):
        """v5.0: Show placeholder for large rasters with info message."""
        if not PYQTGRAPH_AVAILABLE:
            return
        
        # Show empty histogram with message
        self._histogram_data = None
        self._histogram_item.setOpts(x=[0], height=[0], width=1)
        
        # Show informative message
        pixels = layer.width() * layer.height()
        msg = f"Large raster ({pixels:,} px)\nClick ↻ Refresh for histogram"
        self._info_label.setText(msg)
        self._info_label.setStyleSheet("font-size: 9px; color: #888; font-style: italic;")
    
    def _is_large_raster(self, layer) -> bool:
        """v5.0: Check if raster is too large for auto-compute.
        
        Args:
            layer: QgsRasterLayer to check
            
        Returns:
            True if raster should skip auto-compute
        """
        try:
            if not layer:
                return False
            
            # Check total pixels (threshold: 10M)
            total_pixels = layer.width() * layer.height()
            if total_pixels > 10_000_000:
                return True
            
            # Check if VRT
            source = layer.source()
            if source and source.lower().endswith('.vrt'):
                return True
            
            return False
        except Exception:
            return True  # Assume large on error
    
    def _compute_histogram(self):
        """Compute histogram data from the raster layer.
        
        v5.0: Uses sampling for large rasters to avoid freeze.
        v5.1: Improved VRT support with fallback histogram calculation.
        """
        if not self._layer or not self._layer.isValid():
            self._clear_histogram()
            return
        
        try:
            provider = self._layer.dataProvider()
            if not provider:
                logger.warning("No data provider for histogram")
                return
            
            # v5.0: Determine sample size based on raster size
            total_pixels = self._layer.width() * self._layer.height()
            LARGE_THRESHOLD = 10_000_000
            SAMPLE_SIZE = 250_000
            
            sample_size = SAMPLE_SIZE if total_pixels > LARGE_THRESHOLD else 0
            if sample_size > 0:
                logger.debug(f"v5.0: Using sampling ({sample_size:,}) for histogram")
            
            # Get band statistics for min/max
            stats = provider.bandStatistics(
                self._band_index,
                QgsRasterBandStats.Min | QgsRasterBandStats.Max,
                self._layer.extent(),
                sample_size
            )
            
            self._min_val = stats.minimumValue
            self._max_val = stats.maximumValue
            
            # v5.1: Check for invalid statistics (common with VRT)
            if self._min_val == self._max_val or not np.isfinite(self._min_val) or not np.isfinite(self._max_val):
                logger.warning(f"Invalid stats from provider: min={self._min_val}, max={self._max_val}")
                # Try to get stats from a subset for VRT
                if self._layer.source().lower().endswith('.vrt'):
                    self._compute_histogram_from_sample()
                    return
            
            # Get histogram from QGIS
            histogram = provider.histogram(
                self._band_index,
                256,  # Number of bins
                self._min_val,
                self._max_val,
                self._layer.extent(),
                sample_size
            )
            
            # v5.1: Validate histogram data
            if histogram and hasattr(histogram, 'histogramVector'):
                hist_vector = histogram.histogramVector
                if hist_vector and len(hist_vector) > 0 and sum(hist_vector) > 0:
                    self._histogram_data = np.array(hist_vector)
                    # Create bin edges
                    self._bin_edges = np.linspace(self._min_val, self._max_val, len(self._histogram_data) + 1)
                    
                    # Set initial selection to full range
                    self._selected_min = self._min_val
                    self._selected_max = self._max_val
                    
                    logger.debug(f"Histogram computed: {len(self._histogram_data)} bins, "
                               f"range [{self._min_val:.2f}, {self._max_val:.2f}]")
                else:
                    # v5.1: Empty histogram - try fallback for VRT
                    logger.warning("Empty histogram from provider - trying fallback")
                    self._compute_histogram_from_sample()
            else:
                logger.warning("Failed to get histogram data from provider")
                self._compute_histogram_from_sample()
                
        except Exception as e:
            logger.error(f"Error computing histogram: {e}", exc_info=True)
            self._histogram_data = None
    
    def _compute_histogram_from_sample(self):
        """v5.1: Compute histogram from sampled raster data (fallback for VRT).
        
        Uses QGIS block reading to get a sample of pixel values and builds
        histogram manually. This is slower but works for VRT.
        
        v5.1.1: Tries multiple sample positions if center has no data.
        v5.2: OPTIMIZED - Uses numpy array conversion instead of pixel-by-pixel loop.
        """
        try:
            from qgis.PyQt.QtWidgets import QApplication
            
            provider = self._layer.dataProvider()
            if not provider:
                logger.warning("No provider for histogram sampling")
                return
            
            # Try multiple sample positions (center, corners, random)
            raster_width = self._layer.width()
            raster_height = self._layer.height()
            extent = self._layer.extent()
            pixel_width = extent.width() / raster_width
            pixel_height = extent.height() / raster_height
            
            # v5.2: Smaller sample size for VRT to speed up computation
            # Each block read can be slow for VRT, so use fewer positions
            sample_width = min(300, raster_width)
            sample_height = min(300, raster_height)
            
            # Sample positions to try: center, then 4 corners
            sample_positions = [
                # Center
                ((raster_width - sample_width) // 2, (raster_height - sample_height) // 2),
                # Corners
                (0, 0),  # Top-left
                (raster_width - sample_width, 0),  # Top-right
                (0, raster_height - sample_height),  # Bottom-left
                (raster_width - sample_width, raster_height - sample_height),  # Bottom-right
            ]
            
            from qgis.core import QgsRectangle
            all_values = []
            
            for idx, (start_col, start_row) in enumerate(sample_positions):
                # Ensure valid bounds
                start_col = max(0, min(start_col, raster_width - sample_width))
                start_row = max(0, min(start_row, raster_height - sample_height))
                
                # Calculate extent for sample block
                sample_xmin = extent.xMinimum() + start_col * pixel_width
                sample_ymax = extent.yMaximum() - start_row * pixel_height
                sample_xmax = sample_xmin + sample_width * pixel_width
                sample_ymin = sample_ymax - sample_height * pixel_height
                
                sample_extent = QgsRectangle(sample_xmin, sample_ymin, sample_xmax, sample_ymax)
                
                # Read block data
                block = provider.block(self._band_index, sample_extent, sample_width, sample_height)
                if not block or not block.isValid():
                    logger.debug(f"Invalid block at position ({start_col}, {start_row})")
                    continue
                
                # v5.2: OPTIMIZED - Extract values using numpy instead of pixel loop
                # Get nodata value
                nodata_value = None
                if provider.sourceHasNoDataValue(self._band_index):
                    nodata_value = provider.sourceNoDataValue(self._band_index)
                
                # Extract all block values at once (much faster than pixel-by-pixel)
                block_values = []
                try:
                    # Try to get data as numpy array if available (QGIS 3.20+)
                    if hasattr(block, 'data'):
                        data = np.array(block.data())
                        if nodata_value is not None and np.isfinite(nodata_value):
                            valid_mask = (data != nodata_value) & np.isfinite(data)
                        else:
                            valid_mask = np.isfinite(data)
                        block_values = data[valid_mask].tolist()
                    else:
                        # Fallback: sample only a subset of pixels (skip every Nth)
                        step = max(1, sample_height // 100)  # ~100 rows max
                        for row in range(0, sample_height, step):
                            for col in range(0, sample_width, step):
                                if not block.isNoData(row, col):
                                    val = block.value(row, col)
                                    if np.isfinite(val):
                                        block_values.append(val)
                except Exception as e:
                    logger.debug(f"Fast extraction failed, using fallback: {e}")
                    # Fallback with stride sampling
                    step = max(1, sample_height // 50)
                    for row in range(0, sample_height, step):
                        for col in range(0, sample_width, step):
                            try:
                                if not block.isNoData(row, col):
                                    val = block.value(row, col)
                                    if np.isfinite(val):
                                        block_values.append(val)
                            except Exception:
                                pass
                
                if block_values:
                    all_values.extend(block_values)
                    logger.debug(f"Sample {idx+1}/{len(sample_positions)}: {len(block_values)} values")
                
                # v5.2: Process events to keep UI responsive during VRT reads
                QApplication.processEvents()
                
                # Stop if we have enough samples (100k is sufficient for histogram)
                if len(all_values) >= 100_000:
                    break
            
            if not all_values:
                logger.warning("No valid values found in any sample position")
                self._histogram_data = None
                return
            
            values = np.array(all_values)
            self._min_val = float(np.nanmin(values))
            self._max_val = float(np.nanmax(values))
            
            # Build histogram
            if self._min_val < self._max_val:
                self._histogram_data, self._bin_edges = np.histogram(
                    values, bins=256, range=(self._min_val, self._max_val)
                )
                self._selected_min = self._min_val
                self._selected_max = self._max_val
                logger.info(f"v5.1: VRT histogram from {len(all_values):,} sampled values, "
                           f"range [{self._min_val:.2f}, {self._max_val:.2f}]")
            else:
                logger.warning(f"Invalid range for histogram: [{self._min_val}, {self._max_val}]")
                self._histogram_data = None
                
        except Exception as e:
            logger.error(f"Error computing histogram from sample: {e}", exc_info=True)
            self._histogram_data = None
    
    def _update_display(self):
        """Update the histogram display with current data."""
        if not PYQTGRAPH_AVAILABLE:
            logger.warning("_update_display: pyqtgraph not available")
            return
        if self._histogram_data is None:
            logger.warning("_update_display: no histogram data - showing message")
            self._info_label.setText("Could not compute histogram\nTry selecting a different band")
            self._info_label.setStyleSheet("font-size: 9px; color: #888; font-style: italic;")
            return
        
        try:
            # Calculate bar positions and widths
            bin_width = (self._max_val - self._min_val) / len(self._histogram_data)
            x_positions = self._bin_edges[:-1] + bin_width / 2  # Center of each bin
            
            # Normalize heights for display
            max_count = np.max(self._histogram_data) if np.max(self._histogram_data) > 0 else 1
            heights = self._histogram_data / max_count
            
            logger.info(f"Histogram display: {len(heights)} bars, max_count={max_count}, "
                       f"range [{self._min_val:.2f}, {self._max_val:.2f}]")
            
            # Update bar graph
            self._histogram_item.setOpts(
                x=x_positions,
                height=heights,
                width=bin_width * 0.9
            )
            
            # Update selection region bounds
            self._selection_region.setBounds([self._min_val, self._max_val])
            self._selection_region.setRegion([self._selected_min, self._selected_max])
            
            # Auto-range the plot
            self._plot_widget.setXRange(self._min_val, self._max_val, padding=0.02)
            self._plot_widget.setYRange(0, 1.1, padding=0)
            
            # Update info label
            self._update_info_label()
            
            # Force widget update
            self._plot_widget.repaint()
            
        except Exception as e:
            logger.error(f"Error updating histogram display: {e}")
    
    def _clear_histogram(self):
        """Clear the histogram display."""
        if not PYQTGRAPH_AVAILABLE:
            return
            
        self._histogram_data = None
        self._bin_edges = None
        self._histogram_item.setOpts(x=[0], height=[0], width=1)
        self._info_label.setText("No raster layer selected")
    
    def _on_region_changed(self):
        """Handle region change (while dragging)."""
        region = self._selection_region.getRegion()
        self._selected_min = max(region[0], self._min_val)
        self._selected_max = min(region[1], self._max_val)
        
        self._update_info_label()
        self.rangeChanged.emit(self._selected_min, self._selected_max)
    
    def _on_region_change_finished(self):
        """Handle region change finished (drag complete)."""
        region = self._selection_region.getRegion()
        self._selected_min = max(region[0], self._min_val)
        self._selected_max = min(region[1], self._max_val)
        
        self.rangeSelectionFinished.emit(self._selected_min, self._selected_max)
        logger.debug(f"Range selection finished: [{self._selected_min:.2f}, {self._selected_max:.2f}]")
    
    def _update_info_label(self):
        """Update the info label with current selection."""
        if self._histogram_data is not None:
            # Calculate percentage of histogram in selection
            if self._bin_edges is not None:
                mask = (self._bin_edges[:-1] >= self._selected_min) & (self._bin_edges[1:] <= self._selected_max)
                selected_count = np.sum(self._histogram_data[mask])
                total_count = np.sum(self._histogram_data)
                percentage = (selected_count / total_count * 100) if total_count > 0 else 0
                
                self._info_label.setText(
                    f"Range: [{self._selected_min:.1f} - {self._selected_max:.1f}] "
                    f"({percentage:.1f}% of pixels)"
                )
            else:
                self._info_label.setText(
                    f"Range: [{self._selected_min:.1f} - {self._selected_max:.1f}]"
                )
    
    def set_range(self, min_val: float, max_val: float):
        """Set the selection range programmatically.
        
        Args:
            min_val: Minimum value
            max_val: Maximum value
        """
        if not PYQTGRAPH_AVAILABLE:
            return
            
        self._selected_min = max(min_val, self._min_val)
        self._selected_max = min(max_val, self._max_val)
        
        self._selection_region.setRegion([self._selected_min, self._selected_max])
        self._update_info_label()
    
    def get_range(self) -> Tuple[float, float]:
        """Get the current selection range.
        
        Returns:
            Tuple of (min, max) values
        """
        return (self._selected_min, self._selected_max)
    
    def get_data_range(self) -> Tuple[float, float]:
        """Get the full data range (min/max of raster).
        
        Returns:
            Tuple of (min, max) values
        """
        return (self._min_val, self._max_val)


# Convenience function to check availability
def is_histogram_available() -> bool:
    """Check if histogram widget is available (pyqtgraph installed)."""
    return PYQTGRAPH_AVAILABLE
