# -*- coding: utf-8 -*-
"""
Raster Exporter

FilterMate - Raster Export Support

Handles raster layer export operations to various formats.
Supports:
- GeoTIFF export with compression options
- Cloud-Optimized GeoTIFF (COG) creation
- Clipping to vector mask
- Band selection
- Nodata handling
- World file (.tfw, .jgw) generation

Based on GDAL translate and warp algorithms via QGIS Processing.
"""

import os
import logging
import tempfile
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

try:
    from qgis.core import (
        QgsRasterLayer,
        QgsVectorLayer,
        QgsRasterFileWriter,
        QgsRasterPipe,
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsProject,
        QgsRectangle,
        Qgis
    )
    from qgis.PyQt.QtCore import QObject, pyqtSignal
    QGIS_AVAILABLE = True
except ImportError:
    QGIS_AVAILABLE = False
    QgsRasterLayer = Any
    QgsVectorLayer = Any
    QgsRasterFileWriter = Any
    QgsRasterPipe = Any
    QgsCoordinateReferenceSystem = Any
    QgsCoordinateTransform = Any
    QgsProject = Any
    QgsRectangle = Any
    QObject = object
    pyqtSignal = lambda *args: None

logger = logging.getLogger('FilterMate.RasterExport')


class RasterExportFormat(Enum):
    """Supported raster export formats."""
    GEOTIFF = "GTiff"
    COG = "COG"           # Cloud-Optimized GeoTIFF
    JPEG = "JPEG"
    PNG = "PNG"
    BMP = "BMP"
    VRT = "VRT"
    NETCDF = "netCDF"
    GPKG = "GPKG"         # GeoPackage raster


class CompressionType(Enum):
    """Compression options for GeoTIFF export."""
    NONE = "NONE"
    LZW = "LZW"
    DEFLATE = "DEFLATE"
    JPEG = "JPEG"
    ZSTD = "ZSTD"
    PACKBITS = "PACKBITS"


class ResampleMethod(Enum):
    """Resampling methods for raster operations."""
    NEAREST = "nearest"
    BILINEAR = "bilinear"
    CUBIC = "cubic"
    CUBICSPLINE = "cubicspline"
    LANCZOS = "lanczos"
    AVERAGE = "average"
    MODE = "mode"


@dataclass
class RasterExportConfig:
    """Configuration for raster export."""
    
    layer: QgsRasterLayer
    """Source raster layer to export."""
    
    output_path: str
    """Output file path."""
    
    format: RasterExportFormat = RasterExportFormat.GEOTIFF
    """Output format."""
    
    compression: CompressionType = CompressionType.LZW
    """Compression type (for GeoTIFF)."""
    
    target_crs: Optional[QgsCoordinateReferenceSystem] = None
    """Target CRS (None = keep source CRS)."""
    
    extent: Optional[QgsRectangle] = None
    """Clip extent (None = full extent)."""
    
    mask_layer: Optional[QgsVectorLayer] = None
    """Vector layer for clipping mask."""
    
    bands: Optional[List[int]] = None
    """Bands to export (None = all bands)."""
    
    resolution: Optional[Tuple[float, float]] = None
    """Target resolution (x, y) or None to keep original."""
    
    resample_method: ResampleMethod = ResampleMethod.NEAREST
    """Resampling method if resolution changes."""
    
    nodata_value: Optional[float] = None
    """Override nodata value."""
    
    create_pyramids: bool = False
    """Create overview pyramids (for COG)."""
    
    include_world_file: bool = False
    """Generate world file (.tfw, .jgw)."""
    
    tiled: bool = True
    """Create tiled TIFF (recommended for large files)."""
    
    bigtiff: str = "IF_SAFER"
    """BigTIFF mode: YES, NO, IF_NEEDED, IF_SAFER."""
    
    predictor: int = 2
    """Predictor for compression (2=horizontal differencing for integer)."""
    
    extra_options: Dict[str, str] = field(default_factory=dict)
    """Additional GDAL creation options."""


