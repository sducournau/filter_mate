"""
Raster Range Filter Task Module

QgsTask for filtering rasters by value range (background thread operation).
Created for FilterMate v5.0 - EPIC Raster Visibility Controls (Story R-1).

This module contains RasterRangeFilterTask, which handles:
- Raster transparency filtering based on min/max value range
- Single or multi-band raster support
- Memory-based or file-based output (configurable threshold)
- Progress reporting for large rasters
- Cancellation support

Architecture: Hexagonal - Application Layer (Task Port)
Location: core/tasks/raster_range_filter_task.py

Author: Amelia (Developer)
Sprint: Sprint 2, Day 1
Date: 2026-02-05
"""

import logging
import os
from typing import Optional, Dict, Any
from pathlib import Path

from qgis.core import (
    Qgis,
    QgsTask,
    QgsRasterLayer,
    QgsRasterTransparency,
    QgsProject,
    QgsMessageLog,
)
from qgis.PyQt.QtCore import pyqtSignal
from qgis.utils import iface

# Import logging configuration
from ...infrastructure.logging import setup_logger
from ...config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.RasterRangeFilter',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)


class RasterRangeFilterTask(QgsTask):
    """
    Background task for filtering rasters by value range.
    
    Applies transparency to pixels outside the specified min/max range.
    Uses QgsTask for non-blocking UI execution.
    
    Thread Safety:
    - run() executes in background thread (no UI access allowed)
    - finished() executes in main thread (safe for UI updates)
    
    Signals:
    - taskCompleted: Emitted on success with result layer
    - taskTerminated: Emitted on failure with error message
    """
    
    # Signals (connected in main thread)
    taskCompleted = pyqtSignal(QgsRasterLayer, dict)  # (result_layer, metadata)
    taskTerminated = pyqtSignal(str)  # (error_message)
    
    def __init__(
        self,
        source_layer: QgsRasterLayer,
        min_value: float,
        max_value: float,
        band: int = 1,
        default_opacity: int = 70,
        use_file_based_threshold_mb: int = 50,
        task_description: str = "Apply Raster Range Filter"
    ):
        """
        Initialize raster range filter task.
        
        Args:
            source_layer: Source raster layer to filter
            min_value: Minimum pixel value to show (inclusive)
            max_value: Maximum pixel value to show (inclusive)
            band: Band number to filter (1-based index)
            default_opacity: Default opacity for result layer (0-100)
            use_file_based_threshold_mb: Size threshold for file-based vs memory (MB)
            task_description: Task description for QGIS task manager
        """
        super().__init__(task_description, QgsTask.CanCancel)
        
        # Store thread-safe layer metadata (strings only, no QObject references)
        self.source_layer_id = source_layer.id()
        self.source_layer_name = source_layer.name()
        self.source_layer_uri = source_layer.dataProvider().dataSourceUri()
        self.source_layer_crs = source_layer.crs().authid()
        self.source_layer_width = source_layer.width()
        self.source_layer_height = source_layer.height()
        self.source_layer_band_count = source_layer.bandCount()
        
        # Filter parameters
        self.min_value = min_value
        self.max_value = max_value
        self.band = band
        self.default_opacity = default_opacity / 100.0  # Convert to 0-1 range
        self.use_file_based_threshold_mb = use_file_based_threshold_mb
        
        # Result storage (populated in run(), used in finished())
        self.result_layer = None
        self.result_metadata = {}
        self.exception = None
        
        logger.info(
            f"RasterRangeFilterTask initialized: "
            f"layer={self.source_layer_name}, "
            f"range=[{min_value}, {max_value}], "
            f"band={band}"
        )
    
    def run(self) -> bool:
        """
        Execute task in background thread.
        
        THREAD SAFETY:
        - Recreates layer from URI (no shared QObject references)
        - Does NOT access QGIS UI elements (iface, messageBar, etc.)
        - Does NOT call QgsProject.instance().addMapLayer() here
        - Only prepares data, defers UI updates to finished()
        
        Returns:
            bool: True on success, False on failure
        """
        try:
            logger.info(f"Starting raster range filter task for {self.source_layer_name}")
            
            # Check if cancelled
            if self.isCanceled():
                logger.info("Task cancelled before execution")
                return False
            
            # Recreate source layer from URI in background thread (thread-safe)
            source_layer = QgsRasterLayer(self.source_layer_uri, self.source_layer_name, 'gdal')
            if not source_layer.isValid():
                raise ValueError(
                    f"Source layer '{self.source_layer_name}' cannot be loaded from URI: "
                    f"{self.source_layer_uri}"
                )
            
            # Progress: 10%
            self.setProgress(10)
            
            # Validate band number
            band_count = source_layer.bandCount()
            if self.band < 1 or self.band > band_count:
                raise ValueError(
                    f"Band {self.band} out of range (layer has {band_count} bands)"
                )
            
            # Progress: 20%
            self.setProgress(20)
            
            # Check layer size to determine memory vs file-based approach
            layer_size_mb = self._estimate_layer_size_mb()
            use_file_based = layer_size_mb > self.use_file_based_threshold_mb
            
            logger.info(
                f"Layer size: ~{layer_size_mb:.1f} MB, "
                f"using {'file-based' if use_file_based else 'memory'} approach"
            )
            
            # Progress: 30%
            self.setProgress(30)
            
            # Create filtered layer (distinct copy, never the source)
            if use_file_based:
                self.result_layer = self._create_file_based_layer()
            else:
                self.result_layer = self._create_memory_layer()
            
            # Progress: 70%
            self.setProgress(70)
            
            if not self.result_layer or not self.result_layer.isValid():
                raise RuntimeError("Failed to create filtered raster layer")
            
            # Apply transparency to the COPY (not the source)
            self._apply_transparency()
            
            # Progress: 90%
            self.setProgress(90)
            
            # Set layer opacity
            self.result_layer.setOpacity(self.default_opacity)
            
            # Store metadata
            self.result_metadata = {
                'source_layer_id': self.source_layer_id,
                'source_layer_name': self.source_layer_name,
                'min_value': self.min_value,
                'max_value': self.max_value,
                'band': self.band,
                'layer_type': 'file' if use_file_based else 'memory',
                'size_mb': layer_size_mb,
                'filtermate_temp': True,
                'filtermate_type': 'raster_range',
            }
            
            # Progress: 100%
            self.setProgress(100)
            
            logger.info(f"Raster range filter task completed successfully")
            return True
            
        except Exception as e:
            self.exception = e
            logger.error(f"Raster range filter task failed: {str(e)}", exc_info=True)
            return False
    
    def finished(self, result: bool):
        """
        Called in main thread when task completes.
        
        SAFE to access UI elements here (iface, QgsProject, messageBar, etc.)
        
        Args:
            result: Return value from run() (True = success, False = failure)
        """
        if result:
            # Success - emit signal with result layer
            logger.info(f"Task finished successfully: {self.source_layer_name}")
            self.taskCompleted.emit(self.result_layer, self.result_metadata)
            
        else:
            # Failure - emit error signal
            error_msg = str(self.exception) if self.exception else "Unknown error"
            logger.error(f"Task finished with error: {error_msg}")
            self.taskTerminated.emit(error_msg)
    
    def cancel(self):
        """
        Cancel task execution.
        
        Can be called from main thread. Sets flag checked by run().
        """
        logger.info(f"Task cancellation requested: {self.source_layer_name}")
        super().cancel()
    
    # -------------------------------------------------------------------------
    # Private Helper Methods (run in background thread)
    # -------------------------------------------------------------------------
    
    def _estimate_layer_size_mb(self) -> float:
        """
        Estimate raster layer size in MB using stored metadata.
        
        Uses dimensions stored at init time (thread-safe, no layer access).
        
        Returns:
            float: Estimated size in megabytes
        """
        try:
            # Estimate: width * height * bands * 4 bytes (float32)
            size_bytes = (self.source_layer_width * self.source_layer_height 
                         * self.source_layer_band_count * 4)
            size_mb = size_bytes / (1024 * 1024)
            return size_mb
            
        except Exception as e:
            logger.warning(f"Could not estimate layer size: {e}")
            return 0.0
    
    def _create_memory_layer(self) -> Optional[QgsRasterLayer]:
        """
        Create VRT-based copy of source layer for non-destructive filtering.
        
        Uses GDAL BuildVRT to create a virtual raster referencing the source data,
        ensuring the original layer is never modified.
        
        Returns:
            QgsRasterLayer or None if failed
        """
        try:
            import tempfile
            from osgeo import gdal
            
            vrt_path = os.path.join(
                tempfile.gettempdir(),
                f"fm_range_{self.source_layer_id[:8]}_{self.band}.vrt"
            )
            
            vrt_ds = gdal.BuildVRT(vrt_path, [self.source_layer_uri])
            if vrt_ds is None:
                raise RuntimeError(f"GDAL BuildVRT failed: {gdal.GetLastErrorMsg()}")
            vrt_ds.FlushCache()
            vrt_ds = None  # Close dataset
            
            layer_name = f"{self.source_layer_name}_filtered"
            result = QgsRasterLayer(vrt_path, layer_name, 'gdal')
            
            if result.isValid():
                logger.info(f"Created VRT layer for non-destructive filtering: {vrt_path}")
                return result
            else:
                logger.error(f"VRT layer is invalid: {vrt_path}")
                return None
            
        except Exception as e:
            logger.error(f"Failed to create memory layer: {e}")
            return None
    
    def _create_file_based_layer(self) -> Optional[QgsRasterLayer]:
        """
        Create file-based copy of source layer for large rasters.
        
        Uses GDAL Translate to create a real GeoTIFF copy, ensuring the
        original layer is never modified.
        
        Returns:
            QgsRasterLayer or None if failed
        """
        try:
            import tempfile
            from osgeo import gdal
            
            output_path = os.path.join(
                tempfile.gettempdir(),
                f"fm_range_file_{self.source_layer_id[:8]}_{self.band}.tif"
            )
            
            ds = gdal.Translate(output_path, self.source_layer_uri)
            if ds is None:
                raise RuntimeError(f"GDAL Translate failed: {gdal.GetLastErrorMsg()}")
            ds.FlushCache()
            ds = None  # Close dataset
            
            layer_name = f"{self.source_layer_name}_filtered"
            result = QgsRasterLayer(output_path, layer_name, 'gdal')
            
            if result.isValid():
                logger.info(f"Created file-based layer copy: {output_path}")
                return result
            else:
                logger.error(f"File-based layer is invalid: {output_path}")
                return None
            
        except Exception as e:
            logger.error(f"Failed to create file-based layer: {e}")
            return None
    
    def _apply_transparency(self):
        """
        Apply transparency based on value range.
        
        Sets pixels outside [min_value, max_value] to transparent.
        
        FIX 2026-02-08 C6: Removed triggerRepaint() — called from run() (background thread).
        Repaint happens automatically when layer is added to project in finished() (main thread).
        FIX 2026-02-08 C7: Use 3-argument TransparentSingleValuePixel constructor (universal QGIS compat)
        with 100.0 (100% transparent) instead of 0.0.
        """
        try:
            # Get renderer
            renderer = self.result_layer.renderer()
            if not renderer:
                logger.warning("Layer has no renderer, cannot apply transparency")
                return
            
            # Create transparency object
            transparency = QgsRasterTransparency()
            
            # Create transparent pixel list
            # Pixels with values < min or > max become transparent
            transparent_pixels = []
            
            # Get band statistics for range
            try:
                _stat_all = Qgis.RasterBandStatistic.All
            except AttributeError:
                from qgis.core import QgsRasterBandStats
                _stat_all = QgsRasterBandStats.All
            stats = self.result_layer.dataProvider().bandStatistics(self.band, _stat_all)
            min_band_value = stats.minimumValue
            max_band_value = stats.maximumValue
            
            logger.info(
                f"Band {self.band} value range: [{min_band_value}, {max_band_value}]"
            )
            
            # Add transparency rules (3-arg constructor for QGIS version compatibility):
            # 1. Values below min_value → 100% transparent
            if self.min_value > min_band_value:
                transparent_pixels.append(
                    QgsRasterTransparency.TransparentSingleValuePixel(
                        min_band_value,
                        self.min_value - 0.001,
                        100.0
                    )
                )
            
            # 2. Values above max_value → 100% transparent
            if self.max_value < max_band_value:
                transparent_pixels.append(
                    QgsRasterTransparency.TransparentSingleValuePixel(
                        self.max_value + 0.001,
                        max_band_value,
                        100.0
                    )
                )
            
            if not transparent_pixels:
                logger.info("No transparency rules needed (filter range covers full band range)")
                return
            
            # Set transparency list
            transparency.setTransparentSingleValuePixelList(transparent_pixels)
            
            # Apply to renderer (repaint deferred to finished() on main thread)
            renderer.setRasterTransparency(transparency)
            
            logger.info(
                f"Applied transparency: {len(transparent_pixels)} rules "
                f"for range [{self.min_value}, {self.max_value}]"
            )
            
        except Exception as e:
            logger.error(f"Failed to apply transparency: {e}", exc_info=True)
            # Don't raise - layer is still usable without transparency


# Module exports
__all__ = ['RasterRangeFilterTask']
