# -*- coding: utf-8 -*-
"""
Unified Export Adapter.

Bridges the UI controllers with the UnifiedFilterService for
seamless vector and raster export operations.

This adapter:
- Translates UI export configurations to filter criteria
- Provides a unified API for both vector and raster exports
- Handles progress reporting and cancellation
- Maintains backward compatibility with existing controllers

Part of the Unified Filter System (EPIC-UNIFIED-FILTER).

Author: FilterMate Team
Date: February 2026
Version: 5.0.0-alpha
"""

import logging
import os
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger('FilterMate.Adapters.UnifiedExport')


@dataclass
class UnifiedExportRequest:
    """Unified request for export operations.
    
    Works for both vector and raster layers.
    """
    layer_id: str
    output_path: str
    
    # Layer type (auto-detected if None)
    layer_type: Optional[str] = None  # 'vector' or 'raster'
    
    # Common options
    crs_authid: Optional[str] = None  # e.g., 'EPSG:4326'
    
    # Vector-specific options
    vector_format: Optional[str] = None  # 'GPKG', 'ESRI Shapefile', etc.
    expression: Optional[str] = None
    selected_only: bool = False
    
    # Raster-specific options  
    raster_format: Optional[str] = None  # 'GTiff', 'COG', etc.
    compression: Optional[str] = None  # 'LZW', 'DEFLATE', etc.
    band_index: int = 1
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mask_layer_id: Optional[str] = None
    create_pyramids: bool = False
    
    # Progress callback
    progress_callback: Optional[Callable[[int, str], None]] = None


@dataclass
class UnifiedExportResult:
    """Result from unified export operation."""
    success: bool
    output_path: Optional[str] = None
    layer_type: str = ""
    feature_count: int = 0
    pixel_count: int = 0
    file_size_bytes: Optional[int] = None
    execution_time_ms: float = 0.0
    error_message: Optional[str] = None
    statistics: Dict[str, Any] = field(default_factory=dict)


