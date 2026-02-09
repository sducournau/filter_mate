"""
Raster Mask Filter Task Module

QgsTask for filtering rasters by vector overlay (clipping operation).
Created for FilterMate v5.0 - EPIC Raster Visibility Controls (Story R-2).

This module contains RasterMaskTask, which handles:
- Clipping raster to polygon layer extent
- GDAL processing integration
- Memory-based or file-based output
- Progress reporting for large rasters
- Cancellation support

Architecture: Hexagonal - Application Layer (Task Port)
Location: core/tasks/raster_mask_task.py

Author: Amelia (Developer)
Sprint: Sprint 2, Day 2
Date: 2026-02-06
"""

import logging
import os
from typing import Optional, Dict, Any
from pathlib import Path
import tempfile

from qgis.core import (
    Qgis,
    QgsTask,
    QgsRasterLayer,
    QgsVectorLayer,
    QgsProject,
    QgsMessageLog,
    QgsProcessing,
    QgsProcessingContext,
    QgsProcessingFeedback,
)
from qgis.PyQt.QtCore import pyqtSignal
from qgis.utils import iface
from qgis import processing

# Import logging configuration
from ...infrastructure.logging import setup_logger
from ...config.config import ENV_VARS

# Setup logger
logger = setup_logger(
    'FilterMate.Tasks.RasterMask',
    os.path.join(ENV_VARS.get("PATH_ABSOLUTE_PROJECT", "."), 'logs', 'filtermate_tasks.log'),
    level=logging.INFO
)


