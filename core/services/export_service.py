"""
Export Service - Unified Export Orchestration

Orchestrates all export operations for FilterMate.
Extracted from filter_task.py as part of optimization plan (Priority 1).

This service provides:
- Unified export interface
- Multi-layer batch export
- Format-specific export strategies
- Style preservation
- Progress reporting
- Streaming support for large datasets

Responsibilities:
- Validate export parameters
- Coordinate layer_exporter, style_exporter, batch_exporter
- Handle export to various formats (Shapefile, GeoPackage, etc.)
- Manage temporary files and cleanup
- Report progress and errors

Extracted from:
- filter_task.py: execute_exporting() (~600 lines)
- filter_task.py: _export_with_streaming()
- filter_task.py: _validate_export_parameters()

Author: FilterMate Team (BMAD optimization)
Date: January 14, 2026
"""

import logging
import os
from typing import List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

try:
    from qgis.core import QgsVectorLayer, QgsProject
except ImportError:
    QgsVectorLayer = None
    QgsProject = None

from ..ports.qgis_port import get_qgis_factory, IProject

logger = logging.getLogger('FilterMate.Services.Export')


class ExportFormat(Enum):
    """Supported export formats."""
    SHAPEFILE = "shp"
    GEOPACKAGE = "gpkg"
    GEOJSON = "geojson"
    KML = "kml"
    DXF = "dxf"
    TAB = "tab"


class StyleFormat(Enum):
    """Supported style formats."""
    QML = "qml"  # QGIS
    SLD = "sld"  # OGC Standard
    LYRX = "lyrx"  # ArcGIS Pro


@dataclass
class ExportConfig:
    """
    Configuration for export operations.

    Attributes:
        format: Export format
        projection: Target CRS (None = keep original)
        save_styles: Whether to save layer styles
        style_format: Style format to use
        use_streaming: Use streaming for large datasets
        chunk_size: Number of features per chunk (streaming mode)
        zip_output: Create zip archive
        overwrite: Overwrite existing files
    """
    format: ExportFormat = ExportFormat.SHAPEFILE
    projection: Optional[str] = None
    save_styles: bool = True
    style_format: StyleFormat = StyleFormat.QML
    use_streaming: bool = False
    chunk_size: int = 10000
    zip_output: bool = False
    overwrite: bool = False


@dataclass
class ExportResult:
    """
    Result of export operation.

    Attributes:
        success: Whether export succeeded
        output_path: Path to exported file(s)
        layers_exported: Number of layers exported
        features_exported: Total number of features exported
        errors: List of error messages
        warnings: List of warning messages
        elapsed_time: Time taken in seconds
    """
    success: bool = False
    output_path: Optional[str] = None
    layers_exported: int = 0
    features_exported: int = 0
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    elapsed_time: float = 0.0

    def __str__(self) -> str:
        """String representation."""
        status = "SUCCESS" if self.success else "FAILED"
        return (
            f"ExportResult({status}: {self.layers_exported} layers, "
            f"{self.features_exported} features, {self.elapsed_time:.2f}s)"
        )


