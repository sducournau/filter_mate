"""
FilterMate Export Module

v4.0 EPIC-1 Phase E1: Extracted from filter_task.py

This module handles layer export operations, including:
- Export parameter validation
- Style export (QML, SLD, LYRX)
- Single layer export
- Batch export to folder/zip
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
]
