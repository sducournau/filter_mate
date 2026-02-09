"""
Raster Statistics Task

v5.0.2: Async computation of raster band statistics to avoid QGIS freeze
with large rasters (VRT, etc.).

This task computes band statistics in a background thread, allowing the
UI to remain responsive while processing large rasters with many tiles.
"""

from qgis.core import (
    QgsTask,
    QgsRasterLayer,
    QgsRasterBandStats,
)
try:
    from qgis.core import Qgis
    _StatAll = Qgis.RasterBandStatistic.All
except AttributeError:
    _StatAll = QgsRasterBandStats.All
from qgis.PyQt.QtCore import pyqtSignal
import logging

from ...infrastructure.logging import get_logger

logger = get_logger(__name__)


class RasterStatsTask(QgsTask):
    """
    QgsTask for asynchronous computation of raster band statistics.
    
    This task prevents QGIS freeze when loading large VRT files or rasters
    with many tiles by computing statistics in a background thread.
    
    Signals:
        statsComputed (dict): Emitted on completion with statistics dictionary
            containing: min, max, mean, stddev, nodata, band_index, layer_id, layer_name
        statsFailed (str): Emitted if computation fails with error message
    
    Usage:
        task = RasterStatsTask(layer, band_index=1, sample_size=250000)
        task.statsComputed.connect(on_stats_ready)
        task.statsFailed.connect(on_stats_error)
        QgsApplication.taskManager().addTask(task)
    """
    
    statsComputed = pyqtSignal(dict)
    statsFailed = pyqtSignal(str)
    
    # Default threshold for large rasters (10M pixels = ~3000x3000)
    LARGE_RASTER_THRESHOLD = 10_000_000
    # Default sample size for large rasters
    DEFAULT_SAMPLE_SIZE = 250_000
    
    def __init__(
        self,
        layer: QgsRasterLayer,
        band_index: int = 1,
        sample_size: int = None,
        force_full_scan: bool = False,
        description: str = None
    ):
        """
        Initialize raster statistics task.
        
        Args:
            layer: QgsRasterLayer to compute statistics for
            band_index: Band index (1-based) to compute statistics for
            sample_size: Number of pixels to sample (0 = all pixels)
                        If None, auto-determined based on raster size
            force_full_scan: If True, compute stats on all pixels (slow!)
            description: Task description for UI
        """
        desc = description or f"Computing statistics for {layer.name()} band {band_index}"
        super().__init__(desc, QgsTask.CanCancel)
        
        # Store layer info (not the layer itself - not thread safe)
        self._layer_source = layer.source()
        self._layer_id = layer.id()
        self._layer_name = layer.name()
        self._band_index = band_index
        self._force_full_scan = force_full_scan
        
        # Determine sample size
        if sample_size is not None:
            self._sample_size = sample_size
        elif force_full_scan:
            self._sample_size = 0  # 0 = all pixels
        else:
            # Auto-determine based on raster size
            total_pixels = layer.width() * layer.height()
            if total_pixels > self.LARGE_RASTER_THRESHOLD:
                self._sample_size = self.DEFAULT_SAMPLE_SIZE
                logger.info(
                    f"RasterStatsTask: Large raster detected ({total_pixels:,} pixels), "
                    f"using sampling ({self._sample_size:,} samples)"
                )
            else:
                self._sample_size = 0  # All pixels for smaller rasters
        
        # Store extent for stats computation
        self._extent = layer.extent()
        
        # Get NoData value
        provider = layer.dataProvider()
        if provider and provider.sourceHasNoDataValue(band_index):
            self._nodata = provider.sourceNoDataValue(band_index)
        else:
            self._nodata = None
        
        # Results
        self._stats = None
        self._error_message = None
    
    def run(self) -> bool:
        """
        Compute raster statistics in background thread.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(
                f"RasterStatsTask.run(): Computing stats for {self._layer_name} "
                f"band {self._band_index} (sample_size={self._sample_size})"
            )
            
            # Create layer from source (thread-safe)
            layer = QgsRasterLayer(self._layer_source, self._layer_name)
            if not layer.isValid():
                self._error_message = f"Failed to load raster layer: {self._layer_name}"
                logger.error(self._error_message)
                return False
            
            # Check for cancellation
            if self.isCanceled():
                return False
            
            # Get data provider
            provider = layer.dataProvider()
            if not provider:
                self._error_message = f"No data provider for layer: {self._layer_name}"
                logger.error(self._error_message)
                return False
            
            # Check for cancellation
            if self.isCanceled():
                return False
            
            # Compute statistics
            self.setProgress(10)
            
            stats = provider.bandStatistics(
                self._band_index,
                _StatAll,
                self._extent,
                self._sample_size
            )
            
            # Check for cancellation
            if self.isCanceled():
                return False
            
            self.setProgress(90)
            
            # Store results
            self._stats = {
                'min': stats.minimumValue,
                'max': stats.maximumValue,
                'mean': stats.mean,
                'stddev': stats.stdDev,
                'nodata': self._nodata,
                'band_index': self._band_index,
                'layer_id': self._layer_id,
                'layer_name': self._layer_name,
                'sample_size': self._sample_size,
                'was_sampled': self._sample_size > 0
            }
            
            logger.info(
                f"RasterStatsTask: Stats computed for {self._layer_name} band {self._band_index}: "
                f"min={stats.minimumValue:.2f}, max={stats.maximumValue:.2f}, "
                f"mean={stats.mean:.2f}, stddev={stats.stdDev:.2f}"
            )
            
            self.setProgress(100)
            return True
            
        except Exception as e:
            self._error_message = f"Error computing statistics: {str(e)}"
            logger.error(f"RasterStatsTask.run() failed: {e}", exc_info=True)
            return False
    
    def finished(self, result: bool):
        """
        Called on main thread when task completes.
        
        Args:
            result: True if run() succeeded, False otherwise
        """
        if result and self._stats:
            logger.debug(f"RasterStatsTask.finished(): Emitting statsComputed signal")
            self.statsComputed.emit(self._stats)
        else:
            error_msg = self._error_message or "Unknown error computing raster statistics"
            logger.warning(f"RasterStatsTask.finished(): Emitting statsFailed signal: {error_msg}")
            self.statsFailed.emit(error_msg)
    
    def cancel(self):
        """Cancel the task."""
        logger.debug(f"RasterStatsTask: Cancellation requested for {self._layer_name}")
        super().cancel()