class ExportService:
    """
    Service for orchestrating export operations.

    Coordinates layer_exporter, style_exporter, and batch_exporter modules
    to provide unified export interface.

    Usage:
        factory = get_qgis_factory()
        service = ExportService(project=factory.get_project())

        # Single layer export
        result = service.export_layer(
            layer=my_layer,
            output_path="/path/to/output.shp",
            config=ExportConfig(save_styles=True)
        )

        # Batch export
        result = service.export_batch(
            layers=[layer1, layer2, layer3],
            output_folder="/path/to/folder",
            config=ExportConfig(format=ExportFormat.GEOPACKAGE)
        )
    """

    def __init__(
        self,
        project: Optional[IProject] = None,
        progress_callback: Optional[Callable[[int], None]] = None,
        cancel_callback: Optional[Callable[[], bool]] = None
    ):
        """
        Initialize export service.

        Args:
            project: QGIS project instance (via adapter)
            progress_callback: Optional callback for progress (0-100)
            cancel_callback: Optional callback to check for cancellation
        """
        factory = get_qgis_factory()
        self.project = project or factory.get_project()
        self.progress_callback = progress_callback
        self.cancel_callback = cancel_callback

        logger.debug("ExportService initialized")

    def export_layer(
        self,
        layer: QgsVectorLayer,
        output_path: str,
        config: Optional[ExportConfig] = None
    ) -> ExportResult:
        """
        Export single layer to file.

        Args:
            layer: Vector layer to export
            output_path: Output file path
            config: Export configuration

        Returns:
            ExportResult with operation details
        """
        config = config or ExportConfig()
        result = ExportResult()

        try:
            # Validate parameters
            validation_errors = self._validate_export_parameters(
                layers=[layer],
                output_path=output_path,
                config=config
            )

            if validation_errors:
                result.errors = validation_errors
                logger.error(f"Export validation failed: {validation_errors}")
                return result

            # Import here to avoid circular dependencies
            from ...core.export.layer_exporter import export_single_layer

            # Report progress
            if self.progress_callback:
                self.progress_callback(0)

            # Execute export
            export_result = export_single_layer(
                layer=layer,
                output_path=output_path,
                projection=config.projection,
                datatype=config.format.value,
                save_styles=config.save_styles,
                style_format=config.style_format.value,
                overwrite=config.overwrite
            )

            if export_result.get('success'):
                result.success = True
                result.output_path = output_path
                result.layers_exported = 1
                result.features_exported = layer.featureCount()
                logger.info(f"Export successful: {output_path}")
            else:
                result.errors.append(export_result.get('error', 'Unknown error'))
                logger.error(f"Export failed: {result.errors}")

            # Report completion
            if self.progress_callback:
                self.progress_callback(100)

        except Exception as e:
            result.errors.append(str(e))
            logger.exception(f"Export exception: {e}")

        return result

    def export_batch(
        self,
        layers: List[QgsVectorLayer],
        output_folder: str,
        config: Optional[ExportConfig] = None
    ) -> ExportResult:
        """
        Export multiple layers to folder.

        Args:
            layers: List of layers to export
            output_folder: Output folder path
            config: Export configuration

        Returns:
            ExportResult with operation details
        """
        config = config or ExportConfig()
        result = ExportResult()

        try:
            # Validate parameters
            validation_errors = self._validate_export_parameters(
                layers=layers,
                output_path=output_folder,
                config=config
            )

            if validation_errors:
                result.errors = validation_errors
                logger.error(f"Batch export validation failed: {validation_errors}")
                return result

            # Import here to avoid circular dependencies
            from ...core.export.batch_exporter import export_batch_layers

            # Execute batch export
            batch_result = export_batch_layers(
                layers=layers,
                output_folder=output_folder,
                projection=config.projection,
                datatype=config.format.value,
                save_styles=config.save_styles,
                style_format=config.style_format.value,
                zip_output=config.zip_output,
                progress_callback=self.progress_callback,
                cancel_callback=self.cancel_callback
            )

            if batch_result.get('success'):
                result.success = True
                result.output_path = batch_result.get('output_path')
                result.layers_exported = len(layers)
                result.features_exported = sum(layer.featureCount() for layer in layers)
                logger.info(f"Batch export successful: {result.layers_exported} layers")
            else:
                result.errors.append(batch_result.get('error', 'Unknown error'))
                logger.error(f"Batch export failed: {result.errors}")

        except Exception as e:
            result.errors.append(str(e))
            logger.exception(f"Batch export exception: {e}")

        return result

    def export_to_geopackage(
        self,
        layers: List[QgsVectorLayer],
        output_path: str,
        save_styles: bool = True
    ) -> ExportResult:
        """
        Export multiple layers to single GeoPackage.

        Args:
            layers: List of layers to export
            output_path: Output GeoPackage path
            save_styles: Whether to save styles

        Returns:
            ExportResult with operation details
        """
        config = ExportConfig(
            format=ExportFormat.GEOPACKAGE,
            save_styles=save_styles
        )

        result = ExportResult()

        try:
            # Validate
            if not output_path.endswith('.gpkg'):
                output_path += '.gpkg'

            # Import here to avoid circular dependencies
            from ...core.export.batch_exporter import export_to_geopackage

            # Execute
            gpkg_result = export_to_geopackage(
                layers=layers,
                output_path=output_path,
                save_styles=save_styles,
                progress_callback=self.progress_callback
            )

            if gpkg_result.get('success'):
                result.success = True
                result.output_path = output_path
                result.layers_exported = len(layers)
                result.features_exported = sum(layer.featureCount() for layer in layers)
                logger.info(f"GeoPackage export successful: {output_path}")
            else:
                result.errors.append(gpkg_result.get('error', 'Unknown error'))

        except Exception as e:
            result.errors.append(str(e))
            logger.exception(f"GeoPackage export exception: {e}")

        return result

    def _validate_export_parameters(
        self,
        layers: List[QgsVectorLayer],
        output_path: str,
        config: ExportConfig
    ) -> List[str]:
        """
        Validate export parameters.

        Args:
            layers: Layers to export
            output_path: Output path
            config: Export configuration

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate layers
        if not layers:
            errors.append("No layers provided for export")

        for layer in layers:
            if not layer or not layer.isValid():
                errors.append(f"Invalid layer: {layer.name() if layer else 'None'}")

        # Validate output path
        if not output_path:
            errors.append("Output path not specified")
        else:
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir, exist_ok=True)
                except Exception as e:
                    errors.append(f"Cannot create output directory: {e}")

            # Check if file exists and overwrite not allowed
            if os.path.exists(output_path) and not config.overwrite:
                errors.append(f"Output file exists and overwrite is disabled: {output_path}")

        # Validate format compatibility
        if config.format == ExportFormat.GEOPACKAGE and len(layers) > 1:
            # Multiple layers to GeoPackage is OK
            pass
        elif len(layers) > 1 and not os.path.isdir(output_path):
            errors.append("Multiple layers require output folder, not file path")

        return errors


# Global convenience function

def create_export_service(
    project: Optional[QgsProject] = None,
    progress_callback: Optional[Callable[[int], None]] = None
) -> ExportService:
    """
    Create export service instance.

    Args:
        project: QGIS project
        progress_callback: Progress callback

    Returns:
        ExportService instance
    """
    return ExportService(project=project, progress_callback=progress_callback)