class UnifiedExportAdapter:
    """Adapter for unified export operations.
    
    Provides a single API for exporting both vector and raster layers
    using the UnifiedFilterService infrastructure.
    
    Usage:
        adapter = UnifiedExportAdapter()
        
        # Export vector with filter
        result = adapter.export(UnifiedExportRequest(
            layer_id="communes",
            output_path="/tmp/filtered.gpkg",
            expression="population > 10000"
        ))
        
        # Export raster with value range
        result = adapter.export(UnifiedExportRequest(
            layer_id="dem",
            output_path="/tmp/elevation.tif",
            min_value=500,
            max_value=1500
        ))
    """
    
    def __init__(self, project=None):
        """Initialize the adapter.
        
        Args:
            project: QgsProject instance (or None for current)
        """
        self._project = project
        self._unified_service = None
        self._cancelled = False
    
    def _get_unified_service(self):
        """Lazy-load UnifiedFilterService."""
        if self._unified_service is None:
            try:
                from ..core.services.unified_filter_service import (
                    UnifiedFilterService,
                    FilterStrategyFactory
                )
                self._unified_service = UnifiedFilterService(
                    project=self._project
                )
            except ImportError as e:
                logger.warning(f"Could not import UnifiedFilterService: {e}")
        return self._unified_service
    
    def export(self, request: UnifiedExportRequest) -> UnifiedExportResult:
        """Export a layer using the unified filter system.
        
        Auto-detects layer type and uses the appropriate strategy.
        
        Args:
            request: Export request with all options
            
        Returns:
            UnifiedExportResult with operation status
        """
        import time
        start_time = time.time()
        
        self._cancelled = False
        
        try:
            # Detect layer type
            layer_type = request.layer_type or self._detect_layer_type(request.layer_id)
            
            if layer_type == 'vector':
                result = self._export_vector(request)
            elif layer_type == 'raster':
                result = self._export_raster(request)
            else:
                return UnifiedExportResult(
                    success=False,
                    error_message=f"Unknown layer type: {layer_type}"
                )
            
            # Add execution time
            result.execution_time_ms = (time.time() - start_time) * 1000
            
            return result
            
        except Exception as e:
            logger.exception(f"Export failed: {e}")
            return UnifiedExportResult(
                success=False,
                error_message=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
    
    def _export_vector(self, request: UnifiedExportRequest) -> UnifiedExportResult:
        """Export vector layer.
        
        Uses UnifiedFilterService if expression provided,
        otherwise falls back to direct QgsVectorFileWriter.
        """
        try:
            from qgis.core import (
                QgsProject,
                QgsVectorLayer,
                QgsVectorFileWriter,
                QgsCoordinateReferenceSystem,
                QgsCoordinateTransformContext
            )
            
            project = self._project or QgsProject.instance()
            layer = project.mapLayer(request.layer_id)
            
            if not layer or not isinstance(layer, QgsVectorLayer):
                return UnifiedExportResult(
                    success=False,
                    layer_type='vector',
                    error_message=f"Invalid vector layer: {request.layer_id}"
                )
            
            # Report progress
            if request.progress_callback:
                request.progress_callback(10, "Preparing export...")
            
            # Use UnifiedFilterService for filtered export
            if request.expression:
                return self._export_vector_with_filter(request, layer)
            
            # Direct export without filter
            return self._export_vector_direct(request, layer)
            
        except ImportError as e:
            return UnifiedExportResult(
                success=False,
                layer_type='vector',
                error_message=f"QGIS not available: {e}"
            )
    
    def _export_vector_with_filter(
        self, 
        request: UnifiedExportRequest, 
        layer
    ) -> UnifiedExportResult:
        """Export vector with filter expression using UnifiedFilterService."""
        try:
            from ..core.domain.filter_criteria import VectorFilterCriteria
            
            service = self._get_unified_service()
            if not service:
                # Fallback to direct export with subset
                return self._export_vector_direct(request, layer)
            
            # Build criteria
            criteria = VectorFilterCriteria(
                layer_id=request.layer_id,
                expression=request.expression,
                use_selection=request.selected_only
            )
            
            # Set progress callback on service context
            if request.progress_callback:
                service.context.progress_callback = request.progress_callback
            
            # Export via unified service
            result = service.export(
                criteria,
                request.output_path,
                format=request.vector_format or "GPKG",
                crs=request.crs_authid
            )
            
            if result.is_success:
                return UnifiedExportResult(
                    success=True,
                    output_path=request.output_path,
                    layer_type='vector',
                    feature_count=result.affected_count,
                    file_size_bytes=self._get_file_size(request.output_path),
                    statistics=result.statistics
                )
            else:
                return UnifiedExportResult(
                    success=False,
                    layer_type='vector',
                    error_message=result.error_message
                )
                
        except Exception as e:
            logger.warning(f"UnifiedFilterService export failed, using fallback: {e}")
            # Apply filter manually and use direct export
            layer.setSubsetString(request.expression)
            result = self._export_vector_direct(request, layer)
            layer.setSubsetString("")  # Reset filter
            return result
    
    def _export_vector_direct(
        self, 
        request: UnifiedExportRequest, 
        layer
    ) -> UnifiedExportResult:
        """Direct vector export using QgsVectorFileWriter."""
        try:
            from qgis.core import (
                QgsVectorFileWriter,
                QgsCoordinateReferenceSystem,
                QgsCoordinateTransformContext
            )
            
            if request.progress_callback:
                request.progress_callback(30, "Writing features...")
            
            # Determine output format
            driver_name = request.vector_format or "GPKG"
            
            # CRS handling
            dest_crs = layer.crs()
            if request.crs_authid:
                dest_crs = QgsCoordinateReferenceSystem(request.crs_authid)
            
            # Write options
            options = QgsVectorFileWriter.SaveVectorOptions()
            options.driverName = driver_name
            options.fileEncoding = "UTF-8"
            
            # Write layer
            error_code, error_message = QgsVectorFileWriter.writeAsVectorFormatV2(
                layer,
                request.output_path,
                QgsCoordinateTransformContext(),
                options
            )
            
            if request.progress_callback:
                request.progress_callback(100, "Export complete")
            
            if error_code == QgsVectorFileWriter.NoError:
                return UnifiedExportResult(
                    success=True,
                    output_path=request.output_path,
                    layer_type='vector',
                    feature_count=layer.featureCount(),
                    file_size_bytes=self._get_file_size(request.output_path)
                )
            else:
                return UnifiedExportResult(
                    success=False,
                    layer_type='vector',
                    error_message=error_message or f"Write error: {error_code}"
                )
                
        except Exception as e:
            return UnifiedExportResult(
                success=False,
                layer_type='vector',
                error_message=str(e)
            )
    
    def _export_raster(self, request: UnifiedExportRequest) -> UnifiedExportResult:
        """Export raster layer.
        
        Uses UnifiedFilterService for filtered/clipped export,
        otherwise uses RasterExporter directly.
        """
        try:
            from qgis.core import QgsProject, QgsRasterLayer
            
            project = self._project or QgsProject.instance()
            layer = project.mapLayer(request.layer_id)
            
            if not layer or not isinstance(layer, QgsRasterLayer):
                return UnifiedExportResult(
                    success=False,
                    layer_type='raster',
                    error_message=f"Invalid raster layer: {request.layer_id}"
                )
            
            if request.progress_callback:
                request.progress_callback(10, "Preparing raster export...")
            
            # Use UnifiedFilterService if filtering needed
            if request.min_value is not None or request.max_value is not None or request.mask_layer_id:
                return self._export_raster_with_filter(request, layer)
            
            # Direct export
            return self._export_raster_direct(request, layer)
            
        except ImportError as e:
            return UnifiedExportResult(
                success=False,
                layer_type='raster',
                error_message=f"QGIS not available: {e}"
            )
    
    def _export_raster_with_filter(
        self, 
        request: UnifiedExportRequest, 
        layer
    ) -> UnifiedExportResult:
        """Export raster with filter using UnifiedFilterService."""
        try:
            from ..core.domain.filter_criteria import RasterFilterCriteria
            
            service = self._get_unified_service()
            if not service:
                return self._export_raster_direct(request, layer)
            
            # Build criteria
            criteria = RasterFilterCriteria(
                layer_id=request.layer_id,
                band_index=request.band_index,
                min_value=request.min_value,
                max_value=request.max_value,
                mask_layer_id=request.mask_layer_id
            )
            
            if request.progress_callback:
                service.context.progress_callback = request.progress_callback
            
            # Export via unified service
            result = service.export(
                criteria,
                request.output_path,
                format=request.raster_format or "GTiff",
                compression=request.compression or "LZW"
            )
            
            if result.is_success:
                return UnifiedExportResult(
                    success=True,
                    output_path=request.output_path,
                    layer_type='raster',
                    pixel_count=result.affected_count,
                    file_size_bytes=self._get_file_size(request.output_path),
                    statistics=result.statistics
                )
            else:
                return UnifiedExportResult(
                    success=False,
                    layer_type='raster',
                    error_message=result.error_message
                )
                
        except Exception as e:
            logger.warning(f"UnifiedFilterService raster export failed: {e}")
            return self._export_raster_direct(request, layer)
    
    def _export_raster_direct(
        self, 
        request: UnifiedExportRequest, 
        layer
    ) -> UnifiedExportResult:
        """Direct raster export using RasterExporter."""
        try:
            from ..core.export.raster_exporter import (
                RasterExporter,
                RasterExportConfig,
                RasterExportFormat,
                CompressionType
            )
            
            if request.progress_callback:
                request.progress_callback(30, "Writing raster...")
            
            # Map format
            format_map = {
                'GTiff': RasterExportFormat.GEOTIFF,
                'COG': RasterExportFormat.COG,
                'PNG': RasterExportFormat.PNG,
                'JPEG': RasterExportFormat.JPEG,
            }
            
            compression_map = {
                'NONE': CompressionType.NONE,
                'LZW': CompressionType.LZW,
                'DEFLATE': CompressionType.DEFLATE,
                'ZSTD': CompressionType.ZSTD,
            }
            
            config = RasterExportConfig(
                layer=layer,
                output_path=request.output_path,
                format=format_map.get(request.raster_format, RasterExportFormat.GEOTIFF),
                compression=compression_map.get(request.compression, CompressionType.LZW),
                create_pyramids=request.create_pyramids
            )
            
            exporter = RasterExporter()
            result = exporter.export(config)
            
            if request.progress_callback:
                request.progress_callback(100, "Export complete")
            
            if result.success:
                return UnifiedExportResult(
                    success=True,
                    output_path=result.output_path,
                    layer_type='raster',
                    pixel_count=layer.width() * layer.height(),
                    file_size_bytes=self._get_file_size(result.output_path)
                )
            else:
                return UnifiedExportResult(
                    success=False,
                    layer_type='raster',
                    error_message=result.error_message
                )
                
        except ImportError as e:
            return UnifiedExportResult(
                success=False,
                layer_type='raster',
                error_message=f"RasterExporter not available: {e}"
            )
        except Exception as e:
            return UnifiedExportResult(
                success=False,
                layer_type='raster',
                error_message=str(e)
            )
    
    def cancel(self):
        """Cancel current export operation."""
        self._cancelled = True
        if self._unified_service:
            self._unified_service.cancel()
    
    def _detect_layer_type(self, layer_id: str) -> str:
        """Detect whether layer is vector or raster."""
        try:
            from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer
            
            project = self._project or QgsProject.instance()
            layer = project.mapLayer(layer_id)
            
            if isinstance(layer, QgsVectorLayer):
                return 'vector'
            elif isinstance(layer, QgsRasterLayer):
                return 'raster'
            else:
                return 'unknown'
                
        except ImportError:
            return 'unknown'
    
    def _get_file_size(self, path: str) -> Optional[int]:
        """Get file size in bytes."""
        try:
            return os.path.getsize(path) if os.path.exists(path) else None
        except Exception:
            return None
