"""
FilterMate Export Module

v4.0 EPIC-1 Phase E1-E11: Extracted from filter_task.py
Raster Support: Added RasterExporter for raster export support

This module handles layer export operations, including:
- Export parameter validation
- Style export (QML, SLD, LYRX)
- Single layer export (vector)
- Single raster export (GeoTIFF, COG)
- Batch export to folder/zip (E11: BatchExporter)
- GeoPackage export
- Streaming export for large datasets

Exported from modules.tasks.filter_task (~1,000 lines)
Pattern: Strangler Fig migration with legacy fallback
"""

from .layer_exporter import (
    LayerExporter,
    ExportConfig,
    ExportResult,
    ExportFormat,
)

from .style_exporter import (
    StyleExporter,
    StyleFormat,
    save_layer_style,
)

from .export_validator import (
    validate_export_parameters,
    ExportValidationResult,
)

from .batch_exporter import (
    BatchExporter,
    BatchExportResult,
    sanitize_filename,
)

from .raster_exporter import (
    RasterExporter,
    RasterExportConfig,
    RasterExportResult,
    RasterExportFormat,
    CompressionType,
    ResampleMethod,
    export_raster_simple,
    export_raster_clipped,
    export_raster_cog,
)

__all__ = [
    # Layer exporter
    'LayerExporter',
    'ExportConfig',
    'ExportResult',
    'ExportFormat',
    # Style exporter
    'StyleExporter',
    'StyleFormat',
    'save_layer_style',
    # Validator
    'validate_export_parameters',
    'ExportValidationResult',
    # Batch exporter (v4.0 E11)
    'BatchExporter',
    'BatchExportResult',
    'sanitize_filename',
    # Raster exporter (Raster Support)
    'RasterExporter',
    'RasterExportConfig',
    'RasterExportResult',
    'RasterExportFormat',
    'CompressionType',
    'ResampleMethod',
    'export_raster_simple',
    'export_raster_clipped',
    'export_raster_cog',
]