@dataclass
class RasterExportResult:
    """Result of raster export operation."""
    
    success: bool
    """Whether export succeeded."""
    
    output_path: Optional[str] = None
    """Path to exported file (if successful)."""
    
    output_size_mb: float = 0.0
    """Output file size in MB."""
    
    processing_time_seconds: float = 0.0
    """Export processing time."""
    
    error_message: Optional[str] = None
    """Error message if failed."""
    
    warnings: List[str] = field(default_factory=list)
    """Non-fatal warnings."""


class RasterExporter(QObject):
    """Raster layer export service.
    
    Handles exporting raster layers to various formats with options for:
    - Compression
    - CRS transformation
    - Clipping to extent or mask
    - Band selection
    - COG creation
    
    Signals:
        progressChanged: Emitted when progress changes (0-100)
        exportStarted: Emitted when export starts
        exportCompleted: Emitted when export completes
        errorOccurred: Emitted when error occurs
    """
    
    progressChanged = pyqtSignal(int, str)
    exportStarted = pyqtSignal(str)
    exportCompleted = pyqtSignal(str, bool)  # path, success
    errorOccurred = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cancelled = False
    
    def export(self, config: RasterExportConfig) -> RasterExportResult:
        """Export a raster layer according to configuration.
        
        Args:
            config: Export configuration
            
        Returns:
            RasterExportResult with success status and details
        """
        start_time = datetime.now()
        self._cancelled = False
        
        self.exportStarted.emit(config.layer.name())
        logger.info(f"Starting raster export: {config.layer.name()} → {config.output_path}")
        
        try:
            # Validate inputs
            validation_error = self._validate_config(config)
            if validation_error:
                return RasterExportResult(
                    success=False,
                    error_message=validation_error
                )
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(config.output_path), exist_ok=True)
            
            # Determine export method based on requirements
            if config.mask_layer:
                # Use GDAL clip for mask-based export
                result = self._export_with_mask(config)
            elif config.format == RasterExportFormat.COG:
                # Use GDAL translate for COG
                result = self._export_as_cog(config)
            elif config.target_crs and config.target_crs != config.layer.crs():
                # Use GDAL warp for reprojection
                result = self._export_with_warp(config)
            else:
                # Use simple translate
                result = self._export_simple(config)
            
            # Calculate file size
            if result.success and os.path.exists(config.output_path):
                result.output_size_mb = os.path.getsize(config.output_path) / (1024 * 1024)
            
            # Calculate processing time
            result.processing_time_seconds = (datetime.now() - start_time).total_seconds()
            
            # Generate world file if requested
            if result.success and config.include_world_file:
                self._generate_world_file(config)
            
            self.exportCompleted.emit(config.output_path, result.success)
            
            if result.success:
                logger.info(f"Raster export completed: {config.output_path} ({result.output_size_mb:.2f} MB)")
            else:
                logger.error(f"Raster export failed: {result.error_message}")
            
            return result
            
        except Exception as e:
            error_msg = f"Unexpected error during export: {str(e)}"
            logger.exception(error_msg)
            self.errorOccurred.emit(error_msg)
            return RasterExportResult(
                success=False,
                error_message=error_msg,
                processing_time_seconds=(datetime.now() - start_time).total_seconds()
            )
    
    def cancel(self):
        """Cancel ongoing export."""
        self._cancelled = True
    
    def _validate_config(self, config: RasterExportConfig) -> Optional[str]:
        """Validate export configuration.
        
        Returns:
            Error message if invalid, None if valid
        """
        if not config.layer or not config.layer.isValid():
            return "Invalid or null raster layer"
        
        if not config.output_path:
            return "Output path is required"
        
        # Check output directory is writable
        output_dir = os.path.dirname(config.output_path)
        if output_dir and not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except PermissionError:
                return f"Cannot create output directory: {output_dir}"
        
        # Validate mask layer if provided
        if config.mask_layer and not config.mask_layer.isValid():
            return "Invalid mask layer provided"
        
        # Validate bands
        if config.bands:
            band_count = config.layer.bandCount()
            invalid_bands = [b for b in config.bands if b < 1 or b > band_count]
            if invalid_bands:
                return f"Invalid band numbers: {invalid_bands}. Layer has {band_count} bands."
        
        return None
    
    def _export_simple(self, config: RasterExportConfig) -> RasterExportResult:
        """Simple export using GDAL translate."""
        try:
            import processing
            
            # Build creation options
            options = self._build_gdal_options(config)
            
            params = {
                'INPUT': config.layer,
                'TARGET_CRS': config.target_crs if config.target_crs else None,
                'NODATA': config.nodata_value,
                'COPY_SUBDATASETS': False,
                'OPTIONS': options,
                'DATA_TYPE': 0,  # Use input data type
                'OUTPUT': config.output_path
            }
            
            # Add extent if specified
            if config.extent:
                params['PROJWIN'] = f"{config.extent.xMinimum()},{config.extent.xMaximum()},{config.extent.yMinimum()},{config.extent.yMaximum()}"
            
            self.progressChanged.emit(10, "Starting GDAL translate...")
            
            if self._cancelled:
                return RasterExportResult(success=False, error_message="Export cancelled")
            
            result = processing.run("gdal:translate", params)
            
            self.progressChanged.emit(100, "Export complete")
            
            return RasterExportResult(
                success=True,
                output_path=result['OUTPUT']
            )
            
        except Exception as e:
            return RasterExportResult(
                success=False,
                error_message=f"GDAL translate failed: {str(e)}"
            )
    
    def _export_with_mask(self, config: RasterExportConfig) -> RasterExportResult:
        """Export with vector mask clipping."""
        try:
            import processing
            
            options = self._build_gdal_options(config)
            
            params = {
                'INPUT': config.layer,
                'MASK': config.mask_layer,
                'SOURCE_CRS': config.layer.crs() if config.layer.crs().isValid() else None,
                'TARGET_CRS': config.target_crs if config.target_crs else None,
                'TARGET_EXTENT': None,
                'NODATA': config.nodata_value,
                'ALPHA_BAND': False,
                'CROP_TO_CUTLINE': True,
                'KEEP_RESOLUTION': True,
                'SET_RESOLUTION': False,
                'OPTIONS': options,
                'DATA_TYPE': 0,
                'OUTPUT': config.output_path
            }
            
            self.progressChanged.emit(10, "Clipping raster by mask...")
            
            if self._cancelled:
                return RasterExportResult(success=False, error_message="Export cancelled")
            
            result = processing.run("gdal:cliprasterbymasklayer", params)
            
            self.progressChanged.emit(100, "Export complete")
            
            return RasterExportResult(
                success=True,
                output_path=result['OUTPUT']
            )
            
        except Exception as e:
            return RasterExportResult(
                success=False,
                error_message=f"Clip by mask failed: {str(e)}"
            )
    
    def _export_with_warp(self, config: RasterExportConfig) -> RasterExportResult:
        """Export with reprojection using GDAL warp."""
        try:
            import processing
            
            options = self._build_gdal_options(config)
            
            params = {
                'INPUT': config.layer,
                'SOURCE_CRS': config.layer.crs(),
                'TARGET_CRS': config.target_crs,
                'RESAMPLING': self._get_resample_index(config.resample_method),
                'NODATA': config.nodata_value,
                'TARGET_RESOLUTION': config.resolution[0] if config.resolution else None,
                'TARGET_EXTENT': None,
                'TARGET_EXTENT_CRS': None,
                'OPTIONS': options,
                'DATA_TYPE': 0,
                'MULTITHREADING': True,
                'OUTPUT': config.output_path
            }
            
            self.progressChanged.emit(10, "Reprojecting raster...")
            
            if self._cancelled:
                return RasterExportResult(success=False, error_message="Export cancelled")
            
            result = processing.run("gdal:warpreproject", params)
            
            self.progressChanged.emit(100, "Export complete")
            
            return RasterExportResult(
                success=True,
                output_path=result['OUTPUT']
            )
            
        except Exception as e:
            return RasterExportResult(
                success=False,
                error_message=f"GDAL warp failed: {str(e)}"
            )
    
    def _export_as_cog(self, config: RasterExportConfig) -> RasterExportResult:
        """Export as Cloud-Optimized GeoTIFF using GDAL COG driver.
        
        Requires GDAL >= 3.1 for native COG driver support.
        Falls back to standard GeoTIFF with tiling if COG driver unavailable.
        """
        try:
            from osgeo import gdal
            
            source_path = config.layer.dataProvider().dataSourceUri()
            
            # Check GDAL version for COG driver support
            gdal_version = int(gdal.VersionInfo('VERSION_NUM'))
            if gdal_version < 3010000:
                logger.warning(
                    f"COG driver requires GDAL >= 3.1, found {gdal.VersionInfo('RELEASE_NAME')}. "
                    f"Falling back to tiled GeoTIFF."
                )
                return self._export_simple(config)
            
            # COG creation options
            creation_options = [
                f'COMPRESS={config.compression.value}',
                f'BIGTIFF={config.bigtiff}',
            ]
            
            if config.create_pyramids:
                creation_options.append('OVERVIEWS=AUTO')
            
            self.progressChanged.emit(10, "Preparing COG export...")
            
            if self._cancelled:
                return RasterExportResult(success=False, error_message="Export cancelled")
            
            # Build translate options for COG output
            translate_options = gdal.TranslateOptions(
                format='COG',
                creationOptions=creation_options,
            )
            
            self.progressChanged.emit(20, "Writing COG...")
            
            if self._cancelled:
                return RasterExportResult(success=False, error_message="Export cancelled")
            
            # Export using GDAL COG driver
            logger.info(f"Exporting COG with options: {creation_options}")
            result_ds = gdal.Translate(
                config.output_path,
                source_path,
                options=translate_options
            )
            
            if result_ds is None:
                error_msg = gdal.GetLastErrorMsg() or "Unknown GDAL error"
                raise RuntimeError(f"GDAL COG export failed: {error_msg}")
            
            result_ds.FlushCache()
            result_ds = None  # Close dataset
            
            self.progressChanged.emit(90, "Finalizing COG...")
            
            if self._cancelled:
                # Clean up partial output
                try:
                    os.remove(config.output_path)
                except OSError:
                    pass
                return RasterExportResult(success=False, error_message="Export cancelled")
            
            # Calculate output size
            output_size_mb = 0.0
            if os.path.exists(config.output_path):
                output_size_mb = os.path.getsize(config.output_path) / (1024 * 1024)
            
            self.progressChanged.emit(100, "COG export complete")
            
            logger.info(
                f"COG export complete: {config.output_path} "
                f"({output_size_mb:.1f} MB)"
            )
            
            return RasterExportResult(
                success=True,
                output_path=config.output_path,
                output_size_mb=output_size_mb
            )
            
        except ImportError:
            return RasterExportResult(
                success=False,
                error_message="GDAL Python bindings not available for COG export"
            )
        except Exception as e:
            return RasterExportResult(
                success=False,
                error_message=f"COG export failed: {str(e)}"
            )
    
    def _build_gdal_options(self, config: RasterExportConfig) -> str:
        """Build GDAL creation options string."""
        options = []
        
        # Compression
        if config.compression != CompressionType.NONE:
            options.append(f"COMPRESS={config.compression.value}")
            
            # Add predictor for integer data with LZW/DEFLATE
            if config.compression in [CompressionType.LZW, CompressionType.DEFLATE]:
                options.append(f"PREDICTOR={config.predictor}")
        
        # Tiling
        if config.tiled:
            options.append("TILED=YES")
        
        # BigTIFF
        options.append(f"BIGTIFF={config.bigtiff}")
        
        # Add extra options
        for key, value in config.extra_options.items():
            options.append(f"{key}={value}")
        
        return "|".join(options) if options else ""
    
    def _get_resample_index(self, method: ResampleMethod) -> int:
        """Get GDAL resample method index."""
        method_map = {
            ResampleMethod.NEAREST: 0,
            ResampleMethod.BILINEAR: 1,
            ResampleMethod.CUBIC: 2,
            ResampleMethod.CUBICSPLINE: 3,
            ResampleMethod.LANCZOS: 4,
            ResampleMethod.AVERAGE: 5,
            ResampleMethod.MODE: 6
        }
        return method_map.get(method, 0)
    
    def _generate_world_file(self, config: RasterExportConfig):
        """Generate world file for the exported raster."""
        try:
            layer = QgsRasterLayer(config.output_path, "temp")
            if not layer.isValid():
                logger.warning("Cannot generate world file: invalid output layer")
                return
            
            extent = layer.extent()
            width = layer.width()
            height = layer.height()
            
            if width == 0 or height == 0:
                logger.warning("Cannot generate world file: zero dimensions")
                return
            
            pixel_width = extent.width() / width
            pixel_height = -extent.height() / height  # Negative for top-to-bottom
            
            x_origin = extent.xMinimum() + pixel_width / 2
            y_origin = extent.yMaximum() + pixel_height / 2
            
            # Determine world file extension
            base, ext = os.path.splitext(config.output_path)
            if ext.lower() in ['.tif', '.tiff']:
                world_ext = '.tfw'
            elif ext.lower() in ['.jpg', '.jpeg']:
                world_ext = '.jgw'
            elif ext.lower() == '.png':
                world_ext = '.pgw'
            else:
                world_ext = '.wld'
            
            world_path = base + world_ext
            
            with open(world_path, 'w') as f:
                f.write(f"{pixel_width}\n")
                f.write("0.0\n")  # rotation (typically 0)
                f.write("0.0\n")  # rotation (typically 0)
                f.write(f"{pixel_height}\n")
                f.write(f"{x_origin}\n")
                f.write(f"{y_origin}\n")
            
            logger.debug(f"World file generated: {world_path}")
            
        except Exception as e:
            logger.warning(f"Failed to generate world file: {e}")