class RasterMaskTask(QgsTask):
    """
    Background task for clipping rasters by vector polygon mask.
    
    Uses GDAL cliprasterbymasklayer algorithm for efficient clipping.
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
        mask_layer: QgsVectorLayer,
        default_opacity: int = 70,
        crop_to_cutline: bool = True,
        keep_resolution: bool = True,
        task_description: str = "Apply Raster Vector Mask"
    ):
        """
        Initialize raster mask task.
        
        Args:
            source_layer: Source raster layer to clip
            mask_layer: Polygon vector layer to use as mask
            default_opacity: Default opacity for result layer (0-100)
            crop_to_cutline: Crop raster to exact mask extent
            keep_resolution: Maintain original raster resolution
            task_description: Task description for QGIS task manager
        """
        super().__init__(task_description, QgsTask.CanCancel)
        
        # Store thread-safe layer metadata (strings only, no QObject references)
        self.source_layer_id = source_layer.id()
        self.source_layer_name = source_layer.name()
        self.source_layer_uri = source_layer.dataProvider().dataSourceUri()
        self.source_layer_crs = source_layer.crs().authid()
        self.mask_layer_id = mask_layer.id()
        self.mask_layer_name = mask_layer.name()
        self.mask_layer_uri = mask_layer.dataProvider().dataSourceUri()
        self.mask_layer_provider = mask_layer.dataProvider().name()
        self.mask_geometry_type = mask_layer.geometryType()
        
        self.default_opacity = default_opacity / 100.0  # Convert to 0-1 range
        self.crop_to_cutline = crop_to_cutline
        self.keep_resolution = keep_resolution
        
        # Result storage (populated in run(), used in finished())
        self.result_layer = None
        self.result_metadata = {}
        self.exception = None
        self.output_path = None
        
        logger.info(
            f"RasterMaskTask initialized: "
            f"raster={self.source_layer_name}, "
            f"mask={self.mask_layer_name}"
        )
    
    def run(self) -> bool:
        """
        Execute task in background thread.
        
        THREAD SAFETY:
        - Recreates layers from URI (no shared QObject references)
        - Does NOT access QGIS UI elements (iface, messageBar, etc.)
        - Does NOT call QgsProject.instance().addMapLayer() here
        - Only prepares data, defers UI updates to finished()
        
        Returns:
            bool: True on success, False on failure
        """
        try:
            logger.info(f"Starting raster mask task for {self.source_layer_name}")
            
            # Check if cancelled
            if self.isCanceled():
                logger.info("Task cancelled before execution")
                return False
            
            # Recreate layers from URI in background thread (thread-safe)
            source_layer = QgsRasterLayer(
                self.source_layer_uri, self.source_layer_name, 'gdal'
            )
            if not source_layer.isValid():
                raise ValueError(
                    f"Source layer '{self.source_layer_name}' cannot be loaded from URI"
                )
            
            mask_layer = QgsVectorLayer(
                self.mask_layer_uri, self.mask_layer_name, self.mask_layer_provider
            )
            if not mask_layer.isValid():
                raise ValueError(
                    f"Mask layer '{self.mask_layer_name}' cannot be loaded from URI"
                )
            
            # Check mask geometry type (stored at init time for fast validation)
            if self.mask_geometry_type != 2:  # 2 = Polygon
                raise ValueError(
                    f"Mask layer must be polygon type, got {self.mask_geometry_type}"
                )
            
            # Progress: 10%
            self.setProgress(10)
            
            # Create output path in temp directory
            temp_dir = tempfile.gettempdir()
            output_filename = f"fm_masked_{self.source_layer_id[:8]}.tif"
            self.output_path = os.path.join(temp_dir, output_filename)
            
            logger.info(f"Output will be saved to: {self.output_path}")
            
            # Progress: 20%
            self.setProgress(20)
            
            # Prepare GDAL clip parameters using recreated layers
            params = {
                'INPUT': source_layer,
                'MASK': mask_layer,
                'OUTPUT': self.output_path,
                'CROP_TO_CUTLINE': self.crop_to_cutline,
                'KEEP_RESOLUTION': self.keep_resolution,
                'NODATA': -9999,
                'ALPHA_BAND': False,
                'MULTITHREADING': True,
            }
            
            # Progress: 30%
            self.setProgress(30)
            
            # Create processing feedback for progress reporting
            feedback = QgsProcessingFeedback()
            
            # Map GDAL progress (0-100) to task progress (30-90)
            feedback.progressChanged.connect(
                lambda progress: self.setProgress(30 + int(progress * 0.6))
            )
            
            # Create processing context
            context = QgsProcessingContext()
            context.setFeedback(feedback)
            
            # Run GDAL clip algorithm
            logger.info("Running GDAL cliprasterbymasklayer algorithm")
            result = processing.run(
                "gdal:cliprasterbymasklayer",
                params,
                context=context,
                feedback=feedback
            )
            
            # Check if cancelled during processing
            if self.isCanceled():
                logger.info("Task cancelled during GDAL processing")
                self._cleanup_temp_file()
                return False
            
            # Progress: 90%
            self.setProgress(90)
            
            # Load result as raster layer
            output_path = result['OUTPUT']
            layer_name = f"{self.source_layer_name}_masked"
            
            self.result_layer = QgsRasterLayer(output_path, layer_name, 'gdal')
            
            if not self.result_layer or not self.result_layer.isValid():
                raise RuntimeError(f"Failed to load clipped raster from {output_path}")
            
            # Set layer opacity
            self.result_layer.setOpacity(self.default_opacity)
            
            # Store metadata
            self.result_metadata = {
                'source_layer_id': self.source_layer_id,
                'source_layer_name': self.source_layer_name,
                'mask_layer_id': self.mask_layer_id,
                'mask_layer_name': self.mask_layer_name,
                'output_path': output_path,
                'crop_to_cutline': self.crop_to_cutline,
                'filtermate_temp': True,
                'filtermate_type': 'raster_mask',
            }
            
            # Progress: 100%
            self.setProgress(100)
            
            logger.info(f"Raster mask task completed successfully")
            return True
            
        except Exception as e:
            self.exception = e
            logger.error(f"Raster mask task failed: {str(e)}", exc_info=True)
            self._cleanup_temp_file()
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
    # Private Helper Methods
    # -------------------------------------------------------------------------
    
    def _cleanup_temp_file(self):
        """
        Remove temporary output file if task was cancelled or failed.
        """
        if self.output_path and os.path.exists(self.output_path):
            try:
                os.remove(self.output_path)
                logger.info(f"Cleaned up temp file: {self.output_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp file: {e}")


# Module exports
__all__ = ['RasterMaskTask']