# Convenience functions

def export_raster_simple(
    layer: QgsRasterLayer,
    output_path: str,
    compression: str = "LZW"
) -> RasterExportResult:
    """Simple raster export with sensible defaults.
    
    Args:
        layer: Raster layer to export
        output_path: Output file path
        compression: Compression type (LZW, DEFLATE, NONE, etc.)
        
    Returns:
        RasterExportResult
    """
    config = RasterExportConfig(
        layer=layer,
        output_path=output_path,
        compression=CompressionType[compression.upper()]
    )
    exporter = RasterExporter()
    return exporter.export(config)


def export_raster_clipped(
    layer: QgsRasterLayer,
    mask_layer: QgsVectorLayer,
    output_path: str,
    compression: str = "LZW"
) -> RasterExportResult:
    """Export raster clipped to vector mask.
    
    Args:
        layer: Raster layer to export
        mask_layer: Vector layer for clipping
        output_path: Output file path
        compression: Compression type
        
    Returns:
        RasterExportResult
    """
    config = RasterExportConfig(
        layer=layer,
        output_path=output_path,
        mask_layer=mask_layer,
        compression=CompressionType[compression.upper()]
    )
    exporter = RasterExporter()
    return exporter.export(config)


def export_raster_cog(
    layer: QgsRasterLayer,
    output_path: str,
    create_pyramids: bool = True
) -> RasterExportResult:
    """Export raster as Cloud-Optimized GeoTIFF.
    
    Args:
        layer: Raster layer to export
        output_path: Output file path
        create_pyramids: Whether to create overview pyramids
        
    Returns:
        RasterExportResult
    """
    config = RasterExportConfig(
        layer=layer,
        output_path=output_path,
        format=RasterExportFormat.COG,
        compression=CompressionType.LZW,
        create_pyramids=create_pyramids
    )
    exporter = RasterExporter()
    return exporter.export(config)
